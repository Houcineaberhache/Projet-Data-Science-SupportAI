#!/usr/bin/env python3
"""Préparer et contrôler le dataset d'intentions SupportAI (Tâche A).

Sous-commandes :
    validate  vérifie les 560 questions candidates ;
    split     écrit le découpage train/val/test stratifié ;
    sheets    écrit les feuilles d'annotation aveugles.

Le script n'écrit aucune étiquette humaine : les colonnes d'annotation des
feuilles restent vides.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "data" / "annotations" / "_private" / "intent_candidates.jsonl"
SPLIT_PATH = ROOT / "data" / "annotations" / "_private" / "intent_split.csv"
BLIND_DIR = ROOT / "data" / "annotations" / "blind"
INTENTS_PATH = ROOT / "data" / "annotations" / "intents.csv"
PILOT_PATH = ROOT / "data" / "annotations" / "pilot_20_annotation_sheet.csv"
GUIDELINES_PATH = ROOT / "docs" / "annotation_guidelines.md"

SEED = 42
EXPECTED_TOTAL = 560
EXPECTED_PER_INTENT = 40
EXPECTED_FR = 24
EXPECTED_EN = 16
ANNOTATION_COLUMNS = ["id", "language", "text", "intent", "ambiguous", "acceptable_labels", "notes"]
ANNOTATION_EMPTY_COLUMNS = ["intent", "ambiguous", "acceptable_labels", "notes"]
SPLIT_COLUMNS = ["id", "split"]

FR_STOP = {
    "je", "j", "ai", "ma", "mon", "mes", "me", "moi", "le", "la", "les", "un", "une", "des",
    "du", "de", "d", "est", "sont", "etre", "que", "qui", "quoi", "comment", "pourquoi", "quand",
    "ou", "et", "avec", "pour", "pas", "plus", "sur", "dans", "au", "aux", "ce", "cette", "ces",
    "cet", "il", "elle", "nous", "vous", "ils", "elles", "suis", "veux", "voudrais", "peux", "puis",
    "fait", "faire", "commande", "colis", "produit", "remboursement", "livraison", "garantie",
    "paiement", "compte", "donnees", "bonjour", "merci", "svp", "s'il", "vous", "votre", "vos",
    "notre", "nos", "chez", "sans", "sous", "apres", "avant", "depuis", "toujours", "encore",
    "bien", "tres", "tout", "tous", "toute", "toutes", "quel", "quelle", "quels", "quelles",
}

EN_STOP = {
    "i", "my", "me", "we", "our", "you", "your", "he", "she", "it", "they", "their", "the", "a",
    "an", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "can", "could", "would", "should", "will", "do", "does", "did", "have", "has", "had", "not",
    "no", "yes", "where", "when", "why", "how", "what", "who", "which", "and", "or", "with", "for",
    "on", "in", "to", "of", "from", "at", "by", "about", "please", "order", "parcel", "package",
    "product", "refund", "delivery", "warranty", "payment", "account", "data", "hello", "thanks",
    "thank", "want", "need", "still", "now", "today", "after", "before", "since", "because",
}


def fail(message: str) -> None:
    print(f"[KO] {message}")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def tokenize(text: str) -> list[str]:
    """Tokenise pour les contrôles de similarité, sans accents ni ponctuation."""
    text = text.lower().replace("’", "'").replace("œ", "oe").replace("æ", "ae")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", text)


def ngrams(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def jaccard(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Fichier absent : {path.relative_to(ROOT)}")
    rows = []
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


def read_intents() -> dict[str, dict[str, str]]:
    with INTENTS_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return {row["intent_id"]: row for row in csv.DictReader(handle)}


def read_pilot_ids() -> set[str]:
    if not PILOT_PATH.exists():
        return set()
    with PILOT_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return {row["id"] for row in csv.DictReader(handle)}


def language_scores(text: str) -> tuple[int, int]:
    tokens = tokenize(text)
    fr_score = sum(1 for token in tokens if token in FR_STOP)
    en_score = sum(1 for token in tokens if token in EN_STOP)
    return fr_score, en_score


def language_plausible(text: str, language: str) -> bool:
    fr_score, en_score = language_scores(text)
    if language == "fr":
        return fr_score > 0 and fr_score >= en_score
    if language == "en":
        return en_score > 0 and en_score >= fr_score
    return False


def has_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text))


def reference_ngrams(intents: dict[str, dict[str, str]]) -> set[tuple[str, ...]]:
    references = set()
    for row in intents.values():
        for field in ("example_1_fr", "example_1_en", "example_2_fr", "example_2_en"):
            references |= ngrams(tokenize(row.get(field, "")), 6)
    guidelines = GUIDELINES_PATH.read_text(encoding="utf-8")
    references |= ngrams(tokenize(guidelines), 6)
    return references


def quasi_duplicate_pairs(rows: list[dict], threshold: float = 0.8) -> list[tuple[str, str, float]]:
    token_sets = {row["id"]: ngrams(tokenize(row["text"]), 3) for row in rows}
    pairs = []
    for left, right in combinations(rows, 2):
        score = jaccard(token_sets[left["id"]], token_sets[right["id"]])
        if score >= threshold:
            pairs.append((left["id"], right["id"], score))
    return pairs


def validate_candidates(rows: list[dict], intents: dict[str, dict[str, str]]) -> bool:
    valid = True
    expected_fields = {"id", "text", "language", "target_intent", "case_type", "source"}
    valid_case_types = {"typical", "boundary", "typo", "short", "long"}

    print("=== 1. Volumes, identifiants et taxonomie ===")
    if len(rows) != EXPECTED_TOTAL:
        fail(f"{len(rows)} lignes au lieu de {EXPECTED_TOTAL}")
        valid = False
    else:
        ok(f"{len(rows)} lignes")

    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)):
        duplicates = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
        fail(f"ids dupliqués : {duplicates}")
        valid = False
    else:
        ok(f"{len(ids)} ids uniques")

    invalid_ids = [identifier for identifier in ids if not re.fullmatch(r"INT-\d{4}", str(identifier))]
    if invalid_ids:
        fail(f"ids mal formés : {invalid_ids[:10]}")
        valid = False
    else:
        ok("format des ids INT-XXXX")

    pilot_ids = read_pilot_ids()
    reused = sorted(set(ids) & pilot_ids)
    if reused:
        fail(f"ids du pilote réutilisés : {reused}")
        valid = False
    else:
        ok("aucun id du pilote réutilisé")

    per_intent = Counter(row.get("target_intent") for row in rows)
    bad_intents = sorted(set(per_intent) - set(intents))
    if bad_intents:
        fail(f"target_intent inconnus : {bad_intents}")
        valid = False
    for intent in intents:
        if per_intent[intent] != EXPECTED_PER_INTENT:
            fail(f"{intent} : {per_intent[intent]} questions au lieu de {EXPECTED_PER_INTENT}")
            valid = False
    if not bad_intents and all(per_intent[intent] == EXPECTED_PER_INTENT for intent in intents):
        ok(f"40 questions pour chacune des {len(intents)} intentions")

    per_intent_language = Counter((row.get("target_intent"), row.get("language")) for row in rows)
    language_error = False
    for intent in intents:
        fr_count = per_intent_language[(intent, "fr")]
        en_count = per_intent_language[(intent, "en")]
        if (fr_count, en_count) != (EXPECTED_FR, EXPECTED_EN):
            fail(f"{intent} : {fr_count} FR / {en_count} EN au lieu de 24 / 16")
            language_error = True
            valid = False
    if not language_error:
        ok("24 FR + 16 EN par intention")

    field_error = False
    for row in rows:
        missing = expected_fields - set(row)
        extra = set(row) - expected_fields
        if missing or extra:
            fail(f"{row.get('id')} : champs manquants {sorted(missing)}, champs en trop {sorted(extra)}")
            field_error = True
            valid = False
        if row.get("case_type") not in valid_case_types:
            fail(f"{row.get('id')} : case_type invalide {row.get('case_type')!r}")
            field_error = True
            valid = False
        if row.get("source") != "synthetic":
            fail(f"{row.get('id')} : source invalide {row.get('source')!r}")
            field_error = True
            valid = False
    if not field_error:
        ok("champs, case_type et source valides")

    print("\n=== 2. Longueur, langue et caractères ===")
    length_errors = []
    arabic_errors = []
    language_errors = []
    for row in rows:
        word_count = len(tokenize(row["text"]))
        if not 4 <= word_count <= 40:
            length_errors.append((row["id"], word_count, row["text"]))
        if has_arabic(row["text"]):
            arabic_errors.append(row["id"])
        if not language_plausible(row["text"], row["language"]):
            language_errors.append((row["id"], row["language"], language_scores(row["text"]), row["text"]))
    if length_errors:
        fail(f"{len(length_errors)} questions hors 4–40 mots : {length_errors[:10]}")
        valid = False
    else:
        ok("toutes les questions font 4 à 40 mots")
    if arabic_errors:
        fail(f"caractères arabes détectés : {arabic_errors}")
        valid = False
    else:
        ok("aucun caractère arabe")
    if language_errors:
        fail(f"{len(language_errors)} langues peu plausibles : {language_errors[:10]}")
        valid = False
    else:
        ok("langue plausible pour chaque question")

    case_length_errors = []
    for row in rows:
        word_count = len(tokenize(row["text"]))
        if row["case_type"] == "short" and not 4 <= word_count <= 7:
            case_length_errors.append((row["id"], row["case_type"], word_count))
        if row["case_type"] == "long" and not 25 <= word_count <= 40:
            case_length_errors.append((row["id"], row["case_type"], word_count))
    if case_length_errors:
        fail(f"longueurs incompatibles avec le case_type : {case_length_errors[:10]}")
        valid = False
    else:
        ok("short 4–7 mots et long 25–40 mots")

    print("\n=== 3. Doublons ===")
    normalized = {row["id"]: " ".join(tokenize(row["text"])) for row in rows}
    exact_groups = defaultdict(list)
    for row in rows:
        exact_groups[normalized[row["id"]]].append(row["id"])
    exact_duplicates = [group for group in exact_groups.values() if len(group) > 1]
    if exact_duplicates:
        fail(f"doublons exacts : {exact_duplicates}")
        valid = False
    else:
        ok("aucun doublon exact")
    quasi = quasi_duplicate_pairs(rows)
    if quasi:
        fail(f"{len(quasi)} quasi-doublons (Jaccard trigrammes ≥ 0,8) :")
        for left, right, score in quasi[:20]:
            print(f"    {left} / {right} : {score:.3f}")
        valid = False
    else:
        ok("aucun quasi-doublon (Jaccard trigrammes ≥ 0,8)")

    print("\n=== 4. Chevauchements avec les références ===")
    references = reference_ngrams(intents)
    overlaps = []
    for row in rows:
        common = ngrams(tokenize(row["text"]), 6) & references
        if common:
            overlaps.append((row["id"], sorted(" ".join(gram) for gram in common)[:2]))
    if overlaps:
        fail(f"{len(overlaps)} questions partagent 6 mots consécutifs avec intents.csv/guidelines :")
        for identifier, grams in overlaps[:20]:
            print(f"    {identifier} : {grams}")
        valid = False
    else:
        ok("aucun chevauchement de 6 mots avec les exemples ou les guidelines")

    pilot_texts = set()
    if PILOT_PATH.exists():
        with PILOT_PATH.open(encoding="utf-8-sig", newline="") as handle:
            pilot_texts = {" ".join(tokenize(row["text"])) for row in csv.DictReader(handle)}
    pilot_copies = [row["id"] for row in rows if normalized[row["id"]] in pilot_texts]
    if pilot_copies:
        fail(f"questions identiques au pilote : {pilot_copies}")
        valid = False
    else:
        ok("aucune question identique au pilote")

    print("\n=== 5. Équilibre et types de cas ===")
    majority = max(per_intent.values()) if per_intent else 0
    majority_share = majority / len(rows) if rows else 0
    if majority_share >= 0.30:
        fail(f"classe majoritaire {majority_share:.1%} ≥ 30 %")
        valid = False
    else:
        ok(f"classe majoritaire {majority_share:.1%} < 30 %")

    boundary_per_intent = Counter(row["target_intent"] for row in rows if row.get("case_type") == "boundary")
    boundary_errors = [intent for intent in intents if boundary_per_intent[intent] < 6]
    if boundary_errors:
        fail(f"moins de 6 boundary pour : {boundary_errors}")
        valid = False
    else:
        ok("au moins 6 boundary par intention")

    typo_share = sum(1 for row in rows if row.get("case_type") == "typo") / len(rows) if rows else 0
    if not 0.10 <= typo_share <= 0.20:
        fail(f"part de typo {typo_share:.1%} hors de 15 % ±5 points")
        valid = False
    else:
        ok(f"part de typo {typo_share:.1%} (15 % ±5 points)")

    case_counts = Counter(row.get("case_type") for row in rows)
    print(
        "    Répartition des case_type : "
        + ", ".join(f"{name}={case_counts[name]}" for name in ("typical", "boundary", "typo", "short", "long"))
    )

    print("\n=== Résultat ===")
    if valid:
        print("Tous les contrôles sont OK.")
    else:
        print("Au moins un contrôle est KO : corriger les questions puis relancer validate.")
    return valid


def _components(group: list[dict], edges: set[tuple[str, str]]) -> list[list[dict]]:
    by_id = {row["id"]: row for row in group}
    parent = {row["id"]: row["id"] for row in group}

    def find(identifier: str) -> str:
        while parent[identifier] != identifier:
            parent[identifier] = parent[parent[identifier]]
            identifier = parent[identifier]
        return identifier

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left, right in edges:
        if left in by_id and right in by_id:
            union(left, right)

    grouped = defaultdict(list)
    for row in group:
        grouped[find(row["id"])].append(row)
    return list(grouped.values())


def build_split(rows: list[dict], intents: dict[str, dict[str, str]]) -> dict[str, str]:
    edges = {(left, right) for left, right, _score in quasi_duplicate_pairs(rows)}
    split_of: dict[str, str] = {}
    rng = random.Random(SEED)

    for intent in intents:
        for language in ("fr", "en"):
            group = [row for row in rows if row["target_intent"] == intent and row["language"] == language]
            expected_total = EXPECTED_FR if language == "fr" else EXPECTED_EN
            if len(group) != expected_total:
                raise SystemExit(f"{intent}/{language} : {len(group)} questions au lieu de {expected_total}")
            capacities = (
                {"train": 17, "val": 4, "test": 3}
                if language == "fr"
                else {"train": 11, "val": 2, "test": 3}
            )
            components = _components(group, edges)
            # Un quasi-doublon ne doit jamais traverser deux groupes (intention/langue).
            for component in components:
                component_intents = {row["target_intent"] for row in component}
                component_languages = {row["language"] for row in component}
                if len(component_intents) != 1 or len(component_languages) != 1:
                    raise SystemExit(
                        "Un quasi-doublon traverse deux intentions ou deux langues ; "
                        "corriger les questions avant de relancer split."
                    )
            rng.shuffle(components)
            components.sort(key=lambda component: -len(component))
            for component in components:
                placed = False
                for split_name in ("train", "val", "test"):
                    if capacities[split_name] >= len(component):
                        capacities[split_name] -= len(component)
                        for row in component:
                            split_of[row["id"]] = split_name
                        placed = True
                        break
                if not placed:
                    raise SystemExit(
                        f"Impossible de placer un groupe de quasi-doublons dans {intent}/{language} "
                        "tout en respectant les effectifs 17/4/3 ou 11/2/3."
                    )
            if any(capacities.values()):
                raise SystemExit(f"Effectifs non atteints pour {intent}/{language} : {capacities}")

    for left, right, _score in quasi_duplicate_pairs(rows):
        if split_of[left] != split_of[right]:
            raise SystemExit(
                f"Quasi-doublon séparé entre splits : {left} ({split_of[left]}) / "
                f"{right} ({split_of[right]}). Corriger les questions ou rééquilibrer."
            )
    return split_of


def write_split(rows: list[dict], split_of: dict[str, str]) -> None:
    SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SPLIT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(SPLIT_COLUMNS)
        for row in rows:
            writer.writerow([row["id"], split_of[row["id"]]])


def annotation_row(row: dict) -> dict[str, str]:
    return {
        "id": row["id"],
        "language": row["language"],
        "text": row["text"],
        "intent": "",
        "ambiguous": "",
        "acceptable_labels": "",
        "notes": "",
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_annotation_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def verify_sheets(rows: list[dict], split_of: dict[str, str]) -> None:
    by_id = {row["id"]: row for row in rows}
    aya_path = BLIND_DIR / "annotate_aya.csv"
    mohammed_path = BLIND_DIR / "annotate_mohammed.csv"
    spotcheck_path = BLIND_DIR / "spotcheck_train_aya.csv"

    for path in (aya_path, mohammed_path, spotcheck_path):
        header, sheet_rows = read_annotation_csv(path)
        if header != ANNOTATION_COLUMNS:
            raise SystemExit(f"{path.name} : en-tête inattendu {header}")
        for row in sheet_rows:
            if any(row[column] != "" for column in ANNOTATION_EMPTY_COLUMNS):
                raise SystemExit(f"{path.name} : une colonne d'annotation n'est pas vide pour {row['id']}")
            if set(row) != set(ANNOTATION_COLUMNS):
                raise SystemExit(f"{path.name} : colonnes inattendues pour {row['id']}")

    aya_header, aya_rows = read_annotation_csv(aya_path)
    mohammed_header, mohammed_rows = read_annotation_csv(mohammed_path)
    if aya_header != ANNOTATION_COLUMNS or mohammed_header != ANNOTATION_COLUMNS:
        raise SystemExit("Les deux feuilles principales n'ont pas le même en-tête attendu")
    aya_ids = [row["id"] for row in aya_rows]
    mohammed_ids = [row["id"] for row in mohammed_rows]
    if len(aya_ids) != 168 or len(mohammed_ids) != 168:
        raise SystemExit(f"Effectifs inattendus : aya={len(aya_ids)}, mohammed={len(mohammed_ids)}")
    if len(set(aya_ids)) != 168 or len(set(mohammed_ids)) != 168:
        raise SystemExit("Ids dupliqués dans une feuille d'annotation")
    if set(aya_ids) != set(mohammed_ids):
        raise SystemExit("Les ids de annotate_aya.csv et annotate_mohammed.csv diffèrent")
    if aya_ids == mohammed_ids:
        raise SystemExit("Les deux feuilles ont exactement le même ordre")
    if any(split_of[identifier] not in {"val", "test"} for identifier in aya_ids):
        raise SystemExit("Une feuille principale contient un exemple hors val/test")

    spot_header, spot_rows = read_annotation_csv(spotcheck_path)
    if spot_header != ANNOTATION_COLUMNS:
        raise SystemExit("En-tête inattendu pour spotcheck_train_aya.csv")
    spot_ids = [row["id"] for row in spot_rows]
    if len(spot_ids) != 56 or len(set(spot_ids)) != 56:
        raise SystemExit(f"spotcheck_train_aya.csv doit contenir 56 ids uniques, trouvé {len(spot_ids)}")
    if any(split_of[identifier] != "train" for identifier in spot_ids):
        raise SystemExit("Le sondage train contient un exemple hors train")
    spot_per_intent = Counter(by_id[identifier]["target_intent"] for identifier in spot_ids)
    if any(spot_per_intent[intent] != 4 for intent in set(by_id[identifier]["target_intent"] for identifier in spot_ids)):
        raise SystemExit(f"Le sondage train n'a pas 4 exemples par intention : {dict(spot_per_intent)}")


def write_sheets(rows: list[dict], split_of: dict[str, str]) -> None:
    val_test = [row for row in rows if split_of[row["id"]] in {"val", "test"}]
    train = [row for row in rows if split_of[row["id"]] == "train"]
    if len(val_test) != 168 or len(train) != 392:
        raise SystemExit(f"Effectifs inattendus : val+test={len(val_test)}, train={len(train)}")

    aya_rows = [annotation_row(row) for row in val_test]
    mohammed_rows = [annotation_row(row) for row in val_test]
    random.Random(SEED).shuffle(aya_rows)
    random.Random(SEED + 1).shuffle(mohammed_rows)
    if [row["id"] for row in aya_rows] == [row["id"] for row in mohammed_rows]:
        raise SystemExit("Les deux mélanges ont produit le même ordre ; changer les graines.")

    spot_rows = []
    rng = random.Random(SEED)
    for intent in sorted({row["target_intent"] for row in rows}):
        for language in ("fr", "en"):
            group = [row for row in train if row["target_intent"] == intent and row["language"] == language]
            rng.shuffle(group)
            if len(group) < 2:
                raise SystemExit(f"Pas assez d'exemples train pour {intent}/{language}")
            spot_rows.extend(annotation_row(row) for row in group[:2])
    if len(spot_rows) != 56:
        raise SystemExit(f"Le sondage train doit contenir 56 lignes, trouvé {len(spot_rows)}")
    random.Random(SEED + 2).shuffle(spot_rows)

    write_csv(BLIND_DIR / "annotate_aya.csv", aya_rows)
    write_csv(BLIND_DIR / "annotate_mohammed.csv", mohammed_rows)
    write_csv(BLIND_DIR / "spotcheck_train_aya.csv", spot_rows)

    readme = """# Annotation aveugle des intentions — SupportAI

