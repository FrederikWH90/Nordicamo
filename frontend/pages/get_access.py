from __future__ import annotations

import streamlit as st

from pages.footer import render_footer_bar
from services.api import send_access_request

ACCESS_FEEDBACK_TEXT = (
    "You are also welcome to suggest platform features, outlet candidates for future "
    "observation, or other feedback that could strengthen Nordicamo as a research infrastructure."
)


def show_get_access_page() -> None:
    """Show contact form for data access requests."""
    st.markdown('<h1 class="main-header">Get Access</h1>', unsafe_allow_html=True)
    st.markdown(
        "<div class='subtle' style='font-size:1.08rem;'>Request current or historical Nordicamo data for research, journalism, or teaching. "
        "Please describe your purpose, the countries/outlets/time period you need, and the variables or article fields you expect to use.</div>",
        unsafe_allow_html=True,
    )
    request_context = st.session_state.get("access_request_context")
    if request_context:
        if "access_request_draft" not in st.session_state:
            st.session_state["access_request_draft"] = request_context
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='access-checklist'><strong>Prepared workshop request</strong><br/>"
            "Review and edit this text before sending your request.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='access-checklist'>
            <strong>Include this in your request</strong>
            <ul>
                <li>Research purpose and institutional affiliation.</li>
                <li>Countries, outlets, and time period needed.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    with st.form("access_request_form", clear_on_submit=True):
        name = st.text_input("Name")
        email = st.text_input("Email")
        message = st.text_area(
            "Request",
            key="access_request_draft",
            height=250 if request_context else 180,
            placeholder="Describe the research, journalism, or teaching purpose of your request.",
        )
        submitted = st.form_submit_button("Send access request")

    if submitted:
        if not name.strip() or not email.strip() or not message.strip():
            st.error("Please provide your name, email address, and request.")
        else:
            status = send_access_request(name.strip(), email.strip(), message.strip())
            if status == "sent":
                st.success("Request sent. We will reply to the email address you provided.")
                st.session_state.pop("access_request_context", None)
            elif status == "queued":
                st.success("Request received. We will reply to the email address you provided.")

    if request_context and st.button("Clear prepared selection"):
        st.session_state.pop("access_request_context", None)
        st.session_state.pop("access_request_draft", None)
        st.rerun()

    st.markdown(
        "<div class='about-card'><strong>Email:</strong> frmohe @ ruc.dk "
        "(Frederik Henriksen, postdoc in the AlterPublics research project)<br/>"
        f"<span class='subtle'>{ACCESS_FEEDBACK_TEXT}</span></div>",
        unsafe_allow_html=True,
    )
    render_footer_bar()
