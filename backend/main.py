#!/usr/bin/env python3
import json
import os
import re
import shutil
import time
import uuid

import psycopg2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services import classify_intent, generate_rag_answer, retrieve_documents

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
    ("ORD001", "CUST001", "PROD001", "shipped",    "2026-11-10"),
    ("ORD002", "CUST002", "PROD002", "processing", "2026-11-14"),
    ("ORD003", "CUST003", "PROD003", "delivered",  "2026-11-02"),
    ("ORD004", "CUST004", "PROD004", "shipped",    "2026-11-12"),
    ("ORD005", "CUST005", "PROD005", "processing", "2026-11-16"),
    ("ORD006", "CUST006", "PROD006", "delivered",  "2026-10-28"),
    ("ORD007", "CUST007", "PROD007", "cancelled",  "N/A"),
    ("ORD008", "CUST008", "PROD008", "shipped",    "2026-11-13"),
    ("ORD009", "CUST009", "PROD009", "processing", "2026-11-18"),
    ("ORD010", "CUST010", "PROD010", "delivered",  "2026-11-05"),
]

_ORDER_ID_RE = re.compile(r"\b(ORD\d{3,})\b", re.IGNORECASE)


def get_conn():
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host="localhost", port=5433,
        dbname="supportai_db", user="postgres", password="postgres",
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lookup_order(order_id: str) -> dict | None:
    """Return order row as dict or None if not found."""
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
        return None
    return {
        "order_id": row[0],
        "customer_id": row[1],
        "product_id": row[2],
        "status": row[3],
        "estimated_delivery": row[4],
    }


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
    order = _lookup_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id.upper()} not found.")
    return {
        "order_id": order["order_id"],
        "product_id": order["product_id"],
        "status": order["status"],
        "estimated_delivery": order["estimated_delivery"],
    }


# ---------------------------------------------------------------------------
# Intent / answer helpers
# ---------------------------------------------------------------------------

def predict_intent(text: str) -> dict:
    if _ORDER_ID_RE.search(text):
        return {"intent": "order_tracking", "confidence": 0.95}
    return classify_intent(text)


def generate_answer(question: str) -> dict:
    # Order-ID lookup takes priority
    match = _ORDER_ID_RE.search(question)
    if match:
        order_id = match.group(1).upper()
        order = _lookup_order(order_id)
        if order:
            return {
                "answer": (
                    f"Order {order['order_id']}: status is "
                    f"**{order['status']}**, estimated delivery "
                    f"{order['estimated_delivery']}."
                ),
                "is_abstained": False,
                "sources": [],
                "order_status": order["status"],
            }
        return {
            "answer": f"I could not find order {order_id} in our system.",
            "is_abstained": True,
            "sources": [],
        }

    docs = retrieve_documents(question)
    return generate_rag_answer(question, docs)


# ---- Routes ----
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest):
    start = time.perf_counter()
    session_id = req.session_id or str(uuid.uuid4())

    intent = predict_intent(req.message)
    rag = generate_answer(req.message)
    latency = int((time.perf_counter() - start) * 1000)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
        (session_id,),
    )
    cur.execute(
        """INSERT INTO messages
           (conversation_id, question, answer, is_abstained, intent, confidence, latency_ms, sources)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (session_id, req.message, rag["answer"], rag["is_abstained"],
         intent["intent"], intent["confidence"], latency, json.dumps(rag["sources"])),
    )
    message_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {
        **rag,
        "intent": intent["intent"],
        "confidence": intent["confidence"],
        "message_id": message_id,
        "session_id": session_id,
    }


@app.post("/api/admin/upload")
def upload(file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "")
    if os.path.splitext(name)[1].lower() not in {".pdf", ".txt", ".docx"}:
        raise HTTPException(400, "Only PDF, TXT, DOCX allowed")
    os.makedirs("uploads", exist_ok=True)
    with open(os.path.join("uploads", name), "wb") as f:
        shutil.copyfileobj(file.file, f)

    chunks_count = 3  # fake

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (title, chunks_count) VALUES (%s, %s) RETURNING id",
        (name, chunks_count),
    )
    doc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"document_id": doc_id, "title": name, "chunks_count": chunks_count}


@app.get("/api/admin/documents")
def documents():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, chunks_count, uploaded_at FROM documents ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "chunks_count": r[2], "uploaded_at": r[3].isoformat()}
        for r in rows
    ]


@app.get("/api/admin/stats")
def stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*), COALESCE(AVG(latency_ms), 0), "
        "COUNT(*) FILTER (WHERE is_abstained) FROM messages"
    )
    total, avg, abstained = cur.fetchone()
    cur.execute("SELECT COALESCE(intent, 'unknown'), COUNT(*) FROM messages GROUP BY intent")
    intents = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute(
        "SELECT COUNT(*) FILTER (WHERE rating = 1), "
        "COUNT(*) FILTER (WHERE rating = -1) FROM feedback"
    )
    up, down = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "total_questions": total,
        "avg_latency_ms": round(float(avg), 1),
        "abstained": abstained,
        "intents": intents,
        "thumbs_up": up,
        "thumbs_down": down,
    }


@app.get("/api/admin/history")
def history():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, question, answer, intent, latency_ms, is_abstained, created_at "
        "FROM messages ORDER BY id DESC LIMIT 20"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "question": r[1], "answer": r[2], "intent": r[3],
         "latency_ms": r[4], "is_abstained": r[5], "created_at": r[6].isoformat()}
        for r in rows
    ]


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    if req.rating not in (1, -1):
        raise HTTPException(422, "rating must be 1 or -1")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (message_id, rating) VALUES (%s, %s)",
        (req.message_id, req.rating),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "saved"}
