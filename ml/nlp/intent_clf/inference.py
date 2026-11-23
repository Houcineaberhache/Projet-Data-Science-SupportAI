"""Module d'inférence : charge le meilleur modèle et expose classify()."""
import json
import re
from functools import lru_cache

import joblib
import numpy as np

from .nlp_core import ROOT, predict_proba_any

ORDER_ID_RE = re.compile(r"\bORD\d{3,}\b", re.IGNORECASE)
# Les salutations/remerciements sont fusionnés dans out_of_scope (intentions officielles) ;
# on les distingue ici avec une règle simple pour pouvoir répondre poliment (route "canned").
GREETING_RE = re.compile(
    r"^\W*(bonjour|bonsoir|salut|coucou|hello|hi|hey|salam|marhba|ahlan|merci|thanks?|thank you|choukran|mrc|"
    r"bslama|au revoir|goodbye|bye|ok)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _load():
    cfg = json.loads((ROOT / "models" / "config.json").read_text())
    model = joblib.load(ROOT / "models" / f"{cfg['best_model']}.joblib")
    intents = json.loads((ROOT / "data" / "intents.json").read_text())["intents"]
    return cfg, model, intents


def classify(text: str, top_k: int = 3) -> dict:
    cfg, model, intents = _load()
    proba = predict_proba_any(model, [text])[0]
    classes = model.classes_
    order = np.argsort(proba)[::-1]
    top = [{"intent": str(classes[i]), "confidence": round(float(proba[i]), 4)} for i in order[:top_k]]
    best = top[0]
    low = best["confidence"] < cfg["confidence_threshold"]
    meta = intents[best["intent"]]
    m = ORDER_ID_RE.search(text)
    route = "fallback" if low else meta["route"]
    if best["intent"] == "out_of_scope" and GREETING_RE.match(text) and len(text.split()) <= 8:
        route = "canned"
    return {
        "text": text,
        "intent": best["intent"],
        "confidence": best["confidence"],
        "low_confidence": low,
        "route": route,
        "needs_order_id": meta["needs_order_id"],
        "order_id": m.group(0).upper() if m else None,
        "top_k": top,
        "model": cfg["best_model"],
    }
