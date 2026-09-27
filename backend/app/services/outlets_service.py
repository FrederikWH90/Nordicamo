"""Outlet directory and outlet profiles for the Media Archive.

Outlets are keyed by their canonical domain (lower case, no "www."), so
www/non-www variants are always one outlet. Counts come from clean_articles,
the same analysis-ready view as the rest of the dashboard. Descriptive
metadata (name, format, self-description, links) comes from `actors`, where
missing values were imported as the text "NaN" and are treated as empty.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

OUTLET_KEY_SQL = r"regexp_replace(lower(domain), '^www\.', '')"
ACTOR_KEY_SQL = r"regexp_replace(regexp_replace(lower(trim(actor_domain)), '^https?://', ''), '^www\.|/+$', '', 'g')"
EXCLUDED_TOPICS = {"Other"}
LINK_FIELDS = ("website", "facebook_page", "facebook_group", "twitter", "youtube", "telegram",
               "instagram", "tiktok", "gab", "vkontakte")
SIMILARITY_TTL_SECONDS = 1800
_MISSING = {"", "nan", "none", "null", "n/a"}

_topic_vector_cache: Dict[str, Any] = {"at": 0.0, "vectors": {}, "meta": {}, "centred": {}}


def clean_value(value: Any) -> Optional[str]:
    """Strip text; imported blanks like "NaN" become None."""
    if value is None:
        return None
    text_value = str(value).strip()
    return None if text_value.lower() in _MISSING else text_value


def canonical_outlet(value: Optional[str]) -> str:
    key = (value or "").strip().lower()
    key = re.sub(r"^https?://", "", key)
    key = re.sub(r"^www\.", "", key)
    return key.rstrip("/")


def safe_link(value: Any) -> Optional[str]:
    """Only absolute http(s) links, or bare domains turned into https links."""
    cleaned = clean_value(value)
    if not cleaned:
        return None
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", cleaned, re.IGNORECASE):
        return f"https://{cleaned}"
    return None


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def centred_profiles(vectors: Dict[str, Dict[str, float]], weights: Dict[str, int]) -> Dict[str, Dict[str, float]]:
    """Subtract the article-weighted average profile, leaving what is distinctive per outlet.

    Raw topic shares are dominated by topics every outlet covers (politics), so
    raw cosine similarity is ~0.97 for almost any pair. Centred profiles compare
    what each outlet covers more or less than the Nordic average.
    """
    total = sum(weights.get(o, 0) for o in vectors)
    if not total:
        return {}
    topics = {t for v in vectors.values() for t in v}
    mean = {t: sum(v.get(t, 0.0) * weights.get(o, 0) for o, v in vectors.items()) / total for t in topics}
    return {o: {t: v.get(t, 0.0) - mean[t] for t in topics} for o, v in vectors.items()}


def shared_emphasis(a: Dict[str, float], b: Dict[str, float], limit: int = 2) -> List[str]:
    """Topics both outlets cover more than average, strongest first."""
    both = [(min(a.get(t, 0.0), b.get(t, 0.0)), t) for t in set(a) & set(b)]
    return [t for score, t in sorted(both, reverse=True) if score > 0.01][:limit]


class OutletsService:
    def __init__(self, db: Session):
        self.db = db
        self.db.execute(text("SET LOCAL work_mem = '64MB'"))

    # -- directory ---------------------------------------------------------

    def directory(self) -> Dict[str, Any]:
        has_status = self.db.execute(text("SELECT to_regclass('public.article_content_status') IS NOT NULL")).scalar()
        teaser_join = "LEFT JOIN article_content_status s ON s.article_id = c.id" if has_status else ""
        teaser_count = "count(*) FILTER (WHERE s.status = 'teaser')" if has_status else "0"
        rows = self.db.execute(text(f"""
            WITH stats AS (
                SELECT {OUTLET_KEY_SQL.replace('domain', 'c.domain')} AS outlet,
                       max(c.country) AS country, max(c.partisan) AS partisan,
                       count(*) AS articles, min(c.date) AS first_date, max(c.date) AS last_date,
                       count(*) FILTER (WHERE c.date >= current_date - 30) AS last_30_days,
                       {teaser_count} AS teasers
                FROM clean_articles c {teaser_join}
                WHERE c.domain IS NOT NULL
                GROUP BY 1
            ),
            actor AS (
                SELECT DISTINCT ON ({ACTOR_KEY_SQL}) {ACTOR_KEY_SQL} AS outlet, actor_name, primary_format,
                       partisan_fullcategories
                FROM actors ORDER BY {ACTOR_KEY_SQL}, id
            )
            SELECT s.*, a.actor_name, a.primary_format, a.partisan_fullcategories
            FROM stats s LEFT JOIN actor a USING (outlet)
            ORDER BY s.articles DESC
        """)).mappings().all()

        monthly = self.db.execute(text(f"""
            SELECT {OUTLET_KEY_SQL} AS outlet, to_char(date, 'YYYY-MM') AS month, count(*) AS n
            FROM clean_articles
            WHERE date >= date_trunc('month', current_date) - interval '12 months'
              AND date < date_trunc('month', current_date)
            GROUP BY 1, 2
        """)).fetchall()
        months = [r[0] for r in self.db.execute(text("""
            SELECT to_char(m, 'YYYY-MM') FROM generate_series(
                date_trunc('month', current_date) - interval '12 months',
                date_trunc('month', current_date) - interval '1 month', interval '1 month') AS m
        """)).fetchall()]
        by_outlet: Dict[str, Dict[str, int]] = {}
        for outlet, month, n in monthly:
            by_outlet.setdefault(outlet, {})[month] = int(n)

        outlets = []
        for row in rows:
            key = row["outlet"]
            outlets.append({
                "outlet": key,
                "name": clean_value(row["actor_name"]) or key,
                "country": row["country"],
                "partisan": clean_value(row["partisan"]),
                "partisan_detail": clean_value(row["partisan_fullcategories"]),
                "format": clean_value(row["primary_format"]),
                "articles": int(row["articles"] or 0),
                "first_date": str(row["first_date"]) if row["first_date"] else None,
                "last_date": str(row["last_date"]) if row["last_date"] else None,
                "last_30_days": int(row["last_30_days"] or 0),
                "teasers": int(row["teasers"] or 0),
                "monthly_12": [by_outlet.get(key, {}).get(m, 0) for m in months],
            })
        return {"months": months, "outlets": outlets}

    # -- profile -----------------------------------------------------------

    def _topic_vectors(self) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, float]]]:
        """Share of each outlet's articles tagged with each topic; cached (one scan)."""
        now = time.time()
        if now - _topic_vector_cache["at"] < SIMILARITY_TTL_SECONDS and _topic_vector_cache["vectors"]:
            return _topic_vector_cache["vectors"], _topic_vector_cache["meta"], _topic_vector_cache["centred"]
        totals = self.db.execute(text(f"""
            SELECT {OUTLET_KEY_SQL} AS outlet, count(*), max(country), max(partisan)
            FROM clean_articles WHERE domain IS NOT NULL GROUP BY 1
        """)).fetchall()
        meta = {r[0]: {"articles": int(r[1]), "country": r[2], "partisan": r[3]} for r in totals}
        counts = self.db.execute(text(f"""
            SELECT {OUTLET_KEY_SQL} AS outlet, cat, count(*)
            FROM clean_articles,
                 jsonb_array_elements_text(CASE WHEN jsonb_typeof(categories) = 'array' THEN categories ELSE '[]'::jsonb END) AS cat
            WHERE domain IS NOT NULL
            GROUP BY 1, 2
        """)).fetchall()
        vectors: Dict[str, Dict[str, float]] = {}
        for outlet, topic, n in counts:
            if topic in EXCLUDED_TOPICS or outlet not in meta or not meta[outlet]["articles"]:
                continue
            vectors.setdefault(outlet, {})[topic] = int(n) / meta[outlet]["articles"]
        eligible = {o: v for o, v in vectors.items() if meta[o]["articles"] >= 200}
        centred = centred_profiles(eligible, {o: meta[o]["articles"] for o in eligible})
        _topic_vector_cache.update({"at": now, "vectors": vectors, "meta": meta, "centred": centred})
        return vectors, meta, centred

    def profile(self, outlet: str, latest: int = 10, similar: int = 6) -> Optional[Dict[str, Any]]:
        key = canonical_outlet(outlet)
        if not key:
            return None
        variants = [key, f"www.{key}"]
        stats = self.db.execute(text("""
            SELECT count(*), min(date), max(date), count(*) FILTER (WHERE date >= current_date - 30),
                   max(country), max(partisan)
            FROM clean_articles WHERE lower(domain) = ANY(:variants)
        """), {"variants": variants}).fetchone()
        if not stats or not stats[0]:
            return None

        actor = self.db.execute(text(f"""
            SELECT actor_name, primary_format, secondary_format, partisan_fullcategories, self_description, about,
                   {", ".join(LINK_FIELDS)}
            FROM actors WHERE {ACTOR_KEY_SQL} = :key ORDER BY id LIMIT 1
        """), {"key": key}).mappings().first() or {}

        has_status = self.db.execute(text("SELECT to_regclass('public.article_content_status') IS NOT NULL")).scalar()
        teasers = 0
        if has_status:
            teasers = int(self.db.execute(text("""
                SELECT count(*) FROM clean_articles c JOIN article_content_status s ON s.article_id = c.id
                WHERE lower(c.domain) = ANY(:variants) AND s.status = 'teaser'
            """), {"variants": variants}).scalar() or 0)

        monthly = self.db.execute(text("""
            SELECT to_char(date, 'YYYY-MM') AS month, count(*) FROM clean_articles
            WHERE lower(domain) = ANY(:variants) GROUP BY 1 ORDER BY 1
        """), {"variants": variants}).fetchall()

        teaser_expr = "EXISTS (SELECT 1 FROM article_content_status s WHERE s.article_id = c.id)" if has_status else "false"
        latest_rows = self.db.execute(text(f"""
            SELECT c.date, c.title, c.url, c.categories, {teaser_expr} AS teaser
            FROM clean_articles c WHERE lower(c.domain) = ANY(:variants)
            ORDER BY c.date DESC NULLS LAST, c.id DESC LIMIT :limit
        """), {"variants": variants, "limit": max(1, min(latest, 50))}).fetchall()

        vectors, meta, centred = self._topic_vectors()
        own = vectors.get(key, {})
        country = stats[4]
        country_totals: Dict[str, float] = {}
        country_articles = sum(m["articles"] for m in meta.values() if m["country"] == country)
        for other, vector in vectors.items():
            if meta.get(other, {}).get("country") != country:
                continue
            for topic, share in vector.items():
                country_totals[topic] = country_totals.get(topic, 0.0) + share * meta[other]["articles"]
        country_topics = {t: v / country_articles for t, v in country_totals.items()} if country_articles else {}

        own_centred = centred.get(key, {})
        similar_rows = sorted(
            (
                {"outlet": other, "similarity": round(cosine(own_centred, vector), 3),
                 "shared": shared_emphasis(own_centred, vector), **meta.get(other, {})}
                for other, vector in centred.items()
                if other != key
            ),
            key=lambda r: r["similarity"],
            reverse=True,
        )[:similar] if own_centred else []
        names = {}
        if similar_rows:
            names = dict(self.db.execute(text(f"""
                SELECT {ACTOR_KEY_SQL}, max(actor_name) FROM actors
                WHERE {ACTOR_KEY_SQL} = ANY(:keys) GROUP BY 1
            """), {"keys": [r["outlet"] for r in similar_rows]}).fetchall())
        for row in similar_rows:
            row["name"] = clean_value(names.get(row["outlet"])) or row["outlet"]

        return {
            "outlet": key,
            "name": clean_value(actor.get("actor_name")) or key,
            "country": country,
            "partisan": clean_value(stats[5]),
            "partisan_detail": clean_value(actor.get("partisan_fullcategories")),
            "format": clean_value(actor.get("primary_format")),
            "secondary_format": clean_value(actor.get("secondary_format")),
            "self_description": clean_value(actor.get("self_description")),
            "about": clean_value(actor.get("about")),
            "links": {field: link for field in LINK_FIELDS if (link := safe_link(actor.get(field)))},
            "articles": int(stats[0]),
            "first_date": str(stats[1]) if stats[1] else None,
            "last_date": str(stats[2]) if stats[2] else None,
            "last_30_days": int(stats[3] or 0),
            "teasers": teasers,
            "monthly": [{"month": m, "count": int(n)} for m, n in monthly],
            "topics": sorted(({"topic": t, "share": round(s, 4)} for t, s in own.items()), key=lambda r: -r["share"]),
            "country_topics": {t: round(s, 4) for t, s in country_topics.items()},
            "latest": [
                {"date": str(r[0]) if r[0] else None, "title": r[1], "url": r[2], "categories": r[3] or [], "teaser": bool(r[4])}
                for r in latest_rows
            ],
            "similar": similar_rows,
        }
