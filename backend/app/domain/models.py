"""
Relational metadata store (SQLite/Postgres-compatible via SQLAlchemy async).
Neo4j holds the knowledge graph; Qdrant holds vectors; this DB holds
operational state: papers, ingestion jobs, job stages, and users.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    EXTRACTING_ENTITIES = "extracting_entities"
    BUILDING_GRAPH = "building_graph"
    INDEXING_VECTORS = "indexing_vectors"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=True)
    authors = Column(Text, nullable=True)  # JSON-encoded list
    abstract = Column(Text, nullable=True)
    publication_year = Column(Integer, nullable=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    file_hash = Column(String, nullable=False, index=True)
    num_pages = Column(Integer, nullable=True)
    num_chunks = Column(Integer, nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    jobs = relationship("IngestionJob", back_populates="paper", cascade="all, delete-orphan")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    current_stage = Column(String, nullable=True)
    progress_pct = Column(Float, default=0.0)
    attempt = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)

    paper = relationship("Paper", back_populates="jobs")
