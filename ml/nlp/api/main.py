"""API de classification d'intentions — SupportAI / NovaShop.

Lancer : uvicorn api.main:app --port 8002
Contrat consommé par le backend (Étudiant 5) : POST /classify
"""
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from intent_clf.inference import _load, classify

app = FastAPI(title="SupportAI – Intent Classifier", version="1.0.0")


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, examples=["Où est ma commande ORD123 ?"])
    top_k: int = Field(3, ge=1, le=5)


class BatchRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, max_length=100)


class Candidate(BaseModel):
    intent: str
    confidence: float


class ClassifyResponse(BaseModel):
    text: str
    intent: str
    confidence: float
    low_confidence: bool
    route: str  # rag | order_api | human_handoff | canned | fallback
    needs_order_id: bool
    order_id: Optional[str]
    top_k: List[Candidate]
    model: str


@app.get("/health")
def health():
    cfg, _, _ = _load()
    return {"status": "ok", "model": cfg["best_model"], "embedding_backend": cfg["embedding_backend"],
            "confidence_threshold": cfg["confidence_threshold"]}


@app.get("/intents")
def intents():
    _, _, intents = _load()
    return intents


@app.post("/classify", response_model=ClassifyResponse)
def classify_one(req: ClassifyRequest):
    return classify(req.text, req.top_k)


@app.post("/classify/batch", response_model=List[ClassifyResponse])
def classify_batch(req: BatchRequest):
    return [classify(t) for t in req.texts]
