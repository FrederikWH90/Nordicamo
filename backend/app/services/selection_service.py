"""Describe one article selection: how many, what is inside, and a sample.

Powers the Research Workshop. Returns metadata only (never article text).

Keyword syntax (parsed here into a Postgres tsquery, 'simple' configuration,
matching the GIN index idx_articles_fts_simple on title + content):

    klimat              the word "klimat"
    klimat*             words starting with "klimat" (klimatet, klimatkris, ...)
    "grønne omstilling" the exact phrase
    covid OR corona     either word
    -vaccine            exclude articles containing the word
    words side by side  all of them (AND)
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.articles_service import normalize_outlets

COUNTRIES = ("denmark", "finland", "norway", "sweden")
ORIENTATIONS = ("Right", "Left", "Other")
MAX_SAMPLE = 100
TOP_OUTLETS = 30
MAX_QUERY_TERMS = 20

FTS_DOCUMENT = "to_tsvector('simple'::regconfig, coalesce(title, '') || ' ' || coalesce(content, ''))"

_TOKEN_RE = re.compile(r'-?"[^"]*"|\S+')
_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def build_tsquery(query: Optional[str]) -> Optional[str]:
    """Translate researcher keyword syntax into a safe to_tsquery string.

    Every lexeme is reduced to word characters, so user input can never inject
    tsquery operators. Returns None when nothing searchable remains.
    """
    if not query or not query.strip():
        return None
    clauses: List[str] = []
    pending_or = False
    for raw in _TOKEN_RE.findall(query)[:MAX_QUERY_TERMS]:
        if raw == "OR":
            pending_or = bool(clauses)
            continue
        negate = raw.startswith("-") and len(raw) > 1
        token = raw[1:] if negate else raw
        if token.startswith('"'):
            words = [w.lower() for w in _WORD_RE.findall(token)]
            if not words:
                continue
            term = " <-> ".join(words)
            term = f"({term})" if len(words) > 1 else term
        else:
            prefix = token.endswith("*")
            words = [w.lower() for w in _WORD_RE.findall(token)]
            if not words:
                continue
            # "covid-19" -> covid <-> 19 ; "klimat*" -> klimat:*
            parts = [f"{w}:*" if prefix and i == len(words) - 1 else w for i, w in enumerate(words)]
            term = " <-> ".join(parts)
            term = f"({term})" if len(parts) > 1 else term
        if negate:
            term = f"!{term}"
        if pending_or and clauses and not negate:
            clauses[-1] = f"({clauses[-1]} | {term})"
        else:
            clauses.append(term)
        pending_or = False
    return " & ".join(clauses) if clauses else None


def _clean_list(values: Optional[List[str]]) -> List[str]:
    return [v.strip() for v in values or [] if v and v.strip()]


class SelectionService:
    def __init__(self, db: Session):
        self.db = db

    def _has_content_status(self) -> bool:
        return self.db.execute(text("SELECT to_regclass('public.article_content_status') IS NOT NULL")).scalar()

    def _where(
        self,
        countries: List[str],
        date_from: Optional[str],
        date_to: Optional[str],
        partisan: Optional[str],
        outlets: List[str],
        topics: List[str],
        tsquery: Optional[str],
    ) -> tuple[str, Dict[str, Any]]:
        conditions = ["date IS NOT NULL"]
        params: Dict[str, Any] = {}
        countries = [c.lower() for c in countries if c.lower() in COUNTRIES]
        if countries:
            conditions.append("country = ANY(:countries)")
            params["countries"] = countries
        if date_from:
            conditions.append("date >= CAST(:date_from AS date)")
            params["date_from"] = date_from
        if date_to:
            conditions.append("date <= CAST(:date_to AS date)")
            params["date_to"] = date_to
        if partisan in ORIENTATIONS:
            conditions.append("partisan = :partisan")
            params["partisan"] = partisan
        if outlets:
            conditions.append("LOWER(domain) = ANY(:outlets)")
            params["outlets"] = normalize_outlets(outlets)
        if topics:
            conditions.append("categories ?| CAST(:topics AS text[])")
            params["topics"] = topics
        if tsquery:
            conditions.append(f"{FTS_DOCUMENT} @@ to_tsquery('simple'::regconfig, :tsq)")
            params["tsq"] = tsquery
        return " AND ".join(conditions), params

    def describe(
        self,
        countries: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        partisan: Optional[str] = None,
        outlets: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        q: Optional[str] = None,
        sample_size: int = 25,
        order: str = "random",
        seed: str = "nordicamo",
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        tsquery = build_tsquery(q)
        where, params = self._where(
            _clean_list(countries), date_from, date_to, partisan, _clean_list(outlets), _clean_list(topics), tsquery
        )
        has_status = self._has_content_status()
        teaser_join = "LEFT JOIN article_content_status s ON s.article_id = sel.id" if has_status else ""
        teaser_expr = "(s.status = 'teaser')" if has_status else "false"
        params["sample_size"] = max(0, min(int(sample_size or 0), MAX_SAMPLE))
        params["seed"] = str(seed or "nordicamo")[:40]
        params["top_outlets"] = TOP_OUTLETS
        sample_order = "sel.date DESC NULLS LAST, sel.id DESC" if order == "newest" else "md5(sel.id::text || :seed)"

        sql = text(f"""
            WITH sel AS MATERIALIZED (
                SELECT id, date, country, regexp_replace(lower(domain), '^www\\.', '') AS outlet,
                       partisan, categories, title, url
                FROM clean_articles
                WHERE {where}
            ),
            tagged AS MATERIALIZED (
                SELECT sel.*, {teaser_expr} AS teaser FROM sel {teaser_join}
            ),
            totals AS (
                SELECT count(*) AS n, count(*) FILTER (WHERE teaser) AS teasers,
                       count(DISTINCT outlet) AS outlets, min(date) AS first_date, max(date) AS last_date
                FROM tagged
            ),
            by_country AS (
                SELECT coalesce(jsonb_agg(jsonb_build_object('country', country, 'count', n) ORDER BY n DESC), '[]'::jsonb) AS j
                FROM (SELECT country, count(*) AS n FROM tagged GROUP BY 1) x
            ),
            by_outlet AS (
                SELECT coalesce(jsonb_agg(jsonb_build_object(
                           'outlet', outlet, 'country', country, 'partisan', partisan, 'count', n, 'teasers', t
                       ) ORDER BY n DESC), '[]'::jsonb) AS j
                FROM (
                    SELECT outlet, max(country) AS country, max(partisan) AS partisan,
                           count(*) AS n, count(*) FILTER (WHERE teaser) AS t
                    FROM tagged GROUP BY 1 ORDER BY n DESC LIMIT :top_outlets
                ) x
            ),
            by_month AS (
                SELECT coalesce(jsonb_agg(jsonb_build_object('month', m, 'country', country, 'count', n) ORDER BY m, country), '[]'::jsonb) AS j
                FROM (SELECT to_char(date, 'YYYY-MM') AS m, country, count(*) AS n FROM tagged GROUP BY 1, 2) x
            ),
            by_topic AS (
                SELECT coalesce(jsonb_agg(jsonb_build_object('topic', topic, 'count', n) ORDER BY n DESC), '[]'::jsonb) AS j
                FROM (
                    SELECT cat AS topic, count(*) AS n
                    FROM tagged, jsonb_array_elements_text(CASE WHEN jsonb_typeof(categories) = 'array' THEN categories ELSE '[]'::jsonb END) AS cat
                    GROUP BY 1
                ) x
            ),
            sample AS (
                SELECT coalesce(jsonb_agg(jsonb_build_object(
                           'id', id, 'date', date, 'country', country, 'outlet', outlet, 'partisan', partisan,
                           'title', title, 'url', url, 'categories', categories, 'teaser', teaser
                       ) ORDER BY rn), '[]'::jsonb) AS j
                FROM (
                    SELECT sel.*, row_number() OVER (ORDER BY {sample_order}) AS rn
                    FROM tagged sel ORDER BY {sample_order} LIMIT :sample_size
                ) x
            )
            SELECT totals.n, totals.teasers, totals.outlets, totals.first_date, totals.last_date,
                   by_country.j, by_outlet.j, by_month.j, by_topic.j, sample.j
            FROM totals, by_country, by_outlet, by_month, by_topic, sample
        """)
        # With the default 4MB, prefix searches re-check article text row by row
        # (3.7 s for "ukrain*"); 64MB keeps it in the index (0.1 s). Transaction-scoped.
        self.db.execute(text("SET LOCAL work_mem = '64MB'"))
        row = self.db.execute(sql, params).fetchone()
        return {
            "total": int(row[0] or 0),
            "teasers": int(row[1] or 0),
            "outlets": int(row[2] or 0),
            "first_date": str(row[3]) if row[3] else None,
            "last_date": str(row[4]) if row[4] else None,
            "by_country": row[5] or [],
            "by_outlet": row[6] or [],
            "by_month": row[7] or [],
            "by_topic": row[8] or [],
            "sample": row[9] or [],
            "query": {"keywords": q or None, "tsquery": tsquery},
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
