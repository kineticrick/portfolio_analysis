import os
# Import the dashboard tab in DEMO mode so no DB/yfinance is needed.
os.environ.setdefault("PORTFOLIO_DEMO_MODE", "1")

import unittest


class TestChatTabImport(unittest.TestCase):
    def test_module_exposes_layout_and_store_ids(self):
        from visualization.dash.portfolio_dashboard.tabs import chat_tab
        self.assertTrue(hasattr(chat_tab, "chat_tab"))
        self.assertEqual(chat_tab.HISTORY_STORE_ID, "chat-history-store")
        self.assertEqual(chat_tab.THREAD_STORE_ID, "chat-thread-store")
        self.assertEqual(chat_tab.VIEW_CONTEXT_STORE_ID, "view-context-store")
