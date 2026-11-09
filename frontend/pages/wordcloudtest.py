"""nordicamo.org/wordcloudtest — the Tag Cloud Generator inside the dashboard.

Every file in pages/ gets its own URL path in Streamlit, so this file is
served at /wordcloudtest without any web-server change. It shows the
generator from tagcloud/ (all processing happens in the visitor's browser).
"""

import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent
if str(FRONTEND) not in sys.path:
    sys.path.insert(0, str(FRONTEND))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from tagcloud_embed import build_embedded_html  # noqa: E402

st.set_page_config(page_title="Tag Cloud Generator · Nordicamo", layout="wide", initial_sidebar_state="collapsed")

# Hide Streamlit's own chrome and let the tool fill the window; the tool
# scrolls inside its frame like a normal page.
st.markdown(
    """
    <style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stHeader"],
    [data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
    .stApp, .stMain { background: #f4f7f6; }
    .block-container { padding: 0 !important; max-width: none !important; }
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    iframe[title="streamlit_components.v1.html"], .stIFrame, [data-testid="stIFrame"] {
        height: 100vh !important; width: 100% !important; display: block; border: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _page() -> str:
    return build_embedded_html()


components.html(_page(), height=900, scrolling=True)
