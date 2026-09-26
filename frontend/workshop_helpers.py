"""Pure helpers for the Research Workshop (dataset builder).

A Selection is the researcher's definition of an article set. It round-trips
through URL query parameters, so every selection is a shareable, reproducible
link, and it renders into the text of an access request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping
from urllib.parse import urlencode, urlparse

MAX_BROWSER_PREVIEW_ROWS = 100
PUBLIC_BASE_URL = "https://nordicamo.org"
COUNTRIES = ("denmark", "finland", "norway", "sweden")
COUNTRY_CODES = {"denmark": "DK", "finland": "FI", "norway": "NO", "sweden": "SE"}
ORIENTATIONS = ("Right", "Left", "Other")
CATEGORY_LABELS = (
    "Politics & Governance",
    "Immigration & National Identity",
    "Health & Medicine",
    "Media & Censorship",
    "International Relations & Conflict",
    "Economy & Labor",
    "Crime & Justice",
    "Social Issues & Culture",
    "Environment, Climate & Energy",
    "Technology, Science & Digital Society",
    "Other",
)
TOPIC_OPTIONS = tuple(label for label in CATEGORY_LABELS if label != "Other")
CATEGORY_LABELS_BY_CASEFOLD = {label.casefold(): label for label in CATEGORY_LABELS}
LIST_SEPARATOR = "|"  # topic names contain commas


@dataclass(frozen=True)
class Selection:
    countries: tuple[str, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    orientation: str | None = None
    topics: tuple[str, ...] = ()
    outlets: tuple[str, ...] = ()
    keywords: str = ""

    @property
    def date_from(self) -> str | None:
        return f"{self.year_from}-01-01" if self.year_from else None

    @property
    def date_to(self) -> str | None:
        return f"{self.year_to}-12-31" if self.year_to else None

    def api_params(self) -> list[tuple[str, Any]]:
        params: list[tuple[str, Any]] = [("countries", c) for c in self.countries]
        params += [("topics", t) for t in self.topics]
        params += [("outlets", o) for o in self.outlets]
        for key, value in (("date_from", self.date_from), ("date_to", self.date_to),
                           ("partisan", self.orientation), ("q", self.keywords.strip() or None)):
            if value:
                params.append((key, value))
        return params

    def to_query_params(self) -> dict[str, str]:
        params = {"page": "Workshop"}
        if self.countries:
            params["c"] = ",".join(self.countries)
        if self.year_from and self.year_to:
            params["y"] = f"{self.year_from}-{self.year_to}"
        if self.orientation:
            params["o"] = self.orientation
        if self.topics:
            params["t"] = LIST_SEPARATOR.join(self.topics)
        if self.outlets:
            params["out"] = ",".join(self.outlets)
        if self.keywords.strip():
            params["q"] = self.keywords.strip()
        return params

    def share_url(self, base_url: str = PUBLIC_BASE_URL) -> str:
        return f"{base_url.rstrip('/')}/?{urlencode(self.to_query_params())}"


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def selection_from_query_params(params: Mapping[str, Any], year_min: int, year_max: int) -> Selection:
    """Parse a shared link. Unknown or invalid values are dropped, never trusted."""
    countries = tuple(c for c in _first(params.get("c")).lower().split(",") if c in COUNTRIES)
    year_from = year_to = None
    years = _first(params.get("y"))
    if "-" in years:
        try:
            a, b = (int(part) for part in years.split("-", 1))
            year_from, year_to = max(year_min, min(a, b)), min(year_max, max(a, b))
        except ValueError:
            year_from = year_to = None
    orientation = _first(params.get("o"))
    topics = tuple(t for t in _first(params.get("t")).split(LIST_SEPARATOR) if t in TOPIC_OPTIONS)
    outlets = tuple(o.strip().lower() for o in _first(params.get("out")).split(",") if o.strip())
    return Selection(
        countries=countries,
        year_from=year_from,
        year_to=year_to,
        orientation=orientation if orientation in ORIENTATIONS else None,
        topics=topics,
        outlets=outlets[:50],
        keywords=_first(params.get("q"))[:200],
    )


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    question: str
    selection: Selection = field(default_factory=Selection)


def presets(year_max: int) -> tuple[Preset, ...]:
    return (
        Preset("immigration_se", "Immigration in Sweden", "How has Swedish alternative media covered immigration since 2022?",
               Selection(countries=("sweden",), year_from=2022, year_to=year_max, topics=("Immigration & National Identity",))),
        Preset("covid", "COVID-19 and vaccines", "How did the four countries cover the pandemic and vaccines?",
               Selection(year_from=2020, year_to=2022, keywords="covid* OR corona* OR vaccin* OR vaksin* OR rokot*")),
        Preset("ukraine", "War in Ukraine", "How has the war in Ukraine been covered since the invasion?",
               Selection(year_from=2022, year_to=year_max, keywords="ukrain*")),
        Preset("climate_left", "Climate on the left", "How do left-wing outlets write about climate and energy?",
               Selection(orientation="Left", topics=("Environment, Climate & Energy",), year_from=2019, year_to=year_max)),
        Preset("media_dk", "Danish media criticism", "How do Danish outlets write about mainstream media and censorship?",
               Selection(countries=("denmark",), topics=("Media & Censorship",), year_from=2019, year_to=year_max)),
    )


def selection_summary_lines(selection: Selection) -> list[tuple[str, str]]:
    countries = ", ".join(c.capitalize() for c in selection.countries) or "All four countries"
    period = (f"{selection.year_from}–{selection.year_to}" if selection.year_from and selection.year_to
              else "All indexed years")
    return [
        ("Countries", countries),
        ("Period", period),
        ("Outlet orientation", selection.orientation or "All"),
        ("Topics", " or ".join(selection.topics) if selection.topics else "All topics"),
        ("Outlets", ", ".join(selection.outlets) if selection.outlets else "All outlets"),
        ("Keywords", selection.keywords.strip() or "None"),
    ]


def build_access_request_context(selection: Selection, result: Mapping[str, Any] | None = None,
                                 base_url: str = PUBLIC_BASE_URL) -> str:
    """Reproducible request text: the definition, its size, and a link that recreates it."""
    lines = ["Dataset selection from the Nordicamo Research Workshop", ""]
    lines += [f"{label}: {value}" for label, value in selection_summary_lines(selection)]
    if result:
        total = int(result.get("total") or 0)
        teasers = int(result.get("teasers") or 0)
        lines.append(f"Matching articles (at time of request): {total:,}"
                     + (f", of which {teasers:,} teaser-only" if teasers else ""))
    lines += [
        f"Selection link: {selection.share_url(base_url)}",
        "",
        "Purpose and affiliation: [please add before sending]",
        "Fields needed: [e.g. metadata only, or metadata + full text]",
    ]
    return "\n".join(lines)


def teaser_note(total: int, teasers: int) -> str:
    if not total or not teasers:
        return ""
    share = teasers / total
    return (f"{share:.0%} of these articles are teasers: the outlet only published the lead paragraph "
            "openly, so full text is not available for them.")


def format_category_labels(value: object, limit: int = 3) -> str:
    """Present category values as clean, canonical labels in the browser."""
    labels: list[str] = []

    def append_value(item: object) -> None:
        if isinstance(item, (list, tuple)):
            for nested_item in item:
                append_value(nested_item)
            return
        text = str(item or "").strip()
        if not text:
            return
        if text.startswith("["):
            try:
                append_value(json.loads(text))
                return
            except json.JSONDecodeError:
                text = text.strip("[] \\t\\r\\n\\\"'")
        canonical = CATEGORY_LABELS_BY_CASEFOLD.get(text.casefold(), text)
        if canonical and canonical not in labels:
            labels.append(canonical)

    append_value(value)
    return ", ".join(labels[:limit]) if labels else "Not yet categorized"


def preview_records(articles: list[dict[str, Any]], max_rows: int = MAX_BROWSER_PREVIEW_ROWS) -> list[dict[str, str]]:
    """Metadata-only rows for the browser; article text is never included."""
    rows: list[dict[str, str]] = []
    for article in articles[:max_rows]:
        country = str(article.get("country") or "").lower()
        rows.append(
            {
                "Date": str(article.get("date") or "")[:10],
                "Country": COUNTRY_CODES.get(country, country.upper()),
                "Outlet": str(article.get("outlet") or article.get("domain") or ""),
                "Orientation": str(article.get("partisan") or ""),
                "Topics": format_category_labels(article.get("categories")),
                "Title": str(article.get("title") or ""),
                "Article URL": str(article.get("url") or ""),
                "Teaser": "yes" if article.get("teaser") else "",
            }
        )
    return rows


def safe_article_url(value: object) -> str:
    """Return only absolute HTTP(S) article URLs for browser links."""
    url = str(value or "").strip()
    return url if urlparse(url).scheme in {"http", "https"} else ""


def with_changes(selection: Selection, **changes: Any) -> Selection:
    return replace(selection, **changes)
