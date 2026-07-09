import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { GitCompare } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Button, Card, EmptyState, Skeleton } from '@/components/ui'
import { comparePapers, listPapers } from '@/api/client'
import { PaperMultiSelect } from '@/components/PaperMultiSelect'
import { MarkdownOutput } from '@/components/MarkdownOutput'

const DEFAULT_ASPECTS = ['methodology', 'datasets', 'key results', 'limitations']

export function PaperComparisonPage() {
  const [selectedPapers, setSelectedPapers] = useState<string[]>([])
  const [aspects, setAspects] = useState<string[]>(DEFAULT_ASPECTS)
  const { data: papers } = useQuery({ queryKey: ['papers'], queryFn: listPapers })

  const compareMutation = useMutation({
    mutationFn: () => comparePapers(selectedPapers, aspects),
  })

  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  return (
    <div>
      <PageHeader
        title="Paper Comparison"
        description="Select two or more papers to generate a structured, aspect-by-aspect comparison."
      />

      <Card className="mb-6 p-5">
        <label className="mb-1.5 block text-sm font-medium text-ink">Papers to compare</label>
        <PaperMultiSelect papers={completedPapers} selected={selectedPapers} onChange={setSelectedPapers} />

        <label className="mb-1.5 mt-4 block text-sm font-medium text-ink">Comparison aspects</label>
        <div className="flex flex-wrap gap-2">
          {DEFAULT_ASPECTS.map((aspect) => (
            <button
              key={aspect}
              onClick={() =>
                setAspects((prev) => (prev.includes(aspect) ? prev.filter((a) => a !== aspect) : [...prev, aspect]))
              }
              className={`rounded-full px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                aspects.includes(aspect) ? 'bg-citation text-white' : 'bg-paper-dim text-ink-soft hover:text-ink'
              }`}
            >
              {aspect}
            </button>
          ))}
        </div>

        <div className="mt-4">
          <Button
            onClick={() => compareMutation.mutate()}
            loading={compareMutation.isPending}
            disabled={selectedPapers.length < 2}
          >
            <GitCompare className="h-4 w-4" /> Compare {selectedPapers.length >= 2 ? `${selectedPapers.length} papers` : ''}
          </Button>
          {selectedPapers.length < 2 && (
            <p className="mt-2 text-xs text-ink-faint">Select at least 2 papers to compare.</p>
          )}
        </div>
      </Card>

      {compareMutation.isPending && (
        <Card className="space-y-3 p-6">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </Card>
      )}

      {compareMutation.data && (
        <Card className="overflow-x-auto p-6">
          <MarkdownOutput content={compareMutation.data.comparison} />
        </Card>
      )}

      {compareMutation.isError && (
        <EmptyState title="Comparison failed" description="Try selecting different papers, or check the Health Dashboard for service status." />
      )}
    </div>
  )
}
