#!/usr/bin/env python3
"""Génération des documents livrables aux formats demandés.

Le corpus Markdown de ``data/raw/corpus/{fr,en}`` reste la source de rédaction unique
(vérifiée par ``manage_corpus.py``). Ce script le distribue dans les formats
attendus par le pipeline d'ingestion :

* ``data/processed/documents/pdf/*.pdf``    : politiques et synthèses réglementaires
* ``data/processed/documents/docx/*.docx``  : procédures, opérations internes, guides produits
* ``data/processed/documents/faq/*.{json,jsonl,csv}`` : FAQ

Il produit aussi ``data/processed/documents/manifest_documents.csv`` (traçabilité
doc_id / langue / format / empreinte).

Usage :
    python scripts/build_sources.py

Dépendances : bibliothèque standard uniquement. Les fichiers PDF et DOCX sont
écrits directement au format OOXML / PDF 1.4, ce qui évite toute dépendance
externe et garantit un résultat reproductible.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "raw" / "corpus"
OUT = ROOT / "data" / "processed" / "documents"
LANGUAGES = ("fr", "en")

# Répartition des formats, par catégorie documentaire.
PDF_CATEGORIES = {"policies", "legal_summaries"}
DOCX_CATEGORIES = {"procedures", "internal_operations", "product_guides"}
FAQ_CATEGORIES = {"faq"}

# Les trois formats FAQ sont exercés : JSON, JSONL et CSV.
FAQ_FORMATS = {
    "FAQ-01": "json", "FAQ-02": "json", "FAQ-03": "json",
    "FAQ-04": "jsonl", "FAQ-05": "jsonl", "FAQ-06": "jsonl",
    "FAQ-07": "csv", "FAQ-08": "csv",
}

# Caractères hors cp1252 : remplacement explicite pour rester lisible.
PDF_TRANSLIT = {
    "\u2192": "->", "\u2190": "<-", "\u2198": "->", "\u2199": "<-",
    "\u2248": "~", "\u2265": ">=", "\u2264": "<=",
    "\u2713": "[x]", "\u2717": "[ ]",
}

WARNINGS: list[str] = []


# --------------------------------------------------------------------- lecture


def parse_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


def parse_markdown(body: str) -> list[tuple[str, object]]:
    """Découpe le corps Markdown en blocs typés (titre, paragraphe, liste, table)."""
    lines = body.splitlines()
    blocks: list[tuple[str, object]] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if not s:
            i += 1
            continue
        if s == "---":
            blocks.append(("hr", ""))
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", "\n".join(buf)))
            continue
        if s.startswith("### "):
            blocks.append(("h3", s[4:].strip()))
            i += 1
            continue
        if s.startswith("## "):
            blocks.append(("h2", s[3:].strip()))
            i += 1
            continue
        if s.startswith("# "):
            blocks.append(("h1", s[2:].strip()))
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", rows))
            continue
        if s.startswith("- ") or re.match(r"^\d+\.\s", s):
            ordered = bool(re.match(r"^\d+\.\s", s))
            items = []
            while i < len(lines):
                t = lines[i].strip()
                if t.startswith("- ") or re.match(r"^\d+\.\s", t):
                    items.append(t)
                    i += 1
                elif t and lines[i].startswith("  ") and not t.startswith("#"):
                    items[-1] += " " + t
                    i += 1
                else:
                    break
            blocks.append(("olist" if ordered else "list", items))
            continue
        if s.startswith("> "):
            blocks.append(("quote", s[2:].strip()))
            i += 1
            continue
        buf = [s]
        i += 1
        while i < len(lines):
            t = lines[i].strip()
            if (not t or t.startswith("#") or t.startswith("|") or t.startswith("```")
                    or t.startswith("- ") or t.startswith("> ")
                    or re.match(r"^\d+\.\s", t) or t == "---"):
                break
            buf.append(t)
            i += 1
        blocks.append(("p", " ".join(buf)))
    return blocks


def strip_inline(text: str) -> str:
    """Retire le balisage Markdown en conservant le texte."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    return text


def split_inline(text: str) -> list[tuple[str, bool]]:
    """Segmente un paragraphe en (texte, gras) pour DOCX."""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            out.append((part[2:-2], True))
        else:
            out.append((part, False))
    return out


# ------------------------------------------------------------------------ PDF


PAGE_W, PAGE_H = 595.28, 841.89
MARGIN = 50.0
TOP = PAGE_H - MARGIN
BOTTOM = MARGIN


