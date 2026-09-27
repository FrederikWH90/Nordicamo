"""Pure helpers for the Media Archive (outlet directory and profiles)."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode

COUNTRY_CODES = {"denmark": "DK", "finland": "FI", "norway": "NO", "sweden": "SE"}
STATUS_ACTIVE_DAYS = 14
STATUS_QUIET_DAYS = 120
STATUSES = ("Active", "Quiet", "Historical")
SORTS = ("Most articles", "Most active now", "Latest article", "Name (A–Z)")
LINK_LABELS = {
    "website": "Website", "facebook_page": "Facebook", "facebook_group": "Facebook group",
    "twitter": "X / Twitter", "youtube": "YouTube", "telegram": "Telegram", "instagram": "Instagram",
    "tiktok": "TikTok", "gab": "Gab", "vkontakte": "VK",
}


def _parse(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def outlet_status(last_date: Any, today: date) -> str:
    """Based on the newest *collected* article, not on what the outlet may publish offline."""
    last = _parse(last_date)
    if last is None:
        return "Historical"
    age = (today - last).days
    if age <= STATUS_ACTIVE_DAYS:
        return "Active"
    if age <= STATUS_QUIET_DAYS:
        return "Quiet"
    return "Historical"


def time_ago(value: Any, today: date) -> str:
    last = _parse(value)
    if last is None:
        return "unknown"
    days = (today - last).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return last.strftime("%b %Y")


def status_line(outlet: Mapping[str, Any], today: date) -> tuple[str, str]:
    """(status, human text) e.g. ("Active", "last article 2 days ago")."""
    status = outlet_status(outlet.get("last_date"), today)
    return status, f"last article {time_ago(outlet.get('last_date'), today)}"


def coverage_years(outlet: Mapping[str, Any]) -> str:
    first, last = _parse(outlet.get("first_date")), _parse(outlet.get("last_date"))
    if not first or not last:
        return "—"
    return str(first.year) if first.year == last.year else f"{first.year}–{last.year}"


def teaser_share(outlet: Mapping[str, Any]) -> float:
    articles = int(outlet.get("articles") or 0)
    return int(outlet.get("teasers") or 0) / articles if articles else 0.0


def filter_directory(
    outlets: Iterable[Mapping[str, Any]],
    today: date,
    query: str = "",
    countries: Iterable[str] = (),
    orientation: str | None = None,
    status: str | None = None,
) -> list[Mapping[str, Any]]:
    needle = (query or "").strip().lower()
    wanted = {c.lower() for c in countries or ()}
    result = []
    for outlet in outlets or []:
        haystack = f"{outlet.get('name') or ''} {outlet.get('outlet') or ''}".lower()
        if needle and needle not in haystack:
            continue
        if wanted and str(outlet.get("country") or "").lower() not in wanted:
            continue
        if orientation and orientation != "All" and outlet.get("partisan") != orientation:
            continue
        if status and status != "All" and outlet_status(outlet.get("last_date"), today) != status:
            continue
        result.append(outlet)
    return result


def sort_directory(outlets: list[Mapping[str, Any]], sort: str) -> list[Mapping[str, Any]]:
    if sort == "Most active now":
        return sorted(outlets, key=lambda o: (-int(o.get("last_30_days") or 0), -int(o.get("articles") or 0)))
    if sort == "Latest article":
        return sorted(outlets, key=lambda o: str(o.get("last_date") or ""), reverse=True)
    if sort == "Name (A–Z)":
        return sorted(outlets, key=lambda o: str(o.get("name") or o.get("outlet") or "").lower())
    return sorted(outlets, key=lambda o: -int(o.get("articles") or 0))


def profile_url(outlet: str) -> str:
    return "?" + urlencode({"page": "Media", "media": outlet})


def workshop_url(outlet: Mapping[str, Any], today: date) -> str:
    """Open the Research Workshop pre-filtered to this outlet."""
    params = {"page": "Workshop", "out": outlet.get("outlet") or ""}
    first = _parse(outlet.get("first_date"))
    if first:
        params["y"] = f"{max(first.year, 2008)}-{today.year}"
    return "?" + urlencode(params)


def normalize_outlet(value: Any) -> str:
    key = str(value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if key.startswith(prefix):
            key = key[len(prefix):]
    if key.startswith("www."):
        key = key[4:]
    return key.rstrip("/")


def average_per_month(monthly_12: Iterable[int]) -> float:
    values = list(monthly_12 or [])
    return sum(values) / len(values) if values else 0.0
