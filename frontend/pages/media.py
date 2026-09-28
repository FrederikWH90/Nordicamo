"""Media Archive: every outlet in the observatory, and a profile per outlet.

Directory: one API call, filters and sorting in memory, cards rendered as a
single HTML block (links, not Streamlit buttons) so the page stays fast.
Profile: who the outlet is (in its own words), how active it is, what it writes
about compared with its country, its latest articles, and outlets with a
similar agenda.
"""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from explorer_data import COUNTRY_COLORS, ORIENTATION_COLORS, short_topic
from live_activity import repair_mojibake, sparkline_svg
from media_helpers import (
    COUNTRY_CODES,
    LINK_LABELS,
    SORTS,
    STATUSES,
    average_per_month,
    coverage_years,
    filter_directory,
    normalize_outlet,
    profile_url,
    sort_directory,
    status_line,
    teaser_share,
    time_ago,
    workshop_url,
)
from pages.explorer import EXPLORER_CSS, _html, _plot, _plot_responsive, _style, _year_axis, insight_html, section_header
from pages.footer import render_footer_bar
from services.api import fetch_outlet, fetch_outlets
from workshop_helpers import format_category_labels

STATUS_COLORS = {"Active": "#1f9d55", "Quiet": "#d69e2e", "Historical": "#8a8f98"}

MEDIA_CSS = """
<style>
.md-title{font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;color:#111;margin:0 0 4px;}
.md-lede{color:var(--color-text-muted);font-size:1rem;margin:0 0 14px;max-width:48rem;}
.md-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin-top:10px;}
.md-card{display:flex;flex-direction:column;gap:6px;background:#fff;border:1px solid var(--color-border);border-radius:10px;
  padding:14px 16px 12px;text-decoration:none!important;color:inherit!important;transition:border-color .15s,box-shadow .15s;}
.md-card:hover{border-color:#173f5f;box-shadow:0 6px 18px rgba(23,63,95,.08);}
.md-card-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;}
.md-name{font-weight:700;color:#111;font-size:1.02rem;line-height:1.25;}
.md-domain{font-size:.78rem;color:var(--color-text-muted);}
.md-code{font-size:.72rem;font-weight:700;color:#3d4b5a;background:#eef2f6;border-radius:4px;padding:2px 6px;white-space:nowrap;}
.md-chips{display:flex;flex-wrap:wrap;gap:6px;font-size:.76rem;color:#3d4b5a;}
.md-chip{display:inline-flex;align-items:center;gap:5px;background:#f6f8fa;border-radius:999px;padding:2px 9px;}
.md-dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.md-status{font-size:.8rem;color:#3d4b5a;display:flex;align-items:center;gap:6px;}
.md-num{font-family:'Manrope',sans-serif;font-size:1.35rem;font-weight:700;color:#111;line-height:1.1;}
.md-num span{font-size:.78rem;font-weight:500;color:var(--color-text-muted);margin-left:4px;}
.md-card .spark{display:block;width:100%;height:34px;}
.md-foot{display:flex;justify-content:space-between;font-size:.72rem;color:var(--color-text-muted);}
.md-warn{color:#7a4b00;}
.md-back{font-weight:700;color:#173f5f!important;text-decoration:none!important;font-size:.92rem;}
.md-quote{border-left:3px solid var(--color-logo);background:#fff;padding:10px 16px;margin:10px 0 12px;color:#1f2933;font-size:.95rem;line-height:1.55;border-radius:0 8px 8px 0;max-width:52rem;}
.md-quote small{display:block;color:var(--color-text-muted);font-size:.75rem;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em;font-weight:700;}
.md-links{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 10px;}
.md-links a{font-size:.82rem;font-weight:600;color:#173f5f!important;border:1px solid var(--color-border);border-radius:999px;padding:3px 11px;text-decoration:none!important;background:#fff;}
.md-links a:hover{border-color:#173f5f;}
.md-latest{list-style:none;padding:0;margin:0;border-top:1px solid var(--color-border);width:100%!important;max-width:none!important;}
.md-latest li{max-width:none!important;margin:0!important;}
.md-latest li{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;padding:9px 0;border-bottom:1px solid var(--color-border);}
.md-latest .d{font-size:.8rem;color:var(--color-text-muted);}
.md-latest a{color:#111!important;text-decoration:none!important;}
.md-latest a:hover{text-decoration:underline!important;}
.md-latest .t{font-size:.76rem;color:var(--color-text-muted);margin-top:2px;}
.md-badge{display:inline-block;font-size:.68rem;font-weight:700;color:#7a4b00;background:#fff4dc;border-radius:4px;padding:1px 6px;margin-left:6px;}
.md-sim{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;}
.md-bar{height:6px;background:#eef2f6;border-radius:3px;overflow:hidden;margin-top:4px;}
.md-bar i{display:block;height:100%;background:#2a78d6;}
@media (max-width:520px){.md-latest li{grid-template-columns:1fr;gap:2px;}}
</style>
"""


