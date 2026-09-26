"""Landing page: a live observatory first, an archive second.

Reading order:
1. Hero + live status  -> "is it running, and what did it see recently?"
2. Last 7 days by country -> the observatory's current signal
0. Scrolling 'Latest' ticker under the top bar -> what just came in
3. Full dataset -> the big N, then what is analysis-ready
4. Research pathways -> where to go next

All counts come from the cleaned article view (the same data the Explorer
charts use), so numbers on this page match the analysis pages.
"""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import streamlit as st

from live_activity import (
    COUNTRIES,
    CountryActivity,
    activity_window_end,
    activity_window_start,
    display_domain,
    format_delta,
    nordic_totals,
    relative_day,
    repair_mojibake,
    select_latest_feed,
    sparkline_svg,
    summarise_country,
)
from overview_helpers import format_freshness
from pages.footer import render_footer_bar
from services.api import (
    fetch_articles_over_time,
    fetch_landing_bundle,
    fetch_overview,
    fetch_top_outlets,
)

SPARK_COLOR = "#8c342f"
COUNTRY_CODES = {"denmark": "DK", "finland": "FI", "norway": "NO", "sweden": "SE"}

LANDING_CSS = """
<style>
.lp-hero{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:40px;align-items:end;padding:8px 0 28px;border-bottom:1px solid var(--color-border);}
.lp-kicker{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#166534;}
.lp-hero h1.lp-title{font-family:'Manrope',sans-serif!important;font-size:clamp(2.6rem,6vw,4.2rem)!important;font-weight:700!important;line-height:1!important;color:var(--color-logo)!important;margin:14px 0 10px!important;padding:0!important;letter-spacing:-.02em;}
.lp-hero h1.lp-title a{display:none!important;}
.lp-subtitle{font-family:'Manrope',sans-serif;font-size:clamp(1.2rem,2.2vw,1.6rem);font-weight:600;color:#111;margin:0 0 10px;}
.lp-lede{font-size:1.08rem;color:#111;opacity:.62;margin:0 0 22px;max-width:36rem;}
.lp-ctas{display:flex;flex-wrap:wrap;gap:10px;}
.lp-btn{display:inline-flex;align-items:center;min-height:42px;padding:9px 16px;border-radius:8px;font-weight:700;font-size:.95rem;text-decoration:none!important;border:1px solid #173f5f;}
.lp-btn.primary{background:#173f5f;color:#fff!important;}
.lp-btn.primary:hover{background:#0f314d;}
.lp-btn.secondary{background:#fff;color:#173f5f!important;}
.lp-btn.secondary:hover{background:#eef3f7;}
.lp-status{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:18px 20px;box-shadow:var(--shadow-soft);}
.lp-status-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.lp-status-label{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--color-text-muted);}
.lp-status-big{font-family:'Manrope',sans-serif;font-size:2.2rem;font-weight:700;line-height:1.05;color:#111;}
.lp-status-sub{font-size:.92rem;color:var(--color-text-muted);margin:2px 0 10px;}
.lp-status dl{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin:12px 0 0;padding-top:12px;border-top:1px solid var(--color-border);font-size:.9rem;}
.lp-status dt{color:var(--color-text-muted);}
.lp-status dd{margin:0;color:#111;font-weight:600;text-align:right;}
.lp-delta{font-size:.85rem;font-weight:700;}
.lp-delta.up{color:#166534;} .lp-delta.down{color:#9a3412;} .lp-delta.flat{color:var(--color-text-muted);}
.lp-section{margin:34px 0 0;}
.lp-section-head{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:14px;}
.lp-section h2.lp-h2{font-family:'Manrope',sans-serif!important;font-size:1.35rem!important;font-weight:700!important;color:#111!important;margin:0!important;padding:0!important;}
.lp-section h2.lp-h2 a{display:none!important;}
.lp-meta{font-size:.85rem;color:var(--color-text-muted);}
.lp-countries{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;}
.lp-country{display:block;background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:16px 16px 12px;text-decoration:none!important;color:inherit!important;transition:border-color .15s,box-shadow .15s;}
.lp-country:hover{border-color:#173f5f;box-shadow:0 6px 18px rgba(23,63,95,.08);}
.lp-country-name{font-weight:700;color:#111;font-size:1rem;}
.lp-country-num{font-family:'Manrope',sans-serif;font-size:1.9rem;font-weight:700;color:#111;line-height:1.1;margin-top:6px;}
.lp-country-unit{font-size:.8rem;color:var(--color-text-muted);}
.lp-country .spark{display:block;width:100%;height:40px;margin:10px 0 6px;}
.lp-country-foot{display:flex;justify-content:space-between;font-size:.8rem;color:var(--color-text-muted);border-top:1px solid var(--color-border);padding-top:8px;margin-top:4px;}
.lp-country-foot b{color:#173f5f;}
.lp-archive{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:18px 20px;}
.lp-archive-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px 12px;margin:6px 0 14px;}
.news-ticker-country{font-weight:500;color:var(--color-text-muted);font-size:.85em;}
.lp-bign{font-family:'Manrope',sans-serif;font-size:clamp(2.6rem,6vw,3.8rem);font-weight:700;line-height:1;color:var(--color-logo);letter-spacing:-.02em;}
.lp-bign-label{font-size:1rem;color:var(--color-text-muted);margin:6px 0 16px;padding-bottom:14px;border-bottom:1px solid var(--color-border);}
.lp-archive-num{font-family:'Manrope',sans-serif;font-size:1.55rem;font-weight:700;color:#111;line-height:1.1;}
.lp-archive-label{font-size:.82rem;color:var(--color-text-muted);}
.lp-archive p{font-size:.9rem;color:var(--color-text-muted);margin:0 0 12px;line-height:1.5;}
.lp-archive-note{font-size:.78rem!important;border-top:1px solid var(--color-border);padding-top:10px;}
.lp-link{color:#173f5f!important;font-weight:700;font-size:.9rem;text-decoration:none!important;display:inline-block;margin:2px 14px 2px 0;}
.lp-link:hover{text-decoration:underline!important;}
.lp-empty{padding:18px;background:#fff;border:1px dashed var(--color-border);border-radius:10px;color:var(--color-text-muted);font-size:.92rem;}
@media (max-width:900px){
  .lp-hero,  .lp-countries,.lp-archive-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
}
@media (max-width:520px){
  .lp-countries{grid-template-columns:1fr;}
  }
</style>
"""


