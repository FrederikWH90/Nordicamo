"""About Nordicamo: what it is, how outlets and articles are selected and
processed, how to read the results, and the ethical safeguards.

The wording follows the approved About text; edits are limited to condensing
and making it more precise. Layout: one readable column in a logical order,
with an "On this page" menu (sticky on desktop, chips on mobile).
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

from pages.footer import render_footer_bar
from services.api import fetch_outlets, fetch_overview

GITHUB_URL = "https://github.com/FrederikWH90/Nordicamo"
ALTERPUBLICS_URL = "https://ruc.dk/en/forskningsprojekt/alternative-media-and-ideological-counterpublics"
DML_URL = "https://digitalmedialab.ruc.dk/"

SECTIONS = [
    ("what", "What Nordicamo is"),
    ("selection", "Outlet selection and scope"),
    ("collection", "Data collection"),
    ("quality", "Extraction and quality checks"),
    ("analysis", "Analytical approach"),
    ("ethics", "Ethics"),
    ("affiliations", "Affiliations"),
]

ABOUT_CSS = """
<style>
.ab-wrap{display:grid;grid-template-columns:210px minmax(0,1fr);gap:48px;align-items:start;}
.ab-toc{position:sticky;top:84px;font-size:.88rem;}
.ab-toc-label{font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--color-text-muted);margin-bottom:8px;}
.ab-toc a{display:block;padding:5px 0 5px 12px;border-left:2px solid var(--color-border);color:#3d4b5a!important;text-decoration:none!important;}
.ab-toc a:hover{border-left-color:var(--color-logo);color:#111!important;}
.ab-body{max-width:46rem;}
.ab-title{font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;color:#111;margin:0 0 12px;}
.ab-glance{display:flex;flex-wrap:wrap;gap:8px 22px;padding:12px 0;margin:4px 0 26px;border-top:1px solid var(--color-border);border-bottom:1px solid var(--color-border);font-size:.9rem;color:var(--color-text-muted);}
.ab-glance b{font-family:'Manrope',sans-serif;font-size:1.05rem;color:#111;margin-right:4px;}
.ab-section{scroll-margin-top:90px;margin:0 0 34px;}
.ab-section h2{font-family:'Manrope',sans-serif;font-size:1.3rem;font-weight:700;color:#111;margin:0 0 10px;padding:0;}
.ab-section h3{font-size:.98rem;font-weight:700;color:#111;margin:18px 0 6px;}
.ab-section p,.ab-section li{font-size:1rem;line-height:1.65;color:#1f2933;}
.ab-section p{margin:0 0 10px;}
.ab-section ul{margin:4px 0 12px 1.1rem;padding:0;}
.ab-lead{font-size:1.1rem!important;}
.ab-defs{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0 14px;}
.ab-def{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:12px 14px;}
.ab-def b{display:block;font-size:.95rem;color:#111;margin-bottom:4px;}
.ab-def span{font-size:.92rem;line-height:1.5;color:#3d4b5a;}
.ab-note{border-left:3px solid var(--color-logo);background:#fff;border-radius:0 8px 8px 0;padding:10px 14px;margin:12px 0;font-size:.95rem!important;}
.ab-uses{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:10px 0 14px;}
.ab-use{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:12px 14px;font-size:.93rem;line-height:1.5;color:#1f2933;}
.ab-use b{display:block;color:var(--color-logo);font-size:.8rem;letter-spacing:.05em;text-transform:uppercase;margin-bottom:4px;}
.ab-ethics{display:grid;gap:12px;margin-top:10px;}
.ab-ethic{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:14px 16px;}
.ab-ethic h3{margin-top:0;}
.ab-ethic p:last-child{margin-bottom:0;}
.ab-aff{display:grid;grid-template-columns:96px minmax(0,1fr);gap:18px;align-items:center;padding:14px 0;border-bottom:1px solid var(--color-border);}
.ab-aff img{width:96px;height:auto;}
.ab-aff p{margin:0;font-size:.95rem;}
.ab-section a{color:#173f5f;font-weight:600;}
.ab-section [data-testid='stHeaderActionElements']{display:none!important;}
.ab-body h1.ab-title{font-size:2rem!important;line-height:1.2!important;padding:0!important;margin:0 0 12px!important;}
.ab-section h2,.ab-section h3{padding:0!important;line-height:1.3!important;}
.ab-section h2{font-size:1.3rem!important;margin:0 0 10px!important;}
.ab-section h3{font-size:.98rem!important;margin:18px 0 6px!important;}
.ab-ethic h3{margin-top:0!important;}
@media (max-width:900px){
  .ab-wrap{grid-template-columns:1fr;gap:12px;}
  .ab-toc{position:static;display:flex;flex-wrap:wrap;gap:6px;}
  .ab-toc-label{width:100%;}
  .ab-toc a{border:1px solid var(--color-border);border-radius:999px;padding:4px 10px;background:#fff;}
  .ab-defs,.ab-uses{grid-template-columns:1fr;}
}
</style>
"""


def _image_data(path: Path) -> str:
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode('ascii')}" if path.exists() else ""


def glance_html(overview: dict | None, outlet_count: int | None = None) -> str:
    """Live key facts; omitted quietly when the API is unavailable.

    The outlet count comes from the Media Archive directory (www/non-www merged)
    so both pages show the same number.
    """
    if not overview:
        return ""
    earliest = str((overview.get("date_range") or {}).get("earliest") or "")[:4]
    outlets = outlet_count if outlet_count is not None else int(overview.get("total_outlets") or 0)
    items = [
        ("4", "countries"),
        (f"{outlets}", "outlets"),
        (f"{int(overview.get('total_articles') or 0):,}", "analysis-ready articles"),
        (f"since {earliest}" if earliest else "", "coverage"),
        ("Weekly", "collection"),
    ]
    return "<div class='ab-glance'>" + "".join(
        f"<span><b>{html.escape(value)}</b>{html.escape(label)}</span>" for value, label in items if value
    ) + "</div>"


def toc_html() -> str:
    links = "".join(f"<a href='#{key}' target='_self'>{html.escape(label)}</a>" for key, label in SECTIONS)
    return f"<nav class='ab-toc' aria-label='On this page'><div class='ab-toc-label'>On this page</div>{links}</nav>"


def body_html(overview: dict | None, alter_img: str, dml_img: str, outlet_count: int | None = None) -> str:
    return f"""
<div class='ab-body'>
<h1 class='ab-title'>About Nordicamo</h1>
{glance_html(overview, outlet_count)}

<section class='ab-section' id='what'>
<h2>What Nordicamo is</h2>
<p class='ab-lead'><strong>Nordicamo (Nordic Alternative Media Observatory)</strong> is a comparative platform for studying
alternative news media in Denmark, Finland, Norway and Sweden.</p>
<p>Here, alternative news media means publisher-operated outlets that position themselves as alternatives to mainstream
journalism, political institutions or dominant public narratives. The observatory covers outlet websites, not social media accounts.</p>
<p>It offers structured data and descriptive analytics for comparing publication patterns, outlet structures and topics
across countries and over time, and supports case selection, documentation and exploratory analysis.</p>
<p class='ab-note'>Nordicamo is not a complete census of alternative media activity, nor an evaluation of outlets' influence,
audience reach or societal impact.</p>
<p>Code and version history are on <a href='{GITHUB_URL}' target='_blank' rel='noopener'>GitHub</a>.</p>
</section>

<section class='ab-section' id='selection'>
<h2>Outlet selection and scope</h2>
<p>An outlet is included when it shows (1) sustained publication activity and (2) a clear alternative positioning in its
self-descriptions, editorial statements or consistent framing. Country experts help identify outlets and validate their
relevance. The outlet list is versioned, documenting additions, removals and the reasons for them.</p>
<h3>Current and historical coverage</h3>
<div class='ab-defs'>
<div class='ab-def'><b>Active observatory</b><span>Outlets meeting a minimum activity threshold in the current monitoring period.</span></div>
<div class='ab-def'><b>Historical data</b><span>A broader collection that can include outlets mainly active in earlier decades (e.g. the 2000s–2010s).</span></div>
</div>
<h3>Coverage limits</h3>
<p>Collection focuses on recently updated outlets with an accessible web presence, so historical coverage reflects the
outlets that were still technically reachable when collected. Because selection favours stability and technical
feasibility, short-lived projects, irregular publishers and sites without an indexable structure may be underrepresented.</p>
</section>

<section class='ab-section' id='collection'>
<h2>Data collection</h2>
<p>Starting from a seed list of outlet domains, article URLs are collected from sitemaps where available, and otherwise
from site structures such as category and archive pages; some outlets require custom scrapers. Collection respects
robots.txt and uses rate limits and backoff to minimise server load.</p>
<p>Outlets that block automated access, rely heavily on dynamic rendering or give unreliable timestamps may be only
partly covered.</p>
</section>

<section class='ab-section' id='quality'>
<h2>Extraction and quality checks</h2>
<p>Text is extracted with Trafilatura, cleaned of boilerplate and normalised into a common schema: publication date,
outlet, domain, country, URL and main text. Quality checks include routine sampling of extraction quality, duplicate
detection where feasible, and date verification, since some sites give ambiguous or unstable timestamps.</p>
<p>Lightweight metadata, such as self-described political orientation and news classification, is added from public
self-descriptions and manual checks. These tags are contextual aids, not authoritative classifications.</p>
</section>

<section class='ab-section' id='analysis'>
<h2>Analytical approach</h2>
<p>Nordicamo is descriptive and exploratory. It highlights high-level patterns in alternative news production: total
output, distribution across countries, outlet concentration, trends over time and, where available, topics.
These summaries help users:</p>
<div class='ab-uses'>
<div class='ab-use'><b>Detect</b>shifts and spikes that may warrant closer attention</div>
<div class='ab-use'><b>Compare</b>similarities and differences across countries</div>
<div class='ab-use'><b>Guide</b>qualitative work: close reading, case selection and interpretive analysis</div>
</div>
<p>Results should be read in light of the documented selection criteria, technical constraints and the evolving outlet list.</p>
</section>

<section class='ab-section' id='ethics'>
<h2>Ethics</h2>
<p>Nordicamo is designed for research on politically sensitive material and uses safeguards to reduce potential harm.</p>
<div class='ab-ethics'>
<div class='ab-ethic'><h3>Collection and data minimisation</h3>
<p>Only publicly accessible content is collected, with respect for site policies (robots.txt and terms of service where
applicable) and operational limits (rate limiting and backoff). Nordicamo does not collect user-level data, private
communications, comments or social media interactions unless a separately approved research purpose requires it.</p></div>
<div class='ab-ethic'><h3>Access, governance and retention</h3>
<p>Access to raw content is restricted, with access tiers, logging and retention and deletion practices. Public outputs
favour aggregated summaries. Data handling is documented and versioned, so it is transparent what is collected, how it is
processed and what is excluded.</p></div>
</div>
</section>

<section class='ab-section' id='affiliations'>
<h2>Affiliations</h2>
<div class='ab-aff'>{f"<img src='{alter_img}' alt='AlterPublics logo'/>" if alter_img else "<span></span>"}
<p><strong>Nordicamo</strong> is part of the Carlsberg-funded research project
<a href='{ALTERPUBLICS_URL}' target='_blank' rel='noopener'>AlterPublics</a> at Roskilde University (Denmark). AlterPublics
studies alternative media and counterpublics in the Nordic countries (Denmark, Sweden, Norway, Finland), Austria and Germany,
using big data, network analysis and computational text analysis to understand how alternative information environments
function and connect with traditional discourse.</p></div>
<div class='ab-aff'>{f"<img src='{dml_img}' alt='Digital Media Lab logo'/>" if dml_img else "<span></span>"}
<p><a href="{DML_URL}" target="_blank" rel="noopener"><strong>Digital Media Lab (DML)</strong></a> hosts this platform.
DML is a digital and physical lab in the Department of Communication and Arts at Roskilde University, supporting students,
faculty and external practitioners who work with digital data and digital methods.</p></div>
</section>
</div>
"""


def show_about_page() -> None:
    """Show the About page."""
    graphics = Path(__file__).resolve().parent.parent.parent / "graphics"
    alter_img = _image_data(graphics / "Alterpublics_newlogo.png")
    dml_img = _image_data(graphics / "DML_Logo_nobackground.png")
    directory = fetch_outlets() or {}
    outlet_count = len(directory.get("outlets", [])) or None
    page = ABOUT_CSS + f"<div class='ab-wrap'>{toc_html()}{body_html(fetch_overview(), alter_img, dml_img, outlet_count)}</div>"
    st.markdown(" ".join(line.strip() for line in page.splitlines() if line.strip()), unsafe_allow_html=True)
    render_footer_bar()
