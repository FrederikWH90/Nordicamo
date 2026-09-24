"""Explorer page layout."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from media_helpers import consolidate_outlets
from pages.footer import render_footer_bar
from services.api import (
    fetch_analysis_bundle,
    fetch_articles_over_time,
    fetch_articles_over_time_by_outlet,
    fetch_categories,
    fetch_categories_over_time,
    fetch_concentration_metrics,
    fetch_overview,
    fetch_partisan_mix,
    fetch_topic_similarity,
    fetch_top_outlets,
)

COUNTRIES = ["denmark", "sweden", "norway", "finland"]
ORIENTATION_ORDER = ["Left", "Right", "Other"]
PARTISAN_MIX_ORDER = ["Right", "Left", "Other", "Unclassified"]
MODE_COMPARE = "Country Comparison"
MODE_DEEP_DIVE = "Country Deep Dive"
COUNTRY_VIEW_COMPARE = "Compare countries"
COUNTRY_VIEW_OPTIONS = [COUNTRY_VIEW_COMPARE, "Denmark", "Finland", "Norway", "Sweden"]

COUNTRY_COLORS = {
    "denmark": "#C8102E",
    "sweden": "#FECC00",
    "norway": "#87CEEB",
    "finland": "#003580",
}

COUNTRY_LANDSCAPE_LABELS = {
    "denmark": "Danish Alternative Media Landscape",
    "sweden": "Swedish Alternative Media Landscape",
    "norway": "Norwegian Alternative Media Landscape",
    "finland": "Finnish Alternative Media Landscape",
}


def normalize_explorer_mode(mode: str | None) -> str:
    if mode in {MODE_COMPARE, MODE_DEEP_DIVE}:
        return mode
    return MODE_COMPARE


def normalize_country(country: str | None) -> str:
    if country in COUNTRIES:
        return country
    return "denmark"


def country_landscape_label(country: str | None) -> str:
    normalized = normalize_country(country)
    return COUNTRY_LANDSCAPE_LABELS[normalized]


def recent_years(latest_year: int, count: int = 4) -> list[int]:
    return list(range(latest_year - count + 1, latest_year + 1))


def country_year_label(country: str, year: int | str) -> str:
    return f"{str(country).capitalize()}<br>{year}"


def country_year_axis_pairs(countries: list[str], years: list[int]) -> list[tuple[str, str]]:
    return [(country.capitalize(), str(year)) for country in countries for year in years]


def country_year_multicategory_axis(pairs: list[tuple[str, str]]) -> list[list[str]]:
    return [[country for country, _ in pairs], [year for _, year in pairs]]


def normalize_country_orientation_entity(entity: str) -> str:
    text = str(entity or "").strip()
    if " - " not in text:
        return text.capitalize()
    country, orientation = text.split(" - ", 1)
    return f"{country.strip().capitalize()} - {orientation.strip().capitalize()}"


def country_orientation_entities(entities: list[str]) -> list[str]:
    normalized_entities = {normalize_country_orientation_entity(entity) for entity in entities}
    ordered = [
        f"{country.capitalize()} - {orientation}"
        for country in COUNTRIES
        for orientation in ORIENTATION_ORDER
        if f"{country.capitalize()} - {orientation}" in normalized_entities
    ]
    extras = sorted(normalized_entities.difference(ordered))
    return ordered + extras


def country_orientation_axis_labels(entities: list[str]) -> list[str]:
    return [entity.replace(" - ", "<br>") for entity in entities]


def country_orientation_axis_pairs(entities: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for entity in entities:
        if " - " not in entity:
            pairs.append((entity, ""))
            continue
        country, orientation = entity.split(" - ", 1)
        pairs.append((country, orientation))
    return pairs


def country_orientation_multicategory_axis(entities: list[str]) -> list[list[str]]:
    pairs = country_orientation_axis_pairs(entities)
    return [[country for country, _ in pairs], [orientation for _, orientation in pairs]]


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
    """Describe the active analysis lens in one concise sentence."""
    normalized = normalize_country_view(view)
    if normalized == COUNTRY_VIEW_COMPARE:
        return "Compare publication patterns, outlet structure, orientations, and topics across the Nordic region."
    return (
        "Examine publication patterns, outlet structure, and topics within the "
        f"{country_landscape_label(normalized).lower()}."
    )


def deep_dive_view_options() -> list[str]:
    return ["Publication volume", "Outlet drivers", "Orientation over time", "Topic development"]


def topics_metric_transform(df: pd.DataFrame, mode: str) -> tuple[pd.DataFrame, str]:
    """Transform topic counts for chart mode."""
    if df.empty:
        return df, "Articles"
    if mode == "Share of Outlet Topics (%)":
        total_per_outlet = df.groupby("outlet")["count"].transform("sum")
        df = df.copy()
        df["value"] = (df["count"] / total_per_outlet * 100).round(2)
        return df, "Share (%)"
    df = df.copy()
    df["value"] = df["count"]
    return df, "Articles"


def _wrap_two_line_label(label: str) -> str:
    """Wrap long category labels into max two lines for x-axis readability."""
    text = str(label or "").strip()
    if len(text) <= 16:
        return text
    if " & " in text:
        left, right = text.split(" & ", 1)
        return f"{left} &<br>{right}"
    words = text.split()
    if len(words) <= 2:
        return text
    split_at = len(words) // 2
    return f"{' '.join(words[:split_at])}<br>{' '.join(words[split_at:])}"


def _matrix_records_to_df(records: list[dict], entities: list[str]) -> pd.DataFrame:
    """Convert pairwise records to symmetric matrix."""
    if not entities:
        return pd.DataFrame()
    matrix = pd.DataFrame(0.0, index=entities, columns=entities)
    for entity in entities:
        matrix.loc[entity, entity] = 1.0
    for row in records or []:
        a = row.get("entity_a")
        b = row.get("entity_b")
        value = float(row.get("value", 0.0))
        if a in matrix.index and b in matrix.columns:
            matrix.loc[a, b] = value
            matrix.loc[b, a] = value
    return matrix


def _mask_matrix_diagonal(matrix: pd.DataFrame) -> pd.DataFrame:
    display_matrix = matrix.copy()
    diagonal_length = min(len(display_matrix.index), len(display_matrix.columns))
    for idx in range(diagonal_length):
        display_matrix.iat[idx, idx] = float("nan")
    return display_matrix


def _off_diagonal_values(matrix: pd.DataFrame) -> list[float]:
    values = []
    for row_idx, _ in enumerate(matrix.index):
        for col_idx, _ in enumerate(matrix.columns):
            if row_idx == col_idx:
                continue
            value = matrix.iat[row_idx, col_idx]
            if pd.notna(value):
                values.append(float(value))
    return values


def _similarity_color_bounds(matrix: pd.DataFrame) -> tuple[float, float]:
    values = _off_diagonal_values(matrix)
    if not values:
        return 0.0, 1.0
    low = min(values)
    high = max(values)
    padding = max(0.01, (high - low) * 0.12)
    return max(0.0, low - padding), min(1.0, high + padding)


def _plot(fig: go.Figure) -> None:
    """Render a compact, container-sized Plotly chart."""
    is_heatmap = any(getattr(trace, "type", None) == "heatmap" for trace in fig.data)
    current_height = fig.layout.height or 360
    fig.update_layout(
        autosize=True,
        height=min(int(current_height), 390 if is_heatmap else 340),
        font={"size": 11},
    )
    fig.update_xaxes(tickfont={"size": 10}, titlefont={"size": 11})
    fig.update_yaxes(tickfont={"size": 10}, titlefont={"size": 11})
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": False, "responsive": True, "displaylogo": False},
    )


def _period_label(year_from: int, year_to: int) -> str:
    return f"{year_from}-{year_to}"


def _partisan_label(partisan: str | None) -> str:
    return "All orientations" if partisan is None else partisan


def _filter_tokens(*items: tuple[str, str]) -> str:
    return "".join(
        f"<span class='filter-token'>{label}: {value}</span>" for label, value in items
    )


def _chart_context(question: str, unit: str, *filters: tuple[str, str]) -> None:
    st.markdown(
        f"""
        <div class='chart-context'>
            {question}<br/>
            <span>Unit: {unit}</span>
            <span class='filter-summary'>{_filter_tokens(*filters)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _year_bounds(overview: dict | None) -> tuple[int, int]:
    dr = overview.get("date_range", {}) if overview else {}
    try:
        year_min = int(str(dr.get("earliest"))[:4]) if dr.get("earliest") else 2005
    except Exception:
        year_min = 2005
    try:
        year_max = int(str(dr.get("latest"))[:4]) if dr.get("latest") else 2025
    except Exception:
        year_max = 2025
    if year_min > year_max:
        year_min, year_max = 2005, 2025
    return year_min, year_max


def _default_year_range(year_min: int, year_max: int) -> tuple[int, int]:
    """Prefer 2016-2026 defaults while respecting available bounds."""
    default_start = max(year_min, 2016)
    default_end = min(year_max, 2026)
    if default_end < default_start:
        return year_min, year_max
    return default_start, default_end


def _inject_explorer_styles() -> None:
    st.markdown(
        """
        <style>
        .explorer-control-bar {
            position: sticky;
            top: 76px;
            z-index: 980;
            background: rgba(248, 251, 248, 0.95);
            border: 1px solid var(--color-border);
            border-radius: 10px;
            padding: 10px 12px 2px 12px;
            margin-bottom: 14px;
            backdrop-filter: blur(6px);
        }
        .explorer-note {
            color: var(--color-text-muted);
            font-size: 0.9rem;
            margin-top: 2px;
        }
        /* Keep Plotly charts flush inside Streamlit containers on Explorer. */
        .stPlotlyChart {
            background: transparent !important;
            border: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        .stPlotlyChart > div,
        .stPlotlyChart .js-plotly-plot,
        .stPlotlyChart .plot-container,
        .stPlotlyChart .svg-container {
            width: 100% !important;
            max-width: 100% !important;
            overflow: hidden !important;
        }
        /* Make selected outlet tags in multiselect use green instead of red. */
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: rgba(46, 125, 50, 0.10) !important;
            border: 1px solid #2E7D32 !important;
            color: #1B5E20 !important;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #1B5E20 !important;
        }
        .explorer-mode-label {
            color: var(--color-text-muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }
        .analysis-workspace {
            border-top: 1px solid var(--color-border);
            border-bottom: 1px solid var(--color-border);
            padding: 16px 0 14px;
            margin: 22px 0 24px;
        }
        .analysis-workspace-heading {
            color: var(--color-text);
            font-family: 'Manrope', 'Helvetica', 'Arial', sans-serif;
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 2px;
        }
        .analysis-workspace-summary {
            color: var(--color-text-muted);
            font-size: 0.92rem;
            margin: 8px 0 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_global_country_kpis(overview: dict | None) -> None:
    by_country = (overview or {}).get("by_country", {})
    if not by_country:
        return

    with st.container():
        denmark_col, sweden_col, norway_col, finland_col = st.columns(4)
        with denmark_col:
            st.markdown(
                f"<div style='padding:4px 2px;'><div style='font-size:13px; color: var(--color-text-muted);'>Denmark</div>"
                f"<div style='font-size:28px; color: var(--color-text); font-weight:600; line-height:1.1;'>{int(by_country.get('denmark', 0)):,}</div></div>",
                unsafe_allow_html=True,
            )
        with sweden_col:
            st.markdown(
                f"<div style='padding:4px 2px;'><div style='font-size:13px; color: var(--color-text-muted);'>Sweden</div>"
                f"<div style='font-size:28px; color: var(--color-text); font-weight:600; line-height:1.1;'>{int(by_country.get('sweden', 0)):,}</div></div>",
                unsafe_allow_html=True,
            )
        with norway_col:
            st.markdown(
                f"<div style='padding:4px 2px;'><div style='font-size:13px; color: var(--color-text-muted);'>Norway</div>"
                f"<div style='font-size:28px; color: var(--color-text); font-weight:600; line-height:1.1;'>{int(by_country.get('norway', 0)):,}</div></div>",
                unsafe_allow_html=True,
            )
        with finland_col:
            st.markdown(
                f"<div style='padding:4px 2px;'><div style='font-size:13px; color: var(--color-text-muted);'>Finland</div>"
                f"<div style='font-size:28px; color: var(--color-text); font-weight:600; line-height:1.1;'>{int(by_country.get('finland', 0)):,}</div></div>",
                unsafe_allow_html=True,
            )


def _default_country_view() -> str:
    current_view = st.session_state.get("country_view")
    if current_view in COUNTRY_VIEW_OPTIONS:
        return current_view
    mode = normalize_explorer_mode(st.session_state.get("explorer_mode"))
    if mode == MODE_DEEP_DIVE:
        country = normalize_country(st.session_state.get("quick_country") or st.session_state.get("deep_country"))
        return country.capitalize()
    return COUNTRY_VIEW_COMPARE


def _render_country_view_selector() -> tuple[str, str | None]:
    st.markdown(
        """
        <div class='analysis-workspace'>
            <div class='explorer-mode-label'>Analysis lens</div>
            <div class='analysis-workspace-heading'>Choose a country scope</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    default_view = normalize_country_view(_default_country_view())
    if hasattr(st, "segmented_control"):
        selected = st.segmented_control(
            "Country scope",
            options=COUNTRY_VIEW_OPTIONS,
            default=default_view,
            selection_mode="single",
            label_visibility="collapsed",
            key="country_view",
        )
    else:
        selected = st.radio(
            "Country scope",
            options=COUNTRY_VIEW_OPTIONS,
            index=COUNTRY_VIEW_OPTIONS.index(default_view),
            horizontal=True,
            key="country_view",
            label_visibility="collapsed",
        )
    st.markdown(
        f"<div class='analysis-workspace-summary'>{country_view_summary(selected)}</div>",
        unsafe_allow_html=True,
    )
    return country_view_to_state(selected)


def _render_outlets_table(country: str, date_from: str, date_to: str) -> None:
    outlets_data = fetch_top_outlets(country=country, date_from=date_from, date_to=date_to, limit=300)
    if not outlets_data or not outlets_data.get("data"):
        st.info("No outlet data available for this selection.")
        return
    df_outlets = pd.DataFrame(consolidate_outlets(outlets_data["data"]))
    st.dataframe(
        df_outlets[["domain", "partisan", "count"]].style.format({"count": "{:,}"}),
        use_container_width=True,
        hide_index=True,
        column_config={"domain": "Domain", "partisan": "Partisanship", "count": "Articles"},
    )


def _render_categories_table(country: str) -> None:
    categories_data = fetch_categories(country=country, partisan=None)
    if not categories_data or not categories_data.get("data"):
        st.info("No category data available for this selection.")
        return
    df_cat = pd.DataFrame(categories_data["data"]).sort_values("count", ascending=False).head(10)
    total = df_cat["count"].sum() or 1
    df_cat["percentage"] = (df_cat["count"] / total * 100).round(1)
    st.dataframe(
        df_cat[["category", "count", "percentage"]].style.format(
            {"count": "{:,}", "percentage": "{:.1f}%"}
        ),
        use_container_width=True,
        hide_index=True,
        column_config={"category": "Category", "count": "Articles", "percentage": "Percentage"},
    )


def _render_compare_mode(overview: dict | None, analysis_bundle: dict | None = None) -> None:
    year_min, year_max = _year_bounds(overview)
    default_year_from, default_year_to = _default_year_range(year_min, year_max)

    st.subheader("Articles Over Time by Country")
    c1, c2, c3 = st.columns([1, 1, 1.4])
    with c1:
        granularity = st.selectbox(
            "Time Granularity",
            options=["Year", "Month", "Week"],
            index=1,
            key="cmp_granularity",
        )
    with c2:
        partisan_filter = st.selectbox(
            "Filter by Partisan",
            options=[None, "Right", "Left", "Other"],
            format_func=lambda x: "All" if x is None else x,
            key="cmp_partisan",
        )
    with c3:
        year_from, year_to = st.slider(
            "Year range",
            min_value=year_min,
            max_value=year_max,
            value=(default_year_from, default_year_to),
            step=1,
            key="cmp_year_range",
        )

    date_from = f"{year_from}-01-01"
    date_to = f"{year_to}-12-31"
    period = _period_label(year_from, year_to)
    partisan_label = _partisan_label(partisan_filter)
    bundle_filters = (analysis_bundle or {}).get("filters", {})
    can_use_bundle = (
        analysis_bundle
        and bundle_filters.get("date_from") == date_from
        and bundle_filters.get("date_to") == date_to
        and bundle_filters.get("granularity") == granularity.lower()
        and bundle_filters.get("partisan") == partisan_filter
    )

    with st.container(border=True):
        _chart_context(
            "How does publication volume develop across the four Nordic countries?",
            "article count",
            ("Period", period),
            ("Granularity", granularity),
            ("Orientation", partisan_label),
        )
        fig = go.Figure()
        if can_use_bundle and analysis_bundle.get("articles_over_time"):
            bundled_rows = pd.DataFrame(analysis_bundle["articles_over_time"].get("data", []))
            country_time_data = {
                ctry: {"data": bundled_rows[bundled_rows["country"] == ctry].to_dict("records")}
                for ctry in COUNTRIES
                if not bundled_rows.empty
            }
        else:
            country_time_data = {
                ctry: fetch_articles_over_time(
                    country=ctry,
                    partisan=partisan_filter,
                    granularity=granularity.lower(),
                    date_from=date_from,
                    date_to=date_to,
                )
                for ctry in COUNTRIES
            }
        for ctry, time_data in country_time_data.items():
            if time_data and time_data.get("data"):
                df_time = pd.DataFrame(time_data["data"])
                df_time["date"] = pd.to_datetime(df_time["date"], errors="coerce")
                df_time = df_time.sort_values("date")
                fig.add_trace(
                    go.Scatter(
                        x=df_time["date"],
                        y=df_time["count"],
                        mode="lines+markers",
                        name=ctry.capitalize(),
                        line=dict(color=COUNTRY_COLORS.get(ctry, "#1f77b4"), width=2),
                        marker=dict(size=6),
                    )
                )
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Articles",
            height=430,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5),
            title="",
        )
        _plot(fig)

    with st.container(border=True):
        st.subheader("Partisanship Mix by Country")
        mix_years = recent_years(year_max)
        mix_period = f"{mix_years[0]}-{mix_years[-1]}"
        _chart_context(
            "How has each country's outlet-orientation mix developed over the last four indexed years?",
            "percent of articles",
            ("Period", mix_period),
            ("Orientation", "All orientations"),
        )
        st.caption(
            "Outlet orientations are taken from the startlist. Unclassified only appears when an indexed outlet is missing a startlist orientation label."
        )
        partisan_rows = []
        if can_use_bundle and analysis_bundle.get("partisan_mix"):
            for row in analysis_bundle.get("partisan_mix", []):
                if int(row.get("year", 0)) not in mix_years:
                    continue
                if row.get("partisan") == "Unclassified" and float(row.get("count", 0) or 0) <= 0:
                    continue
                partisan_rows.append(
                    {
                        "country": str(row.get("country", "")).capitalize(),
                        "year": str(row.get("year")),
                        "partisan": row.get("partisan"),
                        "share": float(row.get("share", 0.0)) * 100.0,
                    }
                )
        else:
            for ctry in COUNTRIES:
                for year in mix_years:
                    mix = fetch_partisan_mix(
                        country=ctry,
                        date_from=f"{year}-01-01",
                        date_to=f"{year}-12-31",
                    )
                    if mix and mix.get("data"):
                        for row in mix["data"]:
                            if row.get("partisan") == "Unclassified" and float(row.get("count", 0) or 0) <= 0:
                                continue
                            partisan_rows.append(
                                {
                                    "country": ctry.capitalize(),
                                    "year": str(year),
                                    "partisan": row.get("partisan"),
                                    "share": float(row.get("share", 0.0)) * 100.0,
                                }
                            )
                        if mix.get("unknown_or_missing_count", 0) > 0 and not any(
                            row.get("partisan") == "Unclassified" for row in mix["data"]
                        ):
                            total_count = float(mix.get("total_count", 0) or 0)
                            unclassified_count = float(mix.get("unknown_or_missing_count", 0) or 0)
                            partisan_rows.append(
                                {
                                    "country": ctry.capitalize(),
                                    "year": str(year),
                                    "partisan": "Unclassified",
                                    "share": (unclassified_count / total_count * 100.0) if total_count else 0.0,
                                }
                            )
        if partisan_rows:
            df_partisan = pd.DataFrame(partisan_rows)
            axis_pairs = country_year_axis_pairs(COUNTRIES, mix_years)
            x_axis = country_year_multicategory_axis(axis_pairs)
            color_map = {
                "Right": "#0066CC",
                "Left": "#DC143C",
                "Other": "#2ca02c",
                "Unclassified": "#9AA3AF",
            }
            partisan_order = [
                label
                for label in PARTISAN_MIX_ORDER
                if label in set(df_partisan["partisan"].dropna())
            ]
            extra_partisans = [
                str(label)
                for label in df_partisan["partisan"].dropna().unique()
                if label not in partisan_order
            ]
            fig_partisan = go.Figure()
            for partisan in partisan_order + extra_partisans:
                rows = df_partisan[df_partisan["partisan"] == partisan]
                shares_by_group = {
                    (row["country"], row["year"]): float(row["share"])
                    for _, row in rows.iterrows()
                }
                fig_partisan.add_trace(
                    go.Bar(
                        x=x_axis,
                        y=[
                            shares_by_group.get((country, year), 0.0)
                            for country, year in axis_pairs
                        ],
                        customdata=axis_pairs,
                        name=partisan,
                        marker_color=color_map.get(partisan),
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            "Year: %{customdata[1]}<br>"
                            f"Category: {partisan}<br>"
                            "Share: %{y:.1f}%<extra></extra>"
                        ),
                    )
                )
            fig_partisan.update_layout(
                xaxis_title="",
                yaxis_title="Share (%)",
                height=430,
                yaxis=dict(range=[0, 100]),
                barmode="stack",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.05,
                    xanchor="center",
                    x=0.5,
                    title_text="Category",
                    font=dict(size=14),
                    title_font=dict(size=14),
                ),
                margin=dict(t=80, b=95),
            )
            fig_partisan.update_xaxes(type="multicategory", tickangle=0, automargin=True)
            _plot(fig_partisan)
        else:
            st.info("No partisan data available for this selection.")

    with st.container(border=True):
        st.subheader("Outlet Diversity")
        diversity_years = recent_years(year_max)
        diversity_period = f"{diversity_years[0]}-{diversity_years[-1]}"
        _chart_context(
            "How has outlet diversity developed over the last four indexed years?",
            "effective outlet count (1/HHI)",
            ("Period", diversity_period),
            ("Orientation", partisan_label),
        )
        st.caption(
            "HHI measures concentration by summing squared outlet shares. Here it is inverted (1/HHI), so the number reads like the approximate count of equally sized outlets behind the observed output. Higher values mean a more distributed outlet landscape; lower values mean a few outlets dominate."
        )
        concentration_rows = []
        if can_use_bundle and analysis_bundle.get("concentration"):
            for row in analysis_bundle.get("concentration", []):
                if int(row.get("year", 0)) not in diversity_years:
                    continue
                concentration_rows.append(
                    {
                        "country": str(row.get("country", "")).capitalize(),
                        "year": str(row.get("year")),
                        "enp": float(row.get("enp", 0.0)),
                    }
                )
        else:
            for ctry in COUNTRIES:
                for year in diversity_years:
                    metrics = fetch_concentration_metrics(
                        country=ctry,
                        partisan=partisan_filter,
                        date_from=f"{year}-01-01",
                        date_to=f"{year}-12-31",
                        top_n=5,
                    )
                    if metrics:
                        concentration_rows.append(
                            {
                                "country": ctry.capitalize(),
                                "year": str(year),
                                "enp": float(metrics.get("enp", 0.0)),
                            }
                        )
        if concentration_rows:
            df_concentration = pd.DataFrame(concentration_rows)
            df_concentration = df_concentration.rename(columns={"enp": "effective_outlet_count"})
            fig_concentration = px.bar(
                df_concentration,
                x="country",
                y="effective_outlet_count",
                color="year",
                barmode="group",
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_concentration.update_layout(
                height=430,
                yaxis_title="Outlet diversity score (1/HHI)",
                xaxis_title="",
                legend_title_text="Year",
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
                margin=dict(l=105, r=30, t=80, b=60),
                annotations=[
                    dict(
                        x=-0.12,
                        y=1.02,
                        xref="paper",
                        yref="paper",
                        text="More diverse ↑",
                        showarrow=False,
                        font=dict(size=12, color="#2E7D32"),
                        xanchor="left",
                    ),
                    dict(
                        x=-0.12,
                        y=-0.12,
                        xref="paper",
                        yref="paper",
                        text="Less diverse ↓",
                        showarrow=False,
                        font=dict(size=12, color="#8E3D38"),
                        xanchor="left",
                    ),
                ],
            )
            fig_concentration.update_traces(texttemplate="%{y:.2f}", textposition="outside")
            _plot(fig_concentration)
        else:
            st.info("No concentration data available for this selection.")

    if st.toggle("Advanced topic diagnostics", key="cmp_advanced_topics_loaded"):
        with st.container(border=True):
            st.subheader("Topics Over Time (All Countries)")
            _chart_context(
                "Which article categories rise or fall over time across the full Nordic selection?",
                "article count",
                ("Period", period),
                ("Granularity", granularity),
                ("Orientation", partisan_label),
            )
            topic_data = fetch_categories_over_time(
                country=None,
                partisan=partisan_filter,
                granularity=granularity.lower(),
                date_from=date_from,
                date_to=date_to,
                limit=8,
            )
            if topic_data and topic_data.get("data"):
                df_topics = pd.DataFrame(topic_data["data"])
                if not df_topics.empty and {"date", "category", "count"}.issubset(df_topics.columns):
                    df_topics["date"] = pd.to_datetime(df_topics["date"], errors="coerce")
                    df_topics = df_topics.sort_values("date")
                    fig_topics = go.Figure()
                    for topic in df_topics["category"].dropna().unique():
                        rows = df_topics[df_topics["category"] == topic]
                        fig_topics.add_trace(
                            go.Scatter(
                                x=rows["date"],
                                y=rows["count"],
                                mode="lines",
                                name=str(topic),
                                line=dict(width=2),
                            )
                        )
                    fig_topics.update_layout(
                        title="",
                        xaxis_title="Date",
                        yaxis_title="Articles",
                        height=430,
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                        margin=dict(b=90),
                    )
                    _plot(fig_topics)
                else:
                    st.info("No topic data available for this selection.")
            else:
                st.info("No topic data available for this selection.")

        with st.container(border=True):
            st.subheader("Agenda Similarity (Country x Orientation)")
            _chart_context(
                "How similar are country-orientation agendas based on relative topic distributions?",
                "cosine similarity",
                ("Period", period),
                ("Orientation layer", "Left, Right, Other"),
            )
            st.caption(
                "Each cell compares one country-orientation category with another, using normalized topic-share vectors built from article category counts. Self-comparisons are left blank so the color scale focuses on cross-group differences."
            )
            similarity = fetch_topic_similarity(
                level="country_partisan",
                date_from=date_from,
                date_to=date_to,
                limit_topics=12,
            )
            if similarity and similarity.get("entities"):
                entities = country_orientation_entities(
                    [str(e) for e in similarity.get("entities", [])]
                )
                raw_records = similarity.get("cosine", [])
                records = []
                for row in raw_records:
                    records.append(
                        {
                            "entity_a": normalize_country_orientation_entity(row.get("entity_a", "")),
                            "entity_b": normalize_country_orientation_entity(row.get("entity_b", "")),
                            "value": float(row.get("value", 0.0)),
                        }
                    )
                matrix = _matrix_records_to_df(records, entities)
                if not matrix.empty:
                    display_matrix = _mask_matrix_diagonal(matrix)
                    zmin, zmax = _similarity_color_bounds(display_matrix)
                    text_matrix = matrix.round(2).astype(str)
                    diagonal_length = min(len(text_matrix.index), len(text_matrix.columns))
                    for idx in range(diagonal_length):
                        text_matrix.iat[idx, idx] = ""
                    axis_labels = country_orientation_multicategory_axis(entities)
                    hover_matrix = [
                        [f"{row_entity} x {col_entity}" for col_entity in entities]
                        for row_entity in entities
                    ]
                    heatmap = go.Figure(
                        data=go.Heatmap(
                            z=display_matrix.values,
                            x=axis_labels,
                            y=axis_labels,
                            colorscale="Cividis",
                            zmin=zmin,
                            zmax=zmax,
                            text=text_matrix.values,
                            texttemplate="%{text}",
                            customdata=hover_matrix,
                            hovertemplate=(
                                "<b>%{customdata}</b><br>"
                                "Cosine similarity: %{z:.3f}<extra></extra>"
                            ),
                            xgap=3,
                            ygap=3,
                            colorbar=dict(title="Similarity"),
                        )
                    )
                    heatmap.update_layout(
                        height=640,
                        xaxis_title="",
                        yaxis_title="",
                        margin=dict(t=20, b=120, l=120, r=20),
                    )
                    heatmap.update_xaxes(type="multicategory", tickangle=0, automargin=True)
                    heatmap.update_yaxes(type="multicategory", autorange="reversed", automargin=True)
                    _plot(heatmap)
                else:
                    st.info("No similarity matrix available for this selection.")
            else:
                st.info("No similarity data available for this selection.")


def _render_deep_dive_mode(overview: dict | None) -> None:
    year_min, year_max = _year_bounds(overview)
    default_year_from, default_year_to = _default_year_range(year_min, year_max)
    country = normalize_country(st.session_state.get("quick_country") or st.session_state.get("deep_country"))
    st.session_state["quick_country"] = country
    st.session_state["deep_country"] = country
    st.subheader(country_landscape_label(country))

    view_type = st.radio(
        "Analysis view",
        options=deep_dive_view_options(),
        index=0,
        horizontal=True,
        key="deep_view_type",
    )
    c1, c2, c3 = st.columns([1, 1, 1.4])
    with c1:
        granularity = st.selectbox(
            "Time Granularity",
            options=["Year", "Month", "Week"],
            index=1,
            key="deep_granularity",
        )
    with c2:
        partisan_filter = st.selectbox(
            "Filter by Partisan",
            options=[None, "Right", "Left", "Other"],
            format_func=lambda x: "All" if x is None else x,
            key="deep_partisan",
        )
    with c3:
        year_from, year_to = st.slider(
            "Year range",
            min_value=year_min,
            max_value=year_max,
            value=(default_year_from, default_year_to),
            step=1,
            key="deep_year_range",
        )

    date_from = f"{year_from}-01-01"
    date_to = f"{year_to}-12-31"
    period = _period_label(year_from, year_to)
    partisan_label = _partisan_label(partisan_filter)

    with st.container(border=True):
        if view_type == "Publication volume":
            _chart_context(
                f"How does total publication volume develop in {country.capitalize()}?",
                "article count",
                ("Country", country.capitalize()),
                ("Period", period),
                ("Granularity", granularity),
                ("Orientation", partisan_label),
            )
        elif view_type == "Outlet drivers":
            _chart_context(
                f"Which selected outlets drive publication volume in {country.capitalize()}?",
                "article count",
                ("Country", country.capitalize()),
                ("Period", period),
                ("Granularity", granularity),
                ("Orientation", partisan_label),
            )
        elif view_type == "Orientation over time":
            _chart_context(
                f"How does publication volume differ by orientation in {country.capitalize()}?",
                "article count",
                ("Country", country.capitalize()),
                ("Period", period),
                ("Granularity", granularity),
            )
        else:
            _chart_context(
                f"Which article categories rise or fall in {country.capitalize()}?",
                "article count",
                ("Country", country.capitalize()),
                ("Period", period),
                ("Granularity", granularity),
                ("Orientation", partisan_label),
            )
        if view_type == "Publication volume":
            time_data = fetch_articles_over_time(
                country=country,
                partisan=partisan_filter,
                granularity=granularity.lower(),
                date_from=date_from,
                date_to=date_to,
            )
            if time_data and time_data.get("data"):
                df_time = pd.DataFrame(time_data["data"])
                df_time["date"] = pd.to_datetime(df_time["date"], errors="coerce")
                df_time = df_time.sort_values("date")
                fig = px.line(df_time, x="date", y="count", markers=True)
                fig.update_traces(line=dict(width=3, color="#1f77b4"), marker=dict(size=8))
                fig.update_layout(
                    title="",
                    xaxis_title="Date",
                    yaxis_title="Articles",
                    height=420,
                    hovermode="x unified",
                )
                _plot(fig)
            else:
                st.info("No data available for selected filters.")
        elif view_type == "Outlet drivers":
            outlets_list = fetch_top_outlets(
                country=country, partisan=partisan_filter, date_from=date_from, date_to=date_to, limit=20
            )
            selected_outlets = []
            if outlets_list and outlets_list.get("data"):
                outlet_options = [o["domain"] for o in outlets_list["data"]]
                selected_outlets = st.multiselect(
                    "Select Outlets",
                    options=outlet_options,
                    default=outlet_options[:5] if len(outlet_options) >= 5 else outlet_options,
                    key="deep_selected_outlets",
                )
            if not selected_outlets:
                st.info("Please select at least one outlet to display.")
            else:
                outlet_time_data = fetch_articles_over_time_by_outlet(
                    country=country,
                    outlets=selected_outlets,
                    granularity=granularity.lower(),
                    date_from=date_from,
                    date_to=date_to,
                )
                if outlet_time_data and outlet_time_data.get("data"):
                    df_outlets = pd.DataFrame(outlet_time_data["data"])
                    if not df_outlets.empty and {"date", "outlet", "count"}.issubset(df_outlets.columns):
                        df_outlets["date"] = pd.to_datetime(df_outlets["date"], errors="coerce")
                        df_outlets = df_outlets.sort_values("date")
                        fig = go.Figure()
                        colors_list = px.colors.qualitative.Set3
                        for idx, outlet in enumerate(selected_outlets):
                            outlet_rows = df_outlets[df_outlets["outlet"] == outlet.lower()]
                            if outlet_rows.empty:
                                continue
                            fig.add_trace(
                                go.Scatter(
                                    x=outlet_rows["date"],
                                    y=outlet_rows["count"],
                                    mode="lines+markers",
                                    name=outlet,
                                    line=dict(color=colors_list[idx % len(colors_list)], width=2),
                                    marker=dict(size=6),
                                )
                            )
                        fig.update_layout(
                            title="",
                            xaxis_title="Date",
                            yaxis_title="Articles",
                            height=420,
                            hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5),
                        )
                        _plot(fig)
                    else:
                        st.info("No data available for selected outlets.")
                else:
                    st.info("No data available for selected outlets.")
        elif view_type == "Orientation over time":
            fig = go.Figure()
            partisan_colors = {"Right": "#0066CC", "Left": "#DC143C", "Other": "#2ca02c"}
            for partisan in ["Right", "Left", "Other"]:
                time_data = fetch_articles_over_time(
                    country=country,
                    partisan=partisan,
                    granularity=granularity.lower(),
                    date_from=date_from,
                    date_to=date_to,
                )
                if time_data and time_data.get("data"):
                    df_time = pd.DataFrame(time_data["data"])
                    df_time["date"] = pd.to_datetime(df_time["date"], errors="coerce")
                    df_time = df_time.sort_values("date")
                    fig.add_trace(
                        go.Scatter(
                            x=df_time["date"],
                            y=df_time["count"],
                            mode="lines+markers",
                            name=partisan,
                            line=dict(color=partisan_colors[partisan], width=3),
                            marker=dict(size=8),
                        )
                    )
            fig.update_layout(
                title="",
                xaxis_title="Date",
                yaxis_title="Articles",
                height=420,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5),
            )
            _plot(fig)
        else:
            topic_data = fetch_categories_over_time(
                country=country,
                partisan=partisan_filter,
                granularity=granularity.lower(),
                date_from=date_from,
                date_to=date_to,
                limit=8,
            )
            if topic_data and topic_data.get("data"):
                df_topics = pd.DataFrame(topic_data["data"])
                if not df_topics.empty and {"date", "category", "count"}.issubset(df_topics.columns):
                    df_topics["date"] = pd.to_datetime(df_topics["date"], errors="coerce")
                    df_topics = df_topics.sort_values("date")
                    fig = go.Figure()
                    for topic in df_topics["category"].dropna().unique():
                        rows = df_topics[df_topics["category"] == topic]
                        fig.add_trace(
                            go.Scatter(
                                x=rows["date"],
                                y=rows["count"],
                                mode="lines",
                                name=str(topic),
                                line=dict(width=2),
                            )
                        )
                    fig.update_layout(
                        title="",
                        xaxis_title="Date",
                        yaxis_title="Articles",
                        height=420,
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                        margin=dict(b=90),
                    )
                    _plot(fig)
                else:
                    st.info("No topic data available for this selection.")
            else:
                st.info("No topic data available for this selection.")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader(f"Outlets ({country.capitalize()})")
            _chart_context(
                "Which outlets contribute the most indexed articles in this selection?",
                "article count",
                ("Country", country.capitalize()),
                ("Period", period),
            )
            _render_outlets_table(country=country, date_from=date_from, date_to=date_to)
    with right:
        with st.container(border=True):
            st.subheader(f"News Categories ({country.capitalize()})")
            _chart_context(
                "Which categories are most common in this country?",
                "article count and percent",
                ("Country", country.capitalize()),
                ("Period", "all indexed years"),
            )
            _render_categories_table(country=country)

    with st.expander("Advanced outlet and topic diagnostics", expanded=False):
        with st.container(border=True):
            st.subheader("Topics by Media")
            _chart_context(
                "How do selected outlets differ in their topic profiles?",
                "article count or percent",
                ("Country", country.capitalize()),
                ("Period", period),
                ("Orientation", partisan_label),
            )
            outlet_options_data = fetch_top_outlets(
                country=country,
                partisan=partisan_filter,
                date_from=date_from,
                date_to=date_to,
                limit=20,
            )
            outlet_options = []
            if outlet_options_data and outlet_options_data.get("data"):
                outlet_options = [row.get("domain") for row in outlet_options_data["data"] if row.get("domain")]

            selected_media = st.multiselect(
                "Select Media Outlets",
                options=outlet_options,
                default=outlet_options[:3] if len(outlet_options) >= 3 else outlet_options,
                key="deep_topics_by_media_outlets",
            )
            topics_value_mode = st.radio(
                "Metric",
                options=["Absolute Topic Counts", "Share of Outlet Topics (%)"],
                index=0,
                horizontal=True,
                key="deep_topics_by_media_metric",
            )

            if not selected_media:
                st.info("Select at least one outlet to compare topic profiles.")
            else:
                topic_rows = []
                for outlet in selected_media:
                    outlet_topics = fetch_categories_over_time(
                        country=country,
                        partisan=partisan_filter,
                        outlets=[outlet],
                        granularity=granularity.lower(),
                        date_from=date_from,
                        date_to=date_to,
                        limit=8,
                    )
                    if not outlet_topics or not outlet_topics.get("data"):
                        continue
                    df_outlet_topics = pd.DataFrame(outlet_topics["data"])
                    if df_outlet_topics.empty or not {"category", "count"}.issubset(df_outlet_topics.columns):
                        continue
                    aggregated = (
                        df_outlet_topics.groupby("category", as_index=False)["count"]
                        .sum()
                        .sort_values("count", ascending=False)
                    )
                    for _, row in aggregated.iterrows():
                        topic_rows.append(
                            {
                                "outlet": outlet,
                                "category": row["category"],
                                "count": int(row["count"]),
                            }
                        )

                if topic_rows:
                    df_topics_by_media = pd.DataFrame(topic_rows)
                    available_topics = (
                        df_topics_by_media.groupby("category", as_index=False)["count"]
                        .sum()
                        .sort_values("count", ascending=False)["category"]
                        .tolist()
                    )
                    default_topics = available_topics[:10]
                    selected_topics = st.multiselect(
                        "Select Topics",
                        options=available_topics,
                        default=default_topics,
                        key="deep_topics_by_media_topics",
                    )
                    if selected_topics:
                        df_topics_by_media = df_topics_by_media[
                            df_topics_by_media["category"].isin(selected_topics)
                        ].copy()
                    else:
                        df_topics_by_media = df_topics_by_media.iloc[0:0]

                if not topic_rows or df_topics_by_media.empty:
                    st.info("No topic-by-media data available for this selection.")
                else:
                    df_topics_by_media, y_label = topics_metric_transform(
                        df_topics_by_media,
                        mode=topics_value_mode,
                    )
                    df_topics_by_media["category_label"] = df_topics_by_media["category"].apply(_wrap_two_line_label)
                    fig_topics_media = px.bar(
                        df_topics_by_media,
                        x="category_label",
                        y="value",
                        color="outlet",
                        barmode="group",
                    )
                    fig_topics_media.update_layout(
                        title="",
                        xaxis_title="Topic",
                        yaxis_title=y_label,
                        height=420,
                        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
                        margin=dict(t=90, b=130),
                    )
                    fig_topics_media.update_xaxes(tickangle=0, automargin=True)
                    _plot(fig_topics_media)

        with st.container(border=True):
            st.subheader("Agenda Similarity (Outlets)")
            _chart_context(
                "How similar are selected outlet agendas based on relative topic distributions?",
                "cosine similarity",
                ("Country", country.capitalize()),
                ("Period", period),
                ("Orientation", partisan_label),
            )
            st.caption("Computed from normalized topic-share vectors built from article category counts, not full-text semantics.")
            similarity_outlet_options_data = fetch_top_outlets(
                country=country,
                partisan=partisan_filter,
                date_from=date_from,
                date_to=date_to,
                limit=12,
            )
            similarity_outlet_options = []
            if similarity_outlet_options_data and similarity_outlet_options_data.get("data"):
                similarity_outlet_options = [
                    row.get("domain") for row in similarity_outlet_options_data["data"] if row.get("domain")
                ]
            selected_similarity_outlets = st.multiselect(
                "Select Outlets for Similarity",
                options=similarity_outlet_options,
                default=similarity_outlet_options[:5] if len(similarity_outlet_options) >= 5 else similarity_outlet_options,
                key="deep_similarity_outlets",
            )
            if len(selected_similarity_outlets) < 2:
                st.info("Select at least two outlets to compute pairwise similarity.")
            else:
                similarity = fetch_topic_similarity(
                    level="outlet",
                    country=country,
                    partisan=partisan_filter,
                    outlets=selected_similarity_outlets,
                    date_from=date_from,
                    date_to=date_to,
                    limit_topics=12,
                )
                if similarity and similarity.get("entities"):
                    entities = [str(e) for e in similarity.get("entities", [])]
                    raw_records = similarity.get("cosine", [])
                    records = [
                        {
                            "entity_a": str(row.get("entity_a", "")),
                            "entity_b": str(row.get("entity_b", "")),
                            "value": float(row.get("value", 0.0)),
                        }
                        for row in raw_records
                    ]
                    matrix = _matrix_records_to_df(records, entities)
                    if not matrix.empty:
                        heatmap = go.Figure(
                            data=go.Heatmap(
                                z=matrix.values,
                                x=matrix.columns,
                                y=matrix.index,
                                colorscale="Blues",
                                zmin=0.5,
                                zmax=1.0,
                            )
                        )
                        heatmap.update_layout(
                            height=420,
                            xaxis_title="",
                            yaxis_title="",
                            margin=dict(t=20, b=20, l=20, r=20),
                        )
                        _plot(heatmap)
                    else:
                        st.info("No similarity matrix available for selected outlets.")
                else:
                    st.info("No similarity data available for selected outlets.")


def show_explorer_page() -> None:
    """Show comparative Explorer with explicit mode separation."""
    _inject_explorer_styles()

    analysis_bundle = fetch_analysis_bundle() or {}
    overview = analysis_bundle.get("overview") or fetch_overview()

    st.markdown('<h1 class="main-header">Overview</h1>', unsafe_allow_html=True)
    st.markdown(
        "<div class='subtle' style='font-size:1.05rem;'>Explore alternative news media landscapes across the Nordic region or focus on one country as a primary analytical workspace.</div>",
        unsafe_allow_html=True,
    )

    mode, selected_country = _render_country_view_selector()
    st.session_state["explorer_mode"] = mode
    if selected_country:
        st.session_state["quick_country"] = selected_country
        st.session_state["deep_country"] = selected_country
    else:
        st.session_state["quick_country"] = None
    if mode == MODE_COMPARE:
        _render_compare_mode(overview, analysis_bundle)
    else:
        _render_deep_dive_mode(overview)

    render_footer_bar()
