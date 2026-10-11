# Collection improvements — progress on 11 October 2026

## Step 1: dashboard coverage correction deployed

Approved by the user after staging health verification. Production commit: `1e6577b`; staging commit: `c938215`. Previous production commit: `3020c88`.

- Reporting counts now end on the Sunday before the most recent observed collection day, rather than assuming a two-day collection lag. With the current database, this is 28 September–4 October 2026.
- The observation uses `MAX(scraped_at)` from the clean article view, independently of publication dates and later NLP/database updates. This is an observed extraction timestamp, not proof that every outlet was successfully checked.
- All reporting counts are explicitly provisional. Week-on-week percentages are suppressed until coverage can be verified. Country sparklines use the same window as their headline counts.
- The unsupported “collecting daily” claim is replaced by “recurring collection”.
- Missing collection metadata produces no country reporting window, instead of silently falling back to today's date.

Validation: 21 activity-helper tests, 9 landing-page tests, and 1 backend freshness test passed. Staging backend (:8021) and Streamlit (:8502) passed health checks. After deployment, production backend (:8001) and Streamlit (:8501) passed health checks. Both API payloads report collection observed at `2026-10-05 02:35:53.636975` with `coverage_status=unverified`.

Rollback on the server: `./server/deploy/rollback.sh production 3020c88` from `/home/frede/NAMO_nov25`.

## Steps 2–4: pending

Queue repair is being prepared locally. Normal incremental runs will discover fresh URLs even if retries remain, prune URLs already in the manifest/database, and put fresh work before queued retries. Historical recovery keeps its archive-resume behavior. Existing recovery-discovery tests (26) passed; dedicated queue regression checks and server deployment remain outstanding.

Before starting or scheduling new scraping, a clarification is pending: the server has no ExpressVPN client, while `data_collection/AGENTS.md` requires ExpressVPN. The existing server collector accepts its Danish public IP instead. The user was asked whether to retain that server connection or require VPN setup.

Daily collection, weekly archive reconciliation, Derimot/Riks recovery, per-outlet accounting, and separate GPU admission checks have not yet been deployed. Current production collection remains on its existing weekly schedule.
