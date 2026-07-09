import os

import streamlit as st

from engine import is_standalone
from style import inject_css

inject_css()
st.title("Settings")
st.caption("Appearance and runtime information for this app.")

with st.container(border=True):
    st.subheader("Runtime mode")
    if is_standalone():
        st.markdown(
            "**Standalone mode.** Parsing, embedding, entity extraction, and retrieval all run "
            "inside this Streamlit process. Papers live in your browser session only and are "
            "gone when the session ends. Uploads process synchronously."
        )
    else:
        st.markdown(
            "**Full backend mode.** This app is a client for the FastAPI + Celery + Neo4j + Qdrant "
            "backend; uploads process in the background with retry support and persist across sessions."
        )
        st.code(os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1"), language="text")

with st.container(border=True):
    st.subheader("Appearance")
    st.markdown(
        "Streamlit's built-in theme switcher covers Light, Dark, and system-matching themes. "
        "Open the menu in the top-right corner of the page, choose Settings, then pick a theme."
    )
