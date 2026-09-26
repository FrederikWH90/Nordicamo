"""Pure helpers for the live-observatory landing page.

Everything here is Streamlit-free so it can be unit tested. Scrapers backfill
articles in batches, so the most recent days are still incomplete: windows end
COLLECTION_LAG_DAYS before today. The last sparkline bucket is always identical
to the headline "7-day" figure.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Mapping, Sequence

COUNTRIES = ["denmark", "finland", "norway", "sweden"]
SPARKLINE_WEEKS = 13
# Most articles arrive 1-2 days after publication (measured Sep 2026).
COLLECTION_LAG_DAYS = 2
# A UTF-8 lead byte for Latin-1 letters (Ã/Â) followed by a continuation byte.
_MOJIBAKE_PAIR = re.compile("[\u00c2\u00c3][\u0080-\u00bf]")


@dataclass
class CountryActivity:
    country: str
    last_7_days: int
    previous_7_days: int
    weekly_series: list[int] = field(default_factory=list)
    active_outlets: int = 0

    @property
    def delta_ratio(self) -> float | None:
        if self.previous_7_days <= 0:
            return None
        return (self.last_7_days - self.previous_7_days) / self.previous_7_days


def activity_window_end(today: date, lag_days: int = COLLECTION_LAG_DAYS) -> date:
    """Last day considered complete enough to report."""
    return today - timedelta(days=lag_days)


def activity_window_start(today: date, weeks: int = SPARKLINE_WEEKS, lag_days: int = COLLECTION_LAG_DAYS) -> date:
    """First day needed to build `weeks` 7-day blocks ending at the window end."""
    return activity_window_end(today, lag_days) - timedelta(days=7 * weeks - 1)


def weekly_blocks(
    daily_rows: Iterable[Mapping[str, object]],
    today: date,
    weeks: int = SPARKLINE_WEEKS,
    lag_days: int = COLLECTION_LAG_DAYS,
) -> list[int]:
    """Sum daily counts into 7-day blocks, oldest first, ending at the window end."""
    counts: dict[date, int] = {}
    for row in daily_rows or []:
        try:
            day = date.fromisoformat(str(row.get("date"))[:10])
            counts[day] = counts.get(day, 0) + int(row.get("count") or 0)
        except (TypeError, ValueError):
            continue

    window_end = activity_window_end(today, lag_days)
    blocks = []
    for block in range(weeks, 0, -1):
        end = window_end - timedelta(days=7 * (block - 1))
        blocks.append(sum(counts.get(end - timedelta(days=offset), 0) for offset in range(7)))
    return blocks


def summarise_country(
    country: str,
    daily_rows: Iterable[Mapping[str, object]],
    today: date,
    active_outlets: int = 0,
) -> CountryActivity:
    series = weekly_blocks(daily_rows, today)
    return CountryActivity(
        country=country,
        last_7_days=series[-1] if series else 0,
        previous_7_days=series[-2] if len(series) > 1 else 0,
        weekly_series=series,
        active_outlets=active_outlets,
    )


def format_delta(ratio: float | None) -> tuple[str, str]:
    """Return (label, tone) where tone is 'up', 'down' or 'flat'."""
    if ratio is None:
        return ("No comparison yet", "flat")
    pct = round(ratio * 100)
    if pct == 0:
        return ("Unchanged vs previous 7 days", "flat")
    arrow = "▲" if pct > 0 else "▼"
    return (f"{arrow} {abs(pct)}% vs previous 7 days", "up" if pct > 0 else "down")


def sparkline_svg(values: Sequence[int], color: str, width: int = 160, height: int = 40) -> str:
    """Inline SVG sparkline; the final point is highlighted as 'this week'."""
    if not values:
        return ""
    peak = max(values) or 1
    step = width / max(len(values) - 1, 1)
    pad = 4
    points = [
        (round(i * step, 1), round(height - pad - (v / peak) * (height - 2 * pad), 1))
        for i, v in enumerate(values)
    ]
    path = " ".join(f"{x},{y}" for x, y in points)
    area = f"0,{height} {path} {points[-1][0]},{height}"
    last_x, last_y = points[-1]
    safe_color = html.escape(color, quote=True)
    return (
        f"<svg class='spark' viewBox='0 0 {width} {height}' preserveAspectRatio='none' "
        f"role='img' aria-label='Weekly article volume, last {len(values)} weeks'>"
        f"<polygon points='{area}' fill='{safe_color}' opacity='0.12'/>"
        f"<polyline points='{path}' fill='none' stroke='{safe_color}' stroke-width='2' "
        f"stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/>"
        f"<circle cx='{last_x}' cy='{last_y}' r='3' fill='{safe_color}'/>"
        "</svg>"
    )


def relative_day(value: str | None, today: date) -> str:
    try:
        day = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    diff = (today - day).days
    if diff <= 0:
        return "Today"
    if diff == 1:
        return "Yesterday"
    if diff < 7:
        return f"{diff} days ago"
    return day.strftime("%-d %b %Y")


def display_domain(domain: str | None) -> str:
    value = (domain or "").strip().lower()
    return value[4:] if value.startswith("www.") else value


def select_latest_feed(
    articles: Sequence[Mapping[str, object]], limit: int = 8, per_outlet: int = 1
) -> list[Mapping[str, object]]:
    """Newest articles, interleaved across outlets so one prolific site can't flood the feed.

    Takes at most `per_outlet` articles per outlet and orders them round-robin:
    every outlet's newest article first, then every outlet's second newest.
    """
    ordered = sorted(
        (a for a in articles or [] if a.get("title") and a.get("domain")),
        key=lambda a: str(a.get("date") or ""),
        reverse=True,
    )
    by_outlet: dict[str, list[Mapping[str, object]]] = {}
    for article in ordered:
        bucket = by_outlet.setdefault(display_domain(str(article.get("domain"))), [])
        if len(bucket) < per_outlet:
            bucket.append(article)
    feed = []
    for rank in range(per_outlet):
        feed.extend(bucket[rank] for bucket in by_outlet.values() if len(bucket) > rank)
    return feed[:limit]


def nordic_totals(activities: Sequence[CountryActivity]) -> CountryActivity:
    weeks = max((len(a.weekly_series) for a in activities), default=0)
    series = [
        sum(a.weekly_series[i] for a in activities if len(a.weekly_series) == weeks)
        for i in range(weeks)
    ]
    return CountryActivity(
        country="nordic",
        last_7_days=sum(a.last_7_days for a in activities),
        previous_7_days=sum(a.previous_7_days for a in activities),
        weekly_series=series,
        active_outlets=sum(a.active_outlets for a in activities),
    )


def repair_mojibake(text: str | None) -> str:
    """Undo UTF-8 text that was decoded as Latin-1 (e.g. 'nÃ¤r' -> 'när').

    Some scraped titles are stored double-encoded, sometimes with bytes lost
    (an en dash can survive only as a lone 'â'). Display-side repair only;
    already-correct text is left untouched.
    """
    value = str(text or "")
    if not _MOJIBAKE_PAIR.search(value):
        return value
    for codec in ("cp1252", "latin-1"):
        try:
            return value.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    repaired = _MOJIBAKE_PAIR.sub(lambda m: m.group().encode("latin-1").decode("utf-8"), value)
    return re.sub(r"(?<=\s)â(?=\s)", "–", repaired)
