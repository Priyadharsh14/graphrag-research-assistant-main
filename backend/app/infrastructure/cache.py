"""
Shared Redis cache for anything worth not recomputing: entity-extraction
results (keyed by content hash, so identical chunk text across papers or
overlapping windows never hits the LLM twice), and later literature
review / gap analysis responses if the same query repeats.

Redis was already a hard dependency (Celery broker), so this adds no new
infrastructure — just a second logical use of it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_client: aioredis.Redis | None = None


def get_cache_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def content_key(prefix: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


async def cache_get_json(key: str) -> Any | None:
    client = get_cache_client()
    raw = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int = 60 * 60 * 24 * 30) -> None:
    client = get_cache_client()
    await client.set(key, json.dumps(value), ex=ttl_seconds)
