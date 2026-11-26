"""Analyse exploratoire des données SupportAI.

Le script lit uniquement les fichiers publics du dépôt, calcule les métriques,
écrit les figures PNG, ``docs/reports/eda_metrics.json`` et
``docs/reports/eda_findings.md``.

Il n'utilise que la bibliothèque standard et matplotlib. Les sorties ne
contiennent ni horodatage ni chemin absolu. La graine fixe est 42.
"""

from __future__ import annotations

import csv
import json
import random
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 42

# Racine du dépôt : le script est prévu pour être lancé depuis la racine.
ROOT = Path.cwd()
if not (ROOT / "data" / "processed" / "cleaned_corpus.jsonl").exists():
    ROOT = Path(__file__).resolve().parents[1]

FIG_DIR = ROOT / "docs" / "figures" / "eda"
METRICS_PATH = ROOT / "docs" / "reports" / "eda_metrics.json"
FINDINGS_PATH = ROOT / "docs" / "reports" / "eda_findings.md"

FAMILIES = [
    ("FAQ", "faq", "FAQ"),
    ("POL", "policies", "Politiques"),
    ("PRO", "procedures", "Procédures"),
    ("CAT", "product_guides", "Guides produits"),
    ("OPS", "internal_operations", "Opérations internes"),
    ("REG", "legal_summaries", "Synthèses réglementaires"),
]
FAMILY_CODES = [code for code, _, _ in FAMILIES]
FAMILY_LABELS = {code: label for code, _, label in FAMILIES}
LANGUAGES = ["fr", "en"]
LANGUAGE_LABELS = {"fr": "FR", "en": "EN"}
SPLITS = ["train", "val", "test"]
QUESTION_TYPES = ["lexical", "semantic", "procedural", "out_of_corpus"]
QUESTION_TYPE_LABELS = {
    "lexical": "Lexical",
    "semantic": "Sémantique",
    "procedural": "Procédural",
    "out_of_corpus": "Hors corpus",
}
DATASET_LABELS = [
    ("cleaned_corpus", "Corpus nettoyé"),
    ("chunked_corpus", "Corpus chunké"),
    ("intent_dataset", "Intentions"),
    ("rag_eval", "RAG"),
    ("robustness_eval", "Robustesse"),
]
FR_COLOR = "#1f77b4"
EN_COLOR = "#ff7f0e"
SPLIT_COLORS = {"train": "#2ca02c", "val": "#9467bd", "test": "#d62728"}
AUDIENCE_LABELS = {"customer": "Customer", "internal": "Internal"}
FIGURE_FILES = [
    "documents_familles_langue.png",
    "longueurs_documents_chunks.png",
    "parite_fr_en.png",
    "chunks_indexes_audience.png",
    "langues_jeux.png",
    "intentions_split_et_langue.png",
    "doublons_resume.png",
    "questions_longueur.png",
    "questions_types_langue.png",
    "questions_couverture_et_chunks.png",
]


# ---------------------------------------------------------------------------
# Chargement et normalisation
# ---------------------------------------------------------------------------


def read_jsonl(relative_path: str) -> list[dict]:
    """Lit un JSONL public et renvoie la liste des enregistrements."""
    path = ROOT / relative_path
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_manifest() -> list[dict]:
    """Lit le manifeste public (BOM UTF-8 possible)."""
    path = ROOT / "data" / "source_manifest.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_inputs() -> dict:
    """Charge les six entrées publiques autorisées."""
    return {
        "cleaned_corpus": read_jsonl("data/processed/cleaned_corpus.jsonl"),
        "chunked_corpus": read_jsonl("data/processed/chunked_corpus.jsonl"),
        "intent_dataset": read_jsonl("data/annotations/intent_dataset.jsonl"),
        "rag_eval": read_jsonl("data/annotations/rag_eval.jsonl"),
        "robustness_eval": read_jsonl("data/annotations/robustness_eval.jsonl"),
        "manifest": read_manifest(),
    }


def normalize_text(text: str) -> str:
    """Minuscules, accents retirés, ponctuation réduite à des espaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def word_trigrams(text: str) -> set[tuple[str, str, str]]:
    """Trigrammes de mots après normalisation."""
    words = normalize_text(text).split()
    return {tuple(words[index : index + 3]) for index in range(len(words) - 2)}


def jaccard_prepared(
    trigrams_a: set[tuple[str, str, str]],
    trigrams_b: set[tuple[str, str, str]],
    normalized_a: str,
    normalized_b: str,
) -> float:
    """Jaccard des trigrammes ; repli exact pour les textes trop courts."""
    if not trigrams_a and not trigrams_b:
        return 1.0 if normalized_a == normalized_b else 0.0
    if not trigrams_a or not trigrams_b:
        return 0.0
    return len(trigrams_a & trigrams_b) / len(trigrams_a | trigrams_b)


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------


def share(numerator: int, denominator: int) -> float:
    """Part arrondie à quatre décimales."""
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)


def value_stats(values: list[int]) -> dict:
    """Min, médiane, max et moyenne d'une série de valeurs."""
    if not values:
        return {"n": 0, "min": 0, "median": 0.0, "max": 0, "mean": 0.0}
    return {
        "n": len(values),
        "min": int(min(values)),
        "median": round(float(statistics.median(values)), 2),
        "max": int(max(values)),
        "mean": round(float(statistics.mean(values)), 2),
    }


def compute_document_metrics(manifest: list[dict], chunks: list[dict]) -> dict:
    """Documents, longueurs, parité et indexation des chunks."""
    knowledge_base = [
        row for row in manifest if row.get("record_type") == "knowledge_base_document"
    ]

    by_family_language: dict[str, dict[str, dict]] = {}
    for code, _category, _label in FAMILIES:
        by_family_language[code] = {}
        for language in LANGUAGES:
            rows = [
                row
                for row in knowledge_base
                if row["doc_id"].split("-")[0] == code
                and row["language"] == language
            ]
            by_family_language[code][language] = {
                "documents": len(rows),
                "words": sum(int(row["word_count"]) for row in rows),
            }

    parity: dict[str, dict] = {}
    for code in FAMILY_CODES:
        fr = by_family_language[code]["fr"]
        en = by_family_language[code]["en"]
        parity[code] = {
            "documents_fr": fr["documents"],
            "documents_en": en["documents"],
            "documents_ratio_fr_en": round(fr["documents"] / en["documents"], 4)
            if en["documents"]
            else None,
            "words_fr": fr["words"],
            "words_en": en["words"],
            "words_ratio_fr_en": round(fr["words"] / en["words"], 4)
            if en["words"]
            else None,
        }

    documents_by_language = Counter(row["language"] for row in knowledge_base)
    words_by_language = Counter()
    for row in knowledge_base:
        words_by_language[row["language"]] += int(row["word_count"])
    words_total = sum(words_by_language.values())

    document_length = {
        "overall": value_stats([int(row["word_count"]) for row in knowledge_base]),
        "fr": value_stats(
            [
                int(row["word_count"])
                for row in knowledge_base
                if row["language"] == "fr"
            ]
        ),
        "en": value_stats(
            [
                int(row["word_count"])
                for row in knowledge_base
                if row["language"] == "en"
            ]
        ),
    }
    chunk_length = {
        "overall": value_stats([int(row["word_count"]) for row in chunks]),
        "fr": value_stats(
            [int(row["word_count"]) for row in chunks if row["language"] == "fr"]
        ),
        "en": value_stats(
            [int(row["word_count"]) for row in chunks if row["language"] == "en"]
        ),
    }

    chunks_by_audience_index: dict[str, dict] = {}
    for audience in ["customer", "internal"]:
        rows = [row for row in chunks if row["audience"] == audience]
        indexed = sum(1 for row in rows if row["index_in_rag"])
        chunks_by_audience_index[audience] = {
            "total": len(rows),
            "indexed": indexed,
            "not_indexed": len(rows) - indexed,
            "indexed_share": share(indexed, len(rows)),
        }
    total_indexed = sum(1 for row in chunks if row["index_in_rag"])
    exclusion_reasons = Counter(
        row.get("exclusion_reason") or "unknown"
        for row in chunks
        if not row["index_in_rag"]
    )

    return {
        "documents_total": len(knowledge_base),
        "documents_by_language": {
            language: documents_by_language.get(language, 0)
            for language in LANGUAGES
        },
        "words_total": words_total,
        "words_by_language": {
            language: words_by_language.get(language, 0) for language in LANGUAGES
        },
        "words_ratio_fr_en": round(
            words_by_language.get("fr", 0) / words_by_language.get("en", 1), 4
        ),
        "by_family_language": by_family_language,
        "parity": parity,
        "document_length": document_length,
        "chunk_length": chunk_length,
        "chunks_total": len(chunks),
        "chunks_indexed": total_indexed,
        "chunks_not_indexed": len(chunks) - total_indexed,
        "chunks_indexed_share": share(total_indexed, len(chunks)),
        "chunks_by_audience_index": chunks_by_audience_index,
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
    }


