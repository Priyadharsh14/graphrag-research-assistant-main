"""
Shared visual styling and small UI helpers so every page looks consistent
and deliberately designed rather than default-Streamlit. Colors mirror the
React app's design tokens (indigo/graph + amber/citation), so the two
frontends feel like the same product.
"""
import streamlit as st

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --graph: #5B54E8;
    --graph-soft: #EBE9FD;
    --citation: #C08A2E;
    --citation-soft: #F7ECD6;
    --success: #3F8F5F;
    --success-soft: #E4F2E9;
    --danger: #C1483C;
    --danger-soft: #FBE9E6;
    --ink-soft: #565A6E;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important; }

/* Sidebar branding */
[data-testid="stSidebarNav"] { padding-top: 0.5rem; }

/* Card container helper */
.grc-card {
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    background: var(--background-color, inherit);
    margin-bottom: 0.75rem;
}

/* Badges */
.grc-badge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 999px; padding: 2px 10px; font-size: 0.75rem; font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
}
.grc-badge-graph { background: var(--graph-soft); color: var(--graph); }
.grc-badge-citation { background: var(--citation-soft); color: var(--citation); }
.grc-badge-success { background: var(--success-soft); color: var(--success); }
.grc-badge-danger { background: var(--danger-soft); color: var(--danger); }
.grc-badge-neutral { background: rgba(128,128,128,0.12); color: var(--ink-soft); }

/* Thread divider — signature motif echoing knowledge-graph edges */
.grc-thread {
    height: 1px; margin: 1rem 0;
    background-image: radial-gradient(circle, rgba(128,128,128,0.35) 1px, transparent 1.5px);
    background-size: 8px 1px; background-repeat: repeat-x;
}

.grc-empty {
    border: 1.5px dashed rgba(128,128,128,0.3); border-radius: 12px;
    padding: 2.5rem 1rem; text-align: center; color: var(--ink-soft);
}

/* Tighten default top padding */
.block-container { padding-top: 2.2rem; }

/* Mono for entity/citation identifiers */
.grc-mono { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: var(--ink-soft); }
</style>
"""


def inject_css() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="grc-badge grc-badge-{tone}">{text}</span>'


def thread_divider() -> None:
    st.markdown('<div class="grc-thread"></div>', unsafe_allow_html=True)


def empty_state(title: str, description: str) -> None:
    st.markdown(
        f'<div class="grc-empty"><b>{title}</b><br/>{description}</div>',
        unsafe_allow_html=True,
    )


STATUS_TONE = {
    "pending": "neutral", "parsing": "graph", "chunking": "graph", "embedding": "graph",
    "extracting_entities": "graph", "building_graph": "graph", "indexing_vectors": "graph",
    "completed": "success", "failed": "danger", "retrying": "graph",
}

STAGE_LABEL = {
    "pending": "Queued", "parsing": "Parsing PDF", "chunking": "Chunking",
    "embedding": "Generating embeddings", "extracting_entities": "Extracting entities",
    "building_graph": "Building graph", "indexing_vectors": "Indexing vectors",
    "completed": "Completed", "failed": "Failed", "retrying": "Retrying",
}
