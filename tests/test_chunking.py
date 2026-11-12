#!/usr/bin/env python3
"""Tests du découpage du corpus en chunks.

Usage :
    python tests/test_chunking.py
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from chunk_corpus import (  # noqa: E402
    CATEGORIES,
    FIELDS,
    amount_sort_key,
    build_chunks,
    load_documents,
    parse_front_matter,
    serialize,
    split_section_text,
)

EXPECTED_SHORT_IDS = {"POL-01#c9", "REG-02#c8", "REG-03#c9"}


class ChunkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = load_documents()
        cls.chunks = build_chunks(cls.documents)
        cls.by_key = {
            (chunk["chunk_id"], chunk["language"]): chunk for chunk in cls.chunks
        }
        cls.by_id: dict[str, list[dict]] = defaultdict(list)
        for chunk in cls.chunks:
            cls.by_id[chunk["chunk_id"]].append(chunk)

    # ------------------------------------------------------------------ volumes

    def test_volume_and_unique_key(self) -> None:
        self.assertEqual(len(self.chunks), 678)
        self.assertEqual(len(self.by_key), 678)
        counts = Counter(chunk["language"] for chunk in self.chunks)
        self.assertEqual(counts, {"fr": 339, "en": 339})

    def test_fr_en_chunk_id_parity(self) -> None:
        self.assertEqual(len(self.by_id), 339)
        for chunk_id, group in self.by_id.items():
            self.assertEqual(
                {chunk["language"] for chunk in group},
                {"fr", "en"},
                chunk_id,
            )
            self.assertEqual(len(group), 2, chunk_id)

    def test_fr_en_metadata_parity(self) -> None:
        for chunk_id, group in self.by_id.items():
            fr = next(chunk for chunk in group if chunk["language"] == "fr")
            en = next(chunk for chunk in group if chunk["language"] == "en")
            self.assertEqual(fr["chunk_index"], en["chunk_index"], chunk_id)
            self.assertEqual(fr["part"], en["part"], chunk_id)
            self.assertEqual(fr["amounts_mad"], en["amounts_mad"], chunk_id)
            self.assertEqual(fr["cross_refs"], en["cross_refs"], chunk_id)
            self.assertEqual(fr["index_in_rag"], en["index_in_rag"], chunk_id)
            self.assertEqual(
                fr["exclusion_reason"], en["exclusion_reason"], chunk_id
            )

    # --------------------------------------------------------------- provenance

    def test_source_path_and_sha256(self) -> None:
        paths = set()
        for chunk in self.chunks:
            path = ROOT / chunk["source_path"]
            self.assertTrue(path.is_file(), chunk["source_path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(chunk["source_sha256"], digest, chunk["source_path"])
            paths.add(chunk["source_path"])
        self.assertEqual(len(paths), 74)

    def test_every_section_has_a_chunk(self) -> None:
        for document in self.documents:
            raw = document["path"].read_text(encoding="utf-8-sig")
            _, body = parse_front_matter(raw)
            headings = re.findall(r"(?m)^##\s+(.+)$", body)
            self.assertTrue(headings, document["source_path"])

            doc_chunks = [
                chunk for chunk in self.chunks
                if chunk["doc_id"] == document["doc_id"]
                and chunk["language"] == document["language"]
            ]
            base_ids = {chunk["chunk_id"].split(".", 1)[0] for chunk in doc_chunks}
            self.assertEqual(
                len(base_ids), len(headings), document["source_path"]
            )
            self.assertEqual(
                {chunk["section_heading"] for chunk in doc_chunks},
                {heading.strip() for heading in headings},
                document["source_path"],
            )

    # ---------------------------------------------------------------- découpage

    def test_long_chunks_have_a_part(self) -> None:
        for chunk in self.chunks:
            if chunk["word_count"] > 300:
                self.assertIsNotNone(chunk["part"], chunk["chunk_id"])
                self.assertGreaterEqual(chunk["part"], 1, chunk["chunk_id"])

    def test_expected_too_short_exclusions(self) -> None:
        excluded = {
            chunk["chunk_id"] for chunk in self.chunks if chunk["exclusion_reason"]
        }
        self.assertEqual(excluded, EXPECTED_SHORT_IDS)
        self.assertEqual(
            sum(1 for chunk in self.chunks if chunk["exclusion_reason"]), 6
        )
        for chunk in self.chunks:
            if chunk["chunk_id"] in EXPECTED_SHORT_IDS:
                self.assertFalse(chunk["index_in_rag"], chunk["chunk_id"])
                self.assertEqual(
                    chunk["exclusion_reason"], "too_short", chunk["chunk_id"]
                )
                self.assertLess(chunk["word_count"], 15, chunk["chunk_id"])
            else:
                self.assertTrue(chunk["index_in_rag"], chunk["chunk_id"])
                self.assertIsNone(chunk["exclusion_reason"], chunk["chunk_id"])

    def test_short_rule_is_applied_to_fr_en_pairs(self) -> None:
        short_ids = {
            chunk_id
            for chunk_id, group in self.by_id.items()
            if all(
                len(chunk["section_heading"].split()) + chunk["word_count"] < 15
                for chunk in group
            )
        }
        self.assertEqual(short_ids, EXPECTED_SHORT_IDS)

    def test_split_section_text_marks_parts(self) -> None:
        text = ("mot " * 160).strip() + "\n\n" + ("word " * 160).strip()
        parts = split_section_text(text)
        self.assertEqual([part for _, part in parts], [1, 2])
        self.assertTrue(all(len(part.split()) <= 300 for part, _ in parts))

    def test_fictif_block_is_removed(self) -> None:
        for chunk in self.chunks:
            self.assertNotIn("Document fictif", chunk["text"], chunk["chunk_id"])
            self.assertNotIn("Fictional document", chunk["text"], chunk["chunk_id"])

    # ------------------------------------------------------------------- schéma

    def test_schema_fields_and_types(self) -> None:
        chunk_id_re = re.compile(r"^[A-Z]{3}-\d{2}#c\d+(?:\.\d+)?$")
        sha_re = re.compile(r"^[0-9a-f]{64}$")
        section_number_re = re.compile(r"^\d+(?:\.\d+)*$")

        for chunk in self.chunks:
            self.assertEqual(set(chunk), set(FIELDS), chunk.get("chunk_id"))
            self.assertRegex(chunk["chunk_id"], chunk_id_re)
            self.assertIn(chunk["language"], {"fr", "en"})
            self.assertIsInstance(chunk["chunk_index"], int)
            self.assertGreaterEqual(chunk["chunk_index"], 1)
            if chunk["part"] is not None:
                self.assertIsInstance(chunk["part"], int)
                self.assertGreaterEqual(chunk["part"], 1)
            self.assertTrue(chunk["doc_title"])
            self.assertIn(chunk["category"], CATEGORIES)
            self.assertTrue(chunk["doc_type"])
            self.assertTrue(chunk["chunking_profile"])
            self.assertTrue(chunk["section_heading"])
            if chunk["section_number"] is not None:
                self.assertRegex(chunk["section_number"], section_number_re)
            self.assertTrue(chunk["text"])
            self.assertEqual(
                chunk["text_for_embedding"],
                f"{chunk['doc_title']} — {chunk['section_heading']}\n{chunk['text']}",
            )
            self.assertIsInstance(chunk["word_count"], int)
            self.assertGreaterEqual(chunk["word_count"], 0)
            self.assertIsInstance(chunk["est_tokens"], int)
            self.assertEqual(
                chunk["est_tokens"], int(round(chunk["word_count"] * 1.35))
            )
            self.assertIsInstance(chunk["has_table"], bool)
            self.assertIsInstance(chunk["cross_refs"], list)
            self.assertEqual(chunk["cross_refs"], sorted(set(chunk["cross_refs"])))
            self.assertIsInstance(chunk["amounts_mad"], list)
            self.assertEqual(len(chunk["amounts_mad"]), len(set(chunk["amounts_mad"])))
            self.assertTrue(chunk["version"])
            self.assertTrue(chunk["effective_date"])
            self.assertIn(chunk["sensitivity"], {"public", "internal"})
            self.assertIn(chunk["audience"], {"customer", "internal"})
            self.assertIsInstance(chunk["index_in_rag"], bool)
            self.assertIn(chunk["exclusion_reason"], {None, "too_short"})
            self.assertTrue(chunk["license"])
            self.assertTrue((ROOT / chunk["source_path"]).is_file())
            self.assertRegex(chunk["source_sha256"], sha_re)

    def test_amounts_mad_are_sorted(self) -> None:
        for chunk in self.chunks:
            self.assertEqual(
                chunk["amounts_mad"],
                sorted(chunk["amounts_mad"], key=amount_sort_key),
                chunk["chunk_id"],
            )

    def test_deterministic_build(self) -> None:
        first = build_chunks(self.documents)
        second = build_chunks(self.documents)
        self.assertEqual(first, second)
        self.assertEqual(serialize(first), serialize(second))
        self.assertEqual(serialize(first), serialize(self.chunks))


if __name__ == "__main__":
    unittest.main(verbosity=2)
