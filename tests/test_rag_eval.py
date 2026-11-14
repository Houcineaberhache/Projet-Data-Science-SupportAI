import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_rag_eval as ev  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class RagEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = ev.load_jsonl(ev.RAG_PATH)
        cls.rob = ev.load_jsonl(ev.ROB_PATH)
        cls.corpus = ev.load_corpus()
        cls.intents = ev.load_intents()

    def test_counts_and_distribution(self):
        self.assertEqual(len(self.rag), 140)
        self.assertEqual(len(self.rob), 35)
        self.assertEqual(dict(__import__("collections").Counter(r["question_type"] for r in self.rag)), ev.EXPECTED_TYPES)
        self.assertEqual(dict(__import__("collections").Counter(r["language"] for r in self.rag)), ev.EXPECTED_LANGS)
        self.assertEqual(
            dict(__import__("collections").Counter((r["question_type"], r["language"]) for r in self.rag)),
            ev.EXPECTED_TYPE_LANG,
        )
        self.assertEqual(
            dict(__import__("collections").Counter(r["category"] for r in self.rob)),
            ev.ROB_CATEGORIES,
        )

    def test_all_validation_checks_pass(self):
        checks, _, _ = ev.validate_data(self.rag, self.rob, self.corpus, self.intents, verbose=False)
        failures = [c for c in checks if not c["ok"]]
        self.assertFalse(failures, failures)

    def test_chunk_ids_are_customer_indexable_and_consistent(self):
        for row in self.rag:
            if not row["answerable"]:
                self.assertEqual(row["gold_chunk_ids"], [])
                self.assertEqual(row["gold_doc_ids"], [])
                self.assertIsNone(row["gold_answer"])
                continue
            self.assertTrue(row["gold_chunk_ids"])
            self.assertTrue(any(row["gold_relevance"][cid] == 2 for cid in row["gold_chunk_ids"]))
            for cid in row["gold_chunk_ids"]:
                rec = self.corpus[(cid, row["language"])]
                self.assertEqual(rec["audience"], "customer")
                self.assertTrue(rec["index_in_rag"])
                self.assertIn(rec["doc_id"], ev.ALLOWED_DOC_SET)
                self.assertIn(row["gold_relevance"][cid], (1, 2))
            expected_docs = list(dict.fromkeys(cid.split("#", 1)[0] for cid in row["gold_chunk_ids"]))
            self.assertEqual(row["gold_doc_ids"], expected_docs)

    def test_numbers_are_grounded(self):
        for row in self.rag:
            if not row["answerable"]:
                continue
            gold_text = "\n".join(
                self.corpus[(cid, row["language"])]["text"] for cid in row["gold_chunk_ids"]
            )
            gold_numbers = set(ev.numbers(gold_text))
            missing = [n for n in ev.numbers(row["gold_answer"]) if n not in gold_numbers]
            self.assertFalse(missing, f"{row['id']}: {missing}")

    def test_question_style_and_title_avoidance(self):
        for row in self.rag:
            wc = len(row["question"].split())
            self.assertGreaterEqual(wc, 4, row["id"])
            self.assertLessEqual(wc, 40, row["id"])
            self.assertIsNone(re.search(r"[\u0600-\u06ff]", row["question"]), row["id"])
            if not row["answerable"]:
                continue
            for cid in row["gold_chunk_ids"]:
                heading = self.corpus[(cid, row["language"])]["section_heading"]
                score = ev.jaccard(ev.tokens(row["question"]), ev.tokens(heading))
                self.assertLess(score, 0.6, f"{row['id']} vs {heading!r}: {score}")
                if row["question_type"] == "semantic":
                    q_tokens = set(ev.tokens(row["question"]))
                    banned = sorted(t for t in set(ev.tokens(heading)) if len(t) >= 5 and t in q_tokens)
                    self.assertFalse(banned, f"{row['id']}: {banned}")

    def test_build_outputs_are_coherent_and_deterministic(self):
        paths = [ev.WITH_PASSAGES_PATH, ev.REPORT_PATH, ev.REVIEW_PATH]
        before = [sha256(p) for p in paths]

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_rag_eval.py"), "build"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        middle = [sha256(p) for p in paths]
        self.assertEqual(before, middle)

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_rag_eval.py"), "build"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = [sha256(p) for p in paths]
        self.assertEqual(middle, after)

        rag = ev.load_jsonl(ev.RAG_PATH)
        with_passages = ev.load_jsonl(ev.WITH_PASSAGES_PATH)
        self.assertEqual(len(rag), len(with_passages))
        for source, enriched in zip(rag, with_passages):
            for field in ev.RAG_FIELDS:
                self.assertEqual(source[field], enriched[field], f"{source['id']} / {field}")
            self.assertEqual(set(enriched), set(ev.RAG_FIELDS) | {"gold_passages"})
            self.assertEqual(len(enriched["gold_passages"]), len(source["gold_chunk_ids"]))
            for cid, passage in zip(source["gold_chunk_ids"], enriched["gold_passages"]):
                rec = self.corpus[(cid, source["language"])]
                self.assertEqual(passage["chunk_id"], rec["chunk_id"])
                self.assertEqual(passage["doc_id"], rec["doc_id"])
                self.assertEqual(passage["section_heading"], rec["section_heading"])
                self.assertEqual(passage["text"], rec["text"])

    def test_review_sheet_contains_25_samples_and_all_ooc(self):
        text = ev.REVIEW_PATH.read_text(encoding="utf-8")
        ids = re.findall(r"^## (RET-\d{4})", text, flags=re.M)
        self.assertEqual(len(ids), 39)
        self.assertEqual(len(set(ids)), 39)
        by_id = {r["id"]: r for r in self.rag}
        answerable_ids = [rid for rid in ids if by_id[rid]["answerable"]]
        ooc_ids = [rid for rid in ids if not by_id[rid]["answerable"]]
        self.assertEqual(len(answerable_ids), 25)
        self.assertEqual(len(ooc_ids), 14)
        self.assertEqual(set(ooc_ids), {r["id"] for r in self.rag if not r["answerable"]})

    def test_report_has_no_timestamp_and_all_checks_ok(self):
        text = ev.REPORT_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"\b20\d{2}-\d{2}-\d{2}\b")
        self.assertEqual(text.count("| **OK** |"), 7)
        self.assertIn("No timestamp is stored", text)


if __name__ == "__main__":
    unittest.main()
