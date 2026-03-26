import React, { useState, useRef, useEffect } from 'react'

export default function ChatPanel({ apiBase, apiKey, onQueryResult, onNeedApiKey }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome! Ask me about your SAP business data. Try:\n- "How many sales orders are there?"\n- "Show top 5 products by revenue"\n- "List customers with pending payments"',
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const q = input.trim()
    if (!q || loading) return

    if (!apiKey) {
      onNeedApiKey()
      return
    }

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)

    try {
      const res = await fetch(`${apiBase}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, api_key: apiKey }),
      })

      const data = await res.json()

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || 'No answer generated.',
        sql: data.sql,
        results: data.results?.slice(0, 10),
        isOffTopic: data.is_off_topic,
        error: data.error,
      }])

      if (data.node_ids?.length) {
        onQueryResult(data.node_ids)
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${e.message}. Is the backend running?`,
        error: 'network',
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

            {msg.sql && (
              <div className="sql-block">{msg.sql}</div>
            )}

            {msg.results?.length > 0 && (
              <table className="results-table">
                <thead>
                  <tr>
                    {Object.keys(msg.results[0]).map(k => (
                      <th key={k}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {msg.results.map((row, ri) => (
                    <tr key={ri}>
                      {Object.values(row).map((v, ci) => (
                        <td key={ci}>{v != null ? String(v) : '—'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-msg assistant">
            <span className="spinner" style={{ marginRight: 8 }} />
            Analyzing your question...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          id="chat-input"
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your SAP data..."
          disabled={loading}
        />
        <button id="send-btn" className="send-btn" onClick={handleSend} disabled={loading || !input.trim()}>
          {loading ? <span className="spinner" /> : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          )}
        </button>
      </div>
    </div>
  )
}
