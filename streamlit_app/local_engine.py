"""
Standalone engine: runs the whole pipeline in-process for deployments where
the FastAPI/Celery/Neo4j/Qdrant backend isn't available (Streamlit Community
Cloud). Mirrors api_client.py's function signatures exactly so pages don't
know which mode they're in.

Tradeoffs vs. the full backend (deliberate, for free-tier hosting):
- No Neo4j: entities/relationships are extracted with the same batched LLM
  design as the backend, but held in memory per-paper. Retrieval still gets
  graph-style relationship context (the GraphRAG part), just not a queryable
  graph database.
- Papers are stored in st.session_state: per-browser-session, ephemeral.
- Processing is synchronous (no Celery) -- uploads block with a spinner.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

import numpy as np
import streamlit as st


class APIError(Exception):
    """Same shape as api_client.APIError so pages handle both modes identically."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


# --------------------------------------------------------------------------
# Configuration / model access
# --------------------------------------------------------------------------

GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_EXTRACTION_MODEL = "openai/gpt-oss-20b"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_EXTRACTION_MODEL = "gemini-3.5-flash-lite"
# Which provider to use is itself a secret/env var so a public deployment
# can be repointed without a code change -- set LLM_PROVIDER = "groq" to
# go back to Groq once it has a key again.
DEFAULT_PROVIDER = "gemini"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CHUNK_CHARS = 2000
OVERLAP_CHARS = 250
EXTRACTION_BATCH_SIZE = 8
MAX_EXTRACTION_CHUNKS = 60  # quota guard: cap extraction work per paper


def _get_secret(name: str) -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, "")


@st.cache_resource(show_spinner="Loading embedding model (first run only)...")
def _get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def _embed(texts: list[str]) -> np.ndarray:
    model = _get_embedder()
    return np.asarray(model.encode(texts, normalize_embeddings=True, show_progress_bar=False))


def _complete(system: str, user: str, max_tokens: int = 1500, temperature: float = 0.2,
              model: str | None = None, extraction: bool = False, json_mode: bool = False) -> str:
    provider = (_get_secret("LLM_PROVIDER") or DEFAULT_PROVIDER).lower()
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}

    if provider == "groq":
        key = _get_secret("GROQ_API_KEY")
        if not key:
            raise APIError(503, "GROQ_API_KEY is not configured. Add it in the app's secrets settings.")
        from groq import Groq
        client = Groq(api_key=key)
        resolved_model = model or (GROQ_EXTRACTION_MODEL if extraction else GROQ_MODEL)
    else:
        # Gemini via Google's OpenAI-compatible endpoint -- same `openai`
        # client either way, just a different base_url + key + model name.
        key = _get_secret("GEMINI_API_KEY")
        if not key:
            raise APIError(503, "GEMINI_API_KEY is not configured. Add it in the app's secrets settings.")
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=GEMINI_BASE_URL)
        resolved_model = model or (GEMINI_EXTRACTION_MODEL if extraction else GEMINI_MODEL)

    try:
        resp = client.chat.completions.create(
            model=resolved_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        message = str(exc)
        if "rate_limit" in message or "429" in message:
            raise APIError(429, "LLM rate limit reached. Wait for the quota to reset and try again.")
        raise APIError(502, f"LLM call failed: {message[:300]}")


# --------------------------------------------------------------------------
# In-session paper store
# --------------------------------------------------------------------------

def _store() -> dict:
    return st.session_state.setdefault("standalone_papers", {})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# PDF parsing / chunking (simplified port of the backend's pdf_processor)
# --------------------------------------------------------------------------

def _open_pdf(file_bytes: bytes):
    """PyMuPDF exposes its module as `fitz` in most versions but as `pymupdf`
    in some newer ones; import whichever is available so the app doesn't
    hard-fail on a naming difference in the deployed environment."""
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError:
        import pymupdf as fitz  # type: ignore
    return fitz.open(stream=file_bytes, filetype="pdf")


def _parse_pdf(file_bytes: bytes) -> tuple[list[tuple[int, str]], str | None]:
    doc = _open_pdf(file_bytes)
    pages = [(i + 1, page.get_text("text")) for i, page in enumerate(doc)]
    doc.close()

    title = None
    if pages:
        first_lines = [ln.strip() for ln in pages[0][1].splitlines() if ln.strip()]
        candidates = [
            ln for ln in first_lines[:8]
            if len(ln) > 15 and "@" not in ln and not ln.lower().startswith(("abstract", "http"))
        ]
        title = max(candidates, key=len) if candidates else (first_lines[0] if first_lines else None)
    return pages, title


def _chunk(pages: list[tuple[int, str]]) -> list[dict]:
    tagged = ""
    boundaries: list[tuple[int, int]] = []
    for page_num, text in pages:
        boundaries.append((len(tagged), page_num))
        tagged += text + "\n"

    chunks: list[dict] = []
    start, idx = 0, 0
    while start < len(tagged):
        end = min(start + CHUNK_CHARS, len(tagged))
        text = tagged[start:end].strip()
        if text:
            page = None
            for offset, pnum in boundaries:
                if offset <= start:
                    page = pnum
                else:
                    break
            chunks.append({"index": idx, "text": text, "page": page})
            idx += 1
        if end >= len(tagged):
            break
        start = end - OVERLAP_CHARS if end - OVERLAP_CHARS > start else end
    return chunks


# --------------------------------------------------------------------------
# Entity extraction (batched, quota-capped -- the GraphRAG part)
# --------------------------------------------------------------------------

_REFERENCE_LINES = re.compile(r"^\s*\[\d+\]|\(\d{4}\)\.|et al\.,", re.MULTILINE)
_REFERENCE_HEADING = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)