def _chip(label: str, color: str | None = None) -> str:
    dot = f"<span class='md-dot' style='background:{color}'></span>" if color else ""
    return f"<span class='md-chip'>{dot}{html.escape(label)}</span>"


def _card(outlet: dict, today) -> str:
    status, text = status_line(outlet, today)
    code = COUNTRY_CODES.get(str(outlet.get("country") or ""), "")
    orientation = outlet.get("partisan") or "Unclassified"
    chips = [_chip(orientation, ORIENTATION_COLORS.get(orientation, "#c5c9cf"))]
    if outlet.get("format") and outlet["format"] != "text":
        chips.append(_chip(str(outlet["format"]).capitalize()))
    share = teaser_share(outlet)
    teaser = f"<span class='md-warn'>{share:.0%} teasers</span>" if share >= 0.2 else "<span></span>"
    spark = sparkline_svg(outlet.get("monthly_12") or [], COUNTRY_COLORS.get(outlet.get("country"), "#8c342f"), height=34)
    return (
        f"<a class='md-card' href='{html.escape(profile_url(outlet['outlet']), quote=True)}' target='_self'>"
        f"<div class='md-card-head'><div><div class='md-name'>{html.escape(str(outlet.get('name') or outlet['outlet']))}</div>"
        f"<div class='md-domain'>{html.escape(outlet['outlet'])}</div></div><span class='md-code'>{code}</span></div>"
        f"<div class='md-chips'>{''.join(chips)}</div>"
        f"<div class='md-status'><span class='md-dot' style='background:{STATUS_COLORS[status]}'></span>{status} · {html.escape(text)}</div>"
        f"<div class='md-num'>{int(outlet.get('articles') or 0):,}<span>articles · {html.escape(coverage_years(outlet))}</span></div>"
        f"{spark}<div class='md-foot'><span>Last 12 months</span>{teaser}</div></a>"
    )