def pdf_escape(text: str) -> bytes:
    text = text.translate(str.maketrans(PDF_TRANSLIT))
    data = text.encode("cp1252", errors="replace")
    if b"?" in data and "?" not in text:
        WARNINGS.append(f"caractère non représentable en cp1252 : {text[:60]!r}")
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def wrap(text: str, size: float, width: float, mono: bool = False) -> list[str]:
    char_w = size * (0.60 if mono else 0.50)
    max_chars = max(12, int(width / char_w))
    words = text.split()
    if not words:
        return [""]
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            current = word
    if current:
        lines.append(current)
    return lines


class PdfLayout:
    def __init__(self) -> None:
        self.pages: list[list[bytes]] = []
        self.current: list[bytes] = []
        self.y = TOP

    def _new_page(self) -> None:
        if self.current:
            self.pages.append(self.current)
        self.current = []
        self.y = TOP

    def _draw(self, text: str, font: str, size: float, x: float) -> None:
        self.current.append(
            b"BT /" + font.encode() + b" " + f"{size:.2f}".encode()
            + b" Tf 1 0 0 1 " + f"{x:.2f} {self.y:.2f}".encode()
            + b" Tm (" + pdf_escape(text) + b") Tj ET"
        )

    def line(self, text: str, font: str = "F1", size: float = 10.5,
             before: float = 0.0, indent: float = 0.0, mono: bool = False) -> None:
        leading = size * 1.55
        if self.y - before - leading < BOTTOM:
            self._new_page()
        self.y -= before
        wrapped = wrap(text, size, PAGE_W - 2 * MARGIN - indent, mono)
        for chunk in wrapped:
            if self.y - leading < BOTTOM:
                self._new_page()
            self.y -= leading
            self._draw(chunk, font, size, MARGIN + indent)

    def finish(self) -> list[list[bytes]]:
        if self.current:
            self.pages.append(self.current)
            self.current = []
        return self.pages


