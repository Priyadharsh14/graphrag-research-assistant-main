import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { BookOpen } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Button, Card, EmptyState, Skeleton } from '@/components/ui'
import { generateLiteratureReview, listPapers } from '@/api/client'
import { PaperMultiSelect } from '@/components/PaperMultiSelect'
import { MarkdownOutput } from '@/components/MarkdownOutput'

export function LiteratureReviewPage() {
  const [topic, setTopic] = useState('')
  const [selectedPapers, setSelectedPapers] = useState<string[]>([])
  const { data: papers } = useQuery({ queryKey: ['papers'], queryFn: listPapers })

  const reviewMutation = useMutation({
    mutationFn: () => generateLiteratureReview(topic, selectedPapers.length ? selectedPapers : undefined),
  })

  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  return (
    <div>
      <PageHeader
        title="Literature Review"
        description="Generate a theme-organized synthesis across your library, with sources cited inline."
      />

      <Card className="mb-6 p-5">
        <label className="mb-1.5 block text-sm font-medium text-ink">Review topic</label>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. Transformer-based approaches to long-context retrieval"
          className="mb-4 w-full rounded-lg border border-border bg-paper px-4 py-2.5 text-sm outline-none focus:border-graph"
        />
        <label className="mb-1.5 block text-sm font-medium text-ink">Scope (optional)</label>
        <PaperMultiSelect papers={completedPapers} selected={selectedPapers} onChange={setSelectedPapers} />
        <div className="mt-4">
          <Button onClick={() => reviewMutation.mutate()} loading={reviewMutation.isPending} disabled={!topic.trim()}>
            <BookOpen className="h-4 w-4" /> Generate Review
          </Button>
        </div>
      </Card>

      {reviewMutation.isPending && (
        <Card className="space-y-3 p-6">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </Card>
      )}

      {reviewMutation.data && (
        <Card className="p-6">
          <MarkdownOutput content={reviewMutation.data.review} />
        </Card>
      )}

      {reviewMutation.isError && (
        <EmptyState title="Couldn't generate a review" description="Make sure you have processed papers relevant to this topic, then try again." />
      )}
    </div>
  )
}
