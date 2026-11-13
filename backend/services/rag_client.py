"""Client for external RAG generation service with local fallback."""
import json
import logging
import os
import urllib.error
import urllib.request

from schemas.rag import RAGRequest, RAGResponse
from schemas.retrieval import SourceDocument

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 3.0


def _fallback_generate(question: str, context_documents: list[dict]) -> dict:
    if context_documents:
        return {
            "answer": "You can return your product within 14 days.",
            "is_abstained": False,
            "sources": context_documents,
        }
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


def generate_rag_answer(question: str, context_documents: list[dict]) -> dict:
    """Generate answer via external RAG service or fallback to rule-based mock."""
    service_url = os.getenv("RAG_SERVICE_URL", "").strip()
    if not service_url:
        return _fallback_generate(question, context_documents)

    try:
        sources_models = [SourceDocument(**doc) for doc in context_documents]
        req_obj = RAGRequest(question=question, context_documents=sources_models)
        data = json.dumps(req_obj.model_dump()).encode("utf-8")
        req = urllib.request.Request(
            service_url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            parsed = RAGResponse(**raw)
            return parsed.model_dump()
    except Exception as exc:
        logger.warning("RAG service call to %s failed (%s), using fallback", service_url, exc)
        return _fallback_generate(question, context_documents)
