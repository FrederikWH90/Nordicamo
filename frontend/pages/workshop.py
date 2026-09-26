"""Research Workshop: build an article selection, see what is in it, request it.

One flow instead of separate mini-tools:
  1. Start from a question (presets fill the filters) or set filters directly.
  2. See what the selection contains: size, time, outlets, topics, teaser share.
  3. Read a random (reproducible) sample of articles, metadata only.
  4. Share the selection as a link or send it as a dataset request.

The selection lives in the URL, so every state of the page is a shareable,
reproducible link.
"""

from __future__ import annotations

import html
import uuid

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from explorer_data import COUNTRY_COLORS, ORIENTATION_COLORS, pct
from pages.explorer import EXPLORER_CSS, _html, _plot, _style, _year_axis, insight_html, section_header
from pages.footer import render_footer_bar
from services.api import fetch_outlet_directory, fetch_overview, fetch_selection
from workshop_helpers import (
    COUNTRIES,
    COUNTRY_CODES,
    ORIENTATIONS,
    TOPIC_OPTIONS,
    Selection,
    build_access_request_context,
    presets,
    preview_records,
    safe_article_url,
    selection_from_query_params,
    selection_summary_lines,
    teaser_note,
)

KEYWORD_HELP = (
    "Searches titles and article text.\n\n"
    "- `klimat` the word\n"
    "- `klimat*` words starting with klimat (klimatet, klimatkris…)\n"
    '- `"grøn omstilling"` the exact phrase\n'
    "- `covid OR corona` either word\n"
    "- `-vaccine` exclude a word\n\n"
    "Several words means all of them."
)

WORKSHOP_CSS = """
<style>
.ws-title{font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;color:#111;margin:0 0 4px;}
.ws-lede{color:var(--color-text-muted);font-size:1rem;margin:0 0 16px;max-width:48rem;}
.ws-label{font-size:.78rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--color-text-muted);margin:4px 0 6px;}
.st-key-ws_filters{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:14px 16px 6px;}
.st-key-ws_presets button{min-height:0!important;padding:6px 12px!important;font-size:.88rem!important;}
.ws-result{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:18px 0 4px;}
.ws-n{font-family:'Manrope',sans-serif;font-size:2.6rem;font-weight:700;color:var(--color-logo);line-height:1;}
.ws-n-label{font-size:1.05rem;color:#111;}
.ws-sub{font-size:.92rem;color:var(--color-text-muted);margin:2px 0 6px;}
.ws-table-wrap{max-width:100%;overflow-x:auto;border:1px solid var(--color-border);border-radius:10px;background:#fff;}
.ws-table{width:100%;border-collapse:collapse;font-size:.88rem;}
.ws-table th{position:sticky;top:0;background:#f6f8fa;text-align:left;font-weight:700;color:#3d4b5a;padding:8px 10px;border-bottom:1px solid var(--color-border);white-space:nowrap;}
.ws-table td{padding:8px 10px;border-bottom:1px solid #eef1f4;vertical-align:top;color:#1f2933;}
.ws-table td.ws-muted{color:var(--color-text-muted);white-space:nowrap;}
.ws-table td.ws-col-title{min-width:260px;width:48%;}
.ws-table td.ws-topics{color:var(--color-text-muted);font-size:.8rem;min-width:160px;}
.ws-table a{color:#173f5f;text-decoration:none;}
.ws-table a:hover{text-decoration:underline;}
.ws-badge{display:inline-block;font-size:.7rem;font-weight:700;color:#7a4b00;background:#fff4dc;border-radius:4px;padding:1px 6px;margin-left:6px;}
.ws-spec{display:grid;grid-template-columns:auto 1fr;gap:4px 18px;font-size:.92rem;margin:4px 0 12px;}
.ws-spec dt{color:var(--color-text-muted);}
.ws-spec dd{margin:0;color:#111;}
@media (max-width:640px){.ws-n{font-size:2rem;}}
</style>
"""

STATE_KEYS = ("ws_countries", "ws_years", "ws_orientation", "ws_topics", "ws_outlets", "ws_q")


def _year_bounds() -> tuple[int, int]:
    dates = (fetch_overview() or {}).get("date_range") or {}
    try:
        return int(str(dates.get("earliest"))[:4]), int(str(dates.get("latest"))[:4])
    except (TypeError, ValueError):
        return 2008, pd.Timestamp.today().year


