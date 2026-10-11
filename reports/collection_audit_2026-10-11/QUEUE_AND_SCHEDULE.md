# Queue repair and collection schedule — 11 October 2026

## Installed on the Nordicamo server

- Normal incremental runs discover fresh URLs even when retry queues exist. Database URL hashes hydrate the manifest before queue pruning. Fresh discoveries precede retries; already-loaded URLs are removed.
- Historical recovery retains archive queue resumption. Small queues are preserved instead of discarded.
- URLs beyond a run's extraction limit survive initial persistence, flush checkpoints and final queue updates. Unprocessed and transiently failed URLs stay pending.
- Daily collection: 06:00 Europe/Copenhagen, with up to ten minutes random delay. Uses feed/API discovery where available, fallback discovery where needed, and 14 days overlap before the latest stored date. Extraction limit: 200 new URLs per outlet per scheduled daily run.
- Weekly reconciliation: existing Monday 02:00 timer, with up to fifteen minutes random delay. The service now uses broader configured sitemap/archive discovery and 35 days overlap. These are discovery cutoffs, not a guarantee that every outlet/date is completely covered.
- Both collection modes share an exclusive lock. A job arriving during another collection waits rather than being discarded.
- Collection and loading do not invoke NLP. Both modes run orientation synchronization and the existing applied data-quality checks. Separate GPU admission/inference work remains outstanding.
- Parquet output is durable before loading. Failed loads remain retryable; completed files are tracked. New managed output lives in `data/incremental/collection/`.
- Run JSON records include operational status, timestamps, outlet discovery/attempt/extraction/failure reports and file loading results. `coverage_verified` remains false: successful execution alone does not establish completeness.

## Verification

Thirty-two relevant tests passed locally: three queue/mode checks, one loading-retry check, twenty-six existing recovery checks, and two archive decoding checks. The six new queue/loading/archive checks also passed on the server.

The daily end-to-end pilot on Derimot/Riks completed successfully, inserted six new articles, synchronized six orientations, and applied quality repairs. Its extraction cap left two Derimot URLs in the queue, confirming that unfinished work survived the capped run.

The weekly Riks pilot used the wider archive source and inserted one new article. It completed loading, orientation and quality stages but correctly returned a partial result because two URLs produced HTTP 404 responses. Investigation found misdecoded accented characters in the archive URLs. A targeted UTF-8 decoding fix was regression-tested and deployed; both corrected URLs return HTTP 200. The already-running full daily process retains its imported parser until it ends; subsequent runs use the repaired decoder.

Both timers are enabled. The first collection across the configured startlist was launched on 11 October and is still running at this report's last update. Its full result has not yet been audited. The scheduled daily limit applies to subsequent scheduled runs; the initially launched full run has no extraction cap.

Backend (:8001) and Streamlit (:8501) health checks passed. No application deployment/restart was necessary for these collector-only changes.

## Paths and recovery

Runner: `/home/frede/namo_data_collection/scripts/run_collection_server.py`.

Service definitions: `/home/frede/.config/systemd/user/namo-daily-collection.service` and timer; weekly drop-in: `namo-weekly-scrape.service.d/collection.conf`. Credentials are in an owner-readable environment file at `/home/frede/.config/namo/collection.env`.

Reports: `/home/frede/namo_data_collection/data/reports/collection/`. Shared lock: `data/collection.lock`.

Versioned deployment sources and rollback notes: `server/collection/README.md`. Exact deployed patches are saved beside this report. Pre-change scraper backup: `src/namo_scraper/scraper.pre_queue_20261011.py`; parser encoding backup: `src/sitemap_parser.pre_encoding_20261011.py`. The previous weekly shell script remains available.

Next work: audit the first full run, strengthen outlet-level coverage accounting, audit existing extracted text, and configure separate GPU inference with an availability check.
