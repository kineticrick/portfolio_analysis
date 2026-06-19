import unittest
from types import SimpleNamespace

from libraries.chat.provider import AnthropicProvider, LLMResponse, ToolCall


def _block(**kw):
    return SimpleNamespace(**kw)


class TestNormalize(unittest.TestCase):
    def test_text_only_response(self):
        raw = SimpleNamespace(
            content=[_block(type="text", text="Hello there")],
            stop_reason="end_turn",
        )
        result = AnthropicProvider._normalize(raw)
        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "Hello there")
        self.assertEqual(result.tool_calls, [])

    def test_tool_use_response(self):
        raw = SimpleNamespace(
            content=[
                _block(type="text", text="Let me check"),
                _block(type="tool_use", id="tu_1", name="rank_assets",
                       input={"interval": "6m", "count": 5}),
            ],
            stop_reason="tool_use",
        )
        result = AnthropicProvider._normalize(raw)
        self.assertEqual(len(result.tool_calls), 1)
        tc = result.tool_calls[0]
        self.assertEqual(tc, ToolCall(id="tu_1", name="rank_assets",
                                      arguments={"interval": "6m", "count": 5}))
        # Raw content is preserved so the engine can append it to history.
        self.assertEqual(result.raw_assistant_content, raw.content)
