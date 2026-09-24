"""Overview (landing) page layout."""

import html
from collections import deque

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import get_api_base_url
from overview_helpers import format_freshness, load_db_comparison
from ui_labels import AVG_ARTICLES_PER_OUTLET_LABEL
from services.api import (
    fetch_articles_over_time,
    fetch_landing_bundle,
    fetch_overview,
)
from pages.footer import render_footer_bar

API_BASE_URL = get_api_base_url()


def _build_ticker_sample(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    groups: dict[str, list[dict]] = {}
    for article in articles:
        domain = article.get("domain") or ""
        if not domain:
            continue
        groups.setdefault(domain, []).append(article)

    ordered_groups = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
    if not ordered_groups:
        return []

    max_outlets = 40
    per_outlet = 2
    queues: list[deque[dict]] = [
        deque(items[:per_outlet]) for _, items in ordered_groups[:max_outlets]
    ]
    sample: list[dict] = []
    last_domain = None
    next_start = 0

    while any(queues):
        pick_idx = None
        for offset in range(len(queues)):
            idx = (next_start + offset) % len(queues)
            queue = queues[idx]
            if queue and (queue[0].get("domain") or "") != last_domain:
                pick_idx = idx
                break
        if pick_idx is None:
            pick_idx = next((idx for idx, queue in enumerate(queues) if queue), None)
        if pick_idx is None:
            break
        article = queues[pick_idx].popleft()
        sample.append(article)
        last_domain = article.get("domain") or ""
        next_start = (pick_idx + 1) % len(queues)

    return sample


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


def _exclude_incomplete_current_month(
    frame: pd.DataFrame,
    granularity: str,
    today: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, bool]:
    """Hide the in-progress calendar month from monthly publication charts."""
    if frame.empty or granularity.lower() != "month" or "date" not in frame.columns:
        return frame, False

    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    current_month = (today or pd.Timestamp.today()).to_period("M")
    incomplete_mask = result["date"].dt.to_period("M") == current_month
    return result.loc[~incomplete_mask], bool(incomplete_mask.any())


def show_overview_page() -> None:
    """Show overview dashboard page."""
    landing = fetch_landing_bundle() or {}
    overview = landing.get("overview") or fetch_overview()
    freshness = landing.get("freshness")
    kpi_source = overview

    def render_kpi(label: str, value: str, subtitle: str | None = None) -> None:
        subtitle_html = (
            f'<div style="font-size:11px; color: var(--color-text-muted); margin-top:4px;">{subtitle}</div>'
            if subtitle
            else ""
        )
        st.markdown(
            f"""
            <div class="landing-kpi">
                <div class="landing-kpi-label">{label}</div>
                <div class="landing-kpi-value">{value}</div>
                {subtitle_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    def render_kpis() -> None:
        if not kpi_source:
            return

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            total_articles = kpi_source.get("total_articles", 0)
            render_kpi("Total articles", f"{total_articles:,}")
        with k2:
            total_outlets = kpi_source.get("total_outlets", 0)
            render_kpi("Outlets", f"{total_outlets:,}")
        with k3:
            avg_per_outlet = kpi_source.get("avg_articles_per_outlet", 0)
            render_kpi(AVG_ARTICLES_PER_OUTLET_LABEL, f"{avg_per_outlet:,.0f}")
        with k4:
            coverage_years = kpi_source.get("coverage_years")
            if coverage_years:
                try:
                    start_year, end_year = coverage_years.split("-", 1)
                    coverage_years = f"{max(int(start_year), 2006)}-{end_year}"
                except ValueError:
                    pass
            else:
                date_range = overview.get("date_range", {}) if overview else {}
                earliest = date_range.get("earliest") or "N/A"
                latest = date_range.get("latest") or "N/A"
                try:
                    coverage_years = f"{max(int(str(earliest)[:4]), 2006)}-{str(latest)[:4]}"
                except (TypeError, ValueError):
                    coverage_years = "N/A"
            render_kpi("Coverage", str(coverage_years))
        with k5:
            growth_rate = kpi_source.get("growth_rate_per_year")
            if growth_rate:
                growth_display = f"+{growth_rate:,.0f}" if growth_rate > 0 else f"{growth_rate:,.0f}"
                render_kpi("Growth rate", growth_display, "articles/year")
            else:
                render_kpi("Countries", f"{len((overview or {}).get('by_country', {}))}")

    articles = _build_ticker_sample(landing.get("latest_articles", []) or [])
    if articles:
        ticker_items = []
        for article in articles:
            domain = article.get("domain") or "Unknown outlet"
            title = article.get("title") or "Untitled"
            date = (article.get("date") or "")[:10]
            url = article.get("url")
            title_html = html.escape(title)
            if url:
                title_html = (
                    f"<a href='{html.escape(str(url), quote=True)}' "
                    f"target='_blank' rel='noopener noreferrer'>{title_html}</a>"
                )
            item = f"<strong>{html.escape(domain)}</strong> — {title_html} ({html.escape(date)})"
            ticker_items.append(f"<span class='news-ticker-item'>{item}</span>")
        ticker_html = "".join(ticker_items)
        item_count = len(ticker_items)
        duration = max(75, min(210, item_count * 5))
        st.markdown(
            f"""
            <div class="news-ticker">
                <div class="news-ticker-label">Latest</div>
                <div class="news-ticker-track">
                    <div class="news-ticker-items" style="--ticker-duration: {duration}s">{ticker_html}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_kpis()
    st.markdown("<div class='landing-kpi-divider'></div>", unsafe_allow_html=True)

    hero_left, hero_right = st.columns([2.3, 1.2])
    with hero_left:
        st.markdown(
            "<div class='section-title landing-about-title'>About the Observatory</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='subtle' style='color:#111111;font-size:1.14rem;line-height:1.65;'><strong>Nordic Alternative Media Observatory (Nordicamo)</strong> is a comparative research platform for studying "
            "alternative news media across the continental Nordic region (currently <strong>Denmark, Finland, Norway, and Sweden</strong>). "
            "It tracks articles from active alternative news media, connecting current observation with a growing historical archive. "
            "The platform supports cross-national comparison, outlet-level investigation, and transparent development of research cases.</div>",
            unsafe_allow_html=True,
        )
    with hero_right:
        if freshness:
            freshness_text, last_article_formatted = format_freshness(freshness)
            status_body = (
                f"<div class='subtle' style='margin-top:8px;'>{freshness_text}<br/>"
                f"Last article: {last_article_formatted}</div>"
            )
        else:
            status_body = "<div class='subtle' style='margin-top:8px;'>Freshness data unavailable</div>"

        st.markdown(
            f"""
                <aside class='observatory-status'>
                    <div class='chip'><span class='pulse'></span> Observation active</div>
                    {status_body}
                </aside>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <section class='research-actions' aria-label='Research actions'>
            <div class='research-actions-intro'>
                <div class='research-actions-kicker'>Research pathways</div>
            </div>
            <div class='research-actions-grid'>{_research_action_items()}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    if not overview:
        st.error("Unable to load data. Please check API connection.")
        st.info(f"Trying to connect to: {API_BASE_URL}")
        return

    st.divider()

    st.subheader("Articles Over Time")

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
    if year_min < 2006:
        year_min = 2006

    default_start = 2021 if year_min <= 2021 <= year_max else year_min
    year_from, year_to = st.slider(
        "Year range",
        min_value=year_min,
        max_value=year_max,
        value=(default_start, year_max),
        step=1,
        key="ov_year_range",
    )
    date_from = f"{year_from}-01-01"
    date_to = f"{year_to}-12-31"

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_country = st.selectbox(
            "Filter by Country",
            options=[None, "denmark", "sweden", "norway", "finland"],
            format_func=lambda x: "All Countries" if x is None else x.capitalize(),
            help="Select a specific Nordic country or view all countries together",
        )
    with col2:
        selected_partisan = st.selectbox(
            "Filter by Partisan",
            options=[None, "Right", "Left", "Other"],
            format_func=lambda x: "All" if x is None else x,
            help="Political orientation of the media outlet (self-identified or classified)",
        )
    with col3:
        granularity = st.selectbox(
            "Time Granularity",
            options=["Year", "Month", "Week"],
            index=1,
            help="Time period grouping for the time series chart (year, month, or week)",
        )

    bundled_time = landing.get("articles_over_time") if landing else None
    can_use_bundled_time = (
        bundled_time
        and not selected_country
        and not selected_partisan
        and granularity == "Month"
        and str(date_from) == bundled_time.get("filters", {}).get("date_from")
        and str(date_to) == bundled_time.get("filters", {}).get("date_to")
    )

    if not selected_country:
        fig = go.Figure()
        incomplete_month_hidden = False
        countries = ["denmark", "sweden", "norway", "finland"]
        colors = {
            "denmark": "#C8102E",
            "sweden": "#FECC00",
            "norway": "#87CEEB",
            "finland": "#003580",
        }

        if can_use_bundled_time:
            bundled_rows = pd.DataFrame(bundled_time.get("data", []))
            country_time_data = {
                country: {"data": bundled_rows[bundled_rows["country"] == country].to_dict("records")}
                for country in countries
                if not bundled_rows.empty
            }
        else:
            country_time_data = {
                country: fetch_articles_over_time(
                    country=country,
                    partisan=selected_partisan,
                    granularity=granularity.lower(),
                    date_from=str(date_from) if date_from else None,
                    date_to=str(date_to) if date_to else None,
                )
                for country in countries
            }

        for country, time_data in country_time_data.items():
            if time_data and time_data.get("data"):
                df_time = pd.DataFrame(time_data["data"])
                df_time["date"] = pd.to_datetime(df_time["date"], errors="coerce")
                df_time = df_time.sort_values("date")
                df_time, hidden_for_country = _exclude_incomplete_current_month(df_time, granularity)
                incomplete_month_hidden = incomplete_month_hidden or hidden_for_country

                fig.add_trace(
                    go.Scatter(
                        x=df_time["date"],
                        y=df_time["count"],
                        mode="lines+markers",
                        name=country.capitalize(),
                        line=dict(color=colors.get(country, "#808080"), width=2),
                        marker=dict(size=6),
                        hovertemplate=(
                            f"<b>{country.capitalize()}</b><br>Date: %{{x}}<br>Articles: %{{y:,}}<extra></extra>"
                        ),
                    )
                )

        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Number of Articles",
            height=320,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=12),
            ),
            margin=dict(b=42, t=38, l=42, r=18),
            font=dict(size=11),
        )
        st.plotly_chart(fig, use_container_width=True)
        if incomplete_month_hidden:
            st.caption("The current calendar month is excluded because article collection is still in progress.")
    else:
        time_data = fetch_articles_over_time(
            country=selected_country,
            partisan=selected_partisan,
            granularity=granularity.lower(),
            date_from=str(date_from) if date_from else None,
            date_to=str(date_to) if date_to else None,
        )

        if time_data and time_data.get("data"):
            df_time = pd.DataFrame(time_data["data"])
            df_time["date"] = pd.to_datetime(df_time["date"], errors="coerce")
            df_time = df_time.sort_values("date")
            df_time, incomplete_month_hidden = _exclude_incomplete_current_month(df_time, granularity)

            fig = px.line(
                df_time,
                x="date",
                y="count",
                markers=True,
            )
            fig.update_traces(
                line=dict(width=3),
                marker=dict(size=8),
                hovertemplate="<b>Date:</b> %{x}<br><b>Articles:</b> %{y:,}<extra></extra>",
            )
            fig.update_layout(
                xaxis_title="Time",
                yaxis_title="Number of Articles",
                height=320,
                hovermode="x unified",
                margin=dict(b=42, t=30, l=42, r=18),
                font=dict(size=11),
            )
            st.plotly_chart(fig, use_container_width=True)
            if incomplete_month_hidden:
                st.caption("The current calendar month is excluded because article collection is still in progress.")
        else:
            st.info("No data available for selected filters.")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    render_footer_bar()