def _render_directory(data: dict) -> None:
    today = datetime.now().date()
    outlets = data.get("outlets", [])
    active = sum(1 for o in outlets if status_line(o, today)[0] == "Active")
    total_articles = sum(int(o.get("articles") or 0) for o in outlets)
    _html(
        "<div class='md-title'>Media Archive</div>"
        f"<p class='md-lede'>All {len(outlets)} outlets in the observatory: who they are, how active they are and what "
        "they write about. Open an outlet for its full profile.</p>"
        "<div class='ex-kpis'>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Outlets</div><div class='ex-kpi-value'>{len(outlets)}</div><div class='ex-kpi-sub'>in 4 countries</div></div>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'><span class='md-dot' style='background:{STATUS_COLORS['Active']}'></span>Active now</div>"
        f"<div class='ex-kpi-value'>{active}</div><div class='ex-kpi-sub'>articles collected in the last 14 days</div></div>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Articles</div><div class='ex-kpi-value'>{total_articles:,}</div><div class='ex-kpi-sub'>analysis-ready</div></div>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Coverage</div><div class='ex-kpi-value'>{min((o.get('first_date') or '9999')[:4] for o in outlets) if outlets else '—'}–{today.year}</div><div class='ex-kpi-sub'>first to latest article</div></div>"
        "</div>"
    )

    with st.container(key="md_controls"):
        c1, c2, c3 = st.columns([1.6, 1.6, 1.2])
        with c1:
            query = st.text_input("Search", placeholder="Name or domain, e.g. document", key="md_query")
        with c2:
            countries = st.pills("Countries", options=list(COUNTRY_CODES), format_func=str.capitalize,
                                 selection_mode="multi", key="md_countries")
        with c3:
            sort = st.selectbox("Sort by", options=list(SORTS), key="md_sort")
        c4, c5, c6 = st.columns([1.6, 1.6, 1.2])
        with c4:
            orientation = st.segmented_control("Orientation", options=["All", "Right", "Left", "Other"], default="All", key="md_orientation")
        with c5:
            status = st.segmented_control(
                "Status", options=["All", *STATUSES], default="All", key="md_status",
                help="Based on the newest collected article: Active = within 14 days, Quiet = within 4 months, "
                     "Historical = older (the outlet may have stopped, or is no longer collected).",
            )
        with c6:
            view = st.segmented_control("View", options=["Cards", "Table"], default="Cards", key="md_view")

    shown = sort_directory(filter_directory(outlets, today, query, countries or (), orientation, status), sort or SORTS[0])
    _html(f"<p class='ex-note'>{len(shown)} of {len(outlets)} outlets</p>")
    if not shown:
        st.info("No outlets match. Clear the search or choose fewer filters.")
        return
    if view == "Table":
        frame = pd.DataFrame([{
            "Outlet": o.get("name") or o["outlet"],
            "Profile": profile_url(o["outlet"]),
            "Country": str(o.get("country") or "").capitalize(),
            "Orientation": o.get("partisan") or "",
            "Articles": int(o.get("articles") or 0),
            "Last 12 months": o.get("monthly_12") or [],
            "Last 30 days": int(o.get("last_30_days") or 0),
            "First article": o.get("first_date"),
            "Latest article": o.get("last_date"),
            "Teasers": round(teaser_share(o) * 100),
        } for o in shown])
        st.dataframe(
            frame, hide_index=True, use_container_width=True, height=min(40 + 35 * len(frame), 720),
            column_config={
                "Profile": st.column_config.LinkColumn("Profile", display_text="Open"),
                "Articles": st.column_config.NumberColumn(format="%d"),
                "Last 12 months": st.column_config.LineChartColumn("Last 12 months"),
                "Teasers": st.column_config.NumberColumn("Teasers", format="%d%%"),
            },
        )
    else:
        _html("<div class='md-grid'>" + "".join(_card(o, today) for o in shown) + "</div>")


def _activity_figure(monthly: list[dict], country: str | None) -> go.Figure | None:
    frame = pd.DataFrame(monthly)
    if frame.empty:
        return None
    frame["date"] = pd.to_datetime(frame["month"] + "-01", errors="coerce")
    frame = frame[frame["date"].dt.to_period("M") != pd.Timestamp.today().to_period("M")]
    full = pd.DataFrame({"date": pd.date_range(frame["date"].min(), frame["date"].max(), freq="MS")})
    frame = full.merge(frame[["date", "count"]], on="date", how="left").fillna({"count": 0})
    fig = go.Figure(go.Bar(
        x=frame["date"], y=frame["count"], marker_color=COUNTRY_COLORS.get(country or "", "#8c342f"),
        hovertemplate="%{x|%b %Y}: %{y:,} articles<extra></extra>",
    ))
    _style(fig, 280, legend=False)
    fig.update_layout(bargap=0.1)
    fig.update_yaxes(title_text="Articles per month")
    _year_axis(fig, [frame])
    return fig