_EXTRACTION_PROMPT = """You are a precise information-extraction engine for academic research papers.
You will be given several numbered text chunks. For EACH chunk, extract named entities and
relationships mentioned in THAT chunk only.

Entity types: METHOD, MODEL, DATASET, METRIC, TASK, AUTHOR, ORGANIZATION, CONCEPT.
Relationship types: USES, PROPOSES, OUTPERFORMS, EVALUATED_ON, PART_OF, COMPARED_TO, EXTENDS, CITES.

Return ONLY valid JSON: one entry per chunk number (as strings), e.g.
{"0": {"entities": [{"name": str, "type": str}], "relationships": [{"source": str, "target": str, "relation": str}]}}
If a chunk has nothing relevant, use empty lists for it."""


def _is_reference_chunk(text: str) -> bool:
    """Reference lists are citation noise -- not worth extraction tokens."""
    if _REFERENCE_HEADING.search(text[:200]):
        return True
    hits = len(_REFERENCE_LINES.findall(text))
    return hits >= 4 and hits >= len(text) // 200


def _extract_entities(chunks: list[dict]) -> tuple[dict[int, list], list[dict]]:
    """Returns (chunk_index -> entities, flat relationship list). Every
    failure mode -- missing key, rate limit, malformed JSON -- degrades to
    empty results so extraction can never fail an upload; the paper still
    ingests and pure-vector retrieval still works."""
    eligible = [c for c in chunks if not _is_reference_chunk(c["text"])][:MAX_EXTRACTION_CHUNKS]
    per_chunk: dict[int, list] = {c["index"]: [] for c in chunks}
    relations: list[dict] = []

    for i in range(0, len(eligible), EXTRACTION_BATCH_SIZE):
        batch = eligible[i : i + EXTRACTION_BATCH_SIZE]
        numbered = "\n\n".join(f"=== CHUNK {c['index']} ===\n{c['text'][:3000]}" for c in batch)
        try:
            raw = _complete(_EXTRACTION_PROMPT, numbered, extraction=True,
                            json_mode=True, temperature=0.0,
                            max_tokens=400 * len(batch) + 200)
            parsed = json.loads(raw)
            for c in batch:
                entry = parsed.get(str(c["index"])) or {}
                per_chunk[c["index"]] = entry.get("entities", []) or []
                for rel in entry.get("relationships", []) or []:
                    if rel.get("source") and rel.get("target"):
                        relations.append({
                            "source": rel["source"], "target": rel["target"],
                            "relation": rel.get("relation", "RELATES_TO"),
                        })
        except (APIError, json.JSONDecodeError, TypeError):
            continue

    return per_chunk, relations


# --------------------------------------------------------------------------
# Public interface (mirrors api_client)
# --------------------------------------------------------------------------