Tu annotes **seul(e)**, sans consulter l'autre annotateur et sans ouvrir le fichier privé `intent_candidates.jsonl`.

## Fichiers à remplir

- `annotate_aya.csv` ou `annotate_mohammed.csv` : 168 exemples de validation et de test.
- `spotcheck_train_aya.csv` : 56 exemples de train pour le contrôle qualité.

Les colonnes `intent`, `ambiguous`, `acceptable_labels` et `notes` sont **vides** : c'est à toi de les remplir.

## Avant de commencer

Lis `docs/annotation_guidelines.md` :

- §5.2 Choix de l'étiquette
- §5.3 Frontières entre classes
- §5.4 Cas ambigus
- Annexe B Checklist de l'annotateur

## Valeurs autorisées pour `intent`

`order_tracking`, `order_change_cancel`, `delivery_issue`, `return_request`, `refund_status`,
`payment_info`, `payment_issue`, `technical_support`, `warranty_claim`, `product_info`,
`promotion_loyalty`, `account_privacy`, `human_support`, `out_of_scope`.

Une seule étiquette principale par exemple. Si deux annotateurs formés peuvent raisonnablement
choisir deux étiquettes différentes et qu'aucune règle du guide ne tranche, mets `ambiguous=true`
et renseigne `acceptable_labels` avec les codes possibles. Sinon, applique la règle et laisse
`ambiguous=false` avec `acceptable_labels` vide.

