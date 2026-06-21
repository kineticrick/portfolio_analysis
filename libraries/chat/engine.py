"""The tool-calling loop. Pure Python; no Dash, no direct SDK use."""

from libraries.chat import tools
from libraries.chat.config import (SYSTEM_PROMPT, MAX_TOOL_ITERATIONS,
                                   MAX_HISTORY_TURNS)


def _build_system(view_context):
    """Append ambient view context (Level-1 awareness) to the system prompt."""
    if view_context:
        parts = []
        dim = view_context.get("dimension")
        interval = view_context.get("interval")
        if dim:
            parts.append(f"dimension={dim}")
        if interval:
            parts.append(f"interval={interval}")
        if parts:
            return (SYSTEM_PROMPT + "\n\nThe user is currently viewing: "
                    + ", ".join(parts) + ". Resolve vague references like "
                    "'this' against that context.")
    return SYSTEM_PROMPT


def run(provider, handler, prior_turns, user_message, view_context):
    """Answer one user message. Returns (answer_text, [figures]).

    prior_turns: list of {"role": "user"|"assistant", "text": str}. Each turn's
    `text` must be PROSE (the persisted plain-text transcript). Tool-call rounds
    happen only inside this run and must never be passed back in via prior_turns.
    """
    system = _build_system(view_context)
    trimmed = prior_turns[-MAX_HISTORY_TURNS:]
    messages = [{"role": t["role"], "content": t["text"]} for t in trimmed]
    messages.append({"role": "user", "content": user_message})

    figures = []
    for _ in range(MAX_TOOL_ITERATIONS):
        resp = provider.create(system, messages, tools.TOOL_SCHEMAS)
        if not resp.tool_calls:
            return (resp.text or ""), figures

        messages.append({"role": "assistant",
                         "content": resp.raw_assistant_content})
        tool_results = []
        for tc in resp.tool_calls:
            text, fig = tools.dispatch(handler, tc.name, tc.arguments)
            if fig is not None:
                figures.append(fig)
            tool_results.append({"type": "tool_result", "tool_use_id": tc.id,
                                 "content": text})
        messages.append({"role": "user", "content": tool_results})

    return ("I made too many tool calls without finishing — please refine "
            "your question."), figures
