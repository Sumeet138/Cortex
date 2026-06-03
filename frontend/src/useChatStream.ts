import { useState, useCallback } from 'react'
import type { Citation, Message, SSEEvent } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function useChatStream() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)

  const sendMessage = useCallback(
    (question: string, source?: string) => {
      if (isStreaming) return

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        text: question,
        citations: [],
        isStreaming: false,
        isError: false,
      }

      const assistantId = crypto.randomUUID()
      const assistantMsg: Message = {
        id: assistantId,
        role: 'assistant',
        text: '',
        citations: [],
        isStreaming: true,
        isError: false,
      }

      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setIsStreaming(true)

      const params = new URLSearchParams({ q: question, k: '8' })
      if (source) params.set('source', source)

      const es = new EventSource(`${API_BASE}/chat?${params}`)

      const finish = (patch: Partial<Message>) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, ...patch } : m)),
        )
        setIsStreaming(false)
        es.close()
      }

      es.onmessage = (event: MessageEvent<string>) => {
        const data = JSON.parse(event.data) as SSEEvent

        if (data.type === 'token') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, text: m.text + data.text } : m,
            ),
          )
        } else if (data.type === 'done') {
          const citations: Citation[] = data.citations
          finish({ isStreaming: false, citations })
        } else if (data.type === 'error') {
          finish({ text: data.text, isStreaming: false, isError: true })
        }
      }

      es.onerror = () => {
        finish({
          text: 'Connection error — is the server running?',
          isStreaming: false,
          isError: true,
        })
      }
    },
    [isStreaming],
  )

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return { messages, isStreaming, sendMessage, clearMessages }
}
