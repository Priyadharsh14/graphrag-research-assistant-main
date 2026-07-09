import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, UploadCloud, Trash2, RotateCcw } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Badge, Button, Card, ProgressBar, TableSkeleton, EmptyState } from '@/components/ui'
import { deletePaper, listPapers, retryIngestion, uploadPaper } from '@/api/client'
import type { JobStatus, Paper } from '@/types'

const STATUS_TONE: Record<JobStatus, 'neutral' | 'success' | 'danger' | 'graph'> = {
  pending: 'neutral', parsing: 'graph', chunking: 'graph', embedding: 'graph',
  extracting_entities: 'graph', building_graph: 'graph', indexing_vectors: 'graph',
  completed: 'success', failed: 'danger', retrying: 'graph',
}

const STAGE_LABEL: Record<JobStatus, string> = {
  pending: 'Queued', parsing: 'Parsing PDF', chunking: 'Chunking', embedding: 'Generating embeddings',
  extracting_entities: 'Extracting entities', building_graph: 'Building graph',
  indexing_vectors: 'Indexing vectors', completed: 'Completed', failed: 'Failed', retrying: 'Retrying',
}

export function UploadLibraryPage() {
  const queryClient = useQueryClient()
  const [activeUploads, setActiveUploads] = useState<Record<string, number>>({})

  const { data: papers, isLoading } = useQuery({
    queryKey: ['papers'],
    queryFn: listPapers,
    refetchInterval: (query) => {
      const hasActive = query.state.data?.some((p) => !['completed', 'failed'].includes(p.status))
      return hasActive ? 2000 : false
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      uploadPaper(file, (pct) => setActiveUploads((prev) => ({ ...prev, [file.name]: pct }))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: deletePaper,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers'] }),
  })

  const retryMutation = useMutation({
    mutationFn: retryIngestion,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers'] }),
  })

  const onDrop = useCallback((accepted: File[]) => {
    accepted.forEach((file) => uploadMutation.mutate(file))
  }, [uploadMutation])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  })

  return (
    <div>
      <PageHeader
        title="Upload & Library"
        description="Drop in research PDFs — parsing, chunking, embedding, and knowledge-graph construction all run in the background."
      />

      <div
        {...getRootProps()}
        className={`mb-8 flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed py-14 text-center transition-colors ${
          isDragActive ? 'border-graph bg-graph-soft' : 'border-border hover:border-graph/40 hover:bg-paper-dim'
        }`}
      >
        <input {...getInputProps()} />
        <UploadCloud className={`h-8 w-8 ${isDragActive ? 'text-graph' : 'text-ink-faint'}`} />
        <div>
          <p className="font-medium text-ink">Drop PDF papers here, or click to browse</p>
          <p className="mt-1 text-sm text-ink-soft">Processing starts immediately — you can keep working while it runs.</p>
        </div>
      </div>

      {Object.keys(activeUploads).length > 0 && (
        <div className="mb-6 space-y-2">
          {Object.entries(activeUploads).map(([name, pct]) => (
            <Card key={name} className="px-4 py-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="truncate font-medium">{name}</span>
                <span className="text-ink-soft">{pct < 100 ? `Uploading ${pct}%` : 'Processing...'}</span>
              </div>
              <ProgressBar value={pct} />
            </Card>
          ))}
        </div>
      )}

      <Card>
        <div className="border-b border-border px-5 py-4">
          <h2 className="font-display text-sm font-semibold">Library</h2>
        </div>
        <div className="p-5">
          {isLoading ? (
            <TableSkeleton rows={4} cols={5} />
          ) : !papers || papers.length === 0 ? (
            <EmptyState
              title="No papers yet"
              description="Upload a PDF above to start building your knowledge graph."
            />
          ) : (
            <div className="space-y-2">
              {papers.map((paper) => (
                <PaperRow
                  key={paper.id}
                  paper={paper}
                  onDelete={() => deleteMutation.mutate(paper.id)}
                  onRetry={() => retryMutation.mutate(paper.id)}
                />
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

function PaperRow({ paper, onDelete, onRetry }: { paper: Paper; onDelete: () => void; onRetry: () => void }) {
  const inProgress = !['completed', 'failed'].includes(paper.status)

  return (
    <div className="flex items-center gap-4 rounded-lg px-3 py-3 hover:bg-paper-dim">
      <FileText className="h-5 w-5 shrink-0 text-ink-faint" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{paper.title || paper.filename}</p>
        <p className="mt-0.5 flex items-center gap-2 font-mono text-xs text-ink-faint">
          {paper.num_pages ? `${paper.num_pages} pages` : '—'} · {paper.num_chunks ? `${paper.num_chunks} chunks` : '—'}
        </p>
        {inProgress && (
          <div className="mt-2 max-w-xs">
            <ProgressBar value={paper.status === 'pending' ? 5 : 50} />
          </div>
        )}
      </div>
      <Badge tone={STATUS_TONE[paper.status]}>{STAGE_LABEL[paper.status]}</Badge>
      {paper.status === 'failed' && (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          <RotateCcw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
      <Button size="sm" variant="ghost" onClick={onDelete} aria-label="Delete paper">
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  )
}
