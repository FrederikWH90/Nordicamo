"""Explorer: every analysis on one page, driven by three filters.

Two views share the same filters (scope, period, orientation):
- All countries: how the four countries differ.
- Country view: what drives one country's output.

Each section answers one question, shows one chart, and states in one line how
to read it. Nothing is hidden behind toggles or expanders.
"""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from explorer_data import (
    COUNTRIES,
    COUNTRY_COLORS,
    NEUTRAL,
    ORIENTATION_COLORS,
    ORIENTATIONS,
    SEQUENTIAL_BLUE,
    concentration_segments,
    concentration_sentence,
    load_comparison,
    load_country,
    monthly_frame,
    orientation_mix,
    outlet_activity_matrix,
    outlet_shares,
    pct,
    profile_matrix,
    top_n_share,
    topic_gap_sentence,
    topic_profile,
    topic_share_by_year,
)
from pages.footer import render_footer_bar
from services.api import fetch_overview

MODE_COMPARE = "Country Comparison"
MODE_DEEP_DIVE = "Country Deep Dive"
COUNTRY_VIEW_COMPARE = "All countries"
COUNTRY_VIEW_OPTIONS = [COUNTRY_VIEW_COMPARE, "Denmark", "Finland", "Norway", "Sweden"]
ORIENTATION_OPTIONS = ["All", "Right", "Left", "Other"]

COUNTRY_LANDSCAPE_LABELS = {
    "denmark": "Danish Alternative Media Landscape",
    "sweden": "Swedish Alternative Media Landscape",
    "norway": "Norwegian Alternative Media Landscape",
    "finland": "Finnish Alternative Media Landscape",
}
COUNTRY_ADJECTIVES = {"denmark": "Danish", "finland": "Finnish", "norway": "Norwegian", "sweden": "Swedish"}

FONT = "Inter, Helvetica, Arial, sans-serif"
INK = "#1f2933"
MUTED = "#5a6a7a"
GRID = "#eceff3"
AXIS = "#c9d1da"
TICK = "#3d4b5a"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def normalize_explorer_mode(mode: str | None) -> str:
    if mode in {MODE_COMPARE, MODE_DEEP_DIVE}:
        return mode
    return MODE_COMPARE


def normalize_country(country: str | None) -> str:
    if country in COUNTRIES:
        return country
    return "denmark"


def country_landscape_label(country: str | None) -> str:
    return COUNTRY_LANDSCAPE_LABELS[normalize_country(country)]


def normalize_country_view(view: str | None) -> str:
    if view in COUNTRY_VIEW_OPTIONS:
        return view
    return COUNTRY_VIEW_COMPARE


def country_view_to_state(view: str | None) -> tuple[str, str | None]:
    normalized = normalize_country_view(view)
    if normalized == COUNTRY_VIEW_COMPARE:
        return MODE_COMPARE, None
    return MODE_DEEP_DIVE, normalized.lower()


def country_view_summary(view: str | None) -> str:
    """Describe the active scope in one concise sentence."""
    normalized = normalize_country_view(view)
    if normalized == COUNTRY_VIEW_COMPARE:
        return "Compare publication patterns, outlet structure, orientations, and topics across the Nordic region."
    return (
        "Examine publication patterns, outlet structure, and topics within the "
        f"{country_landscape_label(normalized.lower()).lower()}."
    )


def orientation_to_filter(label: str | None) -> str | None:
    return label if label in ORIENTATIONS else None


def _year_bounds(overview: dict | None) -> tuple[int, int]:
    dr = (overview or {}).get("date_range", {}) or {}
    try:
        year_min = int(str(dr.get("earliest"))[:4])
    except (TypeError, ValueError):
        year_min = 2008
    try:
        year_max = int(str(dr.get("latest"))[:4])
    except (TypeError, ValueError):
        year_max = pd.Timestamp.today().year
    if year_min > year_max:
        year_min, year_max = 2008, pd.Timestamp.today().year
    return year_min, year_max


def _default_year_range(year_min: int, year_max: int) -> tuple[int, int]:
    """Prefer 2016-2026 defaults while respecting available bounds."""
    default_start = max(year_min, 2016)
    default_end = min(year_max, 2026)
    if default_end < default_start:
        return year_min, year_max
    return default_start, default_end


def _period_label(year_from: int, year_to: int) -> str:
    return f"{year_from}-{year_to}"