def make_pdf(page_lines: list[list[bytes]]) -> bytes:
    n = len(page_lines)
    page_ids = [6 + 2 * i for i in range(n)]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    }
    for i, lines in enumerate(page_lines):
        pid, cid = 6 + 2 * i, 7 + 2 * i
        objs[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            f"/Contents {cid} 0 R >>"
        ).encode()
        stream = b"\n".join(lines)
        objs[cid] = (b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                     + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for i in range(1, len(objs) + 1):
        offsets[i] = len(out)
        out += f"{i} 0 obj\n".encode() + objs[i] + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for i in range(1, len(objs) + 1):
        out += f"{offsets[i]:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def render_pdf(meta: dict, blocks: list[tuple[str, object]]) -> bytes:
    layout = PdfLayout()
    layout.line(meta["title"], font="F2", size=19, indent=0)
    subtitle = (f"Référence {meta['doc_id']} · version {meta['version']} · "
                f"entrée en vigueur {meta['effective_date']} · NovaShop")
    layout.line(subtitle, font="F1", size=9, before=6)
    layout.line("Document fictif — NovaShop est une société imaginaire créée pour "
                "le projet pédagogique SupportAI.", font="F1", size=8, before=4)

    for kind, payload in blocks:
        if kind == "h1":
            continue  # déjà rendu dans le titre
        elif kind == "h2":
            layout.line(strip_inline(str(payload)), font="F2", size=13.5, before=14)
        elif kind == "h3":
            layout.line(strip_inline(str(payload)), font="F2", size=11.5, before=9)
        elif kind == "p":
            layout.line(strip_inline(str(payload)), size=10.5, before=4)
        elif kind == "quote":
            layout.line(strip_inline(str(payload)), font="F1", size=9.5,
                        before=4, indent=18)
        elif kind == "list":
            for item in payload:  # type: ignore[union-attr]
                text = re.sub(r"^-\s+", "", item)
                layout.line("- " + strip_inline(text), size=10.5, before=1, indent=12)
        elif kind == "olist":
            for i, item in enumerate(payload, 1):  # type: ignore[union-attr]
                text = re.sub(r"^\d+\.\s+", "", item)
                layout.line(f"{i}. " + strip_inline(text), size=10.5, before=1, indent=12)
        elif kind == "table":
            for row_index, row in enumerate(payload):  # type: ignore[union-attr]
                cells = [strip_inline(c.strip()) for c in row.strip("|").split("|")]
                if all(set(c) <= {"-", ":", " "} for c in cells):
                    continue  # ligne de séparation Markdown
                text = " | ".join(cells)
                font = "F2" if row_index == 0 else "F1"
                layout.line(text, font=font, size=9, before=2, indent=6, mono=True)
            layout.line("", size=4, before=0)
        elif kind == "code":
            for line in str(payload).splitlines():
                layout.line(line, font="F3", size=8.5, before=0, indent=12, mono=True)
            layout.line("", size=4)
        elif kind == "hr":
            layout.line("_" * 60, size=8, before=6)
    return make_pdf(layout.finish())


# ----------------------------------------------------------------------- DOCX


DOCX_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {DOCX_NS}>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr></w:style>
</w:styles>"""


def run(text: str, bold: bool = False, code: bool = False) -> str:
    props = ""
    if bold or code:
        props = "<w:rPr>"
        if bold:
            props += "<w:b/>"
        if code:
            props += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
        props += "</w:rPr>"
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(content: str, style: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{props}{content}</w:p>"


def table_xml(rows: list[str]) -> str:
    grid: list[str] = []
    body: list[str] = []
    for row_index, row in enumerate(rows):
        cells = [strip_inline(c.strip()) for c in row.strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        if not grid:
            grid = ['<w:gridCol w:w="2400"/>' for _ in cells]
        tr = ["<w:tr>"]
        for cell in cells:
            tr.append('<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>'
                      + para(run(cell, bold=(row_index == 0))) + "</w:tc>")
        tr.append("</w:tr>")
        body.append("".join(tr))
    borders = ('<w:tblBorders><w:top w:val="single" w:sz="4" w:color="999999"/>'
               '<w:left w:val="single" w:sz="4" w:color="999999"/>'
               '<w:bottom w:val="single" w:sz="4" w:color="999999"/>'
               '<w:right w:val="single" w:sz="4" w:color="999999"/>'
               '<w:insideH w:val="single" w:sz="4" w:color="999999"/>'
               '<w:insideV w:val="single" w:sz="4" w:color="999999"/></w:tblBorders>')
    return (f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>{borders}</w:tblPr>'
            f'<w:tblGrid>{"".join(grid)}</w:tblGrid>{"".join(body)}</w:tbl>')


def render_docx(meta: dict, blocks: list[tuple[str, object]]) -> bytes:
    body: list[str] = [para(run(meta["title"], bold=True), "Title")]
    body.append(para(run(f"Référence {meta['doc_id']} · version {meta['version']} · "
                         f"entrée en vigueur {meta['effective_date']} · NovaShop")))
    body.append(para(run("Document fictif — NovaShop est une société imaginaire créée "
                         "pour le projet pédagogique SupportAI.")))

    for kind, payload in blocks:
        if kind == "h1":
            continue
        if kind == "h2":
            body.append(para(run(strip_inline(str(payload))), "Heading1"))
        elif kind == "h3":
            body.append(para(run(strip_inline(str(payload))), "Heading2"))
        elif kind == "p":
            body.append(para("".join(run(t, bold=b) for t, b in split_inline(str(payload)))))
        elif kind == "quote":
            body.append(para(run(strip_inline(str(payload)))))
        elif kind == "list":
            for item in payload:  # type: ignore[union-attr]
                text = re.sub(r"^-\s+", "", item)
                body.append(para(run("- " + strip_inline(text))))
        elif kind == "olist":
            for i, item in enumerate(payload, 1):  # type: ignore[union-attr]
                text = re.sub(r"^\d+\.\s+", "", item)
                body.append(para(run(f"{i}. " + strip_inline(text))))
        elif kind == "table":
            body.append(table_xml(payload))  # type: ignore[arg-type]
        elif kind == "code":
            for line in str(payload).splitlines():
                body.append(para(run(line, code=True), "Code"))
        elif kind == "hr":
            body.append(para(run("")))

    body.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>')
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<w:document {DOCX_NS}><w:body>{"".join(body)}</w:body></w:document>')

    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", ROOT_RELS)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
        zf.writestr("word/styles.xml", STYLES)
        zf.writestr("word/document.xml", document)
    return buffer.getvalue()


# ------------------------------------------------------------------------- FAQ


def extract_qa(meta: dict, blocks: list[tuple[str, object]]) -> list[dict]:
    items: list[dict] = []
    current_q: str | None = None
    answer: list[str] = []

    def flush() -> None:
        nonlocal current_q, answer
        if current_q is not None:
            items.append({
                "id": f"{meta['doc_id']}-Q{len(items) + 1:02d}",
                "question": strip_inline(current_q).strip(),
                "answer": strip_inline(" ".join(answer)).strip(),
            })
        current_q, answer = None, []

    for kind, payload in blocks:
        if kind in ("h1", "hr"):
            continue
        if kind == "h2":
            flush()
            current_q = str(payload)
        elif kind == "p":
            answer.append(str(payload))
        elif kind == "list":
            answer.append(" ".join(re.sub(r"^-\s+", "- ", i) for i in payload))  # type: ignore[arg-type]
        elif kind == "table":
            rows = []
            for row in payload:  # type: ignore[union-attr]
                cells = [c.strip() for c in row.strip("|").split("|")]
                if all(set(c) <= {"-", ":", " "} for c in cells):
                    continue
                rows.append(" | ".join(cells))
            answer.append(" ".join(rows))
    flush()
    return items


def write_faq(meta: dict, blocks: list[tuple[str, object]], fmt: str, target: Path) -> int:
    items = extract_qa(meta, blocks)
    base = {
        "doc_id": meta["doc_id"],
        "title": meta["title"],
        "language": meta["language"],
        "category": meta["category"],
        "version": meta["version"],
    }
    if fmt == "json":
        payload = dict(base, questions=items)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    elif fmt == "jsonl":
        with target.open("w", encoding="utf-8", newline="\n") as fh:
            for item in items:
                fh.write(json.dumps(dict(base, **item), ensure_ascii=False) + "\n")
    elif fmt == "csv":
        with target.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "doc_id", "language", "id", "title", "category", "version",
                "question", "answer"])
            writer.writeheader()
            for item in items:
                writer.writerow({**base, **item})
    else:  # pragma: no cover - garde-fou
        raise ValueError(fmt)
    return len(items)


# ----------------------------------------------------------------------- main


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    for sub in ("pdf", "docx", "faq"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    counters = {"pdf": 0, "docx": 0, "json": 0, "jsonl": 0, "csv": 0}

    for language in LANGUAGES:
        for path in sorted((CORPUS / language).glob("*.md")):
            meta, body = parse_front_matter(path)
            if not meta:
                print(f"[ERREUR] front matter absent : {path}", file=sys.stderr)
                return 1
            meta["language"] = language
            blocks = parse_markdown(body)
            category = meta["category"]
            stem = path.stem

            if category in FAQ_CATEGORIES:
                fmt = FAQ_FORMATS.get(meta["doc_id"], "json")
                target = OUT / "faq" / language / f"{stem}.{fmt}"
                target.parent.mkdir(parents=True, exist_ok=True)
                units = write_faq(meta, blocks, fmt, target)
                data = target.read_bytes()
                counters[fmt] += 1
            elif category in PDF_CATEGORIES:
                data = render_pdf(meta, blocks)
                target = OUT / "pdf" / language / f"{stem}.pdf"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                units = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
                counters["pdf"] += 1
            elif category in DOCX_CATEGORIES:
                data = render_docx(meta, blocks)
                target = OUT / "docx" / language / f"{stem}.docx"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                units = sum(1 for k, _ in blocks if k == "h2")
                counters["docx"] += 1
            else:
                print(f"[ERREUR] catégorie inconnue : {category} ({path})", file=sys.stderr)
                return 1

            manifest.append({
                "doc_id": meta["doc_id"],
                "language": language,
                "format": target.suffix.lstrip("."),
                "relative_path": target.relative_to(ROOT).as_posix(),
                "source_path": path.relative_to(ROOT).as_posix(),
                "title": meta["title"],
                "category": category,
                "units": units,
                "source_words": len(body.split()),
                "size_bytes": len(data),
                "sha256": sha256_bytes(data),
            })

    manifest_path = OUT / "manifest_documents.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        writer.writeheader()
        writer.writerows(manifest)

    print(f"data/processed/documents/ : {len(manifest)} fichiers "
          f"({counters['pdf']} PDF, {counters['docx']} DOCX, "
          f"{counters['json'] + counters['jsonl'] + counters['csv']} FAQ "
          f"= {counters['json']} json + {counters['jsonl']} jsonl + {counters['csv']} csv)")
    print(f"data/processed/documents/manifest_documents.csv : {len(manifest)} lignes")
    for warning in sorted(set(WARNINGS)):
        print(f"[AVERTISSEMENT] {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
