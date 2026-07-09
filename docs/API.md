# API Reference

Full interactive docs are always available at `/api/docs` (Swagger) and
`/api/redoc` once the API is running. This is a quick reference.

Base path: `/api/v1`

## Upload & Library

| Method | Path | Description |
|---|---|---|
| POST | `/papers/upload` | Upload a PDF. Returns immediately (202) with `paper_id` + `job_id`; processing runs in the background. |
| GET | `/papers` | List papers (paginated via `skip`/`limit`). |
| GET | `/papers/{paper_id}` | Get one paper's metadata and status. |
| GET | `/papers/jobs/{job_id}` | Poll ingestion job status/progress. |
| DELETE | `/papers/{paper_id}` | Delete a paper and all its graph/vector data. |
| POST | `/papers/{paper_id}/retry` | Re-run ingestion for a paper that failed, without re-uploading. |

## Research Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | `{question, paper_ids?}` → GraphRAG answer with citations. |

## Knowledge Graph

| Method | Path | Description |
|---|---|---|
| GET | `/graph/entity/{entity_name}?depth=2` | Entity neighborhood subgraph. |
| GET | `/graph/paper/{paper_id}` | Full chunk/entity/relationship graph for one paper. |

## Research Analysis

| Method | Path | Description |
|---|---|---|
| POST | `/literature-review` | `{topic, paper_ids?}` → theme-organized synthesis. |
| POST | `/compare-papers` | `{paper_ids[], aspects?}` → structured comparison (min 2 papers). |
| POST | `/gap-analysis` | `{paper_ids?, focus_area?}` → grounded list of research gaps. |
| GET | `/citations/{paper_id}` | Entities and relationships extracted from one paper. |
| GET | `/export/{paper_id}?format=json\|csv` | Download paper metadata + graph summary. |

## Operations

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status of Neo4j, Qdrant, Redis, and the metadata DB. |
| GET | `/metrics` | Prometheus metrics (request counts, latency histograms). |

## Job status values

`pending → parsing → chunking → embedding → extracting_entities → building_graph → indexing_vectors → completed`

or `failed` / `retrying` if a stage errors (auto-retried up to `INGEST_MAX_RETRIES`, default 3).
