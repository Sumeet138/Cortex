export interface Citation {
  source: string
  content_type: string
  authored_at: string | null
  url: string | null
  snippet: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  citations: Citation[]
  isStreaming: boolean
  isError: boolean
}

export interface IngestStats {
  total_chunks: number
  inserted: number
  dupes_skipped: number
}

export type SSEEvent =
  | { type: 'token'; text: string }
  | { type: 'done'; citations: Citation[] }
  | { type: 'error'; text: string }
