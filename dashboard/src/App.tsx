import { useEffect, useState, useRef } from 'react'
import { Server, Zap, Shield, CreditCard, X, Play } from 'lucide-react'

type LogEvent = {
  action: string
  result_summary?: string
  timestamp?: number
}

function App() {
  const [identity, setIdentity] = useState<any>(null)
  const [tools, setTools] = useState<any[]>([])
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [showBillingModal, setShowBillingModal] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Fetch initial state
    fetch('/api/identity').then(r => r.json()).then(setIdentity)
    fetch('/api/tools').then(r => r.json()).then(setTools)
    fetch('/api/memory/episodes?limit=10').then(r => r.json()).then(data => {
      // Populate logs with recent memory episodes
      setLogs(data.map((ep: any) => ({
        action: ep.action,
        result_summary: ep.result_summary,
        timestamp: ep.timestamp_ns ? Math.floor(ep.timestamp_ns / 1000000) : Date.now()
      })).reverse())
    })

    // Subscribe to SSE
    const evtSource = new EventSource('/api/events')
    evtSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setLogs(prev => [...prev, {
        action: data.action || 'unknown',
        result_summary: data.result_summary || data.message || '',
        timestamp: Date.now()
      }])
    }

    return () => {
      evtSource.close()
    }
  }, [])

  useEffect(() => {
    // Auto-scroll
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const [toolUrl, setToolUrl] = useState('')
  const [isRegistering, setIsRegistering] = useState(false)

  const handleRegisterTool = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!toolUrl.trim()) return
    setIsRegistering(true)
    try {
      const res = await fetch(`/api/tools/add?url=${encodeURIComponent(toolUrl)}`, { method: 'POST' })
      if (!res.ok) {
        const err = await res.json()
        alert("Error registering tool: " + err.detail)
      } else {
        fetch('/api/tools').then(r => r.json()).then(setTools)
        setToolUrl('')
      }
    } catch (err) {
      alert("Network error: " + String(err))
    } finally {
      setIsRegistering(false)
    }
  }

  return (
    <div className="dashboard-container">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Server size={16} /> AgentPhased Dashboard
        </div>
        <div>
          <span className="badge" style={{ borderColor: 'var(--fg-muted)', color: 'var(--fg-muted)' }}>v0.1.0-alpha</span>
        </div>
      </header>

      <aside className="sidebar">
        <div className="pane">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Shield size={14} /> Identity</h2>
          {identity ? (
            <div className="property-list">
              <span className="property-label">Name</span>
              <span className="property-value">{identity.name}</span>
              <span className="property-label">Project</span>
              <span className="property-value">{identity.project}</span>
              <span className="property-label">Fingerprint</span>
              <span className="property-value">{identity.fingerprint}</span>
              <span className="property-label">Public Key</span>
              <span className="property-value" style={{ fontSize: '10px' }}>{identity.public_key_hex}</span>
            </div>
          ) : (
            <div style={{ fontSize: '13px', color: 'var(--fg-muted)' }}>Loading...</div>
          )}
        </div>

        <div className="pane">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><CreditCard size={14} /> Billing & Access</h2>
          <div className="billing-message">
            <strong>Status: Fully Open Source.</strong><br/><br/>
            Tier enforcement hooks are compiled into the core runtime engine to support downstream multi-tenant enterprise architectures, but all local usage restrictions are bypassed by default.
          </div>
          <button onClick={() => setShowBillingModal(true)}>View Infrastructure Settings</button>
        </div>

        <div className="pane">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Zap size={14} /> Tool Registry</h2>
          {tools.length === 0 ? (
            <div style={{ fontSize: '13px', color: 'var(--fg-muted)', marginBottom: '16px' }}>No tools registered.</div>
          ) : (
            tools.map((t, i) => (
              <div key={i} className="tool-item">
                <div className="tool-item-name">{t.name || 'Unknown Tool'}</div>
                <div className="tool-item-url">{t.url || t}</div>
              </div>
            ))
          )}
          <form onSubmit={handleRegisterTool} style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <input 
              type="text" 
              value={toolUrl} 
              onChange={e => setToolUrl(e.target.value)} 
              placeholder="OpenAPI URL or path..."
              style={{ flexGrow: 1, padding: '8px', border: '1px solid var(--border-color)', fontFamily: 'var(--font-sans)', fontSize: '13px' }}
            />
            <button type="submit" disabled={isRegistering} style={{ padding: '8px 12px' }}>
              {isRegistering ? '...' : <Play size={14} />}
            </button>
          </form>
        </div>
      </aside>

      <main className="main-content">
        <div className="log-container">
          <div style={{ marginBottom: '16px', color: 'var(--fg-muted)', textTransform: 'uppercase', fontSize: '11px', letterSpacing: '0.05em' }}>
            Live Event Stream [SSE connected]
          </div>
          {logs.map((log, i) => (
            <div key={i} className="log-entry">
              <span className="log-time">[{new Date(log.timestamp || Date.now()).toISOString().split('T')[1].slice(0,-1)}]</span>
              <span className="log-action">{log.action}</span>
              {log.result_summary && (
                <span className="log-summary">↳ {log.result_summary}</span>
              )}
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </main>

      {showBillingModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0 }}>Infrastructure State</h2>
              <button style={{ padding: '4px', border: 'none', background: 'transparent', color: 'var(--fg-color)' }} onClick={() => setShowBillingModal(false)}>
                <X size={16} />
              </button>
            </div>
            <div style={{ fontSize: '13px', lineHeight: '1.6', marginBottom: '24px' }}>
              <p><strong>Environment:</strong> LOCAL_DEV</p>
              <p><strong>Active Tier:</strong> UNLIMITED</p>
              <p><strong>Stripe Mock:</strong> READY</p>
              <br/>
              <p style={{ color: 'var(--fg-muted)' }}>Enterprise telemetry and enforcement hooks are currently bypassed. To simulate a paywall restriction, set FORCE_TIER=free in your environment.</p>
            </div>
            <button onClick={() => setShowBillingModal(false)} style={{ width: '100%' }}>Acknowledge</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