def _partisan_label(partisan: str | None) -> str:
    return "All orientations" if partisan is None else partisan


def _default_country_view() -> str:
    mode = normalize_explorer_mode(st.session_state.get("explorer_mode"))
    if mode == MODE_DEEP_DIVE:
        country = normalize_country(st.session_state.get("quick_country") or st.session_state.get("deep_country"))
        return country.capitalize()
    return COUNTRY_VIEW_COMPARE


# ---------------------------------------------------------------------------
# Figures (pure: data in, go.Figure out)
# ---------------------------------------------------------------------------

def _style(fig: go.Figure, height: int, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=40, t=36 if legend else 12, b=44),
        font=dict(family=FONT, size=12, color=INK),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="", font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, size=12, color=INK), bordercolor=GRID),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS, ticklen=4, automargin=True,
                     tickfont=dict(color=TICK, size=12), title_font=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True, tickfont=dict(color=TICK, size=12), title_font=dict(color=MUTED))
    return fig


def _year_axis(fig: go.Figure, frames) -> None:
    """One labelled tick per year (every other year for long periods) on monthly charts."""
    dates = pd.concat([f["date"] for f in frames if not f.empty]) if frames else pd.Series(dtype="datetime64[ns]")
    span = (dates.max().year - dates.min().year) if not dates.empty else 0
    fig.update_xaxes(dtick="M12" if span <= 12 else "M24", tickformat="%Y", showgrid=True, gridcolor=GRID)


def volume_lines_figure(frames: dict[str, pd.DataFrame], colors: dict[str, str], label=str.capitalize) -> go.Figure:
    fig = go.Figure()
    for key, frame in frames.items():
        if frame.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame["date"], y=frame["count"], mode="lines", name=label(key),
                line=dict(color=colors.get(key, NEUTRAL), width=2),
                hovertemplate="%{y:,} articles<extra>" + html.escape(label(key)) + "</extra>",
            )
        )
    _style(fig, 380)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title_text="Articles per month", rangemode="tozero")
    _year_axis(fig, list(frames.values()))
    return fig


def orientation_area_figure(frames: dict[str, pd.DataFrame]) -> go.Figure:
    fig = go.Figure()
    for orientation in ORIENTATIONS:
        frame = frames.get(orientation)
        if frame is None or frame.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame["date"], y=frame["count"], mode="lines", name=orientation, stackgroup="one",
                line=dict(color=ORIENTATION_COLORS[orientation], width=1),
                hovertemplate="%{y:,} articles<extra>" + orientation + "</extra>",
            )
        )
    _style(fig, 360)
    fig.update_layout(hovermode="x unified", legend=dict(traceorder="normal"))
    fig.update_yaxes(title_text="Articles per month", rangemode="tozero")
    _year_axis(fig, [f for f in frames.values() if f is not None])
    return fig


def concentration_figure(segments: pd.DataFrame) -> go.Figure:
    """One horizontal bar per country: top outlets' shares, then everything else."""
    shades = ["#0d366b", "#1c5cab", "#3987e5", "#6da7ec", "#9ec5f4"]
    fig = go.Figure()
    countries = [c for c in COUNTRIES if c in set(segments["country"])]
    for rank in sorted(segments["rank"].unique()):
        rows = segments[segments["rank"] == rank].set_index("country").reindex(countries)
        is_rest = rank > len(shades)
        labels = [
            "" if pd.isna(seg) else (seg if share >= 0.08 else "")
            for seg, share in zip(rows["segment"], rows["share"].fillna(0))
        ]
        fig.add_trace(
            go.Bar(
                y=[c.capitalize() for c in countries], x=rows["share"].fillna(0) * 100, orientation="h",
                marker=dict(color=NEUTRAL if is_rest else shades[rank - 1], line=dict(color="white", width=2)),
                text=labels, textposition="inside", insidetextanchor="middle",
                textfont=dict(color=INK if is_rest or rank >= 4 else "white", size=11),
                customdata=rows["segment"].fillna(""),
                hovertemplate="<b>%{customdata}</b><br>%{x:.1f}% of articles<extra>%{y}</extra>",
                name="All other outlets" if is_rest else f"#{rank} outlet",
            )
        )
    _style(fig, 90 + 56 * len(countries), legend=False)
    fig.update_layout(barmode="stack", bargap=0.3)
    fig.update_xaxes(range=[0, 100], dtick=20, ticksuffix="%", showgrid=True, gridcolor=GRID, title_text="Share of the country's articles")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def orientation_bars_figure(mixes: dict[str, dict[str, float]]) -> go.Figure:
    countries = [c for c in COUNTRIES if mixes.get(c)]
    fig = go.Figure()
    for orientation in ORIENTATIONS + ["Unclassified"]:
        values = [mixes[c].get(orientation, 0.0) * 100 for c in countries]
        if not any(values):
            continue
        fig.add_trace(
            go.Bar(
                y=[c.capitalize() for c in countries], x=values, orientation="h", name=orientation,
                marker=dict(color=ORIENTATION_COLORS[orientation], line=dict(color="white", width=2)),
                text=[f"{v:.0f}%" if v >= 6 else "" for v in values], textposition="inside",
                textfont=dict(color="white" if orientation in ("Right", "Left") else INK),
                hovertemplate="%{x:.1f}%<extra>" + orientation + "</extra>",
            )
        )
    _style(fig, 90 + 52 * len(countries))
    fig.update_layout(barmode="stack", bargap=0.3, legend=dict(traceorder="normal"), margin=dict(t=48))
    fig.update_xaxes(range=[0, 100], dtick=20, ticksuffix="%", showgrid=True, gridcolor=GRID, title_text="Share of the country's articles")
    fig.update_yaxes(autorange="reversed")
    return fig


