"""Tests de l'analyse exploratoire SupportAI."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ["FAQ", "POL", "PRO", "CAT", "OPS", "REG"]
SPLITS = ["train", "val", "test"]
QUESTION_TYPES = ["lexical", "semantic", "procedural", "out_of_corpus"]
FIGURES = [
    "documents_familles_langue.png",
    "longueurs_documents_chunks.png",
    "parite_fr_en.png",
    "chunks_indexes_audience.png",
    "langues_jeux.png",
    "intentions_split_et_langue.png",
    "doublons_resume.png",
    "questions_longueur.png",
    "questions_types_langue.png",
    "questions_couverture_et_chunks.png",
]


def read_jsonl(relative_path: str) -> list[dict]:
    with (ROOT / relative_path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_manifest() -> list[dict]:
    with (ROOT / "data" / "source_manifest.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


class EdaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = subprocess.run(
            [sys.executable, "scripts/run_eda.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if cls.result.returncode != 0:
            raise AssertionError(
                "scripts/run_eda.py a échoué :\n"
                + cls.result.stdout
                + "\n"
                + cls.result.stderr
            )
        cls.metrics = json.loads(
            (ROOT / "docs" / "reports" / "eda_metrics.json").read_text(
                encoding="utf-8"
            )
        )

    def test_script_runs(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_expected_files_exist(self) -> None:
        expected = [
            ROOT / "scripts" / "run_eda.py",
            ROOT / "notebooks" / "eda.ipynb",
            ROOT / "docs" / "reports" / "eda_metrics.json",
            ROOT / "docs" / "reports" / "eda_findings.md",
        ]
        expected.extend(ROOT / "docs" / "figures" / "eda" / name for name in FIGURES)
        for path in expected:
            self.assertTrue(path.exists(), f"Fichier absent : {path}")
            self.assertGreater(path.stat().st_size, 0, f"Fichier vide : {path}")

    def test_notebook_json_and_cells_compile(self) -> None:
        notebook = json.loads(
            (ROOT / "notebooks" / "eda.ipynb").read_text(encoding="utf-8")
        )
        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(notebook["nbformat_minor"], 5)
        code_cells = [
            cell for cell in notebook["cells"] if cell["cell_type"] == "code"
        ]
        self.assertGreater(len(code_cells), 0)
        for cell in code_cells:
            self.assertEqual(cell["outputs"], [])
            self.assertIsNone(cell["execution_count"])
            source = cell["source"]
            if isinstance(source, list):
                source = "".join(source)
            compile(source, "cell", "exec")

    def test_metrics_are_deterministic(self) -> None:
        path = ROOT / "docs" / "reports" / "eda_metrics.json"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        second = subprocess.run(
            [sys.executable, "scripts/run_eda.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_no_timestamp_key(self) -> None:
        forbidden = [
            key
            for key in walk_keys(self.metrics)
            if "timestamp" in key.lower() or "generated_at" in key.lower()
        ]
        self.assertEqual(forbidden, [])

    def test_counts_match_sources(self) -> None:
        cleaned = read_jsonl("data/processed/cleaned_corpus.jsonl")
        chunks = read_jsonl("data/processed/chunked_corpus.jsonl")
        intents = read_jsonl("data/annotations/intent_dataset.jsonl")
        rag = read_jsonl("data/annotations/rag_eval.jsonl")
        robustness = read_jsonl("data/annotations/robustness_eval.jsonl")

        self.assertEqual(
            self.metrics["languages"]["cleaned_corpus"]["total"], len(cleaned)
        )
        self.assertEqual(
            self.metrics["languages"]["chunked_corpus"]["total"], len(chunks)
        )
        self.assertEqual(
            self.metrics["languages"]["intent_dataset"]["total"], len(intents)
        )
        self.assertEqual(self.metrics["languages"]["rag_eval"]["total"], len(rag))
        self.assertEqual(
            self.metrics["languages"]["robustness_eval"]["total"], len(robustness)
        )

        for dataset, rows in [
            ("cleaned_corpus", cleaned),
            ("chunked_corpus", chunks),
            ("intent_dataset", intents),
            ("rag_eval", rag),
            ("robustness_eval", robustness),
        ]:
            counts = Counter(row["language"] for row in rows)
            for language in ["fr", "en"]:
                self.assertEqual(
                    self.metrics["languages"][dataset][language],
                    counts.get(language, 0),
                )

    def test_document_counts_match_manifest(self) -> None:
        manifest = read_manifest()
        knowledge_base = [
            row
            for row in manifest
            if row.get("record_type") == "knowledge_base_document"
        ]
        self.assertEqual(
            self.metrics["documents"]["documents_total"], len(knowledge_base)
        )
        self.assertEqual(
            self.metrics["documents"]["documents_by_language"]["fr"],
            sum(1 for row in knowledge_base if row["language"] == "fr"),
        )
        self.assertEqual(
            self.metrics["documents"]["documents_by_language"]["en"],
            sum(1 for row in knowledge_base if row["language"] == "en"),
        )
        self.assertEqual(
            self.metrics["documents"]["words_total"],
            sum(int(row["word_count"]) for row in knowledge_base),
        )
        for code in FAMILIES:
            for language in ["fr", "en"]:
                rows = [
                    row
                    for row in knowledge_base
                    if row["doc_id"].split("-")[0] == code
                    and row["language"] == language
                ]
                entry = self.metrics["documents"]["by_family_language"][code][
                    language
                ]
                self.assertEqual(entry["documents"], len(rows))
                self.assertEqual(
                    entry["words"], sum(int(row["word_count"]) for row in rows)
                )

    def test_chunk_index_counts_match_source(self) -> None:
        chunks = read_jsonl("data/processed/chunked_corpus.jsonl")
        self.assertEqual(
            self.metrics["documents"]["chunks_total"], len(chunks)
        )
        self.assertEqual(
            self.metrics["documents"]["chunks_indexed"],
            sum(1 for row in chunks if row["index_in_rag"]),
        )
        for audience in ["customer", "internal"]:
            rows = [row for row in chunks if row["audience"] == audience]
            entry = self.metrics["documents"]["chunks_by_audience_index"][audience]
            self.assertEqual(entry["total"], len(rows))
            self.assertEqual(
                entry["indexed"], sum(1 for row in rows if row["index_in_rag"])
            )
            self.assertEqual(
                entry["not_indexed"],
                sum(1 for row in rows if not row["index_in_rag"]),
            )

    def test_intent_counts_match_source(self) -> None:
        intents = read_jsonl("data/annotations/intent_dataset.jsonl")
        self.assertEqual(self.metrics["intents"]["total"], len(intents))
        for split in SPLITS:
            self.assertEqual(
                self.metrics["intents"]["split_totals"][split],
                sum(1 for row in intents if row["split"] == split),
            )
        for label in {row["intent"] for row in intents}:
            rows = [row for row in intents if row["intent"] == label]
            entry = self.metrics["intents"]["by_intent_split"][label]
            self.assertEqual(entry["total"], len(rows))
            for split in SPLITS:
                self.assertEqual(
                    entry[split],
                    sum(1 for row in rows if row["split"] == split),
                )
        self.assertEqual(
            self.metrics["intents"]["ambiguous_count"],
            sum(1 for row in intents if row["ambiguous"]),
        )

    def test_question_counts_match_source(self) -> None:
        rag = read_jsonl("data/annotations/rag_eval.jsonl")
        self.assertEqual(self.metrics["questions"]["rag_total"], len(rag))
        for question_type in QUESTION_TYPES:
            rows = [
                row for row in rag if row["question_type"] == question_type
            ]
            entry = self.metrics["questions"]["by_type_language"][question_type]
            self.assertEqual(entry["total"], len(rows))
            for language in ["fr", "en"]:
                self.assertEqual(
                    entry[language],
                    sum(1 for row in rows if row["language"] == language),
                )
        gold_chunks = Counter(len(row.get("gold_chunk_ids") or []) for row in rag)
        for count in range(0, 3):
            self.assertEqual(
                self.metrics["questions"]["gold_chunks_per_question"][str(count)],
                gold_chunks.get(count, 0),
            )

    def test_duplicate_counts_are_zero(self) -> None:
        duplicates = self.metrics["duplicates"]
        for key in ["cleaned_corpus", "chunked_corpus"]:
            self.assertEqual(duplicates[key]["exact_pair_count"], 0)
            self.assertEqual(duplicates[key]["quasi_pair_count"], 0)
        for split in SPLITS:
            entry = duplicates["intent_dataset"]["intra_split"][split]
            self.assertEqual(entry["exact_pair_count"], 0)
            self.assertEqual(entry["quasi_pair_count"], 0)
        self.assertEqual(
            duplicates["intent_dataset"]["cross_split"]["exact_pair_count"], 0
        )
        self.assertEqual(
            duplicates["intent_dataset"]["cross_split"]["quasi_pair_count"], 0
        )
        for key in ["rag_vs_robustness", "rag_vs_intent_dataset"]:
            self.assertEqual(duplicates[key]["exact_pair_count"], 0)
            self.assertEqual(duplicates[key]["quasi_pair_count"], 0)

    def test_findings_count(self) -> None:
        self.assertGreaterEqual(len(self.metrics["findings"]), 8)
        self.assertLessEqual(len(self.metrics["findings"]), 12)


if __name__ == "__main__":
    unittest.main()
