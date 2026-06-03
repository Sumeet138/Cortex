import { useRef, useEffect, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { useChatStream } from './useChatStream'
import { CitationBadge } from './Citation'
import type { Message } from './types'

const SOURCES = ['linkedin', 'twitter', 'instagram'] as const

interface Props {
  activeSource: string | undefined
  onSourceChange: (s: string | undefined) => void
}

function FormatStreamedText({ text, isStreaming }: { text: string; isStreaming: boolean }) {
  if (!isStreaming) {
    return <>{text}</>
  }
  const tokens = text.split(/(\s+)/)
  return (
    <>
      {tokens.map((token, idx) => {
        if (!token) return null
        if (/\s+/.test(token)) {
          return token
        }
        return (
          <span key={idx} className="word-blur-in">
            {token}
          </span>
        )
      })}
    </>
  )
}

function MessageItem({ m }: { m: Message }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(m.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`message ${m.role}${m.isError ? ' error' : ''}${m.isStreaming ? ' streaming' : ''}`}>
      <div className="message-header">
        {m.role === 'user' ? 'POST /playground/api/query' : m.isError ? 'ERROR · 500' : 'RESPONSE'}
      </div>
      {m.isStreaming && !m.text ? (
        <div className="loader"></div>
      ) : (
        <div className="bubble">
          <FormatStreamedText text={m.text} isStreaming={m.isStreaming} />
          {m.isStreaming && m.text && <span className="cursor" />}
          {m.role === 'assistant' && !m.isError && m.text && (
            <button className="copy-btn" onClick={handleCopy} title="Copy response">
              {copied ? 'COPIED!' : 'COPY'}
            </button>
          )}
        </div>
      )}
      {m.citations.length > 0 && (
        <div className="citations">
          {m.citations.map((c, i) => (
            <CitationBadge key={i} citation={c} />
          ))}
        </div>
      )}
    </div>
  )
}

export function Chat({ activeSource, onSourceChange }: Props) {
  const [input, setInput] = useState('')
  const { messages, isStreaming, sendMessage, clearMessages } = useChatStream()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = () => {
    const q = input.trim()
    if (!q || isStreaming) return
    sendMessage(q, activeSource)
    setInput('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="chat-panel">
      <div className="source-filter">
        <button
          className={activeSource === undefined ? 'active' : ''}
          onClick={() => onSourceChange(undefined)}
        >
          All
        </button>
        {SOURCES.map((s) => (
          <button
            key={s}
            className={activeSource === s ? 'active' : ''}
            onClick={() => onSourceChange(activeSource === s ? undefined : s)}
          >
            {s[0].toUpperCase() + s.slice(1)}
          </button>
        ))}
        <button
          className="new-chat-btn"
          onClick={clearMessages}
          disabled={messages.length === 0 || isStreaming}
          title="Clear chat history"
        >
          New Chat
        </button>
      </div>

      <div className="messages">
        {messages.length === 0 ? (
          <div className="messages-empty">
            <strong>Clone your mind.</strong>
            <p>Upload a data export in the left panel to feed your personal intelligence model, then ask a query to see your reasoning clone in action.</p>
          </div>
        ) : (
          messages.map((m) => (
            <MessageItem key={m.id} m={m} />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a query... (Enter to send, Shift+Enter for newline)"
          disabled={isStreaming}
        />
        <button
          className="send-btn"
          onClick={submit}
          disabled={!input.trim() || isStreaming}
        >
          {isStreaming ? '...' : 'Query →'}
        </button>
      </div>
    </div>
  )
}
