"""Client for external Retrieval service (BM25 / vector search) with local fallback."""
import json
import logging
import os
import urllib.error
import urllib.request

from schemas.retrieval import RetrievalRequest, RetrievalResponse

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 3.0


def _fallback_retrieve(query: str) -> list[dict]:
    if "return" in query.lower():
        return [{
            "doc_name": "return_policy.pdf",
            "snippet": "Returns are accepted within 14 days of delivery.",
            "score": 0.89,
        }]
    return []


def retrieve_documents(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve relevant documents via external retrieval service or fallback."""
    service_url = os.getenv("RETRIEVAL_SERVICE_URL", "").strip()
    if not service_url:
        return _fallback_retrieve(query)

    try:
        req_obj = RetrievalRequest(query=query, top_k=top_k)
        data = json.dumps(req_obj.model_dump()).encode("utf-8")
        req = urllib.request.Request(
            service_url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            parsed = RetrievalResponse(**raw)
            return [doc.model_dump() for doc in parsed.results]
    except Exception as exc:
        logger.warning("Retrieval service call to %s failed (%s), using fallback", service_url, exc)
        return _fallback_retrieve(query)
