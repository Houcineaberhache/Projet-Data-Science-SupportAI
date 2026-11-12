import os
import re
import shutil
import zipfile
from xml.etree import ElementTree as ET

import psycopg2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services import (
    classify_intent,
    generate_rag_answer,
    get_order_status,
    search_documents,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Synthetic orders seed data (10 rows)
# ---------------------------------------------------------------------------
_SEED_ORDERS = [
    ("ORD001", "CUST001", "PROD001", "shipped", "2026-11-10"),
    ("ORD002", "CUST002", "PROD002", "processing", "2026-11-14"),
    ("ORD003", "CUST003", "PROD003", "delivered", "2026-11-02"),
    ("ORD004", "CUST004", "PROD004", "shipped", "2026-11-12"),
    ("ORD005", "CUST005", "PROD005", "processing", "2026-11-16"),
    ("ORD006", "CUST006", "PROD006", "delivered", "2026-10-28"),
    ("ORD007", "CUST007", "PROD007", "cancelled", "N/A"),
    ("ORD008", "CUST008", "PROD008", "shipped", "2026-11-13"),
    ("ORD009", "CUST009", "PROD009", "processing", "2026-11-18"),
    ("ORD010", "CUST010", "PROD010", "delivered", "2026-11-05"),
]

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for space in ("\u00a0", "\u202f", "\u2009", "\u2007", "\u2008"):
        text = text.replace(space, " ")
    for invisible in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"):
        text = text.replace(invisible, "")
    for ligature, replacement in (("\ufb01", "fi"), ("\ufb02", "fl")):
        text = text.replace(ligature, replacement)
    kept = [char for char in text if char in "\n\t" or ord(char) >= 32]
    text = "".join(kept)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return clean_text(f.read())
    elif ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
                if t:
                    pages.append(t)
            except Exception:
                continue
        return clean_text("\n\n".join(pages))
    elif ext == ".docx":
        with zipfile.ZipFile(file_path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        body = root.find(f"{W_NS}body")
        if body is None:
            return ""
        elements = []
        for child in body:
            if child.tag == f"{W_NS}p":
                t = "".join(node.text or "" for node in child.iter(f"{W_NS}t")).strip()
                if t:
                    elements.append(t)
            elif child.tag == f"{W_NS}tbl":
                for row in child.iter(f"{W_NS}tr"):
                    cells = ["".join(node.text or "" for node in cell.iter(f"{W_NS}t")).strip() for cell in row.iter(f"{W_NS}tc")]
                    elements.append(" | ".join(cells))
        return clean_text("\n\n".join(elements))
    return ""


def get_conn():
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host="localhost",
        port=5433,
        dbname="supportai_db",
        user="postgres",
        password="postgres",
    )


def _init_orders_table() -> None:
    """Create the orders table if absent and upsert the seed rows (idempotent)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id           VARCHAR(20) PRIMARY KEY,
            customer_id        VARCHAR(20),
            product_id         VARCHAR(20),
            status             VARCHAR(30),
            estimated_delivery VARCHAR(20)
        )
    """)
    cur.executemany(
        "INSERT INTO orders VALUES (%s, %s, %s, %s, %s)"
        " ON CONFLICT (order_id) DO NOTHING",
        _SEED_ORDERS,
    )
    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup() -> None:
    _init_orders_table()


@app.get("/health")
def health():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unreachable: {e!s}")


# ---------------------------------------------------------------------------
# Order tracking endpoint
# ---------------------------------------------------------------------------

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, customer_id, product_id, status, estimated_delivery"
        " FROM orders WHERE order_id = %s",
        (order_id.upper(),),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id.upper()} not found.")
    return {
        "order_id": row[0],
        "customer_id": row[1],
        "product_id": row[2],
        "status": row[3],
        "estimated_delivery": row[4],
    }


# ---------------------------------------------------------------------------
# Chat endpoint: routed by intent
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


_ORDER_ID_RE = re.compile(r"\b(ORD\d+)\b", re.IGNORECASE)


@app.post("/api/chat")
def chat(req: ChatRequest):
    intent_res = classify_intent(req.message)
    intent = intent_res.get("intent", "")

    if intent == "order_tracking":
        match = _ORDER_ID_RE.search(req.message)
        if not match:
            return {
                "answer": "Could you please provide your order ID (e.g. ORD001) so I can check its status?",
                "sources": [],
            }
        order_id = match.group(1).upper()
        try:
            order_data = get_order_status(order_id)
        except Exception as exc:
            return {
                "answer": f"Unable to reach the order tracking service: {exc!s}",
                "sources": [],
            }

        if order_data.get("status") == "not found":
            answer = order_data.get("message", f"Order {order_id} not found.")
        else:
            status = order_data.get("status", "unknown")
            est = order_data.get("estimated_delivery", "N/A")
            answer = f"Order {order_id}: status is **{status}**, estimated delivery {est}."

        return {
            "answer": answer,
            "sources": [],
        }

    # Any other intent -> search_documents via MCP, pass to RAG client
    try:
        docs = search_documents(req.message)
    except Exception as exc:
        return {
            "answer": f"Unable to retrieve documents from the knowledge base: {exc!s}",
            "sources": [],
        }

    rag = generate_rag_answer(req.message, docs)
    return {
        "answer": rag.get("answer", ""),
        "sources": rag.get("sources", []),
    }


# ---------------------------------------------------------------------------
# Document upload endpoint
# ---------------------------------------------------------------------------

@app.post("/api/admin/upload")
def upload(file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "")
    if os.path.splitext(name)[1].lower() not in {".pdf", ".txt", ".docx"}:
        raise HTTPException(400, "Only PDF, TXT, DOCX allowed")
    os.makedirs("uploads", exist_ok=True)
    saved_path = os.path.join("uploads", name)
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    content = extract_text(saved_path)
    chunks_count = 3  # fake

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (title, content, chunks_count) VALUES (%s, %s, %s) RETURNING id",
        (name, content, chunks_count),
    )
    doc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"document_id": doc_id, "title": name, "chunks_count": chunks_count}
