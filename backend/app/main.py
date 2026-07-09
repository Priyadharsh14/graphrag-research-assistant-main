"""FastAPI application entrypoint: middleware, routers, lifespan startup/shutdown."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.routes_analysis import router as analysis_router
from app.api.v1.routes_papers import router as papers_router
from app.api.v1.routes_research import router as research_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db import init_db
from app.infrastructure.neo4j.client import close_driver, neo4j_client
from app.infrastructure.qdrant.client import vector_store

settings = get_settings()
configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup_begin", env=settings.ENV)
    await init_db()
    try:
        await neo4j_client.ensure_schema()
    except Exception as exc:
        logger.warning("neo4j_schema_init_deferred", error=str(exc))
    try:
        await vector_store.ensure_collection()
    except Exception as exc:
        logger.warning("qdrant_collection_init_deferred", error=str(exc))
    logger.info("startup_complete")
    yield
    await close_driver()
    logger.info("shutdown_complete")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Production-grade GraphRAG Research Assistant API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(papers_router, prefix=settings.API_V1_PREFIX)
app.include_router(research_router, prefix=settings.API_V1_PREFIX)
app.include_router(analysis_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "status": "running", "docs": "/api/docs"}
