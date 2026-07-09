import json

import pytest

import app.services.entity_extraction as ee


@pytest.fixture
def fake_cache(monkeypatch):
    store = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl_seconds=None):
        store[key] = value

    monkeypatch.setattr(ee, "cache_get_json", fake_get)
    monkeypatch.setattr(ee, "cache_set_json", fake_set)
    return store


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    class FakeLLM:
        def complete(self, system, user, temperature, json_mode, max_tokens, use_extraction_model):
            calls.append(user)
            import re
            chunk_nums = re.findall(r"=== CHUNK (\d+) ===", user)
            return json.dumps({
                n: {"entities": [{"name": f"Entity{n}", "type": "CONCEPT"}], "relationships": []}
                for n in chunk_nums
            })

    monkeypatch.setattr(ee, "get_llm_client", lambda: FakeLLM())
    return calls


def test_is_low_value_chunk_detects_reference_lists():
    reference_chunk = "References\n" + "\n".join(f"[{i}] Smith et al., ({2000+i}). Some Journal." for i in range(20))
    assert ee.is_low_value_chunk(reference_chunk) is True


def test_is_low_value_chunk_does_not_flag_normal_prose():
    prose = "This paper proposes a new Transformer architecture for NLP tasks using self-attention."
    assert ee.is_low_value_chunk(prose) is False


async def test_reference_chunks_never_reach_the_llm(fake_cache, fake_llm):
    reference_chunk = "References\n" + "\n".join(f"[{i}] Smith et al., ({2000+i}). Some Journal." for i in range(20))
    results = await ee.extract_entities_for_chunks([reference_chunk], batch_size=6)
    assert results == [ee.EMPTY_RESULT]
    assert len(fake_llm) == 0


async def test_batching_reduces_call_count(fake_cache, fake_llm):
    chunks = [f"Sentence number {i} about some research topic." for i in range(10)]
    results = await ee.extract_entities_for_chunks(chunks, batch_size=4)
    assert len(results) == 10
    # 10 chunks at batch_size=4 -> ceil(10/4) = 3 calls, not 10
    assert len(fake_llm) == 3


async def test_duplicate_chunks_deduped_within_one_call(fake_cache, fake_llm):
    text = "This paper proposes a new Transformer architecture for NLP tasks."
    chunks = [text, "A different sentence entirely.", text]
    results = await ee.extract_entities_for_chunks(chunks, batch_size=6)
    assert results[0] == results[2]
    # Only 1 call needed: 2 unique texts fit in one batch of size 6
    assert len(fake_llm) == 1


async def test_identical_content_cached_across_separate_calls(fake_cache, fake_llm):
    text = "This paper proposes a new Transformer architecture for NLP tasks."
    first = await ee.extract_entities_for_chunks([text], batch_size=6)
    assert len(fake_llm) == 1

    second = await ee.extract_entities_for_chunks([text, "Something new and different."], batch_size=6)
    # Second call should only need the LLM for the new text, not the cached one
    assert len(fake_llm) == 2
    assert second[0] == first[0]