## Consignes pratiques

- Ne consulte ni l'autre annotateur, ni le fichier privé des questions candidates.
- Sauvegarde ton fichier toutes les 50 lignes.
- Ajoute une note dans `notes` pour les cas difficiles.
- Quand tu as terminé, renvoie le fichier sous le nom `annotate_<prénom>_done.csv`
  (par exemple `annotate_aya_done.csv` ou `annotate_mohammed_done.csv`).
- Pour le sondage train, renvoie `spotcheck_train_aya_done.csv`.

Ne modifie pas les colonnes `id`, `language` et `text`.
"""
    (BLIND_DIR / "README_annotation.md").write_text(readme, encoding="utf-8", newline="\n")
    verify_sheets(rows, split_of)


def command_validate(_args: argparse.Namespace) -> int:
    rows = read_jsonl(CANDIDATES_PATH)
    intents = read_intents()
    return 0 if validate_candidates(rows, intents) else 1


def command_split(_args: argparse.Namespace) -> int:
    rows = read_jsonl(CANDIDATES_PATH)
    intents = read_intents()
    split_of = build_split(rows, intents)
    write_split(rows, split_of)
    counts = Counter(split_of.values())
    print(f"Split écrit : {SPLIT_PATH.relative_to(ROOT)}")
    print(f"Effectifs : train={counts['train']}, val={counts['val']}, test={counts['test']}")
    for intent in intents:
        for language in ("fr", "en"):
            local = Counter(
                split_of[row["id"]]
                for row in rows
                if row["target_intent"] == intent and row["language"] == language
            )
            print(f"  {intent}/{language}: train={local['train']}, val={local['val']}, test={local['test']}")
    return 0


def command_sheets(_args: argparse.Namespace) -> int:
    rows = read_jsonl(CANDIDATES_PATH)
    if not SPLIT_PATH.exists():
        raise SystemExit("Lance d'abord : python scripts/prepare_intent_annotation.py split")
    with SPLIT_PATH.open(encoding="utf-8", newline="") as handle:
        split_of = {row["id"]: row["split"] for row in csv.DictReader(handle)}
    missing = [row["id"] for row in rows if row["id"] not in split_of]
    if missing:
        raise SystemExit(f"Ids absents de intent_split.csv : {missing[:10]}")
    write_sheets(rows, split_of)
    print(f"Feuilles écrites dans {BLIND_DIR.relative_to(ROOT)}")
    print("  annotate_aya.csv : 168 lignes + en-tête")
    print("  annotate_mohammed.csv : 168 lignes + en-tête")
    print("  spotcheck_train_aya.csv : 56 lignes + en-tête")
    print("  README_annotation.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="contrôler les 560 questions candidates")
    validate_parser.set_defaults(func=command_validate)
    split_parser = subparsers.add_parser("split", help="écrire le découpage train/val/test")
    split_parser.set_defaults(func=command_split)
    sheets_parser = subparsers.add_parser("sheets", help="écrire les feuilles d'annotation aveugles")
    sheets_parser.set_defaults(func=command_sheets)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