def _wrap(label: str, width: int = 18) -> str:
    words, lines, line = str(label).split(), [], ""
    for word in words:
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    return "<br>".join(lines)


def share_heatmap_figure(matrix: pd.DataFrame, column_label=str.capitalize, height: int | None = None, wrap_columns: bool = False) -> go.Figure:
    """Rows x columns of shares (0-1), labelled in every cell."""
    z = matrix.values * 100
    columns = [column_label(c) for c in matrix.columns]
    if wrap_columns:
        columns = [_wrap(c, 14) for c in columns]
    fig = go.Figure(
        go.Heatmap(
            z=z, x=columns, y=list(matrix.index), colorscale=SEQUENTIAL_BLUE, zmin=0,
            text=[[f"{v:.0f}%" for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=11),
            xgap=2, ygap=2, showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}<br>%{z:.1f}% of articles<extra></extra>",
        )
    )
    _style(fig, height or 44 + 34 * len(matrix.index), legend=False)
    fig.update_xaxes(side="top", tickfont=dict(color=INK))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=INK))
    return fig


def activity_heatmap_figure(matrix: pd.DataFrame) -> go.Figure:
    """Outlets x months, coloured relative to each outlet's own busiest month."""
    peaks = matrix.max(axis=1).replace(0, 1)
    relative = matrix.div(peaks, axis=0)
    fig = go.Figure(
        go.Heatmap(
            z=relative.values, x=matrix.columns, y=list(matrix.index), customdata=matrix.values,
            colorscale=SEQUENTIAL_BLUE, zmin=0, zmax=1, showscale=False, ygap=2,
            hovertemplate="<b>%{y}</b><br>%{x|%b %Y}: %{customdata:,} articles<extra></extra>",
        )
    )
    _style(fig, 44 + 26 * len(matrix.index), legend=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=INK))
    return fig


