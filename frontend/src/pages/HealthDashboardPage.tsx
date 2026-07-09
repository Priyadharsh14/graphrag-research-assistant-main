import { useQuery } from '@tanstack/react-query'
import { Database, Network, Server, HardDrive, CheckCircle2, XCircle } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card, Badge } from '@/components/ui'
import { getHealth } from '@/api/client'

const SERVICES = [
  { key: 'database' as const, label: 'Metadata Database', icon: HardDrive, description: 'Papers, jobs, and ingestion state' },
  { key: 'neo4j' as const, label: 'Neo4j', icon: Network, description: 'Knowledge graph store' },
  { key: 'qdrant' as const, label: 'Qdrant', icon: Server, description: 'Vector index for semantic search' },
  { key: 'redis' as const, label: 'Redis', icon: Database, description: 'Celery broker and result backend' },
]

export function HealthDashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10_000,
  })

  return (
    <div>
      <PageHeader
        title="Health Dashboard"
        description="Live status of every backing service this app depends on."
        action={
          data && (
            <Badge tone={data.status === 'healthy' ? 'success' : 'danger'}>
              {data.status === 'healthy' ? 'All systems operational' : 'Degraded'}
            </Badge>
          )
        }
      />

      {isError && (
        <Card className="mb-6 border-danger/30 bg-danger-soft p-4 text-sm text-danger">
          Could not reach the API. Is the backend running?
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4">
        {SERVICES.map((service) => {
          const isUp = data?.[service.key]
          return (
            <Card key={service.key} className="p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-paper-dim">
                    <service.icon className="h-5 w-5 text-ink-soft" />
                  </div>
                  <div>
                    <p className="font-medium text-ink">{service.label}</p>
                    <p className="text-xs text-ink-faint">{service.description}</p>
                  </div>
                </div>
                {isLoading ? null : isUp ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <XCircle className="h-5 w-5 text-danger" />
                )}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
