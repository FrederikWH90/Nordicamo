import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from namo_scraper.scraper import ContinuousScraper
from namo_scraper import queue_store
from sitemap_parser import SitemapEntry


class TestIncrementalQueueRepair(unittest.TestCase):
    def make_scraper(self, queue_dir, mode='standard', recovery=False):
        s = ContinuousScraper.__new__(ContinuousScraper)
        s._vpn_check_egress_or_raise = Mock()
        s.exclude_domains = set()
        s.manifest = Mock()
        s.manifest.filter_new_urls.side_effect = lambda domain, urls: [u for u in urls if not u.endswith('/loaded')]
        s.manifest.get_latest_date.return_value = None
        s.no_cutoff = False
        s.force_rescrape = False
        s.include_failed_urls = True
        s.recovery_window_active = recovery
        s.db = None
        s.date_from = s.date_to = None
        s.strict_date_window = False
        s.queue_dir = queue_dir
        s.prefer_rss_domains = s.prefer_wpjson_domains = s.prefer_peertube_api_domains = set()
        s.browser_fallback = False
        s.browser_allowlist = set()
        s.discovery_mode = mode
        parser = Mock()
        parser.parse_domain.return_value = [SitemapEntry('https://example.com/new', None)]
        parser._parse_domain_with_rss.return_value = [SitemapEntry('https://example.com/new', None)]
        s._get_sitemap_parser_for_domain = Mock(return_value=parser)
        s._filter_discovered_urls = Mock(side_effect=lambda domain, urls: urls)
        s.stats_lock = threading.Lock()
        s.stats = {'urls_discovered':0,'urls_filtered_by_manifest':0,'urls_new':0}
        s.domain_run_reports = []
        s.run_started_at_iso = '2026-10-11T12:00:00'
        s.discover_only = True
        return s, parser

    def test_fresh_work_precedes_retry_and_cap_retains_both(self):
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            queue_store.write_queue(q, 'example.com', ['https://example.com/retry', 'https://example.com/loaded'], {})
            s, parser = self.make_scraper(q)
            s.scrape_domain('example.com', 'sweden', max_urls=1)
            parser.parse_domain.assert_called_once()
            self.assertEqual([r['url'] for r in queue_store.load_queue_records(q,'example.com')],
                             ['https://example.com/new','https://example.com/retry'])

    def test_recovery_resumes_without_rediscovering_archive(self):
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            queue_store.write_queue(q,'example.com',['https://example.com/retry'],{})
            s, parser = self.make_scraper(q, recovery=True)
            s.scrape_domain('example.com','sweden')
            parser.parse_domain.assert_not_called()

    def test_daily_uses_feed_and_weekly_uses_broader_discovery(self):
        for mode in ('daily','weekly'):
            with TemporaryDirectory() as tmp:
                s, parser = self.make_scraper(Path(tmp),mode)
                s.scrape_domain('example.com','sweden')
                if mode == 'daily':
                    parser._parse_domain_with_rss.assert_called_once()
                    parser.parse_domain.assert_not_called()
                else:
                    parser.parse_domain.assert_called_once()
