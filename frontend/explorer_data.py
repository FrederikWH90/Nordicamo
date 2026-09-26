"""Data loading and shaping for the Explorer.

Two layers:
- Pure transforms (no Streamlit, unit tested) that turn API rows into chart-ready frames.
- Two cached loaders, one per Explorer view, that fetch everything a view needs
  in parallel so the page renders from a single cache hit.

Topics are multi-label (an article can carry several), so topic figures are
always "% of articles tagged with the topic", never raw tag counts: raw counts
mostly mirror how many articles were collected and hide real agenda shifts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd
import requests
import streamlit as st

from config import get_api_base_url
from live_activity import display_domain

COUNTRIES = ["denmark", "finland", "norway", "sweden"]
ORIENTATIONS = ["Right", "Left", "Other"]

# Validated with the dataviz palette checker (all-pairs CVD + contrast pass).
COUNTRY_COLORS = {
    "denmark": "#c8102e",
    "finland": "#2a5fb8",
    "norway": "#199e70",
    "sweden": "#b8860b",
}
ORIENTATION_COLORS = {
    "Right": "#2a78d6",
    "Left": "#d0343f",
    "Other": "#8a8f98",
    "Unclassified": "#c5c9cf",
}
NEUTRAL = "#c5c9cf"
SEQUENTIAL_BLUE = [
    [0.0, "#f3f7fc"],
    [0.25, "#b7d3f6"],
    [0.5, "#6da7ec"],
    [0.75, "#2a78d6"],
    [1.0, "#0d366b"],
]

# Topics excluded from charts: a catch-all bucket says nothing about agendas.
EXCLUDED_TOPICS = {"Other"}
# Years/outlets with fewer articles than this give unstable topic shares.
MIN_TOPIC_BASE = 200

API_TIMEOUT = (3, 30)


# ---------------------------------------------------------------------------
# Pure transforms
# ---------------------------------------------------------------------------

def monthly_frame(rows: Iterable[Mapping[str, Any]], today: date | None = None) -> pd.DataFrame:
    """Monthly counts as a frame, dropping the in-progress calendar month."""
    frame = pd.DataFrame(list(rows or []), columns=["date", "count"])
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["count"] = pd.to_numeric(frame["count"], errors="coerce").fillna(0).astype(int)
    frame = frame.dropna(subset=["date"]).sort_values("date")
    current = pd.Timestamp(today or date.today()).to_period("M")
    return frame[frame["date"].dt.to_period("M") != current].reset_index(drop=True)


def outlet_shares(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Outlets with article counts and share of the selection, www-variants merged."""
    merged: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        key = display_domain(row.get("domain"))
        if not key:
            continue
        entry = merged.setdefault(
            key,
            {"outlet": key, "name": row.get("outlet_name") or key, "partisan": row.get("partisan") or "Unclassified", "count": 0},
        )
        entry["count"] += int(row.get("count") or 0)
    frame = pd.DataFrame(list(merged.values()), columns=["outlet", "name", "partisan", "count"])
    if frame.empty:
        frame["share"] = []
        return frame
    total = frame["count"].sum()
    frame["share"] = frame["count"] / total if total else 0.0
    return frame.sort_values("count", ascending=False).reset_index(drop=True)


def top_n_share(shares: pd.DataFrame, n: int = 3) -> float:
    if shares.empty:
        return 0.0
    return float(shares["share"].head(n).sum())


def concentration_segments(shares_by_country: Mapping[str, pd.DataFrame], top: int = 5) -> pd.DataFrame:
    """Stacked-bar rows: each country's top outlets by share plus 'All other outlets'."""
    rows = []
    for country, shares in shares_by_country.items():
        if shares.empty:
            continue
        for rank, record in enumerate(shares.head(top).itertuples(), start=1):
            rows.append({"country": country, "segment": record.outlet, "rank": rank, "share": record.share})
        rest = float(shares["share"].iloc[top:].sum())
        if rest > 0:
            rows.append({"country": country, "segment": "All other outlets", "rank": top + 1, "share": rest})
    return pd.DataFrame(rows, columns=["country", "segment", "rank", "share"])


def orientation_mix(shares: pd.DataFrame) -> dict[str, float]:
    if shares.empty:
        return {}
    grouped = shares.groupby("partisan")["share"].sum()
    order = ORIENTATIONS + ["Unclassified"]
    return {label: float(grouped[label]) for label in order if label in grouped and grouped[label] > 0}