def _html(markup: str) -> None:
    """Render HTML without Markdown turning indented lines into code blocks."""
    st.markdown(" ".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


def _research_action_items() -> str:
    """Render the three primary ways researchers can enter the observatory."""
    actions = [
        (
            "Compare",
            "Explorer",
            "Compare publication patterns, outlet structure, and topics across the Nordic region or within one country.",
        ),
        (
            "Investigate",
            "Media",
            "Inspect an outlet's profile, orientation, activity, and latest indexed articles.",
        ),
        (
            "Build a research case",
            "Workshop",
            "Start with a question, shape a bounded metadata preview, and prepare a documented dataset request.",
        ),
    ]
    return "".join(
        "<a class='research-action' href='?page={page}' target='_self'>"
        "<div class='research-action-title'>{title}</div>"
        "<div class='research-action-body'>{body}</div>"
        "<div class='research-action-link'>Open {title} <span aria-hidden='true'>&rarr;</span></div>"
        "</a>".format(
            title=html.escape(title),
            page=html.escape(page, quote=True),
            body=html.escape(body),
        )
        for title, page, body in actions
    )


def load_country_activity(today: date) -> list[CountryActivity]:
    """Daily counts for the last 13 weeks plus outlets active in the latest 7-day window."""
    window_start = activity_window_start(today).isoformat()
    window_end = activity_window_end(today)
    week_start = (window_end - timedelta(days=6)).isoformat()
    window_end = window_end.isoformat()
    activity = []
    for country in COUNTRIES:
        daily = fetch_articles_over_time(
            country=country, granularity="day", date_from=window_start, date_to=window_end
        ) or {}
        outlets = fetch_top_outlets(
            country=country, date_from=week_start, date_to=window_end, limit=1000
        ) or {}
        activity.append(
            summarise_country(
                country,
                daily.get("data", []),
                today,
                active_outlets=len({display_domain(o.get("domain")) for o in outlets.get("data", [])}),
            )
        )
    return activity


def domain_country_map(today: date) -> dict[str, str]:
    """Outlet -> country, from the outlets seen in the last 14 days."""
    since = (today - timedelta(days=14)).isoformat()
    mapping: dict[str, str] = {}
    for country in COUNTRIES:
        for outlet in (fetch_top_outlets(country=country, date_from=since, limit=1000) or {}).get("data", []):
            mapping[display_domain(outlet.get("domain"))] = country
    return mapping


def hero_html(nordic: CountryActivity, freshness: dict | None, today: date) -> str:
    delta_label, tone = format_delta(nordic.delta_ratio)
    if freshness:
        updated_text, last_article = format_freshness(freshness)
        updated_text = updated_text.replace("Dashboard last updated: ", "")
        last_article_text = relative_day(last_article, today) or last_article
    else:
        updated_text, last_article_text = "unavailable", "unavailable"

    return f"""
    <section class="lp-hero">
      <div>
        <div class="lp-kicker"><span class="pulse"></span>Live · collecting daily</div>
        <h1 class="lp-title">Nordicamo</h1>
        <p class="lp-subtitle">The Nordic Alternative Media Observatory</p>
        <p class="lp-lede">Monitoring alternative news media content from Denmark, Finland, Norway and Sweden.</p>
        <div class="lp-ctas">
          <a class="lp-btn primary" href="?page=Explorer" target="_self">Explore the data</a>
        </div>
      </div>
      <aside class="lp-status" aria-label="Observatory status">
        <div class="lp-status-head">
          <span class="lp-status-label">Articles published, latest 7 days</span>
        </div>
        <div class="lp-status-big">{nordic.last_7_days:,}</div>
        <div class="lp-status-sub">articles from {nordic.active_outlets} active outlets</div>
        <span class="lp-delta {tone}">{html.escape(delta_label)}</span>
        <dl>
          <dt>Latest article</dt><dd>{html.escape(last_article_text)}</dd>
          <dt>Database updated</dt><dd>{html.escape(updated_text)}</dd>
        </dl>
      </aside>
    </section>
    """


def country_cards_html(activity: list[CountryActivity]) -> str:
    cards = []
    for item in activity:
        label, tone = format_delta(item.delta_ratio)
        name = item.country.capitalize()
        cards.append(
            f"""
            <a class="lp-country" href="?page=Explorer&country={item.country}" target="_self"
               aria-label="Open {name} in the Explorer">
              <div class="lp-country-name">{name}</div>
              <div class="lp-country-num">{item.last_7_days:,} <span class="lp-country-unit">articles</span></div>
              <span class="lp-delta {tone}">{html.escape(label)}</span>
              {sparkline_svg(item.weekly_series, SPARK_COLOR)}
              <div class="lp-country-foot"><span>{item.active_outlets} active outlets</span><b>Open {name} →</b></div>
            </a>
            """
        )
    return f"<div class='lp-countries'>{''.join(cards)}</div>"


def ticker_html(articles: list[dict], countries: dict[str, str]) -> str:
    """The scrolling 'Latest' news bar shown under the top bar."""
    if not articles:
        return ""
    items = []
    for article in articles:
        outlet = display_domain(article.get("domain")) or "Unknown outlet"
        country = countries.get(outlet, "")
        code = COUNTRY_CODES.get(country, "")
        country_html = f" <span class='news-ticker-country'>({code})</span>" if code else ""
        title = html.escape(repair_mojibake(article.get("title")) or "Untitled")
        url = article.get("url")
        if url:
            title = (
                f"<a href='{html.escape(str(url), quote=True)}' "
                f"target='_blank' rel='noopener noreferrer'>{title}</a>"
            )
        date_text = html.escape(str(article.get("date") or "")[:10])
        items.append(
            f"<span class='news-ticker-item'><strong>{html.escape(outlet)}</strong>{country_html} — {title} ({date_text})</span>"
        )
    duration = max(75, min(210, len(items) * 5))
    return (
        "<div class='news-ticker'><div class='news-ticker-label'>Latest</div>"
        "<div class='news-ticker-track'>"
        f"<div class='news-ticker-items' style='--ticker-duration: {duration}s'>{''.join(items)}</div>"
        "</div></div>"
    )


def archive_html(overview: dict | None, raw_total: int | None) -> str:
    if not overview:
        return "<div class='lp-empty'>Archive statistics are temporarily unavailable.</div>"
    date_range = overview.get("date_range") or {}
    start = str(date_range.get("earliest") or "")[:4] or "—"
    end = str(date_range.get("latest") or "")[:4] or "—"
    total = int(overview.get("total_articles") or 0)
    note = ""
    if raw_total and raw_total > total:
        note = (
            f"<p class='lp-archive-note'>{raw_total - total:,} of the collected articles are held back from "
            "the analysis-ready set (excluded outlets, non-article pages, and records with unreliable dates).</p>"
        )
    big_n = max(int(raw_total or 0), total)
    return f"""
    <div class="lp-archive">
      <div class="lp-bign">{big_n:,}</div>
      <div class="lp-bign-label">articles collected from Nordic alternative news media</div>
      <div class="lp-archive-grid">
        <div><div class="lp-archive-num">{total:,}</div><div class="lp-archive-label">analysis-ready articles</div></div>
        <div><div class="lp-archive-num">{int(overview.get('total_outlets') or 0)}</div><div class="lp-archive-label">outlets</div></div>
        <div><div class="lp-archive-num">{start}–{end}</div><div class="lp-archive-label">coverage</div></div>
        <div><div class="lp-archive-num">{len(overview.get('by_country') or {}) or 4}</div><div class="lp-archive-label">countries</div></div>
      </div>
      <a class="lp-link" href="?page=Media" target="_self">Browse outlets →</a>
      <a class="lp-link" href="?page=Workshop" target="_self">Build a dataset →</a>
      {note}
    </div>
    """


def show_overview_page() -> None:
    """Show the landing page."""
    _html(LANDING_CSS)
    today = datetime.now().date()

    landing = fetch_landing_bundle() or {}
    overview = fetch_overview()
    activity = load_country_activity(today)
    nordic = nordic_totals(activity)

    ticker = select_latest_feed(landing.get("latest_articles") or [], limit=60, per_outlet=2)
    _html(ticker_html(ticker, domain_country_map(today)))
    _html(hero_html(nordic, landing.get("freshness"), today))

    window_end = activity_window_end(today)
    _html(
        f"""
        <section class="lp-section">
          <div class="lp-section-head">
            <h2 class="lp-h2">This week across the Nordics</h2>
            <span class="lp-meta">Published {(window_end - timedelta(days=6)).strftime('%-d %b')} – {window_end.strftime('%-d %b %Y')}
            · the last 2 days are still being collected · trend: 13 weeks</span>
          </div>
          {country_cards_html(activity)}
        </section>
        """
    )

    raw_total = (landing.get("overview") or {}).get("total_articles")
    _html(
        f"""
        <section class="lp-section">
          <div class="lp-section-head"><h2 class="lp-h2">Full dataset</h2></div>
          {archive_html(overview, raw_total)}
        </section>
        """
    )

    _html(
        f"""
        <section class='research-actions' aria-label='Research actions'>
          <div class='research-actions-intro'>
            <div class='research-actions-kicker'>Work with the data</div>
          </div>
          <div class='research-actions-grid'>{_research_action_items()}</div>
        </section>
        """
    )
    render_footer_bar()
