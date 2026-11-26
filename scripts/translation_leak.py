"""Détection déterministe des fuites de traduction entre splits.

La détection est volontairement conservatrice : elle ne compare que des paires
de langues différentes, de même intention, avec au moins un nombre commun et
une similarité de concepts >= 0,60. Les traductions FR/EN du domaine sont
ramenées à des concepts communs via un petit lexique explicite.
"""

from __future__ import annotations

import json
import re
import unicodedata
from itertools import combinations

SPLITS = ("train", "val", "test")
DEFAULT_THRESHOLD = 0.60

STOPWORDS = {
    "a", "au", "aux", "by", "de", "des", "du", "elle", "est", "for", "from",
    "is", "la", "le", "les", "lui", "ma", "mon", "mes", "par", "the", "un",
    "une",
}

CONCEPTS = {
    "ancien": "old",
    "ancienne": "old",
    "batterie": "battery",
    "battery": "battery",
    "computer": "pc",
    "couverte": "cover",
    "couvert": "cover",
    "covered": "cover",
    "garantie": "warranty",
    "warranty": "warranty",
    "jour": "day",
    "jours": "day",
    "days": "day",
    "mois": "month",
    "month": "month",
    "months": "month",
    "ordinateur": "pc",
    "pc": "pc",
    "produit": "product",
    "product": "product",
    "retour": "return",
    "return": "return",
    "still": "still",
    "encore": "still",
}


def ascii_fold(text: str) -> str:
    text = (
        (text or "")
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u2009", " ")
    )
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char)).lower()


def concepts(text: str) -> set[str]:
    result = set()
    for token in re.findall(r"[a-z0-9]+", ascii_fold(text)):
        if token.isdigit():
            result.add(token)
            continue
        token = CONCEPTS.get(token, token)
        if token in STOPWORDS or len(token) < 2:
            continue
        result.add(token)
    return result


def jaccard(first: set[str], second: set[str]) -> float:
    if not first and not second:
        return 0.0
    return len(first & second) / len(first | second)


def find_cross_split_translation_leaks(
    rows: list[dict], threshold: float = DEFAULT_THRESHOLD
) -> list[dict]:
    """Renvoie les paires traduites présentes dans deux splits différents."""
    leaks = []
    for first, second in combinations(rows, 2):
        if first.get("split") == second.get("split"):
            continue
        if first.get("language") == second.get("language"):
            continue
        if first.get("intent") != second.get("intent"):
            continue
        first_concepts = concepts(first.get("text", ""))
        second_concepts = concepts(second.get("text", ""))
        shared_numbers = sorted(
            token
            for token in first_concepts & second_concepts
            if token.isdigit()
        )
        if not shared_numbers:
            continue
        score = jaccard(first_concepts, second_concepts)
        if score < threshold:
            continue
        leaks.append(
            {
                "first_id": first["id"],
                "first_split": first.get("split"),
                "first_language": first.get("language"),
                "second_id": second["id"],
                "second_split": second.get("split"),
                "second_language": second.get("language"),
                "intent": first.get("intent"),
                "jaccard": round(score, 4),
                "shared_numbers": shared_numbers,
            }
        )
    leaks.sort(key=lambda item: (item["first_id"], item["second_id"]))
    return leaks


def load_jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]  # type: ignore[name-defined]
