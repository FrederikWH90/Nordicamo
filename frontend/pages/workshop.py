"""Guided research workflows with a bounded, metadata-only data preview."""

from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from pages.footer import render_footer_bar
from services.api import (
    fetch_articles,
    fetch_articles_over_time,
    fetch_categories,
    fetch_categories_over_time,
    fetch_overview,
    fetch_top_outlets,
)
from workshop_helpers import (
    MAX_BROWSER_PREVIEW_ROWS,
    WORKSHOP_PROJECTS,
    build_access_request_context,
    preview_records,
    project_by_key,
    safe_article_url,
)


COUNTRIES = ("denmark", "finland", "norway", "sweden")


def _year_bounds(overview: dict | None) -> tuple[int, int]:
    dates = (overview or {}).get("date_range") or {}
    earliest = str(dates.get("earliest") or "2016")[:4]
    latest = str(dates.get("latest") or "2026")[:4]
    try:
        return int(earliest), int(latest)
    except ValueError:
        return 2016, 2026


def _set_page(page: str) -> None:
    try:
        st.query_params["page"] = page
    except Exception:
        st.experimental_set_query_params(page=page)
    st.rerun()


def _render_project_selector(selected_key: str) -> str:
    st.markdown("<div class='section-title'>Choose a question to investigate</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for index, project in enumerate(WORKSHOP_PROJECTS):
        with cols[index % 2]:
            active = "workshop-card-active" if project.key == selected_key else ""
            st.markdown(
                f"""
                <div class='workshop-card {active}'>
                    <div class='workshop-card-title'>{html.escape(project.title)}</div>
                    <div class='workshop-card-question'>{html.escape(project.question)}</div>
                    <div class='workshop-card-body'>{html.escape(project.description)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Selected" if project.key == selected_key else "Open workshop",
                key=f"workshop_project_{project.key}",
                disabled=project.key == selected_key,
                use_container_width=True,
            ):
                st.session_state["workshop_project"] = project.key
                st.rerun()
    return st.session_state.get("workshop_project", selected_key)


def _outlet_options(country: str, date_from: str, date_to: str) -> list[str]:
    result = fetch_top_outlets(country=country, date_from=date_from, date_to=date_to, limit=60) or {}
    return [str(row.get("domain")) for row in result.get("data", []) if row.get("domain")]


def _article_preview(
    country: str,
    date_from: str,
    date_to: str,
    outlets: list[str],
    categories: list[str],
    keyword: str,
    preview_size: int,
) -> tuple[int | None, list[dict]]:
    result = fetch_articles(
        query=keyword or None,
        country=country,
        date_from=date_from,
        date_to=date_to,
        outlets=outlets or None,
        categories=categories or None,
        limit=preview_size,
        offset=0,
    )
    if result is None:
        return None, []
    return int(result.get("total") or 0), result.get("articles") or []


def _render_preview(total: int | None, articles: list[dict], label: str) -> None:
    st.markdown("<div class='section-title'>Data preview</div>", unsafe_allow_html=True)
    st.caption(
        f"{label}: showing at most {MAX_BROWSER_PREVIEW_ROWS} metadata records in the browser. "
        "This is a preview, not a public dataset download."
    )
    if total is None:
        st.warning("The preview could not be loaded. You can still request the selected dataset.")
        return
    if not articles:
        st.info("No indexed articles match this selection.")
        return
    st.markdown(f"**{total:,}** indexed articles match the selection.")
    records = preview_records(articles)
    headers = ["Date", "Country", "Outlet", "Orientation", "Categories", "Title", "Article URL"]
    body = []
    for record in records:
        cells = []
        for header in headers:
            value = str(record.get(header) or "")
            if header == "Article URL" and value:
                article_url = safe_article_url(value)
                if article_url:
                    safe_url = html.escape(article_url, quote=True)
                    cells.append(f"<td><a href='{safe_url}' target='_blank' rel='noopener'>Open article</a></td>")
                else:
                    cells.append("<td></td>")
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    st.markdown(
        "<div class='workshop-preview-table-wrap'><table class='workshop-preview-table'><thead><tr>"
        + header_html
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _render_method_note(project, countries, date_from, date_to, outlets, categories, keyword) -> None:
    with st.expander("Method and selection note", expanded=False):
        st.markdown(
            f"**Question:** {project.question}\n\n"
            f"**Countries:** {', '.join(country.capitalize() for country in countries)}  \n"
            f"**Period:** {date_from} to {date_to}  \n"
            f"**Outlets:** {', '.join(outlets) if outlets else 'All indexed outlets'}  \n"
            f"**Categories:** {', '.join(categories) if categories else 'All categories'}  \n"
            f"**Keyword:** {keyword or 'None'}\n\n"
            "Article previews are limited to the current filtered selection and show metadata only. "
            "Counts and charts should be read as descriptive evidence about the indexed collection."
        )


def _request_selection(project, countries, date_from, date_to, outlets, categories, keyword) -> None:
    if st.button("Prepare workshop request", type="primary"):
        request_context = build_access_request_context(
            project=project,
            countries=countries,
            date_from=date_from,
            date_to=date_to,
            outlets=outlets,
            categories=categories,
            keyword=keyword,
        )
        st.session_state["access_request_context"] = request_context
        st.session_state["access_request_draft"] = request_context
        _set_page("GetAccess")


def _render_project_chart(
    project_key: str,
    country: str,
    comparison_country: str,
    date_from: str,
    date_to: str,
    outlets: list[str],
    categories: list[str],
) -> None:
    if project_key == "compare_agendas":
        traces = []
        for selected_country in [country, comparison_country]:
            result = fetch_articles_over_time(
                country=selected_country,
                granularity="month",
                date_from=date_from,
                date_to=date_to,
            ) or {}
            for row in result.get("data", []):
                traces.append({**row, "country": selected_country.capitalize()})
        if traces:
            frame = pd.DataFrame(traces)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            fig = px.line(frame, x="date", y="count", color="country", markers=True)
            fig.update_layout(height=320, xaxis_title="Date", yaxis_title="Indexed articles", hovermode="x unified", font={"size": 11})
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
        else:
            st.info("No chart data is available for this selection.")
        return

    if project_key == "outlet_drivers":
        result = fetch_top_outlets(country=country, date_from=date_from, date_to=date_to, limit=12) or {}
        frame = pd.DataFrame(result.get("data", []))
        if not frame.empty and {"domain", "count"}.issubset(frame.columns):
            frame = frame.sort_values("count")
            fig = px.bar(frame, x="count", y="domain", orientation="h")
            fig.update_layout(height=320, xaxis_title="Indexed articles", yaxis_title="Outlet", font={"size": 11})
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
        else:
            st.info("No chart data is available for this selection.")
        return

    if project_key == "trace_topic":
        result = fetch_categories_over_time(
            country=country,
            outlets=outlets or None,
            granularity="month",
            date_from=date_from,
            date_to=date_to,
            limit=6,
        ) or {}
        frame = pd.DataFrame(result.get("data", []))
        if not frame.empty and {"date", "category", "count"}.issubset(frame.columns):
            if categories:
                frame = frame[frame["category"].isin(categories)]
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            fig = px.line(frame, x="date", y="count", color="category")
            fig.update_layout(height=320, xaxis_title="Date", yaxis_title="Indexed articles", hovermode="x unified", font={"size": 11})
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
        else:
            st.info("No chart data is available for this selection.")


def show_workshop_page() -> None:
    """Show starter projects, bounded data previews, and access handoff."""
    st.markdown('<h1 class="main-header">Research Workshop</h1>', unsafe_allow_html=True)
    st.markdown(
        "<div class='subtle' style='font-size:1.08rem;'>Start with a research question, inspect a bounded metadata preview, "
        "and request a documented dataset selection when you need to work beyond the browser.</div>",
        unsafe_allow_html=True,
    )

    default_key = st.session_state.get("workshop_project", WORKSHOP_PROJECTS[0].key)
    selected_key = _render_project_selector(default_key)
    project = project_by_key(selected_key)
    st.session_state["workshop_project"] = project.key

    overview = fetch_overview()
    year_min, year_max = _year_bounds(overview)
    default_start = max(year_min, year_max - 3)
    st.divider()
    st.markdown(f"<div class='section-title'>{html.escape(project.title)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='subtle'>{html.escape(project.question)}</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1.4])
    with c1:
        country = st.selectbox("Primary country", options=list(COUNTRIES), format_func=str.capitalize)
    with c2:
        comparison_country = country
        if project.key == "compare_agendas":
            comparison_country = st.selectbox(
                "Comparison country",
                options=[item for item in COUNTRIES if item != country],
                format_func=str.capitalize,
            )
        else:
            st.markdown("<div class='subtle' style='padding-top:32px;'>Use the selected country as the primary workspace.</div>", unsafe_allow_html=True)
    with c3:
        year_from, year_to = st.slider(
            "Period",
            min_value=year_min,
            max_value=year_max,
            value=(default_start, year_max),
            step=1,
        )
    date_from, date_to = f"{year_from}-01-01", f"{year_to}-12-31"

    outlet_options: list[str] = []
    if project.key in {"outlet_drivers", "trace_topic", "reporting_case"}:
        outlet_options = _outlet_options(country, date_from, date_to)
    selected_outlets: list[str] = []
    selected_categories: list[str] = []
    keyword = ""

    if project.key in {"outlet_drivers", "trace_topic", "reporting_case"}:
        selected_outlets = st.multiselect("Limit to outlets", options=outlet_options)
    if project.key == "trace_topic":
        category_result = fetch_categories(country=country) or {}
        category_options = [str(row.get("category")) for row in category_result.get("data", []) if row.get("category")]
        selected_categories = st.multiselect("Focus on categories", options=category_options[:20])
    if project.key == "reporting_case":
        keyword = st.text_input("Keyword", placeholder="e.g. migration, climate, Ukraine")

    st.markdown("<div class='section-title' style='margin-top:24px;'>Analysis</div>", unsafe_allow_html=True)
    if project.key == "reporting_case":
        st.caption("Use the preview below to identify a bounded set of article records for a case. No public dataset download is available.")
    else:
        _render_project_chart(
            project.key,
            country,
            comparison_country,
            date_from,
            date_to,
            selected_outlets,
            selected_categories,
        )

    preview_size = st.select_slider("Preview rows", options=[25, 50, 100], value=50)
    if project.key == "compare_agendas":
        first_limit = min(50, max(1, preview_size // 2))
        second_limit = min(50, preview_size - first_limit)
        first_total, first_articles = _article_preview(country, date_from, date_to, [], [], "", first_limit)
        second_total, second_articles = _article_preview(comparison_country, date_from, date_to, [], [], "", second_limit)
        combined_total = None if first_total is None or second_total is None else first_total + second_total
        _render_preview(
            combined_total,
            first_articles + second_articles,
            f"Combined preview for {country.capitalize()} and {comparison_country.capitalize()}",
        )
        selected_countries = [country, comparison_country]
    else:
        total, articles = _article_preview(
            country, date_from, date_to, selected_outlets, selected_categories, keyword, preview_size
        )
        _render_preview(total, articles, f"Filtered preview for {country.capitalize()}")
        selected_countries = [country]

    _render_method_note(
        project, selected_countries, date_from, date_to, selected_outlets, selected_categories, keyword
    )
    _request_selection(
        project, selected_countries, date_from, date_to, selected_outlets, selected_categories, keyword
    )
    if st.button("Back to Overview"):
        _set_page("Explorer")
    render_footer_bar()
