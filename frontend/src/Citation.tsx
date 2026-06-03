import type { Citation } from './types'

export function CitationBadge({ citation }: { citation: Citation }) {
  const label = [
    citation.source,
    citation.authored_at ? citation.authored_at.slice(0, 7) : null,
  ]
    .filter(Boolean)
    .join(' · ')

  if (citation.url) {
    return (
      <a
        className="citation"
        href={citation.url}
        target="_blank"
        rel="noreferrer"
        title={citation.snippet}
      >
        {label}
      </a>
    )
  }
  return (
    <span className="citation" title={citation.snippet}>
      {label}
    </span>
  )
}
