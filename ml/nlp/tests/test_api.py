from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_classify_order_tracking_extracts_order_id():
    r = client.post("/classify", json={"text": "Où en est ma commande ORD123 ?"})
    body = r.json()
    assert r.status_code == 200
    assert body["intent"] == "order_tracking"
    assert body["route"] == "order_api"
    assert body["order_id"] == "ORD123"


def test_greeting_is_out_of_scope_but_routed_canned():
    body = client.post("/classify", json={"text": "Bonjour"}).json()
    assert body["intent"] == "out_of_scope" and body["route"] == "canned"


def test_human_support_routes_handoff():
    body = client.post("/classify", json={"text": "Je veux parler à un responsable"}).json()
    assert body["intent"] == "human_support" and body["route"] == "human_handoff"


def test_classify_returns_topk():
    body = client.post("/classify", json={"text": "Quels moyens de paiement ?", "top_k": 3}).json()
    assert len(body["top_k"]) == 3


def test_batch_and_validation():
    assert len(client.post("/classify/batch", json={"texts": ["Salam", "Prix du laptop ?"]}).json()) == 2
    assert client.post("/classify", json={"text": ""}).status_code == 422


def test_intents_catalogue():
    assert "order_tracking" in client.get("/intents").json()
