"""Client for external NLP intent classification service with local fallback."""
import json
import logging
import os
import urllib.error
import urllib.request

from schemas.nlp import NLPRequest, NLPResponse

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 3.0


def _fallback_intent(text: str) -> dict:
    t = text.lower()
    if "return" in t or "refund" in t:
        return {"intent": "return_request", "confidence": 0.9}
    if "order" in t:
        return {"intent": "order_tracking", "confidence": 0.9}
    return {"intent": "other", "confidence": 0.5}


def classify_intent(text: str) -> dict:
    """Classify user intent via NLP service or fall back to rule-based mock."""
    service_url = os.getenv("NLP_SERVICE_URL", "").strip()
    if not service_url:
        return _fallback_intent(text)

    try:
        req_obj = NLPRequest(text=text)
        data = json.dumps(req_obj.model_dump()).encode("utf-8")
        req = urllib.request.Request(
            service_url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            parsed = NLPResponse(**raw)
            return parsed.model_dump()
    except Exception as exc:
        logger.warning("NLP service call to %s failed (%s), using fallback", service_url, exc)
        return _fallback_intent(text)
