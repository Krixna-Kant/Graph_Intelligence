import React from 'react'

export default function NodeInspector({ nodeDetails, onNodeClick }) {
  if (!nodeDetails) {
    return (
      <div className="inspector">
        <div className="inspector-empty">
          <div className="icon" style={{marginBottom: '8px', color: 'var(--accent)'}}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
          </div>
          <p>Click a node in the graph to inspect it</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Double-click to expand connections
          </p>
        </div>
      </div>
    )
  }

  const { node, incoming, outgoing } = nodeDetails
  const skipKeys = ['id', 'type', 'label']

  return (
    <div className="inspector">
      {/* Node Header */}
      <div className="node-header">
        <span className={`node-type-badge ${node.type}`}>{node.type}</span>
        <span className="node-label">{node.label || node.id}</span>
      </div>

      {/* Properties */}
      <div className="node-props">
        {Object.entries(node)
          .filter(([k]) => !skipKeys.includes(k) && node[k])
          .map(([k, v]) => (
            <div className="node-prop" key={k}>
              <span className="node-prop-key">{formatKey(k)}</span>
              <span className="node-prop-val">{formatVal(v)}</span>
            </div>
          ))}
      </div>

      {/* Incoming Connections */}
      {incoming?.length > 0 && (
        <>
          <div className="connections-title">↘ Incoming ({incoming.length})</div>
          {incoming.slice(0, 15).map((conn, i) => (
            <div
              key={i}
              className="connection-item"
              onClick={() => onNodeClick(conn.node_id)}
            >
              <span className={`node-type-badge ${conn.node_type}`} style={{fontSize: '0.65rem', padding: '2px 6px'}}>
                {conn.node_type}
              </span>
              <span style={{ flex: 1, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                {conn.node_label}
              </span>
              <span className="connection-rel">{conn.relationship}</span>
            </div>
          ))}
        </>
      )}

      {/* Outgoing Connections */}
      {outgoing?.length > 0 && (
        <>
          <div className="connections-title">↗ Outgoing ({outgoing.length})</div>
          {outgoing.slice(0, 15).map((conn, i) => (
            <div
              key={i}
              className="connection-item"
              onClick={() => onNodeClick(conn.node_id)}
            >
              <span className={`node-type-badge ${conn.node_type}`} style={{fontSize: '0.65rem', padding: '2px 6px'}}>
                {conn.node_type}
              </span>
              <span style={{ flex: 1, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                {conn.node_label}
              </span>
              <span className="connection-rel">{conn.relationship}</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function formatKey(key) {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, s => s.toUpperCase())
    .trim()
}

function formatVal(val) {
  if (val === 'true') return '✓ Yes'
  if (val === 'false') return '✗ No'
  if (typeof val === 'string' && val.match(/^\d{4}-\d{2}-\d{2}T/)) {
    return new Date(val).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })
  }
  return String(val)
}
