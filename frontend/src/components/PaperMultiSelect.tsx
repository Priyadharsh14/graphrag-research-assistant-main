import type { Paper } from '@/types'

export function PaperMultiSelect({
  papers, selected, onChange,
}: { papers: Paper[]; selected: string[]; onChange: (ids: string[]) => void }) {
  if (papers.length === 0) {
    return <p className="text-sm text-ink-faint">No processed papers yet — upload one in the Library first.</p>
  }
  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id])
  }
  return (
    <div className="flex flex-wrap gap-2">
      {papers.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => toggle(p.id)}
          className={`max-w-[220px] truncate rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
            selected.includes(p.id) ? 'bg-graph text-white' : 'bg-paper-dim text-ink-soft hover:text-ink'
          }`}
        >
          {p.title || p.filename}
        </button>
      ))}
    </div>
  )
}
