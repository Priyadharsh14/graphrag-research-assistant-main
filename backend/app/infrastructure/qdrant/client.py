"""Qdrant vector store client: collection lifecycle, upsert, hybrid-ready search."""
from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=30)
    return _client


class QdrantVectorStore:
    def __init__(self) -> None:
        self.collection = settings.QDRANT_COLLECTION

    async def ensure_collection(self) -> None:
        client = get_client()
        existing = await client.get_collections()
        names = [c.name for c in existing.collections]
        if self.collection not in names:
            await client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=settings.EMBEDDING_DIM, distance=models.Distance.COSINE),
            )
            await client.create_payload_index(
                collection_name=self.collection, field_name="paper_id", field_schema="keyword"
            )
            logger.info("qdrant_collection_created", collection=self.collection)

    @staticmethod
    def deterministic_point_id(chunk_id: str) -> str:
        # Qdrant requires UUID or unsigned int point IDs — derive a stable UUID from our chunk_id.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def upsert_chunks(self, points: list[dict[str, Any]]) -> None:
        """points: [{chunk_id, vector, paper_id, text, chunk_index, page}]"""
        client = get_client()
        qdrant_points = [
            models.PointStruct(
                id=self.deterministic_point_id(p["chunk_id"]),
                vector=p["vector"],
                payload={
                    "chunk_id": p["chunk_id"],
                    "paper_id": p["paper_id"],
                    "text": p["text"],
                    "chunk_index": p["chunk_index"],
                    "page": p.get("page"),
                },
            )
            for p in points
        ]
        await client.upsert(collection_name=self.collection, points=qdrant_points, wait=True)

    async def search(self, query_vector: list[float], top_k: int = 8, paper_ids: list[str] | None = None) -> list[dict[str, Any]]:
        client = get_client()
        query_filter = None
        if paper_ids:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="paper_id", match=models.MatchAny(any=paper_ids))]
            )
        results = await client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {"score": pt.score, **(pt.payload or {})}
            for pt in results.points
        ]

    async def delete_paper(self, paper_id: str) -> None:
        client = get_client()
        await client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(key="paper_id", match=models.MatchValue(value=paper_id))])
            ),
        )


vector_store = QdrantVectorStore()
