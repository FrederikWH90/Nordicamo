"""Statistics service for computing analytics."""

from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from itertools import combinations
import math
import logging

logger = logging.getLogger(__name__)
_DOMAIN_PARTISAN_CACHE: Dict[str, Dict[str, Any]] = {}
_DOMAIN_PARTISAN_CACHE_TTL_SECONDS = 300
_LANDING_BUNDLE_CACHE: Dict[str, Dict[str, Any]] = {}
_LANDING_BUNDLE_CACHE_TTL_SECONDS = 300
_ANALYSIS_BUNDLE_CACHE: Dict[str, Dict[str, Any]] = {}
_ANALYSIS_BUNDLE_CACHE_TTL_SECONDS = 300

CATEGORY_EXPANSION_JOIN = """
CROSS JOIN LATERAL jsonb_array_elements_text(categories) AS raw_category(category_text)
CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE
        WHEN raw_category.category_text ~ '^\\s*\\[\\s*"' THEN raw_category.category_text::jsonb
        ELSE jsonb_build_array(raw_category.category_text)
    END
) AS expanded_category(category)
"""


def domain_variants(value: str) -> List[str]:
    base = (value or "").strip().lower()
    if not base:
        return []
    variants = {base}
    if base.startswith("www."):
        variants.add(base[4:])
    else:
        variants.add(f"www.{base}")
    return list(variants)


def canonical_domain(value: str) -> str:
    base = (value or "").strip().lower()
    if base.startswith("www."):
        return base[4:]
    return base


# SQL fragment: merge www.example.com and example.com in aggregations.
CANONICAL_DOMAIN_SQL = "REGEXP_REPLACE(LOWER(domain), '^www\\.', '')"