def topic_share_by_year(
    topic_rows: Iterable[Mapping[str, Any]],
    volume_rows: Iterable[Mapping[str, Any]],
    min_base: int = MIN_TOPIC_BASE,
) -> pd.DataFrame:
    """Share of each year's articles tagged with each topic (0-1)."""
    volume = {str(r.get("date"))[:4]: int(r.get("count") or 0) for r in volume_rows or []}
    rows = []
    for row in topic_rows or []:
        year = str(row.get("date"))[:4]
        topic = row.get("category")
        base = volume.get(year, 0)
        if not topic or topic in EXCLUDED_TOPICS or base < min_base:
            continue
        rows.append({"year": int(year), "topic": topic, "share": int(row.get("count") or 0) / base, "base": base})
    return pd.DataFrame(rows, columns=["year", "topic", "share", "base"])


def topic_profile(
    topic_rows: Iterable[Mapping[str, Any]],
    total_articles: int,
    min_base: int = MIN_TOPIC_BASE,
) -> dict[str, float]:
    """Share of all articles in the period tagged with each topic."""
    if total_articles < min_base:
        return {}
    totals: dict[str, int] = {}
    for row in topic_rows or []:
        topic = row.get("category")
        if not topic or topic in EXCLUDED_TOPICS:
            continue
        totals[topic] = totals.get(topic, 0) + int(row.get("count") or 0)
    return {topic: count / total_articles for topic, count in totals.items()}


def profile_matrix(profiles: Mapping[str, Mapping[str, float]], row_order: list[str] | None = None) -> pd.DataFrame:
    """Topics (rows) x entities (columns); rows sorted by mean share, highest first."""
    frame = pd.DataFrame(profiles).fillna(0.0)
    if frame.empty:
        return frame
    if row_order:
        frame = frame.reindex([r for r in row_order if r in frame.index])
    else:
        frame = frame.loc[frame.mean(axis=1).sort_values(ascending=False).index]
    return frame


def outlet_activity_matrix(
    rows: Iterable[Mapping[str, Any]],
    outlet_order: list[str],
    today: date | None = None,
) -> pd.DataFrame:
    """Outlets (rows) x months (columns) article counts, zero-filled, in-progress month dropped."""
    frame = pd.DataFrame(list(rows or []), columns=["date", "outlet", "count"])
    if frame.empty or not outlet_order:
        return pd.DataFrame()
    frame["outlet"] = frame["outlet"].map(display_domain)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    current = pd.Timestamp(today or date.today()).to_period("M")
    frame = frame[frame["date"].dt.to_period("M") != current]
    if frame.empty:
        return pd.DataFrame()
    matrix = frame.pivot_table(index="outlet", columns="date", values="count", aggfunc="sum", fill_value=0)
    months = pd.date_range(matrix.columns.min(), matrix.columns.max(), freq="MS")
    return matrix.reindex(index=[o for o in outlet_order if o in matrix.index], columns=months, fill_value=0)


def largest_topic_gaps(matrix: pd.DataFrame, n: int = 2) -> list[tuple[str, str, float, float]]:
    """(topic, entity, entity_share, mean_of_others) for the biggest over-representations."""
    if matrix.empty or matrix.shape[1] < 2:
        return []
    gaps = []
    for topic, row in matrix.iterrows():
        for entity, value in row.items():
            others = row.drop(entity).mean()
            gaps.append((value - others, topic, entity, float(value), float(others)))
    gaps.sort(reverse=True)
    return [(topic, entity, value, others) for _, topic, entity, value, others in gaps[:n]]


def pct(value: float, digits: int = 0) -> str:
    return f"{value * 100:.{digits}f}%"


def concentration_sentence(shares_by_country: Mapping[str, pd.DataFrame]) -> str:
    stats = {c: top_n_share(s, 3) for c, s in shares_by_country.items() if not s.empty}
    if len(stats) < 2:
        return ""
    high = max(stats, key=stats.get)
    low = min(stats, key=stats.get)
    return (
        f"The three largest outlets produce {pct(stats[high])} of all articles in {high.capitalize()}, "
        f"against {pct(stats[low])} in {low.capitalize()}."
    )


