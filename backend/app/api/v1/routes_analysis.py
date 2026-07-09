"""
Higher-level research features built on top of the same GraphRAG primitives:
literature review synthesis, multi-paper comparison, gap analysis, citation
exploration, and export. Each composes vector+graph retrieval with a
purpose-built LLM prompt rather than introducing a separate pipeline.
"""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.logging import get_logger
from app.domain.models import Paper
from app.infrastructure.db import AsyncSessionLocal
from app.infrastructure.neo4j.client import neo4j_client
from app.infrastructure.qdrant.client import vector_store
from app.services.embeddings import embed_query
from app.services.entity_extraction import get_extraction_stats
from app.services.llm_client import LLMProviderError, get_llm_client

router = APIRouter(tags=["Research Analysis"])
logger = get_logger(__name__)


def _complete_or_503(llm, **kwargs) -> str:
    """Runs an LLM completion, converting provider-level failures (rate
    limits, quota, auth) into a 503 with a clear message rather than letting
    them surface as an opaque 500 Internal Server Error."""
    try:
        return llm.complete(**kwargs)
    except LLMProviderError as exc:
        raise HTTPException(503, str(exc)) from exc


class LitReviewRequest(BaseModel):
    topic: str
    paper_ids: list[str] | None = None


class ComparisonRequest(BaseModel):
    paper_ids: list[str]
    aspects: list[str] | None = None


class GapAnalysisRequest(BaseModel):
    paper_ids: list[str] | None = None
    focus_area: str | None = None


async def _gather_context(query: str, paper_ids: list[str] | None, top_k: int = 12) -> str:
    vec = embed_query(query)
    hits = await vector_store.search(vec, top_k=top_k, paper_ids=paper_ids)
    return "\n\n".join(f"[paper_id={h['paper_id']} chunk={h['chunk_index']}]\n{h['text']}" for h in hits)


async def _paper_titles(paper_ids: list[str]) -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Paper).where(Paper.id.in_(paper_ids)))
        return {p.id: (p.title or p.filename) for p in result.scalars().all()}


@router.post("/literature-review")
async def literature_review(request: LitReviewRequest):
    context = await _gather_context(request.topic, request.paper_ids, top_k=16)
    if not context:
        raise HTTPException(404, "No relevant content found for this topic in the library")
    llm = get_llm_client()
    system = (
        "You are an expert academic writer producing a structured literature review section. "
        "Organize by theme, note agreements/disagreements between sources, and cite [paper_id, chunk] inline."
    )
    answer = _complete_or_503(llm, system=system, user=f"Topic: {request.topic}\n\nSource material:\n{context}", max_tokens=2000)
    return {"topic": request.topic, "review": answer}


@router.post("/compare-papers")
async def compare_papers(request: ComparisonRequest):
    if len(request.paper_ids) < 2:
        raise HTTPException(400, "Provide at least 2 paper_ids to compare")
    titles = await _paper_titles(request.paper_ids)
    aspects = request.aspects or ["methodology", "datasets", "key results", "limitations"]
    context = await _gather_context(" ".join(aspects), request.paper_ids, top_k=20)
    llm = get_llm_client()
    system = (
        "You are a research analyst. Produce a structured comparison table (in markdown) of the given papers "
        f"across these aspects: {', '.join(aspects)}. Then add a short synthesis of key differences. "
        "Cite paper_ids inline where relevant."
    )
    user = f"Papers: {json.dumps(titles)}\n\nSource material:\n{context}"
    answer = _complete_or_503(llm, system=system, user=user, max_tokens=2000)
    return {"papers": titles, "comparison": answer}


@router.post("/gap-analysis")
async def gap_analysis(request: GapAnalysisRequest):
    query = request.focus_area or "open problems, limitations, and future work"
    context = await _gather_context(query, request.paper_ids, top_k=20)
    if not context:
        raise HTTPException(404, "No relevant content found")
    llm = get_llm_client()
    system = (
        "You are a research strategist. From the provided excerpts (limitations/future-work sections and "
        "general content), identify concrete, specific research gaps and promising future directions. "
        "Structure as a bullet list, each gap grounded in cited source material [paper_id, chunk]."
    )
    answer = _complete_or_503(llm, system=system, user=f"Focus area: {query}\n\nSource material:\n{context}", max_tokens=1800)
    return {"focus_area": query, "gaps": answer}


@router.get("/citations/{paper_id}")
async def citation_explorer(paper_id: str):
    """Returns the entity/relationship graph for a paper as a citation-style
    explorer: which concepts it relates to, and via what relations."""
    records = await neo4j_client.get_paper_graph(paper_id)
    entities = {}
    relations = []
    for rec in records:
        e = rec.get("e")
        if e and e.get("name"):
            entities[e["name"]] = e.get("type")
        r, e2 = rec.get("r"), rec.get("e2")
        if r and e2 and e2.get("name"):
            relations.append({"relation": r.get("type"), "target": e2["name"]})
    return {"paper_id": paper_id, "entities": entities, "relations": relations}


@router.get("/export/{paper_id}")
async def export_paper_data(paper_id: str, format: str = "json"):
    async with AsyncSessionLocal() as session:
        paper = await session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(404, "Paper not found")

    graph_data = await neo4j_client.get_paper_graph(paper_id)
    payload = {
        "paper": {
            "id": paper.id, "title": paper.title, "authors": paper.authors,
            "abstract": paper.abstract, "num_pages": paper.num_pages, "num_chunks": paper.num_chunks,
        },
        "graph_records": len(graph_data),
    }

    if format == "json":
        buf = io.StringIO(json.dumps(payload, indent=2, default=str))
        return StreamingResponse(iter([buf.getvalue()]), media_type="application/json",
                                  headers={"Content-Disposition": f"attachment; filename={paper_id}.json"})
    elif format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["field", "value"])
        for k, v in payload["paper"].items():
            writer.writerow([k, v])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                  headers={"Content-Disposition": f"attachment; filename={paper_id}.csv"})
    raise HTTPException(400, "format must be 'json' or 'csv'")


@router.get("/metrics/extraction-stats")
async def extraction_stats():
    """Cumulative entity-extraction efficiency stats: how many LLM calls
    were actually made vs. how many chunks were processed, broken down by
    what avoided a call (low-value filtering, exact-content caching)."""
    return await get_extraction_stats()
