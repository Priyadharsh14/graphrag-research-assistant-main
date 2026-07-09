import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models import Base, IngestionJob, JobStatus, Paper


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_create_paper_and_job(db_session):
    paper = Paper(id="p1", filename="test.pdf", filepath="/tmp/test.pdf", file_hash="hash123")
    db_session.add(paper)
    job = IngestionJob(paper_id="p1", status=JobStatus.PENDING)
    db_session.add(job)
    await db_session.commit()

    fetched = await db_session.get(Paper, "p1")
    assert fetched.filename == "test.pdf"
    assert fetched.status == JobStatus.PENDING


async def test_job_status_transitions(db_session):
    paper = Paper(id="p2", filename="x.pdf", filepath="/tmp/x.pdf", file_hash="hash456")
    db_session.add(paper)
    job = IngestionJob(paper_id="p2", status=JobStatus.PENDING)
    db_session.add(job)
    await db_session.commit()

    job.status = JobStatus.EMBEDDING
    job.progress_pct = 40.0
    await db_session.commit()

    fetched = await db_session.get(IngestionJob, job.id)
    assert fetched.status == JobStatus.EMBEDDING
    assert fetched.progress_pct == 40.0
