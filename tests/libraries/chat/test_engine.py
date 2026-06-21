import unittest

from libraries.chat import engine, tools
from libraries.chat.provider import LLMResponse, ToolCall
from tests.libraries.chat.fakes import make_fake_handler, ScriptedProvider


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.h = make_fake_handler()

    def test_direct_text_answer_no_tools(self):
        provider = ScriptedProvider([
            LLMResponse(text="Hi!", tool_calls=[], stop_reason="end_turn",
                        raw_assistant_content=[]),
        ])
        text, figs = engine.run(provider, self.h, prior_turns=[],
                                 user_message="hello", view_context={})
        self.assertEqual(text, "Hi!")
        self.assertEqual(figs, [])

    def test_tool_round_then_answer_collects_figure(self):
        provider = ScriptedProvider([
            LLMResponse(text=None, stop_reason="tool_use",
                        tool_calls=[ToolCall(id="t1", name="show_ranked_bar",
                                             arguments={"interval": "6m",
                                                        "count": 2})],
                        raw_assistant_content=[{"type": "tool_use", "id": "t1",
                                                "name": "show_ranked_bar",
                                                "input": {"interval": "6m",
                                                          "count": 2}}]),
            LLMResponse(text="Here is the chart.", tool_calls=[],
                        stop_reason="end_turn", raw_assistant_content=[]),
        ])
        text, figs = engine.run(provider, self.h, prior_turns=[],
                                user_message="top 2 over 6m", view_context={})
        self.assertEqual(text, "Here is the chart.")
        self.assertEqual(len(figs), 1)

    def test_iteration_cap(self):
        # Always asks for a tool -> engine must stop and not loop forever.
        def tool_resp():
            return LLMResponse(
                text=None, stop_reason="tool_use",
                tool_calls=[ToolCall(id="t", name="get_portfolio_summary",
                                     arguments={})],
                raw_assistant_content=[{"type": "tool_use", "id": "t",
                                        "name": "get_portfolio_summary",
                                        "input": {}}])
        provider = ScriptedProvider([tool_resp() for _ in range(10)])
        text, figs = engine.run(provider, self.h, prior_turns=[],
                                user_message="loop", view_context={})
        self.assertIn("too many", text.lower())
        self.assertEqual(len(provider.calls), 5)

    def test_prior_turns_included_in_messages(self):
        provider = ScriptedProvider([
            LLMResponse(text="ok", tool_calls=[], stop_reason="end_turn",
                        raw_assistant_content=[]),
        ])
        engine.run(provider, self.h,
                   prior_turns=[{"role": "user", "text": "earlier"}],
                   user_message="now", view_context={})
        sent = provider.calls[0]["messages"]
        self.assertEqual(sent[0], {"role": "user", "content": "earlier"})
        self.assertEqual(sent[-1], {"role": "user", "content": "now"})

    def test_build_system_only_interval_omits_none_dimension(self):
        sys = engine._build_system({"interval": "6m"})
        self.assertIn("interval=6m", sys)
        self.assertNotIn("None", sys)
        self.assertNotIn("dimension=", sys)

    def test_build_system_both_fields(self):
        sys = engine._build_system({"dimension": "Sector", "interval": "6m"})
        self.assertIn("dimension=Sector", sys)
        self.assertIn("interval=6m", sys)

    def test_build_system_empty_returns_base(self):
        from libraries.chat.config import SYSTEM_PROMPT
        self.assertEqual(engine._build_system({}), SYSTEM_PROMPT)
