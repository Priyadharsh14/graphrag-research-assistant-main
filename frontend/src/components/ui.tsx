import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import clsx from 'clsx'

// --- Button ---
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}

export function Button({ variant = 'primary', size = 'md', loading, className, children, disabled, ...props }: ButtonProps) {
  const base = 'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100'
  const variants: Record<string, string> = {
    primary: 'bg-graph text-white hover:bg-graph/90 shadow-sm shadow-graph/20',
    secondary: 'bg-surface text-ink border border-border hover:bg-paper-dim',
    ghost: 'text-ink-soft hover:bg-paper-dim hover:text-ink',
    danger: 'bg-danger text-white hover:bg-danger/90',
  }
  const sizes: Record<string, string> = {
    sm: 'text-xs px-3 py-1.5',
    md: 'text-sm px-4 py-2',
    lg: 'text-base px-6 py-3',
  }
  return (
    <button
      className={clsx(base, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {children}
    </button>
  )
}

// --- Spinner ---
export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={clsx('animate-spin', className)} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-90" fill="currentColor" d="M12 2a10 10 0 0 1 10 10h-3a7 7 0 0 0-7-7V2z" />
    </svg>
  )
}

// --- Card ---
export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx('rounded-xl border border-border bg-surface shadow-sm', className)}>
      {children}
    </div>
  )
}

// --- Badge ---
type BadgeTone = 'neutral' | 'success' | 'danger' | 'graph' | 'citation'
export function Badge({ tone = 'neutral', children }: { tone?: BadgeTone; children: ReactNode }) {
  const tones: Record<BadgeTone, string> = {
    neutral: 'bg-paper-dim text-ink-soft',
    success: 'bg-success-soft text-success',
    danger: 'bg-danger-soft text-danger',
    graph: 'bg-graph-soft text-graph',
    citation: 'bg-citation-soft text-citation',
  }
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', tones[tone])}>
      {children}
    </span>
  )
}

// --- ProgressBar ---
export function ProgressBar({ value, tone = 'graph' }: { value: number; tone?: 'graph' | 'success' | 'danger' }) {
  const colors: Record<string, string> = { graph: 'bg-graph', success: 'bg-success', danger: 'bg-danger' }
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper-dim">
      <div
        className={clsx('h-full rounded-full transition-all duration-500 ease-out', colors[tone])}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}

// --- Skeleton ---
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse-soft rounded-md bg-paper-dim', className)} />
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

// --- ThreadDivider (signature element) ---
export function ThreadDivider({ className }: { className?: string }) {
  return <div className={clsx('thread-divider', className)} />
}

// --- Empty state ---
export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-center">
      <p className="font-display text-base font-semibold text-ink">{title}</p>
      <p className="max-w-sm text-sm text-ink-soft">{description}</p>
      {action}
    </div>
  )
}
