"""Vérifie que intents.json utilise exactement les intent_id officiels de data/annotations/intents.csv.
Usage : python -m intent_clf.check_intents"""
import json
import sys

import pandas as pd

from .nlp_core import ROOT, repo_root

rr = repo_root()
f = rr / "data" / "annotations" / "intents.csv" if rr else None
if f is None or not f.exists():
    sys.exit("intents.csv introuvable (module utilisé hors du monorepo ?)")
official = set(pd.read_csv(f, encoding="utf-8-sig")["intent_id"].str.strip())
ours = set(json.loads((ROOT / "data" / "intents.json").read_text())["intents"])
print("Officiels :", len(official), "| intents.json :", len(ours))
print("Manquants dans intents.json :", sorted(official - ours) or "aucun")
print("En trop dans intents.json   :", sorted(ours - official) or "aucun")
sys.exit(0 if official == ours else 1)
