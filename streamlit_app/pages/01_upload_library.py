import time

import streamlit as st

from engine import api, is_standalone
from style import STAGE_LABEL, STATUS_TONE, badge, empty_state, inject_css

inject_css()
st.title("Upload & Library")
if is_standalone():
    st.caption("Drop in research PDFs — parsing, embedding, and entity extraction run in this session. Papers last for this browser session only.")
else:
    st.caption("Drop in research PDFs — parsing, chunking, embedding, and knowledge-graph construction all run in the background.")

uploaded_files = st.file_uploader(
    "Drop PDF papers here, or click to browse",
    type=["pdf"],
    accept_multiple_files=True,
    help="Processing starts immediately in the background — you can keep working while it runs.",
)

if uploaded_files:
    for f in uploaded_files:
        key = f"uploaded_{f.name}_{f.size}"
        if st.session_state.get(key):
            continue
        try:
            spinner_text = (
                f"Processing {f.name} (parsing, embedding, extracting entities) — this can take a minute..."
                if is_standalone() else f"Uploading {f.name}..."
            )
            with st.spinner(spinner_text):
                result = api.upload_paper(f.getvalue(), f.name)
            st.session_state[key] = True
            api.list_papers_cached.clear()
            st.toast(f"'{f.name}' uploaded — processing started.")
        except api.APIError as e:
            if e.status_code == 409:
                st.session_state[key] = True
                st.toast(f"'{f.name}' was already uploaded.")
            else:
                st.error(f"Failed to upload {f.name}: {e.detail}")

st.divider()


@st.fragment(run_every=3)
def render_library():
    st.subheader("Library")
    try:
        papers = api.list_papers()
    except api.APIError as e:
        st.error(f"Could not load papers: {e.detail}")
        return
    except Exception:
        st.error("Could not reach the API. Is the backend running?")
        return

    if not papers:
        empty_state("No papers yet", "Upload a PDF above to start building your knowledge graph.")
        return

    for paper in papers:
        with st.container(border=True):
            cols = st.columns([5, 2, 2, 1, 1])
            with cols[0]:
                st.markdown(f"**{paper.get('title') or paper['filename']}**")
                pages_n = paper.get("num_pages") or "—"
                chunks_n = paper.get("num_chunks") or "—"
                st.markdown(
                    f'<span class="grc-mono">{pages_n} pages · {chunks_n} chunks</span>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                status = paper["status"]
                st.markdown(badge(STAGE_LABEL.get(status, status), STATUS_TONE.get(status, "neutral")),
                            unsafe_allow_html=True)
            with cols[2]:
                if status not in ("completed", "failed", "pending"):
                    st.progress(0.5, text="Processing...")
            with cols[3]:
                if status == "failed":
                    if st.button("Retry", key=f"retry_{paper['id']}", width='stretch'):
                        try:
                            api.retry_ingestion(paper["id"])
                            st.toast("Retry started.")
                            st.rerun()
                        except api.APIError as e:
                            st.error(f"Retry failed: {e.detail}")
            with cols[4]:
                if st.button("Delete", key=f"delete_{paper['id']}", help="Delete paper", width='stretch'):
                    try:
                        api.delete_paper(paper["id"])
                        st.toast(f"Deleted '{paper.get('title') or paper['filename']}'.")
                        st.rerun()
                    except api.APIError as e:
                        st.error(f"Delete failed: {e.detail}")


render_library()
