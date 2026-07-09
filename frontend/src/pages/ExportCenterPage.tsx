import { useQuery } from '@tanstack/react-query'
import { FileJson, FileSpreadsheet } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card, EmptyState, TableSkeleton, Button } from '@/components/ui'
import { exportPaperUrl, listPapers } from '@/api/client'

export function ExportCenterPage() {
  const { data: papers, isLoading } = useQuery({ queryKey: ['papers'], queryFn: listPapers })
  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  return (
    <div>
      <PageHeader
        title="Export Center"
        description="Download paper metadata and extracted graph summaries for use outside the app."
      />

      <Card>
        <div className="border-b border-border px-5 py-4">
          <h2 className="font-display text-sm font-semibold">Processed papers</h2>
        </div>
        <div className="p-5">
          {isLoading ? (
            <TableSkeleton rows={4} cols={3} />
          ) : completedPapers.length === 0 ? (
            <EmptyState title="Nothing to export yet" description="Papers appear here once they finish processing." />
          ) : (
            <div className="space-y-2">
              {completedPapers.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-lg px-3 py-3 hover:bg-paper-dim">
                  <div>
                    <p className="text-sm font-medium text-ink">{p.title || p.filename}</p>
                    <p className="font-mono text-xs text-ink-faint">{p.num_chunks ?? 0} chunks indexed</p>
                  </div>
                  <div className="flex gap-2">
                    <a href={exportPaperUrl(p.id, 'json')} download>
                      <Button size="sm" variant="secondary"><FileJson className="h-3.5 w-3.5" /> JSON</Button>
                    </a>
                    <a href={exportPaperUrl(p.id, 'csv')} download>
                      <Button size="sm" variant="secondary"><FileSpreadsheet className="h-3.5 w-3.5" /> CSV</Button>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
