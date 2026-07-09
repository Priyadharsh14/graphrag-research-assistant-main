from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaperOut(BaseModel):
    id: str
    title: str | None
    authors: str | None
    abstract: str | None
    publication_year: int | None
    filename: str
    num_pages: int | None
    num_chunks: int | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobOut(BaseModel):
    id: str
    paper_id: str
    status: str
    current_stage: str | None
    progress_pct: float
    attempt: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadResponse(BaseModel):
    paper_id: str
    job_id: str
    filename: str
    message: str = "Upload accepted. Processing started in background."


class ChatRequest(BaseModel):
    question: str
    paper_ids: list[str] | None = None


class Citation(BaseModel):
    paper_id: str | None
    chunk_index: int | None
    page: int | None
    score: float | None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


class HealthStatus(BaseModel):
    status: str
    neo4j: bool
    qdrant: bool
    redis: bool
    database: bool