def _apply_selection_to_state(selection: Selection, year_min: int, year_max: int) -> None:
    st.session_state["ws_countries"] = list(selection.countries)
    st.session_state["ws_years"] = (selection.year_from or max(year_min, year_max - 4), selection.year_to or year_max)
    st.session_state["ws_orientation"] = selection.orientation or "All"
    st.session_state["ws_topics"] = list(selection.topics)
    st.session_state["ws_outlets"] = list(selection.outlets)
    st.session_state["ws_q"] = selection.keywords


def _selection_from_state() -> Selection:
    year_from, year_to = st.session_state.get("ws_years") or (None, None)
    orientation = st.session_state.get("ws_orientation")
    return Selection(
        countries=tuple(st.session_state.get("ws_countries") or ()),
        year_from=year_from,
        year_to=year_to,
        orientation=orientation if orientation in ORIENTATIONS else None,
        topics=tuple(st.session_state.get("ws_topics") or ()),
        outlets=tuple(st.session_state.get("ws_outlets") or ()),
        keywords=str(st.session_state.get("ws_q") or ""),
    )


def _sync_from_url(year_min: int, year_max: int) -> None:
    """Load filters from the URL when it changed from outside (shared link, first visit)."""
    params = {k: st.query_params.get(k) for k in ("c", "y", "o", "t", "out", "q")}
    signature = repr(sorted((k, v) for k, v in params.items() if v))
    if st.session_state.get("ws_url_sig") == signature and all(k in st.session_state for k in STATE_KEYS):
        return
    _apply_selection_to_state(selection_from_query_params(params, year_min, year_max), year_min, year_max)
    st.session_state["ws_url_sig"] = signature


def _sync_to_url(selection: Selection) -> None:
    wanted = selection.to_query_params()
    for key in ("c", "y", "o", "t", "out", "q"):
        if key in wanted:
            if st.query_params.get(key) != wanted[key]:
                st.query_params[key] = wanted[key]
        elif key in st.query_params:
            del st.query_params[key]
    params = {k: wanted.get(k) for k in ("c", "y", "o", "t", "out", "q")}
    st.session_state["ws_url_sig"] = repr(sorted((k, v) for k, v in params.items() if v))


def _use_preset(selection: Selection, year_min: int, year_max: int) -> None:
    _apply_selection_to_state(selection, year_min, year_max)
    st.session_state["ws_seed"] = "nordicamo"


def _reset(year_min: int, year_max: int) -> None:
    _apply_selection_to_state(Selection(), year_min, year_max)


def _render_presets(year_min: int, year_max: int) -> None:
    _html("<div class='ws-label'>Start from a question</div>")
    items = presets(year_max)
    with st.container(key="ws_presets"):
        cols = st.columns(len(items))
        for col, preset in zip(cols, items):
            with col:
                st.button(
                    preset.label, key=f"ws_preset_{preset.key}", help=preset.question, use_container_width=True,
                    on_click=_use_preset, args=(preset.selection, year_min, year_max),
                )


def _outlet_label(directory: dict[str, dict]) -> callable:
    def label(outlet: str) -> str:
        entry = directory.get(outlet)
        return f"{outlet} ({COUNTRY_CODES.get(entry['country'], '')})" if entry else outlet
    return label


def _render_filters(year_min: int, year_max: int) -> None:
    directory_rows = fetch_outlet_directory()
    directory = {row["outlet"]: row for row in directory_rows}
    with st.container(key="ws_filters"):
        c1, c2 = st.columns([1.4, 1])
        with c1:
            st.pills(
                "Countries", options=list(COUNTRIES), format_func=str.capitalize, selection_mode="multi",
                key="ws_countries", help="None selected means all four countries.",
            )
        with c2:
            st.slider("Period", min_value=year_min, max_value=year_max, step=1, key="ws_years")
        c3, c4 = st.columns([1, 1.4])
        with c3:
            st.segmented_control("Outlet orientation", options=["All", *ORIENTATIONS], key="ws_orientation")
        with c4:
            st.multiselect("Topics", options=list(TOPIC_OPTIONS), key="ws_topics",
                           placeholder="All topics", help="Articles tagged with any of the selected topics.")
        c5, c6 = st.columns([1, 1.4])
        chosen = set(st.session_state.get("ws_countries") or COUNTRIES)
        options = [row["outlet"] for row in directory_rows if row["country"] in chosen]
        options += [o for o in st.session_state.get("ws_outlets") or [] if o not in options]
        with c5:
            st.multiselect("Outlets", options=options, key="ws_outlets", format_func=_outlet_label(directory),
                           placeholder="All outlets")
        with c6:
            st.text_input("Keywords", key="ws_q", help=KEYWORD_HELP,
                          placeholder='e.g. klimat* OR "grøn omstilling" -EU')
        st.button("Clear all filters", key="ws_reset", on_click=_reset, args=(year_min, year_max), type="tertiary")