def upload_paper(file_bytes: bytes, filename: str) -> dict:
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    for paper in _store().values():
        if paper["file_hash"] == file_hash:
            raise APIError(409, f"This paper was already uploaded (paper_id={paper['id']})")

    pages, title = _parse_pdf(file_bytes)
    chunks = _chunk(pages)
    if not chunks:
        raise APIError(400, "No extractable text found in PDF (possibly a scanned/image-only document)")

    vectors = _embed([c["text"] for c in chunks])
    entities_by_chunk, relations = _extract_entities(chunks)
    paper_id = str(uuid.uuid4())
    _store()[paper_id] = {
        "id": paper_id,
        "title": title,
        "authors": None,
        "abstract": None,
        "publication_year": None,
        "filename": filename,
        "file_hash": file_hash,
        "num_pages": len(pages),
        "num_chunks": len(chunks),
        "status": "completed",
        "created_at": _now(),
        "chunks": chunks,
        "vectors": vectors,
        "entities_by_chunk": entities_by_chunk,
        "relations": relations,
    }
    return {"paper_id": paper_id, "job_id": paper_id, "filename": filename,
            "message": "Processed in standalone mode."}


def list_papers() -> list[dict]:
    return [
        {k: v for k, v in paper.items() if k not in ("chunks", "vectors", "file_hash", "entities_by_chunk", "relations")}
        for paper in sorted(_store().values(), key=lambda p: p["created_at"], reverse=True)
    ]


def list_papers_cached() -> list[dict]:
    # No caching in standalone mode: the store is already in-memory and
    # session-local, so a cache would only risk staleness after uploads.
    return list_papers()


# The API-client mode wraps list_papers_cached with @st.cache_data, which
# exposes a .clear() method that pages call after an upload to invalidate the
# cache. Standalone mode has no cache, but pages call .clear() the same way,
# so attach a no-op .clear() here to keep the two modes interface-compatible.
list_papers_cached.clear = lambda: None  # type: ignore[attr-defined]


def get_paper(paper_id: str) -> dict:
    paper = _store().get(paper_id)
    if paper is None:
        raise APIError(404, "Paper not found")
    return {k: v for k, v in paper.items() if k not in ("chunks", "vectors", "file_hash", "entities_by_chunk", "relations")}


def get_job_status(job_id: str) -> dict:
    # Processing is synchronous in standalone mode, so any known id is done.
    if job_id not in _store():
        raise APIError(404, "Job not found")
    return {"id": job_id, "paper_id": job_id, "status": "completed", "current_stage": "Completed",
            "progress_pct": 100.0, "attempt": 1, "error_message": None,
            "created_at": _now(), "updated_at": _now()}


def delete_paper(paper_id: str) -> None:
    if paper_id not in _store():
        raise APIError(404, "Paper not found")
    del _store()[paper_id]


def retry_ingestion(paper_id: str) -> dict:
    raise APIError(400, "Retry is not applicable in standalone mode -- re-upload the file instead.")


# --------------------------------------------------------------------------
# Retrieval + LLM features
# --------------------------------------------------------------------------

def _search(query: str, paper_ids: list[str] | None, top_k: int) -> list[dict]:
    papers = [
        p for pid, p in _store().items()
        if (paper_ids is None or pid in paper_ids)
    ]
    if not papers:
        return []
    query_vec = _embed([query])[0]

    hits: list[dict] = []
    for paper in papers:
        scores = paper["vectors"] @ query_vec  # normalized -> cosine similarity
        for chunk, score in zip(paper["chunks"], scores):
            hits.append({
                "score": float(score), "paper_id": paper["id"], "text": chunk["text"],
                "chunk_index": chunk["index"], "page": chunk["page"],
                "entities": paper.get("entities_by_chunk", {}).get(chunk["index"], []),
                "relations": paper.get("relations", []),
            })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]


def _graph_context(hits: list[dict], max_lines: int = 40) -> str:
    """Relationship lines for entities the retrieved chunks actually mention —
    the in-memory stand-in for the backend's Neo4j neighborhood traversal."""
    mentioned = {e.get("name") for h in hits for e in h.get("entities", []) if e.get("name")}
    if not mentioned:
        return ""
    lines, seen = [], set()
    for h in hits:
        for rel in h.get("relations", []):
            key = (rel["source"], rel["relation"], rel["target"])
            if key in seen or not (rel["source"] in mentioned or rel["target"] in mentioned):
                continue
            seen.add(key)
            lines.append(f"- {rel['source']} --{rel['relation']}--> {rel['target']}")
            if len(lines) >= max_lines:
                break
    if not lines:
        return ""
    return "\n\nKNOWLEDGE GRAPH RELATIONSHIPS:\n" + "\n".join(lines)


