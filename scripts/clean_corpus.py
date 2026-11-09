#!/usr/bin/env python3
"""Nettoyage, normalisation et déduplication du corpus SupportAI.

Entrée  : ``data/processed/extracted/documents.jsonl``
Sortie  : ``data/processed/cleaned_corpus.jsonl``
Rapport : ``docs/reports/cleaning_report.md``

Usage :
    python scripts/clean_corpus.py [--check]

Le script n'écrit aucun horodatage : deux exécutions produisent des fichiers
identiques octet pour octet. Il n'utilise que la bibliothèque standard.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "extracted" / "documents.jsonl"
OUTPUT = ROOT / "data" / "processed" / "cleaned_corpus.jsonl"
REPORT = ROOT / "docs" / "reports" / "cleaning_report.md"
CORPUS = ROOT / "data" / "raw" / "corpus"

NEAR_DUP_THRESHOLD = 0.90
HEADING_MAX_WORDS = 8
FREQUENT_LINE_MIN = 20
EXPECTED_LANGUAGE_COUNT = 261

NBSP = ("\u00a0", "\u202f", "\u2009", "\u2007", "\u2008")
INVISIBLES = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060")

# Motifs explicites d'en-têtes et de pieds de page répétés. Toute suppression
# passe par cette constante : aucun nettoyage « deviné ».
BOILERPLATE = {
    "reference": re.compile(
        r"^Référence .+ · version .+ · entrée en vigueur .+ · NovaShop$"
    ),
    "fictif_entete": re.compile(
        r"^Document fictif — NovaShop est une société imaginaire créée pour le "
        r"projet pédagogique SupportAI\.$"
    ),
    "fictif_pied": re.compile(r"^(?:Document fictif|Fictional document) — "),
    "version": re.compile(
        r"^Version\s*:\s*[^·\n]+?·\s*(?:Effective date|Entrée en vigueur)"
        r"\s*:\s*[^\n]*?\b\d{4}\b[ \t]*"
    ),
    "separateur": re.compile(r"^_{10,}$"),
}

MONEY_RE = re.compile(r"\d[\d \u00a0\u202f]*\s?MAD")
PERCENT_RE = re.compile(r"\d+(?:[.,]\d+)?\s?%")
WORD_RE = re.compile(r"\w+", re.UNICODE)


class CleaningError(RuntimeError):
    """Un enregistrement est devenu vide après nettoyage."""


@dataclass
class CleanResult:
    text: str
    removed: list[str]
    motifs: Counter
    reflowed: bool
    normalized_changed: bool
    steps: list[str]


# --------------------------------------------------------------- normalisation


def normalize_text(text: str) -> str:
    """Normalise sans jamais supprimer d'information métier.

    Les accents, la ponctuation française et les montants restent intacts.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for space in NBSP:
        text = text.replace(space, " ")
    for invisible in INVISIBLES:
        text = text.replace(invisible, "")
    text = text.replace("\t", " ")
    text = "".join(
        char for char in text
        if char == "\n" or unicodedata.category(char) != "Cc"
    )
    text = re.sub(r" +", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def words(text: str) -> list[str]:
    """Séquence de mots au sens du contrôle « sans perte »."""
    return WORD_RE.findall(text.lower())


def duplicate_key(text: str) -> str:
    """Clé de doublon exact : minuscules, ponctuation réduite."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def trigrams(text: str) -> set[tuple[str, str, str]]:
    tokens = duplicate_key(text).split()
    return set(zip(tokens, tokens[1:], tokens[2:]))


def jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


# --------------------------------------------------------------------- reflow


def is_numbered_title(line: str) -> bool:
    """Titre court numéroté (``6. Procedure``), sans ponctuation finale."""
    stripped = line.strip()
    if len(stripped.split()) > HEADING_MAX_WORDS:
        return False
    if re.search(r"[.!?;:]$", stripped):
        return False
    return bool(re.match(r"^\d+(?:\.\d+)*[.)]?\s+\S", stripped))


def starts_list(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-•]|\d+\.)\s+", line))


def should_join(previous: str, following: str, protect_previous: bool = False) -> bool:
    if protect_previous:
        return False
    if not previous.strip() or not following.strip():
        return False
    if "|" in previous or "|" in following:
        return False
    if previous.rstrip()[-1] in ".!?:;":
        return False
    if is_numbered_title(previous):
        return False
    if starts_list(following):
        return False
    return True


def reflow_pdf(text: str, protect_first_line: bool = False) -> str:
    """Réunit les lignes coupées à ~80 caractères, uniquement pour les PDF."""
    lines = text.split("\n")
    output: list[str] = []
    for line in lines:
        if output:
            protect = protect_first_line and len(output) == 1
            if should_join(output[-1], line, protect):
                output[-1] = output[-1].rstrip() + " " + line.strip()
                continue
        output.append(line)
    return "\n".join(output)


# ------------------------------------------------------------------ en-têtes


def remove_boilerplate(text: str) -> tuple[str, list[str], Counter]:
    """Supprime les en-têtes et pieds de page explicitement listés."""
    lines = text.split("\n")
    output: list[str] = []
    removed: list[str] = []
    motifs: Counter = Counter()
    index = 0

    while index < len(lines):
        raw = lines[index]
        line = raw.strip()

        if not line:
            output.append(raw)
            index += 1
            continue

        if BOILERPLATE["reference"].match(line):
            removed.append(line)
            motifs["reference"] += 1
            index += 1
            continue

        if BOILERPLATE["fictif_entete"].match(line):
            removed.append(line)
            motifs["fictif_entete"] += 1
            index += 1
            continue

        if BOILERPLATE["fictif_pied"].match(line):
            # Le séparateur qui précède immédiatement un pied de page en fait partie.
            position = len(output) - 1
            while position >= 0 and not output[position].strip():
                position -= 1
            if position >= 0 and BOILERPLATE["separateur"].match(output[position].strip()):
                removed.append(output[position].strip())
                motifs["separateur"] += 1
                output.pop(position)

            block: list[str] = []
            while index < len(lines):
                block.append(lines[index])
                if re.search(r"[.!?]\s*$", lines[index].strip()):
                    index += 1
                    break
                index += 1
            removed.append("\n".join(block).strip())
            motifs["fictif_pied"] += 1
            continue

        match = BOILERPLATE["version"].match(line)
        if match:
            prefix = match.group(0)
            removed.append(prefix)
            motifs["version"] += 1
            rest = line[match.end():].strip()
            if rest:
                output.append(rest)
            index += 1
            continue

        output.append(raw)
        index += 1

    return "\n".join(output), removed, motifs


# ------------------------------------------------------------- enregistrement


def clean_record(record: dict) -> CleanResult:
    original = record["text"]
    normalized = normalize_text(original)
    text, removed, motifs = remove_boilerplate(normalized)

    reflowed = False
    if record["format"] == "pdf":
        reflowed_text = reflow_pdf(
            text, protect_first_line=record.get("page") == 1
        )
        reflowed = reflowed_text != text
        text = reflowed_text

    text = normalize_text(text)
    if not text:
        raise CleaningError(
            f"enregistrement vide après nettoyage : {record['record_id']}"
        )

    steps = ["normalisation"]
    if removed:
        steps.append("entetes")
    if reflowed:
        steps.append("reflow_pdf")

    return CleanResult(
        text=text,
        removed=removed,
        motifs=motifs,
        reflowed=reflowed,
        normalized_changed=normalized != original,
        steps=steps,
    )


def is_heading_only(record: dict, text: str) -> bool:
    if record["unit_type"] != "section":
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped.split()) > HEADING_MAX_WORDS:
        return False
    return not re.search(r"[.!?;:]$", stripped)


def build_output_record(record: dict, text: str, cleaning: dict) -> dict:
    """Construit la sortie : identité, texte nettoyé, compteurs, nettoyage."""
    return {
        "record_id": record["record_id"],
        "doc_id": record["doc_id"],
        "language": record["language"],
        "format": record["format"],
        "category": record["category"],
        "title": record["title"],
        "source_path": record["source_path"],
        "source_sha256": record["source_sha256"],
        "unit_type": record["unit_type"],
        "unit_id": record["unit_id"],
        "page": record["page"],
        "section": record["section"],
        "text": text,
        "char_count": len(text),
        "word_count": len(text.split()),
        "cleaning": {
            "steps": cleaning["steps"],
            "removed": cleaning["removed"],
            "reflowed": cleaning["reflowed"],
            "heading_only": cleaning["heading_only"],
            "near_duplicate_of": cleaning["near_duplicate_of"],
        },
    }


def clean_all(records: list[dict]) -> tuple[list[dict], list[dict], list[tuple[str, str]]]:
    """Nettoie tous les enregistrements et retourne aussi les diagnostics."""
    cleaned: list[dict] = []
    diagnostics: list[dict] = []
    duplicates: list[tuple[str, str]] = []
    duplicate_index: dict[tuple[str, str], str] = {}
    kept_trigrams: dict[str, list[tuple[str, set]]] = {"fr": [], "en": []}

    for record in records:
        result = clean_record(record)
        language = record["language"]
        key = duplicate_key(result.text)
        duplicate_of = duplicate_index.get((language, key))
        near_duplicate_of = None
        near_duplicate_score = None

        if duplicate_of is None:
            duplicate_index[(language, key)] = record["record_id"]
            current_trigrams = trigrams(result.text)
            for previous_id, previous_trigrams in kept_trigrams.setdefault(language, []):
                score = jaccard(current_trigrams, previous_trigrams)
                if score >= NEAR_DUP_THRESHOLD:
                    near_duplicate_of = previous_id
                    near_duplicate_score = score
                    break
            kept_trigrams[language].append((record["record_id"], current_trigrams))

        heading_only = is_heading_only(record, result.text)
        steps = list(result.steps)
        if near_duplicate_of:
            steps.append("quasi_doublon")
        if heading_only:
            steps.append("titre_seul")

        cleaning = {
            "steps": steps,
            "removed": result.removed,
            "reflowed": result.reflowed,
            "heading_only": heading_only,
            "near_duplicate_of": near_duplicate_of,
        }

        diagnostics.append({
            "record_id": record["record_id"],
            "doc_id": record["doc_id"],
            "language": language,
            "format": record["format"],
            "unit_type": record["unit_type"],
            "source_path": record["source_path"],
            "input_text": record["text"],
            "cleaned_text": result.text,
            "removed": result.removed,
            "motifs": result.motifs,
            "reflowed": result.reflowed,
            "normalized_changed": result.normalized_changed,
            "heading_only": heading_only,
            "near_duplicate_of": near_duplicate_of,
            "near_duplicate_score": near_duplicate_score,
            "duplicate_of": duplicate_of,
        })

        if duplicate_of is None:
            cleaned.append(build_output_record(record, result.text, cleaning))
        else:
            duplicates.append((record["record_id"], duplicate_of))

    return cleaned, diagnostics, duplicates


# ------------------------------------------------------------------ contrôles


def extract_values(text: str) -> list[str]:
    values = [match.group(0) for match in MONEY_RE.finditer(text)]
    values += [match.group(0) for match in PERCENT_RE.finditer(text)]
    return [re.sub(r"\s+", " ", value.replace("\u00a0", " ").replace("\u202f", " ")).strip()
            for value in values]


def control_no_loss(diagnostics: list[dict]) -> tuple[bool, str, list[str]]:
    problems: list[str] = []
    for diagnostic in diagnostics:
        before = words(diagnostic["input_text"])
        after = words(diagnostic["cleaned_text"])
        matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        deleted: list[str] = []
        inserted: list[str] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("delete", "replace"):
                deleted.extend(before[i1:i2])
            if tag in ("insert", "replace"):
                inserted.extend(after[j1:j2])
        removed_words = [word for segment in diagnostic["removed"] for word in words(segment)]
        if deleted != removed_words or inserted:
            problems.append(diagnostic["record_id"])
    return (
        not problems,
        f"{len(diagnostics)} enregistrements vérifiés, {len(problems)} écart(s)",
        problems,
    )


def control_no_headers(diagnostics: list[dict]) -> tuple[bool, str, list[str]]:
    residual: list[str] = []
    for diagnostic in diagnostics:
        for line in diagnostic["cleaned_text"].split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if (
                BOILERPLATE["reference"].match(stripped)
                or BOILERPLATE["fictif_pied"].match(stripped)
                or BOILERPLATE["version"].match(stripped)
            ):
                residual.append(f"{diagnostic['record_id']}: {stripped[:80]}")
        if diagnostic["language"] == "en":
            for token in ("Référence", "Document fictif", "entrée en vigueur"):
                if token in diagnostic["cleaned_text"]:
                    residual.append(f"{diagnostic['record_id']}: {token}")
    return not residual, f"{len(residual)} résidu(s)", residual


def control_whitespace(diagnostics: list[dict]) -> tuple[bool, str, list[str]]:
    problems: list[str] = []
    for diagnostic in diagnostics:
        text = diagnostic["cleaned_text"]
        issues: list[str] = []
        if "\t" in text:
            issues.append("tabulation")
        if re.search(r"  +", text):
            issues.append("espace double")
        if any(space in text for space in NBSP):
            issues.append("espace insécable")
        if "\n\n\n" in text:
            issues.append("ligne vide triple")
        if any(line != line.rstrip() for line in text.split("\n")):
            issues.append("espace en fin de ligne")
        if text != text.strip():
            issues.append("texte non strip")
        if unicodedata.normalize("NFC", text) != text:
            issues.append("non NFC")
        if issues:
            problems.append(f"{diagnostic['record_id']}: {', '.join(issues)}")
    return (
        not problems,
        f"{len(diagnostics)} enregistrements, {len(problems)} problème(s)",
        problems,
    )


def control_structure(records: list[dict], diagnostics: list[dict]) -> tuple[bool, str, list[str]]:
    groups: dict[tuple[str, str, str], dict[str, set[str]]] = {}
    for record, diagnostic in zip(records, diagnostics):
        if record["format"] not in ("pdf", "docx"):
            continue
        key = (record["doc_id"], record["language"], record["source_path"])
        group = groups.setdefault(key, {"before": set(), "after": set()})
        group["before"].update(line.strip() for line in record["text"].split("\n"))
        group["after"].update(line.strip() for line in diagnostic["cleaned_text"].split("\n"))

    before_total = 0
    after_total = 0
    missing: list[str] = []
    for (doc_id, language, source_path), group in sorted(groups.items()):
        markdown = CORPUS / language / (Path(source_path).stem + ".md")
        if not markdown.exists():
            missing.append(f"{doc_id}/{language}: Markdown absent")
            continue
        headings = [
            match.group(1).strip()
            for match in re.finditer(r"^##\s+(.+)$", markdown.read_text(encoding="utf-8"), re.M)
        ]
        for heading in headings:
            if heading in group["before"]:
                before_total += 1
                if heading in group["after"]:
                    after_total += 1
                else:
                    missing.append(f"{doc_id}/{language}: {heading}")
    ok = not missing and after_total == before_total
    return ok, f"{after_total}/{before_total} titres conservés", missing


def control_volumes(
    records: list[dict], cleaned: list[dict], duplicates: list[tuple[str, str]]
) -> tuple[bool, str, list[str]]:
    expected = len(records) - len(duplicates)
    fr = sum(1 for record in cleaned if record["language"] == "fr")
    en = sum(1 for record in cleaned if record["language"] == "en")
    unique = len({record["record_id"] for record in cleaned}) == len(cleaned)
    parity = "parité OK" if fr == en else "parité rompue"
    ok = (
        len(cleaned) == expected
        and fr == EXPECTED_LANGUAGE_COUNT
        and en == EXPECTED_LANGUAGE_COUNT
        and unique
    )
    value = (
        f"{len(cleaned)} en sortie / {expected} attendus, "
        f"{fr} FR / {en} EN, {parity}, "
        f"identifiants {'uniques' if unique else 'non uniques'}"
    )
    return ok, value, []


def control_business_values(records: list[dict], diagnostics: list[dict]) -> tuple[bool, str, list[str]]:
    problems: list[str] = []
    for record, diagnostic in zip(records, diagnostics):
        before = Counter(extract_values(record["text"]))
        removed = Counter(extract_values("\n".join(diagnostic["removed"])))
        after = Counter(extract_values(diagnostic["cleaned_text"]))
        if (before - removed) != after:
            problems.append(record["record_id"])
    return (
        not problems,
        f"{len(records)} enregistrements, {len(problems)} écart(s)",
        problems,
    )


def control_determinism(records: list[dict]) -> tuple[bool, str, list[str]]:
    first, _, _ = clean_all(records)
    second, _, _ = clean_all(records)
    first_bytes = serialize(first)
    second_bytes = serialize(second)
    digest = hashlib.sha256(first_bytes).hexdigest()
    ok = first_bytes == second_bytes
    value = (
        f"sha256 identique ({digest[:16]}…)"
        if ok
        else "sha256 différent entre deux exécutions"
    )
    return ok, value, []


def run_controls(
    records: list[dict],
    cleaned: list[dict],
    diagnostics: list[dict],
    duplicates: list[tuple[str, str]],
) -> list[dict]:
    definitions = [
        ("Sans perte de mots", control_no_loss(diagnostics)),
        ("Aucun en-tête résiduel", control_no_headers(diagnostics)),
        ("Espaces et Unicode", control_whitespace(diagnostics)),
        ("Structure des titres", control_structure(records, diagnostics)),
        ("Volumes et parité", control_volumes(records, cleaned, duplicates)),
        ("Valeurs métier", control_business_values(records, diagnostics)),
        ("Déterminisme", control_determinism(records)),
    ]
    return [
        {"id": index, "name": name, "ok": result[0], "value": result[1], "details": result[2]}
        for index, (name, result) in enumerate(definitions, 1)
    ]


# ------------------------------------------------------------------- rapport


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def volume_rows(records: list[dict]) -> dict[tuple[str, str], list[int]]:
    rows: dict[tuple[str, str], list[int]] = {}
    for record in records:
        key = (record["language"], record["format"])
        row = rows.setdefault(key, [0, 0, 0])
        row[0] += 1
        row[1] += len(record["text"].split())
        row[2] += len(record["text"])
    return rows


def frequent_lines(records: list[dict]) -> list[tuple[int, str]]:
    counter: Counter = Counter()
    for record in records:
        for line in record["text"].split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.match(stripped) for pattern in BOILERPLATE.values()):
                continue
            counter[stripped] += 1
    return sorted(
        ((count, line) for line, count in counter.items() if count >= FREQUENT_LINE_MIN),
        key=lambda item: (-item[0], item[1]),
    )


def truncate(text: str, limit: int = 600) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def select_examples(diagnostics: list[dict]) -> list[tuple[str, dict]]:
    used: set[str] = set()
    available = [d for d in diagnostics if d["duplicate_of"] is None]

    def pick(predicate, count: int) -> list[dict]:
        picked: list[dict] = []
        for diagnostic in available:
            if diagnostic["record_id"] in used:
                continue
            if predicate(diagnostic):
                picked.append(diagnostic)
                used.add(diagnostic["record_id"])
                if len(picked) == count:
                    break
        return picked

    def has_version_prefix(diagnostic: dict) -> bool:
        return any(
            BOILERPLATE["version"].match(segment.strip())
            for segment in diagnostic["removed"]
        )

    version_scope = pick(
        lambda d: d["language"] == "en"
        and has_version_prefix(d)
        and "Scope:" in d["cleaned_text"],
        1,
    )
    if not version_scope:
        version_scope = pick(
            lambda d: has_version_prefix(d) and "Périmètre :" in d["cleaned_text"],
            1,
        )

    examples: list[tuple[str, dict]] = []
    examples += [("PDF EN", d) for d in pick(
        lambda d: d["format"] == "pdf" and d["language"] == "en" and bool(d["removed"]), 3)]
    examples += [("PDF FR", d) for d in pick(
        lambda d: d["format"] == "pdf" and d["language"] == "fr" and bool(d["removed"]), 2)]
    examples += [("DOCX", d) for d in pick(
        lambda d: d["format"] == "docx" and bool(d["removed"]) and not d["heading_only"], 2)]
    examples += [("FAQ", d) for d in pick(
        lambda d: d["format"] in ("json", "jsonl", "csv"), 1)]
    heading_examples = pick(
        lambda d: d["heading_only"] and is_numbered_title(d["cleaned_text"]), 1)
    if not heading_examples:
        heading_examples = pick(lambda d: d["heading_only"], 1)
    examples += [("Titre seul", d) for d in heading_examples]
    examples += [("Préfixe Version … Scope", d) for d in version_scope]

    if len(examples) < 10:
        for diagnostic in available:
            if diagnostic["record_id"] in used:
                continue
            examples.append(("Complément", diagnostic))
            used.add(diagnostic["record_id"])
            if len(examples) == 10:
                break
    return examples


def build_report(
    records: list[dict],
    cleaned: list[dict],
    diagnostics: list[dict],
    duplicates: list[tuple[str, str]],
    controls: list[dict],
    frequent: list[tuple[int, str]],
    examples: list[tuple[str, dict]],
) -> str:
    input_rows = volume_rows(records)
    output_rows = volume_rows(cleaned)
    keys = sorted(set(input_rows) | set(output_rows))

    lines = [
        "# Rapport de nettoyage et de normalisation du corpus",
        "",
        "> Généré par `scripts/clean_corpus.py`. Ne pas modifier à la main.",
        "> Aucun horodatage : le rapport est reproductible octet pour octet.",
        "",
        f"- Enregistrements en entrée : **{fmt_int(len(records))}**",
        f"- Enregistrements en sortie : **{fmt_int(len(cleaned))}**",
        f"- Doublons exacts supprimés : **{fmt_int(len(duplicates))}**",
        f"- Quasi-doublons signalés : **{fmt_int(sum(1 for d in diagnostics if d['near_duplicate_of']))}**",
        "",
        "## 1. Volumes entrée / sortie",
        "",
        "| Langue | Format | Entrée rec. | Entrée mots | Entrée car. | Sortie rec. | Sortie mots | Sortie car. |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for language, fmt in keys:
        before = input_rows.get((language, fmt), [0, 0, 0])
        after = output_rows.get((language, fmt), [0, 0, 0])
        lines.append(
            f"| {language} | {fmt} | {fmt_int(before[0])} | {fmt_int(before[1])} | "
            f"{fmt_int(before[2])} | {fmt_int(after[0])} | {fmt_int(after[1])} | "
            f"{fmt_int(after[2])} |"
        )
    total_before = [sum(row[i] for row in input_rows.values()) for i in range(3)]
    total_after = [sum(row[i] for row in output_rows.values()) for i in range(3)]
    lines.append(
        f"| **Total** | | **{fmt_int(total_before[0])}** | **{fmt_int(total_before[1])}** | "
        f"**{fmt_int(total_before[2])}** | **{fmt_int(total_after[0])}** | "
        f"**{fmt_int(total_after[1])}** | **{fmt_int(total_after[2])}** |"
    )

    motif_counts: Counter = Counter()
    for diagnostic in diagnostics:
        motif_counts.update(diagnostic["motifs"])
    normalized_changed = sum(1 for d in diagnostics if d["normalized_changed"])
    touched = sum(1 for d in diagnostics if d["removed"])
    segments = sum(len(d["removed"]) for d in diagnostics)
    characters = sum(len(segment) for d in diagnostics for segment in d["removed"])
    reflowed = sum(1 for d in diagnostics if d["reflowed"])
    heading_only = sum(1 for d in diagnostics if d["heading_only"])
    near_duplicates = sum(1 for d in diagnostics if d["near_duplicate_of"])

    lines += [
        "",
        "## 2. Compteurs par étape",
        "",
        "| Étape | Indicateur | Valeur |",
        "| --- | --- | ---: |",
        f"| Normalisation | Enregistrements modifiés | {fmt_int(normalized_changed)} |",
        f"| En-têtes / pieds de page | Enregistrements touchés | {fmt_int(touched)} |",
        f"| En-têtes / pieds de page | Segments supprimés | {fmt_int(segments)} |",
        f"| En-têtes / pieds de page | Caractères supprimés (segments) | {fmt_int(characters)} |",
        f"| Global | Delta mots entrée − sortie | {fmt_int(total_before[1] - total_after[1])} |",
        f"| Global | Delta caractères entrée − sortie | {fmt_int(total_before[2] - total_after[2])} |",
        f"| Motif | `Référence … · version … · entrée en vigueur …` | {fmt_int(motif_counts['reference'])} |",
        f"| Motif | `Document fictif — …` (en-tête) | {fmt_int(motif_counts['fictif_entete'])} |",
        f"| Motif | `Document fictif` / `Fictional document` (pied) | {fmt_int(motif_counts['fictif_pied'])} |",
        f"| Motif | Préfixe `Version … Effective date` / `Entrée en vigueur` | {fmt_int(motif_counts['version'])} |",
        f"| Motif | Séparateur `____` | {fmt_int(motif_counts['separateur'])} |",
        f"| Reflow PDF | Enregistrements reflowés | {fmt_int(reflowed)} |",
        f"| Doublons | Doublons exacts supprimés | {fmt_int(len(duplicates))} |",
        f"| Doublons | Quasi-doublons signalés | {fmt_int(near_duplicates)} |",
        f"| Titres seuls | Enregistrements conservés | {fmt_int(heading_only)} |",
        "",
        "## 3. Contrôles automatiques",
        "",
        "| # | Contrôle | Résultat | Valeur |",
        "| ---: | --- | --- | --- |",
    ]
    for control in controls:
        status = "OK" if control["ok"] else "KO"
        value = control["value"].replace("|", "\\|")
        lines.append(f"| {control['id']} | {control['name']} | {status} | {value} |")

    lines += ["", "## 4. Doublons exacts supprimés", ""]
    if duplicates:
        for record_id, duplicate_of in duplicates:
            lines.append(f"- `{record_id}` (doublon de `{duplicate_of}`)")
    else:
        lines.append("Aucun.")

    lines += ["", "## 5. Quasi-doublons signalés", ""]
    flagged = [d for d in diagnostics if d["near_duplicate_of"]]
    if flagged:
        for diagnostic in flagged:
            score = diagnostic["near_duplicate_score"] or 0.0
            lines.append(
                f"- `{diagnostic['record_id']}` ≈ `{diagnostic['near_duplicate_of']}` "
                f"(Jaccard {score:.3f})"
            )
    else:
        lines.append("Aucun.")

    lines += ["", "## 6. Lignes fréquentes non couvertes", ""]
    if frequent:
        lines += ["| Occurrences | Ligne |", "| ---: | --- |"]
        for count, line in frequent:
            escaped = line.replace("|", "\\|")
            lines.append(f"| {count} | {escaped} |")
    else:
        lines.append(
            f"Aucune ligne présente dans ≥ {FREQUENT_LINE_MIN} enregistrements "
            "hors motifs BOILERPLATE."
        )

    lines += ["", "## 7. Exemples avant / après", ""]
    for index, (category, diagnostic) in enumerate(examples, 1):
        lines += [
            f"### {index}. `{diagnostic['record_id']}` — {category}",
            "",
            f"- Format : `{diagnostic['format']}` · langue : `{diagnostic['language']}`",
            "",
        ]
        if diagnostic["removed"]:
            lines += ["**Segments supprimés**", ""]
            for segment in diagnostic["removed"]:
                lines += ["```text", segment, "```", ""]
        else:
            lines += ["**Segments supprimés**", "", "Aucun.", ""]
        lines += [
            "**Avant**",
            "",
            "```text",
            truncate(diagnostic["input_text"]),
            "```",
            "",
            "**Après**",
            "",
            "```text",
            truncate(diagnostic["cleaned_text"]),
            "```",
            "",
        ]

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------- I/O


def load_records(path: Path = INPUT) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def serialize(records: list[dict]) -> bytes:
    return "".join(
        json.dumps(record, ensure_ascii=False) + "\n" for record in records
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nettoyage, normalisation et déduplication du corpus SupportAI"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exécute et affiche les 7 contrôles automatiques",
    )
    args = parser.parse_args()

    records = load_records(INPUT)
    try:
        cleaned, diagnostics, duplicates = clean_all(records)
    except CleaningError as error:
        print(f"[ERREUR] {error}", file=sys.stderr)
        return 1

    controls = run_controls(records, cleaned, diagnostics, duplicates)
    examples = select_examples(diagnostics)
    frequent = frequent_lines(records)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(serialize(cleaned))
    report = build_report(records, cleaned, diagnostics, duplicates, controls, frequent, examples)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)

    print(f"{len(cleaned)} enregistrements nettoyés depuis {len(records)} en entrée")
    print(f"{display_path(OUTPUT)} : {len(cleaned)} lignes")
    print(f"{display_path(REPORT)} : généré")
    print(
        f"En-têtes supprimés : {sum(1 for d in diagnostics if d['removed'])} enregistrements, "
        f"{sum(len(d['removed']) for d in diagnostics)} segments"
    )
    print(
        f"Doublons exacts supprimés : {len(duplicates)} ; "
        f"quasi-doublons signalés : {sum(1 for d in diagnostics if d['near_duplicate_of'])}"
    )
    if args.check:
        for control in controls:
            status = "OK" if control["ok"] else "KO"
            print(f"[{status}] {control['id']}. {control['name']} — {control['value']}")
    if not all(control["ok"] for control in controls):
        print("[ERREUR] au moins un contrôle a échoué", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
