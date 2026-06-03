import { useState } from 'react'
import { Chat } from './Chat'
import { UploadPanel } from './UploadPanel'

export function App() {
  const [activeSource, setActiveSource] = useState<string | undefined>(undefined)
  return (
    <>
      <nav className="navbar">
        <div className="nav-logo">
          <div className="logo-dot" />
          <span>Cortex</span>
        </div>
        <div className="nav-links">
          <span className="nav-link active">PLAYGROUND</span>
          <a href="https://makecortex.com/#problem" target="_blank" rel="noreferrer" className="nav-link">PROBLEM</a>
          <a href="https://makecortex.com/#cases" target="_blank" rel="noreferrer" className="nav-link">CASES</a>
          <a href="https://makecortex.com/#intelligence" target="_blank" rel="noreferrer" className="nav-link">INTELLIGENCE</a>
        </div>
        <div className="nav-badge">RAG PLAYGROUND</div>
      </nav>
      <div className="layout">
        <UploadPanel />
        <Chat activeSource={activeSource} onSourceChange={setActiveSource} />
      </div>
    </>
  )
}
