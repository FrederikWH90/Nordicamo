# Server collection deployment sources

The runner and regression checks in this directory are versioned copies of files deployed into the separate collection checkout. Deploy the runner to `/home/frede/namo_data_collection/scripts/run_collection_server.py` and the checks to that checkout's `tests/` directory; their path resolution assumes those deployed locations.

Queue changes are preserved in `reports/collection_audit_2026-10-11/queue_scheduler_server.patch`. The archive character-decoding change is preserved in `archive_utf8_server.patch` in the same report directory. Both were applied to the collection checkout, with backups. App frontend/backend code was not changed by this deployment.

Services and timer definitions are under `server/systemd/`. The weekly service uses `namo-weekly-reconciliation.conf` as a drop-in at `/home/frede/.config/systemd/user/namo-weekly-scrape.service.d/collection.conf`.

Run ledgers: `/home/frede/namo_data_collection/data/reports/collection/`. Output and pending-load tracking: `data/incremental/collection/` and `data/reports/collection/loaded_files.json`. Collection processes share `data/collection.lock`.

Rollback scheduling: disable `namo-daily-collection.timer`, remove the weekly service drop-in, and reload the systemd user manager. Do not remove the lock or change scraper files while collection is running. After a run ends, restore `src/namo_scraper/scraper.pre_queue_20261011.py` if rolling back the queue changes, and `src/sitemap_parser.pre_encoding_20261011.py` if rolling back archive decoding. The earlier weekly script and timer remain available.
