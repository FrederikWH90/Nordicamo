# Local and VM recovery — 11 October 2026

Targeted recovery of Derimot and Riks for 28 September–10 October 2026 inclusive. Both environments ran the same scraper source and outlet rules with isolated recovery state and no direct database writes. The user supplied the current VM endpoint, `ucloud@ssh.cloud.sdu.dk:2820`.

## Comparable results

| Outlet / method | Local computer | VM | URL sets agree |
|---|---:|---:|---|
| Derimot, WordPress discovery + browser extraction | 79 | 79 | Yes |
| Riks, paginated archive discovery | 148 | 148 | Yes |

Local feed-only Riks discovery retrieved 27 articles, all dated 8–10 October. It missed most of the requested period. The paginated archive uses `/nyheter?sida={page}` and `/kronikor?sida={page}`. A feed query using `paged=2` repeated the feed instead of reaching older articles.

Earlier runs plus archive runs yielded 154 distinct Riks URLs across routes. Combined with Derimot, the recovery export contains 233 distinct article URLs. There were no publication-date disagreements across the overlapping route results. The archive runs each encountered 135 out-of-window URLs and five HTTP 404 responses; these were excluded, rather than counted as recovered articles. Identical archive sets do not prove a complete census of all publications or sections.

Observed public IPs differed: local `130.226.173.83`, VM `130.225.164.12`, both reported as Danish. ExpressVPN processes were running locally and the local default route used `utun4`. No ExpressVPN client was visible inside the VM. The user described both environments as using different VPNs; public IP checks alone cannot certify the provider or tunnel setup. No VPN configuration was changed.

## Text checks

Eight reproducibly selected local article records were manually inspected for plausible title/body/date alignment. Two additional Derimot route disagreements were inspected: the local extractor omitted long bullet lists, which the VM extractor preserved as relevant article content. The fuller VM versions were selected for those two URLs. Other route text disagreements had similarity at least 95%. Local Trafilatura version: 2.0.0; VM: 2.3.1. The version difference is a plausible explanation for extraction differences; it was not isolated experimentally.

## Database outcome

| Outlet | Distinct recovered | Already in database | Newly inserted and visible |
|---|---:|---:|---:|
| Derimot | 79 | 9 | 70 |
| Riks | 154 | 15 | 139 |
| Total | 233 | 24 | 209 |

The loader reported 209 inserts and zero errors. The orientation synchronization filled all 209 new records; subsequent clean-view checks found zero missing orientations. NLP was not run locally and these records still require normal server inference.

Export: `data_collection/data/recovery_vpn_comparison_20261011/exports/recovered_derimot_riks.parquet`. Server load file: `/home/frede/namo_data_collection/data/incremental/recovery_derimot_riks_20261011.parquet`. Article inventory: `recovered_articles.csv` beside this report. Eight-case audit sample: `data_collection/data/recovery_vpn_comparison_20261011/validation_sample.json`.

The Riks archive rule was installed in the server collector's `config/scraper_rules.json`, preserving its other domain settings. Backup: `config/scraper_rules.pre_riks_20261011.json`. A regression check confirms discovery reaches page 2, retains undated article slugs for subsequent date validation, and excludes off-domain links. That check and three existing rules tests passed. No new frontend/backend deployment was performed in this recovery step.

Daily scheduling, broader weekly reconciliation, production queue repair and per-outlet coverage accounting remain outstanding. This targeted recovery does not establish completeness for the full Nordic collection.
