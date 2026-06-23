import unittest
from libraries.chat import config


class TestConfig(unittest.TestCase):
    def test_model_is_sonnet(self):
        self.assertEqual(config.MODEL, "claude-sonnet-4-6")

    def test_limits_are_positive_ints(self):
        self.assertGreater(config.MAX_TOKENS, 0)
        self.assertGreater(config.MAX_TOOL_ITERATIONS, 0)
        self.assertGreater(config.MAX_HISTORY_TURNS, 0)

    def test_system_prompt_mentions_tools_and_no_guessing(self):
        prompt = config.SYSTEM_PROMPT.lower()
        self.assertIn("tool", prompt)
        self.assertIn("guess", prompt)

    def test_system_prompt_mentions_filtering(self):
        lowered = config.SYSTEM_PROMPT.lower()
        self.assertIn("filter", lowered)
        self.assertIn("account_type", lowered)
