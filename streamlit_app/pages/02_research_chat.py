import streamlit as st

from engine import api
from style import badge, empty_state, inject_css

inject_css()
st.title("Research Chat")
st.caption("Ask questions grounded in your paper library — every answer cites its source chunk.")

try:
    papers = api.list_papers_cached()
except Exception:
    papers = []
completed_papers = [p for p in papers if p["status"] == "completed"]

if completed_papers:
    options = {p["id"]: (p.get("title") or p["filename"]) for p in completed_papers}
    selected_ids = st.multiselect(
        "Scope to specific papers (optional — leave empty to search the whole library)",
        options=list(options.keys()),
        format_func=lambda pid: options[pid],
    )
else:
    selected_ids = []
    st.info("Upload and process at least one paper first, then come back here.")

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            badges = " ".join(
                badge(f"chunk {c.get('chunk_index', '?')} · p.{c.get('page', '?')}", "citation")
                for c in msg["citations"][:6]
            )
            st.markdown(badges, unsafe_allow_html=True)

if not st.session_state.chat_messages:
    empty_state(
        "Ask your first question",
        'Try: "What methods do these papers use to evaluate performance?"'
        if completed_papers else "Upload a paper to get started.",
    )

question = st.chat_input("Ask a question about your library...", disabled=not completed_papers)
if question:
    st.session_state.chat_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving from graph + vector index..."):
            try:
                result = api.ask_question(question, selected_ids or None)
                st.markdown(result["answer"])
                citations = result.get("citations", [])
                if citations:
                    badges = " ".join(
                        badge(f"chunk {c.get('chunk_index', '?')} · p.{c.get('page', '?')}", "citation")
                        for c in citations[:6]
                    )
                    st.markdown(badges, unsafe_allow_html=True)
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": result["answer"], "citations": citations}
                )
            except api.APIError as e:
                error_text = f"Sorry, I couldn't generate an answer: {e.detail}"
                st.error(error_text)
                st.session_state.chat_messages.append({"role": "assistant", "content": error_text})
