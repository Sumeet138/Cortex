import { useState, useRef, useEffect } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import type { IngestStats } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''
const SOURCES = ['linkedin', 'twitter', 'instagram'] as const

type UploadStatus =
  | { type: 'success'; stats: IngestStats }
  | { type: 'error'; message: string }
  | null

interface SeedResult {
  totals: IngestStats
  files: Array<{ file: string; source?: string; inserted?: number; dupes_skipped?: number; error?: string }>
}

export function UploadPanel() {
  const [source, setSource] = useState<string>(SOURCES[0])
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [seeding, setSeeding] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [status, setStatus] = useState<UploadStatus>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const clickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', clickOutside)
    return () => document.removeEventListener('mousedown', clickOutside)
  }, [])

  const pickFile = (f: File) => {
    setFile(f)
    setStatus(null)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) pickFile(f)
  }

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) pickFile(f)
  }

  const upload = async () => {
    if (!file || loading) return
    setLoading(true)
    setStatus(null)

    const body = new FormData()
    body.append('source', source)
    body.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/ingest`, { method: 'POST', body })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText })) as { detail?: string }
        setStatus({ type: 'error', message: err.detail ?? 'Upload failed' })
      } else {
        const stats = (await res.json()) as IngestStats
        setStatus({ type: 'success', stats })
        setFile(null)
        if (inputRef.current) inputRef.current.value = ''
      }
    } catch {
      setStatus({ type: 'error', message: 'Network error — is the server running?' })
    } finally {
      setLoading(false)
    }
  }

  const seedDemo = async () => {
    if (seeding || loading) return
    setSeeding(true)
    setStatus(null)
    try {
      const res = await fetch(`${API_BASE}/seed`, { method: 'POST' })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText })) as { detail?: string }
        setStatus({ type: 'error', message: err.detail ?? 'Seed failed' })
      } else {
        const data = (await res.json()) as SeedResult
        setStatus({ type: 'success', stats: data.totals })
      }
    } catch {
      setStatus({ type: 'error', message: 'Network error — is the server running?' })
    } finally {
      setSeeding(false)
    }
  }

  const clearData = async () => {
    if (clearing || loading || seeding) return
    setClearing(true)
    setStatus(null)
    try {
      const res = await fetch(`${API_BASE}/data`, { method: 'DELETE' })
      if (!res.ok) {
        setStatus({ type: 'error', message: 'Failed to clear data' })
      } else {
        const data = (await res.json()) as { deleted: number }
        setStatus({
          type: 'success',
          stats: { total_chunks: 0, inserted: 0, dupes_skipped: data.deleted },
        })
      }
    } catch {
      setStatus({ type: 'error', message: 'Network error — is the server running?' })
    } finally {
      setClearing(false)
    }
  }

  const dropClass = [
    'drop-zone',
    dragging ? 'drag-over' : '',
    file ? 'has-file' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <aside className="upload-panel">
      <div className="panel-header">
        <span className="panel-mono-tag">01 · Feed It</span>
        <h2>Ingest Export</h2>
      </div>

      {/* ── Quick demo seed ── */}
      <div className="seed-section">
        <span className="panel-mono-tag" style={{ marginBottom: '0.5rem', display: 'block' }}>
          Quick Start
        </span>
        <p className="seed-description">
          Load sample data — LinkedIn posts, Twitter, Instagram — across all three platforms. One click, no file needed.
        </p>
        <button
          className="btn btn-seed"
          onClick={seedDemo}
          disabled={seeding || loading}
          style={seeding ? { display: 'flex', justifyContent: 'center', alignItems: 'center' } : undefined}
        >
          {seeding ? <div className="data-loader"></div> : '⚡ Load Demo Data'}
        </button>
        {seeding && (
          <p className="seed-hint">Embedding via Vertex AI — batched + concurrent. Watch the backend terminal for live progress.</p>
        )}
      </div>

      <div className="divider" />

      <div className="form-group">
        <label className="form-label">Platform Source</label>
        <div className="custom-select-container" ref={dropdownRef}>
          <div
            className={`custom-select-trigger${dropdownOpen ? ' open' : ''}`}
            onClick={() => setDropdownOpen(!dropdownOpen)}
          >
            <span>{source[0].toUpperCase() + source.slice(1)}</span>
            <span className="custom-select-arrow">↓</span>
          </div>
          <div className={`custom-options${dropdownOpen ? ' open' : ''}`}>
            {SOURCES.map((s) => (
              <div
                key={s}
                className={`custom-option${source === s ? ' selected' : ''}`}
                onClick={() => {
                  setSource(s)
                  setDropdownOpen(false)
                }}
              >
                {s[0].toUpperCase() + s.slice(1)}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Data File</label>
        <div
          className={dropClass}
          onDragOver={(e: DragEvent) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
        >
          {file ? `📄 ${file.name}` : 'Drop export file\nor click to browse'}
          <input
            ref={inputRef}
            type="file"
            accept=".zip,.json,.csv,.js,.html"
            style={{ display: 'none' }}
            onChange={onFileChange}
          />
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={upload}
        disabled={!file || loading}
      >
        {loading ? 'Ingesting…' : 'Ingest'}
      </button>

      {status?.type === 'success' && status.stats.inserted > 0 && (
        <div className="upload-result success">
          ✓ {status.stats.inserted} chunks inserted
          {status.stats.dupes_skipped > 0 &&
            ` (${status.stats.dupes_skipped} dupe${status.stats.dupes_skipped !== 1 ? 's' : ''} skipped)`}
        </div>
      )}
      {status?.type === 'success' && status.stats.inserted === 0 && status.stats.dupes_skipped > 0 && (
        <div className="upload-result success">
          ✓ {status.stats.dupes_skipped} chunks cleared
        </div>
      )}
      {status?.type === 'error' && (
        <div className="upload-result error">✗ {status.message}</div>
      )}

      <div style={{ marginTop: 'auto', paddingTop: '0.5rem' }}>
        <button
          className="btn-clear"
          onClick={clearData}
          disabled={clearing || loading || seeding}
        >
          {clearing ? 'Clearing…' : '🗑 Clear All Data'}
        </button>
      </div>
    </aside>
  )
}