def compute_language_metrics(
    cleaned_corpus: list[dict],
    chunked_corpus: list[dict],
    intent_dataset: list[dict],
    rag_eval: list[dict],
    robustness_eval: list[dict],
    manifest: list[dict],
) -> dict:
    """Répartition FR/EN dans chaque jeu."""
    datasets = {
        "cleaned_corpus": cleaned_corpus,
        "chunked_corpus": chunked_corpus,
        "intent_dataset": intent_dataset,
        "rag_eval": rag_eval,
        "robustness_eval": robustness_eval,
    }
    result: dict[str, dict] = {}
    for name, rows in datasets.items():
        counts = Counter(row["language"] for row in rows)
        total = len(rows)
        result[name] = {
            "total": total,
            "fr": counts.get("fr", 0),
            "en": counts.get("en", 0),
            "fr_share": share(counts.get("fr", 0), total),
            "en_share": share(counts.get("en", 0), total),
        }

    knowledge_base = [
        row for row in manifest if row.get("record_type") == "knowledge_base_document"
    ]
    counts = Counter(row["language"] for row in knowledge_base)
    total = len(knowledge_base)
    result["source_manifest_kb"] = {
        "total": total,
        "fr": counts.get("fr", 0),
        "en": counts.get("en", 0),
        "fr_share": share(counts.get("fr", 0), total),
        "en_share": share(counts.get("en", 0), total),
    }
    return result


def compute_intent_metrics(intent_dataset: list[dict]) -> dict:
    """Effectifs par intention, split et langue, ambigus et déséquilibre."""
    labels = sorted({row["intent"] for row in intent_dataset})
    by_intent_split: dict[str, dict] = {}
    by_intent_language: dict[str, dict] = {}
    for label in labels:
        rows = [row for row in intent_dataset if row["intent"] == label]
        split_counts = Counter(row["split"] for row in rows)
        language_counts = Counter(row["language"] for row in rows)
        by_intent_split[label] = {
            **{split: split_counts.get(split, 0) for split in SPLITS},
            "total": len(rows),
        }
        by_intent_language[label] = {
            **{
                language: language_counts.get(language, 0)
                for language in LANGUAGES
            },
            "total": len(rows),
        }

    split_totals = Counter(row["split"] for row in intent_dataset)
    split_stats: dict[str, dict] = {}
    for split in SPLITS:
        counts = Counter(
            row["intent"] for row in intent_dataset if row["split"] == split
        )
        max_count = max(counts.values()) if counts else 0
        min_count = min(counts.values()) if counts else 0
        split_stats[split] = {
            "total": sum(counts.values()),
            "min_count": min_count,
            "max_count": max_count,
            "max_min_ratio": round(max_count / min_count, 4) if min_count else None,
            "majority_labels": sorted(
                label for label, count in counts.items() if count == max_count
            ),
            "min_labels": sorted(
                label for label, count in counts.items() if count == min_count
            ),
        }

    overall_counts = Counter(row["intent"] for row in intent_dataset)
    max_count = max(overall_counts.values())
    min_count = min(overall_counts.values())
    majority_labels = sorted(
        label for label, count in overall_counts.items() if count == max_count
    )
    minority_labels = sorted(
        label for label, count in overall_counts.items() if count == min_count
    )
    ambiguous_rows = [row for row in intent_dataset if row["ambiguous"]]
    ambiguous_examples = [
        {
            "id": row["id"],
            "intent": row["intent"],
            "split": row["split"],
            "language": row["language"],
            "acceptable_labels": list(row.get("acceptable_labels") or []),
        }
        for row in ambiguous_rows
    ]
    language_counts = Counter(row["language"] for row in intent_dataset)

    return {
        "total": len(intent_dataset),
        "labels": labels,
        "by_intent_split": by_intent_split,
        "by_intent_language": by_intent_language,
        "split_totals": {split: split_totals.get(split, 0) for split in SPLITS},
        "split_stats": split_stats,
        "majority": {
            "labels": majority_labels,
            "label": majority_labels[0] if len(majority_labels) == 1 else None,
            "count": max_count,
            "share": share(max_count, len(intent_dataset)),
        },
        "minority": {
            "labels": minority_labels,
            "label": minority_labels[0] if len(minority_labels) == 1 else None,
            "count": min_count,
            "share": share(min_count, len(intent_dataset)),
        },
        "max_min_ratio": round(max_count / min_count, 4) if min_count else None,
        "ambiguous_count": len(ambiguous_rows),
        "ambiguous_share": share(len(ambiguous_rows), len(intent_dataset)),
        "ambiguous_examples": sorted(ambiguous_examples, key=lambda row: row["id"]),
        "language_totals": {
            language: language_counts.get(language, 0) for language in LANGUAGES
        },
    }


def prepare_texts(rows: list[dict], text_key: str, id_key: str) -> list[tuple]:
    """Prépare les textes normalisés et leurs trigrammes."""
    return [
        (row[id_key], normalize_text(row[text_key]), word_trigrams(row[text_key]))
        for row in rows
    ]


def find_duplicates(rows: list[dict], text_key: str, id_key: str) -> dict:
    """Doublons exacts et quasi-doublons dans un même jeu."""
    prepared = prepare_texts(rows, text_key, id_key)
    exact_groups: dict[str, list[str]] = defaultdict(list)
    for identifier, normalized, _trigrams in prepared:
        exact_groups[normalized].append(identifier)
    exact_groups_list = sorted(
        sorted(group) for group in exact_groups.values() if len(group) > 1
    )
    exact_pairs = [
        {"id_a": first, "id_b": second}
        for group in exact_groups_list
        for first, second in combinations(group, 2)
    ]
    exact_pairs.sort(key=lambda pair: (pair["id_a"], pair["id_b"]))

    quasi_pairs: list[dict] = []
    for (id_a, norm_a, tri_a), (id_b, norm_b, tri_b) in combinations(prepared, 2):
        if norm_a == norm_b:
            continue
        score = jaccard_prepared(tri_a, tri_b, norm_a, norm_b)
        if score >= 0.8:
            quasi_pairs.append(
                {"id_a": id_a, "id_b": id_b, "jaccard": round(score, 4)}
            )
    quasi_pairs.sort(key=lambda pair: (pair["id_a"], pair["id_b"]))

    return {
        "n": len(rows),
        "exact_groups": exact_groups_list,
        "exact_pairs": exact_pairs,
        "quasi_pairs": quasi_pairs,
        "exact_pair_count": len(exact_pairs),
        "quasi_pair_count": len(quasi_pairs),
    }


def find_cross_duplicates(
    rows_a: list[dict],
    rows_b: list[dict],
    text_key_a: str,
    text_key_b: str,
    id_key_a: str,
    id_key_b: str,
) -> dict:
    """Doublons exacts et quasi-doublons entre deux jeux."""
    prepared_a = prepare_texts(rows_a, text_key_a, id_key_a)
    prepared_b = prepare_texts(rows_b, text_key_b, id_key_b)
    exact_pairs: list[dict] = []
    quasi_pairs: list[dict] = []
    for id_a, norm_a, tri_a in prepared_a:
        for id_b, norm_b, tri_b in prepared_b:
            if norm_a == norm_b:
                exact_pairs.append({"id_a": id_a, "id_b": id_b})
                continue
            score = jaccard_prepared(tri_a, tri_b, norm_a, norm_b)
            if score >= 0.8:
                quasi_pairs.append(
                    {"id_a": id_a, "id_b": id_b, "jaccard": round(score, 4)}
                )
    exact_pairs.sort(key=lambda pair: (pair["id_a"], pair["id_b"]))
    quasi_pairs.sort(key=lambda pair: (pair["id_a"], pair["id_b"]))
    return {
        "n_a": len(rows_a),
        "n_b": len(rows_b),
        "pairs_compared": len(rows_a) * len(rows_b),
        "exact_pairs": exact_pairs,
        "quasi_pairs": quasi_pairs,
        "exact_pair_count": len(exact_pairs),
        "quasi_pair_count": len(quasi_pairs),
    }


def compute_intent_duplicate_metrics(intent_dataset: list[dict]) -> dict:
    """Doublons intra-split et fuite entre splits."""
    by_split = {
        split: [row for row in intent_dataset if row["split"] == split]
        for split in SPLITS
    }
    intra_split = {
        split: find_duplicates(by_split[split], "text", "id") for split in SPLITS
    }
    cross_results = [
        find_cross_duplicates(
            by_split[first],
            by_split[second],
            "text",
            "text",
            "id",
            "id",
        )
        for first, second in combinations(SPLITS, 2)
    ]
    exact_pairs = sorted(
        [
            pair
            for result in cross_results
            for pair in result["exact_pairs"]
        ],
        key=lambda pair: (pair["id_a"], pair["id_b"]),
    )
    quasi_pairs = sorted(
        [
            pair
            for result in cross_results
            for pair in result["quasi_pairs"]
        ],
        key=lambda pair: (pair["id_a"], pair["id_b"]),
    )
    return {
        "intra_split": intra_split,
        "cross_split": {
            "pairs_compared": sum(result["pairs_compared"] for result in cross_results),
            "exact_pairs": exact_pairs,
            "quasi_pairs": quasi_pairs,
            "exact_pair_count": len(exact_pairs),
            "quasi_pair_count": len(quasi_pairs),
        },
    }


def compute_duplicate_metrics(
    cleaned_corpus: list[dict],
    chunked_corpus: list[dict],
    intent_dataset: list[dict],
    rag_eval: list[dict],
    robustness_eval: list[dict],
) -> dict:
    """Toutes les comparaisons de doublons demandées."""
    return {
        "cleaned_corpus": find_duplicates(cleaned_corpus, "text", "record_id"),
        "chunked_corpus": find_duplicates(chunked_corpus, "text", "chunk_id"),
        "intent_dataset": compute_intent_duplicate_metrics(intent_dataset),
        "rag_vs_robustness": find_cross_duplicates(
            rag_eval, robustness_eval, "question", "question", "id", "id"
        ),
        "rag_vs_intent_dataset": find_cross_duplicates(
            rag_eval, intent_dataset, "question", "text", "id", "id"
        ),
    }


