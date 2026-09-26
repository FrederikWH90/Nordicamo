SET work_mem='256MB';
CREATE TEMP TABLE c AS SELECT id, regexp_replace(lower(domain),'^www\.','') o, country, url, coalesce(title,'') t, coalesce(content_clean,'') x, md5(coalesce(content_clean,'')) h FROM clean_articles;
CREATE TEMP TABLE shared AS SELECT o, h FROM c WHERE length(x) > 0 GROUP BY 1,2 HAVING count(*) >= 20 AND count(DISTINCT t) >= 5;
CREATE TEMP TABLE cls AS
SELECT c.id, c.o, c.country, c.url, c.t,
  CASE
    WHEN c.t IN ('Tack för att du läser – så här läser du vidare!') THEN 'A_paywall_page'
    WHEN s.h IS NOT NULL THEN 'B_same_text_many_titles'
    WHEN c.url ~* '(/attachment/|[?&]attachment_id=|/tag/|/tags/|/category/|/kategori/|/author/|/forfatter/|/skribent/|/page/[0-9]+|/side/[0-9]+|/arkiv/?$)' OR c.t ~* '^(stikkord|kategori|forfatter|tag):' OR c.t ~* ' arkiv(er)?( [-|] |$)' THEN 'C_listing_page'
    WHEN lower(left(c.x, 1500)) ~ '(logg inn for å lese videre|samnytt plus|artikeln fortsätter|det här innehållet är låst|kun for abonnenter|log ind for at læse|vain tilaajille|för att fortsätta läsa)' THEN 'D_teaser_only'
    WHEN length(c.x) < 150 THEN 'E_near_empty'
    ELSE 'OK'
  END AS cat,
  (c.t ~ 'Ã[\u0080-¿]|â€' OR left(c.x,2000) ~ 'Ã[\u0080-¿]|â€') AS mojibake
FROM c LEFT JOIN shared s ON s.o = c.o AND s.h = c.h;
\echo '### totals by category'
SELECT cat, count(*), round(100.0*count(*)/sum(count(*)) over (),1) pct FROM cls GROUP BY 1 ORDER BY 1;
\echo '### garbled text (independent of category)'
SELECT count(*) FILTER (WHERE mojibake) mojibake_rows FROM cls;
\copy (SELECT o outlet, country, count(*) n, count(*) FILTER (WHERE cat='A_paywall_page') a_paywall_page, count(*) FILTER (WHERE cat='B_same_text_many_titles') b_same_text, count(*) FILTER (WHERE cat='C_listing_page') c_listing, count(*) FILTER (WHERE cat='D_teaser_only') d_teaser, count(*) FILTER (WHERE cat='E_near_empty') e_near_empty, count(*) FILTER (WHERE mojibake) garbled_text, round(100.0*count(*) FILTER (WHERE cat IN ('A_paywall_page','B_same_text_many_titles','C_listing_page','E_near_empty'))/count(*),1) pct_unusable, round(100.0*count(*) FILTER (WHERE cat='D_teaser_only')/count(*),1) pct_teaser FROM cls GROUP BY 1,2 ORDER BY pct_unusable DESC, n DESC) TO '/tmp/dq_final_by_outlet.csv' CSV HEADER
\copy (SELECT cat, o outlet, id, url, t title FROM (SELECT *, row_number() OVER (PARTITION BY cat, o ORDER BY random()) r FROM cls WHERE cat <> 'OK') z WHERE r <= 5 ORDER BY cat, o) TO '/tmp/dq_final_samples_for_review.csv' CSV HEADER
\echo '### garbled text by outlet'
SELECT o, count(*) FILTER (WHERE mojibake) g, count(*) n, round(100.0*count(*) FILTER (WHERE mojibake)/count(*),1) pct FROM cls GROUP BY 1 HAVING count(*) FILTER (WHERE mojibake) > 100 ORDER BY 2 DESC;
