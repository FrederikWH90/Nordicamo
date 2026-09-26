"""
NORDICAMO Dashboard - Streamlit Frontend
====================================
Interactive dashboard for Nordic Alternative Media Observatory
"""

import sys
from pathlib import Path
import base64

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageChops

from analytics import build_umami_bootstrap_html
from navigation import ALLOWED_PAGES, LEGACY_PAGE_ALIASES, TOPBAR_NAV_ITEMS, country_from_query_param
from pages.about import show_about_page
from pages.explorer import MODE_DEEP_DIVE, show_explorer_page
from pages.get_access import show_get_access_page
from pages.media import show_media_page
from pages.overview import show_overview_page
from pages.workshop import show_workshop_page

# Page config
WEBSITE_ICON_PATH = Path(__file__).resolve().parent.parent / "graphics" / "website_icon_2.png"
st.set_page_config(
    page_title="NORDICAMO - Nordic Alternative Media Observatory",
    page_icon=Image.open(WEBSITE_ICON_PATH) if WEBSITE_ICON_PATH.exists() else "📰",
    layout="wide",
    initial_sidebar_state="auto"
)

# Session defaults for quick country navigation and page selection
if "quick_country" not in st.session_state:
    st.session_state["quick_country"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "Nordicamo"

# Paths
LOGO_PATH = Path(__file__).resolve().parent.parent / "graphics" / "Nordisk Alternativ Medieobservatorium.png"
TRIMMED_LOGO_PATH = Path(__file__).resolve().parent.parent / "graphics" / "logo_trimmed.png"
PREFERRED_LOGO_PATH = Path(__file__).resolve().parent.parent / "graphics" / "logo_trimmed_v2.png"


def get_trimmed_logo():
    """
    Load logo and auto-trim surrounding whitespace/transparency once.
    Returns path to trimmed logo if possible, else original.
    """
    # Prefer the manually provided trimmed asset if available
    if PREFERRED_LOGO_PATH.exists():
        return PREFERRED_LOGO_PATH
    try:
        if TRIMMED_LOGO_PATH.exists():
            return TRIMMED_LOGO_PATH
        if not LOGO_PATH.exists():
            return LOGO_PATH

        img = Image.open(LOGO_PATH).convert("RGBA")
        # Use alpha if present; otherwise trim near-white background
        alpha = img.split()[-1]
        bbox = alpha.getbbox()
        if not bbox:
            # Fallback: trim near-white
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            diff = Image.eval(ImageChops.difference(img, bg), lambda x: x)
            bbox = diff.getbbox()
        if bbox:
            trimmed = img.crop(bbox)
            trimmed.save(TRIMMED_LOGO_PATH)
            return TRIMMED_LOGO_PATH
    except Exception:
        pass
    return LOGO_PATH


def build_topbar_html(current_page: str) -> str:
    logo_to_use = get_trimmed_logo()
    logo_html = "<div class='topbar-logo'>NAMO</div>"
    if logo_to_use and logo_to_use.exists():
        data = logo_to_use.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        logo_html = f"<div class='topbar-logo'><img src='data:image/png;base64,{encoded}' alt='NAMO logo'/></div>"

    links = []
    for label, page_key in TOPBAR_NAV_ITEMS:
        active_class = "active" if current_page == page_key else ""
        cta_class = "cta" if page_key == "GetAccess" else ""
        links.append(
            f"<a class='nav-link {active_class} {cta_class}' href='?page={page_key}' target='_self' onclick=\"window.location.search='page={page_key}'; return false;\">{label}</a>"
        )
    links_html = "".join(links)

    return f"""
    <div class="topbar">
        <div class="topbar-inner">
            <a class="topbar-logo-link" href="/?page=Nordicamo" target="_self">{logo_html}</a>
            <nav class="topbar-nav">
                {links_html}
            </nav>
            <details class="mobile-menu">
                <summary aria-label="Open navigation menu"><span>Menu</span><span aria-hidden="true">☰</span></summary>
                <nav class="mobile-menu-panel" aria-label="Main navigation">{links_html}</nav>
            </details>
        </div>
    </div>
    """

# Custom CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

    :root {
        --color-bg: #f4f7f6;
        --color-card: #ffffff;
        --color-border: #dce3eb;
        --color-text: #222;
        --color-text-muted: #5a6a7a;
        --color-accent: #1f77b4;
        --color-accent-strong: #155d8f;
        --color-logo: #8c342f;
        --color-slider: #8c342f;
        --color-code-bg: #f5f7f9;
        --color-code-border: #d8dee9;
        --color-topbar: rgba(248, 251, 248, 0.95);
        --radius: 8px;
        --space-1: 4px;
        --space-2: 8px;
        --space-3: 12px;
        --space-4: 16px;
        --space-5: 24px;
        --space-6: 32px;
        --shadow-soft: 0 8px 16px rgba(0, 0, 0, 0.04);
    }

    body, .stApp {
        background: radial-gradient(circle at top left, #eef3f7 0%, #f8fbf9 45%, #f4f7f6 100%);
        color: var(--color-text);
        font-family: 'Inter', 'Helvetica', 'Arial', sans-serif;
        line-height: 1.5;
    }

    /* Keep filter controls readable even when the browser or Streamlit theme is dark. */
    div[data-testid="stSegmentedControl"] button,
    div[data-testid="stRadio"] label {
        color: #243447 !important;
    }
    div[data-testid="stSegmentedControl"] button {
        background-color: #ffffff !important;
        border-color: #cbd5df !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
        background-color: #1f77b4 !important;
        border-color: #1f77b4 !important;
        color: #ffffff !important;
    }
    div[data-testid="stSegmentedControl"] button:not([aria-pressed="true"]):hover,
    div[data-testid="stSegmentedControl"] button:not([aria-pressed="true"]):focus-visible {
        border-color: #155d8f !important;
        color: #173f5f !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"],
    ul[role="listbox"] {
        background-color: #ffffff !important;
        color: #243447 !important;
    }
    li[role="option"],
    div[role="option"] {
        background-color: #ffffff !important;
        color: #243447 !important;
    }
    li[role="option"]:hover,
    div[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[role="option"][aria-selected="true"] {
        background-color: #e8f1f8 !important;
        color: #173f5f !important;
    }

    /* Container spacing */
    .block-container {
        padding: calc(var(--space-6) + 72px) var(--space-5) var(--space-6);
        max-width: 1200px;
        margin: 0 auto;
    }

    /* Header */
    .main-header {
        font-size: 2.2rem;
        font-weight: 600;
        font-family: 'Manrope', 'Helvetica', 'Arial', sans-serif;
        color: var(--color-accent);
        margin: 0 0 var(--space-3) 0;
        line-height: 1.2;
    }

    .section-title {
        font-family: 'Manrope', 'Helvetica', 'Arial', sans-serif;
        font-size: 1.45rem;
        font-weight: 700;
        color: #111111;
        margin: 0 0 var(--space-2) 0;
    }
    .landing-about-title {
        color: var(--color-logo);
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .subtle {
        color: var(--color-text-muted);
        font-size: 0.95rem;
    }

    .workshop-card {
        border: 0;
        border-left: 2px solid var(--color-border);
        border-radius: 0;
        background: transparent;
        min-height: 154px;
        padding: 4px 0 4px var(--space-4);
        margin-bottom: var(--space-2);
    }
    .workshop-card-active {
        border-color: var(--color-accent-strong);
    }
    .workshop-card-title {
        font-family: 'Manrope', 'Helvetica', 'Arial', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: var(--color-text);
        margin-bottom: var(--space-2);
    }
    .workshop-card-question {
        font-size: 0.93rem;
        font-weight: 600;
        color: var(--color-accent-strong);
        margin-bottom: var(--space-2);
    }
    .workshop-card-body {
        color: var(--color-text-muted);
        font-size: 0.88rem;
        line-height: 1.45;
    }
    .workshop-preview-table-wrap {
        max-height: 520px;
        overflow: auto;
        border: 1px solid var(--color-border);
        background: var(--color-card);
    }
    .workshop-preview-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
    }
    .workshop-preview-table th {
        position: sticky;
        top: 0;
        z-index: 1;
        background: #edf3f7;
        color: var(--color-text);
        font-weight: 700;
    }
    .workshop-preview-table th,
    .workshop-preview-table td {
        padding: 8px 10px;
        border-bottom: 1px solid var(--color-border);
        text-align: left;
        vertical-align: top;
    }
    .workshop-preview-table td:nth-child(6) {
        min-width: 260px;
    }

    .hero {
        background: linear-gradient(135deg, #ffffff 0%, #f0f6f4 100%);
        border: 1px solid var(--color-border);
        border-radius: 16px;
        padding: 24px 28px;
        box-shadow: var(--shadow-soft);
    }
    .hero-right {
        text-align: left;
    }
    .observatory-status {
        border-left: 2px solid var(--color-logo);
        padding: 4px 0 4px 18px;
        min-height: 100%;
    }
    .observatory-status .chip {
        font-size: 13px;
        padding: 7px 11px;
    }
    .observatory-status .subtle {
        font-size: 1.05rem;
        line-height: 1.55;
    }
    .landing-kpi {
        min-height: 82px;
        padding: 6px 4px 2px;
        text-align: center;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .landing-kpi-label {
        color: var(--color-text-muted);
        font-size: 14px;
    }
    .landing-kpi-value {
        color: var(--color-text);
        font-size: 30px;
        font-weight: 600;
        line-height: 1.05;
    }
    .landing-kpi-divider {
        height: 2px;
        margin: 20px 0 26px;
        background: var(--color-logo);
    }
    .research-actions {
        border-top: 1px solid var(--color-border);
        border-bottom: 1px solid var(--color-border);
        margin: 28px 0 20px;
        padding: 18px 0 20px;
    }
    .research-actions-intro {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
    }
    .research-actions-kicker {
        color: var(--color-logo);
        font-size: 15px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .research-actions-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .research-action {
        display: block;
        min-height: 185px;
        padding: 4px 22px 6px;
        border-left: 1px solid var(--color-border);
        color: var(--color-text) !important;
        text-decoration: none !important;
    }
    .research-action:first-child {
        border-left: 0;
        padding-left: 0;
    }
    .research-action-title {
        color: var(--color-logo);
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 12px;
    }
    .research-action-body {
        color: var(--color-text-muted);
        font-size: 0.92rem;
        line-height: 1.5;
        max-width: 31rem;
    }
    .research-action-link {
        color: var(--color-logo);
        font-size: 0.86rem;
        font-weight: 700;
        margin-top: 13px;
    }
    .research-action:hover .research-action-title,
    .research-action:hover .research-action-link {
        color: var(--color-accent);
    }
    .overview-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 16px;
    }
    .overview-action {
        display: inline-flex;
        align-items: center;
        min-height: 38px;
        padding: 8px 12px;
        border: 1px solid var(--color-border);
        border-radius: 8px;
        background: #ffffff;
        color: #173f5f;
        font-weight: 700;
        text-decoration: none !important;
        box-shadow: var(--shadow-soft);
    }
    .overview-action.primary {
        background: #173f5f;
        border-color: #173f5f;
        color: #ffffff;
    }
    .overview-action:hover {
        background: #eef3f7;
    }
    .overview-action.primary:hover {
        background: #0f314d;
        color: #ffffff;
    }

    .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        background: #e8f2f8;
        color: #1f5b86;
        font-size: 12px;
        font-weight: 600;
    }

    .pulse {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
        70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
        100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }

    .topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1000;
        background: var(--color-topbar);
        border-bottom: 1px solid var(--color-border);
        backdrop-filter: blur(10px);
        padding: 12px 0;
    }
    .stMainBlockContainer {
        padding-top: 96px !important;
    }
    .topbar-inner {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 var(--space-5);
        display: flex;
        align-items: center;
        gap: 24px;
    }
    .topbar-logo img {
        height: 48px;
    }
    .topbar-nav {
        display: flex;
        gap: 18px;
        margin-left: auto;
        align-items: center;
        flex-wrap: wrap;
        justify-content: flex-end;
    }
    .mobile-menu {
        display: none;
    }
	    .nav-link {
	        font-family: 'Manrope', 'Helvetica', 'Arial', sans-serif;
	        font-size: 0.95rem;
	        font-weight: 600;
	        color: #0f3855 !important;
        text-decoration: none;
        padding: 8px 12px;
        border-radius: 8px;
        border: none;
        background: transparent;
        cursor: pointer;
        transition: background 120ms ease, color 120ms ease;
        display: inline-block;
        outline: none;
        box-shadow: none;
    }
	    .nav-link,
	    .nav-link:visited,
	    .nav-link:hover,
	    .nav-link:active {
	        color: #0f3855 !important;
	        text-decoration: none !important;
	    }
    .nav-link:focus,
    .nav-link:focus-visible {
        outline: none;
        box-shadow: none;
    }
    .nav-link:hover {
        background: #e6eef4;
    }
	    .nav-link.active {
	        color: #0f3855 !important;
	        text-decoration: none;
	    }
    .nav-link.cta {
        background: #173f5f;
        border: 1px solid #173f5f;
        color: #ffffff !important;
        box-shadow: 0 6px 14px rgba(23, 63, 95, 0.18);
    }
    .nav-link.cta:hover {
        background: #0f314d;
        color: #ffffff !important;
    }
    .nav-link.active.cta {
        background: #0f314d;
        border-color: #0f314d;
        color: #ffffff !important;
        box-shadow: 0 8px 18px rgba(23, 63, 95, 0.22);
    }

    .media-card {
        border: 1px solid var(--color-border);
        border-radius: 14px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.6);
        box-shadow: var(--shadow-soft);
        min-height: 210px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .media-card h3 {
        font-family: 'Manrope', 'Helvetica', 'Arial', sans-serif;
        font-size: 1.05rem;
        margin: 0 0 6px 0;
        color: #15212c;
    }
    .media-meta {
        font-size: 0.9rem;
        color: var(--color-text-muted);
        margin-bottom: 8px;
    }
    .media-domain {
        color: #173f5f;
        font-size: 0.85rem;
        font-weight: 700;
        margin-bottom: 8px;
        overflow-wrap: anywhere;
    }
    .media-pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 8px 0;
    }
    .media-pill {
        border: 1px solid var(--color-border);
        border-radius: 999px;
        padding: 4px 8px;
        background: #ffffff;
        color: var(--color-text-muted);
        font-size: 12px;
        font-weight: 700;
    }
    .media-latest {
        color: var(--color-text-muted);
        font-size: 12px;
        margin-top: 8px;
    }
    .media-count {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1f77b4;
    }
    .task-card {
        border: 1px solid var(--color-border);
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.75);
        padding: 12px 14px;
        min-height: 104px;
        box-shadow: var(--shadow-soft);
    }
    .task-card strong {
        color: #15212c;
    }
    .task-card .task-label {
        color: var(--color-text-muted);
        font-size: 0.9rem;
        margin-top: 4px;
    }
    .chart-context {
        color: var(--color-text-muted);
        font-size: 0.92rem;
        margin: -4px 0 12px 0;
    }
    .filter-summary {
        display: inline-flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 6px;
    }
    .filter-token {
        border: 1px solid var(--color-border);
        border-radius: 999px;
        background: #ffffff;
        padding: 3px 8px;
        color: var(--color-text-muted);
        font-size: 12px;
        font-weight: 700;
    }
    .access-checklist {
        border: 1px solid var(--color-border);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.82);
        padding: 16px 18px;
        box-shadow: var(--shadow-soft);
    }
    .access-checklist ul {
        margin: 8px 0 0 20px;
        padding: 0;
    }
    .stat-card {
        border: 1px solid var(--color-border);
        border-radius: 14px;
        padding: 14px 16px;
        background: #ffffff;
        box-shadow: var(--shadow-soft);
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .stat-card .label {
        font-size: 0.85rem;
        color: var(--color-text-muted);
    }
    .stat-card .value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #15212c;
    }

    /* Buttons */
    .stButton > button {
        background: var(--color-accent);
        color: #fff;
        border: none;
        padding: 10px 20px;
        border-radius: var(--radius);
        font-weight: 600;
        box-shadow: var(--shadow-soft);
        transition: all 120ms ease;
    }
    .stButton > button:hover {
        background: var(--color-accent-strong);
        transform: translateY(-1px);
    }

    div[data-baseweb="slider"] [role="slider"] {
        background-color: var(--color-slider) !important;
        border-color: var(--color-slider) !important;
    }
    div[data-baseweb="slider"] > div > div > div {
        background-color: var(--color-slider) !important;
    }
    div[data-baseweb="slider"] [data-testid="stTickBarTick"] {
        color: #0154a3 !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    div[data-baseweb="slider"] [data-testid="stTickBarTickLabel"] {
        color: #0154a3 !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    div[data-baseweb="slider"] [data-testid="stSliderTickBar"] span {
        display: none !important;
    }
    .stSlider [class*="st-c"] {
        color: #0154a3 !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    div[data-baseweb="slider"] [data-testid="stTickBarTickLabel"] + div,
    div[data-baseweb="slider"] .st-cs.st-ct.st-c8.st-c7.st-as.st-cu.st-cv,
    div[data-baseweb="slider"] .st-cs.st-ct.st-c8.st-c7.st-cs.st-cu.st-cv,
    .stSlider [class*="st-c"] {
        color: #0154a3 !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    div[data-baseweb="slider"] [role="tooltip"],
    div[data-baseweb="slider"] [data-testid="stTooltipIcon"] {
        display: none !important;
    }

    /* Cards / metrics */
    .metric-card, .stMetric {
        background: var(--color-card);
        padding: var(--space-4);
        border-radius: var(--radius);
        border: 1px solid var(--color-border);
        box-shadow: var(--shadow-soft);
        color: var(--color-text);
    }

    /* Plotly charts */
    .stPlotlyChart {
        background: var(--color-card) !important;
        border: 1px solid var(--color-border);
        border-radius: var(--radius);
        padding: var(--space-3);
    }

    .affiliation-text {
        margin-top: 4px;
    }
    .about-intro {
        color: #111111;
        margin-bottom: 18px;
    }
    .about-grid-spacer {
        height: 12px;
    }
    .about-card {
        background: rgba(255, 255, 255, 0.75);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        padding: 14px 16px;
        box-shadow: var(--shadow-soft);
        margin-bottom: 12px;
    }
    .about-row {
        align-items: stretch;
    }
    .about-row .about-card {
        height: 100%;
    }
    .about-card.top-row {
        min-height: 560px;
    }
    .about-card.bottom-row {
        min-height: 520px;
    }
    .about-card:empty {
        display: none;
    }
    .about-card h4 {
        margin-top: 0;
        margin-bottom: 4px;
    }
    .about-card h5 {
        margin-top: 18px;
        margin-bottom: 0;
        line-height: 1.1;
    }
    .about-card p {
        margin: 0 0 10px 0;
    }
    .about-card h4 + p,
    .about-card h5 + p {
        margin-top: 0;
    }
    .about-card p + h5,
    .about-card ul + h5 {
        margin-top: 22px;
    }
    .about-card p:last-child,
    .about-card ul:last-child {
        margin-bottom: 0;
    }
    .about-card ul {
        margin-top: 4px;
        margin-bottom: 12px;
        padding-left: 20px;
    }
    .about-card-spacer {
        height: 8px;
    }
    .affiliation-row {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        margin-top: 12px;
    }
    .affiliation-logo {
        width: 120px;
        height: auto;
    }

    /* Tables */
    .dataframe tbody tr:hover {
        background: #eef3f7;
    }

    .news-ticker {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        margin: 0 0 16px 0;
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid var(--color-border);
        border-radius: 999px;
        overflow: hidden;
        box-shadow: var(--shadow-soft);
    }

    .news-ticker-label {
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--color-logo);
        white-space: nowrap;
    }

    .news-ticker-track {
        position: relative;
        flex: 1;
        overflow: hidden;
        white-space: nowrap;
    }

    .news-ticker-items {
        display: inline-block;
        padding-left: 100%;
        animation: ticker-scroll var(--ticker-duration, 40s) linear infinite;
        font-size: 15px;
        color: var(--color-text-muted);
    }

    .news-ticker-item {
        display: inline-block;
        margin-right: 32px;
    }
    .news-ticker-item a,
    .signal-item a {
        color: inherit;
        text-decoration: none;
    }
    .news-ticker-item a:hover,
    .signal-item a:hover {
        color: var(--color-accent-strong);
        text-decoration: underline;
    }

    @keyframes ticker-scroll {
        0% {
            transform: translateX(0);
        }
        100% {
            transform: translateX(-100%);
        }
    }

    .footer-bar {
        margin-top: 28px;
        padding: 14px 18px;
        background: rgba(255, 255, 255, 0.7);
        border-top: 1px solid var(--color-border);
        border-radius: 12px;
        color: #111111;
        font-size: 13px;
        line-height: 1.5;
    }
    .footer-bar a {
        color: var(--color-accent-strong);
        text-decoration: none;
        font-weight: 600;
    }
    .footer-bar a:hover {
        text-decoration: underline;
    }

    @media (max-width: 900px) {
        .topbar {
            padding: 7px 0;
        }
        .topbar-inner {
            padding: 0 14px;
            gap: 12px;
        }
        .topbar-logo img {
            display: block;
            height: 38px;
            max-width: min(52vw, 210px);
            object-fit: contain;
            object-position: left center;
        }
        .topbar-nav {
            display: none;
        }
        .mobile-menu {
            display: block;
            position: relative;
            margin-left: auto;
        }
        .mobile-menu summary {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 9px;
            min-width: 88px;
            min-height: 44px;
            padding: 0 12px;
            border: 1px solid var(--color-border);
            border-radius: 9px;
            background: #fff;
            color: #0f3855;
            font-size: 0.9rem;
            font-weight: 700;
            list-style: none;
            cursor: pointer;
        }
        .mobile-menu summary::-webkit-details-marker {
            display: none;
        }
        .mobile-menu-panel {
            position: absolute;
            top: calc(100% + 8px);
            right: 0;
            z-index: 1100;
            display: flex;
            flex-direction: column;
            min-width: min(260px, calc(100vw - 28px));
            padding: 8px;
            border: 1px solid var(--color-border);
            border-radius: 12px;
            background: #fff;
            box-shadow: 0 12px 28px rgba(15, 56, 85, 0.18);
        }
        .mobile-menu-panel .nav-link {
            display: block;
            min-height: 44px;
            padding: 11px 12px;
            border-radius: 8px;
        }
        .stMainBlockContainer {
            padding: 0 !important;
            max-width: 100vw;
            overflow-x: clip;
        }
        .block-container {
            padding: 68px 18px 24px !important;
            max-width: 100%;
        }
        .main-header {
            font-size: clamp(1.65rem, 7vw, 2rem);
            overflow-wrap: anywhere;
        }
        .section-title {
            font-size: 1.2rem;
            line-height: 1.3;
        }
        .hero {
            padding: 18px 16px;
            border-radius: 12px;
        }
        .about-card.top-row,
        .about-card.bottom-row {
            min-height: 0;
        }
        .about-card {
            padding: 14px;
        }
        .media-card {
            min-height: 0;
            padding: 14px;
        }
        .stPlotlyChart {
            padding: 2px !important;
            max-width: 100%;
            overflow: hidden !important;
        }
        [data-testid="stDataFrame"],
        .workshop-preview-table-wrap {
            max-width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .workshop-preview-table {
            min-width: 680px;
        }
        .workshop-preview-table td:nth-child(6) {
            min-width: 180px;
        }
        .explorer-control-bar {
            top: 62px;
            padding: 9px 10px 2px;
        }
        .stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 44px;
        }
        .stTextInput input,
        .stTextArea textarea,
        .stDateInput input,
        div[data-baseweb="select"] [role="combobox"] {
            font-size: 16px !important;
        }
        div[data-baseweb="select"] [role="combobox"] {
            min-height: 44px;
        }
        .footer-bar {
            padding: 12px;
        }
        .research-actions-intro {
            display: block;
        }
        .research-actions-grid {
            grid-template-columns: 1fr;
        }
        .research-action,
        .research-action:first-child {
            min-height: 0;
            padding: 16px 0;
            border-left: 0;
            border-top: 1px solid var(--color-border);
        }
        .research-action:first-child {
            border-top: 0;
            padding-top: 4px;
        }
    }

    @media (max-width: 520px) {
        .block-container {
            padding: 68px 16px 22px !important;
        }
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 10px !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 0 !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:has(.landing-kpi) {
            flex: 1 1 calc(50% - 6px) !important;
            width: calc(50% - 6px) !important;
        }
        .landing-kpi {
            min-height: 68px;
            padding: 5px 2px;
            gap: 4px;
        }
        .landing-kpi-label {
            font-size: 0.76rem;
            line-height: 1.25;
        }
        .landing-kpi-value {
            font-size: clamp(1.25rem, 7vw, 1.7rem);
        }
        .stPlotlyChart .xtick text,
        .stPlotlyChart .ytick text,
        .stPlotlyChart .legend text {
            font-size: 10px !important;
        }
        .stPlotlyChart .modebar {
            transform: scale(0.85);
            transform-origin: top right;
        }
        .about-intro,
        .subtle {
            overflow-wrap: anywhere;
        }
        .mobile-menu-panel .nav-link.cta {
            text-align: center;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            scroll-behavior: auto !important;
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }

    /* Code blocks */
    code, pre {
        background: var(--color-code-bg);
        border-bottom: 1px solid var(--color-code-border);
        color: #a7adba;
    }
    code {
        padding: 2px 4px;
        vertical-align: text-bottom;
    }
    pre {
        padding: 1em;
        border-left: 2px solid #69c;
        border-radius: var(--radius);
    }

    /* Hide Streamlit status/toolbar strip */
    [data-testid="stStatusWidget"],
    [data-testid="stToolbar"] {
        display: none !important;
    }
    /* Hide default Streamlit sidebar and header */
    [data-testid="stSidebar"], [data-testid="stSidebarContent"], [data-testid="stHeader"] {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)
def main():
    """Main application."""
    components.html(build_umami_bootstrap_html(), height=0, width=0)

    page = None
    try:
        params = st.query_params
        page = params.get("page")
    except Exception:
        params = st.experimental_get_query_params()
        page_list = params.get("page")
        page = page_list[0] if page_list else None

    legacy_pages = LEGACY_PAGE_ALIASES
    if page in legacy_pages:
        page = legacy_pages[page]
        try:
            st.query_params["page"] = page
        except Exception:
            st.experimental_set_query_params(page=page)

    allowed_pages = ALLOWED_PAGES
    if page in allowed_pages:
        st.session_state["page"] = page

    current_page = st.session_state.get("page", "Nordicamo")
    if current_page not in allowed_pages:
        current_page = "Nordicamo"
        st.session_state["page"] = current_page

    if current_page != "Explorer":
        st.session_state["quick_country"] = None
    else:
        # Deep link from the landing page, e.g. ?page=Explorer&country=denmark
        deep_link_country = country_from_query_param(params.get("country"))
        if deep_link_country and "country_view" not in st.session_state:
            st.session_state["explorer_mode"] = MODE_DEEP_DIVE
            st.session_state["quick_country"] = deep_link_country
            st.session_state["deep_country"] = deep_link_country

    st.markdown(build_topbar_html(current_page), unsafe_allow_html=True)

    # Route to page
    if current_page == "Nordicamo":
        show_overview_page()
    elif current_page == "Explorer":
        show_explorer_page()
    elif current_page == "Workshop":
        show_workshop_page()
    elif current_page == "Media":
        show_media_page()
    elif current_page == "About":
        show_about_page()
    elif current_page == "GetAccess":
        show_get_access_page()


if __name__ == "__main__":
    main()