def _topics_figure(topics: list[dict], country_topics: dict, country: str | None, narrow: bool = False) -> go.Figure | None:
    if not topics:
        return None
    frame = pd.DataFrame(topics).sort_values("share", ascending=True)
    label = f"All {str(country or '').capitalize()} outlets"
    fig = go.Figure()
    labels = [short_topic(t) for t in frame["topic"]] if narrow else list(frame["topic"])
    fig.add_trace(go.Bar(
        y=labels, x=frame["share"] * 100, orientation="h", name="This outlet", marker_color="#2a78d6",
        text=[f"{s * 100:.0f}%" for s in frame["share"]], textposition="outside", cliponaxis=False,
        textfont=dict(color="#5a6a7a", size=11),
        hovertemplate="<b>%{y}</b><br>This outlet: %{x:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        y=labels, x=[country_topics.get(t, 0) * 100 for t in frame["topic"]], mode="markers", name=label,
        marker=dict(symbol="line-ns", size=18, line=dict(width=3, color="#1f2933")),
        hovertemplate="<b>%{y}</b><br>" + html.escape(label) + ": %{x:.1f}%<extra></extra>",
    ))
    _style(fig, 90 + 30 * len(frame))
    fig.update_xaxes(ticksuffix="%", range=[0, 100], dtick=25 if narrow else 20, showgrid=True)
    fig.update_yaxes(showgrid=False)
    return fig