def compute_question_metrics(rag_eval: list[dict], manifest: list[dict]) -> dict:
    """Types, longueurs, couverture et chunks gold des questions RAG."""
    by_type_language: dict[str, dict] = {}
    for question_type in QUESTION_TYPES:
        rows = [row for row in rag_eval if row["question_type"] == question_type]
        counts = Counter(row["language"] for row in rows)
        by_type_language[question_type] = {
            **{language: counts.get(language, 0) for language in LANGUAGES},
            "total": len(rows),
        }

    language_counts = Counter(row["language"] for row in rag_eval)
    type_counts = Counter(row["question_type"] for row in rag_eval)

    length_by_language = {
        language: value_stats(
            [
                len(row["question"].split())
                for row in rag_eval
                if row["language"] == language
            ]
        )
        for language in LANGUAGES
    }
    length_by_type = {
        question_type: value_stats(
            [
                len(row["question"].split())
                for row in rag_eval
                if row["question_type"] == question_type
            ]
        )
        for question_type in QUESTION_TYPES
    }
    length_by_type_language: dict[str, dict[str, dict]] = {}
    for question_type in QUESTION_TYPES:
        length_by_type_language[question_type] = {}
        for language in LANGUAGES:
            length_by_type_language[question_type][language] = value_stats(
                [
                    len(row["question"].split())
                    for row in rag_eval
                    if row["question_type"] == question_type
                    and row["language"] == language
                ]
            )

    coverage = Counter()
    for row in rag_eval:
        for doc_id in row.get("gold_doc_ids") or []:
            coverage[doc_id] += 1
    candidate_documents = sorted(
        {
            row["doc_id"]
            for row in manifest
            if row.get("record_type") == "knowledge_base_document"
        }
    )
    covered_documents = sorted(coverage)
    uncovered_documents = sorted(set(candidate_documents) - set(covered_documents))

    gold_chunks = Counter(len(row.get("gold_chunk_ids") or []) for row in rag_eval)
    gold_docs = Counter(len(row.get("gold_doc_ids") or []) for row in rag_eval)

    return {
        "rag_total": len(rag_eval),
        "by_type_language": by_type_language,
        "by_language": {
            language: language_counts.get(language, 0) for language in LANGUAGES
        },
        "by_type": {
            question_type: type_counts.get(question_type, 0)
            for question_type in QUESTION_TYPES
        },
        "length": {
            "overall": value_stats(
                [len(row["question"].split()) for row in rag_eval]
            ),
            "by_language": length_by_language,
            "by_type": length_by_type,
            "by_type_language": length_by_type_language,
        },
        "gold_chunks_per_question": {
            str(count): gold_chunks.get(count, 0) for count in range(0, 3)
        },
        "gold_docs_per_question": {
            str(count): gold_docs.get(count, 0) for count in range(0, 3)
        },
        "coverage_by_document": dict(sorted(coverage.items())),
        "covered_documents": len(covered_documents),
        "candidate_documents": len(candidate_documents),
        "uncovered_documents": uncovered_documents,
        "answerable": sum(1 for row in rag_eval if row.get("answerable")),
        "out_of_corpus": type_counts.get("out_of_corpus", 0),
    }


def compute_robustness_metrics(robustness_eval: list[dict]) -> dict:
    """Répartition des cas de robustesse par catégorie et langue."""
    categories = sorted({row["category"] for row in robustness_eval})
    by_category_language: dict[str, dict] = {}
    for category in categories:
        rows = [row for row in robustness_eval if row["category"] == category]
        counts = Counter(row["language"] for row in rows)
        by_category_language[category] = {
            **{language: counts.get(language, 0) for language in LANGUAGES},
            "total": len(rows),
        }
    language_counts = Counter(row["language"] for row in robustness_eval)
    return {
        "total": len(robustness_eval),
        "by_category_language": by_category_language,
        "by_category": {
            category: by_category_language[category]["total"]
            for category in categories
        },
        "by_language": {
            language: language_counts.get(language, 0) for language in LANGUAGES
        },
    }


def compute_metrics() -> dict:
    """Calcule toutes les métriques et les constats."""
    inputs = load_inputs()
    metrics = {
        "meta": {
            "seed": SEED,
            "inputs": {
                "cleaned_corpus": "data/processed/cleaned_corpus.jsonl",
                "chunked_corpus": "data/processed/chunked_corpus.jsonl",
                "intent_dataset": "data/annotations/intent_dataset.jsonl",
                "rag_eval": "data/annotations/rag_eval.jsonl",
                "robustness_eval": "data/annotations/robustness_eval.jsonl",
                "source_manifest": "data/source_manifest.csv",
            },
            "private_data_used": False,
            "figures": [
                f"docs/figures/eda/{name}" for name in FIGURE_FILES
            ],
        },
        "documents": compute_document_metrics(
            inputs["manifest"], inputs["chunked_corpus"]
        ),
        "languages": compute_language_metrics(
            inputs["cleaned_corpus"],
            inputs["chunked_corpus"],
            inputs["intent_dataset"],
            inputs["rag_eval"],
            inputs["robustness_eval"],
            inputs["manifest"],
        ),
        "intents": compute_intent_metrics(inputs["intent_dataset"]),
        "duplicates": compute_duplicate_metrics(
            inputs["cleaned_corpus"],
            inputs["chunked_corpus"],
            inputs["intent_dataset"],
            inputs["rag_eval"],
            inputs["robustness_eval"],
        ),
        "questions": compute_question_metrics(
            inputs["rag_eval"], inputs["manifest"]
        ),
        "robustness": compute_robustness_metrics(inputs["robustness_eval"]),
    }
    metrics["findings"] = build_findings(metrics)
    return metrics


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------


def fmt_int(value: int | float) -> str:
    """Entier avec espaces de milliers (format français)."""
    return f"{int(value):,}".replace(",", " ")


