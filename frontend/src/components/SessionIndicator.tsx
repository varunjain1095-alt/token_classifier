import React from 'react'
import { useAuth } from '../context/AuthContext'

const SessionIndicator: React.FC = () => {
  const { session, isLoading, clearSession } = useAuth()

  if (isLoading) {
    return <span className="chip chip-neutral">Loading session…</span>
  }

  if (!session) {
    return <span className="chip chip-danger">No active session</span>
  }

  const isAnon = session.sessionType === 'anonymous'
  const label = isAnon ? 'Anonymous' : 'Signed In'
  const title = [
    `Session: ${session.sessionId}`,
    session.userId ? `User: ${session.userId}` : null,
    session.projectId ? `Project: ${session.projectId}` : null,
    session.expiresAt ? `Expires: ${new Date(session.expiresAt).toLocaleString()}` : null,
    isAnon ? `Free preview: ${session.freePreviewUsed ? 'Used' : 'Available'}` : null,
  ].filter(Boolean).join('\n')

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
      <span
        className={`chip ${isAnon ? 'chip-warning' : 'chip-success'}`}
        title={title}
      >
        {isAnon ? '👤' : '🔐'} {label}
      </span>
      <button
        className="btn btn-danger"
        style={{ padding: '4px 10px', fontSize: '12px' }}
        onClick={clearSession}
        title="Clear session"
      >
        Clear
      </button>
    </span>
  )
}

export default SessionIndicator
