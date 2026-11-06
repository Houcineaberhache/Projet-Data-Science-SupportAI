#!/usr/bin/env python3
"""Pipeline d'ingestion documentaire SupportAI.

Lit les documents livrés dans ``data/processed/documents/`` (PDF, DOCX, FAQ JSON/JSONL/CSV),
extrait leur texte, le nettoie, conserve les métadonnées et exporte le tout
dans ``data/processed/extracted/documents.jsonl``.

Usage :
    python scripts/extract_documents.py [--input data/processed/documents] [--output data/processed/extracted/documents.jsonl]

Extracteurs utilisés, par ordre de préférence :

* PDF  : PyMuPDF (``fitz``) -> pdfplumber -> pypdf (repli sans dépendance)
* DOCX : python-docx -> analyse OOXML avec la bibliothèque standard
* FAQ  : json / jsonl / csv (bibliothèque standard)

Le script signale les PDF dont le texte est absent ou insuffisant et qui
nécessiteraient un OCR. Il n'effectue pas l'OCR lui-même.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "documents"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "extracted" / "documents.jsonl"
REPORT = ROOT / "docs" / "reports" / "extraction_report.md"

# Seuils de détection OCR.
OCR_MIN_CHARS = 40

CLEAN_STATS: Counter = Counter()


# ------------------------------------------------------------------ nettoyage


def clean_text(text: str) -> str:
    """Nettoie sans jamais supprimer d'information utile.

    Les accents, la ponctuation française (« » — ’ …) et les chiffres sont
    conservés tels quels : aucune normalisation Unicode destructive (NFKD,
    suppression des diacritiques) n'est appliquée.
    """
    if not text:
        return ""
    before = text

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for space in ("\u00a0", "\u202f", "\u2009", "\u2007", "\u2008"):
        if space in text:
            CLEAN_STATS["espaces_insécables_remplacés"] += text.count(space)
            text = text.replace(space, " ")
    for invisible in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"):
        if invisible in text:
            CLEAN_STATS["caractères_invisibles_supprimés"] += text.count(invisible)
            text = text.replace(invisible, "")
    for ligature, replacement in (("\ufb01", "fi"), ("\ufb02", "fl")):
        if ligature in text:
            CLEAN_STATS["ligatures_normalisées"] += text.count(ligature)
            text = text.replace(ligature, replacement)

    kept = []
    for char in text:
        if char in "\n\t" or ord(char) >= 32:
            kept.append(char)
        else:
            CLEAN_STATS["caractères_de_contrôle_supprimés"] += 1
    text = "".join(kept)

    def collapse(match: re.Match) -> str:
        if match.group(0) != " ":
            CLEAN_STATS["espaces_multiples_réduits"] += 1
        return " "

    text = re.sub(r"[ \t]+", collapse, text)

    def trim(match: re.Match) -> str:
        if match.group(0) != "\n":
            CLEAN_STATS["espaces_de_fin_de_ligne_supprimés"] += 1
        return "\n"

    text = re.sub(r" *\n *", trim, text)
    text, n_blanks = re.subn(r"\n{3,}", "\n\n", text)
    CLEAN_STATS["lignes_vides_réduites"] += n_blanks
    text = text.strip()

    if text != before:
        CLEAN_STATS["textes_modifiés"] += 1
    return text


# ----------------------------------------------------------------------- PDF


def pdf_extractor_name() -> str:
    for name, module in (("pymupdf", "fitz"), ("pdfplumber", "pdfplumber"), ("pypdf", "pypdf")):
        try:
            __import__(module)
            return name
        except Exception:
            continue
    raise RuntimeError("Aucun extracteur PDF disponible (pymupdf, pdfplumber ou pypdf).")


def pdf_has_images(page) -> bool:
    try:
        resources = page.get("/Resources")
        if not resources:
            return False
        xobjects = resources.get("/XObject")
        if not xobjects:
            return False
        for entry in xobjects.values():
            obj = entry.get_object()
            if obj.get("/Subtype") == "/Image":
                return True
    except Exception:
        return False
    return False


def extract_pdf(path: Path) -> tuple[list[dict], str]:
    name = pdf_extractor_name()
    pages: list[dict] = []

    if name == "pymupdf":
        import fitz  # type: ignore

        with fitz.open(path) as doc:
            for index, page in enumerate(doc, 1):
                text = clean_text(page.get_text("text"))
                images = bool(page.get_images(full=True))
                pages.append({"page": index, "text": text, "images": images})
    elif name == "pdfplumber":
        import pdfplumber  # type: ignore

        with pdfplumber.open(path) as doc:
            for index, page in enumerate(doc.pages, 1):
                text = clean_text(page.extract_text() or "")
                pages.append({"page": index, "text": text, "images": bool(page.images)})
    else:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        for index, page in enumerate(reader.pages, 1):
            try:
                raw = page.extract_text() or ""
            except Exception:
                raw = ""
            pages.append({"page": index, "text": clean_text(raw),
                          "images": pdf_has_images(page)})

    for page in pages:
        page["needs_ocr"] = len(page["text"]) < OCR_MIN_CHARS
        if page["needs_ocr"]:
            page["image_hint"] = page["images"]
    return pages, name


# ---------------------------------------------------------------------- DOCX


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_style(paragraph) -> str:
    node = paragraph.find(f"{W}pPr/{W}pStyle")
    return node.get(f"{W}val", "") if node is not None else ""


def docx_text(node) -> str:
    return "".join(t.text or "" for t in node.iter(f"{W}t")).strip()


def extract_docx_stdlib(path: Path) -> tuple[list[dict], str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{W}body")
    if body is None:
        return [], "ooxml-stdlib"

    elements: list[tuple[str, str, str]] = []
    for child in body:
        if child.tag == f"{W}p":
            text = docx_text(child)
            if text:
                elements.append(("p", docx_style(child), text))
        elif child.tag == f"{W}tbl":
            rows = []
            for row in child.iter(f"{W}tr"):
                cells = [docx_text(cell) for cell in row.iter(f"{W}tc")]
                rows.append(" | ".join(cells))
            if rows:
                elements.append(("table", "", "\n".join(rows)))
    return build_sections(elements), "ooxml-stdlib"


def extract_docx_python_docx(path: Path) -> tuple[list[dict], str]:
    import docx  # type: ignore
    from docx.table import Table  # type: ignore
    from docx.text.paragraph import Paragraph  # type: ignore

    document = docx.Document(str(path))
    elements: list[tuple[str, str, str]] = []
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            if item.text.strip():
                elements.append(("p", item.style.name or "", item.text.strip()))
        elif isinstance(item, Table):
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in item.rows]
            if rows:
                elements.append(("table", "", "\n".join(rows)))
    return build_sections(elements), "python-docx"


def build_sections(elements: list[tuple[str, str, str]]) -> list[dict]:
    """Regroupe les blocs DOCX en sections délimitées par les titres."""
    sections: list[dict] = []
    current = {"title": None, "level": 0, "lines": []}

    def flush() -> None:
        nonlocal current
        if current["title"] is None and not current["lines"]:
            return
        sections.append(current)
        current = {"title": None, "level": 0, "lines": []}

    for kind, style, text in elements:
        heading = "Heading" in style or style in {"Title", "Heading1", "Heading2"}
        if kind == "p" and heading:
            flush()
            current["title"] = text
            current["level"] = 1 if style in {"Title", "Heading1"} else 2
        else:
            current["lines"].append(text)
    flush()
    return sections


def extract_docx(path: Path) -> tuple[list[dict], str]:
    try:
        return extract_docx_python_docx(path)
    except Exception:
        return extract_docx_stdlib(path)


# ----------------------------------------------------------------------- FAQ


def extract_faq(path: Path) -> tuple[list[dict], str]:
    suffix = path.suffix.lower()
    items: list[dict] = []

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("questions") or payload.get("items") or []
            base = payload
        else:
            rows, base = payload, {}
        for row in rows:
            items.append({
                "id": row.get("id") or row.get("qid") or "",
                "question": row.get("question", ""),
                "answer": row.get("answer", ""),
                **{k: base.get(k) for k in ("doc_id", "language", "title", "category") if k in base},
            })
        return items, "json"

    if suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
        return items, "jsonl"

    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                items.append(row)
        return items, "csv"

    raise ValueError(f"Format FAQ non pris en charge : {path}")


# ----------------------------------------------------------------- métadonnées


def load_document_manifest(input_dir: Path) -> dict[str, dict]:
    path = input_dir / "manifest_documents.csv"
    if not path.exists():
        return {}
    index: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            index[Path(row["relative_path"]).as_posix()] = row
    return index


def coverage_ratios(records: list[dict], manifest: dict[str, dict]) -> list[tuple[dict, float]]:
    """Rapport mots extraits / mots source, par document."""
    source_words = {}
    for row in manifest.values():
        try:
            source_words[(row["doc_id"], row["language"])] = int(row["source_words"])
        except (KeyError, TypeError, ValueError):
            continue
    extracted: dict[tuple[str, str], int] = {}
    for item in records:
        key = (item["doc_id"], item["language"])
        extracted[key] = extracted.get(key, 0) + item["word_count"]
    ratios = []
    for key, words in extracted.items():
        source = source_words.get(key)
        if source:
            ratios.append(({"doc_id": key[0], "language": key[1],
                            "extracted": words, "source": source}, words / source))
    ratios.sort(key=lambda pair: pair[1])
    return ratios


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(**kwargs) -> dict:
    text = kwargs.get("text", "")
    kwargs["char_count"] = len(text)
    kwargs["word_count"] = len(text.split())
    return kwargs


# ----------------------------------------------------------------------- main


def build_records(input_dir: Path) -> tuple[list[dict], list[str], Counter, dict]:
    manifest = load_document_manifest(input_dir)
    extracted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    records: list[dict] = []
    failures: list[str] = []
    extractors: Counter = Counter()

    files = sorted(
        p for p in input_dir.rglob("*")
        if p.suffix.lower() in {".pdf", ".docx", ".json", ".jsonl", ".csv"}
        and p.name != "manifest_documents.csv"
    )

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        info = manifest.get(rel, {})
        doc_id = info.get("doc_id") or path.stem.split("_")[0]
        language = info.get("language") or ("en" if "_en" in path.stem else "fr")
        fmt = path.suffix.lstrip(".").lower()
        digest = sha256(path)

        common = {
            "doc_id": doc_id,
            "language": language,
            "format": fmt,
            "category": info.get("category", ""),
            "title": info.get("title", ""),
            "source_path": rel,
            "source_sha256": digest,
            "extracted_at": extracted_at,
        }

        try:
            if fmt == "pdf":
                units, extractor = extract_pdf(path)
                extractors[extractor] += 1
                for unit in units:
                    text = unit["text"]
                    warnings = []
                    if unit["needs_ocr"]:
                        warnings.append(
                            "texte_extractible_insuffisant:OCR_requis"
                            + (" (page image)" if unit.get("image_hint") else "")
                        )
                    records.append(record(
                        **common,
                        record_id=f"{doc_id}:{language}:{fmt}:p{unit['page']}",
                        unit_type="page", unit_id=f"p{unit['page']}",
                        page=unit["page"], section=None,
                        text=text, needs_ocr=unit["needs_ocr"], warnings=warnings,
                        extractor=extractor,
                    ))

            elif fmt == "docx":
                sections, extractor = extract_docx(path)
                extractors[extractor] += 1
                for index, section in enumerate(sections, 1):
                    title = section["title"]
                    body = "\n\n".join(line for line in section["lines"] if line)
                    text = (f"{title}\n\n{body}" if title else body).strip()
                    if not text:
                        continue
                    unit_type = "preamble" if title is None else "section"
                    records.append(record(
                        **common,
                        record_id=f"{doc_id}:{language}:{fmt}:s{index}",
                        unit_type=unit_type, unit_id=f"s{index}",
                        page=None, section=title,
                        text=text, needs_ocr=False, warnings=[],
                        extractor=extractor,
                    ))

            elif fmt in {"json", "jsonl", "csv"}:
                items, extractor = extract_faq(path)
                extractors[f"faq-{extractor}"] += 1
                for index, item in enumerate(items, 1):
                    question = clean_text(str(item.get("question", "")))
                    answer = clean_text(str(item.get("answer", "")))
                    if not question and not answer:
                        continue
                    qid = str(item.get("id") or f"q{index}")
                    records.append(record(
                        **common,
                        record_id=f"{doc_id}:{language}:{fmt}:{qid}",
                        unit_type="qa_pair", unit_id=qid,
                        page=None, section=question,
                        text=f"{question}\n\n{answer}".strip(),
                        needs_ocr=False, warnings=[],
                        extractor=extractor,
                        question=question, answer=answer,
                    ))
        except Exception as exc:  # pragma: no cover - remonté dans le rapport
            failures.append(f"{rel} : {type(exc).__name__} — {exc}")

    order = {"pdf": 0, "docx": 1, "json": 2, "jsonl": 3, "csv": 4}
    records.sort(key=lambda r: (r["doc_id"], r["language"], order.get(r["format"], 9),
                                r["page"] or 0, r["unit_id"]))
    return records, failures, extractors, manifest


def write_report(records: list[dict], failures: list[str], extractors: Counter,
                 output: Path, manifest: dict) -> None:
    by_format = Counter(r["format"] for r in records)
    docs = {(r["doc_id"], r["language"]) for r in records}
    ocr = [r for r in records if r["needs_ocr"]]
    empty = [r for r in records if not r["text"]]
    accents = [r for r in records if re.search(r"[àâäéèêëîïôöùûüçœ]", r["text"])]
    fr_records = [r for r in records if r["language"] == "fr"]
    duplicates = len(records) - len({r["text"] for r in records})

    lines = [
        "# Rapport d'extraction documentaire",
        "",
        "> Généré par `scripts/extract_documents.py`. Ne pas modifier à la main.",
        "",
        f"- Documents sources : **{len(docs)}** couples (doc_id, langue)",
        f"- Enregistrements extraits : **{len(records)}**",
        f"- Caractères extraits : **{sum(r['char_count'] for r in records):,}**".replace(",", " "),
        f"- Mots extraits : **{sum(r['word_count'] for r in records):,}**".replace(",", " "),
        f"- Échecs : **{len(failures)}**",
        "",
        "## Enregistrements par format",
        "",
        "| Format | Enregistrements |",
        "| --- | ---: |",
    ]
    for fmt, count in sorted(by_format.items()):
        lines.append(f"| {fmt} | {count} |")

    lines += ["", "## Extracteurs utilisés", "", "| Extracteur | Fichiers |", "| --- | ---: |"]
    for name, count in sorted(extractors.items()):
        lines.append(f"| {name} | {count} |")

    lines += [
        "",
        "## Contrôles",
        "",
        "| Contrôle | Résultat |",
        "| --- | --- |",
        f"| Enregistrements vides | {len(empty)} |",
        f"| Enregistrements avec accents | {len(accents)} / {len(records)} |",
        f"| Enregistrements FR avec accents | "
        f"{sum(1 for r in fr_records if re.search(r'[àâäéèêëîïôöùûüçœ]', r['text']))} / {len(fr_records)} |",
        f"| Textes strictement dupliqués | {duplicates} |",
        f"| Enregistrements nécessitant un OCR | {len(ocr)} |",
        "",
        "## Couverture texte extrait / source",
        "",
    ]
    ratios = coverage_ratios(records, manifest)
    if ratios:
        values = [ratio for _, ratio in ratios]
        values.sort()
        median = values[len(values) // 2]
        low = [pair for pair in ratios if pair[1] < 0.85]
        lines += [
            f"- Ratio minimal : **{min(values):.2f}**",
            f"- Ratio médian : **{median:.2f}**",
            f"- Documents sous 85 % : **{len(low)}**",
            "",
        ]
        if low:
            lines += ["| Document | Langue | Mots extraits | Mots source | Ratio |",
                      "| --- | --- | ---: | ---: | ---: |"]
            for item, ratio in low:
                lines.append(f"| {item['doc_id']} | {item['language']} | "
                             f"{item['extracted']} | {item['source']} | {ratio:.2f} |")
            lines.append("")

    lines += [
        "## Nettoyage appliqué",
        "",
        "| Opération | Occurrences |",
        "| --- | ---: |",
    ]
    for key in ("espaces_insécables_remplacés", "caractères_invisibles_supprimés",
                "ligatures_normalisées", "caractères_de_contrôle_supprimés",
                "espaces_multiples_réduits", "espaces_de_fin_de_ligne_supprimés",
                "lignes_vides_réduites", "textes_modifiés"):
        lines.append(f"| {key.replace('_', ' ')} | {CLEAN_STATS.get(key, 0)} |")

    lines += ["", "## Documents nécessitant un OCR", ""]
    if ocr:
        lines.append("| Document | Page | Caractères |")
        lines.append("| --- | ---: | ---: |")
        for item in ocr:
            lines.append(f"| {item['doc_id']} ({item['language']}) | {item['page']} "
                         f"| {item['char_count']} |")
    else:
        lines.append("Aucun : tous les PDF contiennent une couche de texte exploitable.")

    if failures:
        lines += ["", "## Échecs", ""]
        lines += [f"- {failure}" for failure in failures]

    lines += ["", f"Sortie : `{output.relative_to(ROOT).as_posix()}`", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(records)} enregistrements depuis {len(docs)} documents "
          f"({by_format['pdf']} pages PDF, {by_format['docx']} sections DOCX, "
          f"{by_format['json'] + by_format['jsonl'] + by_format['csv']} paires FAQ)")
    print(f"data/processed/extracted/documents.jsonl : {len(records)} lignes")
    print(f"docs/reports/extraction_report.md : généré")
    if ocr:
        print(f"[AVERTISSEMENT] {len(ocr)} page(s) nécessitent un OCR", file=sys.stderr)
    if failures:
        for failure in failures:
            print(f"[ERREUR] {failure}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extraction PDF / DOCX / FAQ -> JSONL")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    input_dir = args.input if args.input.is_absolute() else ROOT / args.input
    output = args.output if args.output.is_absolute() else ROOT / args.output

    if not input_dir.exists():
        print(f"[ERREUR] dossier absent : {input_dir}", file=sys.stderr)
        return 1

    records, failures, extractors, manifest = build_records(input_dir)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as fh:
        for item in records:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_report(records, failures, extractors, output, manifest)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
