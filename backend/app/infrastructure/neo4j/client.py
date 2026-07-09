"""
Neo4j graph store client. Owns schema constraints and all Cypher writes/reads
for the knowledge graph: Paper, Chunk, Entity, and their relationships.
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_name_type IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
    "CREATE INDEX chunk_paper_idx IF NOT EXISTS FOR (c:Chunk) ON (c.paper_id)",
    "CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS FOR (e:Entity) ON EACH [e.name]",
]


class Neo4jClient:
    """Thin, retry-wrapped async interface over the Neo4j driver."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def run(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        driver = await get_driver()
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, params or {})
            records = [record.data() async for record in result]
            return records

    async def ensure_schema(self) -> None:
        for stmt in SCHEMA_STATEMENTS:
            try:
                await self.run(stmt)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("schema_statement_failed", statement=stmt, error=str(exc))

    async def upsert_paper(self, paper_id: str, title: str, authors: list[str], year: int | None) -> None:
        await self.run(
            """
            MERGE (p:Paper {id: $id})
            SET p.title = $title, p.authors = $authors, p.year = $year
            """,
            {"id": paper_id, "title": title, "authors": authors, "year": year},
        )

    async def upsert_chunk(self, chunk_id: str, paper_id: str, text: str, chunk_index: int, page: int | None) -> None:
        await self.run(
            """
            MATCH (p:Paper {id: $paper_id})
            MERGE (c:Chunk {id: $chunk_id})
            SET c.text = $text, c.chunk_index = $chunk_index, c.page = $page
            MERGE (p)-[:HAS_CHUNK]->(c)
            """,
            {"chunk_id": chunk_id, "paper_id": paper_id, "text": text, "chunk_index": chunk_index, "page": page},
        )

    async def upsert_entity_and_link(
        self, entity_name: str, entity_type: str, chunk_id: str, mention_text: str
    ) -> None:
        await self.run(
            """
            MERGE (e:Entity {name: $name, type: $type})
            WITH e
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (c)-[:MENTIONS {text: $mention_text}]->(e)
            """,
            {"name": entity_name, "type": entity_type, "chunk_id": chunk_id, "mention_text": mention_text},
        )

    async def link_entities(self, source: str, source_type: str, target: str, target_type: str, relation: str, paper_id: str) -> None:
        await self.run(
            """
            MERGE (a:Entity {name: $source, type: $source_type})
            MERGE (b:Entity {name: $target, type: $target_type})
            MERGE (a)-[r:RELATES_TO {type: $relation}]->(b)
            ON CREATE SET r.paper_ids = [$paper_id]
            ON MATCH SET r.paper_ids = CASE WHEN $paper_id IN r.paper_ids THEN r.paper_ids ELSE r.paper_ids + $paper_id END
            """,
            {"source": source, "source_type": source_type, "target": target, "target_type": target_type,
             "relation": relation, "paper_id": paper_id},
        )

    async def get_neighborhood(self, entity_name: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        return await self.run(
            f"""
            MATCH path = (e:Entity {{name: $name}})-[*1..{min(depth, 3)}]-(other)
            RETURN path LIMIT $limit
            """,
            {"name": entity_name, "limit": limit},
        )

    async def get_paper_graph(self, paper_id: str) -> list[dict[str, Any]]:
        return await self.run(
            """
            MATCH (p:Paper {id: $paper_id})-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
            OPTIONAL MATCH (e)-[r:RELATES_TO]-(e2:Entity)
            RETURN p, c, e, r, e2 LIMIT 500
            """,
            {"paper_id": paper_id},
        )

    async def delete_paper(self, paper_id: str) -> None:
        await self.run(
            """
            MATCH (p:Paper {id: $paper_id})-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c
            WITH p
            DETACH DELETE p
            """,
            {"paper_id": paper_id},
        )


neo4j_client = Neo4jClient()
