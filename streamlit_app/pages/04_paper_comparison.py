import streamlit as st

from engine import api
from docx_export import markdown_to_docx_bytes
from style import empty_state, inject_css

inject_css()
st.title("Paper Comparison")
st.caption("Select two or more papers to generate a structured, aspect-by-aspect comparison.")

try:
    papers = api.list_papers_cached()
except Exception:
    papers = []
completed_papers = [p for p in papers if p["status"] == "completed"]
options = {p["id"]: (p.get("title") or p["filename"]) for p in completed_papers}

selected_ids = st.multiselect(
    "Papers to compare", options=list(options.keys()), format_func=lambda pid: options[pid]
)

default_aspects = ["methodology", "datasets", "key results", "limitations"]
aspects = st.multiselect("Comparison aspects", options=default_aspects, default=default_aspects)

if len(selected_ids) < 2:
    st.caption("Select at least 2 papers to compare.")

if st.button("Compare Papers", type="primary", disabled=len(selected_ids) < 2):
    with st.spinner(f"Comparing {len(selected_ids)} papers..."):
        try:
            result = api.compare_papers(selected_ids, aspects)
            st.session_state["comparison_result"] = result
        except api.APIError as e:
            st.error(f"Comparison failed: {e.detail}")

if "comparison_result" in st.session_state:
    st.divider()
    result = st.session_state["comparison_result"]
    st.markdown(result["comparison"])

    paper_titles = ", ".join(result.get("papers", {}).values()) if result.get("papers") else "Selected papers"
    docx_bytes = markdown_to_docx_bytes(
        title="Paper Comparison",
        markdown_text=result["comparison"],
        subtitle=f"Papers: {paper_titles[:200]}",
    )
    st.download_button(
        "Download as Word document",
        data=docx_bytes,
        file_name="paper-comparison.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
elif len(selected_ids) < 2:
    empty_state("Pick papers to compare", "Choose two or more processed papers above, then run the comparison.")
