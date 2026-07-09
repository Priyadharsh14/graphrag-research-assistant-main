"""
Entity & relationship extraction — redesigned around the single biggest
token/cost lever in the whole ingestion pipeline: call count.

Three optimizations stack here, in order of impact:

1. BATCHING (the big one): instead of one LLM call per chunk, group chunks
   into batches and extract entities for the whole batch in a single call.
   This cuts call count ~N-fold (N = batch size) and eliminates the
   repeated ~250-token system prompt overhead that was being paid on every
   single chunk. For a 75-chunk paper at batch size 6: 75 calls -> ~13.

2. CONTENT-HASH CACHING: identical chunk text (duplicate uploads, or
   overlapping sliding-window chunks that happen to coincide) is extracted
   once and reused from Redis thereafter — zero LLM calls on a cache hit.

3. LOW-VALUE CHUNK FILTERING: reference lists / bibliographies are detected
   heuristically and skipped entirely before they ever reach the LLM. They
   rarely contain extractable entities beyond citation noise, so spending
   tokens on them is close to pure waste.

Each chunk's result is still cached and returned individually (keyed by
its original index), so callers don't need to know batching happened.
"""
from __future__ import annotations

import asyncio
import json
import re

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.cache import cache_get_json, cache_set_json, content_key, get_cache_client
from app.services.llm_client import get_llm_client

logger = get_logger(__name__)
settings = get_settings()

EMPTY_RESULT = {"entities": [], "relationships": []}

SYSTEM_PROMPT = """You are a precise information-extraction engine for academic research papers.
You will be given several numbered text chunks. For EACH chunk, extract named entities and
relationships mentioned in THAT chunk only.

Entity types: METHOD, MODEL, DATASET, METRIC, TASK, AUTHOR, ORGANIZATION, CONCEPT.
Relationship types: USES, PROPOSES, OUTPERFORMS, EVALUATED_ON, PART_OF, COMPARED_TO, EXTENDS, CITES.

Return ONLY valid JSON, no prose, matching exactly this schema — one entry per chunk number,
using the SAME chunk numbers given in the input (as strings):
{
  "0": {"entities": [{"name": str, "type": str}], "relationships": [{"source": str, "source_type": str, "target": str, "target_type": str, "relation": str}]},
  "1": {"entities": [...], "relationships": [...]}
}
If a chunk has nothing relevant, use {"entities": [], "relationships": []} for that chunk's entry.
"""

# Reference-list chunks are mostly citation noise (author names, years, journal
# titles repeated hundreds of times) -- rarely worth an LLM call. Detected
# heuristically rather than via a section-parser, since PDF section headers
# are inconsistent across papers.
_REFERENCE_LINE_PATTERN = re.compile(r"^\s*\[\d+\]|\(\d{4}\)\.|et al\.,", re.MULTILINE)
_REFERENCE_HEADING_PATTERN = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)


def is_low_value_chunk(text: str) -> bool:
    """Heuristic filter for reference lists / bibliographies. Errs toward
    NOT filtering when uncertain -- a missed entity is cheaper than a
    silently incomplete graph, but an obviously citation-only chunk is
    pure token waste."""
    if _REFERENCE_HEADING_PATTERN.search(text[:200]):
        return True
    reference_line_hits = len(_REFERENCE_LINE_PATTERN.findall(text))
    # A dense block of citation-shaped lines (roughly one per ~80 chars)
    # is almost certainly a reference list rather than prose.
    return reference_line_hits >= 4 and reference_line_hits >= len(text) // 200


def _batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


STATS_KEY_PREFIX = "extraction_stats"


async def _record_stats(total_chunks: int, filtered: int, cache_hits: int, deduped: int, llm_calls: int) -> None:
    """Cumulative counters for the monitoring dashboard -- how many chunks
    were ever filtered/cached/deduped vs. how many actually needed an LLM
    call, since the app started. Best-effort: monitoring should never be
    able to fail an ingestion job."""
    try:
        client = get_cache_client()
        pipe = client.pipeline()
        pipe.incrby(f"{STATS_KEY_PREFIX}:total_chunks", total_chunks)
        pipe.incrby(f"{STATS_KEY_PREFIX}:filtered_low_value", filtered)
        pipe.incrby(f"{STATS_KEY_PREFIX}:cache_hits", cache_hits)
        pipe.incrby(f"{STATS_KEY_PREFIX}:duplicates_deduped", deduped)
        pipe.incrby(f"{STATS_KEY_PREFIX}:llm_calls", llm_calls)
        pipe.incr(f"{STATS_KEY_PREFIX}:ingestion_runs")
        await pipe.execute()
    except Exception as exc:
        logger.warning("stats_recording_failed_soft", error=str(exc))


