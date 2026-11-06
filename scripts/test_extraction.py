#!/usr/bin/env python3
"""Tests du nettoyage et des extracteurs du pipeline documentaire.

Usage :
    python scripts/test_extraction.py
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sources import PdfLayout, make_pdf, render_docx  # noqa: E402
from extract_documents import (  # noqa: E402
    clean_text, extract_docx, extract_faq, extract_pdf,
)

META = {
    "doc_id": "TST-01", "title": "Document de test", "category": "procedures",
    "doc_type": "procedure", "language": "fr", "version": "1.0",
    "effective_date": "2026-11-06",
}


class CleanTextTests(unittest.TestCase):
    def test_espaces_insecables(self) -> None:
        self.assertEqual(clean_text("39\u00a0MAD\u202f!"), "39 MAD !")

    def test_caracteres_invisibles(self) -> None:
        self.assertEqual(clean_text("re\u200btour\u200d"), "retour")

    def test_caracteres_de_controle(self) -> None:
        self.assertEqual(clean_text("a\x07b\x00c"), "abc")

    def test_espaces_et_lignes(self) -> None:
        self.assertEqual(clean_text("  a   b  \n\n\n\n  c  "), "a b\n\nc")

    def test_accents_conserves(self) -> None:
        text = "échéance, rétractation, œuvre, garçon, naïve"
        self.assertEqual(clean_text(text), text)

    def test_ponctuation_francaise_conservee(self) -> None:
        text = "Le délai « légal » — 14 jours…"
        self.assertEqual(clean_text(text), text)

    def test_valeurs_metier_conservees(self) -> None:
        text = "Retour 14 jours · 39 MAD · 5 % · 7 à 15 jours ouvrés"
        self.assertEqual(clean_text(text), text)

    def test_texte_vide(self) -> None:
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text("   \n\t "), "")


class FaqTests(unittest.TestCase):
    ITEMS = [
        {"id": "Q1", "question": "Question une ?", "answer": "Réponse une."},
        {"id": "Q2", "question": "Question deux ?", "answer": "Réponse deux."},
    ]

    def test_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "faq.json"
            path.write_text(json.dumps({"doc_id": "FAQ-01", "language": "fr",
                                        "questions": self.ITEMS}, ensure_ascii=False),
                            encoding="utf-8")
            items, extractor = extract_faq(path)
            self.assertEqual(extractor, "json")
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["answer"], "Réponse une.")

    def test_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "faq.jsonl"
            path.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in self.ITEMS),
                            encoding="utf-8")
            items, extractor = extract_faq(path)
            self.assertEqual(extractor, "jsonl")
            self.assertEqual(len(items), 2)

    def test_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "faq.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["id", "question", "answer"])
                writer.writeheader()
                writer.writerows(self.ITEMS)
            items, extractor = extract_faq(path)
            self.assertEqual(extractor, "csv")
            self.assertEqual(len(items), 2)


class PdfTests(unittest.TestCase):
    def test_extraction_et_pages(self) -> None:
        layout = PdfLayout()
        layout.line("Bonjour, délai de 14 jours.")
        layout.line("Deuxième ligne avec accents : é è ç.")
        data = make_pdf(layout.finish())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.pdf"
            path.write_bytes(data)
            pages, extractor = extract_pdf(path)
            self.assertIn(extractor, {"pymupdf", "pdfplumber", "pypdf"})
            self.assertEqual(len(pages), 1)
            self.assertFalse(pages[0]["needs_ocr"])
            self.assertIn("14 jours", pages[0]["text"])
            self.assertIn("é", pages[0]["text"])

    def test_detection_ocr(self) -> None:
        data = make_pdf([[]])  # page sans aucun texte
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vide.pdf"
            path.write_bytes(data)
            pages, _ = extract_pdf(path)
            self.assertTrue(pages[0]["needs_ocr"])


class DocxTests(unittest.TestCase):
    def test_sections_et_tableaux(self) -> None:
        blocks = [
            ("h1", "Titre du document"),
            ("h2", "1. Première section"),
            ("p", "Un paragraphe avec du **gras** et un accent é."),
            ("table", ["| Champ | Valeur |", "| --- | --- |", "| Délai | 14 jours |"]),
            ("h2", "2. Seconde section"),
            ("list", ["- premier point", "- deuxième point"]),
        ]
        data = render_docx(META, blocks)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.docx"
            path.write_bytes(data)
            sections, extractor = extract_docx(path)
            self.assertEqual(extractor, "ooxml-stdlib")
            titles = [s["title"] for s in sections]
            self.assertIn("1. Première section", titles)
            self.assertIn("2. Seconde section", titles)
            first = next(s for s in sections if s["title"] == "1. Première section")
            joined = "\n".join(first["lines"])
            self.assertIn("Délai | 14 jours", joined)
            self.assertIn("é", joined)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