def outlet_bars_figure(shares: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for orientation in ORIENTATIONS + ["Unclassified"]:
        rows = shares[shares["partisan"] == orientation]
        if rows.empty:
            continue
        fig.add_trace(
            go.Bar(
                y=rows["outlet"], x=rows["count"], orientation="h", name=orientation,
                marker=dict(color=ORIENTATION_COLORS[orientation]),
                text=[f"{s * 100:.1f}%" for s in rows["share"]], textposition="outside", cliponaxis=False,
                textfont=dict(color=MUTED, size=11),
                hovertemplate="<b>%{y}</b><br>%{x:,} articles<extra>" + orientation + "</extra>",
            )
        )
    _style(fig, 60 + 26 * len(shares))
    fig.update_layout(bargap=0.25)
    fig.update_yaxes(categoryorder="array", categoryarray=list(shares["outlet"]), autorange="reversed", showgrid=False, tickfont=dict(color=INK))
    fig.update_xaxes(title_text="Articles", showgrid=True, gridcolor=GRID, range=[0, float(shares["count"].max() or 1) * 1.12])
    fig.update_layout(legend=dict(traceorder="normal"))
    return fig


def year_ticks(first: int, last: int, current_year: int | None = None, max_labels: int = 4) -> tuple[list[int], list[str]]:
    """Evenly spaced year ticks that always include the first and last year.

    The in-progress year is marked with an asterisk ("2026*").
    """
    current_year = current_year or pd.Timestamp.today().year
    if last <= first:
        values = [first]
    else:
        step = max(1, -(-(last - first) // (max_labels - 1)))
        values = list(range(first, last, step))
        if last - values[-1] < step / 2 and len(values) > 1:
            values[-1] = last
        else:
            values.append(last)
    return values, [f"{v}*" if v == current_year else str(v) for v in values]


def topic_trends_figure(frames: dict[str, pd.DataFrame], colors: dict[str, str], topics: list[str], label=str.capitalize, dashed: set[str] | None = None) -> go.Figure:
    """Small multiples: one panel per topic, one line per series, share of articles by year."""
    cols = 5
    rows = max(1, -(-len(topics) // cols))
    fig = make_subplots(
        rows=rows, cols=cols, shared_yaxes=True,
        subplot_titles=[_wrap(t, 22) for t in topics], horizontal_spacing=0.03, vertical_spacing=0.2,
    )
    years = [int(y) for f in frames.values() for y in f["year"]] or [pd.Timestamp.today().year]
    first, last = min(years), max(years)
    tickvals, ticktext = year_ticks(first, last, max_labels=3)
    for index, topic in enumerate(topics):
        row, col = index // cols + 1, index % cols + 1
        for key, frame in frames.items():
            data = frame[frame["topic"] == topic].sort_values("year")
            if data.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=data["year"], y=data["share"] * 100, mode="lines", name=label(key), legendgroup=key,
                    showlegend=index == 0,
                    line=dict(color=colors.get(key, NEUTRAL), width=2, dash="dot" if dashed and key in dashed else "solid"),
                    hovertemplate="%{x}: %{y:.1f}%<extra>" + html.escape(label(key)) + "</extra>",
                ),
                row=row, col=col,
            )
    _style(fig, 190 + 210 * rows)
    fig.update_annotations(font=dict(size=12, color=INK))
    fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    fig.update_xaxes(
        tickmode="array", tickvals=tickvals, ticktext=ticktext, range=[first - 0.3, last + 0.3],
        showticklabels=True, showgrid=True, gridcolor=GRID, tickangle=0, tickfont=dict(size=11, color=TICK),
    )
    fig.update_layout(margin=dict(t=110, b=40), legend=dict(y=0.99, yanchor="top", yref="container", x=0))
    return fig


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

EXPLORER_CSS = """
<style>
div[data-testid="stLayoutWrapper"]:has(> .st-key-explorer_controls){position:sticky;top:62px;z-index:990;}
.st-key-explorer_controls{background:rgba(248,251,249,.97);border:1px solid var(--color-border);border-radius:10px;
  padding:10px 14px 4px;margin:6px 0 10px;backdrop-filter:blur(6px);box-shadow:0 6px 16px rgba(15,56,85,.06);}
.ex-title{font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;color:#111;margin:0 0 4px;}
.ex-lede{color:var(--color-text-muted);font-size:1rem;margin:0 0 14px;max-width:48rem;}
.ex-context{font-size:.9rem;color:var(--color-text-muted);margin:4px 0 8px;}
.ex-context b{color:#111;}
.ex-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:8px 0 4px;}
.ex-kpi{background:#fff;border:1px solid var(--color-border);border-radius:10px;padding:12px 14px;}
.ex-kpi-label{font-size:.8rem;color:var(--color-text-muted);display:flex;align-items:center;gap:6px;}
.ex-kpi-dot{width:9px;height:9px;border-radius:50%;display:inline-block;}
.ex-kpi-value{font-family:'Manrope',sans-serif;font-size:1.5rem;font-weight:700;color:#111;line-height:1.2;}
.ex-kpi-sub{font-size:.78rem;color:var(--color-text-muted);}
.ex-section{margin:34px 0 4px;padding-top:18px;border-top:1px solid var(--color-border);}
.ex-q{font-family:'Manrope',sans-serif;font-size:1.3rem;font-weight:700;color:#111;margin:2px 0 4px;}
.ex-read{font-size:.88rem;color:var(--color-text-muted);margin:0 0 6px;max-width:52rem;}
.ex-insight{background:#f3f7fc;border-left:3px solid #2a78d6;border-radius:0 8px 8px 0;padding:9px 14px;margin:6px 0 10px;font-size:.93rem;color:#1f2933;}
.ex-note{font-size:.82rem;color:var(--color-text-muted);margin:2px 0 0;}
@media (max-width:900px){.ex-kpis{grid-template-columns:repeat(2,minmax(0,1fr));}div[data-testid="stLayoutWrapper"]:has(> .st-key-explorer_controls){position:static;}}
</style>
"""


def _html(markup: str) -> None:
    st.markdown(" ".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


def _plot(fig: go.Figure) -> None:
    st.plotly_chart(
        fig,
        use_container_width=True,
        theme=None,  # our own styling; Streamlit's theme otherwise overrides tick fonts and margins
        config={"scrollZoom": False, "responsive": True, "displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )


def section_header(question: str, how_to_read: str) -> str:
    return (
        f"<div class='ex-section'>"
        f"<div class='ex-q'>{html.escape(question)}</div>"
        f"<p class='ex-read'>{html.escape(how_to_read)}</p></div>"
    )


def insight_html(text: str) -> str:
    return f"<div class='ex-insight'>{html.escape(text)}</div>" if text else ""


def _empty(message: str = "No data for this selection. Try a wider period or a different orientation.") -> None:
    st.info(message)


def _render_controls(year_min: int, year_max: int) -> tuple[str, int, int, str | None]:
    with st.container(key="explorer_controls"):
        c1, c2, c3 = st.columns([3.0, 1.3, 1.8])
        with c1:
            view = st.segmented_control(
                "Scope", options=COUNTRY_VIEW_OPTIONS, default=normalize_country_view(_default_country_view()),
                selection_mode="single", key="country_view",
            ) or COUNTRY_VIEW_COMPARE
        with c2:
            year_from, year_to = st.slider(
                "Period", min_value=year_min, max_value=year_max,
                value=_default_year_range(year_min, year_max), step=1, key="explorer_years",
            )
        with c3:
            orientation = st.segmented_control(
                "Outlet orientation", options=ORIENTATION_OPTIONS, default="All",
                selection_mode="single", key="explorer_orientation",
            ) or "All"
    return view, year_from, year_to, orientation_to_filter(orientation)


def _topic_order(*profiles: dict[str, float]) -> list[str]:
    totals: dict[str, float] = {}
    for profile in profiles:
        for topic, share in profile.items():
            totals[topic] = totals.get(topic, 0.0) + share
    return sorted(totals, key=totals.get, reverse=True)


def _render_comparison(date_from: str, date_to: str, partisan: str | None, period: str) -> None:
    data = load_comparison(date_from, date_to, partisan)
    if data["failed"]:
        st.warning("Some data could not be loaded right now; affected charts may be incomplete. Reload the page to retry.")

    shares = {c: outlet_shares(data["outlets"][c]) for c in COUNTRIES}
    totals = {c: int(shares[c]["count"].sum()) if not shares[c].empty else 0 for c in COUNTRIES}
    kpis = "".join(
        f"<div class='ex-kpi'><div class='ex-kpi-label'><span class='ex-kpi-dot' style='background:{COUNTRY_COLORS[c]}'></span>{c.capitalize()}</div>"
        f"<div class='ex-kpi-value'>{totals[c]:,}</div><div class='ex-kpi-sub'>articles · {len(shares[c])} outlets</div></div>"
        for c in COUNTRIES
    )
    _html(f"<div class='ex-context'>{html.escape(period)} · {html.escape(_partisan_label(partisan))}</div><div class='ex-kpis'>{kpis}</div>")

    # 1. Volume
    _html(section_header("How much does each country publish?",
                         "Articles per month from the monitored outlets. Changes reflect both publishing activity and which outlets are covered; the current month is left out until it is complete."))
    frames = {c: monthly_frame(data["monthly"][c]) for c in COUNTRIES}
    if any(not f.empty for f in frames.values()):
        _plot(volume_lines_figure(frames, COUNTRY_COLORS))
    else:
        _empty()

    # 2. Concentration
    _html(section_header("How concentrated is each country's output?",
                         "Each bar splits a country's articles by outlet: the five largest outlets from dark to light, everything else in grey. Hover to see outlet names."))
    segments = concentration_segments(shares)
    if not segments.empty:
        _html(insight_html(concentration_sentence(shares)))
        _plot(concentration_figure(segments))
    else:
        _empty()

    # 3. Orientation
    _html(section_header("What is the orientation mix of each country's output?",
                         "Share of articles by the outlet's self-described orientation. This describes the monitored outlets, so shifts mostly follow outlets entering or leaving the collection."))
    if partisan:
        _empty(f"Showing {partisan} outlets only. Set orientation to “All” to compare the mix.")
    else:
        mixes = {c: orientation_mix(shares[c]) for c in COUNTRIES}
        if any(mixes.values()):
            _plot(orientation_bars_figure(mixes))
        else:
            _empty()

    # 4. Topic profile
    _html(section_header("What does each country write about?",
                         "Percent of each country's articles tagged with a topic in the selected period. Articles can carry several topics, so columns add up to more than 100%."))
    profiles = {c: topic_profile(data["topics"][c], totals[c]) for c in COUNTRIES}
    profiles = {c: p for c, p in profiles.items() if p}
    matrix = profile_matrix(profiles)
    if not matrix.empty:
        matrix = matrix[[c for c in COUNTRIES if c in matrix.columns]]
        _html(insight_html(topic_gap_sentence(matrix)))
        _plot(share_heatmap_figure(matrix))
    else:
        _empty()

    # 5. Topic trends
    _html(section_header("Which topics are rising or falling?",
                         "Each panel is one topic: percent of that year's articles tagged with it, per country. * marks the current year (year to date). Years with fewer than 200 articles are left out because shares become unstable."))
    trend_frames = {c: topic_share_by_year(data["topics"][c], data["yearly"][c]) for c in COUNTRIES}
    trend_frames = {c: f for c, f in trend_frames.items() if not f.empty}
    if trend_frames and not matrix.empty:
        _plot(topic_trends_figure(trend_frames, COUNTRY_COLORS, list(matrix.index)))
    else:
        _empty()


def _render_country(country: str, date_from: str, date_to: str, partisan: str | None, period: str) -> None:
    data = load_country(country, date_from, date_to, partisan)
    if data["failed"]:
        st.warning("Some data could not be loaded right now; affected charts may be incomplete. Reload the page to retry.")
    name = country.capitalize()
    shares = outlet_shares(data["outlets"])
    total = int(shares["count"].sum()) if not shares.empty else 0
    mix = orientation_mix(shares)
    kpis = [
        ("Articles", f"{total:,}", period),
        ("Outlets", f"{len(shares)}", "with at least one article"),
        ("Top 3 outlets", pct(top_n_share(shares, 3)), "share of all articles"),
        ("Largest orientation", max(mix, key=mix.get) if mix else "—", pct(max(mix.values())) if mix else ""),
    ]
    _html(
        f"<div class='ex-context'><b>{html.escape(country_landscape_label(country))}</b> · {html.escape(period)} · {html.escape(_partisan_label(partisan))}</div>"
        "<div class='ex-kpis'>" + "".join(
            f"<div class='ex-kpi'><div class='ex-kpi-label'>{html.escape(k)}</div><div class='ex-kpi-value'>{html.escape(v)}</div>"
            f"<div class='ex-kpi-sub'>{html.escape(s)}</div></div>" for k, v, s in kpis
        ) + "</div>"
    )

    # 1. Volume by orientation
    _html(section_header(f"How much is published in {name}, and from which side?",
                         "Articles per month, stacked by outlet orientation. The current month is left out until it is complete."))
    frames = {o: monthly_frame(rows) for o, rows in data["monthly"].items()}
    if any(not f.empty for f in frames.values()):
        _plot(orientation_area_figure(frames) if not partisan else volume_lines_figure(frames, ORIENTATION_COLORS, label=str))
    else:
        _empty()

    # 2. Outlets
    _html(section_header("Which outlets produce it?",
                         "The 15 largest outlets by articles in the period, coloured by orientation; labels show each outlet's share of the country total."))
    if not shares.empty:
        top = shares.head(15)
        _html(insight_html(
            f"{top.iloc[0]['outlet']} alone accounts for {pct(top.iloc[0]['share'])} of {name}'s articles; "
            f"the three largest outlets for {pct(top_n_share(shares, 3))}."
        ))
        _plot(outlet_bars_figure(top))
        with st.container():
            st.dataframe(
                shares.assign(share=shares["share"] * 100)[["outlet", "partisan", "count", "share"]],
                hide_index=True, use_container_width=True, height=min(38 + 35 * len(shares), 260),
                column_config={
                    "outlet": "Outlet", "partisan": "Orientation",
                    "count": st.column_config.NumberColumn("Articles", format="%d"),
                    "share": st.column_config.ProgressColumn("Share", format="%.1f%%", min_value=0, max_value=100),
                },
            )
    else:
        _empty()

    # 3. Activity
    _html(section_header("When was each outlet active?",
                         "One row per outlet, one cell per month. Darker means closer to that outlet's busiest month, so small and large outlets are equally visible; white gaps are months with no collected articles (inactive, or not collected)."))
    activity = outlet_activity_matrix(data["outlet_monthly"], list(shares["outlet"].head(15)))
    if not activity.empty:
        _plot(activity_heatmap_figure(activity))
    else:
        _empty()

    # 4. Topic profile by outlet
    _html(section_header("What does each outlet write about?",
                         "Percent of each outlet's articles tagged with a topic (12 largest outlets). Articles can carry several topics, so rows add up to more than 100%."))
    counts = dict(zip(shares["outlet"], shares["count"]))
    outlet_profiles = {o: topic_profile(rows, int(counts.get(o, 0))) for o, rows in data["outlet_topics"].items()}
    outlet_profiles = {o: p for o, p in outlet_profiles.items() if p}
    country_profile = topic_profile(data["topics"], total)
    nordic_total = sum(int(r.get("count") or 0) for r in data["nordic_yearly"])
    nordic_profile = topic_profile(data["nordic_topics"], nordic_total)
    topics = _topic_order(country_profile, nordic_profile)
    if outlet_profiles and topics:
        matrix = profile_matrix(outlet_profiles, row_order=topics).T
        matrix = matrix.reindex([o for o in shares["outlet"] if o in matrix.index])
        _html(insight_html(topic_gap_sentence(matrix.T, entity_label=str)))
        _plot(share_heatmap_figure(matrix, column_label=str, wrap_columns=True, height=90 + 34 * len(matrix.index)))
    else:
        _empty()

    # 5. Topic trends vs Nordic average
    _html(section_header(f"Which topics are rising or falling in {name}?",
                         f"Each panel is one topic: percent of that year's articles tagged with it, in {name} (solid) and across all four countries (dotted). * marks the current year (year to date). Years with fewer than 200 articles are left out."))
    trend_frames = {
        country: topic_share_by_year(data["topics"], data["yearly"]),
        "nordic": topic_share_by_year(data["nordic_topics"], data["nordic_yearly"]),
    }
    trend_frames = {k: f for k, f in trend_frames.items() if not f.empty}
    if trend_frames and topics:
        colors = {country: COUNTRY_COLORS[country], "nordic": "#8a8f98"}
        labels = {country: name, "nordic": "Nordic average"}
        _plot(topic_trends_figure(trend_frames, colors, topics, label=labels.get, dashed={"nordic"}))
    else:
        _empty()


def show_explorer_page() -> None:
    """Show the Explorer."""
    _html(EXPLORER_CSS)
    _html(
        "<div class='ex-title'>Explorer</div>"
        "<p class='ex-lede'>Compare the four countries, or pick one to see which outlets and topics drive it. "
        "Every chart below follows the three filters.</p>"
    )
    overview = fetch_overview()
    year_min, year_max = _year_bounds(overview)
    view, year_from, year_to, partisan = _render_controls(year_min, year_max)
    mode, country = country_view_to_state(view)
    st.session_state["explorer_mode"] = mode
    st.session_state["quick_country"] = country
    if country:
        st.session_state["deep_country"] = country

    date_from, date_to = f"{year_from}-01-01", f"{year_to}-12-31"
    period = f"{year_from}–{year_to}"
    if mode == MODE_COMPARE:
        _render_comparison(date_from, date_to, partisan, period)
    else:
        _render_country(country, date_from, date_to, partisan, period)

    latest = str(((overview or {}).get("date_range") or {}).get("latest") or "")[:10]
    _html(
        "<p class='ex-note' style='margin-top:28px;'>Source: cleaned Nordicamo article index"
        + (f", latest article {html.escape(latest)}" if latest else "")
        + ". Orientation labels are outlets' self-descriptions; topic tags are automated and multi-label.</p>"
    )
    render_footer_bar()
