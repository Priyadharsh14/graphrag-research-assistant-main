"""
GraphRAG question-answering pipeline as a LangGraph state machine:

  retrieve_vectors -> retrieve_graph_context -> rerank_and_merge -> generate_answer

Vector retrieval (Qdrant) finds semantically similar chunks; graph retrieval
(Neo4j) pulls the entity neighborhood for entities mentioned in those chunks,
giving the LLM structural context (relationships) that pure vector search
would miss. Both are merged into a single grounded context for generation,
and every claim is required to cite a chunk/paper.
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

from app.core.logging import get_logger
from app.infrastructure.neo4j.client import neo4j_client
from app.infrastructure.qdrant.client import vector_store
from app.services.embeddings import embed_query
from app.services.llm_client import get_llm_client

logger = get_logger(__name__)

ANSWER_SYSTEM_PROMPT = """You are a rigorous research assistant answering questions about a corpus \
of academic papers using retrieved context. Rules:
- Answer ONLY from the provided context. If the context is insufficient, say so explicitly.
- Every factual claim must include an inline citation like [Paper: <title>, chunk <n>].
- Be precise and technical; do not pad with generic statements.
- If graph relationships are provided, use them to explain how concepts/methods relate.
"""


class GraphRAGState(TypedDict):
    question: str
    paper_ids: list[str] | None
    vector_hits: list[dict]
    graph_context: list[dict]
    merged_context: str
    answer: str
    citations: Annotated[list[dict], "citations used in the answer"]


def retrieve_vectors(state: GraphRAGState) -> GraphRAGState:
    query_vector = embed_query(state["question"])
    hits = _run_sync(vector_store.search(query_vector, top_k=8, paper_ids=state.get("paper_ids")))
    state["vector_hits"] = hits
    return state


def retrieve_graph_context(state: GraphRAGState) -> GraphRAGState:
    # Pull entity names mentioned near the top vector hits by re-using chunk_ids
    # to query Neo4j for entities + their relationships (structural context).
    chunk_ids = [h["chunk_id"] for h in state["vector_hits"]]
    if not chunk_ids:
        state["graph_context"] = []
        return state
    query = """
    MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
    WHERE c.id IN $chunk_ids
    OPTIONAL MATCH (e)-[r:RELATES_TO]-(other:Entity)
    RETURN DISTINCT e.name AS entity, e.type AS type, other.name AS related_entity,
           type(r) AS rel_type, r.type AS relation
    LIMIT 50
    """
    records = _run_sync(neo4j_client.run(query, {"chunk_ids": chunk_ids}))
    state["graph_context"] = records
    return state


def rerank_and_merge(state: GraphRAGState) -> GraphRAGState:
    context_blocks = []
    for hit in state["vector_hits"]:
        context_blocks.append(
            f"[chunk {hit.get('chunk_index')} | paper_id={hit.get('paper_id')} | score={hit.get('score', 0):.3f}]\n{hit.get('text', '')}"
        )
    graph_lines = [
        f"- {g['entity']} ({g.get('type')}) --{g.get('relation') or 'RELATED_TO'}--> {g.get('related_entity')}"
        for g in state["graph_context"] if g.get("related_entity")
    ]
    merged = "RETRIEVED PASSAGES:\n" + "\n\n".join(context_blocks)
    if graph_lines:
        merged += "\n\nKNOWLEDGE GRAPH RELATIONSHIPS:\n" + "\n".join(graph_lines)
    state["merged_context"] = merged
    return state


def generate_answer(state: GraphRAGState) -> GraphRAGState:
    llm = get_llm_client()
    user_prompt = f"Question: {state['question']}\n\nContext:\n{state['merged_context']}"
    answer = llm.complete(system=ANSWER_SYSTEM_PROMPT, user=user_prompt, temperature=0.1, max_tokens=1200)
    state["answer"] = answer
    state["citations"] = [
        {"paper_id": h.get("paper_id"), "chunk_index": h.get("chunk_index"), "page": h.get("page"), "score": h.get("score")}
        for h in state["vector_hits"]
    ]
    return state


def build_graphrag_graph():
    graph = StateGraph(GraphRAGState)
    graph.add_node("retrieve_vectors", retrieve_vectors)
    graph.add_node("retrieve_graph_context", retrieve_graph_context)
    graph.add_node("rerank_and_merge", rerank_and_merge)
    graph.add_node("generate_answer", generate_answer)

    graph.set_entry_point("retrieve_vectors")
    graph.add_edge("retrieve_vectors", "retrieve_graph_context")
    graph.add_edge("retrieve_graph_context", "rerank_and_merge")
    graph.add_edge("rerank_and_merge", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()


_compiled_graph = None


def get_graphrag_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graphrag_graph()
    return _compiled_graph


def _run_sync(coro):
    """LangGraph nodes here are sync; bridge to the async infra clients via
    the shared persistent-loop utility (see app.core.async_utils) rather
    than spinning up a fresh event loop per call — the Neo4j/Qdrant clients
    are cached singletons whose connections bind to whichever loop first
    used them, so a fresh loop per call eventually crashes with
    'Event loop is closed' on the second-or-later request."""
    from app.core.async_utils import run_async
    return run_async(coro)


async def answer_question(question: str, paper_ids: list[str] | None = None) -> dict:
    graph = get_graphrag_graph()
    initial_state: GraphRAGState = {
        "question": question, "paper_ids": paper_ids, "vector_hits": [], "graph_context": [],
        "merged_context": "", "answer": "", "citations": [],
    }
    result = await graph.ainvoke(initial_state)
    return {"answer": result["answer"], "citations": result["citations"]}
