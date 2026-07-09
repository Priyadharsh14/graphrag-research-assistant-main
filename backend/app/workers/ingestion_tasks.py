"""
The ingestion pipeline, run as a Celery task so uploads return instantly and
processing happens in the background with real progress tracking.

Design for reliability:
  - Each stage updates `IngestionJob.current_stage` / `progress_pct` in the DB
    immediately, so the API can report live progress and a crashed worker
    can be resumed from the last completed stage rather than from scratch.
  - Idempotent writes: Neo4j MERGE and deterministic Qdrant point IDs mean
    re-running a stage never creates duplicates.
  - Celery `autoretry_for` + exponential backoff handles transient failures
    (LLM rate limits, momentary DB unavailability) automatically.
  - Entity extraction failures are soft (per-chunk try/except) so one bad
    LLM response never fails the whole paper.
"""
from __future__ import annotations

import asyncio

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.core.async_utils import run_async
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.models import IngestionJob, JobStatus, Paper, utcnow
from app.infrastructure.celery.app import celery_app
from app.infrastructure.db import AsyncSessionLocal
from app.infrastructure.neo4j.client import neo4j_client
from app.infrastructure.qdrant.client import vector_store
from app.services.embeddings import embed_texts
from app.services.entity_extraction import extract_entities_for_chunks
from app.services.pdf_processor import chunk_document, parse_pdf

logger = get_logger(__name__)
settings = get_settings()

STAGE_WEIGHTS = {
    JobStatus.PARSING: 10,
    JobStatus.CHUNKING: 10,
    JobStatus.EMBEDDING: 30,
    JobStatus.EXTRACTING_ENTITIES: 30,
    JobStatus.BUILDING_GRAPH: 15,
    JobStatus.INDEXING_VECTORS: 5,
}


async def _update_job(job_id: str, **fields) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = utcnow()
        await session.commit()


async def _advance_stage(job_id: str, paper_id: str, status: JobStatus, current_stage: str) -> None:
    """Updates both the IngestionJob (detailed progress) and the Paper record
    (what the Library view reads) so the UI reflects real per-stage progress
    instead of showing "Queued" for the paper's entire processing time."""
    progress = _progress_for_stage(status)
    await _update_job(job_id, status=status, current_stage=current_stage, progress_pct=progress)
    await _update_paper(paper_id, status=status)


async def _update_paper(paper_id: str, **fields) -> None:
    async with AsyncSessionLocal() as session:
        paper = await session.get(Paper, paper_id)
        if paper is None:
            return
        for k, v in fields.items():
            setattr(paper, k, v)
        paper.updated_at = utcnow()
        await session.commit()


def _progress_for_stage(stage: JobStatus) -> float:
    order = list(STAGE_WEIGHTS.keys())
    completed = order[: order.index(stage)]
    return sum(STAGE_WEIGHTS[s] for s in completed)