ANSWER_SYSTEM_PROMPT = (
    "You are a rigorous research assistant answering questions about a corpus of academic papers "
    "using retrieved context. Rules: Answer ONLY from the provided context. If the context is "
    "insufficient, say so explicitly. Every factual claim must include an inline citation like "
    "[paper_id, chunk <n>]. Be precise and technical; do not pad with generic statements. "
    "If knowledge graph relationships are provided, use them to explain how concepts/methods relate."
)


def ask_question(question: str, paper_ids: list[str] | None = None) -> dict:
    hits = _search(question, paper_ids, top_k=8)
    if not hits:
        raise APIError(404, "No relevant content found. Upload and process a paper first.")
    context = "\n\n".join(
        f"[paper_id={h['paper_id']} chunk={h['chunk_index']} page={h['page']}]\n{h['text']}" for h in hits
    ) + _graph_context(hits)
    answer = _complete(ANSWER_SYSTEM_PROMPT, f"Question: {question}\n\nContext:\n{context}", max_tokens=1200)
    citations = [
        {"paper_id": h["paper_id"], "chunk_index": h["chunk_index"], "page": h["page"], "score": h["score"]}
        for h in hits
    ]
    return {"answer": answer, "citations": citations}


def literature_review(topic: str, paper_ids: list[str] | None = None) -> dict:
    hits = _search(topic, paper_ids, top_k=16)
    if not hits:
        raise APIError(404, "No relevant content found for this topic in the library")
    context = "\n\n".join(f"[paper_id={h['paper_id']} chunk={h['chunk_index']}]\n{h['text']}" for h in hits) + _graph_context(hits)
    system = (
        "You are an expert academic writer producing a structured literature review section. "
        "Organize by theme, note agreements/disagreements between sources, and cite [paper_id, chunk] inline."
    )
    review = _complete(system, f"Topic: {topic}\n\nSource material:\n{context}", max_tokens=2000)
    return {"topic": topic, "review": review}


def compare_papers(paper_ids: list[str], aspects: list[str] | None = None) -> dict:
    if len(paper_ids) < 2:
        raise APIError(400, "Provide at least 2 paper_ids to compare")
    titles = {}
    for pid in paper_ids:
        paper = _store().get(pid)
        if paper:
            titles[pid] = paper.get("title") or paper["filename"]
    aspects = aspects or ["methodology", "datasets", "key results", "limitations"]
    hits = _search(" ".join(aspects), paper_ids, top_k=20)
    context = "\n\n".join(f"[paper_id={h['paper_id']} chunk={h['chunk_index']}]\n{h['text']}" for h in hits) + _graph_context(hits)
    system = (
        "You are a research analyst. Produce a structured comparison table (in markdown) of the given papers "
        f"across these aspects: {', '.join(aspects)}. Then add a short synthesis of key differences. "
        "Cite paper_ids inline where relevant."
    )
    import json
    comparison = _complete(system, f"Papers: {json.dumps(titles)}\n\nSource material:\n{context}", max_tokens=2000)
    return {"papers": titles, "comparison": comparison}


def gap_analysis(paper_ids: list[str] | None = None, focus_area: str | None = None) -> dict:
    query = focus_area or "open problems, limitations, and future work"
    hits = _search(query, paper_ids, top_k=20)
    if not hits:
        raise APIError(404, "No relevant content found")
    context = "\n\n".join(f"[paper_id={h['paper_id']} chunk={h['chunk_index']}]\n{h['text']}" for h in hits) + _graph_context(hits)
    system = (
        "You are a research strategist. From the provided excerpts (limitations/future-work sections and "
        "general content), identify concrete, specific research gaps and promising future directions. "
        "Structure as a bullet list, each gap grounded in cited source material [paper_id, chunk]."
    )
    gaps = _complete(system, f"Focus area: {query}\n\nSource material:\n{context}", max_tokens=1800)
    return {"focus_area": query, "gaps": gaps}