def _render_profile(profile: dict) -> None:
    today = datetime.now().date()
    country = profile.get("country")
    status, text = status_line(profile, today)
    orientation = profile.get("partisan") or "Unclassified"
    _html("<a class='md-back' href='?page=Media' target='_self'>← All outlets</a>")
    chips = [
        _chip(f"{str(country or '').capitalize()} ({COUNTRY_CODES.get(country or '', '')})"),
        _chip(orientation, ORIENTATION_COLORS.get(orientation, "#c5c9cf")),
    ]
    if profile.get("partisan_detail"):
        chips.append(_chip(profile["partisan_detail"]))
    if profile.get("format"):
        chips.append(_chip(str(profile["format"]).capitalize()))
    chips.append(_chip(f"{status} · {text}", STATUS_COLORS[status]))
    _html(
        f"<div class='md-title' style='margin-top:10px;'>{html.escape(profile.get('name') or profile['outlet'])}</div>"
        f"<p class='md-domain' style='font-size:.95rem;margin:0 0 8px;'>{html.escape(profile['outlet'])}</p>"
        f"<div class='md-chips' style='font-size:.82rem;'>{''.join(chips)}</div>"
    )
    own_words = profile.get("self_description") or profile.get("about")
    if own_words:
        _html(f"<div class='md-quote'><small>In their own words</small>{html.escape(own_words)}</div>")
    links = profile.get("links") or {}
    if links:
        _html("<div class='md-links'>" + "".join(
            f"<a href='{html.escape(url, quote=True)}' target='_blank' rel='noopener noreferrer'>{html.escape(LINK_LABELS.get(k, k))} ↗</a>"
            for k, url in links.items()
        ) + "</div>")

    monthly_values = [int(m["count"]) for m in profile.get("monthly", [])][-13:-1]
    share = teaser_share(profile)
    _html(
        "<div class='ex-kpis'>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Articles collected</div><div class='ex-kpi-value'>{int(profile.get('articles') or 0):,}</div><div class='ex-kpi-sub'>analysis-ready</div></div>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Coverage</div><div class='ex-kpi-value'>{html.escape(coverage_years(profile))}</div><div class='ex-kpi-sub'>{html.escape(str(profile.get('first_date')))} to {html.escape(str(profile.get('last_date')))}</div></div>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Per month</div><div class='ex-kpi-value'>{average_per_month(monthly_values):,.0f}</div><div class='ex-kpi-sub'>average, last 12 months</div></div>"
        f"<div class='ex-kpi'><div class='ex-kpi-label'>Full text</div><div class='ex-kpi-value'>{1 - share:.0%}</div><div class='ex-kpi-sub'>{'of articles; the rest are teasers' if share else 'of articles'}</div></div>"
        "</div>"
    )
    if share >= 0.2:
        _html(insight_html(f"{share:.0%} of this outlet's articles are teasers: only the lead paragraph is public, "
                           "so full text is not available for them."))

    _html(section_header("Publishing activity", "Collected articles per month. Gaps can mean the outlet paused, or that it was not collected in that period."))
    fig = _activity_figure(profile.get("monthly", []), country)
    if fig:
        _plot(fig)

    _html(section_header("What it writes about",
                         f"Percent of its articles tagged with each topic (bars), against all {str(country or '').capitalize()} "
                         "outlets (black line). Articles can have several topics."))
    args = (profile.get("topics", []), profile.get("country_topics") or {}, country)
    fig = _topics_figure(*args)
    if fig:
        _plot_responsive(fig, _topics_figure(*args, narrow=True), "outlet_topic_bars")

    _html(section_header("Latest articles", "The ten newest collected articles. Titles link to the original."))
    items = []
    for article in profile.get("latest", []):
        title = html.escape(repair_mojibake(article.get("title")) or "Untitled")
        url = str(article.get("url") or "")
        link = f"<a href='{html.escape(url, quote=True)}' target='_blank' rel='noopener noreferrer'>{title}</a>" if url.startswith(("http://", "https://")) else title
        badge = "<span class='md-badge'>teaser</span>" if article.get("teaser") else ""
        items.append(
            f"<li><div class='d'>{html.escape(time_ago(article.get('date'), today).capitalize())}<br>{html.escape(str(article.get('date') or ''))}</div>"
            f"<div>{link}{badge}<div class='t'>{html.escape(format_category_labels(article.get('categories')))}</div></div></li>"
        )
    _html(f"<ul class='md-latest'>{''.join(items)}</ul>")

    similar = profile.get("similar") or []
    if similar:
        _html(section_header("Outlets with a similar agenda",
                             "Outlets that emphasise the same topics more or less than the Nordic average, in any country. "
                             "Similar topics, not necessarily similar positions."))
        cards = []
        for other in similar:
            score = max(0.0, float(other.get("similarity") or 0))
            shared = ", ".join(other.get("shared") or []) or "overall topic mix"
            orientation = other.get("partisan") or "Unclassified"
            cards.append(
                f"<a class='md-card' href='{html.escape(profile_url(other['outlet']), quote=True)}' target='_self'>"
                f"<div class='md-card-head'><div><div class='md-name'>{html.escape(str(other.get('name') or other['outlet']))}</div>"
                f"<div class='md-domain'>{html.escape(other['outlet'])}</div></div>"
                f"<span class='md-code'>{COUNTRY_CODES.get(other.get('country') or '', '')}</span></div>"
                f"<div class='md-chips'>{_chip(orientation, ORIENTATION_COLORS.get(orientation, '#c5c9cf'))}</div>"
                f"<div class='md-status'>Both emphasise: {html.escape(shared)}</div>"
                f"<div class='md-bar' title='Agenda match {score:.0%}'><i style='width:{score * 100:.0f}%'></i></div></a>"
            )
        _html(f"<div class='md-sim'>{''.join(cards)}</div>")

    _html(
        f"<p style='margin-top:22px;'><a class='md-back' href='{html.escape(workshop_url(profile, today), quote=True)}' "
        "target='_self'>Build a dataset from this outlet in the Research Workshop →</a></p>"
    )


def show_media_page() -> None:
    """Show the outlet directory, or one outlet's profile when ?media= is set."""
    _html(EXPLORER_CSS)
    _html(MEDIA_CSS)
    selected = normalize_outlet(st.query_params.get("media"))
    if selected:
        with st.spinner("Loading outlet profile…"):
            profile = fetch_outlet(selected)
        if profile:
            _render_profile(profile)
            render_footer_bar()
            return
        st.warning(f"No outlet called “{selected}” was found. Showing all outlets instead.")

    with st.spinner("Loading outlets…"):
        data = fetch_outlets()
    if not data:
        st.error("The outlet directory could not be loaded right now. Please try again in a moment.")
    else:
        _render_directory(data)
    render_footer_bar()
