import unittest
from datetime import date, datetime
from unittest.mock import MagicMock

from app.services.stats_service import StatsService, _LANDING_BUNDLE_CACHE


class TestCollectionFreshness(unittest.TestCase):
    def test_collection_date_is_independent_of_later_nlp_update(self):
        _LANDING_BUNDLE_CACHE.clear()
        db = MagicMock()
        results = [MagicMock() for _ in range(7)]
        results[0].fetchone.return_value = (100, 5, date(2022, 1, 1), date(2026, 10, 5), datetime(2026, 10, 11), 20)
        for i in (1, 2, 3, 5, 6):
            results[i].fetchall.return_value = []
        results[4].fetchone.return_value = (datetime(2026, 10, 5, 2, 35),)
        db.execute.side_effect = results
        try:
            payload = StatsService(db).get_landing_bundle()
            self.assertEqual(payload['freshness']['last_collected_at'], '2026-10-05 02:35:00')
            self.assertEqual(payload['freshness']['coverage_status'], 'unverified')
            self.assertIn('2026-10-11', payload['freshness']['last_updated'])
            query = str(db.execute.call_args_list[4].args[0])
            self.assertIn('clean_articles', query)
            self.assertIn('scraped_at <= CURRENT_TIMESTAMP', query)
        finally:
            _LANDING_BUNDLE_CACHE.clear()
