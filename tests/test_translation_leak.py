"""Tests de non-régression sur la fuite de traduction TR-0001."""

from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import translation_leak as tl  # noqa: E402

V10_SOURCE = ROOT / "data" / "annotations" / "intent_dataset.jsonl"
V11_SOURCE = ROOT / "data" / "annotations" / "intent_dataset_v1.1.jsonl"
LEAK_IDS = frozenset({"INT-0445", "INT-0421"})
LEGITIMATE_IDS = frozenset({"INT-0445", "INT-0223"})


def load_rows(path: Path) -> list[dict]:
    return tl.load_jsonl(path)


class TranslationLeakTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v10 = load_rows(V10_SOURCE)
        cls.v11 = load_rows(V11_SOURCE)

    def test_detector_finds_known_v10_leak(self) -> None:
        leaks = tl.find_cross_split_translation_leaks(self.v10)
        pairs = {frozenset((item["first_id"], item["second_id"])) for item in leaks}
        self.assertIn(LEAK_IDS, pairs)
        self.assertNotIn(LEGITIMATE_IDS, pairs)
        self.assertEqual(len(leaks), 1, leaks)

    def test_v11_has_no_cross_split_translation_leak(self) -> None:
        self.assertEqual(tl.find_cross_split_translation_leaks(self.v11), [])

    def test_v11_keeps_both_examples_with_only_split_changed(self) -> None:
        before = {row["id"]: row for row in self.v10}
        after = {row["id"]: row for row in self.v11}
        self.assertEqual(set(before), set(after))
        self.assertEqual(len(before), 560)

        for identifier in LEAK_IDS:
            old = dict(before[identifier])
            new = dict(after[identifier])
            self.assertEqual(old.pop("split"), "train" if identifier == "INT-0421" else "test")
            self.assertEqual(new.pop("split"), "test")
            self.assertEqual(old, new)

        for row in self.v10:
            old = dict(row)
            new = dict(after[row["id"]])
            old.pop("split")
            new.pop("split")
            self.assertEqual(old, new, row["id"])

    def test_split_counts_and_legitimate_case_are_preserved(self) -> None:
        counts = Counter(row["split"] for row in self.v11)
        self.assertEqual(dict(counts), {"train": 391, "val": 84, "test": 85})
        legitimate = next(row for row in self.v11 if row["id"] == "INT-0223")
        self.assertEqual(legitimate["split"], "val")
        self.assertEqual(legitimate["intent"], "return_request")


if __name__ == "__main__":
    unittest.main()
