import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Quote, ArrowRight } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card, Badge, EmptyState, TableSkeleton } from '@/components/ui'
import { getCitationExplorer, listPapers } from '@/api/client'

export function CitationExplorerPage() {
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null)
  const { data: papers } = useQuery({ queryKey: ['papers'], queryFn: listPapers })
  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  const { data: explorerData, isLoading } = useQuery({
    queryKey: ['citations', selectedPaperId],
    queryFn: () => getCitationExplorer(selectedPaperId!),
    enabled: !!selectedPaperId,
  })

  return (
    <div>
      <PageHeader
        title="Citation Explorer"
        description="Browse the entities a paper mentions and how they relate to concepts elsewhere in your graph."
      />

      {completedPapers.length === 0 ? (
        <EmptyState title="No processed papers yet" description="Upload and process a paper first." />
      ) : (
        <div className="grid grid-cols-[280px_1fr] gap-6">
          <Card className="h-fit p-2">
            {completedPapers.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedPaperId(p.id)}
                className={`block w-full truncate rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  selectedPaperId === p.id ? 'bg-graph-soft text-graph font-medium' : 'text-ink-soft hover:bg-paper-dim'
                }`}
              >
                {p.title || p.filename}
              </button>
            ))}
          </Card>

          <Card className="p-5">
            {!selectedPaperId ? (
              <EmptyState title="Select a paper" description="Choose a paper from the list to explore its entities and citations." />
            ) : isLoading ? (
              <TableSkeleton rows={6} cols={2} />
            ) : explorerData && Object.keys(explorerData.entities).length > 0 ? (
              <div className="space-y-5">
                <div>
                  <h3 className="mb-3 font-display text-sm font-semibold">Entities mentioned</h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(explorerData.entities).map(([name, type]) => (
                      <Badge key={name} tone="graph">
                        {name} <span className="ml-1 opacity-60">· {type}</span>
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="thread-divider" />
                <div>
                  <h3 className="mb-3 font-display text-sm font-semibold">Relationships</h3>
                  {explorerData.relations.length === 0 ? (
                    <p className="text-sm text-ink-faint">No cross-entity relationships extracted for this paper.</p>
                  ) : (
                    <div className="space-y-2">
                      {explorerData.relations.map((rel, i) => (
                        <div key={i} className="flex items-center gap-2 rounded-lg bg-paper-dim px-3 py-2 text-sm">
                          <Quote className="h-3.5 w-3.5 shrink-0 text-citation" />
                          <span className="font-mono text-xs text-ink-soft">{rel.relation}</span>
                          <ArrowRight className="h-3.5 w-3.5 text-ink-faint" />
                          <span className="font-medium">{rel.target}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <EmptyState title="No entities found" description="This paper may not have yielded extractable entities." />
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
