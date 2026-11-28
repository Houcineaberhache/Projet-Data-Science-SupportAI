"""Contrat avec le backend : backend/services/nlp_client.py envoie {"text": ...} à NLP_SERVICE_URL
et attend {"intent": str, "confidence": float} (backend/schemas/nlp.py). Ces tests échouent si l'API s'en écarte."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import BaseModel

from api.main import app

client = TestClient(app)
OFFICIAL = set(json.loads((Path(__file__).resolve().parent.parent / "data" / "intents.json").read_text())["intents"])


class NLPResponse(BaseModel):  # copie du schéma du backend (backend/schemas/nlp.py)
    intent: str
    confidence: float


def test_response_parses_with_backend_schema():
    raw = client.post("/classify", json={"text": "Où est ma commande ORD123 ?"}).json()
    parsed = NLPResponse(**raw)  # les champs en plus (route, top_k...) sont ignorés par le backend
    assert parsed.intent == "order_tracking"
    assert 0.0 <= parsed.confidence <= 1.0


def test_intent_is_always_an_official_intent():
    for text in ["Bonjour", "Je veux annuler ma commande", "blabla xyz", "Quel temps fait-il ?", "j'ai été débité deux fois"]:
        assert client.post("/classify", json={"text": text}).json()["intent"] in OFFICIAL
