# Server cross-check — 11 October 2026

At the user's explicit request, collection was also tested from the Nordicamo production server, `frede@212.27.13.34:2111`, using its existing connection. These were isolated, date-bounded recovery runs without direct database writes, launched through transient systemd user services.

Period: 28 September–10 October 2026 inclusive.

| Comparable discovery method | Local | VM | Nordicamo server after repair |
|---|---:|---:|---:|
| Derimot WordPress discovery | 79 | 79 | 79 |
| Riks paginated archive | 148 | 148 | 148 |

Final server URL sets exactly match the corresponding local/VM sets. Derimot publication dates also agree with the previously validated recovery export. The server found no additional URLs beyond the earlier 233-article union, so no additional database load was needed. The earlier 209 new rows remain the recovery outcome.

## Server-specific issue repaired

The first server run retrieved only 74 Derimot articles. Its older WordPress discovery implementation used `modified_gmt` during historical date filtering, while the local/VM code used publication dates. The initial discovery included six articles subsequently excluded as out of window and omitted five valid 28 September articles.

The server parser now uses publication dates and publication ordering when an upper recovery bound is provided, and sends an exclusive WordPress `before` bound at midnight after the requested final day. Normal incremental behavior retains its existing modification ordering. The existing regression test `test_wpjson_historical_window_uses_publication_dates_and_before_bound` passed on the server. A clean rerun retrieved all 79 Derimot articles without failures. This comparison reveals a code-version difference; it does not provide evidence of route-specific blocking.

Server backup: `/home/frede/namo_data_collection/src/sitemap_parser.pre_datefix_20261011.py`. Exact change: `server_wp_datefix.patch` beside this report. Initial log: `server_route_scrape.log`. Recovery outputs were downloaded to `data_collection/data/recovery_vpn_server_download_20261011/`.

Services `namo-three-route-probe-20261011.service` and `namo-three-route-datefix-20261011.service` both completed successfully. No frontend/backend deployment or local inference was performed. These checks cover the two affected outlets; they do not establish completeness for the entire Nordic collection.
