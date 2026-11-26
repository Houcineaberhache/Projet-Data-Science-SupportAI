"""Gel versionné des jeux de test SupportAI (bibliothèque standard uniquement).

Sous-commandes :
    freeze [--version X]  : contrôle a→g puis écrit data/frozen/vX/ (refuse d'écraser) ;
    verify  [--version X] : recalcule empreintes et contrôles, ne modifie rien.

La v1.0 reste intacte. La v1.1 utilise une source d'intentions corrigée qui
regroupe les deux traductions de TR-0001 dans le même split. Les cas douteux
restent signalés pour revue humaine ; aucun dossier gelé n'est réécrit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

VERSION = "1.0"
SEED = 42
LICENSE = "NovaShop-Proprietary-Synthetic"
LICENSE_STATUS = "internal_verified"
LICENSE_SOURCE = "data/source_manifest.csv"
LICENSE_NOTES = (
    "Licence confirmée pour les 74 fichiers de langue du corpus (reuse_permission="
    "full_text_index). Les 7 références externes ne sont pas indexées et gardent "
    "leurs licences propres. Les jeux dérivés (intent_dataset, rag_eval, "
    "robustness_eval, gel v1.0) n'ont pas de licence distincte explicite dans le "
    "dépôt ; la redistribution hors projet reste à confirmer."
)
ANNOTATION_STATUS = "single_annotator"
ROOT = Path(__file__).resolve().parents[1]

SOURCE_PATHS = {
    "intent_dataset": "data/annotations/intent_dataset.jsonl",
    "rag_eval": "data/annotations/rag_eval.jsonl",
    "robustness_eval": "data/annotations/robustness_eval.jsonl",
    "chunked_corpus": "data/processed/chunked_corpus.jsonl",
}
V11_SOURCE_OVERRIDES = {
    "intent_dataset": "data/annotations/intent_dataset_v1.1.jsonl",
}
GUIDELINES_PATH = "docs/annotation_guidelines.md"
SPLITS = ["train", "val", "test"]
REVIEW_LOW = 0.60
QUASI_THRESHOLD = 0.80
RARE_MAX_DF = 4
HIDDEN_FIELDS = {
    "intent",
    "acceptable_labels",
    "ambiguous",
    "notes",
    "annotator_1",
    "annotator_2",
    "adjudicated",
}
ORDER_RE = re.compile(r"ORD-\d+", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<!\d)\d+(?!\d)")

TRANSLATION_DECISIONS = {
    ("INT-0445", "INT-0421"): (
        "Fuite de traduction confirmée : même intention `warranty_claim`, même "
        "nombre 14 mois et même propos (batterie couverte par la garantie) en EN "
        "et en FR. Dans v1.0, aucun exemple n'est modifié ; en v1.1, `INT-0421` "
        "est regroupé avec `INT-0445` dans le split `test` sans changer son texte "
        "ni son étiquette."
    ),
    ("INT-0445", "INT-0223"): (
        "Cas légitime : seul le nombre 14 est partagé ; les intentions diffèrent "
        "(`warranty_claim` vs `return_request`) et il n'y a pas de traduction. "
        "L'exemple est conservé tel quel."
    ),
}

TRANSLATION_FIX_V11 = {
    "group_id": "TR-0001",
    "strategy": (
        "Regrouper les exemples traduits dans le même split ; seul le champ "
        "`split` est modifié, aucun texte ni étiquette n'est touché."
    ),
    "target_split": "test",
    "members": [
        {
            "id": "INT-0421",
            "original_split": "train",
            "new_split": "test",
            "language": "fr",
            "intent": "warranty_claim",
            "source": "data/annotations/_private/intent_candidates.jsonl",
        },
        {
            "id": "INT-0445",
            "original_split": "test",
            "new_split": "test",
            "language": "en",
            "intent": "warranty_claim",
            "source": "data/annotations/blind/annotate_aya_done.csv",
        },
    ],
    "legitimate_pairs": [
        {
            "ids": ["INT-0445", "INT-0223"],
            "reason": (
                "Intentions différentes (`warranty_claim` vs `return_request`) ; "
                "seul le nombre 14 est partagé."
            ),
        }
    ],
}

VERSION_NOTES = {
    "1.0": "Gel initial, conservé intégralement pour la reproductibilité historique.",
    "1.1": (
        "Correction de la fuite de traduction TR-0001 : `INT-0421` rejoint "
        "`INT-0445` dans `test`. Aucune suppression, aucun texte ni étiquette "
        "modifié. `INT-0445` / `INT-0223` reste un cas légitime documenté."
    ),
}

V10_BASELINE = {
    "counts": {"train": 392, "val": 84, "test": 84},
    "source_intent_sha256": (
        "c8c98ed852abd9c46dbfe48d3ab56e2b2d1cdc040881220da84105d134627ecf"
    ),
    "intent_test_sha256": (
        "088b67d803a23c46167a672c8a777ea304294dd4813ac44b70bf688f859392ee"
    ),
    "translation_leak": "INT-0445 (test) / INT-0421 (train)",
}


def source_paths_for(version: str) -> dict[str, str]:
    """Sources utilisées par une version de gel."""
    paths = dict(SOURCE_PATHS)
    if version == "1.1":
        paths.update(V11_SOURCE_OVERRIDES)
    return paths


def license_notes_for(version: str) -> str:
    return LICENSE_NOTES.replace("gel v1.0", f"gel v{version}")

CHECK_LABELS = {
    "a": "ids uniques et union complète",
    "b": "aucun texte exact test ↔ train/val",
    "c": "aucun quasi-doublon test ↔ train/val (Jaccard ≥ 0,80)",
    "d": "aucun identifiant de commande ni numéro identifiant partagé",
    "e": "recherche de fuite par traduction (signalement)",
    "f": "aucun doublon RAG/robustesse ↔ intentions",
    "g": "gold_chunk_id valides, customer et indexés",
}


class FreezeError(Exception):
    """Erreur bloquante : le gel ne doit pas être écrit."""


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_info(path: Path, relative_path: str) -> dict:
    data = path.read_bytes()
    return {
        "path": relative_path,
        "size_bytes": len(data),
        "lines": len(data.splitlines()),
        "sha256": sha256_bytes(data),
    }


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def word_trigrams(text: str) -> set[tuple[str, str, str]]:
    words = normalize_text(text).split()
    return {tuple(words[index : index + 3]) for index in range(len(words) - 2)}


def jaccard(
    trigrams_a: set[tuple[str, str, str]],
    trigrams_b: set[tuple[str, str, str]],
    normalized_a: str,
    normalized_b: str,
) -> float:
    if not trigrams_a and not trigrams_b:
        return 1.0 if normalized_a == normalized_b else 0.0
    if not trigrams_a or not trigrams_b:
        return 0.0
    return len(trigrams_a & trigrams_b) / len(trigrams_a | trigrams_b)


def order_ids(text: str) -> set[str]:
    return {match.group(0).lower() for match in ORDER_RE.finditer(text or "")}


def numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(normalize_text(text)))


def line_ending(raw_line: bytes) -> bytes:
    if raw_line.endswith(b"\r\n"):
        return b"\r\n"
    if raw_line.endswith(b"\n"):
        return b"\n"
    return b""


def load_jsonl(path: Path) -> dict:
    raw_lines = []
    rows = []
    with path.open("rb") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            raw_lines.append(raw_line)
            rows.append(json.loads(raw_line.decode("utf-8")))
    return {
        "raw_lines": raw_lines,
        "rows": rows,
        "size_bytes": path.stat().st_size,
        "lines": len(raw_lines),
        "sha256": sha256_file(path),
    }


def load_sources(
    root: Path, version: str = VERSION, source_paths: dict[str, str] | None = None
) -> dict:
    paths = source_paths or source_paths_for(version)
    sources = {}
    for key, relative_path in paths.items():
        sources[key] = load_jsonl(root / relative_path)
    return sources


def git_output(root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            args, cwd=root, capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.rstrip("\r\n") if result.returncode == 0 else ""


def make_check(letter: str, ok: bool, details: dict) -> dict:
    return {
        "id": letter,
        "label": CHECK_LABELS[letter],
        "status": "OK" if ok else "KO",
        "blocking": letter != "e",
        "details": details,
    }


# ---------------------------------------------------------------------------
# Contrôles anti-fuite a → g
# ---------------------------------------------------------------------------


def check_a(intent_rows: list[dict]) -> dict:
    by_split = {
        split: [row["id"] for row in intent_rows if row.get("split") == split]
        for split in SPLITS
    }
    overlaps = []
    for first, second in combinations(SPLITS, 2):
        common = sorted(set(by_split[first]) & set(by_split[second]))
        if common:
            overlaps.append({"splits": [first, second], "ids": common})
    union = sorted({row["id"] for row in intent_rows})
    details = {
        "counts": {split: len(by_split[split]) for split in SPLITS},
        "by_language": {
            split: dict(
                sorted(
                    Counter(
                        row.get("language")
                        for row in intent_rows
                        if row.get("split") == split
                    ).items()
                )
            )
            for split in SPLITS
        },
        "total_rows": len(intent_rows),
        "union_size": len(union),
        "overlaps": overlaps,
    }
    return make_check("a", not overlaps and len(union) == len(intent_rows), details)


def check_b(intent_rows: list[dict]) -> dict:
    test_rows = [row for row in intent_rows if row.get("split") == "test"]
    other_rows = [row for row in intent_rows if row.get("split") in ("train", "val")]
    by_norm = defaultdict(list)
    for row in other_rows:
        by_norm[normalize_text(row["text"])].append(row["id"])
    pairs = []
    for row in test_rows:
        for other_id in by_norm.get(normalize_text(row["text"]), []):
            pairs.append({"test_id": row["id"], "other_id": other_id})
    pairs.sort(key=lambda pair: (pair["test_id"], pair["other_id"]))
    return make_check(
        "b",
        not pairs,
        {"test_rows": len(test_rows), "other_rows": len(other_rows), "pairs": pairs},
    )


def check_c(intent_rows: list[dict]) -> dict:
    test_rows = [row for row in intent_rows if row.get("split") == "test"]
    other_rows = [row for row in intent_rows if row.get("split") in ("train", "val")]
    prepared_test = [
        (row["id"], normalize_text(row["text"]), word_trigrams(row["text"]))
        for row in test_rows
    ]
    prepared_other = [
        (row["id"], normalize_text(row["text"]), word_trigrams(row["text"]))
        for row in other_rows
    ]
    blocking = []
    review = []
    for test_id, norm_test, tri_test in prepared_test:
        for other_id, norm_other, tri_other in prepared_other:
            if norm_test == norm_other:
                continue
            score = jaccard(tri_test, tri_other, norm_test, norm_other)
            pair = {
                "test_id": test_id,
                "other_id": other_id,
                "jaccard": round(score, 4),
            }
            if score >= QUASI_THRESHOLD:
                blocking.append(pair)
            elif score >= REVIEW_LOW:
                review.append(pair)
    blocking.sort(key=lambda pair: (-pair["jaccard"], pair["test_id"], pair["other_id"]))
    review.sort(key=lambda pair: (-pair["jaccard"], pair["test_id"], pair["other_id"]))
    return make_check(
        "c",
        not blocking,
        {
            "threshold": QUASI_THRESHOLD,
            "review_range": [REVIEW_LOW, QUASI_THRESHOLD],
            "pairs_compared": len(prepared_test) * len(prepared_other),
            "blocking_pairs": blocking,
            "review_pairs": review,
        },
    )


def check_d(intent_rows: list[dict]) -> dict:
    test_rows = [row for row in intent_rows if row.get("split") == "test"]
    other_rows = [row for row in intent_rows if row.get("split") in ("train", "val")]

    def collect(rows: list[dict]) -> tuple[dict, dict, dict]:
        orders = defaultdict(list)
        long_numbers = defaultdict(list)
        short_numbers = defaultdict(list)
        for row in rows:
            for value in sorted(order_ids(row["text"])):
                orders[value].append(row["id"])
            for value in sorted(numbers(row["text"])):
                target = long_numbers if len(value) >= 3 else short_numbers
                target[value].append(row["id"])
        return orders, long_numbers, short_numbers

    test_orders, test_long, test_short = collect(test_rows)
    other_orders, other_long, other_short = collect(other_rows)

    def shared(test_map: dict, other_map: dict) -> list[dict]:
        result = []
        for value in sorted(set(test_map) & set(other_map)):
            result.append(
                {
                    "value": value,
                    "test_ids": sorted(set(test_map[value])),
                    "other_ids": sorted(set(other_map[value])),
                }
            )
        return result

    shared_orders = shared(test_orders, other_orders)
    shared_long = shared(test_long, other_long)
    shared_short = shared(test_short, other_short)
    details = {
        "definition": (
            "Bloquant : ORD-\\d+ ou nombre d'au moins 3 chiffres partagé. "
            "Les nombres courts (ex. 14 jours) sont listés mais non bloquants."
        ),
        "shared_order_ids": shared_orders,
        "shared_identifier_numbers": shared_long,
        "shared_short_numbers": shared_short,
    }
    ok = not shared_orders and not shared_long
    return make_check("d", ok, details)


def check_e(intent_rows: list[dict]) -> dict:
    test_rows = [row for row in intent_rows if row.get("split") == "test"]
    other_rows = [row for row in intent_rows if row.get("split") in ("train", "val")]
    document_frequency = Counter(
        token
        for row in intent_rows
        for token in set(normalize_text(row["text"]).split())
    )
    rare_tokens = {
        token for token, count in document_frequency.items() if count <= RARE_MAX_DF
    }
    suspicious = []
    for test in test_rows:
        test_numbers = numbers(test["text"]) | order_ids(test["text"])
        test_tokens = set(normalize_text(test["text"]).split())
        for other in other_rows:
            if test.get("language") == other.get("language"):
                continue
            other_numbers = numbers(other["text"]) | order_ids(other["text"])
            shared_numbers = sorted(test_numbers & other_numbers)
            shared_rare = sorted(test_tokens & set(normalize_text(other["text"]).split()) & rare_tokens)
            if shared_numbers and shared_rare:
                suspicious.append(
                    {
                        "test_id": test["id"],
                        "test_language": test.get("language"),
                        "other_id": other["id"],
                        "other_language": other.get("language"),
                        "other_split": other.get("split"),
                        "shared_numbers_or_ids": shared_numbers,
                        "shared_rare_tokens": shared_rare,
                    }
                )
    suspicious.sort(
        key=lambda pair: (pair["test_id"], pair["other_id"])
    )
    details = {
        "rare_max_document_frequency": RARE_MAX_DF,
        "method": (
            "Langue différente + nombre/identifiant commun + au moins un mot rare "
            "commun après normalisation. Signalement uniquement."
        ),
        "suspicious_pairs": suspicious,
    }
    return make_check("e", True, details)


def check_f(sources: dict) -> dict:
    intent_rows = sources["intent_dataset"]["rows"]
    prepared_intent = [
        (row["id"], normalize_text(row["text"]), word_trigrams(row["text"]))
        for row in intent_rows
    ]
    blocking = []
    review = []
    for source_key in ["rag_eval", "robustness_eval"]:
        for row in sources[source_key]["rows"]:
            question = row["question"]
            norm_question = normalize_text(question)
            tri_question = word_trigrams(question)
            for intent_id, norm_intent, tri_intent in prepared_intent:
                if norm_question == norm_intent:
                    blocking.append(
                        {
                            "dataset": source_key,
                            "question_id": row["id"],
                            "intent_id": intent_id,
                            "match": "exact",
                            "jaccard": 1.0,
                        }
                    )
                    continue
                score = jaccard(tri_question, tri_intent, norm_question, norm_intent)
                pair = {
                    "dataset": source_key,
                    "question_id": row["id"],
                    "intent_id": intent_id,
                    "match": "quasi",
                    "jaccard": round(score, 4),
                }
                if score >= QUASI_THRESHOLD:
                    blocking.append(pair)
                elif score >= REVIEW_LOW:
                    review.append(pair)
    blocking.sort(
        key=lambda pair: (
            -pair["jaccard"],
            pair["dataset"],
            pair["question_id"],
            pair["intent_id"],
        )
    )
    review.sort(
        key=lambda pair: (
            -pair["jaccard"],
            pair["dataset"],
            pair["question_id"],
            pair["intent_id"],
        )
    )
    return make_check(
        "f",
        not blocking,
        {
            "threshold": QUASI_THRESHOLD,
            "blocking_pairs": blocking,
            "review_pairs": review,
        },
    )


def check_g(sources: dict) -> dict:
    chunks = {}
    for row in sources["chunked_corpus"]["rows"]:
        chunks[(row.get("chunk_id"), row.get("language"))] = row
    invalid = []
    checked = 0
    for source_key in ["rag_eval", "robustness_eval"]:
        for row in sources[source_key]["rows"]:
            for chunk_id in row.get("gold_chunk_ids") or []:
                checked += 1
                chunk = chunks.get((chunk_id, row.get("language")))
                reason = None
                if chunk is None:
                    reason = "chunk absent"
                elif chunk.get("audience") != "customer":
                    reason = f"audience={chunk.get('audience')}"
                elif not chunk.get("index_in_rag"):
                    reason = "index_in_rag=false"
                if reason:
                    invalid.append(
                        {
                            "dataset": source_key,
                            "question_id": row["id"],
                            "chunk_id": chunk_id,
                            "language": row.get("language"),
                            "reason": reason,
                        }
                    )
    invalid.sort(
        key=lambda item: (
            item["dataset"],
            item["question_id"],
            item["chunk_id"],
        )
    )
    return make_check(
        "g",
        not invalid,
        {
            "chunked_corpus_rows": len(sources["chunked_corpus"]["rows"]),
            "gold_links_checked": checked,
            "invalid_links": invalid,
        },
    )


def run_checks(sources: dict) -> dict:
    intent_rows = sources["intent_dataset"]["rows"]
    checks = {
        "a": check_a(intent_rows),
        "b": check_b(intent_rows),
        "c": check_c(intent_rows),
        "d": check_d(intent_rows),
        "e": check_e(intent_rows),
        "f": check_f(sources),
        "g": check_g(sources),
    }
    return checks


# ---------------------------------------------------------------------------
# Construction des fichiers gelés
# ---------------------------------------------------------------------------


def build_split_ids(intent_rows: list[dict], version: str) -> dict:
    splits = {}
    for split in SPLITS:
        rows = [row for row in intent_rows if row.get("split") == split]
        ids = sorted(row["id"] for row in rows)
        joined = "\n".join(ids) + ("\n" if ids else "")
        splits[split] = {
            "ids": ids,
            "count": len(ids),
            "by_language": dict(
                sorted(Counter(row.get("language") for row in rows).items())
            ),
            "sha256": sha256_bytes(joined.encode("utf-8")),
            "sha256_definition": "sha256 de la liste triée des ids, un id par ligne, LF final",
        }
    all_rows = sorted(intent_rows, key=lambda row: row["id"])
    return {
        "version": version,
        "seed": SEED,
        "splits": splits,
        "total": {
            "rows": len(intent_rows),
            "by_language": dict(
                sorted(Counter(row.get("language") for row in all_rows).items())
            ),
        },
    }


def build_frozen_files(sources: dict, version: str) -> dict[str, bytes]:
    intent = sources["intent_dataset"]
    files: dict[str, bytes] = {}

    split_ids = build_split_ids(intent["rows"], version)
    files["split_ids.json"] = (
        json.dumps(split_ids, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    def extract(split: str) -> bytes:
        return b"".join(
            raw
            for raw, row in zip(intent["raw_lines"], intent["rows"])
            if row.get("split") == split
        )

    files["intent_test.jsonl"] = extract("test")
    files["intent_val.jsonl"] = extract("val")

    inputs = []
    for raw, row in zip(intent["raw_lines"], intent["rows"]):
        if row.get("split") != "test":
            continue
        hidden = {key: row[key] for key in HIDDEN_FIELDS if key in row}
        visible = {key: value for key, value in row.items() if key not in hidden}
        serialized = json.dumps(visible, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        inputs.append(serialized + line_ending(raw))
    files["intent_test_inputs.jsonl"] = b"".join(inputs)

    files["rag_eval.jsonl"] = b"".join(sources["rag_eval"]["raw_lines"])
    files["robustness_eval.jsonl"] = b"".join(
        sources["robustness_eval"]["raw_lines"]
    )
    return files


def build_manifest(
    root: Path,
    version: str,
    sources: dict,
    checks: dict,
    frozen_files: dict[str, bytes],
    guidelines_path: Path,
    source_paths: dict[str, str] | None = None,
) -> dict:
    paths = source_paths or source_paths_for(version)
    frozen_dir = f"data/frozen/v{version}"
    frozen_entries = {}
    for name, data in frozen_files.items():
        frozen_entries[name] = {
            "path": f"{frozen_dir}/{name}",
            "size_bytes": len(data),
            "lines": len(data.splitlines()),
            "sha256": sha256_bytes(data),
        }

    source_entries = {}
    for key, relative_path in paths.items():
        source_entries[key] = {
            "path": relative_path,
            "size_bytes": sources[key]["size_bytes"],
            "lines": sources[key]["lines"],
            "sha256": sources[key]["sha256"],
        }

    porcelain_output = git_output(root, ["git", "status", "--porcelain"])
    porcelain = porcelain_output.splitlines() if porcelain_output else []
    head = git_output(root, ["git", "rev-parse", "HEAD"]) or "unknown"
    guidelines_commit = (
        git_output(
            root,
            ["git", "log", "-1", "--format=%H", "--", GUIDELINES_PATH],
        )
        or "unknown"
    )

    blocking_ko = [
        letter
        for letter, check in checks.items()
        if check["status"] == "KO" and check["blocking"]
    ]
    manifest = {
        "version": version,
        "license": LICENSE,
        "license_status": LICENSE_STATUS,
        "license_source": LICENSE_SOURCE,
        "license_notes": license_notes_for(version),
        "annotation_status": ANNOTATION_STATUS,
        "seed": SEED,
        "version_notes": VERSION_NOTES.get(version, ""),
        "frozen_dir": frozen_dir,
        "frozen_files": frozen_entries,
        "sources": source_entries,
        "guidelines": {
            "path": GUIDELINES_PATH,
            "sha256": sha256_file(guidelines_path),
            "commit": guidelines_commit,
        },
        "git": {
            "head": head,
            "state": "clean" if not porcelain else "dirty",
            "clean": not porcelain,
            "porcelain": porcelain,
        },
        "checks": checks,
        "checks_summary": {
            "all_blocking_ok": not blocking_ko,
            "blocking_ko": blocking_ko,
            "review_required": sorted(
                letter
                for letter, check in checks.items()
                if check["details"].get("review_pairs")
                or check["details"].get("suspicious_pairs")
                or check["details"].get("shared_short_numbers")
            ),
        },
    }
    if version == "1.1":
        manifest["translation_fix"] = TRANSLATION_FIX_V11
    return manifest


# ---------------------------------------------------------------------------
# Rapport de gel
# ---------------------------------------------------------------------------


def md_table(headers: list[str], rows: list[list]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(str(cell).replace("|", "\\|") for cell in row)
            + " |"
        )
    return "\n".join(lines)


def format_pair(pair: dict) -> str:
    if "test_language" in pair:
        return (
            f"{pair['test_id']} ({pair['test_language']}) ↔ "
            f"{pair['other_id']} ({pair['other_split']}, "
            f"{pair['other_language']}) — "
            f"{', '.join(pair['shared_numbers_or_ids'])} ; "
            f"{', '.join(pair['shared_rare_tokens'])}"
        )
    if "test_id" in pair:
        return (
            f"{pair['test_id']} ↔ {pair['other_id']} "
            f"(Jaccard {pair['jaccard']:.2f})"
        )
    if "value" in pair:
        return (
            f"{pair['value']} : "
            f"{', '.join(pair['test_ids'])} ↔ {', '.join(pair['other_ids'])}"
        )
    return str(pair)


def write_freeze_report(root: Path, manifest: dict, split_ids: dict) -> Path:
    checks = manifest["checks"]
    check_rows = [
        [letter, checks[letter]["label"], checks[letter]["status"]]
        for letter in sorted(checks)
    ]

    effectif_rows = []
    for split in SPLITS:
        entry = split_ids["splits"][split]
        effectif_rows.append(
            [
                split,
                entry["count"],
                entry["by_language"].get("fr", 0),
                entry["by_language"].get("en", 0),
                entry["sha256"],
            ]
        )

    file_rows = [
        [
            name,
            info["lines"],
            info["size_bytes"],
            info["sha256"],
        ]
        for name, info in sorted(manifest["frozen_files"].items())
    ]

    source_rows = [
        [name, info["lines"], info["sha256"]]
        for name, info in sorted(manifest["sources"].items())
    ]

    review_c = checks["c"]["details"]["review_pairs"]
    review_e = checks["e"]["details"]["suspicious_pairs"]
    short_numbers = checks["d"]["details"]["shared_short_numbers"]
    review_lines = []
    review_lines.append("### Paires Jaccard 0,60–0,80")
    review_lines.append("")
    if review_c:
        review_lines.extend(f"- {format_pair(pair)}" for pair in review_c)
    else:
        review_lines.append("- Aucune paire.")
    review_lines.append("")
    review_lines.append("### Fuite par traduction (signalements)")
    review_lines.append("")
    if review_e:
        review_lines.extend(f"- {format_pair(pair)}" for pair in review_e)
    else:
        review_lines.append("- Aucune paire signalée.")
    review_lines.append("")
    review_lines.append("### Décision d'analyse des signalements")
    review_lines.append("")
    decision_keys = set(TRANSLATION_DECISIONS)
    decision_keys.update((pair["test_id"], pair["other_id"]) for pair in review_e)
    decisions = [
        TRANSLATION_DECISIONS[key]
        for key in sorted(decision_keys)
        if key in TRANSLATION_DECISIONS
    ]
    if decisions:
        review_lines.extend(f"- {decision}" for decision in decisions)
    else:
        review_lines.append("- Aucune décision enregistrée pour ces paires.")
    review_lines.append("")
    review_lines.append("### Nombres courts partagés (non bloquants)")
    review_lines.append("")
    if short_numbers:
        review_lines.extend(f"- {format_pair(pair)}" for pair in short_numbers)
    else:
        review_lines.append("- Aucun nombre court partagé.")
    review_lines.append("")

    extra_sections = []
    translation_fix = manifest.get("translation_fix")
    if translation_fix:
        member_rows = [
            [
                member["id"],
                member["language"],
                member["original_split"],
                member["new_split"],
                f"`{member['source']}`",
            ]
            for member in translation_fix["members"]
        ]
        extra_sections.extend(
            [
                "## Correction de la fuite de traduction",
                "",
                f"- Groupe : `{translation_fix['group_id']}`",
                f"- Stratégie : {translation_fix['strategy']}",
                f"- Split cible : `{translation_fix['target_split']}`",
                "",
                md_table(
                    ["Id", "Langue", "Split v1.0", "Split v1.1", "Source"],
                    member_rows,
                ),
                "",
            ]
        )
        for pair in translation_fix["legitimate_pairs"]:
            extra_sections.append(
                f"- Cas légitime conservé : {', '.join(pair['ids'])} — {pair['reason']}"
            )
        extra_sections.append("")

        current_counts = manifest["checks"]["a"]["details"]["counts"]
        comparison_rows = [
            [
                "Effectif train",
                V10_BASELINE["counts"]["train"],
                current_counts["train"],
            ],
            ["Effectif val", V10_BASELINE["counts"]["val"], current_counts["val"]],
            [
                "Effectif test",
                V10_BASELINE["counts"]["test"],
                current_counts["test"],
            ],
            [
                "Source intent SHA-256",
                V10_BASELINE["source_intent_sha256"],
                manifest["sources"]["intent_dataset"]["sha256"],
            ],
            [
                "intent_test SHA-256",
                V10_BASELINE["intent_test_sha256"],
                manifest["frozen_files"]["intent_test.jsonl"]["sha256"],
            ],
            [
                "Fuite TR-0001",
                V10_BASELINE["translation_leak"],
                "corrigée : INT-0421 et INT-0445 tous deux en test",
            ],
        ]
        extra_sections.extend(
            [
                "## Comparaison v1.0 / v1.1",
                "",
                md_table(["Élément", "v1.0", "v1.1"], comparison_rows),
                "",
            ]
        )

    lines = [
        "# Rapport de gel des jeux de test — SupportAI",
        "",
        f"- Version : **v{manifest['version']}**",
        f"- Dossier : `{manifest['frozen_dir']}/`",
        f"- Note de version : {manifest.get('version_notes', '')}",
        f"- Licence : **{manifest['license']}** (`{manifest['license_status']}`)",
        f"- Source de la licence : `{manifest['license_source']}`",
        f"- Note de licence : {manifest['license_notes']}",
        f"- Statut d'annotation : `{manifest['annotation_status']}`",
        f"- Graine : `{manifest['seed']}`",
        "- Horodatage : aucun (rapport reproductible).",
        "",
        *extra_sections,
        "## Contrôles anti-fuite",
        "",
        md_table(["Contrôle", "Description", "Résultat"], check_rows),
        "",
        "Le contrôle **e** est non bloquant : il signale des paires à revoir ; "
        "aucune étiquette ni aucun texte n'est corrigé par le script.",
        "",
        "## Paires à revue humaine",
        "",
        *review_lines,
        "## Effectifs figés",
        "",
        md_table(
            ["Split", "Total", "FR", "EN", "SHA-256 de la liste d'ids"],
            effectif_rows,
        ),
        "",
        f"Total général : **{split_ids['total']['rows']}** exemples "
        f"({split_ids['total']['by_language'].get('fr', 0)} FR, "
        f"{split_ids['total']['by_language'].get('en', 0)} EN).",
        "",
        "## Fichiers gelés",
        "",
        md_table(["Fichier", "Lignes", "Octets", "SHA-256"], file_rows),
        "",
        "## Empreintes des sources",
        "",
        md_table(["Source", "Lignes", "SHA-256"], source_rows),
        "",
        "## Provenance git",
        "",
        f"- Commit courant : `{manifest['git']['head']}`",
        f"- État : **{manifest['git']['state']}**",
        f"- Commit des guidelines : `{manifest['guidelines']['commit']}`",
        f"- SHA-256 des guidelines : `{manifest['guidelines']['sha256']}`",
        "",
        "## Commandes",
        "",
        "```bash",
        f"python scripts/freeze_test_sets.py freeze --version {manifest['version']}  # premier gel uniquement",
        f"python scripts/freeze_test_sets.py verify --version {manifest['version']}",
        "python scripts/freeze_test_sets.py verify --version 1.0  # gel historique",
        f"python scripts/freeze_test_sets.py freeze --version {manifest['version']}  # doit refuser d'ecraser",
        f"sha256sum data/frozen/v{manifest['version']}/*                        # ou hashlib si sha256sum est absent",
        "python tests/test_freeze.py",
        "python tests/test_translation_leak.py",
        "git status --short",
        "```",
        "",
    ]
    report_text = "\n".join(lines).rstrip() + "\n"
    path = root / "docs" / "reports" / "freeze_report.md"
    versioned_path = root / "docs" / "reports" / f"freeze_report_v{manifest['version']}.md"
    for output in (path, versioned_path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_text, encoding="utf-8", newline="\n")
    return path


# ---------------------------------------------------------------------------
# API freeze / verify
# ---------------------------------------------------------------------------


def freeze(
    root: Path = ROOT,
    version: str = VERSION,
    write_report: bool = True,
) -> dict:
    root = Path(root)
    frozen_dir = root / "data" / "frozen" / f"v{version}"
    if frozen_dir.exists():
        raise FreezeError(
            f"Refus d'écraser le gel existant : data/frozen/v{version}/. "
            "Utilisez une nouvelle version."
        )

    paths = source_paths_for(version)
    sources = load_sources(root, version, paths)
    checks = run_checks(sources)
    blocking_ko = [
        letter
        for letter, check in checks.items()
        if check["status"] == "KO" and check["blocking"]
    ]
    if blocking_ko:
        details = "; ".join(
            f"{letter}: {checks[letter]['label']}" for letter in blocking_ko
        )
        raise FreezeError(f"Contrôles anti-fuite KO : {details}. Rien n'a été écrit.")

    frozen_files = build_frozen_files(sources, version)
    guidelines_path = root / GUIDELINES_PATH
    if not guidelines_path.exists():
        raise FreezeError(f"Guidelines absentes : {GUIDELINES_PATH}. Rien n'a été écrit.")
    manifest = build_manifest(
        root,
        version,
        sources,
        checks,
        frozen_files,
        guidelines_path,
        source_paths=paths,
    )
    frozen_bytes = dict(frozen_files)
    frozen_bytes["MANIFEST.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    frozen_dir.mkdir(parents=True)
    for name, data in frozen_bytes.items():
        (frozen_dir / name).write_bytes(data)

    if write_report:
        split_ids = build_split_ids(sources["intent_dataset"]["rows"], version)
        write_freeze_report(root, manifest, split_ids)
    return manifest


def verify(root: Path = ROOT, version: str = VERSION, verbose: bool = True) -> bool:
    root = Path(root)
    frozen_dir = root / "data" / "frozen" / f"v{version}"
    manifest_path = frozen_dir / "MANIFEST.json"
    if not manifest_path.exists():
        if verbose:
            print(f"KO  MANIFEST absent : data/frozen/v{version}/MANIFEST.json")
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if verbose:
            print(f"KO  MANIFEST illisible : {exc}")
        return False

    ok = True

    def report(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        status = "OK " if passed else "KO "
        if verbose:
            print(ascii_text(f"{status} {label}{(' - ' + detail) if detail else ''}"))
        if not passed:
            ok = False

    for name, info in sorted(manifest.get("frozen_files", {}).items()):
        path = root / info["path"]
        if not path.exists():
            report(f"fichier {name}", False, "absent")
            continue
        data = path.read_bytes()
        passed = (
            sha256_bytes(data) == info["sha256"]
            and len(data) == info["size_bytes"]
            and len(data.splitlines()) == info["lines"]
        )
        report(f"fichier {name}", passed, info["sha256"])

    for name, info in sorted(manifest.get("sources", {}).items()):
        path = root / info["path"]
        if not path.exists():
            report(f"source {name}", False, "absente")
            continue
        data = path.read_bytes()
        passed = (
            sha256_bytes(data) == info["sha256"]
            and len(data) == info["size_bytes"]
            and len(data.splitlines()) == info["lines"]
        )
        report(f"source {name}", passed, info["sha256"])

    guidelines_info = manifest.get("guidelines", {})
    guidelines_path = root / guidelines_info.get("path", GUIDELINES_PATH)
    if guidelines_path.exists():
        report(
            "guidelines",
            sha256_file(guidelines_path) == guidelines_info.get("sha256"),
            guidelines_info.get("sha256", ""),
        )
    else:
        report("guidelines", False, "absentes")

    paths = {
        key: info["path"]
        for key, info in manifest.get("sources", {}).items()
        if isinstance(info, dict) and "path" in info
    } or source_paths_for(version)
    if all((root / relative_path).exists() for relative_path in paths.values()):
        sources = load_sources(root, version, paths)
        current_checks = run_checks(sources)
    else:
        current_checks = {}
    for letter in sorted(manifest.get("checks", {})):
        expected = manifest["checks"][letter]
        actual = current_checks.get(letter)
        passed = bool(
            actual
            and actual["status"] == expected["status"]
            and actual["details"] == expected["details"]
        )
        report(f"contrôle {letter}", passed, CHECK_LABELS.get(letter, ""))

    if verbose:
        print("VERIFY " + ("OK" if ok else "KO"))
    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def ascii_text(text: str) -> str:
    """Rend la sortie console compatible avec les terminaux cp1252."""
    return (
        text.replace("↔", "<->")
        .replace("→", "->")
        .replace("≥", ">=")
        .replace("≤", "<=")
        .replace("—", "-")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_parser = subparsers.add_parser(
        "freeze", help="contrôler puis écrire le gel versionné"
    )
    freeze_parser.add_argument(
        "--version", default=VERSION, help="version du gel (défaut : 1.0)"
    )
    verify_parser = subparsers.add_parser(
        "verify", help="vérifier sans modifier le gel"
    )
    verify_parser.add_argument(
        "--version", default=VERSION, help="version du gel à vérifier (défaut : 1.0)"
    )
    args = parser.parse_args(argv)

    if args.command == "freeze":
        try:
            manifest = freeze(version=args.version)
        except FreezeError as exc:
            print(ascii_text(f"FREEZE KO : {exc}"), file=sys.stderr)
            return 1
        print(ascii_text(f"FREEZE OK : v{manifest['version']} ecrit dans {manifest['frozen_dir']}/"))
        for letter in sorted(manifest["checks"]):
            check = manifest["checks"][letter]
            suffix = " (non bloquant)" if not check["blocking"] else ""
            print(
                ascii_text(
                    f"  {letter}. {check['status']} - {check['label']}{suffix}"
                )
            )
        return 0

    return 0 if verify(version=args.version) else 1


if __name__ == "__main__":
    raise SystemExit(main())