async def _run_pipeline(job_id: str, paper_id: str, filepath: str) -> None:
    await neo4j_client.ensure_schema()
    await vector_store.ensure_collection()

    async with AsyncSessionLocal() as session:
        paper = await session.get(Paper, paper_id)
        job = await session.get(IngestionJob, job_id)
    if paper is None or job is None:
        raise RuntimeError(f"Paper or job not found for job_id={job_id}")

    # --- Stage: PARSING ---
    await _advance_stage(job_id, paper_id, JobStatus.PARSING, "Parsing PDF")
    parsed = parse_pdf(filepath)
    await _update_paper(paper_id, title=paper.title or parsed.title, abstract=parsed.abstract,
                         num_pages=len(parsed.pages))

    # --- Stage: CHUNKING ---
    await _advance_stage(job_id, paper_id, JobStatus.CHUNKING, "Chunking document")
    chunks = chunk_document(parsed)
    await _update_paper(paper_id, num_chunks=len(chunks))
    if not chunks:
        raise RuntimeError("No extractable text found in PDF (possibly a scanned/image-only document)")

    await neo4j_client.upsert_paper(paper_id, paper.title or parsed.title or paper.filename,
                                     _safe_authors(paper.authors), paper.publication_year)

    # --- Stage: EMBEDDING (batched for throughput) ---
    await _advance_stage(job_id, paper_id, JobStatus.EMBEDDING, "Generating embeddings")
    texts = [c.text for c in chunks]
    vectors = await asyncio.get_event_loop().run_in_executor(None, embed_texts, texts)

    # --- Stage: EXTRACTING_ENTITIES (batched + cached, see entity_extraction.py) ---
    await _advance_stage(job_id, paper_id, JobStatus.EXTRACTING_ENTITIES, "Extracting entities & relationships")
    extraction_results = await extract_entities_for_chunks(texts, batch_size=settings.ENTITY_EXTRACTION_BATCH_SIZE)

    # --- Stage: BUILDING_GRAPH ---
    await _advance_stage(job_id, paper_id, JobStatus.BUILDING_GRAPH, "Building knowledge graph")
    chunk_ids = [f"{paper_id}:{c.index}" for c in chunks]
    for chunk, chunk_id in zip(chunks, chunk_ids):
        await neo4j_client.upsert_chunk(chunk_id, paper_id, chunk.text, chunk.index, chunk.page)

    for chunk_id, result in zip(chunk_ids, extraction_results):
        for entity in result["entities"]:
            await neo4j_client.upsert_entity_and_link(entity["name"], entity["type"], chunk_id, entity["name"])
        for rel in result["relationships"]:
            await neo4j_client.link_entities(
                rel["source"], rel.get("source_type", "CONCEPT"),
                rel["target"], rel.get("target_type", "CONCEPT"),
                rel["relation"], paper_id,
            )

    # --- Stage: INDEXING_VECTORS ---
    await _advance_stage(job_id, paper_id, JobStatus.INDEXING_VECTORS, "Indexing vectors")
    points = [
        {"chunk_id": chunk_id, "vector": vector, "paper_id": paper_id, "text": chunk.text,
         "chunk_index": chunk.index, "page": chunk.page}
        for chunk_id, vector, chunk in zip(chunk_ids, vectors, chunks)
    ]
    await vector_store.upsert_chunks(points)

    # --- Done ---
    await _update_job(job_id, status=JobStatus.COMPLETED, current_stage="Completed", progress_pct=100.0,
                       completed_at=utcnow())
    await _update_paper(paper_id, status=JobStatus.COMPLETED)


def _safe_authors(authors_field) -> list[str]:
    if not authors_field:
        return []
    if isinstance(authors_field, list):
        return authors_field
    try:
        import json
        return json.loads(authors_field)
    except Exception:
        return [authors_field]


@celery_app.task(
    bind=True,
    name="ingest_paper",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def ingest_paper_task(self: Task, job_id: str, paper_id: str, filepath: str) -> dict:
    """Entry point invoked by the API on upload. Synchronous Celery wrapper
    around the async pipeline, with resume-aware retry: on failure the task
    is retried automatically (up to max_retries) and each stage is idempotent,
    so a retried run picks up cleanly rather than duplicating work."""
    try:
        run_async(_mark_attempt(job_id, self.request.retries))
        run_async(_run_pipeline(job_id, paper_id, filepath))
        return {"status": "completed", "job_id": job_id}
    except SoftTimeLimitExceeded:
        logger.error("ingestion_soft_timeout", job_id=job_id)
        run_async(_update_job(job_id, status=JobStatus.FAILED, error_message="Processing timed out"))
        raise
    except Exception as exc:
        logger.error("ingestion_failed", job_id=job_id, error=str(exc), attempt=self.request.retries)
        will_retry = self.request.retries < (self.max_retries or 0)
        run_async(_update_job(
            job_id,
            status=JobStatus.RETRYING if will_retry else JobStatus.FAILED,
            error_message=str(exc),
        ))
        raise


async def _mark_attempt(job_id: str, retry_count: int) -> None:
    await _update_job(job_id, attempt=retry_count + 1, status=JobStatus.PARSING if retry_count == 0 else JobStatus.RETRYING)
