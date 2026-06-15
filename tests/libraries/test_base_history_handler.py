import datetime
import unittest
from unittest import mock

import pandas as pd

from libraries.HistoryHandlers.BaseHistoryHandler import BaseHistoryHandler


class TestBaseHistoryHandlerCacheOrdering(unittest.TestCase):
    """
    Regression test for the cache-ordering bug:

    set_history() writes new rows to the DB and then returns get_history(),
    which reads through the still-populated (stale) history cache. The cache
    is only evicted *after* that read in __init__, so the handler's in-memory
    history_df froze at the pre-update snapshot even though the DB was current.

    The handler must end up holding the *post-update* data.
    """

    def _make_handler_class(self, state, stale_date, fresh_date):
        """Build a BaseHistoryHandler subclass that simulates a cached read.

        get_history() returns the stale date while the cache is warm, and the
        fresh date once the cache has been evicted. set_history() mimics the
        real handlers: it "writes" (no-op here) and returns the cached read.
        """

        class FakeHandler(BaseHistoryHandler):
            def gen_table(self_inner):
                # Skip real DB table creation
                pass

            def get_history(self_inner):
                date = stale_date if state['cache_warm'] else fresh_date
                return pd.DataFrame({'Date': [date]})

            def set_history(self_inner, start_date=None, overwrite=False):
                # The DB is now current (fresh_date); the cached read is stale.
                return self_inner.get_history()

        return FakeHandler

    def test_history_df_reflects_db_after_update(self):
        state = {'cache_warm': True}
        fresh_date = datetime.date.today()
        stale_date = fresh_date - datetime.timedelta(days=40)

        FakeHandler = self._make_handler_class(state, stale_date, fresh_date)

        # Evicting the cache makes subsequent get_history() reads return fresh data.
        def fake_evict(tag):
            state['cache_warm'] = False

        with mock.patch(
            'libraries.HistoryHandlers.BaseHistoryHandler.mysql_cache_evict',
            side_effect=fake_evict,
        ):
            handler = FakeHandler()

        self.assertEqual(handler.latest_history_date, fresh_date)


if __name__ == '__main__':
    unittest.main()
