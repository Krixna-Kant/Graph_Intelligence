"""
db.py — SAP ERP Data Ingestion & Knowledge Graph Builder
Ingests JSONL files from the Dataset directory into SQLite and constructs
a NetworkX directed graph representing the SAP Order-to-Cash process.
"""
import json
import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional

import networkx as nx

# ─── Configuration ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = BASE_DIR / "Dataset"
DB_PATH = BASE_DIR / "backend" / "graph_intel.db"

logger = logging.getLogger(__name__)

# All 19 SAP dataset table folders
TABLES = [
    "business_partners",
    "customer_sales_areas",
    "products",
    "product_descriptions",
    "product_sales_deliveries",
    "sales_order_headers",
    "sales_order_items",
    "sales_order_partners",
    "sales_order_pricing_elements",
    "sales_order_schedule_lines",
    "outbound_delivery_headers",
    "outbound_delivery_items",
    "billing_document_headers",
    "billing_document_items",
    "credit_memo_request_headers",
    "credit_memo_request_items",
    "journal_entry_items_accounts_receivable",
    "payments_accounts_receivable",
    "products",
]

# De-duplicate (products listed twice above by mistake in original code)
TABLES = list(dict.fromkeys(TABLES))

# ─── Database Connection ──────────────────────────────────────────────
_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


