import os
import psycopg2
from starlette.requests import Request
from starlette.responses import JSONResponse

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP

mcp = FastMCP("supportai-mcp")


def get_conn():
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "supportai_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool()
def search_documents(query: str) -> list[dict]:
    """Keyword search (ILIKE) in documents.content, returns up to 3 results with title and the matching text."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT title, content FROM documents WHERE content ILIKE %s LIMIT 3",
        (f"%{query}%",),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for title, content in rows:
        text = content or ""
        idx = text.lower().find(query.lower())
        if idx != -1:
            start = max(0, idx - 100)
            end = min(len(text), idx + len(query) + 200)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
        else:
            snippet = text[:300].strip()
        # score is a placeholder until the retrieval service is connected.
        results.append({"doc_name": title, "snippet": snippet or text, "score": 1.0})
    return results


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """Returns the row from the orders table, or a clear 'not found' result."""
    clean_id = order_id.upper().strip()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, customer_id, product_id, status, estimated_delivery FROM orders WHERE order_id = %s",
        (clean_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return {"status": "not found", "message": f"Order {clean_id} not found."}
    return {
        "order_id": row[0],
        "customer_id": row[1],
        "product_id": row[2],
        "status": row[3],
        "estimated_delivery": row[4],
    }


@mcp.tool()
def get_product(product_id: str) -> dict:
    """Returns the row from the products table, or 'not found'."""
    clean_id = product_id.upper().strip()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT product_id, name, category, price FROM products WHERE product_id = %s",
        (clean_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return {"status": "not found", "message": f"Product {clean_id} not found."}
    return {
        "product_id": row[0],
        "name": row[1],
        "category": row[2],
        "price": float(row[3]) if row[3] is not None else None,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