def fmt_num(value: int | float) -> str:
    """Nombre avec virgule décimale si nécessaire."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def fmt_ratio(value: float | None) -> str:
    """Ratio à deux décimales, virgule française."""
    if value is None:
        return "n/a"
    return f"{value:.2f}".replace(".", ",")


def fmt_pct(numerator: int, denominator: int) -> str:
    """Pourcentage à une décimale, virgule française."""
    if not denominator:
        return "n/a"
    return f"{100.0 * numerator / denominator:.1f} %".replace(".", ",")


def md_table(headers: list[str], rows: list[list], aligns: list[str] | None = None) -> str:
    """Tableau Markdown simple."""
    if aligns is None:
        aligns = ["---"] + ["---:"] * (len(headers) - 1)
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "| " + " | ".join(aligns) + " |",
    ]
    for row in rows:
        cells = [str(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def table_documents(metrics: dict) -> str:
    """Tableaux de la section 1."""
    documents = metrics["documents"]
    rows = []
    for code in FAMILY_CODES:
        fr = documents["by_family_language"][code]["fr"]
        en = documents["by_family_language"][code]["en"]
        rows.append(
            [
                FAMILY_LABELS[code],
                fmt_int(fr["documents"]),
                fmt_int(en["documents"]),
                fmt_int(fr["words"]),
                fmt_int(en["words"]),
                fmt_ratio(documents["parity"][code]["words_ratio_fr_en"]),
            ]
        )
    rows.append(
        [
            "**Total**",
            fmt_int(documents["documents_by_language"]["fr"]),
            fmt_int(documents["documents_by_language"]["en"]),
            fmt_int(documents["words_by_language"]["fr"]),
            fmt_int(documents["words_by_language"]["en"]),
            fmt_ratio(documents["words_ratio_fr_en"]),
        ]
    )
    table_families = md_table(
        ["Famille", "Docs FR", "Docs EN", "Mots FR", "Mots EN", "Ratio mots FR/EN"],
        rows,
    )

    length_rows = []
    for scope, key in [
        ("Documents (manifeste)", "document_length"),
        ("Chunks", "chunk_length"),
    ]:
        for language in ["overall", "fr", "en"]:
            stats = documents[key][language]
            label = scope if language == "overall" else f"— {LANGUAGE_LABELS[language]}"
            length_rows.append(
                [
                    label,
                    fmt_int(stats["n"]),
                    fmt_int(stats["min"]),
                    fmt_num(stats["median"]),
                    fmt_int(stats["max"]),
                    fmt_num(stats["mean"]),
                ]
            )
    table_lengths = md_table(
        ["Périmètre", "n", "Min", "Médiane", "Max", "Moyenne"],
        length_rows,
    )

    audience_rows = []
    for audience in ["customer", "internal"]:
        stats = documents["chunks_by_audience_index"][audience]
        audience_rows.append(
            [
                AUDIENCE_LABELS[audience],
                fmt_int(stats["total"]),
                fmt_int(stats["indexed"]),
                fmt_int(stats["not_indexed"]),
                fmt_pct(stats["indexed"], stats["total"]),
            ]
        )
    audience_rows.append(
        [
            "**Total**",
            fmt_int(documents["chunks_total"]),
            fmt_int(documents["chunks_indexed"]),
            fmt_int(documents["chunks_not_indexed"]),
            fmt_pct(documents["chunks_indexed"], documents["chunks_total"]),
        ]
    )
    table_audience = md_table(
        ["Audience", "Chunks", "Indexés", "Non indexés", "Part indexée"],
        audience_rows,
    )

    return "\n\n".join(
        [
            "**Tableau 1.1 — Documents et mots par famille et par langue**\n\n"
            + table_families,
            "**Tableau 1.2 — Longueur des documents et des chunks (en mots)**\n\n"
            + table_lengths,
            "**Tableau 1.3 — Indexation des chunks dans le RAG par audience**\n\n"
            + table_audience,
        ]
    )


def table_languages(metrics: dict) -> str:
    """Tableaux de la section 2."""
    languages = metrics["languages"]
    rows = []
    for key, label in [
        ("cleaned_corpus", "Corpus nettoyé"),
        ("chunked_corpus", "Corpus chunké"),
        ("source_manifest_kb", "Manifeste (documents)"),
        ("intent_dataset", "Intentions"),
        ("rag_eval", "RAG"),
        ("robustness_eval", "Robustesse"),
    ]:
        stats = languages[key]
        rows.append(
            [
                label,
                fmt_int(stats["total"]),
                fmt_int(stats["fr"]),
                fmt_int(stats["en"]),
                fmt_pct(stats["fr"], stats["total"]),
                fmt_pct(stats["en"], stats["total"]),
            ]
        )
    table_languages = md_table(
        ["Jeu", "Total", "FR", "EN", "Part FR", "Part EN"],
        rows,
    )

    robustness_rows = []
    for category, stats in sorted(
        metrics["robustness"]["by_category_language"].items()
    ):
        robustness_rows.append(
            [
                category,
                fmt_int(stats["fr"]),
                fmt_int(stats["en"]),
                fmt_int(stats["total"]),
            ]
        )
    table_robustness = md_table(
        ["Catégorie de robustesse", "FR", "EN", "Total"],
        robustness_rows,
    )

    return "\n\n".join(
        [
            "**Tableau 2.1 — Répartition FR/EN dans les jeux**\n\n"
            + table_languages,
            "**Tableau 2.2 — Cas de robustesse par catégorie et par langue**\n\n"
            + table_robustness,
        ]
    )


def table_intents(metrics: dict) -> str:
    """Tableaux de la section 3."""
    intents = metrics["intents"]
    rows = []
    for label in intents["labels"]:
        split_counts = intents["by_intent_split"][label]
        language_counts = intents["by_intent_language"][label]
        rows.append(
            [
                label,
                fmt_int(split_counts["train"]),
                fmt_int(split_counts["val"]),
                fmt_int(split_counts["test"]),
                fmt_int(split_counts["total"]),
                fmt_int(language_counts["fr"]),
                fmt_int(language_counts["en"]),
            ]
        )
    rows.append(
        [
            "**Total**",
            fmt_int(intents["split_totals"]["train"]),
            fmt_int(intents["split_totals"]["val"]),
            fmt_int(intents["split_totals"]["test"]),
            fmt_int(intents["total"]),
            fmt_int(intents["language_totals"]["fr"]),
            fmt_int(intents["language_totals"]["en"]),
        ]
    )
    table_effectifs = md_table(
        [
            "Intention",
            "Train",
            "Val",
            "Test",
            "Total",
            "FR",
            "EN",
        ],
        rows,
    )

    split_rows = []
    for split in SPLITS:
        stats = intents["split_stats"][split]
        majority = ", ".join(stats["majority_labels"])
        if len(stats["majority_labels"]) > 3:
            majority = f"ex æquo ({len(stats['majority_labels'])} classes à {stats['max_count']})"
        split_rows.append(
            [
                split,
                fmt_int(stats["total"]),
                fmt_int(stats["min_count"]),
                fmt_int(stats["max_count"]),
                fmt_ratio(stats["max_min_ratio"]),
                majority,
            ]
        )
    table_splits = md_table(
        ["Split", "Total", "Classe min", "Classe max", "Ratio max/min", "Majoritaire"],
        split_rows,
    )

    ambiguous_rows = []
    for example in intents["ambiguous_examples"]:
        ambiguous_rows.append(
            [
                example["id"],
                example["intent"],
                example["split"],
                example["language"],
                ", ".join(example["acceptable_labels"]),
            ]
        )
    if not ambiguous_rows:
        ambiguous_rows = [["Aucun", "—", "—", "—", "—"]]
    table_ambiguous = md_table(
        ["ID", "Intention", "Split", "Langue", "Étiquettes acceptables"],
        ambiguous_rows,
    )

    return "\n\n".join(
        [
            "**Tableau 3.1 — Effectifs par intention, split et langue**\n\n"
            + table_effectifs,
            "**Tableau 3.2 — Équilibre par split**\n\n" + table_splits,
            "**Tableau 3.3 — Exemples ambigus**\n\n" + table_ambiguous,
        ]
    )


def table_duplicates(metrics: dict) -> str:
    """Tableau de la section 4."""
    duplicates = metrics["duplicates"]
    rows = [
        [
            "Corpus nettoyé",
            fmt_int(len(duplicates["cleaned_corpus"]["exact_groups"])),
            fmt_int(duplicates["cleaned_corpus"]["exact_pair_count"]),
            fmt_int(duplicates["cleaned_corpus"]["quasi_pair_count"]),
        ],
        [
            "Corpus chunké",
            fmt_int(len(duplicates["chunked_corpus"]["exact_groups"])),
            fmt_int(duplicates["chunked_corpus"]["exact_pair_count"]),
            fmt_int(duplicates["chunked_corpus"]["quasi_pair_count"]),
        ],
    ]
    for split in SPLITS:
        stats = duplicates["intent_dataset"]["intra_split"][split]
        rows.append(
            [
                f"Intentions — intra {split}",
                fmt_int(len(stats["exact_groups"])),
                fmt_int(stats["exact_pair_count"]),
                fmt_int(stats["quasi_pair_count"]),
            ]
        )
    cross = duplicates["intent_dataset"]["cross_split"]
    rows.append(
        [
            "Intentions — entre splits",
            "—",
            fmt_int(cross["exact_pair_count"]),
            fmt_int(cross["quasi_pair_count"]),
        ]
    )
    for key, label in [
        ("rag_vs_robustness", "RAG vs robustesse"),
        ("rag_vs_intent_dataset", "RAG vs intentions"),
    ]:
        stats = duplicates[key]
        rows.append(
            [
                label,
                "—",
                fmt_int(stats["exact_pair_count"]),
                fmt_int(stats["quasi_pair_count"]),
            ]
        )
    table = md_table(
        ["Périmètre", "Groupes exacts", "Paires exactes", "Paires quasi"],
        rows,
    )
    all_pairs = []
    for key in ["cleaned_corpus", "chunked_corpus"]:
        all_pairs.extend(duplicates[key]["exact_pairs"])
        all_pairs.extend(duplicates[key]["quasi_pairs"])
    for split in SPLITS:
        stats = duplicates["intent_dataset"]["intra_split"][split]
        all_pairs.extend(stats["exact_pairs"])
        all_pairs.extend(stats["quasi_pairs"])
    all_pairs.extend(cross["exact_pairs"])
    all_pairs.extend(cross["quasi_pairs"])
    for key in ["rag_vs_robustness", "rag_vs_intent_dataset"]:
        all_pairs.extend(duplicates[key]["exact_pairs"])
        all_pairs.extend(duplicates[key]["quasi_pairs"])
    if all_pairs:
        pair_rows = [
            [pair.get("id_a", ""), pair.get("id_b", ""), fmt_ratio(pair.get("jaccard"))]
            for pair in all_pairs
        ]
        table_pairs = md_table(["ID A", "ID B", "Jaccard"], pair_rows)
    else:
        table_pairs = "Aucune paire exacte ou quasi-doublon (Jaccard trigrammes ≥ 0,80) détectée."
    return "\n\n".join(
        [
            "**Tableau 4.1 — Synthèse des doublons**\n\n" + table,
            "**Tableau 4.2 — Paires détectées**\n\n" + table_pairs,
        ]
    )


def table_questions(metrics: dict) -> str:
    """Tableaux de la section 5."""
    questions = metrics["questions"]
    type_rows = []
    for question_type in QUESTION_TYPES:
        stats = questions["by_type_language"][question_type]
        type_rows.append(
            [
                QUESTION_TYPE_LABELS[question_type],
                fmt_int(stats["fr"]),
                fmt_int(stats["en"]),
                fmt_int(stats["total"]),
                fmt_pct(stats["fr"], stats["total"]),
                fmt_pct(stats["en"], stats["total"]),
            ]
        )
    type_rows.append(
        [
            "**Total**",
            fmt_int(questions["by_language"]["fr"]),
            fmt_int(questions["by_language"]["en"]),
            fmt_int(questions["rag_total"]),
            fmt_pct(questions["by_language"]["fr"], questions["rag_total"]),
            fmt_pct(questions["by_language"]["en"], questions["rag_total"]),
        ]
    )
    table_types = md_table(
        ["Type", "FR", "EN", "Total", "Part FR", "Part EN"],
        type_rows,
    )

    length_rows = []
    for question_type in QUESTION_TYPES:
        for language in LANGUAGES:
            stats = questions["length"]["by_type_language"][question_type][language]
            length_rows.append(
                [
                    QUESTION_TYPE_LABELS[question_type],
                    LANGUAGE_LABELS[language],
                    fmt_int(stats["n"]),
                    fmt_int(stats["min"]),
                    fmt_num(stats["median"]),
                    fmt_int(stats["max"]),
                    fmt_num(stats["mean"]),
                ]
            )
    for language in LANGUAGES:
        stats = questions["length"]["by_language"][language]
        length_rows.append(
            [
                "**Total**",
                LANGUAGE_LABELS[language],
                fmt_int(stats["n"]),
                fmt_int(stats["min"]),
                fmt_num(stats["median"]),
                fmt_int(stats["max"]),
                fmt_num(stats["mean"]),
            ]
        )
    table_lengths = md_table(
        ["Type", "Langue", "n", "Min", "Médiane", "Max", "Moyenne"],
        length_rows,
    )

    gold_rows = []
    for count in ["0", "1", "2"]:
        chunks = questions["gold_chunks_per_question"][count]
        docs = questions["gold_docs_per_question"][count]
        gold_rows.append(
            [
                count,
                fmt_int(chunks),
                fmt_pct(chunks, questions["rag_total"]),
                fmt_int(docs),
                fmt_pct(docs, questions["rag_total"]),
            ]
        )
    table_gold = md_table(
        ["Nombre de gold", "Questions (chunks)", "Part", "Questions (docs)", "Part"],
        gold_rows,
    )

    coverage_rows = [
        [doc_id, fmt_int(count)]
        for doc_id, count in questions["coverage_by_document"].items()
    ]
    table_coverage = md_table(["Document gold", "Questions"], coverage_rows)

    return "\n\n".join(
        [
            "**Tableau 5.1 — Types de questions par langue**\n\n" + table_types,
            "**Tableau 5.2 — Longueur des questions en mots, par type et par langue**\n\n"
            + table_lengths,
            "**Tableau 5.3 — Nombre de chunks et de documents gold par question**\n\n"
            + table_gold,
            "**Tableau 5.4 — Couverture par document gold**\n\n" + table_coverage,
        ]
    )


def table_dispatch(section: str) -> str:
    """Retourne le tableau Markdown d'une section."""
    metrics = load_metrics()
    if section == "documents":
        return table_documents(metrics)
    if section == "languages":
        return table_languages(metrics)
    if section == "intents":
        return table_intents(metrics)
    if section == "duplicates":
        return table_duplicates(metrics)
    if section == "questions":
        return table_questions(metrics)
    raise ValueError(f"Section inconnue : {section}")


