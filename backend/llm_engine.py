"""
llm_engine.py — Natural Language to SQL Pipeline using Google Gemini
Converts user questions about SAP ERP data into SQL queries,
executes them, and formats answers using an LLM.
"""
import os
import re
import logging
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Gemini Client Setup ──────────────────────────────────────────────
_model = None


def _get_model():
    global _model
    if _model is None:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set. Add it to backend/.env")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-3-flash-preview")
    return _model


# ─── Domain Guardrails ────────────────────────────────────────────────
ALLOWED_DOMAINS = [
    "sales", "order", "customer", "business partner", "product", "material",
    "delivery", "billing", "invoice", "payment", "journal", "accounting",
    "revenue", "amount", "quantity", "price", "shipment", "credit memo",
    "profit center", "cost center", "company code", "fiscal year",
    "plant", "storage", "currency", "INR", "batch", "weight",
    "SAP", "ERP", "O2C", "order to cash", "document",
]

OFF_TOPIC_RESPONSE = {
    "answer": "I can only answer questions about SAP business data — sales orders, customers, products, deliveries, billing, payments, and accounting. Please ask about your ERP data!",
    "sql": None,
    "results": [],
    "is_off_topic": True,
}


def _check_domain(question: str) -> bool:
    """Check if the question is related to SAP/business domain."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in ALLOWED_DOMAINS)


# ─── SQL Safety ────────────────────────────────────────────────────────
DANGEROUS_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
                      "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "EXEC"]


def _validate_sql(sql: str) -> bool:
    """Ensure SQL is read-only (SELECT only)."""
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return False
    for kw in DANGEROUS_KEYWORDS:
        if re.search(rf'\b{kw}\b', sql_upper):
            return False
    return True


# ─── Schema Context for LLM ───────────────────────────────────────────
def _build_schema_prompt(schema: str) -> str:
    """Build the system prompt with schema context."""
    return f"""You are an expert SQL analyst for SAP ERP data. You translate natural language questions into SQLite queries.

DATABASE SCHEMA:
{schema}

KEY RELATIONSHIPS:
- business_partners.businessPartner links to sales_order_headers.soldToParty (customer who placed the order)
- sales_order_items.salesOrder links to sales_order_headers.salesOrder
- sales_order_items.material links to products.product
- outbound_delivery_items.referenceSdDocument links to sales_order_headers.salesOrder  
- outbound_delivery_items.deliveryDocument links to outbound_delivery_headers.deliveryDocument
- billing_document_items.referenceSdDocument links to deliveries (deliveryDocument)
- billing_document_headers.soldToParty links to business_partners.businessPartner
- billing_document_headers.accountingDocument links to journal_entry_items_accounts_receivable.accountingDocument
- journal_entry_items_accounts_receivable.customer links to business_partners.businessPartner
- payments_accounts_receivable.customer links to business_partners.businessPartner

IMPORTANT NOTES:
- All monetary amounts are in TEXT format, cast to REAL for calculations: CAST(netAmount AS REAL)
- Currency is mostly INR (Indian Rupees)
- Product IDs are like S8907367039280, and productOldId in products table has readable names like ABC-WEB-3803
- Customer IDs (businessPartner) are like 320000082, 320000083
- Boolean fields like billingDocumentIsCancelled are stored as 0 (False) or 1 (True). NEVER use 'false' or 'true' strings.
- Use double quotes for table/column names with special characters

RULES:
1. Output ONLY a valid SQLite SELECT query
2. No INSERT, UPDATE, DELETE, DROP, or any data-modifying statements  
3. Use table aliases for clarity
4. LIMIT results to 50 rows max unless user specifies otherwise
5. For aggregate queries, include meaningful column aliases
"""


# ─── Main Query Handler ───────────────────────────────────────────────
def handle_query(question: str, schema: str) -> dict:
    """
    Full NL → SQL → Answer pipeline.
    Returns: {question, sql, results, answer, is_off_topic, node_ids}
    """
    # Step 1: Domain check
    if not _check_domain(question):
        return OFF_TOPIC_RESPONSE

    try:
        model = _get_model()
    except ValueError as e:
        return {
            "answer": str(e),
            "sql": None,
            "results": [],
            "is_off_topic": False,
            "error": "api_key_missing",
        }

    # Step 2: Generate SQL
    schema_prompt = _build_schema_prompt(schema)
    sql_prompt = f"""{schema_prompt}

USER QUESTION: {question}

Generate ONLY the SQL query, nothing else. No markdown, no explanation, just the raw SQL."""

    try:
        sql_response = model.generate_content(sql_prompt)
        raw_sql = sql_response.text.strip()
        # Clean markdown code blocks if present
        raw_sql = re.sub(r'^```(?:sql)?\s*', '', raw_sql)
        raw_sql = re.sub(r'\s*```$', '', raw_sql)
        raw_sql = raw_sql.strip()
    except Exception as e:
        logger.error(f"Gemini SQL generation error: {e}")
        return {
            "answer": f"Error generating SQL: {str(e)}",
            "sql": None,
            "results": [],
            "is_off_topic": False,
            "error": "llm_error",
        }

    # Step 3: Validate SQL safety
    if not _validate_sql(raw_sql):
        return {
            "answer": "Generated query was blocked for safety. Only SELECT queries are allowed.",
            "sql": raw_sql,
            "results": [],
            "is_off_topic": False,
            "error": "unsafe_sql",
        }

    # Step 4: Execute SQL
    from db import execute_query
    try:
        results = execute_query(raw_sql)
    except ValueError as e:
        return {
            "answer": f"Query execution error: {str(e)}",
            "sql": raw_sql,
            "results": [],
            "is_off_topic": False,
            "error": "execution_error",
        }

    # Step 5: Generate natural language answer
    answer_prompt = f"""Based on the following SQL query results, provide a clear, concise answer to the user's question.

USER QUESTION: {question}
SQL QUERY: {raw_sql}
RESULTS ({len(results)} rows): {str(results[:20])}

Give a direct, helpful answer. Use numbers and specifics from the data. 
If the results are empty, say so and suggest why.
Format monetary values with ₹ symbol for INR currency."""

    try:
        answer_response = model.generate_content(answer_prompt)
        answer = answer_response.text.strip()
    except Exception as e:
        answer = f"Query returned {len(results)} results. (Could not generate summary: {e})"

    # Step 6: Extract node IDs for graph highlighting
    node_ids = _extract_node_ids(results)

    return {
        "question": question,
        "sql": raw_sql,
        "results": results[:50],  # Cap at 50
        "answer": answer,
        "is_off_topic": False,
        "node_ids": node_ids,
    }


def _extract_node_ids(results: list[dict]) -> list[str]:
    """Extract graph node IDs from query results for highlighting."""
    node_ids = []
    id_fields = {
        "businessPartner": "CUST_",
        "soldToParty": "CUST_",
        "customer": "CUST_",
        "product": "PROD_",
        "material": "PROD_",
        "salesOrder": "SO_",
        "deliveryDocument": "DEL_",
        "billingDocument": "BILL_",
        "accountingDocument": "JRN_",
    }

    for row in results[:20]:  # Limit extraction
        for field, prefix in id_fields.items():
            if field in row and row[field]:
                node_ids.append(f"{prefix}{row[field]}")

    return list(set(node_ids))