def _time_figure(by_month: list[dict]) -> go.Figure | None:
    frame = pd.DataFrame(by_month)
    if frame.empty:
        return None
    frame["date"] = pd.to_datetime(frame["month"] + "-01", errors="coerce")
    current = pd.Timestamp.today().to_period("M")
    frame = frame[frame["date"].dt.to_period("M") != current]
    fig = go.Figure()
    for country in COUNTRIES:
        rows = frame[frame["country"] == country]
        if rows.empty:
            continue
        fig.add_trace(go.Bar(
            x=rows["date"], y=rows["count"], name=country.capitalize(), marker_color=COUNTRY_COLORS[country],
            hovertemplate="%{x|%b %Y}: %{y:,}<extra>" + country.capitalize() + "</extra>",
        ))
    _style(fig, 300)
    fig.update_layout(barmode="stack", bargap=0.15, hovermode="x unified", legend=dict(traceorder="normal"))
    fig.update_yaxes(title_text="Articles per month")
    _year_axis(fig, [frame.rename(columns={"count": "count"})])
    return fig


def _outlets_figure(by_outlet: list[dict], total: int) -> go.Figure | None:
    frame = pd.DataFrame(by_outlet).head(15)
    if frame.empty or not total:
        return None
    frame["share"] = frame["count"] / total
    frame["label"] = frame.apply(lambda r: f"{r['outlet']} ({COUNTRY_CODES.get(r['country'], '')})", axis=1)
    fig = go.Figure()
    for orientation in [*ORIENTATIONS, None]:
        rows = frame[frame["partisan"] == orientation] if orientation else frame[~frame["partisan"].isin(ORIENTATIONS)]
        if rows.empty:
            continue
        fig.add_trace(go.Bar(
            y=rows["label"], x=rows["count"], orientation="h", name=orientation or "Unclassified",
            marker_color=ORIENTATION_COLORS.get(orientation or "Unclassified"),
            text=[f"{s:.0%}" for s in rows["share"]], textposition="outside", cliponaxis=False,
            textfont=dict(color="#5a6a7a", size=11),
            customdata=rows[["teasers"]].values,
            hovertemplate="<b>%{y}</b><br>%{x:,} articles<br>%{customdata[0]:,} teasers<extra></extra>",
        ))
    _style(fig, 70 + 24 * len(frame))
    fig.update_layout(bargap=0.25, legend=dict(traceorder="normal"))
    fig.update_yaxes(categoryorder="array", categoryarray=list(frame["label"]), autorange="reversed", showgrid=False)
    fig.update_xaxes(range=[0, float(frame["count"].max()) * 1.15], showgrid=True)
    return fig


