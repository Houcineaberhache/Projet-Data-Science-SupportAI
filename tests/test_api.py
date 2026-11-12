import os
import requests
import pytest

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def test_health():
    """1. GET /health returns ok."""
    resp = requests.get(f"{BACKEND_URL}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"


def test_get_order_found():
    """2. GET /api/orders/ORD001 returns 200 with order_id, status, estimated_delivery."""
    resp = requests.get(f"{BACKEND_URL}/api/orders/ORD001")
    assert resp.status_code == 200
    data = resp.json()
    assert "order_id" in data
    assert "status" in data
    assert "estimated_delivery" in data
    assert data["order_id"] == "ORD001"


def test_get_order_not_found():
    """3. GET /api/orders/ORD999 returns 404 with not found detail."""
    resp = requests.get(f"{BACKEND_URL}/api/orders/ORD999")
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_chat_order_tracking_with_id():
    """4. POST /api/chat with 'Where is my order ORD001?' returns the order status in the answer."""
    # Fetch status from test 2 behavior
    order_resp = requests.get(f"{BACKEND_URL}/api/orders/ORD001")
    assert order_resp.status_code == 200
    order_status = order_resp.json()["status"]

    chat_resp = requests.post(
        f"{BACKEND_URL}/api/chat",
        json={"message": "Where is my order ORD001?"},
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert "answer" in data
    assert order_status.lower() in data["answer"].lower()
    assert "sources" in data


def test_chat_order_tracking_without_id():
    """5. POST /api/chat with 'Where is my order?' asks for an order ID."""
    resp = requests.post(
        f"{BACKEND_URL}/api/chat",
        json={"message": "Where is my order?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "order id" in data["answer"].lower()


def test_chat_policy_question():
    """6. POST /api/chat with a policy question returns answer and sources (with doc_name, snippet, score)."""
    resp = requests.post(
        f"{BACKEND_URL}/api/chat",
        json={"message": "Can I return my product?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"].strip()) > 0

    assert "sources" in data
    assert isinstance(data["sources"], list)
    for source in data["sources"]:
        assert "doc_name" in source
        assert "snippet" in source
        assert "score" in source


def test_admin_upload_txt():
    """7. POST /api/admin/upload with a small .txt file succeeds and returns document_id."""
    files = {
        "file": ("test_doc.txt", b"This is a small test document content.", "text/plain")
    }
    resp = requests.post(f"{BACKEND_URL}/api/admin/upload", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert "document_id" in data
    assert data.get("title") == "test_doc.txt"


def test_admin_upload_unsupported_type():
    """Upload route rejects unsupported file types with 400."""
    files = {
        "file": ("test_image.png", b"\x89PNG\r\n\x1a\nfakeimage", "image/png")
    }
    resp = requests.post(f"{BACKEND_URL}/api/admin/upload", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "Only PDF, TXT, DOCX allowed" in data["detail"]
