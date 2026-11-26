"""Tests du gel versionné SupportAI.

Tous les jeux utilisés ici sont fabriqués dans des dossiers temporaires :
aucun test ne lit ni n'écrit les vrais jeux de données du dépôt.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import freeze_test_sets as freeze_mod  # noqa: E402

FORBIDDEN_INPUT_FIELDS = {
    "intent",
    "acceptable_labels",
    "ambiguous",
    "notes",
    "annotator_1",
    "annotator_2",
    "adjudicated",
}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def intent_row(identifier: str, split: str, text: str, language: str = "fr") -> dict:
    return {
        "id": identifier,
        "text": text,
        "language": language,
        "intent": "order_tracking",
        "acceptable_labels": [],
        "ambiguous": False,
        "source": "synthetic",
        "split": split,
        "annotator_1": "aya",
        "annotator_2": None,
        "adjudicated": False,
        "notes": "",
        "created_at": "2026-11-14",
    }


def make_root(root: Path, intent_rows: list[dict]) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "annotation_guidelines.md").write_text(
        "# Guidelines de test\n", encoding="utf-8", newline="\n"
    )
    write_jsonl(root / "data" / "annotations" / "intent_dataset.jsonl", intent_rows)
    write_jsonl(root / "data" / "annotations" / "rag_eval.jsonl", [])
    write_jsonl(root / "data" / "annotations" / "robustness_eval.jsonl", [])
    write_jsonl(root / "data" / "processed" / "chunked_corpus.jsonl", [])


def baseline_rows() -> list[dict]:
    return [
        intent_row("INT-0001", "train", "ou puis je trouver le suivi de ma commande"),
        intent_row("INT-0002", "val", "how do I change the delivery address", "en"),
        intent_row("INT-0003", "test", "le remboursement tarde a arriver sur mon compte"),
    ]


class FreezeTests(unittest.TestCase):
    def test_freeze_baseline_inputs_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_root(root, baseline_rows())
            manifest = freeze_mod.freeze(root, write_report=False)

            frozen_dir = root / "data" / "frozen" / "v1.0"
            expected = [
                "MANIFEST.json",
                "intent_test.jsonl",
                "intent_test_inputs.jsonl",
                "intent_val.jsonl",
                "rag_eval.jsonl",
                "robustness_eval.jsonl",
                "split_ids.json",
            ]
            self.assertEqual(sorted(path.name for path in frozen_dir.iterdir()), sorted(expected))
            self.assertTrue(freeze_mod.verify(root, verbose=False))

            inputs = [
                json.loads(line)
                for line in (frozen_dir / "intent_test_inputs.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(len(inputs), 1)
            self.assertFalse(FORBIDDEN_INPUT_FIELDS.intersection(inputs[0]))
            self.assertEqual(
                inputs[0]["text"], "le remboursement tarde a arriver sur mon compte"
            )
            self.assertEqual(manifest["license"], freeze_mod.LICENSE)
            self.assertEqual(manifest["license_status"], freeze_mod.LICENSE_STATUS)
            self.assertEqual(manifest["license_source"], freeze_mod.LICENSE_SOURCE)
            self.assertEqual(manifest["annotation_status"], "single_annotator")
            self.assertEqual(manifest["seed"], 42)

    def test_determinism_two_runs_same_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bases = [Path(temporary) / "a", Path(temporary) / "b"]
            manifests = []
            for base in bases:
                make_root(base, baseline_rows())
                manifests.append(freeze_mod.freeze(base, write_report=False))
            first, second = manifests
            self.assertEqual(first["frozen_files"], second["frozen_files"])
            self.assertEqual(first["sources"], second["sources"])
            self.assertEqual(
                first["guidelines"]["sha256"], second["guidelines"]["sha256"]
            )

    def test_refuse_to_overwrite_existing_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_root(root, baseline_rows())
            freeze_mod.freeze(root, write_report=False)
            with self.assertRaisesRegex(freeze_mod.FreezeError, "Refus d'écraser"):
                freeze_mod.freeze(root, write_report=False)

    def test_shared_id_blocks_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = baseline_rows()
            rows[2]["id"] = rows[0]["id"]
            make_root(root, rows)
            with self.assertRaisesRegex(freeze_mod.FreezeError, "a:"):
                freeze_mod.freeze(root, write_report=False)
            self.assertFalse((root / "data" / "frozen" / "v1.0").exists())

    def test_exact_duplicate_blocks_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = baseline_rows()
            rows[2]["text"] = rows[0]["text"]
            make_root(root, rows)
            with self.assertRaisesRegex(freeze_mod.FreezeError, "b:"):
                freeze_mod.freeze(root, write_report=False)
            self.assertFalse((root / "data" / "frozen" / "v1.0").exists())

    def test_quasi_duplicate_blocks_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = baseline_rows()
            rows[0]["text"] = "je voudrais savoir ou en est ma commande aujourd hui"
            rows[2]["text"] = "je voudrais savoir ou en est ma commande aujourd hui svp"
            make_root(root, rows)
            with self.assertRaisesRegex(freeze_mod.FreezeError, "c:"):
                freeze_mod.freeze(root, write_report=False)
            self.assertFalse((root / "data" / "frozen" / "v1.0").exists())

    def test_shared_order_id_blocks_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = baseline_rows()
            rows[0]["text"] = "ma commande ORD-100001 est en retard"
            rows[2]["text"] = "ou en est la commande ORD-100001"
            make_root(root, rows)
            with self.assertRaisesRegex(freeze_mod.FreezeError, "d:"):
                freeze_mod.freeze(root, write_report=False)
            self.assertFalse((root / "data" / "frozen" / "v1.0").exists())

    def test_verify_detects_one_character_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_root(root, baseline_rows())
            freeze_mod.freeze(root, write_report=False)
            target = root / "data" / "frozen" / "v1.0" / "intent_test.jsonl"
            data = target.read_bytes()
            index = data.find(b"le ")
            self.assertGreaterEqual(index, 0)
            target.write_bytes(data[:index] + b"la " + data[index + 3 :])
            self.assertFalse(freeze_mod.verify(root, verbose=False))

    def test_verify_detects_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_root(root, baseline_rows())
            freeze_mod.freeze(root, write_report=False)
            source = root / "data" / "annotations" / "intent_dataset.jsonl"
            source.write_bytes(source.read_bytes().replace(b"aya", b"AXA"))
            self.assertFalse(freeze_mod.verify(root, verbose=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
