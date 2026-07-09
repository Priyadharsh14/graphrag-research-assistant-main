import axios from 'axios'
import type {
  ChatMessage, Citation, HealthStatus, IngestionJob, Paper, UploadResponse,
} from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const apiClient = axios.create({ baseURL: API_BASE, timeout: 120_000 })

// --- Papers / Upload & Library ---
export async function uploadPaper(file: File, onProgress?: (pct: number) => void): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<UploadResponse>('/papers/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100))
    },
  })
  return data
}

export async function listPapers(): Promise<Paper[]> {
  const { data } = await apiClient.get<Paper[]>('/papers')
  return data
}

export async function getPaper(paperId: string): Promise<Paper> {
  const { data } = await apiClient.get<Paper>(`/papers/${paperId}`)
  return data
}

export async function getJobStatus(jobId: string): Promise<IngestionJob> {
  const { data } = await apiClient.get<IngestionJob>(`/papers/jobs/${jobId}`)
  return data
}

export async function deletePaper(paperId: string): Promise<void> {
  await apiClient.delete(`/papers/${paperId}`)
}

export async function retryIngestion(paperId: string): Promise<UploadResponse> {
  const { data } = await apiClient.post<UploadResponse>(`/papers/${paperId}/retry`)
  return data
}

// --- Research Chat ---
export async function askQuestion(question: string, paperIds?: string[]): Promise<{ answer: string; citations: Citation[] }> {
  const { data } = await apiClient.post('/chat', { question, paper_ids: paperIds ?? null })
  return data
}

// --- Literature Review / Comparison / Gap Analysis ---
export async function generateLiteratureReview(topic: string, paperIds?: string[]) {
  const { data } = await apiClient.post('/literature-review', { topic, paper_ids: paperIds ?? null })
  return data as { topic: string; review: string }
}

export async function comparePapers(paperIds: string[], aspects?: string[]) {
  const { data } = await apiClient.post('/compare-papers', { paper_ids: paperIds, aspects: aspects ?? null })
  return data as { papers: Record<string, string>; comparison: string }
}

export async function analyzeGaps(paperIds?: string[], focusArea?: string) {
  const { data } = await apiClient.post('/gap-analysis', { paper_ids: paperIds ?? null, focus_area: focusArea ?? null })
  return data as { focus_area: string; gaps: string }
}

// --- Citation Explorer / Knowledge Graph ---
export async function getCitationExplorer(paperId: string) {
  const { data } = await apiClient.get(`/citations/${paperId}`)
  return data as { paper_id: string; entities: Record<string, string>; relations: { relation: string; target: string }[] }
}

export async function getEntityNeighborhood(entityName: string, depth = 2) {
  const { data } = await apiClient.get(`/graph/entity/${encodeURIComponent(entityName)}`, { params: { depth } })
  return data
}

export async function getPaperGraph(paperId: string) {
  const { data } = await apiClient.get(`/graph/paper/${paperId}`)
  return data
}

// --- Health ---
export async function getHealth(): Promise<HealthStatus> {
  const { data } = await apiClient.get<HealthStatus>('/health')
  return data
}

// --- Export ---
export function exportPaperUrl(paperId: string, format: 'json' | 'csv') {
  return `${API_BASE}/export/${paperId}?format=${format}`
}

export function newChatMessage(role: ChatMessage['role'], content: string, citations?: Citation[]): ChatMessage {
  return { id: crypto.randomUUID(), role, content, citations, timestamp: new Date().toISOString() }
}