# ─── JSONL Ingestion ──────────────────────────────────────────────────
def _load_jsonl(filepath: Path) -> list[dict]:
    """Read a JSONL file and return list of dicts."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def ingest_table(table_name: str) -> int:
    """Ingest a single table from its JSONL files into SQLite."""
    folder = DATA_ROOT / table_name
    if not folder.exists():
        logger.warning(f"Dataset folder not found: {folder}")
        return 0

    conn = get_conn()
    all_records = []

    for jsonl_file in sorted(folder.glob("*.jsonl")):
        all_records.extend(_load_jsonl(jsonl_file))

    if not all_records:
        logger.warning(f"No records found in {folder}")
        return 0

    # Flatten any nested dicts/lists in records to strings
    for rec in all_records:
        for k, v in rec.items():
            if isinstance(v, (dict, list)):
                rec[k] = json.dumps(v)

    # Create table dynamically from first record's keys
    columns = list(all_records[0].keys())
    col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

    # Insert all records
    placeholders = ", ".join("?" for _ in columns)
    col_names = ", ".join(f'"{c}"' for c in columns)
    insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

    for rec in all_records:
        values = [rec.get(c) for c in columns]
        conn.execute(insert_sql, values)

    conn.commit()
    logger.info(f"Ingested {len(all_records)} records into {table_name}")
    return len(all_records)


def ingest_all() -> dict:
    """Ingest all SAP dataset tables. Returns {table: row_count}."""
    results = {}
    for table in TABLES:
        count = ingest_table(table)
        results[table] = count
    return results


# ─── Schema Introspection ─────────────────────────────────────────────
def get_schema() -> str:
    """Return a human-readable schema of all tables."""
    conn = get_conn()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]

    schema_parts = []
    for table in tables:
        cursor = conn.execute(f'PRAGMA table_info("{table}")')
        cols = [row[1] for row in cursor.fetchall()]
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        schema_parts.append(
            f"TABLE {table} ({row_count} rows):\n  " + ", ".join(cols)
        )

    return "\n\n".join(schema_parts)


def get_table_sample(table_name: str, limit: int = 3) -> list[dict]:
    """Get sample rows from a table."""
    conn = get_conn()
    try:
        cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


# ─── Knowledge Graph Construction ─────────────────────────────────────
def build_graph() -> nx.DiGraph:
    """
    Build a directed graph representing the SAP Order-to-Cash process.
    
    Node types: CUSTOMER, PRODUCT, SALES_ORDER, DELIVERY, BILLING, JOURNAL, PAYMENT
    Edge types: PLACED, CONTAINS, FULFILLED_BY, BILLED_IN, RECORDED_AS, PAID_VIA
    """
    conn = get_conn()
    G = nx.DiGraph()

    # ── 1. Customer nodes (from business_partners) ──
    try:
        rows = conn.execute(
            'SELECT * FROM business_partners'
        ).fetchall()
        for r in rows:
            r = dict(r)
            node_id = f"CUST_{r['businessPartner']}"
            G.add_node(node_id, **{
                "type": "CUSTOMER",
                "id": r["businessPartner"],
                "label": r.get("businessPartnerFullName", r["businessPartner"]),
                "category": r.get("businessPartnerCategory", ""),
                "grouping": r.get("businessPartnerGrouping", ""),
                "isBlocked": r.get("businessPartnerIsBlocked", "false"),
            })
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load business_partners: {e}")

    # ── 2. Product nodes ──
    try:
        rows = conn.execute('SELECT * FROM products').fetchall()
        for r in rows:
            r = dict(r)
            node_id = f"PROD_{r['product']}"
            G.add_node(node_id, **{
                "type": "PRODUCT",
                "id": r["product"],
                "label": r.get("productOldId", r["product"]),
                "productType": r.get("productType", ""),
                "productGroup": r.get("productGroup", ""),
                "baseUnit": r.get("baseUnit", ""),
                "grossWeight": r.get("grossWeight", ""),
                "weightUnit": r.get("weightUnit", ""),
            })
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load products: {e}")

    # ── 3. Sales Order nodes (from sales_order_headers) ──
    try:
        rows = conn.execute('SELECT * FROM sales_order_headers').fetchall()
        for r in rows:
            r = dict(r)
            so_id = r["salesOrder"]
            node_id = f"SO_{so_id}"
            G.add_node(node_id, **{
                "type": "SALES_ORDER",
                "id": so_id,
                "label": f"SO-{so_id}",
                "orderType": r.get("salesOrderType", ""),
                "organization": r.get("salesOrganization", ""),
                "totalNetAmount": r.get("totalNetAmount", ""),
                "currency": r.get("transactionCurrency", ""),
                "creationDate": r.get("creationDate", ""),
                "soldToParty": r.get("soldToParty", ""),
            })
            # Edge: Customer → Sales Order (PLACED)
            cust_id = r.get("soldToParty", "")
            if cust_id:
                G.add_edge(f"CUST_{cust_id}", node_id,
                           relationship="PLACED", weight=1)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load sales_order_headers: {e}")

    # ── 4. Sales Order Items → Product edges ──
    try:
        rows = conn.execute('SELECT * FROM sales_order_items').fetchall()
        for r in rows:
            r = dict(r)
            so_id = r["salesOrder"]
            material = r.get("material", "")
            if material:
                G.add_edge(f"SO_{so_id}", f"PROD_{material}",
                           relationship="CONTAINS",
                           item=r.get("salesOrderItem", ""),
                           quantity=r.get("requestedQuantity", ""),
                           netAmount=r.get("netAmount", ""),
                           weight=1)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load sales_order_items: {e}")

    # ── 5. Delivery nodes (from outbound_delivery_headers) ──
    try:
        rows = conn.execute('SELECT * FROM outbound_delivery_headers').fetchall()
        for r in rows:
            r = dict(r)
            del_id = r["deliveryDocument"]
            node_id = f"DEL_{del_id}"
            G.add_node(node_id, **{
                "type": "DELIVERY",
                "id": del_id,
                "label": f"DEL-{del_id}",
                "deliveryType": r.get("deliveryDocumentType", ""),
                "shippingPoint": r.get("shippingPoint", ""),
                "soldToParty": r.get("soldToParty", ""),
                "deliveryDate": r.get("deliveryDate", ""),
                "totalNetWeight": r.get("headerNetWeight", ""),
            })
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load outbound_delivery_headers: {e}")

    # ── 6. Delivery Items → link SO ↔ Delivery ──
    try:
        rows = conn.execute('SELECT * FROM outbound_delivery_items').fetchall()
        for r in rows:
            r = dict(r)
            del_id = r["deliveryDocument"]
            ref_sd_doc = r.get("referenceSdDocument", "")
            if ref_sd_doc:
                G.add_edge(f"SO_{ref_sd_doc}", f"DEL_{del_id}",
                           relationship="FULFILLED_BY",
                           item=r.get("deliveryDocumentItem", ""),
                           quantity=r.get("actualDeliveryQuantity", ""),
                           weight=1)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load outbound_delivery_items: {e}")

    # ── 7. Billing Document nodes (from billing_document_headers) ──
    try:
        rows = conn.execute('SELECT * FROM billing_document_headers').fetchall()
        for r in rows:
            r = dict(r)
            bill_id = r["billingDocument"]
            node_id = f"BILL_{bill_id}"
            G.add_node(node_id, **{
                "type": "BILLING",
                "id": bill_id,
                "label": f"BILL-{bill_id}",
                "billingType": r.get("billingDocumentType", ""),
                "totalNetAmount": r.get("totalNetAmount", ""),
                "currency": r.get("transactionCurrency", ""),
                "billingDate": r.get("billingDocumentDate", ""),
                "isCancelled": r.get("billingDocumentIsCancelled", ""),
                "soldToParty": r.get("soldToParty", ""),
                "accountingDocument": r.get("accountingDocument", ""),
            })
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load billing_document_headers: {e}")

    # ── 8. Billing Items → link Delivery ↔ Billing ──
    try:
        rows = conn.execute('SELECT * FROM billing_document_items').fetchall()
        for r in rows:
            r = dict(r)
            bill_id = r["billingDocument"]
            ref_sd = r.get("referenceSdDocument", "")
            if ref_sd:
                # referenceSdDocument in billing items often points to delivery doc
                G.add_edge(f"DEL_{ref_sd}", f"BILL_{bill_id}",
                           relationship="BILLED_IN",
                           item=r.get("billingDocumentItem", ""),
                           netAmount=r.get("netAmount", ""),
                           weight=1)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load billing_document_items: {e}")

    # ── 9. Journal Entry nodes ──
    try:
        rows = conn.execute(
            'SELECT * FROM journal_entry_items_accounts_receivable'
        ).fetchall()
        seen_journals = set()
        for r in rows:
            r = dict(r)
            doc_id = r["accountingDocument"]
            node_id = f"JRN_{doc_id}"
            if node_id not in seen_journals:
                seen_journals.add(node_id)
                G.add_node(node_id, **{
                    "type": "JOURNAL",
                    "id": doc_id,
                    "label": f"JRN-{doc_id}",
                    "fiscalYear": r.get("fiscalYear", ""),
                    "amount": r.get("amountInTransactionCurrency", ""),
                    "currency": r.get("transactionCurrency", ""),
                    "postingDate": r.get("postingDate", ""),
                    "customer": r.get("customer", ""),
                    "glAccount": r.get("glAccount", ""),
                })
            # Edge: Billing → Journal (via accountingDocument match)
            cust_id = r.get("customer", "")
            if cust_id:
                G.add_edge(f"CUST_{cust_id}", node_id,
                           relationship="RECORDED_AS", weight=0.5)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load journal entries: {e}")

    # ── 10. Payment nodes ──
    try:
        rows = conn.execute(
            'SELECT * FROM payments_accounts_receivable'
        ).fetchall()
        seen_payments = set()
        for r in rows:
            r = dict(r)
            doc_id = r["accountingDocument"]
            node_id = f"PAY_{doc_id}"
            if node_id not in seen_payments:
                seen_payments.add(node_id)
                G.add_node(node_id, **{
                    "type": "PAYMENT",
                    "id": doc_id,
                    "label": f"PAY-{doc_id}",
                    "amount": r.get("amountInTransactionCurrency", ""),
                    "currency": r.get("transactionCurrency", ""),
                    "postingDate": r.get("postingDate", ""),
                    "customer": r.get("customer", ""),
                    "clearingDate": r.get("clearingDate", ""),
                })
            cust_id = r.get("customer", "")
            if cust_id:
                G.add_edge(f"CUST_{cust_id}", node_id,
                           relationship="PAID_VIA", weight=0.5)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load payments: {e}")

    # ── 11. Link billing docs to journal entries via accountingDocument ──
    try:
        billing_rows = conn.execute(
            'SELECT billingDocument, accountingDocument FROM billing_document_headers'
        ).fetchall()
        for r in billing_rows:
            r = dict(r)
            bill_id = r["billingDocument"]
            acct_doc = r.get("accountingDocument", "")
            if acct_doc:
                jrn_node = f"JRN_{acct_doc}"
                if G.has_node(jrn_node):
                    G.add_edge(f"BILL_{bill_id}", jrn_node,
                               relationship="POSTED_AS", weight=1)
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not link billing→journal: {e}")

    logger.info(
        f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    )
    return G


# ─── Graph Serialization ──────────────────────────────────────────────
def graph_to_json(G: nx.DiGraph, max_nodes: int = 200) -> dict:
    """Serialize a subgraph to JSON for the frontend."""
    nodes = []
    node_list = list(G.nodes(data=True))[:max_nodes]
    node_ids = {n[0] for n in node_list}

    for node_id, data in node_list:
        node_obj = {**data}
        node_obj["id"] = node_id  # Guarantee the graph ID is retained
        nodes.append(node_obj)

    edges = []
    for u, v, data in G.edges(data=True):
        if u in node_ids and v in node_ids:
            edges.append({
                "source": u,
                "target": v,
                **data
            })

    return {"nodes": nodes, "edges": edges}


# ─── SQL Execution ────────────────────────────────────────────────────
def execute_query(sql: str) -> list[dict]:
    """Execute a read-only SQL query and return results."""
    conn = get_conn()
    try:
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        raise ValueError(f"SQL Error: {e}")


def get_stats() -> dict:
    """Get database statistics."""
    conn = get_conn()
    stats = {}
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    for row in cursor.fetchall():
        table = row[0]
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        stats[table] = count
    return stats
