import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ForceGraph2D from 'react-force-graph-2d'
import { PageHeader } from '@/components/PageHeader'
import { Card, EmptyState, Skeleton } from '@/components/ui'
import { getPaperGraph, listPapers } from '@/api/client'
import { useTheme } from '@/hooks/useTheme'

interface GraphNode { id: string; label: string; type: 'paper' | 'chunk' | 'entity' }
interface GraphLink { source: string; target: string; label: string }

export function KnowledgeGraphPage() {
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null)
  const { resolvedTheme } = useTheme()
  const { data: papers } = useQuery({ queryKey: ['papers'], queryFn: listPapers })
  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  const { data: graphData, isLoading } = useQuery({
    queryKey: ['paper-graph', selectedPaperId],
    queryFn: () => getPaperGraph(selectedPaperId!),
    enabled: !!selectedPaperId,
  })

  const { nodes, links } = useMemo(() => buildGraph(graphData?.data ?? []), [graphData])

  const isDark = resolvedTheme === 'dark'
  const nodeColors: Record<string, string> = {
    paper: '#C08A2E', chunk: isDark ? '#565a6e' : '#c9c7bc', entity: '#5B54E8',
  }

  return (
    <div>
      <PageHeader
        title="Knowledge Graph"
        description="Visualize how a paper's chunks, entities, and relationships connect."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {completedPapers.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelectedPaperId(p.id)}
            className={`max-w-[220px] truncate rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              selectedPaperId === p.id ? 'bg-graph text-white' : 'bg-paper-dim text-ink-soft hover:text-ink'
            }`}
          >
            {p.title || p.filename}
          </button>
        ))}
      </div>

      <Card className="h-[600px] overflow-hidden">
        {!selectedPaperId ? (
          <div className="flex h-full items-center justify-center">
            <EmptyState title="Select a paper" description="Choose a paper above to render its knowledge graph." />
          </div>
        ) : isLoading ? (
          <div className="p-6"><Skeleton className="h-full w-full" /></div>
        ) : nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <EmptyState title="No graph data" description="This paper didn't yield entities to visualize." />
          </div>
        ) : (
          <ForceGraph2D
            graphData={{ nodes, links }}
            nodeLabel={(n: any) => `${n.label} (${n.type})`}
            nodeColor={(n: any) => nodeColors[n.type]}
            nodeVal={(n: any) => (n.type === 'paper' ? 8 : n.type === 'entity' ? 4 : 2)}
            linkColor={() => (isDark ? '#2a2b38' : '#e4e2da')}
            linkLabel={(l: any) => l.label}
            backgroundColor="transparent"
            width={800}
            height={600}
          />
        )}
      </Card>
      <div className="mt-3 flex gap-4 text-xs text-ink-soft">
        <LegendDot color="#C08A2E" label="Paper" />
        <LegendDot color="#5B54E8" label="Entity" />
        <LegendDot color="#9a9a9a" label="Chunk" />
      </div>
    </div>
  )
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  )
}

function buildGraph(records: any[]): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodeMap = new Map<string, GraphNode>()
  const links: GraphLink[] = []

  for (const rec of records) {
    const p = rec.p, c = rec.c, e = rec.e, e2 = rec.e2, r = rec.r
    if (p?.id) nodeMap.set(`paper:${p.id}`, { id: `paper:${p.id}`, label: p.title || 'Paper', type: 'paper' })
    if (c?.id) {
      nodeMap.set(`chunk:${c.id}`, { id: `chunk:${c.id}`, label: `Chunk ${c.chunk_index ?? ''}`, type: 'chunk' })
      if (p?.id) links.push({ source: `paper:${p.id}`, target: `chunk:${c.id}`, label: 'HAS_CHUNK' })
    }
    if (e?.name) {
      nodeMap.set(`entity:${e.name}`, { id: `entity:${e.name}`, label: e.name, type: 'entity' })
      if (c?.id) links.push({ source: `chunk:${c.id}`, target: `entity:${e.name}`, label: 'MENTIONS' })
    }
    if (e2?.name) {
      nodeMap.set(`entity:${e2.name}`, { id: `entity:${e2.name}`, label: e2.name, type: 'entity' })
      if (e?.name) links.push({ source: `entity:${e.name}`, target: `entity:${e2.name}`, label: r?.type || 'RELATES_TO' })
    }
  }

  return { nodes: Array.from(nodeMap.values()), links }
}
