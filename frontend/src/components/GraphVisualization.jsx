import React, { useRef, useEffect, useCallback } from 'react'
import * as d3 from 'd3'
import { NODE_COLORS } from '../constants'

const NODE_RADIUS = {
  CUSTOMER: 12,
  PRODUCT: 6,
  SALES_ORDER: 10,
  DELIVERY: 9,
  BILLING: 8,
  JOURNAL: 7,
  PAYMENT: 7,
}

export default function GraphVisualization({ data, onNodeClick, onNodeExpand, highlightedNodes, selectedNode }) {
  const svgRef = useRef(null)
  const simRef = useRef(null)

  useEffect(() => {
    if (!data?.nodes?.length) return

    const container = document.getElementById('graph-viz-container')
    if (!container) return
    const width = container.clientWidth
    const height = container.clientHeight

    // Clone data to avoid D3 mutating React state props directly
    const nodesData = data.nodes.map(d => ({ ...d }))
    const edgesData = data.edges.map(d => ({ ...d }))

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    // Zoom behavior
    const g = svg.append('g')
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => g.attr('transform', event.transform))
    svg.call(zoom)

    // Initial zoom to fit
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.6))

    // Simulation
    const simulation = d3.forceSimulation(nodesData)
      .force('link', d3.forceLink(edgesData).id(d => d.id).distance(60).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-100))
      .force('center', d3.forceCenter(0, 0))
      .force('collision', d3.forceCollide().radius(d => (NODE_RADIUS[d.type] || 8) + 4))

    simRef.current = simulation

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(edgesData)
      .join('line')
      .attr('class', 'link-line')

    // Node groups
    const node = g.append('g')
      .selectAll('g')
      .data(nodesData)
      .join('g')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null; d.fy = null
        })
      )

    // Node circles
    node.append('circle')
      .attr('class', 'node-circle')
      .attr('r', d => NODE_RADIUS[d.type] || 8)
      .attr('fill', d => NODE_COLORS[d.type] || '#6366f1')
      .attr('stroke', d => d.id === selectedNode ? '#fff' : 'rgba(255,255,255,0.1)')
      .attr('stroke-width', d => d.id === selectedNode ? 2.5 : 1)
      .attr('opacity', 0.85)
      .on('click', (event, d) => {
        event.stopPropagation()
        onNodeClick(d.id)
      })
      .on('dblclick', (event, d) => {
        event.stopPropagation()
        onNodeExpand(d.id)
      })

    // Labels (only for larger nodes)
    node.filter(d => ['CUSTOMER', 'SALES_ORDER', 'DELIVERY'].includes(d.type))
      .append('text')
      .attr('class', 'node-label-text')
      .attr('dy', d => (NODE_RADIUS[d.type] || 8) + 12)
      .text(d => d.label ? (d.label.length > 12 ? d.label.slice(0, 12) + '…' : d.label) : '')

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => simulation.stop()
  }, [data, selectedNode])

  // Highlight effect
  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)

    svg.selectAll('.node-circle')
      .attr('filter', d => highlightedNodes.includes(d.id) ? 'drop-shadow(0 0 12px gold)' : null)
      .attr('stroke', d => {
        if (d.id === selectedNode) return '#000'
        if (highlightedNodes.includes(d.id)) return '#f59e0b'
        return '#fff'
      })
      .attr('stroke-width', d => {
        if (d.id === selectedNode) return 3
        if (highlightedNodes.includes(d.id)) return 3
        return 1.5
      })
  }, [highlightedNodes, selectedNode])

  return <svg ref={svgRef} />
}
