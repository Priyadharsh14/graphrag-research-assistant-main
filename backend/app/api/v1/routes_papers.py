"""Upload & Library endpoints: fast accept-and-background-process upload,
job/progress polling, paper listing, and deletion (with graph+vector cleanup)."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.v1.schemas import JobOut, PaperOut, UploadResponse
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.models import IngestionJob, JobStatus, Paper
from app.infrastructure.db import AsyncSessionLocal
from app.infrastructure.neo4j.client import neo4j_client
from app.infrastructure.qdrant.client import vector_store
from app.services.pdf_processor import file_sha256
from app.workers.ingestion_tasks import ingest_paper_task

router = APIRouter(prefix="/papers", tags=["Upload & Library"])
logger = get_logger(__name__)
settings = get_settings()


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_paper(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    paper_id = str(uuid.uuid4())
    dest_path = os.path.join(settings.UPLOAD_DIR, f"{paper_id}.pdf")

    size = 0
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                os.remove(dest_path)
                raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")
            out.write(chunk)

    file_hash = file_sha256(dest_path)

    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(Paper).where(Paper.file_hash == file_hash))).scalar_one_or_none()
        if existing:
            os.remove(dest_path)
            raise HTTPException(409, detail=f"This paper was already uploaded (paper_id={existing.id})")

        paper = Paper(
            id=paper_id, filename=file.filename, filepath=dest_path, file_hash=file_hash,
            status=JobStatus.PENDING,
        )
        session.add(paper)
        job = IngestionJob(paper_id=paper_id, status=JobStatus.PENDING, max_attempts=settings.INGEST_MAX_RETRIES)
        session.add(job)
        await session.commit()
        job_id = job.id

    task = ingest_paper_task.delay(job_id, paper_id, dest_path)
    async with AsyncSessionLocal() as session:
        db_job = await session.get(IngestionJob, job_id)
        db_job.celery_task_id = task.id
        await session.commit()

    logger.info("upload_accepted", paper_id=paper_id, job_id=job_id, filename=file.filename)
    return UploadResponse(paper_id=paper_id, job_id=job_id, filename=file.filename)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job_status(job_id: str) -> JobOut:
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return JobOut.model_validate(job)


@router.get("", response_model=list[PaperOut])
async def list_papers(skip: int = 0, limit: int = 50) -> list[PaperOut]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Paper).order_by(Paper.created_at.desc()).offset(skip).limit(limit))
        return [PaperOut.model_validate(p) for p in result.scalars().all()]


@router.get("/{paper_id}", response_model=PaperOut)
async def get_paper(paper_id: str) -> PaperOut:
    async with AsyncSessionLocal() as session:
        paper = await session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(404, "Paper not found")
        return PaperOut.model_validate(paper)


@router.delete("/{paper_id}", status_code=204, response_model=None)
async def delete_paper(paper_id: str) -> None:
    async with AsyncSessionLocal() as session:
        paper = await session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(404, "Paper not found")
        filepath = paper.filepath
        await session.delete(paper)
        await session.commit()

    await neo4j_client.delete_paper(paper_id)
    await vector_store.delete_paper(paper_id)
    if filepath and os.path.exists(filepath):
        os.remove(filepath)
    logger.info("paper_deleted", paper_id=paper_id)


@router.post("/{paper_id}/retry", response_model=UploadResponse)
async def retry_ingestion(paper_id: str) -> UploadResponse:
    """Resume/retry a failed ingestion job without re-uploading the file."""
    async with AsyncSessionLocal() as session:
        paper = await session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(404, "Paper not found")
        job = IngestionJob(paper_id=paper_id, status=JobStatus.PENDING, max_attempts=settings.INGEST_MAX_RETRIES)
        session.add(job)
        await session.commit()
        job_id = job.id

    task = ingest_paper_task.delay(job_id, paper_id, paper.filepath)
    async with AsyncSessionLocal() as session:
        db_job = await session.get(IngestionJob, job_id)
        db_job.celery_task_id = task.id
        await session.commit()

    return UploadResponse(paper_id=paper_id, job_id=job_id, filename=paper.filename, message="Retry started")
