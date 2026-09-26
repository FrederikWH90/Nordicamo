-- Read-only data-quality audit of the analysis-ready set (clean_articles).
-- Uses a session TEMP table only; nothing persistent is written.
\timing on
SET work_mem = '256MB';

CREATE TEMP TABLE dq AS
SELECT
  id,
  regexp_replace(lower(domain), '^www\.', '') AS outlet,
  country,
  date,
  url,
  coalesce(title, '') AS title,
  length(coalesce(content_clean, '')) AS clen,
  word_count,
  md5(coalesce(content_clean, '')) AS chash,
  md5(left(regexp_replace(coalesce(content_clean, ''), '\s+', ' ', 'g'), 300)) AS head_hash,
  md5(right(regexp_replace(coalesce(content_clean, ''), '\s+', ' ', 'g'), 300)) AS tail_hash,
  lower(coalesce(title, '') || ' ' || left(coalesce(content_clean, ''), 600)) AS probe
FROM clean_articles;

CREATE INDEX ON dq (outlet);
ANALYZE dq;

-- Per-outlet totals
CREATE TEMP TABLE outlet_n AS SELECT outlet, country, count(*) n FROM dq GROUP BY 1, 2;

-- CHECK 1: same title repeated many times within an outlet
\echo '=== CHECK 1: repeated titles (>=20 copies) ==='
\copy (SELECT d.outlet, d.title, count(*) copies, round(100.0*count(*)/o.n,1) pct_of_outlet, min(d.date) first_seen, max(d.date) last_seen, min(d.url) example_url FROM dq d JOIN outlet_n o USING (outlet) GROUP BY d.outlet, d.title, o.n HAVING count(*) >= 20 ORDER BY copies DESC) TO '/tmp/dq_1_repeated_titles.csv' CSV HEADER

-- CHECK 2: identical full content (non-empty) repeated within an outlet
\echo '=== CHECK 2: identical content (>=5 copies) ==='
\copy (SELECT d.outlet, count(*) copies, round(100.0*count(*)/o.n,1) pct_of_outlet, min(d.title) example_title, min(d.url) example_url, max(d.clen) content_chars FROM dq d JOIN outlet_n o USING (outlet) WHERE d.clen > 0 GROUP BY d.outlet, d.chash, o.n HAVING count(*) >= 5 ORDER BY copies DESC) TO '/tmp/dq_2_identical_content.csv' CSV HEADER

-- CHECK 3: identical opening 300 chars (templated pages, paywall teasers)
\echo '=== CHECK 3: identical openings (>=20 copies) ==='
\copy (SELECT d.outlet, count(*) copies, round(100.0*count(*)/o.n,1) pct_of_outlet, count(DISTINCT d.title) distinct_titles, min(d.title) example_title, min(d.url) example_url FROM dq d JOIN outlet_n o USING (outlet) WHERE d.clen > 0 GROUP BY d.outlet, d.head_hash, o.n HAVING count(*) >= 20 ORDER BY copies DESC) TO '/tmp/dq_3_identical_openings.csv' CSV HEADER

-- CHECK 4: paywall / login / subscription language near the top of the text
\echo '=== CHECK 4: paywall language ==='
\copy (SELECT d.outlet, o.country, o.n, count(*) hits, round(100.0*count(*)/o.n,1) pct_of_outlet, (array_agg(d.url ORDER BY random()))[1:3] sample_urls, (array_agg(d.title ORDER BY random()))[1:3] sample_titles FROM dq d JOIN outlet_n o USING (outlet) WHERE d.probe ~ '(tack för att du läser|läs vidare|bli prenumerant|för prenumeranter|logga in för att|kun for abonnenter|for abonnenter|bliv abonnent|log ind for at|allerede abonnent|denne artikkelen er|logg inn for|kjøp abonnement|tilaa |tilaajille|kirjaudu sisään|vain tilaajille|subscribe to read|subscribers only|this content is for|premium content|plus-artikel|plussartikkel|låst artikel|cookie|javascript is disabled|enable javascript|access denied|403 forbidden|page not found|sidan kunde inte hittas|siden blev ikke fundet|sivua ei löytynyt)' GROUP BY d.outlet, o.country, o.n ORDER BY hits DESC) TO '/tmp/dq_4_paywall_language.csv' CSV HEADER

-- CHECK 5: very short content
\echo '=== CHECK 5: short content (<400 chars) ==='
\copy (SELECT d.outlet, o.country, o.n, count(*) FILTER (WHERE d.clen = 0) empty, count(*) FILTER (WHERE d.clen BETWEEN 1 AND 399) under_400_chars, round(100.0*count(*) FILTER (WHERE d.clen < 400)/o.n,1) pct_of_outlet, (array_agg(d.url ORDER BY random()) FILTER (WHERE d.clen < 400))[1:3] sample_urls FROM dq d JOIN outlet_n o USING (outlet) GROUP BY d.outlet, o.country, o.n HAVING count(*) FILTER (WHERE d.clen < 400) > 0 ORDER BY pct_of_outlet DESC) TO '/tmp/dq_5_short_content.csv' CSV HEADER

-- CHECK 6: non-article URL patterns
\echo '=== CHECK 6: non-article URLs ==='
\copy (SELECT d.outlet, o.n, count(*) hits, round(100.0*count(*)/o.n,1) pct_of_outlet, (array_agg(d.url ORDER BY random()))[1:4] sample_urls FROM dq d JOIN outlet_n o USING (outlet) WHERE d.url ~* '(/tag/|/tags/|/category/|/kategori/|/author/|/forfatter/|/skribent/|/page/[0-9]+|/sida/[0-9]+|/side/[0-9]+|/arkiv/?$|/archive/?$|/search|\?s=|/feed/?$|/wp-json|/login|/logg-inn|/prenumerera|/abonnement|/tilaa|/om-oss|/about|/kontakt|/contact|/privacy|/cookie)' GROUP BY d.outlet, o.n ORDER BY hits DESC) TO '/tmp/dq_6_nonarticle_urls.csv' CSV HEADER

-- Combined per-outlet scorecard: rows caught by ANY check (dedupe by id)
\echo '=== SCORECARD ==='
CREATE TEMP TABLE rep_titles AS SELECT outlet, title FROM dq GROUP BY 1, 2 HAVING count(*) >= 20;
CREATE TEMP TABLE rep_heads AS SELECT outlet, head_hash FROM dq WHERE clen > 0 GROUP BY 1, 2 HAVING count(*) >= 20 AND count(DISTINCT title) <= 3;
\copy (SELECT o.outlet, o.country, o.n, count(*) FILTER (WHERE flagged) suspect, round(100.0*count(*) FILTER (WHERE flagged)/o.n,1) pct_suspect FROM outlet_n o JOIN (SELECT d.outlet, (rt.title IS NOT NULL OR rh.head_hash IS NOT NULL OR d.clen < 400 OR d.probe ~ '(tack för att du läser|kun for abonnenter|for abonnenter|bliv abonnent|logg inn for|vain tilaajille|subscribers only|javascript is disabled|access denied|page not found)') flagged FROM dq d LEFT JOIN rep_titles rt ON rt.outlet = d.outlet AND rt.title = d.title LEFT JOIN rep_heads rh ON rh.outlet = d.outlet AND rh.head_hash = d.head_hash) x USING (outlet) GROUP BY o.outlet, o.country, o.n ORDER BY suspect DESC) TO '/tmp/dq_0_scorecard.csv' CSV HEADER

SELECT count(*) AS analysis_ready_rows FROM dq;
