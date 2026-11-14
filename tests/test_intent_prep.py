import contextlib
import csv
import io
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import prepare_intent_annotation as prep  # noqa: E402


class IntentPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = prep.read_jsonl(prep.CANDIDATES_PATH)
        cls.intents = prep.read_intents()
        cls.by_id = {row["id"]: row for row in cls.rows}
        cls.split_of = prep.build_split(cls.rows, cls.intents)
        prep.write_split(cls.rows, cls.split_of)
        prep.write_sheets(cls.rows, cls.split_of)

    def test_candidate_volume_and_taxonomy(self):
        self.assertEqual(len(self.rows), 560)
        self.assertEqual(len({row["id"] for row in self.rows}), 560)
        per_intent = Counter(row["target_intent"] for row in self.rows)
        self.assertEqual(set(per_intent), set(self.intents))
        self.assertTrue(all(count == 40 for count in per_intent.values()))
        per_language = Counter((row["target_intent"], row["language"]) for row in self.rows)
        for intent in self.intents:
            self.assertEqual(per_language[(intent, "fr")], 24)
            self.assertEqual(per_language[(intent, "en")], 16)

    def test_candidate_ids_do_not_reuse_pilot(self):
        pilot_ids = prep.read_pilot_ids()
        self.assertFalse({row["id"] for row in self.rows} & pilot_ids)

    def test_candidate_validation_passes(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            valid = prep.validate_candidates(self.rows, self.intents)
        self.assertTrue(valid, output.getvalue())
        self.assertIn("Tous les contrôles sont OK", output.getvalue())

    def test_no_quasi_duplicates(self):
        self.assertEqual(prep.quasi_duplicate_pairs(self.rows), [])

    def test_split_counts(self):
        counts = Counter(self.split_of.values())
        self.assertEqual(counts["train"], 392)
        self.assertEqual(counts["val"], 84)
        self.assertEqual(counts["test"], 84)

    def test_split_is_stratified_by_intent_and_language(self):
        for intent in self.intents:
            for language in ("fr", "en"):
                local = Counter(
                    self.split_of[row["id"]]
                    for row in self.rows
                    if row["target_intent"] == intent and row["language"] == language
                )
                expected = (
                    {"train": 17, "val": 4, "test": 3}
                    if language == "fr"
                    else {"train": 11, "val": 2, "test": 3}
                )
                self.assertEqual(local, expected)

    def test_sheet_headers_and_counts(self):
        for name, expected_rows in (
            ("annotate_aya.csv", 168),
            ("annotate_mohammed.csv", 168),
            ("spotcheck_train_aya.csv", 56),
        ):
            path = prep.BLIND_DIR / name
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, prep.ANNOTATION_COLUMNS)
                rows = list(reader)
            self.assertEqual(len(rows), expected_rows)
            self.assertEqual(len({row["id"] for row in rows}), expected_rows)

    def test_sheets_have_no_annotation_or_target_columns(self):
        for name in ("annotate_aya.csv", "annotate_mohammed.csv", "spotcheck_train_aya.csv"):
            path = prep.BLIND_DIR / name
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, prep.ANNOTATION_COLUMNS)
                self.assertNotIn("target_intent", reader.fieldnames)
                self.assertNotIn("case_type", reader.fieldnames)
                self.assertNotIn("split", reader.fieldnames)
                for row in reader:
                    for column in prep.ANNOTATION_EMPTY_COLUMNS:
                        self.assertEqual(row[column], "", f"{name}:{row['id']}:{column}")

    def test_main_sheets_have_same_ids_but_different_order(self):
        aya = [row["id"] for row in self._read_sheet("annotate_aya.csv")]
        mohammed = [row["id"] for row in self._read_sheet("annotate_mohammed.csv")]
        self.assertEqual(set(aya), set(mohammed))
        self.assertEqual(len(set(aya)), 168)
        self.assertNotEqual(aya, mohammed)
        self.assertTrue(all(self.split_of[identifier] in {"val", "test"} for identifier in aya))

    def test_spotcheck_is_train_and_four_per_intent(self):
        rows = self._read_sheet("spotcheck_train_aya.csv")
        self.assertEqual(len(rows), 56)
        self.assertTrue(all(self.split_of[row["id"]] == "train" for row in rows))
        per_intent = Counter(self.by_id[row["id"]]["target_intent"] for row in rows)
        self.assertTrue(all(count == 4 for count in per_intent.values()))

    def test_determinism(self):
        split_before = prep.SPLIT_PATH.read_bytes()
        aya_before = (prep.BLIND_DIR / "annotate_aya.csv").read_bytes()
        mohammed_before = (prep.BLIND_DIR / "annotate_mohammed.csv").read_bytes()
        spot_before = (prep.BLIND_DIR / "spotcheck_train_aya.csv").read_bytes()

        split_again = prep.build_split(self.rows, self.intents)
        prep.write_split(self.rows, split_again)
        prep.write_sheets(self.rows, split_again)

        self.assertEqual(split_before, prep.SPLIT_PATH.read_bytes())
        self.assertEqual(aya_before, (prep.BLIND_DIR / "annotate_aya.csv").read_bytes())
        self.assertEqual(mohammed_before, (prep.BLIND_DIR / "annotate_mohammed.csv").read_bytes())
        self.assertEqual(spot_before, (prep.BLIND_DIR / "spotcheck_train_aya.csv").read_bytes())

    def test_private_directory_is_git_ignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "-q", "data/annotations/_private/intent_candidates.jsonl"],
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)

    def test_gitignore_and_outputs_are_lf(self):
        gitignore = (ROOT / ".gitignore").read_bytes()
        self.assertIn(b"data/annotations/_private/\n", gitignore)
        self.assertNotIn(b"\r\n", gitignore)
        for path in (
            prep.CANDIDATES_PATH,
            prep.SPLIT_PATH,
            prep.BLIND_DIR / "annotate_aya.csv",
            prep.BLIND_DIR / "annotate_mohammed.csv",
            prep.BLIND_DIR / "spotcheck_train_aya.csv",
        ):
            self.assertNotIn(b"\r\n", path.read_bytes(), str(path))

    def test_readme_does_not_reveal_target_labels(self):
        text = (prep.BLIND_DIR / "README_annotation.md").read_text(encoding="utf-8")
        self.assertNotIn("target_intent", text)
        self.assertNotIn("case_type", text)
        self.assertIn("annotate_<prénom>_done.csv", text)

    @staticmethod
    def _read_sheet(name):
        with (prep.BLIND_DIR / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main(verbosity=2)
