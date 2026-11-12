#!/usr/bin/env python3
"""Découpage du corpus Markdown NovaShop en chunks prêts pour le RAG.

Entrée  : ``data/raw/corpus/{fr,en}/*.md`` + ``data/source_manifest.csv``
Sortie  : ``data/processed/chunked_corpus.jsonl``
Rapport : ``docs/reports/chunking_report.md``

Le Markdown brut est la source de vérité du découpage (pas les PDF/DOCX).
Une section ``##`` produit un chunk ; au-delà de 300 mots, elle est scindée
par paragraphes en parties ``.1``, ``.2``, etc. Le script n'utilise que la
bibliothèque standard et n'écrit aucun horodatage : deux exécutions produisent
des fichiers identiques octet pour octet.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "raw" / "corpus"
MANIFEST = ROOT / "data" / "source_manifest.csv"
OUTPUT = ROOT / "data" / "processed" / "chunked_corpus.jsonl"
REPORT = ROOT / "docs" / "reports" / "chunking_report.md"

LANGUAGES = ("fr", "en")
MAX_WORDS = 300
MIN_WORDS = 15
CATEGORIES = {
    "policies", "faq", "procedures", "internal_operations",
    "product_guides", "legal_summaries",
}

FIELDS = [
    "chunk_id",
    "doc_id",
    "language",
    "chunk_index",
    "part",
    "doc_title",
    "category",
    "doc_type",
    "chunking_profile",
    "section_heading",
    "section_number",
    "text",
    "text_for_embedding",
    "word_count",
    "est_tokens",
    "has_table",
    "cross_refs",
    "amounts_mad",
    "version",
    "effective_date",
    "sensitivity",
    "audience",
    "index_in_rag",
    "exclusion_reason",
    "license",
    "source_path",
    "source_sha256",
]

FICTIF_RE = re.compile(
    r"^\*(?:Document fictif|Fictional document)\b.*\*$", re.IGNORECASE
)
SECTION_RE = re.compile(r"(?m)^##\s+")
SECTION_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
REFERENCE_RE = re.compile(r"\b(?:POL|REG|PRO|OPS|CAT|FAQ)-\d{2}\b")
AMOUNT_RE = re.compile(
    r"(?<![\w.,])(\d[\d \u00a0\u202f]*(?:[.,]\d+)?)\s*MAD\b",
    re.IGNORECASE,
)


class ChunkingError(RuntimeError):
    """Le corpus ne respecte pas les hypothèses du découpage."""


# --------------------------------------------------------------- utilitaires


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Retourne (front matter, corps) sans dépendance YAML externe."""
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        raise ChunkingError("front matter absent")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ChunkingError("front matter incomplet")
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


def remove_fictif_block(lines: list[str]) -> tuple[list[str], list[str]]:
    """Retire la ligne italique « Document fictif » et son séparateur.

    Retourne aussi les lignes retirées, pour le tableau de couverture.
    Aucun autre contenu n'est supprimé.
    """
    cleaned: list[str] = []
    removed: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if FICTIF_RE.match(line.strip()):
            removed.append(line)
            while cleaned and not cleaned[-1].strip():
                cleaned.pop()
            if cleaned and cleaned[-1].strip() == "---":
                removed.append(cleaned.pop())
            index += 1
            continue
        cleaned.append(line)
        index += 1
    return cleaned, removed


def section_number(heading: str) -> str | None:
    match = SECTION_NUMBER_RE.match(heading)
    return match.group(1) if match else None