def topic_gap_sentence(matrix: pd.DataFrame, entity_label=str.capitalize) -> str:
    gaps = largest_topic_gaps(matrix, n=2)
    if not gaps:
        return ""
    parts = [
        f"{topic} appears in {pct(value)} of {entity_label(entity)}'s articles (others: {pct(others)})"
        for topic, entity, value, others in gaps
    ]
    return "Largest differences: " + "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _get(path: str, params: Mapping[str, Any]) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    try:
        response = requests.get(f"{get_api_base_url()}{path}", params=clean, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _parallel(calls: Mapping[Any, tuple[str, Mapping[str, Any]]]) -> dict[Any, Any]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {key: pool.submit(_get, path, params) for key, (path, params) in calls.items()}
        return {key: future.result() for key, future in futures.items()}


def _data(payload: Any) -> list:
    return (payload or {}).get("data", []) if isinstance(payload, dict) else []


@st.cache_data(ttl=600, show_spinner="Loading the Nordic comparison…")
def load_comparison(date_from: str, date_to: str, partisan: str | None) -> dict[str, Any]:
    base = {"partisan": partisan, "date_from": date_from, "date_to": date_to}
    calls = {}
    for country in COUNTRIES:
        calls[("monthly", country)] = ("/api/stats/articles-over-time", {**base, "country": country, "granularity": "month"})
        calls[("yearly", country)] = ("/api/stats/articles-over-time", {**base, "country": country, "granularity": "year"})
        calls[("outlets", country)] = ("/api/stats/top-outlets", {**base, "country": country, "limit": 1000})
        calls[("topics", country)] = ("/api/stats/categories/over-time", {**base, "country": country, "granularity": "year", "limit": 20})
    results = _parallel(calls)
    return {
        kind: {country: _data(results[(kind, country)]) for country in COUNTRIES}
        for kind in ("monthly", "yearly", "outlets", "topics")
    } | {"failed": sorted({k[0] for k, v in results.items() if v is None})}


@st.cache_data(ttl=600, show_spinner="Loading the country view…")
def load_country(country: str, date_from: str, date_to: str, partisan: str | None, top_outlets: int = 15) -> dict[str, Any]:
    base = {"date_from": date_from, "date_to": date_to}
    orientations = [partisan] if partisan else ORIENTATIONS
    calls = {
        ("monthly", o): ("/api/stats/articles-over-time", {**base, "country": country, "partisan": o, "granularity": "month"})
        for o in orientations
    }
    calls["outlets"] = ("/api/stats/top-outlets", {**base, "country": country, "partisan": partisan, "limit": 1000})
    calls["yearly"] = ("/api/stats/articles-over-time", {**base, "country": country, "partisan": partisan, "granularity": "year"})
    calls["topics"] = ("/api/stats/categories/over-time", {**base, "country": country, "partisan": partisan, "granularity": "year", "limit": 20})
    calls["nordic_yearly"] = ("/api/stats/articles-over-time", {**base, "partisan": partisan, "granularity": "year"})
    calls["nordic_topics"] = ("/api/stats/categories/over-time", {**base, "partisan": partisan, "granularity": "year", "limit": 20})
    first = _parallel(calls)

    shares = outlet_shares(_data(first["outlets"]))
    top = shares.head(top_outlets)
    raw_domains = sorted({row["domain"] for row in _data(first["outlets"]) if display_domain(row.get("domain")) in set(top["outlet"])})
    second_calls = {
        "outlet_monthly": (
            "/api/stats/articles-over-time-by-outlet",
            {**base, "country": country, "outlets": ",".join(raw_domains), "granularity": "month"},
        )
    } if raw_domains else {}
    for outlet in top["outlet"].head(12):
        variants = [d for d in raw_domains if display_domain(d) == outlet]
        second_calls[("outlet_topics", outlet)] = (
            "/api/stats/categories/over-time",
            {**base, "country": country, "partisan": partisan, "outlets": ",".join(variants), "granularity": "year", "limit": 20},
        )
    second = _parallel(second_calls) if second_calls else {}

    return {
        "monthly": {o: _data(first[("monthly", o)]) for o in orientations},
        "outlets": _data(first["outlets"]),
        "yearly": _data(first["yearly"]),
        "topics": _data(first["topics"]),
        "nordic_yearly": _data(first["nordic_yearly"]),
        "nordic_topics": _data(first["nordic_topics"]),
        "outlet_monthly": _data(second.get("outlet_monthly")),
        "outlet_topics": {key[1]: _data(value) for key, value in second.items() if isinstance(key, tuple)},
        "failed": sorted({str(k if isinstance(k, str) else k[0]) for k, v in {**first, **second}.items() if v is None}),
    }
