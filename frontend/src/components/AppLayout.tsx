import { NavLink, Outlet } from 'react-router-dom'
import {
  Upload, MessageSquare, BookOpen, GitCompare, Lightbulb,
  Quote, Share2, Settings as SettingsIcon, Activity, Download, Sun, Moon, Monitor,
} from 'lucide-react'
import clsx from 'clsx'
import { useTheme } from '@/hooks/useTheme'

const NAV_ITEMS = [
  { to: '/', label: 'Upload & Library', icon: Upload },
  { to: '/chat', label: 'Research Chat', icon: MessageSquare },
  { to: '/literature-review', label: 'Literature Review', icon: BookOpen },
  { to: '/compare', label: 'Paper Comparison', icon: GitCompare },
  { to: '/gaps', label: 'Research Gap Analysis', icon: Lightbulb },
  { to: '/citations', label: 'Citation Explorer', icon: Quote },
  { to: '/graph', label: 'Knowledge Graph', icon: Share2 },
  { to: '/health', label: 'Health Dashboard', icon: Activity },
  { to: '/export', label: 'Export Center', icon: Download },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

export function AppLayout() {
  return (
    <div className="flex h-screen w-full bg-paper text-ink">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function Sidebar() {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-ink text-paper">
      <div className="flex items-center gap-2.5 px-6 py-6">
        <GraphMark />
        <div>
          <p className="font-display text-sm font-semibold leading-tight">GraphRAG</p>
          <p className="text-[11px] leading-tight text-paper/50">Research Assistant</p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors',
                isActive ? 'bg-white/10 text-white font-medium' : 'text-paper/60 hover:bg-white/5 hover:text-white'
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-white/10 px-3 py-4">
        <ThemeSwitcher />
      </div>
    </aside>
  )
}

function GraphMark() {
  // Signature mark: three connected nodes — the product's core primitive.
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <circle cx="7" cy="8" r="3" fill="#8B85FF" />
      <circle cx="21" cy="8" r="3" fill="#E0AB52" />
      <circle cx="14" cy="21" r="3" fill="#8B85FF" />
      <path d="M9.5 9.5L18.5 9.5M8.5 10.5L13 19M19.5 10.5L15 19" stroke="#4A4D5E" strokeWidth="1.2" />
    </svg>
  )
}

function ThemeSwitcher() {
  const { theme, setTheme } = useTheme()
  const options = [
    { value: 'light' as const, icon: Sun },
    { value: 'system' as const, icon: Monitor },
    { value: 'dark' as const, icon: Moon },
  ]
  return (
    <div className="flex items-center gap-1 rounded-lg bg-white/5 p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => setTheme(opt.value)}
          className={clsx(
            'flex flex-1 items-center justify-center rounded-md py-1.5 transition-colors',
            theme === opt.value ? 'bg-white/15 text-white' : 'text-paper/50 hover:text-white'
          )}
          aria-label={`${opt.value} theme`}
        >
          <opt.icon className="h-3.5 w-3.5" />
        </button>
      ))}
    </div>
  )
}
