import streamlit as st

from engine import api
from style import empty_state, inject_css

inject_css()
st.title("Research Gap Analysis")
st.caption("Surface concrete, source-grounded gaps and promising future directions from your library.")

try:
    papers = api.list_papers_cached()
except Exception:
    papers = []
completed_papers = [p for p in papers if p["status"] == "completed"]
options = {p["id"]: (p.get("title") or p["filename"]) for p in completed_papers}

focus_area = st.text_input(
    "Focus area (optional)",
    placeholder="Leave blank to scan for open problems and future-work sections across all papers",
)
selected_ids = st.multiselect(
    "Scope (optional)", options=list(options.keys()), format_func=lambda pid: options[pid]
)

if st.button("Analyze Gaps", type="primary", disabled=not completed_papers):
    with st.spinner("Scanning for research gaps..."):
        try:
            result = api.gap_analysis(selected_ids or None, focus_area or None)
            st.session_state["gap_result"] = result
        except api.APIError as e:
            st.error(f"Couldn't analyze gaps: {e.detail}")

if "gap_result" in st.session_state:
    st.divider()
    st.markdown(st.session_state["gap_result"]["gaps"])
elif not completed_papers:
    empty_state("No processed papers yet", "Upload and process a paper first, then come back here.")
