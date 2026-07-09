import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Send, Quote } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Button, Card, Spinner, EmptyState, Badge } from '@/components/ui'
import { askQuestion, listPapers, newChatMessage } from '@/api/client'
import type { ChatMessage } from '@/types'

export function ResearchChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [selectedPapers, setSelectedPapers] = useState<string[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: papers } = useQuery({ queryKey: ['papers'], queryFn: listPapers })

  const askMutation = useMutation({
    mutationFn: (question: string) => askQuestion(question, selectedPapers.length ? selectedPapers : undefined),
    onSuccess: (result) => {
      setMessages((prev) => [
        ...prev,
        newChatMessage('assistant', result.answer, result.citations),
      ])
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    },
  })

  const handleSend = () => {
    if (!input.trim() || askMutation.isPending) return
    setMessages((prev) => [...prev, newChatMessage('user', input)])
    askMutation.mutate(input)
    setInput('')
  }

  const completedPapers = papers?.filter((p) => p.status === 'completed') ?? []

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <PageHeader
        title="Research Chat"
        description="Ask questions grounded in your paper library — every answer cites its source chunk."
      />

      {completedPapers.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedPapers([])}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              selectedPapers.length === 0 ? 'bg-graph text-white' : 'bg-paper-dim text-ink-soft hover:text-ink'
            }`}
          >
            All papers
          </button>
          {completedPapers.map((p) => (
            <button
              key={p.id}
              onClick={() =>
                setSelectedPapers((prev) => (prev.includes(p.id) ? prev.filter((id) => id !== p.id) : [...prev, p.id]))
              }
              className={`max-w-[200px] truncate rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                selectedPapers.includes(p.id) ? 'bg-graph text-white' : 'bg-paper-dim text-ink-soft hover:text-ink'
              }`}
            >
              {p.title || p.filename}
            </button>
          ))}
        </div>
      )}

      <Card className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <EmptyState
              title="Ask your first question"
              description={
                completedPapers.length === 0
                  ? 'Upload and process at least one paper first, then come back here.'
                  : 'Try: "What methods do these papers use to evaluate performance?"'
              }
            />
          ) : (
            <div className="space-y-5">
              {messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
              {askMutation.isPending && (
                <div className="flex items-center gap-2 text-sm text-ink-soft">
                  <Spinner className="h-4 w-4 text-graph" /> Retrieving from graph + vector index...
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
        <div className="border-t border-border p-4">
          <div className="flex items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask a question about your library..."
              className="flex-1 rounded-lg border border-border bg-paper px-4 py-2.5 text-sm outline-none focus:border-graph"
            />
            <Button onClick={handleSend} loading={askMutation.isPending} disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[75%] rounded-xl px-4 py-3 ${isUser ? 'bg-graph text-white' : 'bg-paper-dim text-ink'}`}>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-white/10 pt-2">
            {message.citations.slice(0, 6).map((c, i) => (
              <Badge key={i} tone="citation">
                <Quote className="mr-1 h-3 w-3" />
                chunk {c.chunk_index ?? '?'} · p.{c.page ?? '?'}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