def _topics_figure(by_topic: list[dict], total: int) -> go.Figure | None:
    frame = pd.DataFrame(by_topic)
    if frame.empty or not total:
        return None
    frame = frame[frame["topic"].isin(TOPIC_OPTIONS)].sort_values("count", ascending=False)
    frame["share"] = frame["count"] / total * 100
    fig = go.Figure(go.Bar(
        y=frame["topic"], x=frame["share"], orientation="h", marker_color="#2a78d6",
        text=[f"{s:.0f}%" for s in frame["share"]], textposition="outside", cliponaxis=False,
        textfont=dict(color="#5a6a7a", size=11),
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% of the selection<extra></extra>",
    ))
    _style(fig, 70 + 24 * len(frame), legend=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(ticksuffix="%", range=[0, max(100.0, float(frame["share"].max()) * 1.1)], showgrid=True)
    return fig


def _render_contents(selection: Selection, result: dict) -> None:
    total = int(result.get("total") or 0)
    countries = [row["country"] for row in result.get("by_country", [])]
    span = ""
    if result.get("first_date") and result.get("last_date"):
        span = f", published {pd.Timestamp(result['first_date']):%-d %b %Y} – {pd.Timestamp(result['last_date']):%-d %b %Y}"
    _html(
        f"<div class='ws-result'><span class='ws-n'>{total:,}</span><span class='ws-n-label'>articles match</span></div>"
        f"<p class='ws-sub'>from {int(result.get('outlets') or 0)} outlets in {len(countries)} "
        f"{'country' if len(countries) == 1 else 'countries'}{html.escape(span)}</p>"
    )
    note = teaser_note(total, int(result.get("teasers") or 0))
    if note:
        _html(insight_html(note))
    if not total:
        st.info("Nothing matches. Try a wider period, fewer topics or outlets, or a keyword with * (e.g. klimat*).")
        return

    _html(section_header("When were they published?",
                         "Articles per month in this selection, by country. The current month is left out until it is complete."))
    fig = _time_figure(result.get("by_month", []))
    if fig:
        _plot(fig)
    left, right = st.columns(2)
    with left:
        _html(section_header("Which outlets?", "The 15 largest outlets in the selection; labels show their share of it."))
        fig = _outlets_figure(result.get("by_outlet", []), total)
        if fig:
            _plot(fig)
    with right:
        _html(section_header("Which topics?", "Percent of the selection tagged with each topic (articles can have several)."))
        fig = _topics_figure(result.get("by_topic", []), total)
        if fig:
            _plot(fig)


def _render_sample(result: dict) -> None:
    _html(section_header("Read a sample",
                         "A random sample of the selection (the same sample every time, until you draw a new one), "
                         "or the newest articles. Metadata only: titles link to the original article."))
    c1, c2, c3 = st.columns([1.4, 1, 1])
    with c1:
        st.segmented_control("Order", options=["Random sample", "Newest first"], key="ws_order",
                             default="Random sample", label_visibility="collapsed")
    with c2:
        st.selectbox("Rows", options=[25, 50, 100], key="ws_size", label_visibility="collapsed",
                     format_func=lambda n: f"{n} articles")
    with c3:
        if st.button("Draw a new sample", key="ws_new_sample", use_container_width=True):
            st.session_state["ws_seed"] = uuid.uuid4().hex[:8]
    rows = preview_records(result.get("sample", []))
    if not rows:
        return
    body = []
    for row in rows:
        url = safe_article_url(row["Article URL"])
        title = html.escape(row["Title"] or "Untitled")
        title_html = f"<a href='{html.escape(url, quote=True)}' target='_blank' rel='noopener noreferrer'>{title}</a>" if url else title
        badge = "<span class='ws-badge'>teaser</span>" if row["Teaser"] else ""
        body.append(
            f"<tr><td class='ws-muted'>{html.escape(row['Date'])}</td><td class='ws-muted'>{html.escape(row['Country'])}</td>"
            f"<td class='ws-muted'>{html.escape(row['Outlet'])}</td><td class='ws-col-title'>{title_html}{badge}</td>"
            f"<td class='ws-topics'>{html.escape(row['Topics'])}</td></tr>"
        )
    _html(
        "<div class='ws-table-wrap'><table class='ws-table'><thead><tr><th>Date</th><th></th><th>Outlet</th>"
        "<th>Title</th><th>Topics</th></tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def _render_use(selection: Selection, result: dict) -> None:
    _html(section_header("Use this selection",
                         "Share the link to reopen exactly this selection, or request it as a dataset. "
                         "Requests are reviewed by the Nordicamo team."))
    spec = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in selection_summary_lines(selection))
    _html(f"<dl class='ws-spec'>{spec}</dl>")
    st.code(selection.share_url(), language=None)
    if st.button("Request this dataset", type="primary", key="ws_request"):
        context = build_access_request_context(selection, result)
        st.session_state["access_request_context"] = context
        st.session_state["access_request_draft"] = context
        st.query_params.clear()
        st.query_params["page"] = "GetAccess"
        st.rerun()


def show_workshop_page() -> None:
    """Build an article selection, inspect it, and request it."""
    _html(EXPLORER_CSS)  # shared section headers, insight boxes, chart spacing
    _html(WORKSHOP_CSS)
    _html(
        "<div class='ws-title'>Research Workshop</div>"
        "<p class='ws-lede'>Build an article selection, see what is in it, read a sample, and request it as a dataset. "
        "Start from one of the questions below or set the filters yourself.</p>"
    )
    year_min, year_max = _year_bounds()
    _sync_from_url(year_min, year_max)
    _render_presets(year_min, year_max)
    _render_filters(year_min, year_max)

    selection = _selection_from_state()
    _sync_to_url(selection)
    order = "newest" if st.session_state.get("ws_order") == "Newest first" else "random"
    with st.spinner("Counting matching articles…"):
        result = fetch_selection(
            tuple(selection.api_params()),
            sample_size=int(st.session_state.get("ws_size") or 25),
            order=order,
            seed=st.session_state.get("ws_seed", "nordicamo"),
        )
    if result is None:
        st.error("The selection could not be loaded right now. Please try again in a moment.")
        render_footer_bar()
        return

    _render_contents(selection, result)
    if int(result.get("total") or 0):
        _render_sample(result)
        _render_use(selection, result)
    render_footer_bar()