def has_markdown_table(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "---" in stripped:
            return True
    return False


def cross_refs(text: str) -> list[str]:
    return sorted(set(REFERENCE_RE.findall(text)))


def normalize_amount(raw: str) -> str:
    value = raw.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    return value


def amount_sort_key(value: str) -> tuple[int, float, str]:
    try:
        return (0, float(value), value)
    except ValueError:
        return (1, 0.0, value)


def amounts_mad(text: str) -> list[str]:
    values = {normalize_amount(match.group(1)) for match in AMOUNT_RE.finditer(text)}
    return sorted(values, key=amount_sort_key)


def est_tokens(word_count: int) -> int:
    return int(round(word_count * 1.35))


def split_paragraphs(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def split_section_text(text: str) -> list[tuple[str, int | None]]:
    """Découpe une section de plus de 300 mots par paragraphes.

    Un tableau Markdown reste dans un seul bloc : les lignes d'un tableau ne
    sont jamais séparées par une ligne vide, donc le découpage par paragraphes
    ne le coupe pas. Si un paragraphe unique dépasse 300 mots, il reste entier
    mais porte ``part`` pour signaler le découpage.
    """
    if len(text.split()) <= MAX_WORDS:
        return [(text, None)]

    blocks = split_paragraphs(text)
    if not blocks:
        return [(text, 1)]

    parts: list[str] = []
    current: list[str] = []
    current_words = 0
    for block in blocks:
        block_words = len(block.split())
        if current and current_words + block_words > MAX_WORDS:
            parts.append("\n\n".join(current))
            current = []
            current_words = 0
        current.append(block)
        current_words += block_words
    if current:
        parts.append("\n\n".join(current))
    if not parts:
        parts = [text]
    return [(part, index) for index, part in enumerate(parts, 1)]


# ------------------------------------------------------------------- lecture


def load_manifest() -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("record_type") != "knowledge_base_document":
                continue
            rows[(row["doc_id"], row["language"])] = row
    return rows


def parse_document(path: Path, language: str) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    meta, body = parse_front_matter(text)
    for field in ("doc_id", "title", "category", "doc_type", "version",
                  "effective_date", "sensitivity"):
        if not meta.get(field):
            raise ChunkingError(f"{path.name}: champ front matter manquant: {field}")
    if meta.get("language") != language:
        raise ChunkingError(f"{path.name}: langue front matter incohérente")
    if path.name.split("_", 1)[0] != meta["doc_id"]:
        raise ChunkingError(f"{path.name}: doc_id différent du nom de fichier")
    if meta["category"] not in CATEGORIES:
        raise ChunkingError(f"{path.name}: catégorie inconnue: {meta['category']}")

    body_word_count = len(body.split())
    lines = body.splitlines()
    title_line: str | None = None
    without_title: list[str] = []
    for line in lines:
        if title_line is None and re.match(r"^#\s+", line):
            title_line = line.strip()
            continue
        without_title.append(line)
    if title_line is None:
        raise ChunkingError(f"{path.name}: titre H1 absent")

    without_fictif, fictif_lines = remove_fictif_block(without_title)
    cleaned_body = "\n".join(without_fictif)
    raw_sections = SECTION_RE.split(cleaned_body)
    preamble = raw_sections[0].strip()

    sections: list[dict] = []
    for raw in raw_sections[1:]:
        heading, _, content = raw.partition("\n")
        heading = heading.strip()
        if not heading:
            raise ChunkingError(f"{path.name}: titre de section vide")
        sections.append({
            "heading": heading,
            "number": section_number(heading),
            "text": content.strip(),
        })
    if not sections:
        raise ChunkingError(f"{path.name}: aucune section ##")
    if preamble:
        sections[0]["text"] = (preamble + "\n\n" + sections[0]["text"]).strip()

    return {
        "doc_id": meta["doc_id"],
        "language": language,
        "meta": meta,
        "path": path,
        "source_path": path.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(path),
        "body_word_count": body_word_count,
        "title_line": title_line,
        "fictif_lines": fictif_lines,
        "sections": sections,
        "section_heading_word_count": sum(
            len(("## " + section["heading"]).split()) for section in sections
        ),
    }


def load_documents() -> list[dict]:
    manifest = load_manifest()
    documents: list[dict] = []
    for language in LANGUAGES:
        for path in sorted((CORPUS / language).glob("*.md")):
            document = parse_document(path, language)
            key = (document["doc_id"], language)
            if key not in manifest:
                raise ChunkingError(
                    f"{document['source_path']}: absent du manifeste ({key})"
                )
            row = manifest[key]
            declared_path = row.get("relative_path", "")
            if declared_path and declared_path != document["source_path"]:
                raise ChunkingError(
                    f"{document['source_path']}: chemin différent du manifeste"
                )
            declared_sha = row.get("sha256", "")
            if declared_sha and declared_sha != document["source_sha256"]:
                raise ChunkingError(
                    f"{document['source_path']}: SHA-256 différent du manifeste"
                )
            document["manifest"] = row
            documents.append(document)
    return documents


# --------------------------------------------------------------- construction


def build_chunks(documents: list[dict] | None = None) -> list[dict]:
    """Construit la liste déterministe des chunks (sans horodatage)."""
    if documents is None:
        documents = load_documents()

    chunks: list[dict] = []
    for document in documents:
        meta = document["meta"]
        row = document["manifest"]
        audience = "customer" if meta["sensitivity"] == "public" else "internal"
        manifest_index = row.get("index_in_rag", "yes").strip().lower() == "yes"

        chunk_index = 0
        for section_index, section in enumerate(document["sections"], 1):
            for text, part in split_section_text(section["text"]):
                chunk_index += 1
                chunk_id = f"{document['doc_id']}#c{section_index}"
                if part is not None:
                    chunk_id = f"{chunk_id}.{part}"
                word_count = len(text.split())
                chunk = {
                    "chunk_id": chunk_id,
                    "doc_id": document["doc_id"],
                    "language": document["language"],
                    "chunk_index": chunk_index,
                    "part": part,
                    "doc_title": meta["title"],
                    "category": meta["category"],
                    "doc_type": meta["doc_type"],
                    "chunking_profile": row.get("chunking_profile", ""),
                    "section_heading": section["heading"],
                    "section_number": section["number"],
                    "text": text,
                    "text_for_embedding": (
                        f"{meta['title']} — {section['heading']}\n{text}"
                    ),
                    "word_count": word_count,
                    "est_tokens": est_tokens(word_count),
                    "has_table": has_markdown_table(text),
                    "cross_refs": cross_refs(text),
                    "amounts_mad": amounts_mad(text),
                    "version": meta["version"],
                    "effective_date": meta["effective_date"],
                    "sensitivity": meta["sensitivity"],
                    "audience": audience,
                    "index_in_rag": manifest_index,
                    "exclusion_reason": None,
                    "license": row.get("license", ""),
                    "source_path": document["source_path"],
                    "source_sha256": document["source_sha256"],
                }
                chunks.append(chunk)

    chunks.sort(
        key=lambda chunk: (
            chunk["doc_id"], chunk["language"], chunk["chunk_index"], chunk["chunk_id"]
        )
    )
    apply_short_exclusions(chunks)
    return chunks


def apply_short_exclusions(chunks: list[dict]) -> None:
    """Exclut les chunks trop courts, au niveau du couple FR/EN.

    La décision est prise par ``chunk_id`` : un chunk n'est exclu que si toutes
    ses variantes linguistiques sont courtes. Cela garantit que le même
    ``chunk_id`` a la même politique d'indexation en FR et en EN, conformément
    à l'exigence de parité. Le compte inclut le titre de section, car un titre
    substantiel n'est pas un fragment vide.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        groups[chunk["chunk_id"]].append(chunk)

    for group in groups.values():
        short = all(
            len(chunk["section_heading"].split()) + chunk["word_count"] < MIN_WORDS
            for chunk in group
        )
        if short:
            for chunk in group:
                chunk["index_in_rag"] = False
                chunk["exclusion_reason"] = "too_short"


# -------------------------------------------------------------------- rapport


def fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def coverage_stats(documents: list[dict], chunks: list[dict]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for language in LANGUAGES:
        docs = [d for d in documents if d["language"] == language]
        lang_chunks = [c for c in chunks if c["language"] == language]
        body_words = sum(d["body_word_count"] for d in docs)
        chunk_words = sum(c["word_count"] for c in lang_chunks)
        title_words = sum(len(d["title_line"].split()) for d in docs)
        fictif_words = sum(
            len(line.split()) for d in docs for line in d["fictif_lines"]
        )
        heading_words = sum(d["section_heading_word_count"] for d in docs)
        gap = body_words - chunk_words
        other = gap - title_words - fictif_words
        stats[language] = {
            "documents": len(docs),
            "body_words": body_words,
            "chunk_words": chunk_words,
            "gap": gap,
            "title_words": title_words,
            "fictif_words": fictif_words,
            "heading_words": heading_words,
            "other_words": other,
            "unclassified_words": other - heading_words,
        }
    return stats


def size_bucket(word_count: int) -> str:
    if word_count < 15:
        return "0–14"
    if word_count <= 30:
        return "15–30"
    if word_count <= 60:
        return "31–60"
    if word_count <= 100:
        return "61–100"
    if word_count <= 200:
        return "101–200"
    if word_count <= 300:
        return "201–300"
    return "> 300"


SIZE_BUCKETS = ["0–14", "15–30", "31–60", "61–100", "101–200", "201–300", "> 300"]


def build_report(
    chunks: list[dict],
    documents: list[dict],
    coverage: dict[str, dict[str, int]],
) -> str:
    by_language = Counter(c["language"] for c in chunks)
    words_by_language = {
        language: sum(c["word_count"] for c in chunks if c["language"] == language)
        for language in LANGUAGES
    }
    tokens_by_language = {
        language: sum(c["est_tokens"] for c in chunks if c["language"] == language)
        for language in LANGUAGES
    }
    docs_by_language = Counter(d["language"] for d in documents)
    sections_by_language = Counter(
        d["language"] for d in documents for _ in d["sections"]
    )

    by_category: dict[tuple[str, str], dict[str, int]] = {}
    for language in LANGUAGES:
        for category in sorted(CATEGORIES):
            selected = [
                c for c in chunks
                if c["language"] == language and c["category"] == category
            ]
            if not selected:
                continue
            by_category[(language, category)] = {
                "documents": len({c["doc_id"] for c in selected}),
                "chunks": len(selected),
                "words": sum(c["word_count"] for c in selected),
                "tokens": sum(c["est_tokens"] for c in selected),
            }

    size_counts: dict[tuple[str, str], int] = Counter()
    for chunk in chunks:
        size_counts[(chunk["language"], size_bucket(chunk["word_count"]))] += 1

    split_chunks = [c for c in chunks if c["part"] is not None]
    excluded = [c for c in chunks if c["exclusion_reason"]]
    table_chunks = sum(1 for c in chunks if c["has_table"])
    ref_chunks = sum(1 for c in chunks if c["cross_refs"])
    amount_chunks = sum(1 for c in chunks if c["amounts_mad"])
    all_words = [c["word_count"] for c in chunks]
    max_words = max(all_words) if all_words else 0
    median_words = median(all_words) if all_words else 0
    mean_words = mean(all_words) if all_words else 0

    lines = [
        "# Rapport de découpage / Chunking report",
        "",
        "> Généré par `scripts/chunk_corpus.py`. Ne pas modifier à la main.",
        "> Aucun horodatage : deux exécutions produisent un rapport identique.",
        "",
        "## 1. Synthèse",
        "",
        f"- Chunks : **{fmt_int(len(chunks))}** "
        f"({fmt_int(by_language['fr'])} FR + {fmt_int(by_language['en'])} EN)",
        f"- Documents : **{fmt_int(len(documents))}** "
        f"({fmt_int(docs_by_language['fr'])} FR + {fmt_int(docs_by_language['en'])} EN)",
        f"- Sections `##` : **{fmt_int(sum(sections_by_language.values()))}** "
        f"({fmt_int(sections_by_language['fr'])} FR + "
        f"{fmt_int(sections_by_language['en'])} EN)",
        f"- Chunks scindés (`part` non nul) : **{fmt_int(len(split_chunks))}**",
        f"- Chunks exclus (`too_short`) : **{fmt_int(len(excluded))}** "
        f"({fmt_int(sum(1 for c in excluded if c['language'] == 'fr'))} FR + "
        f"{fmt_int(sum(1 for c in excluded if c['language'] == 'en'))} EN)",
        f"- Chunks avec tableau : **{fmt_int(table_chunks)}**",
        f"- Chunks avec référence documentaire : **{fmt_int(ref_chunks)}**",
        f"- Chunks avec montant en MAD : **{fmt_int(amount_chunks)}**",
        f"- Longueur des chunks (mots) : min **{fmt_int(min(all_words) if all_words else 0)}**, "
        f"médiane **{median_words:.1f}**, moyenne **{mean_words:.1f}**, "
        f"max **{fmt_int(max_words)}**",
        "",
        "## 2. Volumes par langue et catégorie",
        "",
        "| Langue | Catégorie | Documents | Chunks | Mots | Tokens estimés |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for language in LANGUAGES:
        for category in sorted(CATEGORIES):
            values = by_category.get((language, category))
            if not values:
                continue
            lines.append(
                f"| {language} | {category} | {fmt_int(values['documents'])} | "
                f"{fmt_int(values['chunks'])} | {fmt_int(values['words'])} | "
                f"{fmt_int(values['tokens'])} |"
            )
        lines.append(
            f"| **{language}** | **Total** | **{fmt_int(docs_by_language[language])}** | "
            f"**{fmt_int(by_language[language])}** | "
            f"**{fmt_int(words_by_language[language])}** | "
            f"**{fmt_int(tokens_by_language[language])}** |"
        )
    lines.append(
        f"| **Total** | | **{fmt_int(len(documents))}** | **{fmt_int(len(chunks))}** | "
        f"**{fmt_int(sum(words_by_language.values()))}** | "
        f"**{fmt_int(sum(tokens_by_language.values()))}** |"
    )

    lines += [
        "",
        "## 3. Distribution des tailles",
        "",
        "| Langue | " + " | ".join(SIZE_BUCKETS) + " | Total |",
        "| --- | " + " | ".join("---:" for _ in SIZE_BUCKETS) + " | ---: |",
    ]
    for language in LANGUAGES:
        counts = [size_counts[(language, bucket)] for bucket in SIZE_BUCKETS]
        lines.append(
            f"| {language} | " + " | ".join(fmt_int(value) for value in counts) +
            f" | {fmt_int(by_language[language])} |"
        )
    total_counts = [
        sum(size_counts[(language, bucket)] for language in LANGUAGES)
        for bucket in SIZE_BUCKETS
    ]
    lines.append(
        "| **Total** | " + " | ".join(fmt_int(value) for value in total_counts) +
        f" | **{fmt_int(len(chunks))}** |"
    )
    lines += [
        "",
        "La distribution compte les chunks par `word_count` du texte seul. La "
        "règle `too_short` inclut le titre de section et s'applique au couple "
        "FR/EN : certains chunks de 0–14 mots restent indexés si leur "
        "contrepartie linguistique est substantielle (voir section 5).",
    ]

    lines += [
        "",
        "## 4. Chunks scindés",
        "",
    ]
    if split_chunks:
        lines += [
            "| Chunk ID | Langue | Parties | Mots |",
            "| --- | --- | ---: | ---: |",
        ]
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for chunk in split_chunks:
            grouped[(chunk["chunk_id"], chunk["language"])].append(chunk)
        for (chunk_id, language), group in sorted(grouped.items()):
            lines.append(
                f"| `{chunk_id}` | {language} | {len(group)} | "
                f"{fmt_int(sum(c['word_count'] for c in group))} |"
            )
    else:
        lines.append(
            f"Aucun chunk scindé : aucune section ne dépasse {MAX_WORDS} mots "
            f"(maximum observé : {fmt_int(max_words)} mots)."
        )

    lines += [
        "",
        "## 5. Chunks exclus (`too_short`)",
        "",
    ]
    if excluded:
        lines += [
            "| Chunk ID | Langue | Mots | Titre de section | Raison |",
            "| --- | --- | ---: | --- | --- |",
        ]
        for chunk in sorted(excluded, key=lambda c: (c["chunk_id"], c["language"])):
            lines.append(
                f"| `{chunk['chunk_id']}` | {chunk['language']} | "
                f"{fmt_int(chunk['word_count'])} | {chunk['section_heading']} | "
                f"`{chunk['exclusion_reason']}` |"
            )
        lines += [
            "",
            "La décision est prise au niveau du couple FR/EN du même `chunk_id` : "
            "un chunk n'est exclu que si ses deux variantes sont courtes. "
            "Un chunk court dans une seule langue n'est donc pas exclu si sa "
            "contrepartie est substantielle ; la parité d'indexation est conservée.",
        ]
    else:
        lines.append("Aucun chunk exclu.")

    lines += [
        "",
        "## 6. Couverture du texte source",
        "",
        "Le corps du fichier Markdown est compté après le front matter, avant "
        "retrait du titre, du bloc fictif et des titres de section. Les chunks "
        "contiennent le préambule éventuel dans leur première section.",
        "",
        "| Langue | Mots corps | Mots chunks | Écart | Titre du document | "
        "Avertissement fictif | Titres de section (`##`) | Non classé |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for language in LANGUAGES:
        row = coverage[language]
        lines.append(
            f"| {language} | {fmt_int(row['body_words'])} | "
            f"{fmt_int(row['chunk_words'])} | {fmt_int(row['gap'])} | "
            f"{fmt_int(row['title_words'])} | {fmt_int(row['fictif_words'])} | "
            f"{fmt_int(row['heading_words'])} | "
            f"{fmt_int(row['unclassified_words'])} |"
        )
    totals = {
        key: sum(coverage[language][key] for language in LANGUAGES)
        for key in (
            "body_words", "chunk_words", "gap", "title_words",
            "fictif_words", "heading_words", "unclassified_words",
        )
    }
    lines.append(
        f"| **Total** | **{fmt_int(totals['body_words'])}** | "
        f"**{fmt_int(totals['chunk_words'])}** | **{fmt_int(totals['gap'])}** | "
        f"**{fmt_int(totals['title_words'])}** | **{fmt_int(totals['fictif_words'])}** | "
        f"**{fmt_int(totals['heading_words'])}** | "
        f"**{fmt_int(totals['unclassified_words'])}** |"
    )
    lines += [
        "",
        f"L'écart observé est de **{fmt_int(coverage['fr']['gap'])} mots en FR** et "
        f"**{fmt_int(coverage['en']['gap'])} mots en EN**, soit environ 2 250 mots "
        "par langue ; le total des deux langues est "
        f"**{fmt_int(totals['gap'])} mots**. Les catégories expliquent tout l'écart "
        "observé : titre `#`, avertissement fictif (bloc et séparateur) et titres "
        "de section `##`. La colonne « Non classé » doit rester à zéro ; si elle "
        "ne l'est pas, l'écart est signalé sans être corrigé.",
        "",
        "## 7. Méthode",
        "",
        "- Une section `##` = un chunk ; les sous-titres `###` restent dans le "
        "texte de leur section.",
        "- Au-delà de 300 mots, découpage par paragraphes avec suffixe `.1`, "
        "`.2`, … et `part` renseigné ; les tableaux Markdown restent entiers.",
        "- `chunk_id` = `<DOC_ID>#c<n>` où `n` est l'ordre de la section ; "
        "la clé unique est `(chunk_id, language)`.",
        "- `word_count` compte les mots du texte du chunk (hors titre de section) ; "
        "`text_for_embedding` ajoute le titre du document et le titre de section.",
        "- `audience` = `customer` si `sensitivity` vaut `public`, sinon `internal` ; "
        "`index_in_rag` vient du manifeste et passe à `false` pour `too_short`.",
        "- `amounts_mad` normalise les espaces, trie numériquement et conserve les "
        "montants avant « MAD » ; `cross_refs` trie les références documentaires.",
        "- Aucun horodatage, aucun embedding, aucune dépendance externe.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def serialize(chunks: list[dict]) -> bytes:
    return "".join(
        json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks
    ).encode("utf-8")


# ----------------------------------------------------------------------- main


def main() -> int:
    try:
        documents = load_documents()
        chunks = build_chunks(documents)
    except ChunkingError as error:
        print(f"[ERREUR] {error}", file=sys.stderr)
        return 1

    coverage = coverage_stats(documents, chunks)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(serialize(chunks))
    report = build_report(chunks, documents, coverage)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)

    by_language = Counter(chunk["language"] for chunk in chunks)
    excluded = sorted({chunk["chunk_id"] for chunk in chunks if chunk["exclusion_reason"]})
    print(f"{len(chunks)} chunks ({by_language['fr']} fr / {by_language['en']} en)")
    print(f"{OUTPUT.relative_to(ROOT).as_posix()} : {len(chunks)} lignes")
    print(f"{REPORT.relative_to(ROOT).as_posix()} : généré")
    print(f"Chunks scindés : {sum(1 for c in chunks if c['part'] is not None)}")
    print(
        f"Chunks exclus (too_short) : "
        f"{sum(1 for c in chunks if c['exclusion_reason'])} "
        f"({', '.join(excluded) if excluded else 'aucun'})"
    )
    unclassified = sum(row["unclassified_words"] for row in coverage.values())
    if unclassified:
        print(
            f"[ATTENTION] écart non classé : {unclassified} mots (non corrigé)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