# Alias lisible pour le notebook.
metrics_table = table_dispatch


# ---------------------------------------------------------------------------
# Constats
# ---------------------------------------------------------------------------


def build_findings(metrics: dict) -> list[str]:
    """Constats chiffrés, calculés à partir des métriques."""
    documents = metrics["documents"]
    languages = metrics["languages"]
    intents = metrics["intents"]
    questions = metrics["questions"]
    duplicates = metrics["duplicates"]

    cleaned = languages["cleaned_corpus"]
    chunked = languages["chunked_corpus"]
    customer = documents["chunks_by_audience_index"]["customer"]
    internal = documents["chunks_by_audience_index"]["internal"]
    not_indexed = documents["chunks_not_indexed"]
    train = intents["split_stats"]["train"]
    val = intents["split_stats"]["val"]

    family_docs = {
        code: documents["by_family_language"][code]["fr"]["documents"]
        for code in FAMILY_CODES
    }
    ambiguous_ids = ", ".join(
        example["id"] for example in intents["ambiguous_examples"]
    )
    ambiguous_splits = sorted(
        {example["split"] for example in intents["ambiguous_examples"]}
    )
    ambiguous_intents = sorted(
        {example["intent"] for example in intents["ambiguous_examples"]}
    )
    acceptable_labels = sorted(
        {
            label
            for example in intents["ambiguous_examples"]
            for label in example["acceptable_labels"]
        }
    )

    language_patterns = Counter(
        (stats["fr"], stats["en"])
        for stats in intents["by_intent_language"].values()
    )
    common_pattern, _common_count = language_patterns.most_common(1)[0]
    language_exceptions = [
        (label, stats["fr"], stats["en"])
        for label, stats in intents["by_intent_language"].items()
        if (stats["fr"], stats["en"]) != common_pattern
    ]
    exception_text = ", ".join(
        f"{label} ({fr}/{en})" for label, fr, en in language_exceptions
    )
    if exception_text:
        exception_text = f", sauf {exception_text}"
    else:
        exception_text = ""

    procedural = questions["by_type_language"]["procedural"]
    semantic = questions["by_type_language"]["semantic"]
    gold_chunks = questions["gold_chunks_per_question"]
    gold_docs = questions["gold_docs_per_question"]
    uncovered = ", ".join(questions["uncovered_documents"])

    return [
        (
            f"Le corpus nettoyé contient {fmt_int(cleaned['total'])} sections "
            f"({fmt_int(cleaned['fr'])} FR, {fmt_int(cleaned['en'])} EN) et le corpus "
            f"chunké {fmt_int(chunked['total'])} chunks ({fmt_int(chunked['fr'])} FR, "
            f"{fmt_int(chunked['en'])} EN) : la parité en nombre d'unités est exacte."
        ),
        (
            f"Le manifeste décrit {fmt_int(documents['documents_total'])} fichiers de "
            f"connaissance ({fmt_int(documents['documents_by_language']['fr'])} FR, "
            f"{fmt_int(documents['documents_by_language']['en'])} EN) pour "
            f"{fmt_int(documents['words_total'])} mots ; les documents FR totalisent "
            f"{fmt_int(documents['words_by_language']['fr'])} mots contre "
            f"{fmt_int(documents['words_by_language']['en'])} en EN (ratio "
            f"{fmt_ratio(documents['words_ratio_fr_en'])}), donc la parité en mots "
            "n'est pas parfaite."
        ),
        (
            f"Les familles sont déséquilibrées : {family_docs['POL']} politiques et "
            f"{family_docs['FAQ']} FAQ par langue, contre {family_docs['PRO']} "
            f"procédures et {family_docs['REG']} synthèses réglementaires par langue."
        ),
        (
            f"La longueur médiane d'un document est de "
            f"{fmt_num(documents['document_length']['overall']['median'])} mots "
            f"(min {fmt_int(documents['document_length']['overall']['min'])}, max "
            f"{fmt_int(documents['document_length']['overall']['max'])}) ; celle d'un "
            f"chunk est de {fmt_num(documents['chunk_length']['overall']['median'])} "
            f"mots (min {fmt_int(documents['chunk_length']['overall']['min'])}, max "
            f"{fmt_int(documents['chunk_length']['overall']['max'])})."
        ),
        (
            f"{fmt_int(documents['chunks_indexed'])} chunks sur "
            f"{fmt_int(documents['chunks_total'])} "
            f"({fmt_pct(documents['chunks_indexed'], documents['chunks_total'])}) sont "
            f"indexés dans le RAG ; la part est de "
            f"{fmt_pct(customer['indexed'], customer['total'])} pour l'audience "
            f"customer ({fmt_int(customer['indexed'])}/{fmt_int(customer['total'])}) et "
            f"{fmt_pct(internal['indexed'], internal['total'])} pour l'audience internal "
            f"({fmt_int(internal['indexed'])}/{fmt_int(internal['total'])}). Les "
            f"{fmt_int(not_indexed)} chunks exclus sont marqués too_short."
        ),
        (
            f"Le jeu d'intentions contient {fmt_int(intents['total'])} exemples : "
            f"{fmt_int(intents['split_totals']['train'])} train, "
            f"{fmt_int(intents['split_totals']['val'])} val, "
            f"{fmt_int(intents['split_totals']['test'])} test. La classe majoritaire "
            f"est {intents['majority']['label']} ({fmt_int(intents['majority']['count'])}), "
            f"la minoritaire {intents['minority']['label']} "
            f"({fmt_int(intents['minority']['count'])}), soit un ratio max/min de "
            f"{fmt_ratio(intents['max_min_ratio'])}."
        ),
        (
            f"Les val/test sont équilibrés à {fmt_int(val['max_count'])} exemples par "
            f"intention ; le train varie de {fmt_int(train['min_count'])} "
            f"({', '.join(train['min_labels'])}) à {fmt_int(train['max_count'])} "
            f"({', '.join(train['majority_labels'])})."
        ),
        (
            f"{fmt_int(intents['ambiguous_count'])} exemples sur "
            f"{fmt_int(intents['total'])} "
            f"({fmt_pct(intents['ambiguous_count'], intents['total'])}) sont marqués "
            f"ambigus : {ambiguous_ids}, tous en {', '.join(ambiguous_splits)} et "
            f"{', '.join(ambiguous_intents)} avec {', '.join(acceptable_labels)} comme "
            "étiquettes acceptables."
        ),
        (
            f"Le jeu d'intentions est à "
            f"{fmt_pct(intents['language_totals']['fr'], intents['total'])} FR "
            f"({fmt_int(intents['language_totals']['fr'])}) et "
            f"{fmt_pct(intents['language_totals']['en'], intents['total'])} EN "
            f"({fmt_int(intents['language_totals']['en'])}) ; chaque intention suit ce "
            f"déséquilibre ({common_pattern[0]} FR/{common_pattern[1]} EN)"
            f"{exception_text}."
        ),
        (
            "Aucun doublon exact ni quasi-doublon (Jaccard trigrammes ≥ 0,80) n'est "
            "détecté dans le corpus nettoyé, le corpus chunké, le jeu d'intentions "
            "(intra- et inter-splits), entre rag_eval et robustness_eval, ou entre "
            "rag_eval et intent_dataset."
        ),
        (
            f"Le jeu RAG contient {fmt_int(questions['rag_total'])} questions "
            f"({fmt_int(questions['by_language']['fr'])} FR, "
            f"{fmt_int(questions['by_language']['en'])} EN) : "
            f"{fmt_int(semantic['total'])} sémantiques, "
            f"{fmt_int(questions['by_type']['lexical'])} lexicales, "
            f"{fmt_int(procedural['total'])} procédurales et "
            f"{fmt_int(questions['by_type']['out_of_corpus'])} hors corpus. Les "
            f"procédurales sont majoritairement EN ({fmt_int(procedural['en'])} EN vs "
            f"{fmt_int(procedural['fr'])} FR, soit "
            f"{fmt_pct(procedural['en'], procedural['total'])} EN), alors que les "
            f"sémantiques sont majoritairement FR ({fmt_int(semantic['fr'])} FR vs "
            f"{fmt_int(semantic['en'])} EN)."
        ),
        (
            f"Parmi les {fmt_int(questions['answerable'])} questions answerable, "
            f"{fmt_int(gold_chunks['1'])} ont un seul chunk gold et "
            f"{fmt_int(gold_chunks['2'])} en ont deux ; "
            f"{fmt_int(gold_docs['1'])} ont un seul document gold et "
            f"{fmt_int(gold_docs['2'])} en ont deux. Les "
            f"{fmt_int(questions['out_of_corpus'])} questions hors corpus n'ont aucun "
            f"gold. La couverture atteint {fmt_int(questions['covered_documents'])} "
            f"documents sur {fmt_int(questions['candidate_documents'])} "
            f"({fmt_pct(questions['covered_documents'], questions['candidate_documents'])}) ; "
            f"{uncovered} ne sont jamais gold."
        ),
    ]


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def _save_figure(figure: plt.Figure, filename: str) -> Path:
    """Sauvegarde une figure avec des métadonnées stables."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / filename
    figure.savefig(
        path,
        dpi=150,
        bbox_inches="tight",
        metadata={"Software": "SupportAI EDA"},
    )
    plt.close(figure)
    return path


def _setup_axes(axes) -> None:
    """Style commun des axes."""
    for axis in axes:
        axis.grid(True, axis="y", alpha=0.25)
        axis.set_axisbelow(True)


def plot_documents(metrics: dict) -> Path:
    """Graphique 1a : documents et mots par famille et par langue."""
    documents = metrics["documents"]
    labels = [FAMILY_LABELS[code] for code in FAMILY_CODES]
    positions = list(range(len(FAMILY_CODES)))
    width = 0.38
    fr_documents = [
        documents["by_family_language"][code]["fr"]["documents"]
        for code in FAMILY_CODES
    ]
    en_documents = [
        documents["by_family_language"][code]["en"]["documents"]
        for code in FAMILY_CODES
    ]
    fr_words = [
        documents["by_family_language"][code]["fr"]["words"]
        for code in FAMILY_CODES
    ]
    en_words = [
        documents["by_family_language"][code]["en"]["words"]
        for code in FAMILY_CODES
    ]

    figure, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    bars_fr = axes[0].bar(
        [position - width / 2 for position in positions],
        fr_documents,
        width,
        label="FR",
        color=FR_COLOR,
    )
    bars_en = axes[0].bar(
        [position + width / 2 for position in positions],
        en_documents,
        width,
        label="EN",
        color=EN_COLOR,
    )
    axes[0].set_title("Nombre de documents")
    axes[0].set_ylabel("Documents")
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels(labels, rotation=25, ha="right")
    axes[0].bar_label(bars_fr, padding=2, fontsize=7)
    axes[0].bar_label(bars_en, padding=2, fontsize=7)
    axes[0].legend(title="Langue")

    bars_fr = axes[1].bar(
        [position - width / 2 for position in positions],
        fr_words,
        width,
        label="FR",
        color=FR_COLOR,
    )
    bars_en = axes[1].bar(
        [position + width / 2 for position in positions],
        en_words,
        width,
        label="EN",
        color=EN_COLOR,
    )
    axes[1].set_title("Nombre de mots (manifeste)")
    axes[1].set_ylabel("Mots")
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels(labels, rotation=25, ha="right")
    axes[1].bar_label(bars_fr, padding=2, fontsize=7)
    axes[1].bar_label(bars_en, padding=2, fontsize=7)
    axes[1].legend(title="Langue")

    _setup_axes(axes)
    figure.suptitle(
        "Documents et mots par famille et par langue", fontsize=13, fontweight="bold"
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    return _save_figure(figure, "documents_familles_langue.png")


def plot_lengths(metrics: dict) -> Path:
    """Graphique 1b : histogrammes des longueurs de documents et de chunks."""
    manifest = read_manifest()
    chunks = read_jsonl("data/processed/chunked_corpus.jsonl")
    knowledge_base = [
        row for row in manifest if row.get("record_type") == "knowledge_base_document"
    ]
    document_values = [int(row["word_count"]) for row in knowledge_base]
    chunk_values = [int(row["word_count"]) for row in chunks]

    figure, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for language, color in [("fr", FR_COLOR), ("en", EN_COLOR)]:
        values = [
            int(row["word_count"])
            for row in knowledge_base
            if row["language"] == language
        ]
        axes[0].hist(
            values,
            bins=range(0, 801, 50),
            alpha=0.55,
            color=color,
            edgecolor="white",
            label=f"{LANGUAGE_LABELS[language]} (n={len(values)})",
        )
        median = statistics.median(values)
        axes[0].axvline(
            median,
            color=color,
            linestyle="--",
            linewidth=1.6,
            label=f"Médiane {LANGUAGE_LABELS[language]} = {fmt_num(median)}",
        )
    axes[0].set_title("Longueur des documents (manifeste)")
    axes[0].set_xlabel("Mots par document")
    axes[0].set_ylabel("Nombre de documents")
    axes[0].legend(fontsize=7)
    axes[0].text(
        0.98,
        0.95,
        f"Min {fmt_int(min(document_values))} · Médiane "
        f"{fmt_num(statistics.median(document_values))} · Max "
        f"{fmt_int(max(document_values))}",
        transform=axes[0].transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.8},
    )

    for language, color in [("fr", FR_COLOR), ("en", EN_COLOR)]:
        values = [
            int(row["word_count"])
            for row in chunks
            if row["language"] == language
        ]
        axes[1].hist(
            values,
            bins=range(0, 241, 20),
            alpha=0.55,
            color=color,
            edgecolor="white",
            label=f"{LANGUAGE_LABELS[language]} (n={len(values)})",
        )
        median = statistics.median(values)
        axes[1].axvline(
            median,
            color=color,
            linestyle="--",
            linewidth=1.6,
            label=f"Médiane {LANGUAGE_LABELS[language]} = {fmt_num(median)}",
        )
    axes[1].set_title("Longueur des chunks")
    axes[1].set_xlabel("Mots par chunk")
    axes[1].set_ylabel("Nombre de chunks")
    axes[1].legend(fontsize=7)
    axes[1].text(
        0.98,
        0.95,
        f"Min {fmt_int(min(chunk_values))} · Médiane "
        f"{fmt_num(statistics.median(chunk_values))} · Max "
        f"{fmt_int(max(chunk_values))}",
        transform=axes[1].transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.8},
    )

    _setup_axes(axes)
    figure.suptitle(
        "Distribution des longueurs de documents et de chunks",
        fontsize=13,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    return _save_figure(figure, "longueurs_documents_chunks.png")


def plot_parity(metrics: dict) -> Path:
    """Graphique 1c : parité FR/EN en volume de mots par famille."""
    documents = metrics["documents"]
    labels = [FAMILY_LABELS[code] for code in FAMILY_CODES]
    positions = list(range(len(FAMILY_CODES)))
    width = 0.38
    fr_words = [
        documents["by_family_language"][code]["fr"]["words"]
        for code in FAMILY_CODES
    ]
    en_words = [
        documents["by_family_language"][code]["en"]["words"]
        for code in FAMILY_CODES
    ]
    figure, axis = plt.subplots(figsize=(11, 5.2))
    bars_fr = axis.bar(
        [position - width / 2 for position in positions],
        fr_words,
        width,
        label="FR",
        color=FR_COLOR,
    )
    bars_en = axis.bar(
        [position + width / 2 for position in positions],
        en_words,
        width,
        label="EN",
        color=EN_COLOR,
    )
    axis.bar_label(bars_fr, padding=2, fontsize=8)
    axis.bar_label(bars_en, padding=2, fontsize=8)
    maximum = max(fr_words + en_words)
    for index, code in enumerate(FAMILY_CODES):
        ratio = documents["parity"][code]["words_ratio_fr_en"]
        axis.text(
            index,
            max(fr_words[index], en_words[index]) + maximum * 0.06,
            f"×{fmt_ratio(ratio)}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#444444",
            fontweight="bold",
        )
    axis.set_title("Parité FR/EN en volume de mots par famille")
    axis.set_ylabel("Nombre de mots (manifeste)")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=20, ha="right")
    axis.set_ylim(0, maximum * 1.18)
    axis.legend(title="Langue")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.text(
        0.99,
        0.02,
        "Ratio FR/EN annoté au-dessus des barres EN",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#444444",
    )
    figure.tight_layout()
    return _save_figure(figure, "parite_fr_en.png")


def plot_chunks_audience(metrics: dict) -> Path:
    """Graphique 1d : part des chunks indexés par audience."""
    documents = metrics["documents"]
    audiences = ["customer", "internal"]
    labels = [AUDIENCE_LABELS[audience] for audience in audiences]
    indexed = [
        documents["chunks_by_audience_index"][audience]["indexed"]
        for audience in audiences
    ]
    not_indexed = [
        documents["chunks_by_audience_index"][audience]["not_indexed"]
        for audience in audiences
    ]
    totals = [indexed[index] + not_indexed[index] for index in range(len(audiences))]
    figure, axis = plt.subplots(figsize=(8.5, 5.2))
    bars_indexed = axis.bar(
        labels, indexed, label="Indexés", color="#2ca02c", width=0.55
    )
    bars_not_indexed = axis.bar(
        labels,
        not_indexed,
        bottom=indexed,
        label="Non indexés",
        color="#d62728",
        width=0.55,
    )
    for index, audience in enumerate(audiences):
        stats = documents["chunks_by_audience_index"][audience]
        axis.text(
            index,
            indexed[index] / 2,
            f"{fmt_pct(stats['indexed'], stats['total'])}\nindexés",
            ha="center",
            va="center",
            color="white",
            fontsize=9,
            fontweight="bold",
        )
        axis.text(
            index,
            totals[index] + max(totals) * 0.035,
            f"Total {fmt_int(totals[index])}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    axis.set_title("Part des chunks indexés dans le RAG par audience")
    axis.set_ylabel("Nombre de chunks")
    axis.set_ylim(0, max(totals) * 1.18)
    axis.legend()
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save_figure(figure, "chunks_indexes_audience.png")


def plot_languages(metrics: dict) -> Path:
    """Graphique 2 : répartition FR/EN dans les jeux."""
    languages = metrics["languages"]
    labels = [label for _, label in DATASET_LABELS]
    positions = list(range(len(DATASET_LABELS)))
    fr = [languages[key]["fr"] for key, _ in DATASET_LABELS]
    en = [languages[key]["en"] for key, _ in DATASET_LABELS]
    totals = [fr[index] + en[index] for index in range(len(labels))]
    width = 0.38
    figure, axis = plt.subplots(figsize=(11, 5.4))
    bars_fr = axis.bar(
        [position - width / 2 for position in positions],
        fr,
        width,
        label="FR",
        color=FR_COLOR,
    )
    bars_en = axis.bar(
        [position + width / 2 for position in positions],
        en,
        width,
        label="EN",
        color=EN_COLOR,
    )
    axis.bar_label(
        bars_fr,
        labels=[
            f"{fmt_int(fr[index])}\n({fmt_pct(fr[index], totals[index])})"
            for index in range(len(labels))
        ],
        padding=3,
        fontsize=7,
    )
    axis.bar_label(
        bars_en,
        labels=[
            f"{fmt_int(en[index])}\n({fmt_pct(en[index], totals[index])})"
            for index in range(len(labels))
        ],
        padding=3,
        fontsize=7,
    )
    axis.set_title("Répartition FR/EN dans les jeux de données")
    axis.set_ylabel("Nombre d'éléments")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=15, ha="right")
    axis.set_ylim(0, max(totals) * 1.28)
    axis.legend(title="Langue")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save_figure(figure, "langues_jeux.png")


def plot_intents(metrics: dict) -> Path:
    """Graphique 3 : intentions par split et par langue."""
    intents = metrics["intents"]
    labels = intents["labels"]
    positions = list(range(len(labels)))
    figure, axes = plt.subplots(2, 1, figsize=(13, 9.2))

    bottoms = [0] * len(labels)
    for split in SPLITS:
        values = [intents["by_intent_split"][label][split] for label in labels]
        bars = axes[0].bar(
            positions,
            values,
            bottom=bottoms,
            label=split,
            color=SPLIT_COLORS[split],
            width=0.7,
        )
        axes[0].bar_label(bars, label_type="center", fontsize=6)
        bottoms = [bottoms[index] + values[index] for index in range(len(labels))]
    for index, label in enumerate(labels):
        axes[0].text(
            index,
            bottoms[index] + 0.8,
            str(intents["by_intent_split"][label]["total"]),
            ha="center",
            va="bottom",
            fontsize=7,
        )
    axes[0].set_title("Effectifs par intention et par split")
    axes[0].set_ylabel("Exemples")
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
    axes[0].legend(title="Split", ncol=3)
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].set_axisbelow(True)

    width = 0.38
    fr = [intents["by_intent_language"][label]["fr"] for label in labels]
    en = [intents["by_intent_language"][label]["en"] for label in labels]
    bars_fr = axes[1].bar(
        [position - width / 2 for position in positions],
        fr,
        width,
        label="FR",
        color=FR_COLOR,
    )
    bars_en = axes[1].bar(
        [position + width / 2 for position in positions],
        en,
        width,
        label="EN",
        color=EN_COLOR,
    )
    axes[1].bar_label(bars_fr, padding=1, fontsize=6)
    axes[1].bar_label(bars_en, padding=1, fontsize=6)
    axes[1].set_title("Répartition FR/EN par intention")
    axes[1].set_ylabel("Exemples")
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
    axes[1].legend(title="Langue")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].set_axisbelow(True)

    figure.suptitle(
        "Intentions : splits et langues", fontsize=13, fontweight="bold"
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    return _save_figure(figure, "intentions_split_et_langue.png")


def plot_duplicates(metrics: dict) -> Path:
    """Graphique 4 : synthèse des doublons détectés."""
    duplicates = metrics["duplicates"]
    intra_exact = sum(
        duplicates["intent_dataset"]["intra_split"][split]["exact_pair_count"]
        for split in SPLITS
    )
    intra_quasi = sum(
        duplicates["intent_dataset"]["intra_split"][split]["quasi_pair_count"]
        for split in SPLITS
    )
    scopes = [
        ("Corpus nettoyé", duplicates["cleaned_corpus"]["exact_pair_count"], duplicates["cleaned_corpus"]["quasi_pair_count"]),
        ("Corpus chunké", duplicates["chunked_corpus"]["exact_pair_count"], duplicates["chunked_corpus"]["quasi_pair_count"]),
        ("Intentions intra-split", intra_exact, intra_quasi),
        (
            "Intentions inter-splits",
            duplicates["intent_dataset"]["cross_split"]["exact_pair_count"],
            duplicates["intent_dataset"]["cross_split"]["quasi_pair_count"],
        ),
        (
            "RAG vs robustesse",
            duplicates["rag_vs_robustness"]["exact_pair_count"],
            duplicates["rag_vs_robustness"]["quasi_pair_count"],
        ),
        (
            "RAG vs intentions",
            duplicates["rag_vs_intent_dataset"]["exact_pair_count"],
            duplicates["rag_vs_intent_dataset"]["quasi_pair_count"],
        ),
    ]
    labels = [scope[0] for scope in scopes]
    exact = [scope[1] for scope in scopes]
    quasi = [scope[2] for scope in scopes]
    positions = list(range(len(labels)))
    width = 0.38
    figure, axis = plt.subplots(figsize=(12, 5.2))
    bars_exact = axis.bar(
        [position - width / 2 for position in positions],
        exact,
        width,
        label="Paires exactes",
        color="#1f77b4",
    )
    bars_quasi = axis.bar(
        [position + width / 2 for position in positions],
        quasi,
        width,
        label="Paires quasi (Jaccard ≥ 0,80)",
        color="#ff7f0e",
    )
    axis.bar_label(bars_exact, padding=2, fontsize=8)
    axis.bar_label(bars_quasi, padding=2, fontsize=8)
    axis.set_title("Doublons exacts et quasi-doublons détectés")
    axis.set_ylabel("Nombre de paires")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=20, ha="right")
    axis.set_ylim(0, 1)
    axis.legend()
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.text(
        0.99,
        0.95,
        "Aucune paire détectée" if not any(exact) and not any(quasi) else "",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.85},
    )
    figure.tight_layout()
    return _save_figure(figure, "doublons_resume.png")


def plot_question_lengths(metrics: dict) -> Path:
    """Graphique 5a : longueur des questions par type et par langue."""
    rag_eval = read_jsonl("data/annotations/rag_eval.jsonl")
    type_data = [
        [
            len(row["question"].split())
            for row in rag_eval
            if row["question_type"] == question_type
        ]
        for question_type in QUESTION_TYPES
    ]
    language_data = [
        [
            len(row["question"].split())
            for row in rag_eval
            if row["language"] == language
        ]
        for language in LANGUAGES
    ]
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    boxes = axes[0].boxplot(type_data, patch_artist=True)
    for patch, color in zip(
        boxes["boxes"], ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
    ):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[0].set_xticks(range(1, len(QUESTION_TYPES) + 1))
    axes[0].set_xticklabels(
        [QUESTION_TYPE_LABELS[question_type] for question_type in QUESTION_TYPES]
    )
    axes[0].set_title("Par type de question")
    axes[0].set_ylabel("Longueur de la question (mots)")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].set_axisbelow(True)

    boxes = axes[1].boxplot(language_data, patch_artist=True)
    for patch, color in zip(boxes["boxes"], [FR_COLOR, EN_COLOR]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[1].set_xticks(range(1, len(LANGUAGES) + 1))
    axes[1].set_xticklabels([LANGUAGE_LABELS[language] for language in LANGUAGES])
    axes[1].set_title("Par langue")
    axes[1].set_ylabel("Longueur de la question (mots)")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].set_axisbelow(True)

    figure.suptitle(
        "Distribution de la longueur des questions RAG",
        fontsize=13,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    return _save_figure(figure, "questions_longueur.png")


def plot_question_types(metrics: dict) -> Path:
    """Graphique 5b : types de questions par langue."""
    questions = metrics["questions"]
    labels = [QUESTION_TYPE_LABELS[question_type] for question_type in QUESTION_TYPES]
    positions = list(range(len(QUESTION_TYPES)))
    width = 0.38
    fr = [
        questions["by_type_language"][question_type]["fr"]
        for question_type in QUESTION_TYPES
    ]
    en = [
        questions["by_type_language"][question_type]["en"]
        for question_type in QUESTION_TYPES
    ]
    figure, axis = plt.subplots(figsize=(10, 5.2))
    bars_fr = axis.bar(
        [position - width / 2 for position in positions],
        fr,
        width,
        label="FR",
        color=FR_COLOR,
    )
    bars_en = axis.bar(
        [position + width / 2 for position in positions],
        en,
        width,
        label="EN",
        color=EN_COLOR,
    )
    for index, question_type in enumerate(QUESTION_TYPES):
        stats = questions["by_type_language"][question_type]
        axis.text(
            index,
            max(fr[index], en[index]) + max(fr + en) * 0.06,
            f"FR {fmt_int(fr[index])} ({fmt_pct(stats['fr'], stats['total'])})\n"
            f"EN {fmt_int(en[index])} ({fmt_pct(stats['en'], stats['total'])})",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    axis.set_title("Types de questions RAG par langue")
    axis.set_ylabel("Nombre de questions")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels)
    axis.set_ylim(0, max(fr + en) * 1.32)
    axis.legend(title="Langue")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save_figure(figure, "questions_types_langue.png")


def plot_question_coverage(metrics: dict) -> Path:
    """Graphique 5c : couverture par document et chunks gold par question."""
    questions = metrics["questions"]
    coverage = questions["coverage_by_document"]
    documents = list(coverage.keys())
    counts = [coverage[document] for document in documents]
    positions = list(range(len(documents)))

    figure, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    bars = axes[0].bar(positions, counts, color="#1f77b4")
    axes[0].bar_label(bars, padding=2, fontsize=7)
    axes[0].set_title("Questions par document gold")
    axes[0].set_ylabel("Nombre de questions")
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels(documents, rotation=90, fontsize=7)
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].set_axisbelow(True)
    axes[0].text(
        0.99,
        0.95,
        f"{questions['covered_documents']}/{questions['candidate_documents']} "
        "documents couverts",
        transform=axes[0].transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.85},
    )

    gold_labels = ["0", "1", "2"]
    gold_counts = [
        questions["gold_chunks_per_question"][count] for count in gold_labels
    ]
    axes[1].bar(gold_labels, gold_counts, color="#ff7f0e")
    for index, count in enumerate(gold_labels):
        axes[1].text(
            index,
            gold_counts[index] + max(gold_counts) * 0.04,
            f"{fmt_int(gold_counts[index])}\n"
            f"({fmt_pct(gold_counts[index], questions['rag_total'])})",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    axes[1].set_title("Nombre de chunks gold par question")
    axes[1].set_xlabel("Chunks gold")
    axes[1].set_ylabel("Nombre de questions")
    axes[1].set_ylim(0, max(gold_counts) * 1.28)
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].set_axisbelow(True)

    figure.suptitle(
        "Couverture des documents et chunks gold", fontsize=13, fontweight="bold"
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    return _save_figure(figure, "questions_couverture_et_chunks.png")


def plot_all(metrics: dict) -> list[Path]:
    """Génère toutes les figures."""
    return [
        plot_documents(metrics),
        plot_lengths(metrics),
        plot_parity(metrics),
        plot_chunks_audience(metrics),
        plot_languages(metrics),
        plot_intents(metrics),
        plot_duplicates(metrics),
        plot_question_lengths(metrics),
        plot_question_types(metrics),
        plot_question_coverage(metrics),
    ]


# ---------------------------------------------------------------------------
# Écriture des sorties
# ---------------------------------------------------------------------------


def write_metrics(metrics: dict) -> None:
    """Écrit le JSON trié, sans horodatage."""
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def findings_markdown() -> str:
    """Constats sous forme de liste Markdown."""
    metrics = load_metrics()
    lines = ["### Constats", ""]
    for index, finding in enumerate(metrics["findings"], start=1):
        lines.append(f"{index}. {finding}")
    return "\n".join(lines)


def write_findings(metrics: dict) -> None:
    """Écrit le rapport Markdown avec figures, tableaux et constats."""
    lines = [
        "# Analyse exploratoire des données — SupportAI",
        "",
        "> Fichier généré par `python scripts/run_eda.py`. Aucun horodatage, "
        "aucun chemin absolu.",
        "> L'EDA porte sur la source canonique v1.0. La source v1.1 utilisée par "
        "le gel courant ne diffère que par le `split` de `INT-0421` "
        "(train → test) ; les métriques de texte et de classes restent "
        "identiques, seuls les effectifs de train/test changent d'une unité.",
        "",
        "## Périmètre",
        "",
        "L'analyse porte uniquement sur les fichiers publics listés ci-dessous. "
        "`data/annotations/_private/` n'est ni lu ni utilisé.",
        "",
        "- `data/processed/cleaned_corpus.jsonl`",
        "- `data/processed/chunked_corpus.jsonl`",
        "- `data/annotations/intent_dataset.jsonl`",
        "- `data/annotations/rag_eval.jsonl`",
        "- `data/annotations/robustness_eval.jsonl`",
        "- `data/source_manifest.csv`",
        "",
        "## Reproductibilité",
        "",
        "```bash",
        "python scripts/run_eda.py",
        "python tests/test_eda.py",
        "```",
        "",
        "Graine fixe : `42`. Les clés de `docs/reports/eda_metrics.json` sont "
        "triées et le fichier ne contient pas d'horodatage. Les figures sont "
        "écrites dans `docs/figures/eda/`.",
        "",
        "## 1. Documents et chunks",
        "",
        "![Documents et mots par famille et par langue]"
        "(../figures/eda/documents_familles_langue.png)",
        "",
        "![Distribution des longueurs de documents et de chunks]"
        "(../figures/eda/longueurs_documents_chunks.png)",
        "",
        "![Parité FR/EN en volume de mots]"
        "(../figures/eda/parite_fr_en.png)",
        "",
        "![Part des chunks indexés par audience]"
        "(../figures/eda/chunks_indexes_audience.png)",
        "",
        table_documents(metrics),
        "",
        "## 2. Langues",
        "",
        "![Répartition FR/EN dans les jeux]"
        "(../figures/eda/langues_jeux.png)",
        "",
        table_languages(metrics),
        "",
        "## 3. Intentions",
        "",
        "![Intentions par split et par langue]"
        "(../figures/eda/intentions_split_et_langue.png)",
        "",
        table_intents(metrics),
        "",
        "## 4. Doublons",
        "",
        "![Synthèse des doublons]"
        "(../figures/eda/doublons_resume.png)",
        "",
        "Les textes sont normalisés (minuscules, accents retirés, ponctuation "
        "réduite) et comparés par Jaccard sur les trigrammes de mots. Le seuil "
        "de quasi-doublon est `0,80`.",
        "",
        table_duplicates(metrics),
        "",
        "## 5. Questions",
        "",
        "![Longueur des questions]"
        "(../figures/eda/questions_longueur.png)",
        "",
        "![Types de questions par langue]"
        "(../figures/eda/questions_types_langue.png)",
        "",
        "![Couverture des documents et chunks gold]"
        "(../figures/eda/questions_couverture_et_chunks.png)",
        "",
        table_questions(metrics),
        "",
        "## 6. Constats",
        "",
    ]
    for index, finding in enumerate(metrics["findings"], start=1):
        lines.append(f"{index}. {finding}")
    lines.extend(
        [
            "",
            "## Limites",
            "",
            "- Les longueurs de documents proviennent de `word_count` du "
            "manifeste ; les longueurs de chunks proviennent de "
            "`chunked_corpus.jsonl`.",
            "- Les doublons sont détectés sur le texte normalisé ; une "
            "reformulation sémantique sans recouvrement de trigrammes n'est pas "
            "signalée.",
            "- Notebook non exécuté, faute de jupyter ; ses cellules de code ont "
            "été nettoyées (`outputs = []`, `execution_count = null`) et leur "
            "syntaxe est validée par `tests/test_eda.py`. L'exécution reste à "
            "faire par l'humain : lancer `python scripts/run_eda.py` puis ouvrir "
            "`notebooks/eda.ipynb`.",
            "",
        ]
    )
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def load_metrics() -> dict:
    """Charge les métriques ; les recalcule si le fichier n'existe pas."""
    if not METRICS_PATH.exists():
        return compute_metrics()
    with METRICS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def generate_all() -> dict:
    """Calcule, trace et écrit toutes les sorties."""
    random.seed(SEED)
    metrics = compute_metrics()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot_all(metrics)
    write_metrics(metrics)
    write_findings(metrics)
    return metrics


def main() -> None:
    """Point d'entrée du script."""
    metrics = generate_all()
    print("EDA SupportAI")
    print("=" * 72)
    print(f"Documents : {metrics['documents']['documents_total']}")
    print(f"Chunks : {metrics['documents']['chunks_total']}")
    print(f"Intentions : {metrics['intents']['total']}")
    print(f"Questions RAG : {metrics['questions']['rag_total']}")
    print(f"Cas de robustesse : {metrics['robustness']['total']}")
    print(f"Métriques : docs/reports/eda_metrics.json")
    print(f"Rapport : docs/reports/eda_findings.md")
    print(f"Figures : {len(FIGURE_FILES)} fichiers dans docs/figures/eda/")


if __name__ == "__main__":
    main()
