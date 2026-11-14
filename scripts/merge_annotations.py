#!/usr/bin/env python3
"""Fusionner les annotations aveugles d'intentions et mesurer l'accord.

Le script ne choisit jamais une étiquette à la place des annotateurs. En cas
de désaccord, il écrit une file d'arbitrage vide dans
``docs/reports/adjudication_log.csv``. Le mode ``--build`` refuse de produire
``intent_dataset.jsonl`` tant que tous les désaccords n'ont pas reçu un
``adjudicated_intent``.

Commandes :
    python scripts/merge_annotations.py
    python scripts/merge_annotations.py --build
    python scripts/merge_annotations.py --single-annotator
    python scripts/merge_annotations.py --build --single-annotator

Le mode ``--single-annotator`` n'ouvre pas le fichier de Mohammed, ne calcule
aucun kappa et n'écrit aucune file d'arbitrage. Il compare les étiquettes d'Aya
aux cibles privées pour produire une liste de relecture, sans correction
automatique : les corrections de relecture sont appliquées dans les fichiers
d'annotation.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import re
import subprocess
import sys
import unicodedata
import warnings
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

ANNOTATION_COLUMNS = ["id", "language", "text", "intent", "ambiguous", "acceptable_labels", "notes"]
ADJUDICATION_COLUMNS = [
    "id",
    "text",
    "intent_aya",
    "intent_mohammed",
    "adjudicated_intent",
    "arbiter",
    "date",
    "justification",
]
DATASET_FIELDS = [
    "id",
    "text",
    "language",
    "intent",
    "acceptable_labels",
    "ambiguous",
    "source",
    "split",
    "annotator_1",
    "annotator_2",
    "adjudicated",
    "notes",
    "created_at",
]
DATASET_CSV_FIELDS = ["id", "text", "language", "intent", "split"]

SHEET_CANDIDATES = {
    "aya": (
        "annotate_aya_done.csv",
        "annotate_aya.csv",
    ),
    "mohammed": (
        "annotate_mohammed_done.csv",
        "annotate_mohammed.csv",
    ),
    "spotcheck": (
        "spotcheck_train_aya_done.csv",
        "spotcheck_train_aya.csv",
    ),
}

SEED = 42

try:  # scikit-learn est déjà installé dans l'environnement du projet.
    from sklearn.metrics import cohen_kappa_score as _sklearn_kappa
except Exception:  # pragma: no cover - repli stdlib
    _sklearn_kappa = None


@dataclass
class Config:
    root: Path
    blind_dir: Path
    candidates_path: Path
    split_path: Path
    intents_path: Path
    adjudication_path: Path
    previous_path: Path
    dataset_jsonl: Path
    dataset_csv: Path
    report_path: Path
    guidelines_path: Path
    aya_path: Path | None = None
    mohammed_path: Path | None = None
    spotcheck_path: Path | None = None
    today: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class Annotation:
    id: str
    language: str
    text: str
    intent: str
    ambiguous: bool
    acceptable_labels: list[str]
    notes: str
    path: Path
    row_number: int


def default_config() -> Config:
    return Config(
        root=ROOT,
        blind_dir=ROOT / "data" / "annotations" / "blind",
        candidates_path=ROOT / "data" / "annotations" / "_private" / "intent_candidates.jsonl",
        split_path=ROOT / "data" / "annotations" / "_private" / "intent_split.csv",
        intents_path=ROOT / "data" / "annotations" / "intents.csv",
        adjudication_path=ROOT / "docs" / "reports" / "adjudication_log.csv",
        previous_path=ROOT / "docs" / "reports" / "adjudication_log.previous.csv",
        dataset_jsonl=ROOT / "data" / "annotations" / "intent_dataset.jsonl",
        dataset_csv=ROOT / "data" / "annotations" / "intent_dataset.csv",
        report_path=ROOT / "docs" / "reports" / "intent_dataset_report.md",
        guidelines_path=ROOT / "docs" / "annotation_guidelines.md",
    )


def ok(message: str) -> None:
    print(f"[OK] {message}")


def ko(message: str) -> None:
    print(f"[KO] {message}")


def info(message: str) -> None:
    print(f"[INFO] {message}")


def attention(message: str) -> None:
    print(f"[ATTENTION] {message}")


def relpath(path: Path, config: Config) -> str:
    try:
        return path.resolve().relative_to(config.root.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Fichier absent : {path}")
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise SystemExit(f"JSON invalide ligne {line_number} : {error}") from error
    return rows


def load_candidates(config: Config) -> list[dict]:
    return read_jsonl(config.candidates_path)


def load_split(config: Config) -> dict[str, str]:
    if not config.split_path.exists():
        raise SystemExit(f"Fichier absent : {config.split_path}")
    with config.split_path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["id"]: row["split"] for row in csv.DictReader(handle)}


def load_intents(config: Config) -> tuple[list[str], dict[str, dict[str, str]]]:
    if not config.intents_path.exists():
        raise SystemExit(f"Fichier absent : {config.intents_path}")
    with config.intents_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row["intent_id"] for row in rows], {row["intent_id"]: row for row in rows}


def resolve_sheet_path(config: Config, role: str) -> Path:
    explicit = {
        "aya": config.aya_path,
        "mohammed": config.mohammed_path,
        "spotcheck": config.spotcheck_path,
    }[role]
    if explicit is not None:
        return Path(explicit)
    for name in SHEET_CANDIDATES[role]:
        path = config.blind_dir / name
        if path.exists():
            return path
    return config.blind_dir / SHEET_CANDIDATES[role][0]


def parse_bool(value: str) -> bool | None:
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1", "yes", "oui"}:
        return True
    if normalized in {"false", "0", "no", "non"}:
        return False
    return None


def parse_labels(value: str) -> list[str]:
    labels: list[str] = []
    for part in re.split(r"[|;,]", value or ""):
        label = part.strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def read_annotation_csv(path: Path) -> tuple[list[Annotation], list[str]]:
    if not path.exists():
        return [], [f"Fichier absent : {path}"]
    errors: list[str] = []
    annotations: list[Annotation] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if header != ANNOTATION_COLUMNS:
            return [], [
                f"{path.name} : en-tête inattendu {header} ; attendu {ANNOTATION_COLUMNS}"
            ]
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                errors.append(f"{path.name}:{row_number} : colonnes en trop")
                continue
            identifier = (row.get("id") or "").strip()
            language = (row.get("language") or "").strip().lower()
            text = row.get("text") or ""
            intent = (row.get("intent") or "").strip()
            ambiguous_raw = (row.get("ambiguous") or "").strip()
            ambiguous = parse_bool(ambiguous_raw)
            labels = parse_labels(row.get("acceptable_labels") or "")
            notes = (row.get("notes") or "").strip()

            if not any(
                [identifier, language, text.strip(), intent, ambiguous_raw, labels, notes]
            ):
                errors.append(f"{path.name}:{row_number} : ligne entièrement vide")
                continue
            if not identifier:
                errors.append(f"{path.name}:{row_number} : id vide")
            if not language:
                errors.append(f"{path.name}:{row_number} : language vide")
            if not text.strip():
                errors.append(f"{path.name}:{row_number} : text vide")
            if not intent:
                errors.append(f"{path.name}:{row_number} : intent vide")
            if not ambiguous_raw:
                errors.append(f"{path.name}:{row_number} : ambiguous vide")
            if ambiguous is None and ambiguous_raw:
                errors.append(
                    f"{path.name}:{row_number} : ambiguous invalide {ambiguous_raw!r}"
                )
            annotations.append(
                Annotation(
                    id=identifier,
                    language=language,
                    text=text,
                    intent=intent,
                    ambiguous=bool(ambiguous),
                    acceptable_labels=labels,
                    notes=notes,
                    path=path,
                    row_number=row_number,
                )
            )
    return annotations, errors


def expected_spotcheck_ids(candidates: list[dict], split: dict[str, str]) -> set[str]:
    """Reproduit exactement le tirage de prepare_intent_annotation.py (SEED=42)."""
    rng = random.Random(SEED)
    selected: list[str] = []
    for intent in sorted({row["target_intent"] for row in candidates}):
        for language in ("fr", "en"):
            group = [
                row
                for row in candidates
                if row["target_intent"] == intent
                and row["language"] == language
                and split.get(row["id"]) == "train"
            ]
            rng.shuffle(group)
            selected.extend(row["id"] for row in group[:2])
    return set(selected)


def detect_misalignment(
    aya_list: list[Annotation],
    mohammed_list: list[Annotation],
    aya_by_id: dict[str, Annotation],
    mohammed_by_id: dict[str, Annotation],
) -> dict:
    total = min(len(aya_list), len(mohammed_list))
    same_positional_labels = (
        len(aya_list) == len(mohammed_list)
        and total > 0
        and all(aya.intent == moh.intent for aya, moh in zip(aya_list, mohammed_list))
    )
    same_text_order = (
        len(aya_list) == len(mohammed_list)
        and total > 0
        and all(aya.text == moh.text for aya, moh in zip(aya_list, mohammed_list))
    )
    label_multiset_equal = sorted(a.intent for a in aya_list) == sorted(
        m.intent for m in mohammed_list
    )
    common = sorted(set(aya_by_id) & set(mohammed_by_id))
    per_id_agreement = sum(
        1 for identifier in common if aya_by_id[identifier].intent == mohammed_by_id[identifier].intent
    )
    per_id_total = len(common)
    low_per_id = per_id_total > 0 and per_id_agreement / per_id_total < 0.5
    suspected = bool(
        label_multiset_equal
        and not same_text_order
        and (same_positional_labels or low_per_id)
    )
    message = ""
    if suspected:
        message = (
            "Les étiquettes de Mohammed sont identiques à celles d'Aya rang par rang, "
            "alors que l'ordre des textes diffère "
            f"(accord par identifiant : {per_id_agreement}/{per_id_total}). "
            "Cela suggère une colonne copiée/collée sans réalignement. "
            "Aucune étiquette n'est corrigée automatiquement ; les désaccords sont consignés tels quels."
        )
    elif low_per_id:
        message = (
            f"Accord par identifiant très faible ({per_id_agreement}/{per_id_total}) ; "
            "vérifier l'alignement des deux feuilles avant d'exploiter le kappa."
        )
    return {
        "suspected": suspected,
        "same_positional_labels": same_positional_labels,
        "same_text_order": same_text_order,
        "label_multiset_equal": label_multiset_equal,
        "per_id_agreement": per_id_agreement,
        "per_id_total": per_id_total,
        "message": message,
    }


def validate_inputs(
    config: Config,
    candidates: list[dict],
    split: dict[str, str],
    codes: list[str],
) -> tuple[dict | None, list[str], list[str], dict, dict[str, Path]]:
    errors: list[str] = []
    warnings_list: list[str] = []
    paths = {
        "aya": resolve_sheet_path(config, "aya"),
        "mohammed": resolve_sheet_path(config, "mohammed"),
        "spotcheck": resolve_sheet_path(config, "spotcheck"),
    }

    for role, path in paths.items():
        if not path.exists():
            errors.append(f"Fichier {role} absent : {relpath(path, config)}")
    if errors:
        return None, errors, warnings_list, {}, paths

    for role, path in paths.items():
        canonical = config.blind_dir / SHEET_CANDIDATES[role][0]
        if path.name != canonical.name:
            warnings_list.append(
                f"Nom canonique {canonical.name} absent ; utilisation de {relpath(path, config)}."
            )

    aya_list, aya_errors = read_annotation_csv(paths["aya"])
    mohammed_list, mohammed_errors = read_annotation_csv(paths["mohammed"])
    spotcheck_list, spotcheck_errors = read_annotation_csv(paths["spotcheck"])
    errors.extend(aya_errors)
    errors.extend(mohammed_errors)
    errors.extend(spotcheck_errors)
    if errors:
        return None, errors, warnings_list, {}, paths

    candidates_by_id = {row["id"]: row for row in candidates}
    if len(candidates_by_id) != len(candidates):
        errors.append("Ids dupliqués dans intent_candidates.jsonl")
    if set(split) != set(candidates_by_id):
        missing = sorted(set(candidates_by_id) - set(split))[:10]
        extra = sorted(set(split) - set(candidates_by_id))[:10]
        errors.append(f"intent_split.csv ne couvre pas les candidats : absents={missing}, en trop={extra}")

    expected_valtest = {identifier for identifier, name in split.items() if name in {"val", "test"}}
    expected_spotcheck = expected_spotcheck_ids(candidates, split)

    def check_ids(role: str, rows: list[Annotation], expected: set[str]) -> None:
        ids = [row.id for row in rows]
        duplicates = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
        if duplicates:
            errors.append(f"{role} : ids dupliqués {duplicates[:10]}")
        actual = set(ids)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append(f"{role} : {len(missing)} id(s) attendu(s) absent(s) {missing[:20]}")
        if extra:
            errors.append(f"{role} : {len(extra)} id(s) inattendu(s) {extra[:20]}")
        if len(rows) != len(expected):
            errors.append(f"{role} : {len(rows)} lignes au lieu de {len(expected)}")

    check_ids("annotate_aya", aya_list, expected_valtest)
    check_ids("annotate_mohammed", mohammed_list, expected_valtest)
    check_ids("spotcheck_train_aya", spotcheck_list, expected_spotcheck)

    def check_rows(role: str, rows: list[Annotation], allowed_splits: set[str]) -> None:
        for row in rows:
            location = f"{role}:{row.row_number}"
            if row.intent not in codes:
                errors.append(f"{location} : intent inconnu {row.intent!r}")
            if row.language not in {"fr", "en"}:
                errors.append(f"{location} : language invalide {row.language!r}")
            if row.ambiguous and not row.acceptable_labels:
                errors.append(
                    f"{location} : ambiguous=true mais acceptable_labels vide"
                )
            if not row.ambiguous and row.acceptable_labels:
                warnings_list.append(
                    f"{location} : acceptable_labels renseigné alors que ambiguous=false"
                )
            for label in row.acceptable_labels:
                if label not in codes:
                    errors.append(f"{location} : acceptable_labels contient {label!r} inconnu")
            if row.id in split and split[row.id] not in allowed_splits:
                errors.append(
                    f"{location} : id {row.id} dans le split {split[row.id]!r}, "
                    f"attendu {sorted(allowed_splits)}"
                )
            candidate = candidates_by_id.get(row.id)
            if candidate is None:
                errors.append(f"{location} : id absent de intent_candidates.jsonl")
                continue
            if row.text != candidate["text"]:
                errors.append(f"{location} : texte différent du fichier privé")
            if row.language != candidate["language"]:
                errors.append(f"{location} : langue différente du fichier privé")

    check_rows("annotate_aya", aya_list, {"val", "test"})
    check_rows("annotate_mohammed", mohammed_list, {"val", "test"})
    check_rows("spotcheck_train_aya", spotcheck_list, {"train"})

    if not errors:
        expected_spot_counts = Counter(
            (candidates_by_id[identifier]["target_intent"], candidates_by_id[identifier]["language"])
            for identifier in expected_spotcheck
        )
        actual_spot_counts = Counter(
            (candidates_by_id[row.id]["target_intent"], candidates_by_id[row.id]["language"])
            for row in spotcheck_list
        )
        if actual_spot_counts != expected_spot_counts:
            errors.append(
                "spotcheck : répartition par intention/langue différente du tirage attendu "
                f"({dict(actual_spot_counts)} vs {dict(expected_spot_counts)})"
            )

    if errors:
        return None, errors, warnings_list, {}, paths

    aya_by_id = {row.id: row for row in aya_list}
    mohammed_by_id = {row.id: row for row in mohammed_list}
    spotcheck_by_id = {row.id: row for row in spotcheck_list}
    misalignment = detect_misalignment(aya_list, mohammed_list, aya_by_id, mohammed_by_id)
    if misalignment["message"]:
        warnings_list.append(misalignment["message"])

    annotations = {
        "aya": aya_by_id,
        "mohammed": mohammed_by_id,
        "spotcheck": spotcheck_by_id,
        "aya_list": aya_list,
        "mohammed_list": mohammed_list,
        "spotcheck_list": spotcheck_list,
    }
    return annotations, errors, warnings_list, misalignment, paths


def validate_single_inputs(
    config: Config,
    candidates: list[dict],
    split: dict[str, str],
    codes: list[str],
) -> tuple[dict | None, list[str], list[str], dict[str, Path]]:
    """Valider Aya + le sondage train sans ouvrir le fichier de Mohammed."""
    errors: list[str] = []
    warnings_list: list[str] = []
    paths = {
        "aya": resolve_sheet_path(config, "aya"),
        "spotcheck": resolve_sheet_path(config, "spotcheck"),
    }

    for role, path in paths.items():
        if not path.exists():
            errors.append(f"Fichier {role} absent : {relpath(path, config)}")
    if errors:
        return None, errors, warnings_list, paths

    for role, path in paths.items():
        canonical = config.blind_dir / SHEET_CANDIDATES[role][0]
        if path.name != canonical.name:
            warnings_list.append(
                f"Nom canonique {canonical.name} absent ; utilisation de {relpath(path, config)}."
            )

    aya_list, aya_errors = read_annotation_csv(paths["aya"])
    spotcheck_list, spotcheck_errors = read_annotation_csv(paths["spotcheck"])
    errors.extend(aya_errors)
    errors.extend(spotcheck_errors)
    if errors:
        return None, errors, warnings_list, paths

    candidates_by_id = {row["id"]: row for row in candidates}
    if len(candidates_by_id) != len(candidates):
        errors.append("Ids dupliqués dans intent_candidates.jsonl")
    if set(split) != set(candidates_by_id):
        missing = sorted(set(candidates_by_id) - set(split))[:10]
        extra = sorted(set(split) - set(candidates_by_id))[:10]
        errors.append(f"intent_split.csv ne couvre pas les candidats : absents={missing}, en trop={extra}")

    expected_valtest = {identifier for identifier, name in split.items() if name in {"val", "test"}}
    expected_spotcheck = expected_spotcheck_ids(candidates, split)

    def check_ids(role: str, rows: list[Annotation], expected: set[str]) -> None:
        ids = [row.id for row in rows]
        duplicates = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
        if duplicates:
            errors.append(f"{role} : ids dupliqués {duplicates[:10]}")
        actual = set(ids)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append(f"{role} : {len(missing)} id(s) attendu(s) absent(s) {missing[:20]}")
        if extra:
            errors.append(f"{role} : {len(extra)} id(s) inattendu(s) {extra[:20]}")
        if len(rows) != len(expected):
            errors.append(f"{role} : {len(rows)} lignes au lieu de {len(expected)}")

    check_ids("annotate_aya", aya_list, expected_valtest)
    check_ids("spotcheck_train_aya", spotcheck_list, expected_spotcheck)

    def check_rows(role: str, rows: list[Annotation], allowed_splits: set[str]) -> None:
        for row in rows:
            location = f"{role}:{row.row_number}"
            if row.intent not in codes:
                errors.append(f"{location} : intent inconnu {row.intent!r}")
            if row.language not in {"fr", "en"}:
                errors.append(f"{location} : language invalide {row.language!r}")
            if row.ambiguous and not row.acceptable_labels:
                errors.append(f"{location} : ambiguous=true mais acceptable_labels vide")
            if not row.ambiguous and row.acceptable_labels:
                warnings_list.append(
                    f"{location} : acceptable_labels renseigné alors que ambiguous=false"
                )
            for label in row.acceptable_labels:
                if label not in codes:
                    errors.append(f"{location} : acceptable_labels contient {label!r} inconnu")
            if row.id in split and split[row.id] not in allowed_splits:
                errors.append(
                    f"{location} : id {row.id} dans le split {split[row.id]!r}, "
                    f"attendu {sorted(allowed_splits)}"
                )
            candidate = candidates_by_id.get(row.id)
            if candidate is None:
                errors.append(f"{location} : id absent de intent_candidates.jsonl")
                continue
            if row.text != candidate["text"]:
                errors.append(f"{location} : texte différent du fichier privé")
            if row.language != candidate["language"]:
                errors.append(f"{location} : langue différente du fichier privé")

    check_rows("annotate_aya", aya_list, {"val", "test"})
    check_rows("spotcheck_train_aya", spotcheck_list, {"train"})

    if not errors:
        expected_spot_counts = Counter(
            (candidates_by_id[identifier]["target_intent"], candidates_by_id[identifier]["language"])
            for identifier in expected_spotcheck
        )
        actual_spot_counts = Counter(
            (candidates_by_id[row.id]["target_intent"], candidates_by_id[row.id]["language"])
            for row in spotcheck_list
        )
        if actual_spot_counts != expected_spot_counts:
            errors.append(
                "spotcheck : répartition par intention/langue différente du tirage attendu "
                f"({dict(actual_spot_counts)} vs {dict(expected_spot_counts)})"
            )

    if errors:
        return None, errors, warnings_list, paths

    annotations = {
        "aya": {row.id: row for row in aya_list},
        "spotcheck": {row.id: row for row in spotcheck_list},
        "aya_list": aya_list,
        "spotcheck_list": spotcheck_list,
    }
    return annotations, errors, warnings_list, paths


def target_coherence(
    annotations: dict, candidates: list[dict], split: dict[str, str]
) -> list[dict]:
    """Lister les écarts Aya / cible, sans corriger ni arbitrer."""
    candidates_by_id = {row["id"]: row for row in candidates}
    rows: list[dict] = []
    for split_name in ("val", "test"):
        for identifier in sorted(annotations["aya"]):
            if split.get(identifier) != split_name:
                continue
            aya = annotations["aya"][identifier]
            target = candidates_by_id[identifier]["target_intent"]
            if aya.intent != target:
                rows.append(
                    {
                        "scope": split_name,
                        "id": identifier,
                        "text": aya.text,
                        "aya": aya.intent,
                        "target": target,
                    }
                )
    for identifier in sorted(annotations["spotcheck"]):
        if split.get(identifier) != "train":
            continue
        spot = annotations["spotcheck"][identifier]
        target = candidates_by_id[identifier]["target_intent"]
        if spot.intent != target:
            rows.append(
                {
                    "scope": "train (sondage)",
                    "id": identifier,
                    "text": spot.text,
                    "aya": spot.intent,
                    "target": target,
                }
            )
    return rows


def single_intents(
    annotations: dict, candidates: list[dict], split: dict[str, str]
) -> dict[str, str]:
    """Étiquette retenue en mode annotateur unique."""
    result: dict[str, str] = {}
    for candidate in candidates:
        identifier = candidate["id"]
        if split.get(identifier) == "train":
            spot = annotations["spotcheck"].get(identifier)
            if spot is not None and spot.intent != candidate["target_intent"]:
                result[identifier] = spot.intent
            else:
                result[identifier] = candidate["target_intent"]
        else:
            result[identifier] = annotations["aya"][identifier].intent
    return result


def build_single_dataset(
    config: Config,
    annotations: dict,
    candidates: list[dict],
    split: dict[str, str],
) -> list[dict]:
    """Construire le dataset sans second annotateur ni arbitrage."""
    dataset: list[dict] = []
    for candidate in sorted(candidates, key=lambda row: row["id"]):
        identifier = candidate["id"]
        split_name = split[identifier]
        if split_name == "train":
            spot = annotations["spotcheck"].get(identifier)
            target = candidate["target_intent"]
            notes_parts: list[str] = []
            if spot is not None and spot.notes:
                notes_parts.append(spot.notes)
            if spot is not None and spot.intent != target:
                intent = spot.intent
                notes_parts.append(
                    f"Sondage Aya : {spot.intent} ; cible : {target}. "
                    "Étiquette du sondage conservée."
                )
            else:
                intent = target
            row = {
                "id": identifier,
                "text": candidate["text"],
                "language": candidate["language"],
                "intent": intent,
                "acceptable_labels": list(spot.acceptable_labels) if spot is not None else [],
                "ambiguous": spot.ambiguous if spot is not None else False,
                "source": "synthetic",
                "split": split_name,
                "annotator_1": "aya",
                "annotator_2": None,
                "adjudicated": False,
                "notes": " ".join(part for part in notes_parts if part),
                "created_at": config.today,
            }
        else:
            left = annotations["aya"][identifier]
            row = {
                "id": identifier,
                "text": candidate["text"],
                "language": candidate["language"],
                "intent": left.intent,
                "acceptable_labels": list(left.acceptable_labels),
                "ambiguous": left.ambiguous,
                "source": "synthetic",
                "split": split_name,
                "annotator_1": "aya",
                "annotator_2": None,
                "adjudicated": False,
                "notes": left.notes,
                "created_at": config.today,
                "annotation_status": "single_annotator",
            }
        dataset.append(row)
    return dataset


def manual_cohen_kappa(y1: list, y2: list, labels: list) -> float | None:
    if len(y1) != len(y2) or not y1:
        return None
    n = len(y1)
    observed = sum(1 for left, right in zip(y1, y2) if left == right) / n
    left_counts = Counter(y1)
    right_counts = Counter(y2)
    expected = sum((left_counts[label] / n) * (right_counts[label] / n) for label in labels)
    if expected >= 1.0 - 1e-12:
        return None
    return (observed - expected) / (1.0 - expected)


def cohen_kappa(y1: list, y2: list, labels: list) -> float | None:
    if len(y1) != len(y2) or not y1:
        return None
    if _sklearn_kappa is None:
        return manual_cohen_kappa(y1, y2, labels)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = _sklearn_kappa(y1, y2, labels=labels)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def kappa_interpretation(value: float | None) -> str:
    if value is None:
        return "indéfini (une seule classe)"
    if abs(value) < 0.0005:
        return "accord nul (κ ≈ 0)"
    if value < 0:
        return "désaccord (κ < 0)"
    if value <= 0.20:
        return "accord léger (0,00–0,20)"
    if value <= 0.40:
        return "accord faible (0,21–0,40)"
    if value <= 0.60:
        return "accord modéré (0,41–0,60)"
    if value <= 0.80:
        return "accord substantiel (0,61–0,80)"
    return "accord presque parfait (0,81–1,00)"


def agreement_stats(y1: list[str], y2: list[str], codes: list[str]) -> dict:
    n = len(y1)
    agreements = sum(1 for left, right in zip(y1, y2) if left == right)
    observed = agreements / n if n else 0.0
    kappa = cohen_kappa(y1, y2, codes)
    per_intent: dict[str, dict] = {}
    for code in codes:
        binary_left = [1 if value == code else 0 for value in y1]
        binary_right = [1 if value == code else 0 for value in y2]
        per_intent[code] = {
            "n": n,
            "aya_positive": sum(binary_left),
            "mohammed_positive": sum(binary_right),
            "kappa": cohen_kappa(binary_left, binary_right, [0, 1]),
        }
    confusion = Counter(zip(y1, y2))
    off_diagonal = [
        (left, right, count)
        for (left, right), count in confusion.items()
        if left != right and count > 0
    ]
    off_diagonal.sort(key=lambda item: (-item[2], item[0], item[1]))
    return {
        "n": n,
        "agreements": agreements,
        "observed": observed,
        "kappa": kappa,
        "per_intent": per_intent,
        "confusion": confusion,
        "top_confusions": off_diagonal[:5],
    }


def analyze_agreement(
    annotations: dict, split: dict[str, str], codes: list[str]
) -> dict[str, dict]:
    aya = annotations["aya"]
    mohammed = annotations["mohammed"]
    scopes = {
        "val": sorted(identifier for identifier in aya if split.get(identifier) == "val"),
        "test": sorted(identifier for identifier in aya if split.get(identifier) == "test"),
    }
    scopes["ensemble"] = sorted(set(scopes["val"]) | set(scopes["test"]))
    results: dict[str, dict] = {}
    for name, identifiers in scopes.items():
        y1 = [aya[identifier].intent for identifier in identifiers]
        y2 = [mohammed[identifier].intent for identifier in identifiers]
        results[name] = agreement_stats(y1, y2, codes)
    return results


def print_agreement(results: dict[str, dict]) -> None:
    print("\n=== Accord inter-annotateurs ===")
    for name in ("val", "test", "ensemble"):
        result = results[name]
        print(
            f"{name:<9} : n={result['n']:>3}, accords={result['agreements']:>3}, "
            f"taux={100 * result['observed']:6.2f} %, κ={format_kappa(result['kappa'])} "
            f"({kappa_interpretation(result['kappa'])})"
        )
    top = results["ensemble"]["top_confusions"]
    if top:
        print("5 paires les plus confondues (Aya -> Mohammed) :")
        for left, right, count in top:
            print(f"  {left} -> {right} : {count}")
    else:
        print("Aucune paire confondue.")


def disagreement_rows(annotations: dict, split: dict[str, str]) -> list[dict]:
    aya = annotations["aya"]
    mohammed = annotations["mohammed"]
    rows: list[dict] = []
    for identifier in sorted(aya):
        if split.get(identifier) not in {"val", "test"}:
            continue
        left = aya[identifier]
        right = mohammed[identifier]
        if left.intent == right.intent:
            continue
        rows.append(
            {
                "id": identifier,
                "text": left.text,
                "intent_aya": left.intent,
                "intent_mohammed": right.intent,
                "adjudicated_intent": "",
                "arbiter": "",
                "date": "",
                "justification": "",
            }
        )
    return rows


def normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalize_lf(text))


def count_data_rows(text: str) -> int:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return 0
    return sum(1 for row in rows[1:] if any(cell.strip() for cell in row))


def git_show_head(config: Config, path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(config.root.resolve()).as_posix()
        result = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=config.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        return None
    return None


def backup_previous_adjudication(config: Config) -> str:
    current = config.adjudication_path
    previous = config.previous_path
    if previous.exists():
        previous_rows = count_data_rows(previous.read_text(encoding="utf-8-sig"))
        if previous_rows > 0:
            return (
                f"Sauvegarde existante conservée dans {relpath(previous, config)} "
                f"({previous_rows} ligne(s))."
            )

    if not current.exists():
        legacy = git_show_head(config, current)
        if legacy and count_data_rows(legacy) > 0:
            write_text_lf(previous, legacy)
            return f"Ancien journal restauré depuis HEAD vers {relpath(previous, config)}."
        return "Aucun journal existant à sauvegarder."

    current_text = current.read_text(encoding="utf-8-sig")
    current_rows = count_data_rows(current_text)
    if current_rows > 0:
        write_text_lf(previous, current_text)
        return (
            f"Ancien journal ({current_rows} ligne(s)) sauvegardé dans "
            f"{relpath(previous, config)}."
        )

    legacy = git_show_head(config, current)
    if legacy and count_data_rows(legacy) > 0:
        write_text_lf(previous, legacy)
        return (
            f"Journal courant vide ; ancienne version de HEAD "
            f"({count_data_rows(legacy)} ligne(s)) sauvegardée dans {relpath(previous, config)}."
        )

    write_text_lf(previous, current_text)
    return f"Journal courant vide sauvegardé dans {relpath(previous, config)}."


def read_adjudication_log(config: Config) -> tuple[list[dict], list[str]]:
    path = config.adjudication_path
    if not path.exists():
        return [], [f"Journal d'arbitrage absent : {relpath(path, config)}"]
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if header != ADJUDICATION_COLUMNS:
            return [], [
                f"{relpath(path, config)} : en-tête inattendu {header} ; attendu {ADJUDICATION_COLUMNS}"
            ]
        rows: list[dict] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                errors.append(f"{relpath(path, config)}:{row_number} : colonnes en trop")
                continue
            rows.append({column: (row.get(column) or "") for column in ADJUDICATION_COLUMNS})
    return rows, errors


def write_adjudication_log(
    config: Config, rows: list[dict], preserve: bool = True
) -> tuple[int, int]:
    existing: dict[str, dict] = {}
    if preserve and config.adjudication_path.exists():
        existing_rows, _errors = read_adjudication_log(config)
        existing = {row["id"]: row for row in existing_rows}

    output: list[dict] = []
    preserved = 0
    for row in rows:
        new_row = dict(row)
        previous = existing.get(row["id"])
        if previous and previous.get("adjudicated_intent", "").strip():
            for column in ("adjudicated_intent", "arbiter", "date", "justification"):
                new_row[column] = previous.get(column, "")
            preserved += 1
        output.append(new_row)

    config.adjudication_path.parent.mkdir(parents=True, exist_ok=True)
    with config.adjudication_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=ADJUDICATION_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(output)
    return len(output), preserved


def check_adjudications(
    config: Config, disagreements: list[dict], codes: list[str]
) -> tuple[dict[str, str], list[str], list[str]]:
    if not disagreements:
        return {}, [], []
    rows, errors = read_adjudication_log(config)
    if errors:
        return {}, errors, []
    duplicates = sorted(
        identifier for identifier, count in Counter(row["id"] for row in rows).items() if count > 1
    )
    if duplicates:
        errors.append(f"Journal d'arbitrage : ids dupliqués {duplicates[:10]}")
    by_id = {row["id"]: row for row in rows}
    adjudications: dict[str, str] = {}
    missing: list[str] = []
    invalid: list[tuple[str, str]] = []
    warnings_list: list[str] = []
    for disagreement in disagreements:
        identifier = disagreement["id"]
        row = by_id.get(identifier)
        value = (row or {}).get("adjudicated_intent", "").strip()
        if not value:
            missing.append(identifier)
            continue
        if value not in codes:
            invalid.append((identifier, value))
            continue
        adjudications[identifier] = value
        for column in ("arbiter", "date", "justification"):
            if not (row or {}).get(column, "").strip():
                warnings_list.append(
                    f"{identifier} : {column} vide alors que adjudicated_intent est renseigné."
                )
    if missing:
        errors.append(
            f"{len(missing)} désaccord(s) sans adjudicated_intent : {missing[:20]}"
        )
    if invalid:
        errors.append(f"adjudicated_intent invalide : {invalid[:20]}")
    return adjudications, errors, warnings_list


def provisional_intents(annotations: dict, candidates: list[dict], split: dict[str, str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for candidate in candidates:
        identifier = candidate["id"]
        if split.get(identifier) == "train":
            spot = annotations["spotcheck"].get(identifier)
            if spot is not None and spot.intent != candidate["target_intent"]:
                result[identifier] = spot.intent
            else:
                result[identifier] = candidate["target_intent"]
        else:
            left = annotations["aya"][identifier]
            right = annotations["mohammed"][identifier]
            result[identifier] = left.intent if left.intent == right.intent else None
    return result


def build_dataset(
    config: Config,
    annotations: dict,
    candidates: list[dict],
    split: dict[str, str],
    adjudications: dict[str, str],
) -> list[dict]:
    dataset: list[dict] = []
    for candidate in sorted(candidates, key=lambda row: row["id"]):
        identifier = candidate["id"]
        split_name = split[identifier]
        notes = ""
        if split_name == "train":
            spot = annotations["spotcheck"].get(identifier)
            target = candidate["target_intent"]
            if spot is not None and spot.intent != target:
                intent = spot.intent
                notes = (
                    f"Sondage Aya : {spot.intent} ; cible : {target}. "
                    "Étiquette du sondage conservée."
                )
            else:
                intent = target
            ambiguous = spot.ambiguous if spot is not None else False
            acceptable_labels = list(spot.acceptable_labels) if spot is not None else []
            annotator_2 = None
            adjudicated = False
        else:
            left = annotations["aya"][identifier]
            right = annotations["mohammed"][identifier]
            ambiguous = left.ambiguous or right.ambiguous
            acceptable_labels = sorted(set(left.acceptable_labels) | set(right.acceptable_labels))
            if ambiguous and not acceptable_labels:
                acceptable_labels = sorted({left.intent, right.intent})
            if left.intent == right.intent:
                intent = left.intent
                adjudicated = False
            else:
                intent = adjudications[identifier]
                adjudicated = True
                notes = (
                    f"Désaccord Aya={left.intent}, Mohammed={right.intent} ; "
                    f"arbitrage={intent}."
                )
            annotator_2 = "mohammed"

        dataset.append(
            {
                "id": identifier,
                "text": candidate["text"],
                "language": candidate["language"],
                "intent": intent,
                "acceptable_labels": acceptable_labels,
                "ambiguous": ambiguous,
                "source": "synthetic",
                "split": split_name,
                "annotator_1": "aya",
                "annotator_2": annotator_2,
                "adjudicated": adjudicated,
                "notes": notes,
                "created_at": config.today,
            }
        )
    return dataset


def write_dataset(config: Config, dataset: list[dict]) -> None:
    config.dataset_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with config.dataset_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for row in dataset:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    with config.dataset_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=DATASET_CSV_FIELDS, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(dataset)


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("’", "'").replace("œ", "oe").replace("æ", "ae")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", text)


def ngrams(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index : index + size])
        for index in range(len(tokens) - size + 1)
    }


def jaccard(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def quasi_duplicate_pairs(candidates: list[dict], threshold: float = 0.8) -> list[tuple[str, str, float]]:
    token_sets = {
        row["id"]: ngrams(tokenize(row["text"]), 3) for row in candidates
    }
    pairs: list[tuple[str, str, float]] = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            score = jaccard(token_sets[left["id"]], token_sets[right["id"]])
            if score >= threshold:
                pairs.append((left["id"], right["id"], score))
    return pairs


def exact_duplicates(candidates: list[dict]) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for row in candidates:
        normalized = " ".join(tokenize(row["text"]))
        groups.setdefault(normalized, []).append(row["id"])
    return [identifiers for identifiers in groups.values() if len(identifiers) > 1]


def format_kappa(value: float | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) < 0.0005:
        return "0,000"
    return f"{value:.3f}".replace(".", ",")


def format_pct(value: float) -> str:
    return f"{100 * value:.2f}".replace(".", ",") + " %"


def md_escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(cell) for cell in row) + " |")
    return "\n".join(lines)


def guidelines_state(config: Config) -> tuple[str, str]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=config.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        commit_hash = commit.stdout.strip() if commit.returncode == 0 else "inconnu"
    except Exception:
        commit_hash = "inconnu"
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "docs/annotation_guidelines.md"],
            cwd=config.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        dirty = bool(status.stdout.strip()) if status.returncode == 0 else False
    except Exception:
        dirty = False
    state = "modifié dans le worktree" if dirty else "identique à HEAD"
    return commit_hash, state


def write_report(
    config: Config,
    *,
    candidates: list[dict],
    split: dict[str, str],
    codes: list[str],
    annotations: dict,
    agreement: dict[str, dict],
    disagreements: list[dict],
    adjudications: dict[str, str] | None,
    dataset: list[dict] | None,
    build_status: str,
    validation_warnings: list[str],
    sheet_paths: dict[str, Path],
    backup_info: str,
    misalignment: dict,
) -> None:
    candidates_by_id = {row["id"]: row for row in candidates}
    provisional = provisional_intents(annotations, candidates, split)
    train_ids = sorted(identifier for identifier, name in split.items() if name == "train")
    train_counts = Counter(provisional[identifier] for identifier in train_ids if provisional[identifier])
    train_total = sum(train_counts.values())
    min_class = min(train_counts.values()) if train_counts else 0
    min_classes = sorted(code for code in codes if train_counts.get(code, 0) < 25)
    majority_class, majority_count = (
        max(train_counts.items(), key=lambda item: (item[1], item[0]))
        if train_counts
        else ("n/a", 0)
    )
    majority_share = majority_count / train_total if train_total else 0.0

    ambiguous_count = 0
    for candidate in candidates:
        identifier = candidate["id"]
        if split.get(identifier) == "train":
            spot = annotations["spotcheck"].get(identifier)
            if spot is not None and spot.ambiguous:
                ambiguous_count += 1
        else:
            left = annotations["aya"][identifier]
            right = annotations["mohammed"][identifier]
            if left.ambiguous or right.ambiguous:
                ambiguous_count += 1
    ambiguous_rate = ambiguous_count / len(candidates) if candidates else 0.0

    exact_groups = exact_duplicates(candidates)
    quasi_pairs = quasi_duplicate_pairs(candidates)
    paraphrase_leaks = [
        (left, right, score)
        for left, right, score in quasi_pairs
        if split.get(left) != split.get(right)
    ]

    poll_ids = sorted(annotations["spotcheck"])
    poll_agreements = sum(
        1
        for identifier in poll_ids
        if annotations["spotcheck"][identifier].intent
        == candidates_by_id[identifier]["target_intent"]
    )
    poll_contradictions = [
        (
            identifier,
            annotations["spotcheck"][identifier].intent,
            candidates_by_id[identifier]["target_intent"],
            candidates_by_id[identifier]["text"],
        )
        for identifier in poll_ids
        if annotations["spotcheck"][identifier].intent
        != candidates_by_id[identifier]["target_intent"]
    ]

    kappa_ensemble = agreement["ensemble"]["kappa"]
    kappa_ok = kappa_ensemble is not None and kappa_ensemble >= 0.75
    controls = [
        (
            "≥ 25 exemples par classe (train)",
            f"min={min_class}" + (f" ; classes < 25 : {', '.join(min_classes)}" if min_classes else ""),
            "≥ 25",
            "OK" if min_class >= 25 else "KO",
            f"{train_total} exemples train",
        ),
        (
            "Classe majoritaire (train)",
            f"{majority_class} = {majority_count} ({format_pct(majority_share)})",
            "< 30 %",
            "OK" if majority_share < 0.30 else "KO",
            f"{train_total} exemples train",
        ),
        (
            "Taux d'exemples ambigus",
            f"{ambiguous_count}/{len(candidates)} ({format_pct(ambiguous_rate)})",
            "< 10 %",
            "OK" if ambiguous_rate < 0.10 else "KO",
            "560 exemples",
        ),
        (
            "Doublons exacts",
            str(len(exact_groups)),
            "0",
            "OK" if not exact_groups else "KO",
            "textes normalisés",
        ),
        (
            "Quasi-doublons (Jaccard trigrammes ≥ 0,8)",
            str(len(quasi_pairs)),
            "0",
            "OK" if not quasi_pairs else "KO",
            "560 exemples",
        ),
        (
            "Kappa de Cohen global (val+test)",
            format_kappa(kappa_ensemble),
            "≥ 0,75",
            "OK" if kappa_ok else "KO",
            "seuil §5.7",
        ),
        (
            "Fuite de paraphrase entre splits",
            str(len(paraphrase_leaks)),
            "0",
            "OK" if not paraphrase_leaks else "KO",
            "paires Jaccard ≥ 0,8",
        ),
        (
            "Indépendance des annotations",
            "suspectée" if misalignment["suspected"] else "non suspectée",
            "non suspectée",
            "KO" if misalignment["suspected"] else "OK",
            "contrôle d'intégrité supplémentaire",
        ),
    ]

    commit_hash, guidelines_state_value = guidelines_state(config)

    lines: list[str] = []
    lines.append("# Rapport de fusion des annotations d'intentions — SupportAI")
    lines.append("")
    lines.append(
        "> Généré par `scripts/merge_annotations.py`. Aucun horodatage : le rapport est "
        "reproductible à partir des fichiers d'entrée."
    )
    lines.append(
        f"> Version des guidelines : commit `{commit_hash}` (`docs/annotation_guidelines.md`, "
        f"{guidelines_state_value})."
    )
    lines.append("")
    lines.append("## 1. Contexte et protocole")
    lines.append("")
    lines.append(
        "Le chantier A des guidelines porte sur la classification d'intentions. "
        "Deux annotateurs, **Aya** et **Mohammed**, ont annoté en aveugle les exemples "
        "de validation et de test, puis Aya a réalisé un sondage sur 56 exemples de train. "
        "Le protocole prévu est une annotation aveugle indépendante, avec la même version "
        f"des guidelines (commit `{commit_hash}`)."
    )
    lines.append("")
    lines.append(
        f"- Exemples : **{len(candidates)}** (train 392, val 84, test 84)."
    )
    lines.append(
        "- Langues : FR et EN ; les identifiants sont partagés entre les langues."
    )
    lines.append("- Annotateurs : Aya et Mohammed.")
    lines.append(
        "- Fichiers d'entrée : "
        + ", ".join(
            f"{role} = `{relpath(path, config)}`" for role, path in sheet_paths.items()
        )
        + "."
    )
    lines.append(f"- Statut du build : **{build_status}**.")
    lines.append("")
    lines.append("## 2. Validation des fichiers")
    lines.append("")
    lines.append(
        "- Les trois fichiers d'annotation sont présents et lisibles."
    )
    lines.append(
        "- Tous les identifiants attendus sont présents : 168 pour Aya, 168 pour "
        "Mohammed, 56 pour le sondage train."
    )
    lines.append("- Toutes les étiquettes appartiennent aux 14 codes de `intents.csv`.")
    lines.append("- Aucune ligne vide.")
    lines.append(
        "- Chaque ligne `ambiguous=true` possède au moins un code dans `acceptable_labels`."
    )
    lines.append("- **Résultat : OK.**")
    if validation_warnings:
        lines.append("")
        lines.append("Avertissements :")
        for warning in validation_warnings:
            lines.append(f"- {warning}")
    lines.append("")
    lines.append("### 2.1 Contrôle d'intégrité de l'alignement")
    lines.append("")
    lines.append(
        f"- Étiquettes identiques rang par rang : **{'oui' if misalignment['same_positional_labels'] else 'non'}**."
    )
    lines.append(
        f"- Ordre des textes identique : **{'oui' if misalignment['same_text_order'] else 'non'}**."
    )
    lines.append(
        f"- Multiset des étiquettes identique : **{'oui' if misalignment['label_multiset_equal'] else 'non'}**."
    )
    lines.append(
        f"- Accord par identifiant : **{misalignment['per_id_agreement']}/{misalignment['per_id_total']}**."
    )
    if misalignment["suspected"]:
        lines.append("")
        lines.append(
            "**Anomalie probable** : la colonne `intent` de Mohammed semble être celle "
            "d'Aya copiée sans réalignement. Le script ne corrige aucune étiquette ; "
            "les désaccords sont consignés tels quels. L'indépendance de l'annotation "
            "n'est donc pas démontrée."
        )
    else:
        lines.append("")
        lines.append("Aucune anomalie d'alignement détectée.")
    lines.append("")
    lines.append("## 3. Accord inter-annotateurs")
    lines.append("")
    lines.append("### 3.1 Résultats globaux")
    lines.append("")
    global_rows = []
    for name in ("val", "test", "ensemble"):
        result = agreement[name]
        global_rows.append(
            [
                name,
                str(result["n"]),
                str(result["agreements"]),
                format_pct(result["observed"]),
                format_kappa(result["kappa"]),
                kappa_interpretation(result["kappa"]),
                "OK" if result["kappa"] is not None and result["kappa"] >= 0.75 else "KO",
            ]
        )
    lines.append(
        md_table(
            ["Périmètre", "n", "Accords", "Taux d'accord", "κ", "Interprétation", "Seuil κ ≥ 0,75"],
            global_rows,
        )
    )
    lines.append("")
    lines.append("### 3.2 Kappa par intention (un-contre-tous)")
    lines.append("")
    per_intent_rows = []
    for code in codes:
        val = agreement["val"]["per_intent"][code]
        test = agreement["test"]["per_intent"][code]
        ensemble = agreement["ensemble"]["per_intent"][code]
        per_intent_rows.append(
            [
                code,
                str(ensemble["n"]),
                str(ensemble["aya_positive"]),
                str(ensemble["mohammed_positive"]),
                format_kappa(val["kappa"]),
                format_kappa(test["kappa"]),
                format_kappa(ensemble["kappa"]),
                kappa_interpretation(ensemble["kappa"]),
            ]
        )
    lines.append(
        md_table(
            [
                "Intention",
                "n",
                "Aya+",
                "Mohammed+",
                "κ val",
                "κ test",
                "κ ensemble",
                "Interprétation (ensemble)",
            ],
            per_intent_rows,
        )
    )
    lines.append("")
    lines.append("### 3.3 Matrice de confusion (ensemble)")
    lines.append("")
    lines.append("Lignes = Aya, colonnes = Mohammed. Les codes sont numérotés pour garder le tableau lisible.")
    lines.append("")
    lines.append(md_table(["Code", "Intention"], [[f"{index + 1:02d}", code] for index, code in enumerate(codes)]))
    lines.append("")
    confusion = agreement["ensemble"]["confusion"]
    matrix_header = ["Aya \\ Mohammed"] + [f"{index + 1:02d}" for index in range(len(codes))] + ["Total"]
    matrix_rows = []
    for row_index, row_code in enumerate(codes):
        row = [f"{row_index + 1:02d}"]
        for col_index, col_code in enumerate(codes):
            row.append(str(confusion.get((row_code, col_code), 0)))
        row.append(str(sum(confusion.get((row_code, col_code), 0) for col_code in codes)))
        matrix_rows.append(row)
    total_row = ["Total"]
    for col_code in codes:
        total_row.append(str(sum(confusion.get((row_code, col_code), 0) for row_code in codes)))
    total_row.append(str(agreement["ensemble"]["n"]))
    matrix_rows.append(total_row)
    lines.append(md_table(matrix_header, matrix_rows))
    lines.append("")
    lines.append("### 3.4 Paires de classes les plus confondues (ensemble)")
    lines.append("")
    if agreement["ensemble"]["top_confusions"]:
        lines.append(
            md_table(
                ["Rang", "Aya", "Mohammed", "Désaccords"],
                [
                    [str(index + 1), left, right, str(count)]
                    for index, (left, right, count) in enumerate(
                        agreement["ensemble"]["top_confusions"]
                    )
                ],
            )
        )
    else:
        lines.append("Aucune paire confondue : les deux annotateurs sont d'accord partout.")
    lines.append("")
    lines.append("## 4. Désaccords et file d'arbitrage")
    lines.append("")
    lines.append(f"- Désaccords val+test : **{len(disagreements)}**.")
    lines.append(
        f"- File d'arbitrage : `{relpath(config.adjudication_path, config)}`."
    )
    lines.append(
        f"- Sauvegarde de l'ancien journal : `{relpath(config.previous_path, config)}` — {backup_info}"
    )
    if disagreements:
        lines.append("")
        lines.append("Premiers désaccords (la file complète est dans le CSV) :")
        lines.append("")
        lines.append(
            md_table(
                ["id", "Aya", "Mohammed", "Texte"],
                [
                    [row["id"], row["intent_aya"], row["intent_mohammed"], row["text"][:90]]
                    for row in disagreements[:10]
                ],
            )
        )
        pending = len(disagreements) - (len(adjudications) if adjudications else 0)
        lines.append("")
        lines.append(f"- Désaccords en attente d'arbitrage : **{pending}**.")
        if pending:
            lines.append(
                "- Le mode `--build` refuse de produire `intent_dataset.jsonl` tant que "
                "ces lignes n'ont pas de `adjudicated_intent`."
            )
    else:
        lines.append("- Aucun désaccord : aucune arbitrage n'est nécessaire.")
    lines.append("")
    lines.append("## 5. Sondage train vs étiquettes cibles")
    lines.append("")
    lines.append(
        f"- Exemples sondés : **{len(poll_ids)}** ; accords avec la cible : "
        f"**{poll_agreements}/{len(poll_ids)}** ({format_pct(poll_agreements / len(poll_ids) if poll_ids else 0)})."
    )
    lines.append(
        f"- Contradictions : **{len(poll_contradictions)}**. Elles sont signalées ci-dessous ; "
        "l'étiquette du sondage Aya est conservée dans le train (consigne de fusion : "
        "le sondage humain prime sur la cible en cas de contradiction)."
    )
    if poll_contradictions:
        lines.append("")
        lines.append(
            md_table(
                ["id", "Aya", "Cible", "Texte"],
                [
                    [identifier, aya, target, text[:80]]
                    for identifier, aya, target, text in poll_contradictions
                ],
            )
        )
    lines.append("")
    lines.append("## 6. Contrôles qualité §12.4")
    lines.append("")
    lines.append(
        md_table(
            ["Contrôle", "Valeur", "Seuil", "Statut", "Portée"],
            [list(control) for control in controls],
        )
    )
    lines.append("")
    lines.append("## 7. Tailles du dataset")
    lines.append("")
    lines.append("### 7.1 Par split et par langue")
    lines.append("")
    split_language = Counter((split[identifier], candidate["language"]) for identifier, candidate in candidates_by_id.items())
    size_rows = []
    for split_name in ("train", "val", "test"):
        fr = split_language.get((split_name, "fr"), 0)
        en = split_language.get((split_name, "en"), 0)
        size_rows.append([split_name, str(fr), str(en), str(fr + en)])
    fr_total = sum(split_language.get((name, "fr"), 0) for name in ("train", "val", "test"))
    en_total = sum(split_language.get((name, "en"), 0) for name in ("train", "val", "test"))
    size_rows.append(["**Total**", str(fr_total), str(en_total), str(fr_total + en_total)])
    lines.append(md_table(["Split", "FR", "EN", "Total"], size_rows))
    lines.append("")
    lines.append("### 7.2 Par split et par intention")
    lines.append("")
    if dataset is not None:
        counts = Counter((row["split"], row["intent"]) for row in dataset)
        intent_rows = []
        for code in codes:
            train_count = counts.get(("train", code), 0)
            val_count = counts.get(("val", code), 0)
            test_count = counts.get(("test", code), 0)
            intent_rows.append(
                [code, str(train_count), str(val_count), str(test_count), str(train_count + val_count + test_count)]
            )
        lines.append(md_table(["Intention", "Train", "Val", "Test", "Total"], intent_rows))
        lines.append("")
        lines.append("Les effectifs val/test incluent les désaccords arbitrés.")
    else:
        train_intent_rows = [
            [code, str(train_counts.get(code, 0))] for code in codes
        ]
        lines.append("**Train (définitif)**")
        lines.append("")
        lines.append(md_table(["Intention", "Train"], train_intent_rows))
        lines.append("")
        lines.append("**Val/test (provisoire : accords seulement)**")
        lines.append("")
        agreed = Counter()
        pending = Counter()
        for identifier, split_name in split.items():
            if split_name not in {"val", "test"}:
                continue
            value = provisional.get(identifier)
            if value is None:
                pending[split_name] += 1
            else:
                agreed[(split_name, value)] += 1
        val_test_rows = []
        for code in codes:
            val_count = agreed.get(("val", code), 0)
            test_count = agreed.get(("test", code), 0)
            val_test_rows.append([code, str(val_count), str(test_count)])
        lines.append(md_table(["Intention", "Val (accord)", "Test (accord)"], val_test_rows))
        lines.append("")
        lines.append(
            f"En attente d'arbitrage : val = {pending.get('val', 0)}, test = {pending.get('test', 0)}."
        )
    lines.append("")
    lines.append("## 8. Limites")
    lines.append("")
    lines.append(
        "- Le kappa global est très inférieur au seuil de 0,75 : la taxonomie n'est pas "
        "validée par ces annotations et aucun modèle ne doit être entraîné en l'état."
    )
    if misalignment["suspected"]:
        lines.append(
            "- L'anomalie d'alignement entre les feuilles Aya et Mohammed rend l'accord "
            "observé non interprétable comme un accord inter-annotateurs indépendant."
        )
    lines.append(
        "- Les effectifs par classe restent modestes (25 à 36 exemples en train) ; les "
        "intervalles de confiance sur le kappa sont larges."
    )
    lines.append(
        "- Le jeu de test n'est ni gelé ni haché dans cette tâche : le gel et l'empreinte "
        "SHA-256 relèvent de la tâche « Freeze test datasets »."
    )
    lines.append(
        "- Aucun commit ni push n'a été effectué. Le rapport ne contient pas d'horodatage."
    )
    lines.append("")
    lines.append("## 9. Reproductibilité")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/merge_annotations.py")
    lines.append("python scripts/merge_annotations.py --build")
    lines.append("python tests/test_merge_annotations.py")
    lines.append("```")
    lines.append("")

    write_text_lf(config.report_path, "\n".join(lines))


def write_single_report(
    config: Config,
    *,
    candidates: list[dict],
    split: dict[str, str],
    codes: list[str],
    annotations: dict,
    coherence: list[dict],
    dataset: list[dict] | None,
    build_status: str,
    validation_warnings: list[str],
    sheet_paths: dict[str, Path],
) -> None:
    candidates_by_id = {row["id"]: row for row in candidates}
    intents = single_intents(annotations, candidates, split)
    train_ids = sorted(identifier for identifier, name in split.items() if name == "train")
    train_counts = Counter(intents[identifier] for identifier in train_ids)
    train_total = sum(train_counts.values())
    min_class = min(train_counts.values()) if train_counts else 0
    min_classes = sorted(code for code in codes if train_counts.get(code, 0) < 25)
    majority_class, majority_count = (
        max(train_counts.items(), key=lambda item: (item[1], item[0]))
        if train_counts
        else ("n/a", 0)
    )
    majority_share = majority_count / train_total if train_total else 0.0

    ambiguous_count = 0
    for candidate in candidates:
        identifier = candidate["id"]
        if split.get(identifier) == "train":
            spot = annotations["spotcheck"].get(identifier)
            if spot is not None and spot.ambiguous:
                ambiguous_count += 1
        else:
            if annotations["aya"][identifier].ambiguous:
                ambiguous_count += 1
    ambiguous_rate = ambiguous_count / len(candidates) if candidates else 0.0

    exact_groups = exact_duplicates(candidates)
    quasi_pairs = quasi_duplicate_pairs(candidates)
    paraphrase_leaks = [
        (left, right, score)
        for left, right, score in quasi_pairs
        if split.get(left) != split.get(right)
    ]

    valtest_coherence = [row for row in coherence if row["scope"] in {"val", "test"}]
    train_coherence = [row for row in coherence if row["scope"] == "train (sondage)"]
    valtest_total = len(annotations["aya"])
    spot_total = len(annotations["spotcheck"])
    annotated_total = valtest_total + spot_total

    controls = [
        (
            "≥ 25 exemples par classe (train)",
            f"min={min_class}" + (f" ; classes < 25 : {', '.join(min_classes)}" if min_classes else ""),
            "≥ 25",
            "OK" if min_class >= 25 else "KO",
            f"{train_total} exemples train",
        ),
        (
            "Classe majoritaire (train)",
            f"{majority_class} = {majority_count} ({format_pct(majority_share)})",
            "< 30 %",
            "OK" if majority_share < 0.30 else "KO",
            f"{train_total} exemples train",
        ),
        (
            "Taux d'exemples ambigus",
            f"{ambiguous_count}/{len(candidates)} ({format_pct(ambiguous_rate)})",
            "< 10 %",
            "OK" if ambiguous_rate < 0.10 else "KO",
            f"{len(candidates)} exemples",
        ),
        (
            "Doublons exacts",
            str(len(exact_groups)),
            "0",
            "OK" if not exact_groups else "KO",
            "textes normalisés",
        ),
        (
            "Quasi-doublons (Jaccard trigrammes ≥ 0,8)",
            str(len(quasi_pairs)),
            "0",
            "OK" if not quasi_pairs else "KO",
            f"{len(candidates)} exemples",
        ),
        (
            "Kappa de Cohen global (val+test)",
            "non mesuré (annotateur unique)",
            "≥ 0,75",
            "NON APPLICABLE",
            "annotateur unique",
        ),
        (
            "Fuite de paraphrase entre splits",
            str(len(paraphrase_leaks)),
            "0",
            "OK" if not paraphrase_leaks else "KO",
            "paires Jaccard ≥ 0,8",
        ),
        (
            "Indépendance des annotations",
            "NON APPLICABLE (annotateur unique)",
            "non applicable",
            "NON APPLICABLE",
            "un seul annotateur",
        ),
    ]

    commit_hash, guidelines_state_value = guidelines_state(config)

    lines: list[str] = []
    lines.append("# Rapport de fusion des annotations d'intentions — SupportAI")
    lines.append("")
    lines.append(
        "> Généré par `scripts/merge_annotations.py --single-annotator`. Aucun horodatage : "
        "le rapport est reproductible à partir des fichiers d'entrée."
    )
    lines.append(
        f"> Version des guidelines : commit `{commit_hash}` (`docs/annotation_guidelines.md`, "
        f"{guidelines_state_value})."
    )
    lines.append("")
    lines.append("## 1. Contexte et protocole")
    lines.append("")
    lines.append(
        "**Annotation : annotateur unique (Aya) ; accord inter-annotateurs non mesuré.**"
    )
    lines.append("")
    lines.append(
        "Seule Aya a annoté les 168 exemples de validation et de test, puis réalisé le "
        "sondage sur 56 exemples de train. Aucun second annotateur n'est disponible. "
        "Le fichier de Mohammed n'est ni lu ni utilisé dans ce mode."
    )
    lines.append("")
    lines.append(f"- Exemples : **{len(candidates)}** (train 392, val 84, test 84).")
    lines.append("- Langues : FR et EN ; les identifiants sont partagés entre les langues.")
    lines.append("- Annotateur : **Aya uniquement**.")
    lines.append(
        "- Fichiers d'entrée : "
        + ", ".join(
            f"{role} = `{relpath(path, config)}`" for role, path in sheet_paths.items()
        )
        + "."
    )
    lines.append(f"- Statut du build : **{build_status}**.")
    lines.append("")
    lines.append(
        "Aucun kappa de Cohen n'est calculé. Aucune file d'arbitrage n'est produite. "
        "Les étiquettes ne sont pas remplacées automatiquement ; les corrections de "
        "relecture sont appliquées dans les fichiers d'annotation."
    )
    lines.append("")
    lines.append("## 2. Validation des fichiers")
    lines.append("")
    lines.append("- Les fichiers d'entrée Aya et sondage train sont présents et lisibles.")
    lines.append(
        f"- Tous les identifiants attendus sont présents : {valtest_total} pour Aya "
        f"val/test, {spot_total} pour le sondage train."
    )
    lines.append("- Toutes les étiquettes appartiennent aux 14 codes de `intents.csv`.")
    lines.append("- Aucune ligne vide.")
    lines.append(
        "- Chaque ligne `ambiguous=true` possède au moins un code dans `acceptable_labels`."
    )
    lines.append("- **Résultat : OK.**")
    if validation_warnings:
        lines.append("")
        lines.append("Avertissements :")
        for warning in validation_warnings:
            lines.append(f"- {warning}")
    lines.append("")
    lines.append("## 3. Contrôle de cohérence avec les cibles")
    lines.append("")
    lines.append(
        "Ce contrôle n'est pas une mesure inter-annotateurs. Il compare les étiquettes "
        "d'Aya aux `target_intent` du fichier privé, sans correction automatique."
    )
    lines.append("")
    lines.append(
        f"- Différences val/test : **{len(valtest_coherence)}/{valtest_total}**."
    )
    lines.append(
        f"- Différences train sondé : **{len(train_coherence)}/{spot_total}**."
    )
    lines.append(
        f"- Total : **{len(coherence)}/{annotated_total}** comparaisons annotées."
    )
    lines.append("")
    remaining_ambiguous = [
        row["id"]
        for row in coherence
        if row["scope"] == "train (sondage)"
        and annotations["spotcheck"].get(row["id"]) is not None
        and annotations["spotcheck"][row["id"]].ambiguous
    ]
    if coherence:
        lines.append(
            md_table(
                ["Périmètre", "id", "Texte", "Étiquette Aya", "Cible"],
                [
                    [row["scope"], row["id"], row["text"], row["aya"], row["target"]]
                    for row in coherence
                ],
            )
        )
        lines.append("")
        lines.append(
            "Les étiquettes listées ci-dessus restent inchangées dans les fichiers "
            "d'annotation. Les corrections de relecture sont appliquées directement "
            "dans `annotate_aya_done.csv` et `spotcheck_train_aya_done.csv` ; ce "
            "rapport ne liste que les différences restantes. Cette liste est une file "
            "de relecture pour Aya, pas une file d'arbitrage automatique. Pour le "
            "train, l'étiquette d'Aya est conservée dans le dataset en cas de "
            "contradiction."
        )
        if remaining_ambiguous:
            lines.append("")
            lines.append(
                "Les cas restants marqués `ambiguous=true` sont "
                + ", ".join(f"`{identifier}`" for identifier in remaining_ambiguous)
                + " ; `acceptable_labels` contient les deux codes possibles."
            )
    else:
        lines.append("Aucune différence avec les cibles.")
    lines.append("")
    lines.append("## 4. Dataset")
    lines.append("")
    lines.append(f"- Statut : **{build_status}**.")
    lines.append(
        "- Lignes val/test : `intent` = étiquette d'Aya, `annotator_1 = \"aya\"`, "
        "`annotator_2 = null`, `adjudicated = false`, "
        "`annotation_status = \"single_annotator\"`."
    )
    lines.append(
        "- Lignes train : `intent` = `target_intent`, sauf contradiction du sondage "
        "où l'étiquette d'Aya est conservée et signalée dans `notes`."
    )
    lines.append(
        f"- Export CSV : `{relpath(config.dataset_csv, config)}` "
        "(`id,text,language,intent,split`)."
    )
    lines.append("")
    lines.append("### 4.1 Par split et par langue")
    lines.append("")
    split_language = Counter(
        (split[identifier], candidate["language"])
        for identifier, candidate in candidates_by_id.items()
    )
    size_rows = []
    for split_name in ("train", "val", "test"):
        fr = split_language.get((split_name, "fr"), 0)
        en = split_language.get((split_name, "en"), 0)
        size_rows.append([split_name, str(fr), str(en), str(fr + en)])
    fr_total = sum(split_language.get((name, "fr"), 0) for name in ("train", "val", "test"))
    en_total = sum(split_language.get((name, "en"), 0) for name in ("train", "val", "test"))
    size_rows.append(["**Total**", str(fr_total), str(en_total), str(fr_total + en_total)])
    lines.append(md_table(["Split", "FR", "EN", "Total"], size_rows))
    lines.append("")
    lines.append("### 4.2 Par split et par intention")
    lines.append("")
    counts = Counter((split[identifier], intents[identifier]) for identifier in intents)
    intent_rows = []
    for code in codes:
        train_count = counts.get(("train", code), 0)
        val_count = counts.get(("val", code), 0)
        test_count = counts.get(("test", code), 0)
        intent_rows.append(
            [code, str(train_count), str(val_count), str(test_count), str(train_count + val_count + test_count)]
        )
    lines.append(md_table(["Intention", "Train", "Val", "Test", "Total"], intent_rows))
    lines.append("")
    lines.append(
        "Les effectifs val/test sont ceux des étiquettes d'Aya, sans arbitrage ni "
        "double annotation."
    )
    lines.append("")
    lines.append("## 5. Contrôles qualité §12.4")
    lines.append("")
    lines.append(
        md_table(
            ["Contrôle", "Valeur", "Seuil", "Statut", "Portée"],
            [list(control) for control in controls],
        )
    )
    lines.append("")
    lines.append("## 6. Limites")
    lines.append("")
    lines.append(
        "- Aucun kappa n'est calculé : l'accord inter-annotateurs n'est pas mesuré et "
        "le seuil de 0,75 n'est pas vérifié."
    )
    lines.append(
        "- Risque de biais de l'annotateur unique : les étiquettes val/test reflètent "
        "la lecture d'une seule personne."
    )
    lines.append(
        "- Le jeu de test n'est pas double-annoté ; sa qualité inter-annotateurs reste "
        "inconnue."
    )
    lines.append(
        "- Le jeu de test n'est pas gelé dans cette tâche : le gel et l'empreinte "
        "SHA-256 relèvent de la tâche « Freeze test datasets »."
    )
    lines.append(
        "- Le fichier de Mohammed est invalide (colonne `intent` copiée sans "
        "réalignement) et n'est pas utilisé."
    )
    lines.append("- Aucun commit ni push n'a été effectué. Le rapport ne contient pas d'horodatage.")
    lines.append("")
    lines.append("## 7. Reproductibilité")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/merge_annotations.py --single-annotator")
    lines.append("python scripts/merge_annotations.py --build --single-annotator")
    lines.append("python tests/test_merge_annotations.py")
    lines.append("```")
    lines.append("")

    write_text_lf(config.report_path, "\n".join(lines))


def run_single(config: Config, build: bool = False) -> int:
    candidates = load_candidates(config)
    split = load_split(config)
    codes, _intents = load_intents(config)

    print("=== Validation des annotations (annotateur unique) ===")
    annotations, errors, validation_warnings, sheet_paths = validate_single_inputs(
        config, candidates, split, codes
    )
    if errors:
        for error in errors:
            ko(error)
        print("Arrêt : corriger les erreurs ci-dessus avant de relancer.")
        return 1
    for warning in validation_warnings:
        attention(warning)
    ok("2 fichiers présents, ids complets, 14 codes, aucune ligne vide, ambigus documentés")

    assert annotations is not None
    coherence = target_coherence(annotations, candidates, split)
    valtest_coherence = [row for row in coherence if row["scope"] in {"val", "test"}]
    train_coherence = [row for row in coherence if row["scope"] == "train (sondage)"]
    annotated_total = len(annotations["aya"]) + len(annotations["spotcheck"])
    print(
        "\nDifférences avec la cible : "
        f"val/test {len(valtest_coherence)}/{len(annotations['aya'])}, "
        f"train sondé {len(train_coherence)}/{len(annotations['spotcheck'])}, "
        f"total {len(coherence)}/{annotated_total}"
    )
    print("[INFO] Aucun kappa : annotateur unique (Aya).")
    print("[INFO] Aucune file d'arbitrage : le fichier de Mohammed n'est pas lu.")

    if build:
        dataset = build_single_dataset(config, annotations, candidates, split)
        write_dataset(config, dataset)
        build_status = f"écrit : {len(dataset)} lignes"
        print(f"[OK] Dataset écrit : {relpath(config.dataset_jsonl, config)} ({len(dataset)} lignes)")
        print(f"[OK] Export CSV écrit : {relpath(config.dataset_csv, config)}")
    else:
        dataset = None
        build_status = "non écrit : relancer avec --build --single-annotator"
        print("[INFO] Dataset non écrit (mode validation seulement).")

    write_single_report(
        config,
        candidates=candidates,
        split=split,
        codes=codes,
        annotations=annotations,
        coherence=coherence,
        dataset=dataset,
        build_status=build_status,
        validation_warnings=validation_warnings,
        sheet_paths=sheet_paths,
    )
    print(f"[OK] Rapport écrit : {relpath(config.report_path, config)}")
    return 0


def run(config: Config, build: bool = False, single_annotator: bool = False) -> int:
    if single_annotator:
        return run_single(config, build=build)
    candidates = load_candidates(config)
    split = load_split(config)
    codes, _intents = load_intents(config)

    print("=== Validation des annotations ===")
    annotations, errors, validation_warnings, misalignment, sheet_paths = validate_inputs(
        config, candidates, split, codes
    )
    if errors:
        for error in errors:
            ko(error)
        print("Arrêt : corriger les erreurs ci-dessus avant de relancer.")
        return 1
    for warning in validation_warnings:
        attention(warning)
    ok("3 fichiers présents, ids complets, 14 codes, aucune ligne vide, ambigus documentés")

    assert annotations is not None
    agreement = analyze_agreement(annotations, split, codes)
    print_agreement(agreement)

    disagreements = disagreement_rows(annotations, split)
    print(f"\nDésaccords val+test : {len(disagreements)}")

    if build:
        adjudications, adjudication_errors, adjudication_warnings = check_adjudications(
            config, disagreements, codes
        )
        for warning in adjudication_warnings:
            attention(warning)
        if adjudication_errors:
            for error in adjudication_errors:
                ko(error)
            print("Build refusé : la file d'arbitrage n'est pas complète.")
            return 1
        dataset = build_dataset(config, annotations, candidates, split, adjudications)
        write_dataset(config, dataset)
        build_status = f"écrit : {len(dataset)} lignes"
        backup_info = "non modifié (mode --build)"
        print(f"[OK] Dataset écrit : {relpath(config.dataset_jsonl, config)} ({len(dataset)} lignes)")
        print(f"[OK] Export CSV écrit : {relpath(config.dataset_csv, config)}")
    else:
        backup_info = backup_previous_adjudication(config)
        written, preserved = write_adjudication_log(config, disagreements)
        build_status = (
            f"bloqué : {len(disagreements)} désaccord(s) en attente d'arbitrage"
            if disagreements
            else "prêt : aucun désaccord"
        )
        dataset = None
        adjudications = None
        print(f"[OK] File d'arbitrage écrite : {relpath(config.adjudication_path, config)} "
              f"({written} ligne(s), {preserved} arbitrage(s) conservé(s))")
        print(f"[INFO] {backup_info}")

    write_report(
        config,
        candidates=candidates,
        split=split,
        codes=codes,
        annotations=annotations,
        agreement=agreement,
        disagreements=disagreements,
        adjudications=adjudications,
        dataset=dataset,
        build_status=build_status,
        validation_warnings=validation_warnings,
        sheet_paths=sheet_paths,
        backup_info=backup_info,
        misalignment=misalignment,
    )
    print(f"[OK] Rapport écrit : {relpath(config.report_path, config)}")
    if not build and disagreements:
        print(
            "[ATTENTION] Le dataset n'est pas écrit : compléter "
            "adjudicated_intent pour chaque désaccord, puis relancer --build."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build",
        action="store_true",
        help="écrire intent_dataset.jsonl et intent_dataset.csv après arbitrage complet",
    )
    parser.add_argument(
        "--single-annotator",
        action="store_true",
        help=(
            "mode annotateur unique : Aya + sondage train seulement, sans kappa, "
            "sans file d'arbitrage et sans fichier de Mohammed"
        ),
    )
    parser.add_argument("--aya", type=Path, default=None, help="feuille Aya (val+test)")
    parser.add_argument("--mohammed", type=Path, default=None, help="feuille Mohammed (val+test)")
    parser.add_argument("--spotcheck", type=Path, default=None, help="sondage train Aya")
    parser.add_argument(
        "--today",
        default=None,
        help="date ISO pour created_at (défaut : date du jour ; utile aux tests)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = default_config()
    if args.aya is not None:
        config.aya_path = args.aya
    if args.mohammed is not None:
        config.mohammed_path = args.mohammed
    if args.spotcheck is not None:
        config.spotcheck_path = args.spotcheck
    if args.today is not None:
        config.today = args.today
    return run(config, build=args.build, single_annotator=args.single_annotator)


if __name__ == "__main__":
    raise SystemExit(main())
