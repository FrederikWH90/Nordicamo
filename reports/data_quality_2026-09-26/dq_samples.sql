\pset format unaligned
\pset fieldsep ' | '
\echo '### document.no: which paywall keyword matches?'
SELECT kw, count(*) FROM (SELECT unnest(regexp_matches(lower(coalesce(title,'')||' '||left(coalesce(content_clean,''),600)), '(kun for abonnenter|for abonnenter|logg inn for|kjøp abonnement|denne artikkelen er|cookie|javascript is disabled|access denied|page not found)', 'g')) kw FROM clean_articles WHERE lower(domain) LIKE '%document.no') x GROUP BY 1 ORDER BY 2 DESC;
\echo '### document.no: 3 random short (<400 chars) articles'
SELECT date, left(title,60), length(content_clean), left(regexp_replace(content_clean,'\s+',' ','g'),300) FROM clean_articles WHERE lower(domain) LIKE '%document.no' AND length(coalesce(content_clean,'')) < 400 ORDER BY random() LIMIT 3;
\echo '### document.no: 2 random paywall-matching articles (opening)'
SELECT date, left(title,60), length(content_clean), left(regexp_replace(content_clean,'\s+',' ','g'),350) FROM clean_articles WHERE lower(domain) LIKE '%document.no' AND lower(left(content_clean,600)) ~ '(for abonnenter|logg inn for)' ORDER BY random() LIMIT 2;
\echo '### Shared identical content per outlet (the repeated text itself)'
WITH g AS (
  SELECT regexp_replace(lower(domain),'^www\.','') o, md5(coalesce(content_clean,'')) h, count(*) c, min(content_clean) txt
  FROM clean_articles WHERE length(coalesce(content_clean,''))>0 GROUP BY 1,2 HAVING count(*) >= 300)
SELECT o, c, left(regexp_replace(txt,'\s+',' ','g'),260) FROM g ORDER BY c DESC;
\echo '### denkorteavis.dk random sample of the repeated-content rows'
WITH h AS (SELECT md5(coalesce(content_clean,'')) h FROM clean_articles WHERE lower(domain) LIKE '%denkorteavis%' GROUP BY 1 ORDER BY count(*) DESC LIMIT 1)
SELECT date, left(title,70), url FROM clean_articles WHERE lower(domain) LIKE '%denkorteavis%' AND md5(coalesce(content_clean,'')) = (SELECT h FROM h) ORDER BY random() LIMIT 3;
\echo '### hemali.no + frihetskamp.no non-article URLs sample'
SELECT regexp_replace(lower(domain),'^www\.',''), left(title,50), url FROM clean_articles WHERE lower(domain) ~ '(hemali|frihetskamp|solidaritet)' AND url ~* '(/tag/|/category/|/kategori/|/author/|/forfatter/|/page/[0-9]+|/arkiv)' ORDER BY random() LIMIT 6;
