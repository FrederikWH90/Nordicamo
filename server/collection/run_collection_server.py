#!/usr/bin/env python3
"""Daily discovery and weekly reconciliation; durable loading without inference."""
import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def run(mode, domains=None, max_urls=None):
    from namo_scraper.scraper import ContinuousScraper
    from namo_scraper.vpn_preflight import ensure_vpn, parse_allowed_countries
    from namo_pipeline.load_incremental_to_db import load_file_to_db
    from db_connector import get_database_connector

    os.chdir(ROOT)
    reports = ROOT / 'data/reports/collection'
    reports.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    run_id = started.strftime('%Y%m%dT%H%M%S%fZ')
    ledger_path = reports / f'{mode}_{run_id}.json'
    record = {'run_id': run_id, 'mode': mode, 'started_at': started.isoformat(),
              'status': 'running', 'coverage_verified': False}
    ledger_path.write_text(json.dumps(record, indent=2))
    def checkpoint():
        temp = ledger_path.with_suffix('.tmp')
        temp.write_text(json.dumps(record, indent=2, default=str))
        temp.replace(ledger_path)
    try:
        allowed = parse_allowed_countries('Denmark')
        ensure_vpn(require=True, allowed_countries=allowed, manage_vpn=False,
            vpn_location=None, vpn_cli_path=None, rotate_on_fail=False,
            rotate_max_attempts=0, timeout_s=15)
        db = get_database_connector()
        if not db.is_connected():
            raise RuntimeError('Database unavailable: cannot prune already-loaded URLs')
        scraper = ContinuousScraper(use_db=False, workers=4, timeout=15,
            browser_fallback=True, backfill_days=14 if mode == 'daily' else 35,
            discovery_mode=mode, vpn_allowed_countries=allowed,
            vpn_check_every_s=300, flush_every=100)
        # Read database dates/hashes, but load only through the durable loader.
        scraper.db = db
        scraper.db_write_enabled = False
        scraper.output_dir = ROOT / 'data/incremental/collection'
        scraper.output_dir.mkdir(parents=True, exist_ok=True)
        stats = scraper.run_scrape(domains=domains, max_urls_per_domain=max_urls)
        record['stats'] = stats
        record['outlets'] = scraper.domain_run_reports
        checkpoint()
        # Failed loads from previous runs are retried even if discovery yields none.
        loaded_path = reports / 'loaded_files.json'
        loaded = set(json.loads(loaded_path.read_text())) if loaded_path.exists() else set()
        load_results = []
        for path in sorted(scraper.output_dir.glob('incremental_*.parquet')):
            key = str(path.resolve())
            if key in loaded:
                continue
            success = load_file_to_db(path)
            load_results.append({'file': key, 'loaded': success})
            if success:
                loaded.add(key)
                temp = loaded_path.with_suffix('.tmp')
                temp.write_text(json.dumps(sorted(loaded), indent=2))
                temp.replace(loaded_path)
            record['loads'] = load_results
            checkpoint()
        subprocess.run([sys.executable, 'scripts/sync_article_orientation.py'], check=True)
        app_root = Path(os.environ.get('NAMO_DIR', '/home/frede/NAMO_nov25'))
        quality = app_root / 'scripts/flag_data_quality.py'
        if quality.exists():
            subprocess.run([str(app_root / 'backend/.venv/bin/python'), str(quality), '--apply'], check=True)
        record['status'] = ('partial' if stats.get('domains_failed', 0) or stats.get('urls_failed', 0)
                            or any(r.get('note') == 'no_sitemap_entries' for r in record['outlets'])
                            or any(not r['loaded'] for r in load_results) else 'finished')
        # Finished is an operational status, never a claim of complete coverage.
        return 0 if record['status'] == 'finished' else 1
    except Exception as exc:
        record['status'] = 'failed'
        record['error'] = str(exc)
        raise
    finally:
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        checkpoint()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['daily', 'weekly'], required=True)
    parser.add_argument('--domains')
    parser.add_argument('--max-urls', type=int)
    args = parser.parse_args()
    lock_path = ROOT / 'data/collection.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        # A queued run waits for the current collector; it does not lose its turn.
        fcntl.flock(lock, fcntl.LOCK_EX)
        raise SystemExit(run(args.mode, args.domains.split(',') if args.domains else None, args.max_urls))
