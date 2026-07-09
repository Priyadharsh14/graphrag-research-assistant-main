"""
GraphRAG Research Assistant — Streamlit frontend.

This app is a thin client over the same FastAPI + Celery + Neo4j + Qdrant
backend used by the React frontend; all ingestion, retrieval, and LLM logic
lives there. This file just wires up navigation and global page config.
"""
import streamlit as st

from style import inject_css

st.set_page_config(
    page_title="GraphRAG Research Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

pages = [
    st.Page("pages/01_upload_library.py", title="Upload & Library", default=True),
    st.Page("pages/02_research_chat.py", title="Research Chat"),
    st.Page("pages/03_literature_review.py", title="Literature Review"),
    st.Page("pages/04_paper_comparison.py", title="Paper Comparison"),
    st.Page("pages/05_gap_analysis.py", title="Research Gap Analysis"),
    st.Page("pages/10_settings.py", title="Settings"),
]

with st.sidebar:
    st.markdown(
        "<div style='padding:0.25rem 0 1rem 0;'>"
        "<b style='font-family:Space Grotesk,sans-serif;font-size:1.1rem;'>GraphRAG</b><br/>"
        "<span style='font-size:0.75rem;opacity:0.6;'>Research Assistant</span>"
        "</div>",
        unsafe_allow_html=True,
    )

nav = st.navigation(pages)
nav.run()
