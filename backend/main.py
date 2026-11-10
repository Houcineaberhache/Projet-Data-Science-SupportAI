import json
import time
import uuid
from typing import Optional

import os
import shutil
from fastapi import File, HTTPException, UploadFile

import psycopg2
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_conn():
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host="localhost", port=5433,
        dbname="supportai_db", user="postgres", password="postgres",
    )



def predict_intent(text: str) -> dict:
    t = text.lower()
    if "return" in t or "refund" in t:
        return {"intent": "return_request", "confidence": 0.9}
    if "order" in t:
        return {"intent": "order_tracking", "confidence": 0.9}
    return {"intent": "other", "confidence": 0.5}


def generate_answer(question: str) -> dict:
    if "return" in question.lower():
        return {
            "answer": "You can return your product within 14 days.",
            "is_abstained": False,
            "sources": [{
                "doc_name": "return_policy.pdf",
                "snippet": "Returns are accepted within 14 days of delivery.",
                "score": 0.89,
            }],
        }
    return {
        "answer": "I could not find this in our documents.",
        "is_abstained": True,
        "sources": [],
    }


# ---- Route ----
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


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

    chunks_count = 3  #fake

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