def _safe_share(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return float(count) / float(total)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _jensen_shannon_divergence(vec_a: List[float], vec_b: List[float]) -> float:
    eps = 1e-12
    m = [(a + b) / 2.0 for a, b in zip(vec_a, vec_b)]

    def _kl(p: List[float], q: List[float]) -> float:
        total = 0.0
        for pi, qi in zip(p, q):
            if pi <= 0.0:
                continue
            total += pi * math.log2(max(pi, eps) / max(qi, eps))
        return total

    return 0.5 * _kl(vec_a, m) + 0.5 * _kl(vec_b, m)


class StatsService:
    """Service for computing statistics."""
    
    def __init__(self, db: Session):
        self.db = db

    def _get_domain_partisan_lookup(self, country: Optional[str] = None) -> Dict[str, str]:
        """Map outlet domains to startlist orientation labels from actors."""
        cache_key = (country or "__all__").strip().lower()
        now = datetime.utcnow().timestamp()
        cached = _DOMAIN_PARTISAN_CACHE.get(cache_key)
        if cached and now - float(cached.get("created_at", 0)) <= _DOMAIN_PARTISAN_CACHE_TTL_SECONDS:
            return dict(cached.get("values", {}))

        params: Dict[str, Any] = {}
        country_filter = ""
        if country:
            country_filter = "AND LOWER(actor_country) = LOWER(:country)"
            params["country"] = country

        query = text(f"""
            WITH actor_domains AS (
                SELECT
                    REGEXP_REPLACE(
                        SPLIT_PART(REGEXP_REPLACE(LOWER(TRIM(actor_domain)), '^https?://', ''), '/', 1),
                        '^www\\.',
                        ''
                    ) as canonical_domain,
                    partisan,
                    country as actor_country
                FROM actors
                WHERE actor_domain IS NOT NULL
                  AND TRIM(actor_domain) <> ''
                  AND partisan IN ('Right', 'Left', 'Other')
                UNION ALL
                SELECT
                    REGEXP_REPLACE(
                        SPLIT_PART(REGEXP_REPLACE(LOWER(TRIM(website)), '^https?://', ''), '/', 1),
                        '^www\\.',
                        ''
                    ) as canonical_domain,
                    partisan,
                    country as actor_country
                FROM actors
                WHERE website IS NOT NULL
                  AND TRIM(website) <> ''
                  AND partisan IN ('Right', 'Left', 'Other')
            )
            SELECT DISTINCT ON (canonical_domain)
                canonical_domain,
                partisan
            FROM actor_domains
            WHERE canonical_domain IS NOT NULL
              AND canonical_domain <> ''
              {country_filter}
            ORDER BY canonical_domain, partisan
        """)
        rows = self.db.execute(query, params).fetchall()
        values = {str(row[0]): str(row[1]) for row in rows if row[0] and row[1]}
        _DOMAIN_PARTISAN_CACHE[cache_key] = {"created_at": now, "values": values}
        return values
    
    def get_overview(self) -> Dict:
        """Get overview statistics."""
        query = text("""
            SELECT 
                COUNT(*) as total_articles,
                COUNT(DISTINCT domain) as total_outlets,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM clean_articles
            WHERE date IS NOT NULL
        """)
        result = self.db.execute(query).fetchone()
        
        # Get country distribution
        country_query = text("""
            SELECT country, COUNT(*) as count
            FROM clean_articles
            WHERE country IS NOT NULL
            GROUP BY country
            ORDER BY count DESC
        """)
        country_results = self.db.execute(country_query).fetchall()
        by_country = {row[0]: row[1] for row in country_results}
        
        # Get partisan distribution
        partisan_query = text("""
            SELECT partisan, COUNT(*) as count
            FROM clean_articles
            WHERE partisan IS NOT NULL
            GROUP BY partisan
            ORDER BY count DESC
        """)
        partisan_results = self.db.execute(partisan_query).fetchall()
        by_partisan = {row[0]: row[1] for row in partisan_results}
        
        return {
            "total_articles": result[0] or 0,
            "total_outlets": result[1] or 0,
            "date_range": {
                "earliest": str(result[2]) if result[2] else None,
                "latest": str(result[3]) if result[3] else None
            },
            "by_country": by_country,
            "by_partisan": by_partisan
        }

    def get_overview_full(self) -> Dict:
        """Get overview statistics from the full articles table."""
        query = text("""
            SELECT 
                COUNT(*) as total_articles,
                COUNT(DISTINCT domain) as total_outlets,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM articles
            WHERE date IS NOT NULL
        """)
        result = self.db.execute(query).fetchone()

        country_query = text("""
            SELECT country, COUNT(*) as count
            FROM articles
            WHERE country IS NOT NULL
            GROUP BY country
            ORDER BY count DESC
        """)
        country_results = self.db.execute(country_query).fetchall()
        by_country = {row[0]: row[1] for row in country_results}

        partisan_query = text("""
            SELECT partisan, COUNT(*) as count
            FROM articles
            WHERE partisan IS NOT NULL
            GROUP BY partisan
            ORDER BY count DESC
        """)
        partisan_results = self.db.execute(partisan_query).fetchall()
        by_partisan = {row[0]: row[1] for row in partisan_results}

        return {
            "total_articles": result[0] or 0,
            "total_outlets": result[1] or 0,
            "date_range": {
                "earliest": str(result[2]) if result[2] else None,
                "latest": str(result[3]) if result[3] else None,
            },
            "by_country": by_country,
            "by_partisan": by_partisan,
        }
    
    def get_articles_by_country(
        self,
        partisan: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """Get article counts by country with optional filters."""
        conditions = ["country IS NOT NULL"]
        params = {}
        
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        
        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to
        
        where_clause = " AND ".join(conditions)
        
        query = text(f"""
            SELECT country, COUNT(*) as count
            FROM clean_articles
            WHERE {where_clause}
            GROUP BY country
            ORDER BY count DESC
        """)
        
        results = self.db.execute(query, params).fetchall()
        return [{"country": row[0], "count": row[1]} for row in results]
    
    def get_articles_over_time(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None,
        granularity: str = "month",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict]:
        """Get time series data for articles."""
        conditions = ["date IS NOT NULL"]
        params = {}
        
        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        
        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to
        
        where_clause = " AND ".join(conditions)
        
        # Determine date format based on granularity
        if granularity == "year":
            date_format = "TO_CHAR(date, 'YYYY')"
            group_by = "TO_CHAR(date, 'YYYY')"
        elif granularity == "month":
            date_format = "TO_CHAR(date, 'YYYY-MM')"
            group_by = "TO_CHAR(date, 'YYYY-MM')"
        elif granularity == "week":
            date_format = "TO_CHAR(date, 'IYYY-IW')"
            group_by = "TO_CHAR(date, 'IYYY-IW')"
        else:  # day
            date_format = "TO_CHAR(date, 'YYYY-MM-DD')"
            group_by = "TO_CHAR(date, 'YYYY-MM-DD')"
        
        query = text(f"""
            SELECT 
                {date_format} as date,
                COUNT(*) as count
            FROM clean_articles
            WHERE {where_clause}
            GROUP BY {group_by}
            ORDER BY date
        """)
        
        results = self.db.execute(query, params).fetchall()
        return [{"date": str(row[0]), "count": row[1]} for row in results]

    def get_articles_over_time_by_outlet(
        self,
        outlets: List[str],
        country: Optional[str] = None,
        granularity: str = "month",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict]:
        """Get time series data for selected outlets."""
        if not outlets:
            return []

        normalized: List[str] = []
        for outlet in outlets:
            normalized.extend(domain_variants(outlet))
        normalized = sorted({o for o in normalized if o})

        conditions = ["date IS NOT NULL", "lower(domain) = ANY(:outlets)"]
        params: Dict[str, Any] = {"outlets": normalized}

        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country

        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from

        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions)

        if granularity == "year":
            date_format = "TO_CHAR(date, 'YYYY')"
            group_by = "TO_CHAR(date, 'YYYY')"
        elif granularity == "month":
            date_format = "TO_CHAR(date, 'YYYY-MM')"
            group_by = "TO_CHAR(date, 'YYYY-MM')"
        elif granularity == "week":
            date_format = "TO_CHAR(date, 'IYYY-IW')"
            group_by = "TO_CHAR(date, 'IYYY-IW')"
        else:
            date_format = "TO_CHAR(date, 'YYYY-MM-DD')"
            group_by = "TO_CHAR(date, 'YYYY-MM-DD')"

        query = text(f"""
            SELECT 
                {date_format} as date,
                {CANONICAL_DOMAIN_SQL} as outlet,
                COUNT(*) as count
            FROM clean_articles
            WHERE {where_clause}
            GROUP BY {group_by}, {CANONICAL_DOMAIN_SQL}
            ORDER BY date, outlet
        """)

        results = self.db.execute(query, params).fetchall()
        return [{"date": str(row[0]), "outlet": row[1], "count": row[2]} for row in results]
    
    def get_top_outlets(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get top outlets by article count."""
        conditions = ["domain IS NOT NULL"]
        params = {"limit": limit}
        
        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan

        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to
        
        where_clause = " AND ".join(conditions)
        
        query = text(f"""
            WITH base AS (
                SELECT
                    REGEXP_REPLACE(LOWER(domain), '^www\\.', '') as domain_key,
                    LOWER(domain) as domain,
                    actor,
                    country,
                    partisan,
                    date
                FROM clean_articles
                WHERE {where_clause}
            ),
            outlet_counts AS (
                SELECT
                    domain_key,
                    COALESCE(
                        MAX(domain) FILTER (WHERE domain LIKE 'www.%'),
                        MAX(domain)
                    ) as domain,
                    MAX(actor) FILTER (WHERE actor IS NOT NULL) as outlet_name,
                    MAX(country) FILTER (WHERE country IS NOT NULL) as country,
                    MAX(partisan) FILTER (WHERE partisan IS NOT NULL) as partisan,
                    COUNT(*) as count
                FROM base
                GROUP BY domain_key
            )
            SELECT domain, outlet_name, country, partisan, count
            FROM outlet_counts
            ORDER BY count DESC
            LIMIT :limit
        """)
        
        results = self.db.execute(query, params).fetchall()
        return [
            {
                "domain": row[0],
                "outlet_name": row[1],
                "country": row[2],
                "partisan": row[3],
                "count": row[4]
            }
            for row in results
        ]

    def get_concentration_metrics(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """Get outlet concentration metrics for the filtered subset."""
        conditions = ["date IS NOT NULL"]
        params: Dict[str, Any] = {}

        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions)

        total_query = text(f"""
            SELECT COUNT(*) as total_count
            FROM clean_articles
            WHERE {where_clause}
        """)
        total_count = int((self.db.execute(total_query, params).scalar() or 0))

        by_outlet_query = text(f"""
            SELECT {CANONICAL_DOMAIN_SQL} as domain_key, COUNT(*) as count
            FROM clean_articles
            WHERE {where_clause} AND domain IS NOT NULL
            GROUP BY {CANONICAL_DOMAIN_SQL}
            ORDER BY count DESC
        """)
        outlet_rows = self.db.execute(by_outlet_query, params).fetchall()
        counts = [int(row[1]) for row in outlet_rows]

        covered_count = sum(counts)
        coverage_share = _safe_share(covered_count, total_count)
        n_outlets = len(counts)

        if covered_count <= 0 or n_outlets == 0:
            return {
                "top_n": top_n,
                "top_n_share": 0.0,
                "hhi": 0.0,
                "enp": 0.0,
                "n_outlets": 0,
                "coverage_share": coverage_share,
            }

        shares = [count / covered_count for count in counts]
        top_n_share = sum(shares[: max(1, top_n)])
        hhi = sum(share * share for share in shares)
        enp = (1.0 / hhi) if hhi > 0 else 0.0

        return {
            "top_n": top_n,
            "top_n_share": top_n_share,
            "hhi": hhi,
            "enp": enp,
            "n_outlets": n_outlets,
            "coverage_share": coverage_share,
        }

    def get_partisan_mix(
        self,
        country: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get partisan composition with explicit unknown/missing count."""
        conditions = ["date IS NOT NULL"]
        params: Dict[str, Any] = {}

        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions)
        query = text(f"""
            SELECT
                COALESCE(partisan, '') as partisan_label,
                REGEXP_REPLACE(LOWER(domain), '^www\\.', '') as canonical_domain,
                COUNT(*) as count
            FROM clean_articles
            WHERE {where_clause}
            GROUP BY COALESCE(partisan, ''), REGEXP_REPLACE(LOWER(domain), '^www\\.', '')
        """)
        results = self.db.execute(query, params).fetchall()
        domain_partisan_lookup = self._get_domain_partisan_lookup(country=country)

        canonical = {"Right": 0, "Left": 0, "Other": 0}
        unknown_count = 0
        total_count = 0
        for row in results:
            article_label = str(row[0] or "").strip()
            canonical_domain = str(row[1] or "").strip()
            count = int(row[2] or 0)
            total_count += count
            if article_label in canonical:
                canonical[article_label] += count
            elif canonical_domain and domain_partisan_lookup.get(canonical_domain) in canonical:
                canonical[domain_partisan_lookup[canonical_domain]] += count
            else:
                unknown_count += count

        data = [
            {"partisan": label, "count": count, "share": _safe_share(count, total_count)}
            for label, count in canonical.items()
        ]
        data.append(
            {
                "partisan": "Unclassified",
                "count": unknown_count,
                "share": _safe_share(unknown_count, total_count),
            }
        )
        return {
            "total_count": total_count,
            "unknown_or_missing_count": unknown_count,
            "data": data,
        }

    def get_topic_similarity(
        self,
        level: str = "country",
        country: Optional[str] = None,
        partisan: Optional[str] = None,
        outlets: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit_topics: int = 12,
    ) -> Dict[str, Any]:
        """Get pairwise topic similarity (cosine + JSD) for countries, country-orientations, or outlets."""
        level = (level or "country").lower()
        if level not in {"country", "country_partisan", "country_orientation", "outlet"}:
            level = "country"

        if level == "country":
            entity_expr = "LOWER(country)"
        elif level in {"country_partisan", "country_orientation"}:
            entity_expr = "INITCAP(LOWER(country)) || ' - ' || INITCAP(LOWER(partisan))"
        else:
            entity_expr = "LOWER(domain)"
        conditions = ["date IS NOT NULL", f"{entity_expr} IS NOT NULL"]
        params: Dict[str, Any] = {"limit_topics": max(2, min(int(limit_topics), 40))}
        if level in {"country_partisan", "country_orientation"}:
            conditions.append("LOWER(partisan) IN ('left', 'right', 'other')")

        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        if outlets:
            normalized: List[str] = []
            for outlet in outlets:
                normalized.extend(domain_variants(outlet))
            normalized = sorted({o for o in normalized if o})
            if normalized:
                conditions.append("LOWER(domain) = ANY(:outlets)")
                params["outlets"] = normalized
        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions)
        check_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='articles' AND column_name='category'
        """)
        has_category_column = self.db.execute(check_query).fetchone() is not None

        if has_category_column:
            top_topics_query = text(f"""
                SELECT category, COUNT(*) as count
                FROM clean_articles
                WHERE {where_clause} AND category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                LIMIT :limit_topics
            """)
            top_rows = self.db.execute(top_topics_query, params).fetchall()
            topics = [str(row[0]) for row in top_rows if row[0]]
            if not topics:
                return {"topics": [], "entities": [], "cosine": [], "jsd": []}

            params["topics"] = topics
            vector_query = text(f"""
                SELECT {entity_expr} as entity, category, COUNT(*) as count
                FROM clean_articles
                WHERE {where_clause} AND category = ANY(:topics)
                GROUP BY {entity_expr}, category
            """)
        else:
            top_topics_query = text(f"""
                SELECT expanded_category.category, COUNT(*) as count
                FROM clean_articles
                {CATEGORY_EXPANSION_JOIN}
                WHERE {where_clause} AND categories IS NOT NULL
                GROUP BY expanded_category.category
                ORDER BY count DESC
                LIMIT :limit_topics
            """)
            top_rows = self.db.execute(top_topics_query, params).fetchall()
            topics = [str(row[0]) for row in top_rows if row[0]]
            if not topics:
                return {"topics": [], "entities": [], "cosine": [], "jsd": []}

            params["topics"] = topics
            vector_query = text(f"""
                WITH expanded AS (
                    SELECT
                        {entity_expr} as entity,
                        expanded_category.category as category
                    FROM clean_articles
                    {CATEGORY_EXPANSION_JOIN}
                    WHERE {where_clause} AND categories IS NOT NULL
                )
                SELECT entity, category, COUNT(*) as count
                FROM expanded
                WHERE category = ANY(:topics)
                GROUP BY entity, category
            """)

        rows = self.db.execute(vector_query, params).fetchall()
        topic_index = {topic: idx for idx, topic in enumerate(topics)}
        vectors: Dict[str, List[float]] = {}

        for entity, topic, count in rows:
            if entity is None or topic not in topic_index:
                continue
            entity_key = str(entity)
            if entity_key not in vectors:
                vectors[entity_key] = [0.0] * len(topics)
            vectors[entity_key][topic_index[str(topic)]] = float(count or 0)

        # Convert to topic-share vectors for comparability.
        for entity_key, vec in list(vectors.items()):
            total = sum(vec)
            if total <= 0:
                vectors[entity_key] = [0.0] * len(topics)
            else:
                vectors[entity_key] = [value / total for value in vec]

        entities = sorted(vectors.keys())
        cosine_rows: List[Dict[str, Any]] = []
        jsd_rows: List[Dict[str, Any]] = []
        for a, b in combinations(entities, 2):
            vec_a = vectors[a]
            vec_b = vectors[b]
            cosine_rows.append(
                {"entity_a": a, "entity_b": b, "value": _cosine_similarity(vec_a, vec_b)}
            )
            jsd_rows.append(
                {"entity_a": a, "entity_b": b, "value": _jensen_shannon_divergence(vec_a, vec_b)}
            )

        return {
            "topics": topics,
            "entities": entities,
            "cosine": cosine_rows,
            "jsd": jsd_rows,
        }

    def get_outlet_profile(self, domain: str) -> Optional[Dict]:
        """Get outlet profile summary by domain."""
        domains = domain_variants(domain)
        if not domains:
            return None

        query = text("""
            SELECT
                COALESCE(
                    MAX(LOWER(domain)) FILTER (WHERE LOWER(domain) LIKE 'www.%'),
                    MAX(LOWER(domain))
                ) as domain,
                MAX(actor) FILTER (WHERE actor IS NOT NULL) as outlet_name,
                MAX(country) FILTER (WHERE country IS NOT NULL) as country,
                COUNT(*) as total_articles,
                MIN(date) as first_article_date,
                MAX(date) as last_article_date
            FROM clean_articles
            WHERE LOWER(domain) = ANY(:domains)
        """)
        result = self.db.execute(query, {"domains": domains}).fetchone()
        if not result or not result[0]:
            return None
        return {
            "domain": result[0],
            "outlet_name": result[1],
            "country": result[2],
            "total_articles": result[3],
            "first_article_date": str(result[4]) if result[4] else None,
            "last_article_date": str(result[5]) if result[5] else None,
        }
    
    def get_categories_distribution(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None
    ) -> List[Dict]:
        """Get distribution of categories."""
        # Check if category column exists (newer format)
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='articles' AND column_name='category'
        """)
        has_category_column = self.db.execute(check_query).fetchone() is not None
        
        if has_category_column:
            # Use category column (simpler and faster)
            conditions = ["category IS NOT NULL"]
            params = {}
            
            if country:
                conditions.append("LOWER(country) = LOWER(:country)")
                params["country"] = country
            
            if partisan:
                conditions.append("LOWER(partisan) = LOWER(:partisan)")
                params["partisan"] = partisan
            
            where_clause = " AND ".join(conditions)
            
            query = text(f"""
                SELECT 
                    category,
                    COUNT(*) as count
                FROM clean_articles
                WHERE {where_clause}
                GROUP BY category
                ORDER BY count DESC
            """)
        else:
            # Fallback to categories JSONB column
            conditions = ["categories IS NOT NULL"]
            params = {}
            
            if country:
                conditions.append("LOWER(country) = LOWER(:country)")
                params["country"] = country
            
            if partisan:
                conditions.append("LOWER(partisan) = LOWER(:partisan)")
                params["partisan"] = partisan
            
            where_clause = " AND ".join(conditions)
            
            query = text(f"""
                SELECT 
                    expanded_category.category as category,
                    COUNT(*) as count
                FROM clean_articles
                {CATEGORY_EXPANSION_JOIN}
                WHERE {where_clause}
                GROUP BY expanded_category.category
                ORDER BY count DESC
            """)
        
        results = self.db.execute(query, params).fetchall()
        return [{"category": row[0], "count": row[1]} for row in results]
    
    def get_sentiment_distribution(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None
    ) -> List[Dict]:
        """Get sentiment distribution."""
        conditions = ["sentiment IS NOT NULL"]
        params = {}
        
        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        
        where_clause = " AND ".join(conditions)
        
        query = text(f"""
            SELECT 
                sentiment,
                COUNT(*) as count,
                AVG(sentiment_score) as avg_score
            FROM clean_articles
            WHERE {where_clause}
            GROUP BY sentiment
            ORDER BY count DESC
        """)
        
        results = self.db.execute(query, params).fetchall()
        return [
            {
                "sentiment": row[0],
                "count": row[1],
                "avg_score": float(row[2]) if row[2] else 0.0
            }
            for row in results
        ]

    def get_categories_over_time(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None,
        outlets: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        granularity: str = "month",
        limit: int = 6,
    ) -> List[Dict]:
        """Get category trends over time."""
        if granularity == "year":
            date_format = "TO_CHAR(date, 'YYYY')"
            group_by = "TO_CHAR(date, 'YYYY')"
        elif granularity == "week":
            date_format = "TO_CHAR(date, 'IYYY-IW')"
            group_by = "TO_CHAR(date, 'IYYY-IW')"
        else:
            date_format = "TO_CHAR(date, 'YYYY-MM')"
            group_by = "TO_CHAR(date, 'YYYY-MM')"

        conditions = ["date IS NOT NULL"]
        params: Dict[str, Any] = {"limit": limit}

        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        if outlets:
            normalized: List[str] = []
            for outlet in outlets:
                normalized.extend(domain_variants(outlet))
            normalized = sorted({o for o in normalized if o})
            if normalized:
                conditions.append("LOWER(domain) = ANY(:outlets)")
                params["outlets"] = normalized
        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions)

        check_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='articles' AND column_name='category'
        """)
        has_category_column = self.db.execute(check_query).fetchone() is not None

        if has_category_column:
            top_categories_query = text(f"""
                SELECT category, COUNT(*) as count
                FROM clean_articles
                WHERE {where_clause} AND category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                LIMIT :limit
            """)
            top_rows = self.db.execute(top_categories_query, params).fetchall()
            categories = [row[0] for row in top_rows if row[0]]
            if not categories:
                return []

            params["categories"] = categories
            query = text(f"""
                SELECT
                    {date_format} as date,
                    category,
                    COUNT(*) as count
                FROM clean_articles
                WHERE {where_clause} AND category = ANY(:categories)
                GROUP BY {group_by}, category
                ORDER BY date
            """)
        else:
            top_categories_query = text(f"""
                SELECT expanded_category.category as category, COUNT(*) as count
                FROM clean_articles
                {CATEGORY_EXPANSION_JOIN}
                WHERE {where_clause} AND categories IS NOT NULL
                GROUP BY expanded_category.category
                ORDER BY count DESC
                LIMIT :limit
            """)
            top_rows = self.db.execute(top_categories_query, params).fetchall()
            categories = [row[0] for row in top_rows if row[0]]
            if not categories:
                return []

            params["categories"] = categories
            query = text(f"""
                WITH expanded AS (
                    SELECT
                        {date_format} as date,
                        expanded_category.category as category
                    FROM clean_articles
                    {CATEGORY_EXPANSION_JOIN}
                    WHERE {where_clause} AND categories IS NOT NULL
                )
                SELECT
                    date,
                    category,
                    COUNT(*) as count
                FROM expanded
                WHERE category = ANY(:categories)
                GROUP BY date, category
                ORDER BY date
            """)

        results = self.db.execute(query, params).fetchall()
        return [
            {"date": str(row[0]), "category": row[1], "count": row[2]}
            for row in results
        ]
    
    def get_top_entities(
        self,
        entity_type: str = "persons",  # persons, locations, organizations
        country: Optional[str] = None,
        partisan: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get top entities by type."""
        conditions = [
            "entities_json IS NOT NULL",
            f"entities_json ? '{entity_type}'",
            f"jsonb_array_length(entities_json->'{entity_type}') > 0"
        ]
        params = {"limit": limit, "entity_type": entity_type}
        
        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        
        where_clause = " AND ".join(conditions)
        
        # Extract entities and count occurrences
        # Note: entity_type is validated before this function is called
        query = text(f"""
            WITH entity_extract AS (
                SELECT 
                    jsonb_array_elements(entities_json->'{entity_type}') as entity_data
                FROM clean_articles
                WHERE {where_clause}
            )
            SELECT 
                entity_data->>'name' as entity_name,
                COUNT(*) as count,
                COUNT(CASE WHEN entity_data->>'sentiment' = 'positive' THEN 1 END) as positive_count,
                COUNT(CASE WHEN entity_data->>'sentiment' = 'negative' THEN 1 END) as negative_count,
                COUNT(CASE WHEN entity_data->>'sentiment' = 'neutral' OR entity_data->>'sentiment' = 'none' THEN 1 END) as neutral_count
            FROM entity_extract
            WHERE entity_data->>'name' IS NOT NULL
            GROUP BY entity_data->>'name'
            ORDER BY count DESC
            LIMIT :limit
        """)
        
        results = self.db.execute(query, params).fetchall()
        return [
            {
                "entity_name": row[0],
                "count": row[1],
                "positive_count": row[2],
                "negative_count": row[3],
                "neutral_count": row[4]
            }
            for row in results
        ]
    
    def get_entity_statistics(
        self,
        country: Optional[str] = None,
        partisan: Optional[str] = None
    ) -> Dict:
        """Get overall entity statistics."""
        conditions = ["entities_json IS NOT NULL"]
        params = {}
        
        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        
        if partisan:
            conditions.append("LOWER(partisan) = LOWER(:partisan)")
            params["partisan"] = partisan
        
        where_clause = " AND ".join(conditions)
        
        query = text(f"""
            SELECT 
                COUNT(*) FILTER (WHERE entities_json ? 'persons' AND jsonb_array_length(entities_json->'persons') > 0) as articles_with_persons,
                COUNT(*) FILTER (WHERE entities_json ? 'locations' AND jsonb_array_length(entities_json->'locations') > 0) as articles_with_locations,
                COUNT(*) FILTER (WHERE entities_json ? 'organizations' AND jsonb_array_length(entities_json->'organizations') > 0) as articles_with_organizations,
                COUNT(*) as total_articles
            FROM clean_articles
            WHERE {where_clause}
        """)
        
        result = self.db.execute(query, params).fetchone()
        
        return {
            "total_articles": result[3] or 0,
            "articles_with_persons": result[0] or 0,
            "articles_with_locations": result[1] or 0,
            "articles_with_organizations": result[2] or 0,
            "coverage": {
                "persons": (result[0] / result[3] * 100) if result[3] and result[3] > 0 else 0,
                "locations": (result[1] / result[3] * 100) if result[3] and result[3] > 0 else 0,
                "organizations": (result[2] / result[3] * 100) if result[3] and result[3] > 0 else 0
            }
        }
    
    def get_data_freshness(self) -> Dict:
        """Get data freshness information (last updated timestamp)."""
        query = text("""
            SELECT 
                MAX(date) as last_article_date,
                MAX(updated_at) as last_updated
            FROM clean_articles
        """)
        result = self.db.execute(query).fetchone()
        
        last_article_date = result[0] if result[0] else None
        last_updated = result[1] if result[1] else None
        
        # Calculate hours ago if we have a timestamp
        hours_ago = None
        if last_updated:
            try:
                if isinstance(last_updated, str):
                    last_updated_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                else:
                    last_updated_dt = last_updated
                now = datetime.now(last_updated_dt.tzinfo) if last_updated_dt.tzinfo else datetime.now()
                delta = now - last_updated_dt
                hours_ago = int(delta.total_seconds() / 3600)
            except Exception:
                pass
        
        return {
            "last_article_date": str(last_article_date) if last_article_date else None,
            "last_updated": str(last_updated) if last_updated else None,
            "hours_ago": hours_ago
        }

    def get_landing_bundle(self, latest_limit: int = 120) -> Dict[str, Any]:
        """Get the landing-page payload in a small number of database queries."""
        cache_key = str(latest_limit)
        now_ts = datetime.utcnow().timestamp()
        cached = _LANDING_BUNDLE_CACHE.get(cache_key)
        if cached and now_ts - float(cached.get("created_at", 0)) <= _LANDING_BUNDLE_CACHE_TTL_SECONDS:
            return dict(cached.get("value", {}))

        stats_query = text("""
            SELECT
                COUNT(*) as total_articles,
                COUNT(DISTINCT domain) as total_outlets,
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                MAX(updated_at) as last_updated,
                COUNT(*)::float / NULLIF(COUNT(DISTINCT domain), 0) as avg_articles_per_outlet
            FROM articles
        """)
        result = self.db.execute(stats_query).fetchone()

        country_rows = self.db.execute(
            text("""
                SELECT country, COUNT(*) as count
                FROM articles
                WHERE country IS NOT NULL
                GROUP BY country
                ORDER BY count DESC
            """)
        ).fetchall()
        by_country = {row[0]: int(row[1] or 0) for row in country_rows}

        partisan_rows = self.db.execute(
            text("""
                SELECT partisan, COUNT(*) as count
                FROM articles
                WHERE partisan IS NOT NULL
                GROUP BY partisan
                ORDER BY count DESC
            """)
        ).fetchall()
        by_partisan = {row[0]: int(row[1] or 0) for row in partisan_rows}

        growth_results = self.db.execute(
            text("""
                SELECT EXTRACT(YEAR FROM date)::int as year, COUNT(*) as count
                FROM articles
                WHERE date IS NOT NULL
                GROUP BY EXTRACT(YEAR FROM date)::int
                ORDER BY year
            """)
        ).fetchall()
        growth_rate = None
        if len(growth_results) >= 2:
            years = [int(row[0]) for row in growth_results]
            counts = [int(row[1] or 0) for row in growth_results]
            n = len(years)
            sum_x = sum(years)
            sum_y = sum(counts)
            sum_xy = sum(years[i] * counts[i] for i in range(n))
            sum_x2 = sum(year * year for year in years)
            denominator = n * sum_x2 - sum_x * sum_x
            if denominator != 0:
                growth_rate = round((n * sum_xy - sum_x * sum_y) / denominator, 1)

        latest_date = result[3] if result and result[3] else None
        last_updated = result[4] if result and result[4] else None
        hours_ago = None
        if last_updated:
            try:
                now = datetime.now(last_updated.tzinfo) if last_updated.tzinfo else datetime.now()
                hours_ago = int((now - last_updated).total_seconds() / 3600)
            except Exception:
                hours_ago = None

        earliest = result[2] if result and result[2] else None
        coverage_years = None
        if earliest and latest_date:
            coverage_years = f"{earliest.year}-{latest_date.year}"

        overview = {
            "total_articles": int(result[0] or 0) if result else 0,
            "total_outlets": int(result[1] or 0) if result else 0,
            "date_range": {
                "earliest": str(earliest) if earliest else None,
                "latest": str(latest_date) if latest_date else None,
            },
            "by_country": by_country,
            "by_partisan": by_partisan,
            "avg_articles_per_outlet": round(float(result[5] or 0.0), 1) if result else 0.0,
            "growth_rate_per_year": growth_rate,
            "coverage_years": coverage_years,
        }
        freshness = {
            "last_article_date": str(latest_date) if latest_date else None,
            "last_updated": str(last_updated) if last_updated else None,
            "hours_ago": hours_ago,
        }

        latest_date_from = None
        if latest_date:
            latest_date_from = latest_date - timedelta(days=14)

        latest_date_condition = "date >= :date_from" if latest_date_from else "TRUE"
        latest_articles_query = text(f"""
            SELECT id, title, url, date, domain
            FROM clean_articles
            WHERE date IS NOT NULL
              AND {latest_date_condition}
            ORDER BY date DESC NULLS LAST
            LIMIT :limit
        """)
        latest_params: Dict[str, Any] = {"limit": max(1, min(latest_limit, 200))}
        if latest_date_from:
            latest_params["date_from"] = latest_date_from
        latest_rows = self.db.execute(latest_articles_query, latest_params).fetchall()
        latest_articles = [
            {
                "id": row[0],
                "title": row[1],
                "url": row[2],
                "date": str(row[3]) if row[3] else None,
                "domain": row[4],
            }
            for row in latest_rows
        ]

        start_year = 2021
        end_year = latest_date.year if latest_date else datetime.now().year
        time_query = text("""
            SELECT
                lower(country) as country,
                TO_CHAR(date, 'YYYY-MM') as date,
                COUNT(*) as count
            FROM clean_articles
            WHERE date >= :date_from
              AND date <= :date_to
              AND country IS NOT NULL
            GROUP BY lower(country), TO_CHAR(date, 'YYYY-MM')
            ORDER BY date, country
        """)
        date_from = f"{start_year}-01-01"
        date_to = f"{end_year}-12-31"
        time_rows = self.db.execute(time_query, {"date_from": date_from, "date_to": date_to}).fetchall()
        articles_over_time = {
            "granularity": "month",
            "filters": {
                "country": None,
                "partisan": None,
                "date_from": date_from,
                "date_to": date_to,
            },
            "data": [
                {"country": row[0], "date": row[1], "count": int(row[2] or 0)}
                for row in time_rows
            ],
        }

        bundle = {
            "overview": overview,
            "freshness": freshness,
            "latest_articles": latest_articles,
            "articles_over_time": articles_over_time,
        }
        _LANDING_BUNDLE_CACHE[cache_key] = {"created_at": now_ts, "value": bundle}
        return bundle

    def get_analysis_bundle(self) -> Dict[str, Any]:
        """Get default Analysis compare-mode data without repeated endpoint calls."""
        cache_key = "default"
        now_ts = datetime.utcnow().timestamp()
        cached = _ANALYSIS_BUNDLE_CACHE.get(cache_key)
        if cached and now_ts - float(cached.get("created_at", 0)) <= _ANALYSIS_BUNDLE_CACHE_TTL_SECONDS:
            return dict(cached.get("value", {}))

        overview = self.get_landing_bundle().get("overview", {})
        year_min = 2016
        latest = (overview.get("date_range") or {}).get("latest")
        try:
            year_max = min(int(str(latest)[:4]), 2026) if latest else 2026
        except Exception:
            year_max = 2026
        if year_max < year_min:
            year_min, year_max = year_max, year_min

        date_from = f"{year_min}-01-01"
        date_to = f"{year_max}-12-31"
        countries = ["denmark", "sweden", "norway", "finland"]
        recent_years_values = list(range(max(year_min, year_max - 3), year_max + 1))

        time_rows = self.db.execute(
            text("""
                SELECT
                    LOWER(country) as country,
                    TO_CHAR(date, 'YYYY-MM') as date,
                    COUNT(*) as count
                FROM clean_articles
                WHERE date >= :date_from
                  AND date <= :date_to
                  AND country IS NOT NULL
                GROUP BY LOWER(country), TO_CHAR(date, 'YYYY-MM')
                ORDER BY date, country
            """),
            {"date_from": date_from, "date_to": date_to},
        ).fetchall()
        articles_over_time = {
            "granularity": "month",
            "filters": {
                "country": None,
                "partisan": None,
                "date_from": date_from,
                "date_to": date_to,
            },
            "data": [
                {"country": row[0], "date": str(row[1]), "count": int(row[2] or 0)}
                for row in time_rows
            ],
        }

        mix_rows = self.db.execute(
            text("""
                SELECT
                    LOWER(country) as country,
                    EXTRACT(YEAR FROM date)::int as year,
                    CASE
                        WHEN partisan IN ('Right', 'Left', 'Other') THEN partisan
                        ELSE 'Unclassified'
                    END as partisan,
                    COUNT(*) as count
                FROM clean_articles
                WHERE date >= :date_from
                  AND date <= :date_to
                  AND country IS NOT NULL
                GROUP BY LOWER(country), EXTRACT(YEAR FROM date)::int,
                         CASE
                             WHEN partisan IN ('Right', 'Left', 'Other') THEN partisan
                             ELSE 'Unclassified'
                         END
            """),
            {"date_from": f"{recent_years_values[0]}-01-01", "date_to": f"{recent_years_values[-1]}-12-31"},
        ).fetchall()
        mix_totals: Dict[tuple[str, int], int] = {}
        for row in mix_rows:
            key = (str(row[0]), int(row[1]))
            mix_totals[key] = mix_totals.get(key, 0) + int(row[3] or 0)
        partisan_mix = []
        for row in mix_rows:
            country = str(row[0])
            year = int(row[1])
            count = int(row[3] or 0)
            total = mix_totals.get((country, year), 0)
            partisan_mix.append(
                {
                    "country": country,
                    "year": year,
                    "partisan": str(row[2]),
                    "count": count,
                    "share": _safe_share(count, total),
                }
            )

        outlet_rows = self.db.execute(
            text("""
                SELECT
                    LOWER(country) as country,
                    EXTRACT(YEAR FROM date)::int as year,
                    REGEXP_REPLACE(LOWER(domain), '^www\\.', '') as domain_key,
                    COUNT(*) as count
                FROM clean_articles
                WHERE date >= :date_from
                  AND date <= :date_to
                  AND country IS NOT NULL
                  AND domain IS NOT NULL
                GROUP BY LOWER(country), EXTRACT(YEAR FROM date)::int,
                         REGEXP_REPLACE(LOWER(domain), '^www\\.', '')
            """),
            {"date_from": f"{recent_years_values[0]}-01-01", "date_to": f"{recent_years_values[-1]}-12-31"},
        ).fetchall()
        grouped_counts: Dict[tuple[str, int], List[int]] = {}
        for row in outlet_rows:
            key = (str(row[0]), int(row[1]))
            grouped_counts.setdefault(key, []).append(int(row[3] or 0))
        concentration = []
        for country in countries:
            for year in recent_years_values:
                counts = grouped_counts.get((country, year), [])
                covered_count = sum(counts)
                hhi = 0.0
                if covered_count > 0:
                    hhi = sum((count / covered_count) ** 2 for count in counts)
                concentration.append(
                    {
                        "country": country,
                        "year": year,
                        "enp": (1.0 / hhi) if hhi > 0 else 0.0,
                        "hhi": hhi,
                        "n_outlets": len(counts),
                    }
                )

        bundle = {
            "overview": overview,
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "year_from": year_min,
                "year_to": year_max,
                "granularity": "month",
                "partisan": None,
                "recent_years": recent_years_values,
            },
            "articles_over_time": articles_over_time,
            "partisan_mix": partisan_mix,
            "concentration": concentration,
        }
        _ANALYSIS_BUNDLE_CACHE[cache_key] = {"created_at": now_ts, "value": bundle}
        return bundle
    
    def get_enhanced_overview(self) -> Dict:
        """Get enhanced overview with additional metrics."""
        base_overview = self.get_overview()
        
        # Get articles per outlet average
        query = text("""
            SELECT 
                COUNT(*)::float / NULLIF(COUNT(DISTINCT domain), 0) as avg_articles_per_outlet
            FROM clean_articles
            WHERE domain IS NOT NULL
        """)
        result = self.db.execute(query).fetchone()
        avg_articles_per_outlet = float(result[0]) if result[0] else 0.0
        
        # Get growth rate (articles per year trend)
        growth_query = text("""
            SELECT 
                TO_CHAR(date, 'YYYY') as year,
                COUNT(*) as count
            FROM clean_articles
            WHERE date IS NOT NULL
            GROUP BY TO_CHAR(date, 'YYYY')
            ORDER BY year
        """)
        growth_results = self.db.execute(growth_query).fetchall()
        
        # Calculate average growth rate
        growth_rate = None
        if len(growth_results) >= 2:
            years = [int(row[0]) for row in growth_results]
            counts = [row[1] for row in growth_results]
            if len(years) > 1:
                # Simple linear regression slope
                n = len(years)
                sum_x = sum(years)
                sum_y = sum(counts)
                sum_xy = sum(years[i] * counts[i] for i in range(n))
                sum_x2 = sum(x * x for x in years)
                
                denominator = n * sum_x2 - sum_x * sum_x
                if denominator != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / denominator
                    growth_rate = round(slope, 1)
        
        # Get date range for coverage display
        dr = base_overview.get("date_range", {})
        earliest = dr.get("earliest")
        latest = dr.get("latest")
        coverage_years = None
        if earliest and latest:
            try:
                earliest_year = int(str(earliest)[:4])
                latest_year = int(str(latest)[:4])
                coverage_years = f"{earliest_year}-{latest_year}"
            except Exception:
                pass
        
        return {
            **base_overview,
            "avg_articles_per_outlet": round(avg_articles_per_outlet, 1),
            "growth_rate_per_year": growth_rate,
            "coverage_years": coverage_years
        }

    def get_enhanced_overview_full(self) -> Dict:
        """Get enhanced overview with full dataset metrics."""
        base_overview = self.get_overview_full()

        query = text("""
            SELECT 
                COUNT(*)::float / NULLIF(COUNT(DISTINCT domain), 0) as avg_articles_per_outlet
            FROM articles
            WHERE domain IS NOT NULL
        """)
        result = self.db.execute(query).fetchone()
        avg_articles_per_outlet = float(result[0]) if result[0] else 0.0

        growth_query = text("""
            SELECT 
                TO_CHAR(date, 'YYYY') as year,
                COUNT(*) as count
            FROM articles
            WHERE date IS NOT NULL
            GROUP BY TO_CHAR(date, 'YYYY')
            ORDER BY year
        """)
        growth_results = self.db.execute(growth_query).fetchall()

        growth_rate = None
        if len(growth_results) >= 2:
            years = [int(row[0]) for row in growth_results]
            counts = [row[1] for row in growth_results]
            if len(years) > 1:
                n = len(years)
                sum_x = sum(years)
                sum_y = sum(counts)
                sum_xy = sum(years[i] * counts[i] for i in range(n))
                sum_x2 = sum(x * x for x in years)

                denominator = n * sum_x2 - sum_x * sum_x
                if denominator != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / denominator
                    growth_rate = round(slope, 1)

        dr = base_overview.get("date_range", {})
        earliest = dr.get("earliest")
        latest = dr.get("latest")
        coverage_years = None
        if earliest and latest:
            try:
                earliest_year = int(str(earliest)[:4])
                latest_year = int(str(latest)[:4])
                coverage_years = f"{earliest_year}-{latest_year}"
            except Exception:
                pass

        return {
            **base_overview,
            "avg_articles_per_outlet": round(avg_articles_per_outlet, 1),
            "growth_rate_per_year": growth_rate,
            "coverage_years": coverage_years,
        }
    
    def get_outlet_concentration(self, country: Optional[str] = None) -> Dict:
        """Get outlet concentration ratio (top 3 outlets' % of total articles)."""
        conditions = ["domain IS NOT NULL"]
        params = {}
        
        if country:
            conditions.append("LOWER(country) = LOWER(:country)")
            params["country"] = country
        
        where_clause = " AND ".join(conditions)
        
        # Get total articles for the country/filter
        total_query = text(f"""
            SELECT COUNT(*) as total
            FROM clean_articles
            WHERE {where_clause}
        """)
        total_result = self.db.execute(total_query, params).fetchone()
        total_articles = total_result[0] if total_result[0] else 0
        
        # Get top 3 outlets (merge www. and bare-domain variants)
        top_outlets_query = text(f"""
            WITH base AS (
                SELECT
                    {CANONICAL_DOMAIN_SQL} as domain_key,
                    LOWER(domain) as domain,
                    country
                FROM clean_articles
                WHERE {where_clause}
            ),
            outlet_counts AS (
                SELECT
                    domain_key,
                    COALESCE(
                        MAX(domain) FILTER (WHERE domain LIKE 'www.%'),
                        MAX(domain)
                    ) as domain,
                    MAX(country) FILTER (WHERE country IS NOT NULL) as country,
                    COUNT(*) as count
                FROM base
                GROUP BY domain_key
            )
            SELECT domain, country, count
            FROM outlet_counts
            ORDER BY count DESC
            LIMIT 3
        """)
        top_outlets = self.db.execute(top_outlets_query, params).fetchall()
        
        # Calculate concentration
        top3_total = sum(row[2] for row in top_outlets)
        concentration_pct = (top3_total / total_articles * 100) if total_articles > 0 else 0
        
        outlets_detail = [
            {
                "domain": row[0],
                "country": row[1],
                "count": row[2],
                "percentage": round((row[2] / total_articles * 100), 1) if total_articles > 0 else 0
            }
            for row in top_outlets
        ]
        
        return {
            "total_articles": total_articles,
            "top3_articles": top3_total,
            "concentration_percentage": round(concentration_pct, 1),
            "outlets": outlets_detail
        }
    
    def get_comparative_metrics(self) -> Dict:
        """Get comparative metrics across countries."""
        countries = ["denmark", "sweden", "norway", "finland"]
        comparative = {}
        
        for country in countries:
            # Get outlet concentration for each country
            concentration = self.get_outlet_concentration(country=country)
            
            # Get partisan balance
            partisan_query = text("""
                SELECT 
                    partisan,
                    COUNT(*) as count
                FROM clean_articles
                WHERE LOWER(country) = LOWER(:country) AND partisan IS NOT NULL
                GROUP BY partisan
            """)
            partisan_results = self.db.execute(partisan_query, {"country": country}).fetchall()
            
            partisan_counts = {row[0]: row[1] for row in partisan_results}
            right_count = partisan_counts.get("Right", 0)
            left_count = partisan_counts.get("Left", 0)
            total_partisan = right_count + left_count
            
            # Calculate partisan balance ratio
            partisan_ratio = None
            if total_partisan > 0:
                partisan_ratio = round((right_count / total_partisan) * 100, 1)
            
            comparative[country] = {
                "outlet_concentration": concentration["concentration_percentage"],
                "partisan_balance": {
                    "right_percentage": partisan_ratio,
                    "right_count": right_count,
                    "left_count": left_count
                },
                "top_outlets": concentration["outlets"]
            }
        
        return comparative
