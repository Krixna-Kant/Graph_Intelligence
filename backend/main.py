"""
main.py — FastAPI Backend for Graph-based SAP Query System
Provides REST endpoints for graph traversal, NL→SQL queries,
schema introspection, and dataset statistics.
"""
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import ingest_all, build_graph, get_schema, graph_to_json, get_stats, execute_query, get_table_sample
from llm_engine import handle_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Global State ──────────────────────────────────────────────────────
_graph = None
_schema = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ingest data and build graph."""
    global _graph, _schema
    logger.info("Starting SAP Graph Intelligence Engine...")

    # Ingest all JSONL data into SQLite
    results = ingest_all()
    total = sum(results.values())
    logger.info(f"Ingested {total} total records across {len(results)} tables")
    for table, count in results.items():
        logger.info(f"   {table}: {count} records")

    # Build knowledge graph
    _graph = build_graph()
    logger.info(
        f"Graph built: {_graph.number_of_nodes()} nodes, "
        f"{_graph.number_of_edges()} edges"
    )

    # Cache schema
    _schema = get_schema()
    logger.info("Schema cached for LLM context")

    yield

    logger.info("Shutting down...")


# ─── App Setup ─────────────────────────────────────────────────────────
app = FastAPI(
    title="SAP Graph Intelligence API",
    description="Graph-based business intelligence system for SAP ERP data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ──────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    api_key: Optional[str] = None


class QueryResponse(BaseModel):
    question: str = ""
    sql: Optional[str] = None
    results: list = []
    answer: str = ""
    is_off_topic: bool = False
    node_ids: list = []
    error: Optional[str] = None


# ─── Endpoints ─────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Health check with system stats."""
    return {
        "status": "healthy",
        "graph_nodes": _graph.number_of_nodes() if _graph else 0,
        "graph_edges": _graph.number_of_edges() if _graph else 0,
        "tables": get_stats(),
    }


@app.get("/graph")
async def get_graph(max_nodes: int = Query(default=200, ge=1, le=2000)):
    """Get serialized graph data for visualization."""
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not yet built.")
    return graph_to_json(_graph, max_nodes=max_nodes)


@app.get("/schema")
async def schema():
    """Get database schema."""
    return {"schema": _schema or "Schema not loaded"}


@app.get("/stats")
async def stats():
    """Get per-table row counts and graph summary."""
    table_stats = get_stats()

    # Aggregate stats
    summary = {
        "total_records": sum(table_stats.values()),
        "total_tables": len(table_stats),
        "graph_nodes": _graph.number_of_nodes() if _graph else 0,
        "graph_edges": _graph.number_of_edges() if _graph else 0,
    }

    # Node type counts
    if _graph:
        type_counts = {}
        for _, data in _graph.nodes(data=True):
            ntype = data.get("type", "UNKNOWN")
            type_counts[ntype] = type_counts.get(ntype, 0) + 1
        summary["node_types"] = type_counts

        # Edge relationship counts
        rel_counts = {}
        for _, _, data in _graph.edges(data=True):
            rel = data.get("relationship", "UNKNOWN")
            rel_counts[rel] = rel_counts.get(rel, 0) + 1
        summary["relationship_types"] = rel_counts

    return {"tables": table_stats, "summary": summary}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Process a natural language query."""
    import os

    # Allow runtime API key override
    if req.api_key:
        os.environ["GEMINI_API_KEY"] = req.api_key

    if not _schema:
        raise HTTPException(status_code=503, detail="Schema not loaded yet.")

    result = handle_query(req.question, _schema)
    return QueryResponse(**result)


@app.get("/node/{node_id}")
async def get_node(node_id: str):
    """Get node details and its connections."""
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not built.")

    if node_id not in _graph:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    node_data = dict(_graph.nodes[node_id])

    # Get incoming and outgoing connections
    incoming = []
    for pred in _graph.predecessors(node_id):
        edge_data = _graph.edges[pred, node_id]
        incoming.append({
            "node_id": pred,
            "node_type": _graph.nodes[pred].get("type", ""),
            "node_label": _graph.nodes[pred].get("label", pred),
            **edge_data,
        })

    outgoing = []
    for succ in _graph.successors(node_id):
        edge_data = _graph.edges[node_id, succ]
        outgoing.append({
            "node_id": succ,
            "node_type": _graph.nodes[succ].get("type", ""),
            "node_label": _graph.nodes[succ].get("label", succ),
            **edge_data,
        })

    return {
        "node": {"id": node_id, **node_data},
        "incoming": incoming,
        "outgoing": outgoing,
        "degree_in": len(incoming),
        "degree_out": len(outgoing),
    }


@app.get("/neighbors/{node_id}")
async def get_neighbors(node_id: str, depth: int = Query(default=1, ge=1, le=3)):
    """Get n-hop neighborhood of a node for graph expansion."""
    if not _graph:
        raise HTTPException(status_code=503, detail="Graph not built.")

    if node_id not in _graph:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    # BFS to collect neighbors up to depth
    visited = {node_id}
    frontier = {node_id}
    for _ in range(depth):
        next_frontier = set()
        for n in frontier:
            for neighbor in list(_graph.predecessors(n)) + list(_graph.successors(n)):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier

    # Build subgraph
    subgraph = _graph.subgraph(visited)
    return graph_to_json(subgraph, max_nodes=len(visited))


@app.get("/table/{table_name}/sample")
async def table_sample(table_name: str, limit: int = Query(default=5, ge=1, le=50)):
    """Get sample rows from a table."""
    rows = get_table_sample(table_name, limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or empty.")
    return {"table": table_name, "rows": rows, "count": len(rows)}
