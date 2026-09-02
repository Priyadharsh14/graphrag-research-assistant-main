# GraphRAG Research Assistant

A production-grade research assistant that turns a folder of PDF papers into
a queryable knowledge graph. Upload papers; it parses, chunks, embeds,
extracts entities and relationships, builds a Neo4j knowledge graph, indexes
a Qdrant vector store, and answers questions using a LangGraph GraphRAG
pipeline that grounds every answer in cited source chunks.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────────────┐
│   React +   │─────▶│   FastAPI    │─────▶│  SQLite/Postgres         │
│  TypeScript │◀─────│   (api)      │      │  (papers, job state)     │
└─────────────┘      └──────┬───────┘      └─────────────────────────┘
                             │ enqueues
                             ▼
                      ┌──────────────┐      ┌───────────┐   ┌──────────┐
                      │ Celery worker│─────▶│  Neo4j    │   │ Qdrant   │
                      │ (ingestion)  │─────▶│  (graph)  │   │ (vectors)│
                      └──────────────┘      └───────────┘   └──────────┘
                             │
                             ▼
                      Groq / OpenAI (LLM: entity extraction + generation)
```

**Ingestion pipeline** (runs as a background Celery task per upload):
`parse PDF → chunk → embed → extract entities/relationships → write to Neo4j → index in Qdrant`.
Every stage writes progress to the database so the UI can poll live status,
and every write is idempotent (Neo4j `MERGE`, deterministic Qdrant point IDs),
so a retried or resumed job never duplicates data.

**Query pipeline** (LangGraph state machine): vector search in Qdrant finds
relevant chunks, Neo4j supplies the entity/relationship neighborhood for
those chunks, both are merged into a single grounded context, and the LLM
answers with inline citations back to `[paper_id, chunk_index, page]`.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript, Vite, Tailwind CSS v4, React Query, React Router |
| Backend API | FastAPI (async), SQLAlchemy (async), Pydantic v2 |
| Background jobs | Celery + Redis (broker/backend), autoretry with backoff |
| Knowledge graph | Neo4j 5 |
| Vector index | Qdrant |
| Embeddings | Sentence Transformers (`BAAI/bge-small-en-v1.5`, swappable) |
| LLM | Groq (Llama 3.3 70B) or OpenAI — provider-switchable via config |
| Orchestration | LangGraph |
| Testing | pytest (backend), oxlint + tsc (frontend) |
| CI/CD | GitHub Actions (test → lint → build → docker build) |

## Features

- **Upload & Library** — drag-and-drop PDF upload, background processing with live progress, retry on failure
- **Research Chat** — GraphRAG question answering with inline citations, scoped to selected papers
- **Literature Review** — theme-organized synthesis across the library
- **Paper Comparison** — structured side-by-side comparison across chosen aspects
- **Research Gap Analysis** — surfaces open problems and future directions from source material
- **Citation Explorer** — browse a paper's extracted entities and relationships
- **Knowledge Graph Visualization** — interactive force-directed graph per paper
- **Health Dashboard** — live status of Neo4j, Qdrant, Redis, and the metadata DB
- **Export Center** — download paper metadata/graph summaries as JSON or CSV
- **Settings** — Light / Dark / System theme, connection info

## Frontends

There are two interchangeable frontends, both talking to the same FastAPI backend:

| | React + TypeScript | Streamlit |
|---|---|---|
| Path | `frontend/` | `streamlit_app/` |
| Port | 3000 | 8501 |
| Best for | polished, production-facing UI | fast iteration, simpler deploy, no npm/nginx build step |

Pick whichever you want to run — `docker compose up` starts both by default (they don't conflict, just different ports), or run `docker compose up api worker neo4j qdrant redis streamlit` to skip building the React app entirely.

## Running it

### Prerequisites
Docker and Docker Compose. A Gemini API key (free tier works, get one at
https://aistudio.google.com/apikey), or a Groq/OpenAI key.

### Quickstart

```bash
git clone <this-repo>
cd graphrag-assistant
cp .env.example .env
# Edit .env and set GEMINI_API_KEY (or switch LLM_PROVIDER=groq/openai and set the matching key)

