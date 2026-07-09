import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Lightbulb } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Button, Card, EmptyState, Skeleton } from '@/components/ui'
import { analyzeGaps, listPapers } from '@/api/client'
import { PaperMultiSelect } from '@/components/PaperMultiSelect'
import { MarkdownOutput } from '@/components/MarkdownOutput'

export function GapAnalysisPage() {
  const [focusArea, setFocusArea] = useState('')
  const [selectedPapers, setSelectedPapers] = useState<string[]>([])
  const { data: papers } = useQuery({ queryKey: ['papers'], queryFn: listPapers })

  const gapMutation = useMutation({
    mutationFn: () => analyzeGaps(selectedPapers.length ? selectedPapers : undefined, focusArea || undefined),
  })

  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  return (
    <div>
      <PageHeader
        title="Research Gap Analysis"
        description="Surface concrete, source-grounded gaps and promising future directions from your library."
      />

      <Card className="mb-6 p-5">
        <label className="mb-1.5 block text-sm font-medium text-ink">Focus area (optional)</label>
        <input
          value={focusArea}
          onChange={(e) => setFocusArea(e.target.value)}
          placeholder="Leave blank to scan for open problems and future-work sections across all papers"
          className="mb-4 w-full rounded-lg border border-border bg-paper px-4 py-2.5 text-sm outline-none focus:border-graph"
        />
        <label className="mb-1.5 block text-sm font-medium text-ink">Scope (optional)</label>
        <PaperMultiSelect papers={completedPapers} selected={selectedPapers} onChange={setSelectedPapers} />
        <div className="mt-4">
          <Button onClick={() => gapMutation.mutate()} loading={gapMutation.isPending}>
            <Lightbulb className="h-4 w-4" /> Analyze Gaps
          </Button>
        </div>
      </Card>

      {gapMutation.isPending && (
        <Card className="space-y-3 p-6">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </Card>
      )}

      {gapMutation.data && (
        <Card className="p-6">
          <MarkdownOutput content={gapMutation.data.gaps} />
        </Card>
      )}

      {gapMutation.isError && (
        <EmptyState title="Couldn't analyze gaps" description="Ensure your library has at least one fully processed paper." />
      )}
    </div>
  )
}
