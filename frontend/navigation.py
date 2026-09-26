"""Navigation labels and route keys for the Streamlit shell."""

TOPBAR_NAV_ITEMS = [
    ("Explorer", "Explorer"),
    ("Research Workshop", "Workshop"),
    ("Browse Media", "Media"),
    ("About", "About"),
    ("Request Access", "GetAccess"),
]

ALLOWED_PAGES = {"Nordicamo", "Explorer", "Workshop", "Media", "About", "GetAccess"}

LEGACY_PAGE_ALIASES = {
    "Platform": "Nordicamo",
    "Countries": "Explorer",
    "Analysis": "Explorer",
    "Overview": "Explorer",
    "Explorer": "Explorer",
    "Browse Media": "Media",
    "About": "About",
    "Request Access": "GetAccess",
    "Full Data Access": "GetAccess",
}

COUNTRY_DEEP_LINKS = {"denmark", "finland", "norway", "sweden"}


def country_from_query_param(value) -> str | None:
    """Normalise a `?country=` deep-link value; unknown values are ignored."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    country = str(value or "").strip().lower()
    return country if country in COUNTRY_DEEP_LINKS else None
