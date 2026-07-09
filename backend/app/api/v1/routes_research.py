from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas import ChatRequest, ChatResponse, HealthStatus
from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.db import engine
from app.infrastructure.neo4j.client import get_driver, neo4j_client
from app.infrastructure.qdrant.client import get_client as get_qdrant_client
from app.services.graphrag_pipeline import answer_question

router = APIRouter(tags=["Research Chat"])
logger = get_logger(__name__)
settings = get_settings()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")
    try:
        result = await answer_question(request.question, request.paper_ids)
        return ChatResponse(**result)
    except Exception as exc:
        logger.error("chat_failed", error=str(exc))
        raise HTTPException(502, f"Failed to generate answer: {exc}")


@router.get("/graph/entity/{entity_name}")
async def get_entity_neighborhood(entity_name: str, depth: int = 2):
    records = await neo4j_client.get_neighborhood(entity_name, depth=depth)
    return {"entity": entity_name, "paths": len(records), "data": records}


@router.get("/graph/paper/{paper_id}")
async def get_paper_graph(paper_id: str):
    records = await neo4j_client.get_paper_graph(paper_id)
    return {"paper_id": paper_id, "data": records}


@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    neo4j_ok = qdrant_ok = redis_ok = db_ok = False

    try:
        driver = await get_driver()
        await driver.verify_connectivity()
        neo4j_ok = True
    except Exception as exc:
        logger.warning("health_neo4j_down", error=str(exc))

    try:
        client = get_qdrant_client()
        await client.get_collections()
        qdrant_ok = True
    except Exception as exc:
        logger.warning("health_qdrant_down", error=str(exc))

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_ok = True
        await r.close()
    except Exception as exc:
        logger.warning("health_redis_down", error=str(exc))

    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("health_db_down", error=str(exc))

    overall = "healthy" if all([neo4j_ok, qdrant_ok, redis_ok, db_ok]) else "degraded"
    return HealthStatus(status=overall, neo4j=neo4j_ok, qdrant=qdrant_ok, redis=redis_ok, database=db_ok)
