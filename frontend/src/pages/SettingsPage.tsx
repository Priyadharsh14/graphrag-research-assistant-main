import { Sun, Moon, Monitor } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui'
import { useTheme } from '@/hooks/useTheme'

export function SettingsPage() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="max-w-2xl">
      <PageHeader title="Settings" description="Appearance and connection preferences for this app." />

      <Card className="mb-6 p-5">
        <h2 className="mb-1 font-display text-sm font-semibold">Appearance</h2>
        <p className="mb-4 text-sm text-ink-soft">Choose how the interface looks.</p>
        <div className="grid grid-cols-3 gap-3">
          {([
            { value: 'light' as const, icon: Sun, label: 'Light' },
            { value: 'system' as const, icon: Monitor, label: 'System' },
            { value: 'dark' as const, icon: Moon, label: 'Dark' },
          ]).map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors ${
                theme === opt.value ? 'border-graph bg-graph-soft text-graph' : 'border-border text-ink-soft hover:bg-paper-dim'
              }`}
            >
              <opt.icon className="h-5 w-5" />
              <span className="text-sm font-medium">{opt.label}</span>
            </button>
          ))}
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-1 font-display text-sm font-semibold">Connection</h2>
        <p className="mb-4 text-sm text-ink-soft">API base URL and provider are configured via environment variables at build/deploy time.</p>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between border-b border-border py-2">
            <dt className="text-ink-soft">API base URL</dt>
            <dd className="font-mono text-xs">{import.meta.env.VITE_API_BASE_URL || '/api/v1'}</dd>
          </div>
          <div className="flex justify-between py-2">
            <dt className="text-ink-soft">Check live service status</dt>
            <dd><a href="/health" className="text-graph hover:underline">Health Dashboard →</a></dd>
          </div>
        </dl>
      </Card>
    </div>
  )
}
