#!/usr/bin/env python3
"""Tests du nettoyage, de la normalisation et de la déduplication.

Usage :
    python tests/test_cleaning.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from clean_corpus import (  # noqa: E402
    CleaningError,
    control_business_values,
    control_no_loss,
    control_whitespace,
    clean_all,
    clean_record,
    duplicate_key,
    is_heading_only,
    load_records,
    normalize_text,
    reflow_pdf,
    remove_boilerplate,
    run_controls,
    serialize,
)

META = {
    "category": "procedures",
    "title": "Document de test",
    "source_sha256": "0" * 64,
}


def make_record(
    record_id: str,
    text: str,
    language: str = "fr",
    fmt: str = "docx",
    unit_type: str = "section",
    **overrides,
) -> dict:
    record = {
        "record_id": record_id,
        "doc_id": record_id.split(":")[0],
        "language": language,
        "format": fmt,
        "category": META["category"],
        "title": META["title"],
        "source_path": f"data/processed/documents/{fmt}/{language}/test.{fmt}",
        "source_sha256": META["source_sha256"],
        "unit_type": unit_type,
        "unit_id": "s1",
        "page": None,
        "section": None,
        "text": text,
    }
    record.update(overrides)
    return record


class NormalizationTests(unittest.TestCase):
    def test_nfc(self) -> None:
        self.assertEqual(normalize_text("e\u0301"), "é")

    def test_espaces_insecables(self) -> None:
        self.assertEqual(normalize_text("39\u00a0MAD\u202f!"), "39 MAD !")

    def test_tabulations_invisibles_et_controles(self) -> None:
        self.assertEqual(normalize_text("re\u200btour\tok\x00"), "retour ok")

    def test_espaces_et_lignes(self) -> None:
        self.assertEqual(normalize_text("  a   b  \n\n\n\n  c  "), "a b\n\nc")

    def test_ponctuation_francaise_et_montants(self) -> None:
        text = "Retour : 14 jours ? 2 499 MAD ; 5 %"
        self.assertEqual(normalize_text(text), text)

    def test_texte_vide(self) -> None:
        self.assertEqual(normalize_text("   \n\t "), "")


class BoilerplateTests(unittest.TestCase):
    def test_reference_entete_et_prefixe_version(self) -> None:
        text = (
            "Titre du document\n"
            "Référence T-01 · version 1.0 · entrée en vigueur 2026-01-01 · NovaShop\n"
            "Document fictif — NovaShop est une société imaginaire créée pour le projet "
            "pédagogique SupportAI.\n"
            "Version: 1.0 · Effective date: 1 September 2026 Scope: orders placed in Morocco.\n"
            "Corps du document."
        )
        cleaned, removed, motifs = remove_boilerplate(normalize_text(text))
        self.assertTrue(cleaned.startswith("Titre du document"))
        self.assertIn("Scope: orders placed in Morocco.", cleaned)
        self.assertNotIn("Référence", cleaned)
        self.assertNotIn("Document fictif", cleaned)
        self.assertNotIn("Effective date", cleaned)
        self.assertEqual(len(removed), 3)
        self.assertEqual(motifs["reference"], 1)
        self.assertEqual(motifs["fictif_entete"], 1)
        self.assertEqual(motifs["version"], 1)

    def test_pied_de_page_et_separateur(self) -> None:
        text = (
            "Titre\n\nCorps du document.\n\n"
            "____________________________________________________________\n"
            "Fictional document — NovaShop is an imaginary company created for the SupportAI\n"
            "educational project. Prices are invented."
        )
        cleaned, removed, motifs = remove_boilerplate(normalize_text(text))
        self.assertEqual(cleaned.strip(), "Titre\n\nCorps du document.")
        self.assertEqual(motifs["fictif_pied"], 1)
        self.assertEqual(motifs["separateur"], 1)
        self.assertTrue(any(set(segment) == {"_"} for segment in removed))

    def test_prefixe_version_francais_colle(self) -> None:
        text = (
            "Version : 1.0 · Entrée en vigueur : 1er septembre 2026 "
            "Périmètre : commandes passées en boutique."
        )
        cleaned, removed, motifs = remove_boilerplate(normalize_text(text))
        self.assertEqual(cleaned, "Périmètre : commandes passées en boutique.")
        self.assertEqual(motifs["version"], 1)
        self.assertEqual(removed, ["Version : 1.0 · Entrée en vigueur : 1er septembre 2026 "])


class ReflowTests(unittest.TestCase):
    def test_phrase_coupee(self) -> None:
        self.assertEqual(
            reflow_pdf("Une phrase coupée\nsur deux lignes."),
            "Une phrase coupée sur deux lignes.",
        )

    def test_pas_de_jonction_apres_ponctuation(self) -> None:
        text = "Fin.\nDébut."
        self.assertEqual(reflow_pdf(text), text)

    def test_titre_numerote_non_joint(self) -> None:
        text = "6. Procedure\nTexte."
        self.assertEqual(reflow_pdf(text), text)

    def test_liste_non_jointe(self) -> None:
        text = "Introduction\n- premier point"
        self.assertEqual(reflow_pdf(text), text)

    def test_tableau_non_touche(self) -> None:
        text = "| a | b |\n| c | d |"
        self.assertEqual(reflow_pdf(text), text)

    def test_premiere_ligne_protegee(self) -> None:
        text = "Titre du document\nSuite du texte."
        self.assertEqual(reflow_pdf(text, protect_first_line=True), text)
        self.assertEqual(
            reflow_pdf(text, protect_first_line=False),
            "Titre du document Suite du texte.",
        )

    def test_continuation_de_liste(self) -> None:
        self.assertEqual(
            reflow_pdf("- un point coupé\nsur deux lignes."),
            "- un point coupé sur deux lignes.",
        )


class DedupTests(unittest.TestCase):
    def test_doublon_exact_supprime(self) -> None:
        records = [
            make_record("T-01:fr:docx:s1", "Texte strictement identique."),
            make_record("T-02:fr:docx:s1", "Texte strictement identique."),
        ]
        cleaned, _, duplicates = clean_all(records)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(duplicates, [("T-02:fr:docx:s1", "T-01:fr:docx:s1")])

    def test_paires_fr_en_non_fusionnees(self) -> None:
        records = [
            make_record("T-01:fr:docx:s1", "Texte identique.", language="fr"),
            make_record("T-01:en:docx:s1", "Texte identique.", language="en"),
        ]
        cleaned, _, duplicates = clean_all(records)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(duplicates, [])

    def test_quasi_doublon_signale_sans_suppression(self) -> None:
        base = " ".join(f"mot{index}" for index in range(60))
        variant = " ".join(f"mot{index}" for index in range(59)) + " different"
        records = [
            make_record("T-01:fr:docx:s1", base),
            make_record("T-02:fr:docx:s1", variant),
        ]
        cleaned, diagnostics, duplicates = clean_all(records)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(duplicates, [])
        self.assertEqual(diagnostics[1]["near_duplicate_of"], "T-01:fr:docx:s1")
        self.assertGreaterEqual(diagnostics[1]["near_duplicate_score"], 0.90)

    def test_cle_de_doublon_ignore_ponctuation(self) -> None:
        self.assertEqual(
            duplicate_key("Retour : 14 jours !"),
            duplicate_key("retour 14 jours"),
        )


class HeadingOnlyTests(unittest.TestCase):
    def test_titre_seul(self) -> None:
        record = make_record("T-01:fr:docx:s3", "2. Niveaux", section="2. Niveaux")
        cleaned, _, _ = clean_all([record])
        self.assertTrue(cleaned[0]["cleaning"]["heading_only"])

    def test_titre_avec_corps(self) -> None:
        record = make_record(
            "T-01:fr:docx:s3", "2. Niveaux\n\nUn paragraphe de contenu.")
        self.assertFalse(is_heading_only(record, record["text"]))

    def test_titre_trop_long(self) -> None:
        text = "1. Un titre vraiment beaucoup trop long pour être considéré comme seul"
        record = make_record("T-01:fr:docx:s3", text)
        self.assertFalse(is_heading_only(record, text))

    def test_page_jamais_titre_seul(self) -> None:
        record = make_record(
            "T-01:fr:pdf:p1", "2. Niveaux", fmt="pdf", unit_type="page", page=1)
        self.assertFalse(is_heading_only(record, record["text"]))


class EmptyRecordTests(unittest.TestCase):
    def test_enregistrement_vide_leve_une_erreur(self) -> None:
        record = make_record(
            "T-01:fr:docx:s1",
            "Référence T-01 · version 1.0 · entrée en vigueur 2026-01-01 · NovaShop",
        )
        with self.assertRaises(CleaningError):
            clean_record(record)


class ControlTests(unittest.TestCase):
    def test_sans_perte(self) -> None:
        record = make_record(
            "T-01:fr:docx:s1",
            "Titre\n\nRéférence T-01 · version 1.0 · entrée en vigueur 2026-01-01 · NovaShop\n\nCorps.",
        )
        result = clean_record(record)
        diagnostic = {
            "record_id": record["record_id"],
            "input_text": record["text"],
            "cleaned_text": result.text,
            "removed": result.removed,
        }
        ok, _, problems = control_no_loss([diagnostic])
        self.assertTrue(ok, problems)

    def test_valeurs_metier(self) -> None:
        record = make_record(
            "T-01:fr:docx:s1", "Le retour coûte 39 MAD, soit 5 % du montant.")
        result = clean_record(record)
        diagnostic = {
            "record_id": record["record_id"],
            "input_text": record["text"],
            "cleaned_text": result.text,
            "removed": result.removed,
        }
        ok, _, problems = control_business_values([record], [diagnostic])
        self.assertTrue(ok, problems)

    def test_valeur_metier_perdue_detectee(self) -> None:
        record = make_record("T-01:fr:docx:s1", "Le retour coûte 39 MAD.")
        diagnostic = {
            "record_id": record["record_id"],
            "input_text": record["text"],
            "cleaned_text": "Le retour est gratuit.",
            "removed": [],
        }
        ok, _, problems = control_business_values([record], [diagnostic])
        self.assertFalse(ok)
        self.assertEqual(problems, [record["record_id"]])

    def test_espaces_propres(self) -> None:
        diagnostic = {
            "record_id": "T-01:fr:docx:s1",
            "cleaned_text": "Texte propre : 39 MAD.",
        }
        ok, _, problems = control_whitespace([diagnostic])
        self.assertTrue(ok, problems)

    def test_espaces_sales_detectes(self) -> None:
        diagnostic = {
            "record_id": "T-01:fr:docx:s1",
            "cleaned_text": "Texte  sale\tavec espaces.",
        }
        ok, _, problems = control_whitespace([diagnostic])
        self.assertFalse(ok)
        self.assertEqual(len(problems), 1)


class RealCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = load_records()
        cls.cleaned, cls.diagnostics, cls.duplicates = clean_all(cls.records)
        cls.controls = run_controls(
            cls.records, cls.cleaned, cls.diagnostics, cls.duplicates)

    def test_volumes(self) -> None:
        self.assertEqual(len(self.records), 522)
        self.assertEqual(len(self.cleaned), 522)
        self.assertEqual(len(self.duplicates), 0)
        self.assertEqual(
            sum(1 for record in self.cleaned if record["language"] == "fr"), 261)
        self.assertEqual(
            sum(1 for record in self.cleaned if record["language"] == "en"), 261)
        self.assertEqual(
            len({record["record_id"] for record in self.cleaned}), 522)

    def test_les_sept_controles_passent(self) -> None:
        for control in self.controls:
            self.assertTrue(control["ok"], f"{control['id']}. {control['name']} : {control['value']}")

    def test_schema_de_sortie(self) -> None:
        expected = {
            "record_id", "doc_id", "language", "format", "category", "title",
            "source_path", "source_sha256", "unit_type", "unit_id", "page",
            "section", "text", "char_count", "word_count", "cleaning",
        }
        for record in self.cleaned:
            self.assertEqual(set(record), expected)
            self.assertNotIn("extracted_at", record)
            self.assertEqual(record["char_count"], len(record["text"]))
            self.assertEqual(record["word_count"], len(record["text"].split()))
            self.assertEqual(
                set(record["cleaning"]),
                {"steps", "removed", "reflowed", "heading_only", "near_duplicate_of"},
            )

    def test_determinisme_octet_pour_octet(self) -> None:
        first, _, _ = clean_all(self.records)
        second, _, _ = clean_all(self.records)
        self.assertEqual(serialize(first), serialize(second))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