async def get_extraction_stats() -> dict:
    """Cumulative counts since the Redis instance was last flushed, for the
    Health/Monitoring dashboard. All-zero if nothing has run yet."""
    client = get_cache_client()
    keys = ["total_chunks", "filtered_low_value", "cache_hits", "duplicates_deduped", "llm_calls", "ingestion_runs"]
    values = await client.mget([f"{STATS_KEY_PREFIX}:{k}" for k in keys])
    stats = {k: int(v) if v else 0 for k, v in zip(keys, values)}
    would_have_been = stats["total_chunks"]
    saved_calls = would_have_been - stats["llm_calls"]
    stats["calls_saved_vs_naive"] = max(0, saved_calls)
    stats["reduction_pct"] = round(100 * saved_calls / would_have_been, 1) if would_have_been else 0.0
    return stats


async def _extract_batch_uncached(batch_indices: list[int], batch_texts: list[str]) -> dict[int, dict]:
    """One LLM call covering multiple chunks. Falls back to per-chunk empty
    results (never raises) so one malformed response can't fail ingestion."""
    llm = get_llm_client()
    numbered_input = "\n\n".join(f"=== CHUNK {i} ===\n{text[:3000]}" for i, text in zip(batch_indices, batch_texts))
    try:
        raw = llm.complete(
            system=SYSTEM_PROMPT, user=numbered_input, temperature=0.0, json_mode=True,
            max_tokens=400 * len(batch_indices) + 200, use_extraction_model=True,
        )
        parsed = json.loads(raw)
        results = {}
        for i in batch_indices:
            entry = parsed.get(str(i)) or parsed.get(i) or EMPTY_RESULT
            results[i] = {
                "entities": entry.get("entities", []),
                "relationships": entry.get("relationships", []),
            }
        return results
    except Exception as exc:
        logger.warning("batch_entity_extraction_failed_soft", error=str(exc), batch_size=len(batch_indices))
        return {i: dict(EMPTY_RESULT) for i in batch_indices}


async def extract_entities_for_chunks(chunk_texts: list[str], batch_size: int = 6) -> list[dict]:
    """Main entry point: extracts entities/relationships for a full list of
    chunks, applying filtering, caching, and batching. Returns a list
    aligned with the input order (one result dict per chunk).

    Identical chunk text (duplicate/overlapping chunks within the SAME call,
    not just across separate calls) is deduplicated before any LLM call is
    made -- every original index sharing that content gets the same result."""
    results: dict[int, dict] = {}
    cache_keys: dict[int, str] = {}
    # content hash -> representative text + all original indices sharing it
    unique_pending: dict[str, tuple[str, list[int]]] = {}

    for idx, text in enumerate(chunk_texts):
        if is_low_value_chunk(text):
            results[idx] = dict(EMPTY_RESULT)
            continue

        key = content_key("entity_extraction", text)
        cache_keys[idx] = key
        cached = await cache_get_json(key)
        if cached is not None:
            results[idx] = cached
            continue

        if key in unique_pending:
            unique_pending[key][1].append(idx)
        else:
            unique_pending[key] = (text, [idx])

    unique_keys = list(unique_pending.keys())
    unique_texts = [unique_pending[k][0] for k in unique_keys]

    filtered_count = len(chunk_texts) - len(cache_keys)
    cache_hit_count = sum(1 for i in results if i in cache_keys)
    dedup_count = sum(len(v[1]) for v in unique_pending.values()) - len(unique_keys)
    llm_calls_count = (len(unique_keys) + batch_size - 1) // batch_size if unique_keys else 0

    logger.info(
        "entity_extraction_plan",
        total_chunks=len(chunk_texts),
        filtered_low_value=filtered_count,
        cache_hits=cache_hit_count,
        duplicate_chunks_deduped=dedup_count,
        llm_calls_needed=llm_calls_count,
    )
    await _record_stats(
        total_chunks=len(chunk_texts), filtered=filtered_count, cache_hits=cache_hit_count,
        deduped=dedup_count, llm_calls=llm_calls_count,
    )

    # Batch over the *deduplicated* texts -- position within this list is
    # the batch index, mapped back to unique_keys to find every original
    # chunk index that shares this content.
    batch_position_groups = list(_batches(list(range(len(unique_texts))), batch_size))
    batch_text_groups = list(_batches(unique_texts, batch_size))

    semaphore = asyncio.Semaphore(6)

    async def _run_batch(positions: list[int], text_batch: list[str]) -> None:
        async with semaphore:
            batch_results = await _extract_batch_uncached(positions, text_batch)
        for pos, result in batch_results.items():
            key = unique_keys[pos]
            await cache_set_json(key, result)
            for original_idx in unique_pending[key][1]:
                results[original_idx] = result

    await asyncio.gather(*[
        _run_batch(positions, text_batch)
        for positions, text_batch in zip(batch_position_groups, batch_text_groups)
    ])

    return [results[i] for i in range(len(chunk_texts))]
