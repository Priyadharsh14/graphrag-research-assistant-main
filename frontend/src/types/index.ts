export type JobStatus =
  | 'pending' | 'parsing' | 'chunking' | 'embedding'
  | 'extracting_entities' | 'building_graph' | 'indexing_vectors'
  | 'completed' | 'failed' | 'retrying'

export interface Paper {
  id: string
  title: string | null
  authors: string | null
  abstract: string | null
  publication_year: number | null
  filename: string
  num_pages: number | null
  num_chunks: number | null
  status: JobStatus
  created_at: string
}

export interface IngestionJob {
  id: string
  paper_id: string
  status: JobStatus
  current_stage: string | null
  progress_pct: number
  attempt: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Citation {
  paper_id: string | null
  chunk_index: number | null
  page: number | null
  score: number | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  timestamp: string
}

export interface HealthStatus {
  status: 'healthy' | 'degraded'
  neo4j: boolean
  qdrant: boolean
  redis: boolean
  database: boolean
}

export interface UploadResponse {
  paper_id: string
  job_id: string
  filename: string
  message: string
}
