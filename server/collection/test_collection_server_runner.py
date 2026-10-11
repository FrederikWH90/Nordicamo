import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
spec = importlib.util.spec_from_file_location('collection_runner', Path(__file__).resolve().parents[1] / 'scripts/run_collection_server.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestCollectionRunner(unittest.TestCase):
    def test_failed_load_remains_retryable_and_completed_load_is_skipped(self):
        previous = Path.cwd()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'data/incremental/collection'
            output.mkdir(parents=True)
            file = output / 'incremental_test.parquet'
            file.touch()
            scraper = Mock(domain_run_reports=[{'domain':'example.com','articles_scraped':1}])
            scraper.run_scrape.return_value = {'domains_failed':0,'urls_failed':0}
            db = Mock()
            db.is_connected.return_value = True
            try:
                with patch.object(runner,'ROOT',root), patch.dict(os.environ,{'NAMO_DIR':str(root)}), \
                     patch('namo_scraper.scraper.ContinuousScraper',return_value=scraper) as factory, \
                     patch('db_connector.get_database_connector',return_value=db), \
                     patch('namo_scraper.vpn_preflight.ensure_vpn'), \
                     patch('namo_pipeline.load_incremental_to_db.load_file_to_db',side_effect=[False,True]) as loader, \
                     patch.object(runner.subprocess,'run'):
                    self.assertEqual(runner.run('daily'),1)
                    self.assertEqual(runner.run('weekly'),0)
                    self.assertEqual(runner.run('daily'),0)
                    self.assertEqual(loader.call_count,2)
                    self.assertFalse(scraper.db_write_enabled)
                    self.assertEqual(factory.call_args.kwargs['backfill_days'],14)
                    loaded = json.loads((root/'data/reports/collection/loaded_files.json').read_text())
                    self.assertEqual(loaded,[str(file.resolve())])
            finally:
                os.chdir(previous)
