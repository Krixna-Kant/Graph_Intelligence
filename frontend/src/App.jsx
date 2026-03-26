import React, { useState, useEffect, useRef, useCallback } from 'react'
import GraphVisualization from './components/GraphVisualization'
import ChatPanel from './components/ChatPanel'
import NodeInspector from './components/NodeInspector'
import StatsBar from './components/StatsBar'
import ApiKeyModal from './components/ApiKeyModal'
import { NODE_COLORS } from './constants'

const API_BASE = 'http://localhost:8000'

export default function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [selectedNode, setSelectedNode] = useState(null)
  const [nodeDetails, setNodeDetails] = useState(null)
  const [stats, setStats] = useState(null)
  const [activeTab, setActiveTab] = useState('chat')
  const [highlightedNodes, setHighlightedNodes] = useState([])
  const [apiKey, setApiKey] = useState(localStorage.getItem('gemini_api_key') || '')
  const [showApiModal, setShowApiModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Resizer state
  const [sidebarWidth, setSidebarWidth] = useState(420)
  const isDragging = useRef(false)
  
  const startDrag = useCallback(() => { isDragging.current = true }, [])
  const stopDrag = useCallback(() => { isDragging.current = false }, [])
  const onDrag = useCallback((e) => {
    if (!isDragging.current) return
    const newWidth = document.body.clientWidth - e.clientX
    if (newWidth > 300 && newWidth < 800) setSidebarWidth(newWidth)
  }, [])
  
  useEffect(() => {
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', stopDrag)
    return () => {
      window.removeEventListener('mousemove', onDrag)
      window.removeEventListener('mouseup', stopDrag)
    }
  }, [onDrag, stopDrag])

  // ─── Load initial data ──
  useEffect(() => {
    async function init() {
      try {
        const [graphRes, statsRes] = await Promise.all([
          fetch(`${API_BASE}/graph?max_nodes=300`),
          fetch(`${API_BASE}/stats`),
        ])
        if (!graphRes.ok) throw new Error('Failed to load graph')
        const gData = await graphRes.json()
        const sData = await statsRes.json()
        setGraphData(gData)
        setStats(sData)
        setLoading(false)
      } catch (e) {
        setError(e.message)
        setLoading(false)
      }
    }
    init()
  }, [])

  // ─── Node selection handler ──
  const handleNodeClick = useCallback(async (nodeId) => {
    setSelectedNode(nodeId)
    setActiveTab('inspect')
    try {
      const res = await fetch(`${API_BASE}/node/${encodeURIComponent(nodeId)}`)
      if (res.ok) {
        const data = await res.json()
        setNodeDetails(data)
      }
    } catch (e) {
      console.error('Failed to load node details:', e)
    }
  }, [])

  // ─── Node expansion (double-click) ──
  const handleNodeExpand = useCallback(async (nodeId) => {
    try {
      const res = await fetch(`${API_BASE}/neighbors/${encodeURIComponent(nodeId)}?depth=1`)
      if (res.ok) {
        const data = await res.json()
        setGraphData(prev => {
          const existingIds = new Set(prev.nodes.map(n => n.id))
          const newNodes = data.nodes.filter(n => !existingIds.has(n.id))
          const existingEdges = new Set(prev.edges.map(e => `${e.source}-${e.target}`))
          const newEdges = data.edges.filter(e => {
            const key = `${typeof e.source === 'object' ? e.source.id : e.source}-${typeof e.target === 'object' ? e.target.id : e.target}`
            return !existingEdges.has(key)
          })
          return {
            nodes: [...prev.nodes, ...newNodes],
            edges: [...prev.edges, ...newEdges],
          }
        })
      }
    } catch (e) {
      console.error('Failed to expand node:', e)
    }
  }, [])

  // ─── Query result highlighting ──
  const handleQueryResult = useCallback((nodeIds) => {
    if (nodeIds?.length) {
      setHighlightedNodes(nodeIds)
      setTimeout(() => setHighlightedNodes([]), 8000)
    }
  }, [])

  // ─── API key save ──
  const handleSaveApiKey = useCallback((key) => {
    setApiKey(key)
    localStorage.setItem('gemini_api_key', key)
    setShowApiModal(false)
  }, [])

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>Initializing SAP Graph Intelligence Engine...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="loading-screen">
        <p style={{color: 'var(--red)'}}>⚠ {error}</p>
        <p style={{color: 'var(--text-muted)', fontSize: '0.85rem'}}>
          Make sure the backend is running: <code>uvicorn main:app --reload</code>
        </p>
        <button className="btn btn-accent" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="header-logo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
              <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
          </div>
          <h1>Graph Intelligence <span>| SAP ERP</span></h1>
        </div>
        <div className="header-actions">
          <button className="btn" onClick={() => setShowApiModal(true)}>
            <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><line x1="18" y1="8" x2="23" y2="13"></line><line x1="16" y1="16" x2="21" y2="21"></line></svg>
              {apiKey ? 'API Configured' : 'Setup API Key'}
            </div>
          </button>
        </div>
      </header>

      {/* Stats Bar */}
      {stats && <StatsBar stats={stats} />}

      {/* Main: Graph + Right Panel */}
      <div className="main-content">
        <div className="graph-container" id="graph-viz-container">
          <GraphVisualization
            data={graphData}
            onNodeClick={handleNodeClick}
            onNodeExpand={handleNodeExpand}
            highlightedNodes={highlightedNodes}
            selectedNode={selectedNode}
          />
          <div className="graph-overlay">
            {['CUSTOMER', 'PRODUCT', 'SALES_ORDER', 'DELIVERY', 'BILLING', 'JOURNAL', 'PAYMENT'].map(t => (
              <span className="graph-badge" key={t}>
                <span className="dot" style={{background: NODE_COLORS[t]}} />
                {t.replace('_', ' ')}
              </span>
            ))}
          </div>
        </div>

        {/* Draggable Resizer */}
        <div className="resizer" onMouseDown={startDrag} />

        <div className="right-panel" style={{ width: `${sidebarWidth}px` }}>
          <div className="panel-tabs">
            <button
              className={`panel-tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px'}}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                Query
              </div>
            </button>
            <button
              className={`panel-tab ${activeTab === 'inspect' ? 'active' : ''}`}
              onClick={() => setActiveTab('inspect')}
            >
              <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px'}}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                Inspect
              </div>
            </button>
          </div>

          <div className="panel-content">
            {activeTab === 'chat' ? (
              <ChatPanel
                apiBase={API_BASE}
                apiKey={apiKey}
                onQueryResult={handleQueryResult}
                onNeedApiKey={() => setShowApiModal(true)}
              />
            ) : (
              <NodeInspector
                nodeDetails={nodeDetails}
                onNodeClick={handleNodeClick}
              />
            )}
          </div>
        </div>
      </div>

      {/* API Key Modal */}
      {showApiModal && (
        <ApiKeyModal
          currentKey={apiKey}
          onSave={handleSaveApiKey}
          onClose={() => setShowApiModal(false)}
        />
      )}
    </div>
  )
}

