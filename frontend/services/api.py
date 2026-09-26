"""API client helpers for the Streamlit frontend."""

from typing import Optional, List

import requests
import streamlit as st

from config import get_api_base_url

API_BASE_URL = get_api_base_url()
# Requests timeout = (connect timeout, read timeout)
# Keep these relatively short so the UI fails fast when the backend is wedged.
API_TIMEOUT = (3, 25)
API_TIMEOUT_LONG = (3, 25)


@st.cache_data(ttl=300)
def fetch_overview():
    """Fetch overview statistics."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats/overview", timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching overview: {exc}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_landing_bundle():
    """Fetch the compact landing-page payload."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats/landing", timeout=API_TIMEOUT_LONG)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching landing overview: {exc}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_analysis_bundle():
    """Fetch the default Analysis page payload."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats/analysis", timeout=API_TIMEOUT_LONG)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching analysis overview: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_enhanced_overview():
    """Fetch enhanced overview with additional metrics."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/stats/overview/enhanced",
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching enhanced overview: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_full_enhanced_overview():
    """Fetch enhanced overview from the full dataset."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats/overview/full", timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching full overview: {exc}")
        return None


@st.cache_data(ttl=60)
def fetch_data_freshness():
    """Fetch data freshness information."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/stats/data-freshness",
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_outlet_concentration(country: Optional[str] = None):
    """Fetch outlet concentration ratio."""
    try:
        params = {}
        if country:
            params["country"] = country
        response = requests.get(
            f"{API_BASE_URL}/api/stats/outlet-concentration",
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_comparative_metrics():
    """Fetch comparative metrics across countries."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/stats/comparative",
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


@st.cache_data(ttl=60)
def fetch_articles(
    query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    sentiment: Optional[str] = None,
    categories: Optional[List[str]] = None,
    entities: Optional[List[str]] = None,
    outlets: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search articles with filters."""
    try:
        params = {
            "limit": limit,
            "offset": offset,
        }
        if query:
            params["q"] = query
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if sentiment:
            params["sentiment"] = sentiment
        if categories:
            params["categories"] = ",".join(categories) if isinstance(categories, list) else categories
        if entities:
            params["entities"] = ",".join(entities) if isinstance(entities, list) else entities
        if outlets:
            params["outlets"] = ",".join(outlets) if isinstance(outlets, list) else outlets

        response = requests.get(
            f"{API_BASE_URL}/api/articles/search",
            params=params,
            timeout=API_TIMEOUT_LONG,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error searching articles: {exc}")
        return None


def fetch_articles_search(
    query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    sentiment: Optional[str] = None,
    categories: Optional[List[str]] = None,
    entities: Optional[List[str]] = None,
    outlets: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Compatibility wrapper for article search."""
    return fetch_articles(
        query=query,
        date_from=date_from,
        date_to=date_to,
        country=country,
        partisan=partisan,
        sentiment=sentiment,
        categories=categories,
        entities=entities,
        outlets=outlets,
        limit=limit,
        offset=offset,
    )


@st.cache_data(ttl=300)
def fetch_article_by_id(article_id: int):
    """Fetch a single article by ID."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/articles/{article_id}",
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_related_articles(article_id: int, limit: int = 5):
    """Fetch related articles."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/articles/{article_id}/related",
            params={"limit": limit},
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_articles_by_country(
    partisan: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch articles by country."""
    try:
        params = {}
        if partisan:
            params["partisan"] = partisan
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/stats/articles-by-country",
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching articles by country: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_articles_over_time(
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    granularity: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch articles over time."""
    try:
        params = {"granularity": granularity}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/stats/articles-over-time",
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching articles over time: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_articles_over_time_by_outlet(
    country: Optional[str] = None,
    outlets: Optional[List[str]] = None,
    granularity: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch articles over time grouped by outlet."""
    try:
        params = {"granularity": granularity}
        if country:
            params["country"] = country
        if outlets:
            params["outlets"] = ",".join(outlets) if isinstance(outlets, list) else outlets
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/stats/articles-over-time-by-outlet",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching articles over time by outlet: {exc}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_top_outlets(
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
):
    """Fetch top outlets."""
    try:
        params = {"limit": limit}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/stats/top-outlets",
            params=params,
            timeout=API_TIMEOUT_LONG,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching top outlets: {exc}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_outlet_profile(domain: str):
    """Fetch outlet profile summary by domain."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/stats/outlet-profile",
            params={"domain": domain},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching outlet profile: {exc}")
        return None


def send_access_request(name: str, email: str, message: str) -> str:
    """Send access request to backend for email delivery."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/contact",
            json={"name": name, "email": email, "message": message},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() if response.content else {}
        status = str(payload.get("status", "sent")).lower()
        if status not in {"sent", "queued"}:
            status = "sent"
        return status
    except Exception as exc:
        st.error(f"Error sending request: {exc}")
        return "error"


@st.cache_data(ttl=300)
def fetch_categories(country: Optional[str] = None, partisan: Optional[str] = None):
    """Fetch category distribution."""
    try:
        params = {}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan

        response = requests.get(
            f"{API_BASE_URL}/api/stats/categories",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching categories: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_concentration_metrics(
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    top_n: int = 5,
):
    """Fetch concentration metrics (Top-N share, HHI, ENP)."""
    try:
        params = {"top_n": top_n}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        response = requests.get(
            f"{API_BASE_URL}/api/stats/concentration",
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching concentration metrics: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_partisan_mix(
    country: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch partisan composition and unknown diagnostics."""
    try:
        params = {}
        if country:
            params["country"] = country
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        response = requests.get(
            f"{API_BASE_URL}/api/stats/partisan-mix",
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching partisan mix: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_categories_over_time(
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    outlets: Optional[List[str]] = None,
    granularity: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 6,
):
    """Fetch category trends over time."""
    try:
        params = {"granularity": granularity, "limit": limit}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if outlets:
            params["outlets"] = ",".join(outlets) if isinstance(outlets, list) else outlets
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/stats/categories/over-time",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching category trends: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_topic_similarity(
    level: str = "country",
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    outlets: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit_topics: int = 12,
):
    """Fetch pairwise topic similarity matrices (cosine and JSD)."""
    try:
        params = {"level": level, "limit_topics": limit_topics}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if outlets:
            params["outlets"] = ",".join(outlets) if isinstance(outlets, list) else outlets
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        response = requests.get(
            f"{API_BASE_URL}/api/stats/topic-similarity",
            params=params,
            timeout=API_TIMEOUT_LONG,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching topic similarity: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_sentiment(country: Optional[str] = None, partisan: Optional[str] = None):
    """Fetch sentiment distribution."""
    try:
        params = {}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan

        response = requests.get(
            f"{API_BASE_URL}/api/stats/sentiment",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching sentiment: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_top_entities(
    entity_type: str = "persons",
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    limit: int = 20,
):
    """Fetch top entities."""
    try:
        params = {"entity_type": entity_type, "limit": limit}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan

        response = requests.get(
            f"{API_BASE_URL}/api/stats/entities/top",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching top entities: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_entity_statistics(country: Optional[str] = None, partisan: Optional[str] = None):
    """Fetch entity statistics summary."""
    try:
        params = {}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan

        response = requests.get(
            f"{API_BASE_URL}/api/stats/entities",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching entity statistics: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_topic_distribution(
    country: Optional[str] = None,
    partisan: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch topic distribution."""
    try:
        params = {}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/topics/distribution",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching topic distribution: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_topics_over_time(
    topic_id: Optional[int] = None,
    country: Optional[str] = None,
    granularity: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch topics over time."""
    try:
        params = {"granularity": granularity}
        if topic_id:
            params["topic_id"] = topic_id
        if country:
            params["country"] = country
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        response = requests.get(
            f"{API_BASE_URL}/api/topics/over-time",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching topics over time: {exc}")
        return None


@st.cache_data(ttl=300)
def fetch_topic_statistics(country: Optional[str] = None, partisan: Optional[str] = None):
    """Fetch topic statistics summary."""
    try:
        params = {}
        if country:
            params["country"] = country
        if partisan:
            params["partisan"] = partisan

        response = requests.get(
            f"{API_BASE_URL}/api/topics/statistics",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Error fetching topic statistics: {exc}")
        return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_selection(params: tuple, sample_size: int = 25, order: str = "random", seed: str = "nordicamo"):
    """Count, composition and metadata-only sample for one Workshop selection.

    `params` is Selection.api_params() as a tuple (hashable for caching); list
    filters are sent as repeated query parameters because topic names contain commas.
    Returns None on failure so the page can show a clear message.
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/articles/selection",
            params=list(params) + [("sample_size", sample_size), ("order", order), ("seed", seed)],
            timeout=API_TIMEOUT_LONG,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_outlet_directory() -> list[dict]:
    """All outlets with country and article count, for filter pickers."""
    rows: dict[str, dict] = {}
    for country in ("denmark", "finland", "norway", "sweden"):
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/stats/top-outlets",
                params={"country": country, "limit": 1000},
                timeout=API_TIMEOUT,
            )
            response.raise_for_status()
            for row in response.json().get("data", []):
                domain = str(row.get("domain") or "").lower()
                key = domain[4:] if domain.startswith("www.") else domain
                if not key:
                    continue
                entry = rows.setdefault(key, {"outlet": key, "country": country, "count": 0})
                entry["count"] += int(row.get("count") or 0)
        except Exception:
            continue
    return sorted(rows.values(), key=lambda r: r["count"], reverse=True)
