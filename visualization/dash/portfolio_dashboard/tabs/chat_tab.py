import os

from dash import callback, dcc, html, Input, Output, State, no_update
import dash_mantine_components as dmc
import plotly.graph_objs as go

from visualization.dash.portfolio_dashboard.globals import *
from libraries.chat import engine
from libraries.chat.provider import AnthropicProvider

HISTORY_STORE_ID = "chat-history-store"
THREAD_STORE_ID = "chat-thread-store"
VIEW_CONTEXT_STORE_ID = "view-context-store"

# One provider instance reused across queries (only constructed if a key exists).
_PROVIDER = None


def _get_provider():
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = AnthropicProvider()
    return _PROVIDER


def _render_thread(thread):
    """Turn the persisted thread (list of dicts) into message components."""
    bubbles = []
    for entry in thread:
        align = "flex-end" if entry["role"] == "user" else "flex-start"
        color = "blue" if entry["role"] == "user" else "gray"
        children = [dcc.Markdown(entry["text"])] if entry.get("text") else []
        for fig_dict in entry.get("figures", []):
            children.append(dcc.Graph(figure=go.Figure(fig_dict)))
        bubbles.append(
            dmc.Paper(children, shadow="xs", p="sm", withBorder=True,
                      style={"alignSelf": align, "maxWidth": "85%",
                             "background": "var(--mantine-color-%s-0)" % color}))
    return dmc.Stack(bubbles, gap="sm")


@callback(
    Output(THREAD_STORE_ID, "data"),
    Output(HISTORY_STORE_ID, "data"),
    Output("chat-input", "value"),
    Input("chat-send", "n_clicks"),
    State("chat-input", "value"),
    State(HISTORY_STORE_ID, "data"),
    State(THREAD_STORE_ID, "data"),
    State(VIEW_CONTEXT_STORE_ID, "data"),
    prevent_initial_call=True,
)
def on_send(n_clicks, user_text, history, thread, view_context):
    if not user_text or not user_text.strip():
        return no_update, no_update, no_update
    history = history or []
    thread = thread or []

    if not os.environ.get("ANTHROPIC_API_KEY"):
        answer, figures = ("Chat needs an ANTHROPIC_API_KEY environment "
                           "variable to be set.", [])
    else:
        try:
            answer, figs = engine.run(_get_provider(), DASH_HANDLER,
                                      prior_turns=history,
                                      user_message=user_text,
                                      view_context=view_context or {})
            figures = [f.to_dict() for f in figs]
        except Exception as exc:
            answer, figures = (f"Sorry, I hit an error: {exc}", [])

    thread = thread + [{"role": "user", "text": user_text},
                       {"role": "assistant", "text": answer, "figures": figures}]
    history = history + [{"role": "user", "text": user_text},
                         {"role": "assistant", "text": answer}]
    return thread, history, ""


@callback(
    Output("chat-thread", "children"),
    Input(THREAD_STORE_ID, "data"),
)
def render(thread):
    return _render_thread(thread or [])


chat_tab = dmc.Container(
    [
        dcc.Store(id=HISTORY_STORE_ID, data=[]),
        dcc.Store(id=THREAD_STORE_ID, data=[]),
        # Populated by other tabs later (Level-1 awareness seam). Empty for now.
        dcc.Store(id=VIEW_CONTEXT_STORE_ID, data={}),
        dmc.Title("Ask your portfolio", order=2, mb="md"),
        html.Div(id="chat-thread", style={"minHeight": "400px",
                                          "marginBottom": "1rem"}),
        dmc.Group([
            dcc.Input(id="chat-input", type="text",
                      placeholder="e.g. Top 5 assets in my discretionary account "
                                  "over the last 6 months",
                      style={"flex": 1}),
            dmc.Button("Send", id="chat-send"),
        ], align="flex-end"),
    ],
    fluid=True,
)
