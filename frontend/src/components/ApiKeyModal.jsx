import React, { useState } from 'react'

export default function ApiKeyModal({ currentKey, onSave, onClose }) {
  const [key, setKey] = useState(currentKey || '')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (key.trim()) {
      onSave(key.trim())
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal" onClick={e => e.stopPropagation()} onSubmit={handleSubmit}>
        <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px'}}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{color: 'var(--accent)'}}><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg>
          <h2 style={{margin: 0}}>API Configuration</h2>
        </div>
        <p>Enter your Google Gemini API key to enable AI queries.</p>
        <input
          id="api-key-input"
          type="password"
          value={key}
          onChange={e => setKey(e.target.value)}
          placeholder="AIza..."
          autoFocus
        />
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-accent" disabled={!key.trim()}>
            Save Key
          </button>
        </div>
      </form>
    </div>
  )
}