docker compose up --build
```

Then open:
- React app: http://localhost:3000
- Streamlit app: http://localhost:8501
- API docs: http://localhost:8000/api/docs
- Neo4j browser: http://localhost:7474
- Qdrant dashboard: http://localhost:6333/dashboard
- Flower (Celery monitoring): http://localhost:5555

### Local development (without Docker)

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # then edit values, especially NEO4J_URI/QDRANT_HOST to localhost
uvicorn app.main:app --reload
# in a second terminal, run the worker:
celery -A app.infrastructure.celery.app.celery_app worker --loglevel=info
```

**React frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Streamlit frontend:**
```bash
cd streamlit_app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export API_BASE_URL=http://localhost:8000/api/v1
streamlit run app.py
```

## Deploying the Streamlit app standalone (Streamlit Community Cloud)

The Streamlit app has a dual-mode design (`streamlit_app/engine.py`): with
`API_BASE_URL` set it is a thin client for the full backend, and without it
(or with `STANDALONE_MODE=true`) it runs the entire pipeline in-process via
`streamlit_app/local_engine.py` — PyMuPDF parsing, sentence-transformers
embeddings, in-memory cosine-similarity retrieval, batched entity
extraction (Gemini by default, Groq optional), and graph-relationship
context in every answer. No Docker,
Neo4j, Qdrant, Redis, or Celery required.

To deploy on Streamlit Community Cloud:

1. Push this repository to GitHub.
2. On share.streamlit.io, create a new app pointing at this repo with
   **main file path** `streamlit_app/app.py`.
3. In the app's **Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key"
   ```
   (Get a free key at https://aistudio.google.com/apikey. To use Groq
   instead, set `LLM_PROVIDER = "groq"` and `GROQ_API_KEY = "..."`.)
4. Deploy. Dependencies install from the root `requirements.txt` (CPU-only
   torch is pinned there to keep the install within free-tier limits).

Standalone-mode trade-offs (deliberate, documented in `local_engine.py`):
papers live only for the browser session (no cross-session persistence),
uploads process synchronously with a spinner instead of in the background,
and entities/relationships are held in memory rather than in a queryable
Neo4j graph — retrieval still receives knowledge-graph relationship context,
preserving the GraphRAG behavior, but graph persistence and traversal depth
belong to the full Docker deployment.
Note: `st.graphviz_chart` (used on the Knowledge Graph page) needs the system `graphviz` binary installed (`brew install graphviz` / `apt install graphviz`), not just the Python package — the Docker image already includes it.

## Testing

```bash
cd backend
pytest tests/ -v --cov=app
```

```bash
cd frontend
npm run lint
npm run build   # runs tsc type-check + production build
```

## Project layout

```
backend/
  app/
    api/v1/            # FastAPI routers + Pydantic schemas
    core/               # config, logging
    domain/             # SQLAlchemy models
    infrastructure/     # Neo4j, Qdrant, Celery, DB session clients
    services/           # PDF processing, embeddings, LLM client, entity extraction, GraphRAG pipeline
    workers/             # Celery ingestion task
  tests/
frontend/
  src/
    api/                # typed API client
    components/         # shared UI primitives + layout
    hooks/              # theme provider
    pages/              # one file per feature (10 pages)
    types/
docker-compose.yml
.github/workflows/ci.yml
```

## Design notes / decisions worth knowing

- **Resume-on-failure**: ingestion stages are idempotent, and Celery's
  `autoretry_for` + exponential backoff means a transient LLM rate-limit or
  DB hiccup retries automatically without re-processing already-completed
  stages' side effects (though the current implementation re-runs the full
  task on retry — stage-level checkpointing to skip already-embedded chunks
  is the natural next optimization if papers get very large).
- **Entity extraction never hard-fails a paper**: each chunk's extraction
  call is wrapped so a single malformed LLM response degrades to "no
  entities for this chunk" rather than failing the whole ingestion job.
- **Deterministic Qdrant point IDs** (UUID5 derived from `chunk_id`) mean
  re-upserting the same chunk never creates a duplicate point.
- **Provider-agnostic LLM client**: swap Groq ↔ OpenAI via `LLM_PROVIDER`
  in `.env` with no code changes.
