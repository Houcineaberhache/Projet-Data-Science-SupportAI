import contextlib
import csv
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import merge_annotations as merge  # noqa: E402

CODES = [
    "order_tracking",
    "order_change_cancel",
    "delivery_issue",
    "return_request",
    "refund_status",
    "payment_info",
    "payment_issue",
    "technical_support",
    "warranty_claim",
    "product_info",
    "promotion_loyalty",
    "account_privacy",
    "human_support",
    "out_of_scope",
]

BASE = [
    {
        "id": "INT-9001",
        "language": "fr",
        "text": "où est ma commande",
        "target_intent": "order_tracking",
        "case_type": "typical",
        "source": "synthetic",
        "split": "val",
    },
    {
        "id": "INT-9002",
        "language": "en",
        "text": "where is my order",
        "target_intent": "order_tracking",
        "case_type": "typical",
        "source": "synthetic",
        "split": "test",
    },
    {
        "id": "INT-9003",
        "language": "fr",
        "text": "mon colis est en retard",
        "target_intent": "delivery_issue",
        "case_type": "typical",
        "source": "synthetic",
        "split": "val",
    },
    {
        "id": "INT-9004",
        "language": "en",
        "text": "my parcel is late",
        "target_intent": "delivery_issue",
        "case_type": "typical",
        "source": "synthetic",
        "split": "test",
    },
    {
        "id": "INT-9005",
        "language": "fr",
        "text": "suivre mon colis",
        "target_intent": "order_tracking",
        "case_type": "typical",
        "source": "synthetic",
        "split": "train",
    },
    {
        "id": "INT-9006",
        "language": "en",
        "text": "track my parcel",
        "target_intent": "order_tracking",
        "case_type": "typical",
        "source": "synthetic",
        "split": "train",
    },
    {
        "id": "INT-9007",
        "language": "fr",
        "text": "colis pas reçu",
        "target_intent": "delivery_issue",
        "case_type": "typical",
        "source": "synthetic",
        "split": "train",
    },
    {
        "id": "INT-9008",
        "language": "en",
        "text": "parcel not received",
        "target_intent": "delivery_issue",
        "case_type": "typical",
        "source": "synthetic",
        "split": "train",
    },
]

VAL_TEST_IDS = ["INT-9001", "INT-9002", "INT-9003", "INT-9004"]
SPOT_IDS = ["INT-9005", "INT-9006", "INT-9007", "INT-9008"]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sheet_rows(ids: list[str], labels: dict[str, str], *, ambiguous: bool = False) -> list[dict]:
    by_id = {row["id"]: row for row in BASE}
    rows = []
    for identifier in ids:
        candidate = by_id[identifier]
        rows.append(
            {
                "id": identifier,
                "language": candidate["language"],
                "text": candidate["text"],
                "intent": labels[identifier],
                "ambiguous": "TRUE" if ambiguous else "FALSE",
                "acceptable_labels": "",
                "notes": "",
            }
        )
    return rows


class MergeAnnotationsTests(unittest.TestCase):
    def make_config(
        self,
        *,
        aya_labels: dict[str, str] | None = None,
        mohammed_labels: dict[str, str] | None = None,
        spot_labels: dict[str, str] | None = None,
        drop_mohammed_id: str | None = None,
        invalid_ambiguous: bool = False,
        include_mohammed: bool = True,
    ) -> merge.Config:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        private = tmp / "data" / "annotations" / "_private"
        blind = tmp / "data" / "annotations" / "blind"
        reports = tmp / "docs" / "reports"
        private.mkdir(parents=True)
        blind.mkdir(parents=True)
        reports.mkdir(parents=True)

        intents_path = tmp / "data" / "annotations" / "intents.csv"
        write_csv(intents_path, ["intent_id"], [{"intent_id": code} for code in CODES])

        candidates_path = private / "intent_candidates.jsonl"
        with candidates_path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in BASE:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        split_path = private / "intent_split.csv"
        write_csv(
            split_path,
            ["id", "split"],
            [{"id": row["id"], "split": row["split"]} for row in BASE],
        )

        default_labels = {row["id"]: row["target_intent"] for row in BASE}
        aya = dict(default_labels)
        if aya_labels:
            aya.update(aya_labels)
        mohammed = dict(default_labels)
        if mohammed_labels:
            mohammed.update(mohammed_labels)
        spot = dict(default_labels)
        if spot_labels:
            spot.update(spot_labels)

        aya_rows = sheet_rows(VAL_TEST_IDS, aya)
        if invalid_ambiguous:
            aya_rows[0]["ambiguous"] = "TRUE"
            aya_rows[0]["acceptable_labels"] = ""
        mohammed_rows = sheet_rows(VAL_TEST_IDS, mohammed)
        if drop_mohammed_id:
            mohammed_rows = [row for row in mohammed_rows if row["id"] != drop_mohammed_id]
        spot_rows = sheet_rows(SPOT_IDS, spot)

        write_csv(blind / "annotate_aya_done.csv", merge.ANNOTATION_COLUMNS, aya_rows)
        if include_mohammed:
            write_csv(blind / "annotate_mohammed_done.csv", merge.ANNOTATION_COLUMNS, mohammed_rows)
        write_csv(blind / "spotcheck_train_aya_done.csv", merge.ANNOTATION_COLUMNS, spot_rows)

        return merge.Config(
            root=tmp,
            blind_dir=blind,
            candidates_path=candidates_path,
            split_path=split_path,
            intents_path=intents_path,
            adjudication_path=reports / "adjudication_log.csv",
            previous_path=reports / "adjudication_log.previous.csv",
            dataset_jsonl=tmp / "data" / "annotations" / "intent_dataset.jsonl",
            dataset_csv=tmp / "data" / "annotations" / "intent_dataset.csv",
            report_path=reports / "intent_dataset_report.md",
            guidelines_path=tmp / "docs" / "annotation_guidelines.md",
            today="2026-11-12",
        )

    def run_quietly(
        self, config: merge.Config, build: bool = False, single_annotator: bool = False
    ) -> int:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            return merge.run(config, build=build, single_annotator=single_annotator)

    def test_perfect_agreement_builds_dataset(self):
        config = self.make_config()
        self.assertEqual(self.run_quietly(config), 0)

        with config.adjudication_path.open(encoding="utf-8", newline="") as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])
        report = config.report_path.read_text(encoding="utf-8")
        self.assertIn("| ensemble | 4 | 4 | 100,00 % | 1,000 |", report)
        self.assertIn("Désaccords val+test : **0**", report)

        self.assertEqual(self.run_quietly(config, build=True), 0)
        dataset = [
            json.loads(line)
            for line in config.dataset_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(dataset), 8)
        self.assertEqual(list(dataset[0]), merge.DATASET_FIELDS)
        by_id = {row["id"]: row for row in dataset}
        self.assertEqual(by_id["INT-9001"]["split"], "val")
        self.assertEqual(by_id["INT-9001"]["annotator_2"], "mohammed")
        self.assertFalse(by_id["INT-9001"]["adjudicated"])
        self.assertEqual(by_id["INT-9005"]["split"], "train")
        self.assertIsNone(by_id["INT-9005"]["annotator_2"])
        self.assertEqual(by_id["INT-9001"]["created_at"], "2026-11-12")

        with config.dataset_csv.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, merge.DATASET_CSV_FIELDS)
            self.assertEqual(len(list(reader)), 8)

    def test_one_disagreement_requires_adjudication(self):
        config = self.make_config(mohammed_labels={"INT-9001": "delivery_issue"})
        self.assertEqual(self.run_quietly(config), 0)

        with config.adjudication_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "INT-9001")
        self.assertEqual(rows[0]["intent_aya"], "order_tracking")
        self.assertEqual(rows[0]["intent_mohammed"], "delivery_issue")
        for column in ("adjudicated_intent", "arbiter", "date", "justification"):
            self.assertEqual(rows[0][column], "")

        self.assertEqual(self.run_quietly(config, build=True), 1)
        self.assertFalse(config.dataset_jsonl.exists())

        rows[0].update(
            {
                "adjudicated_intent": "order_tracking",
                "arbiter": "test",
                "date": "2026-11-12",
                "justification": "test",
            }
        )
        write_csv(config.adjudication_path, merge.ADJUDICATION_COLUMNS, rows)
        self.assertEqual(self.run_quietly(config, build=True), 0)
        dataset = {
            row["id"]: row
            for row in (
                json.loads(line)
                for line in config.dataset_jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        self.assertEqual(dataset["INT-9001"]["intent"], "order_tracking")
        self.assertTrue(dataset["INT-9001"]["adjudicated"])
        self.assertEqual(dataset["INT-9001"]["annotator_2"], "mohammed")
        report = config.report_path.read_text(encoding="utf-8")
        self.assertIn("Désaccords en attente d'arbitrage : **0**", report)

    def test_validation_error_stops_before_writing(self):
        with self.subTest("id manquant"):
            config = self.make_config(drop_mohammed_id="INT-9001")
            self.assertEqual(self.run_quietly(config), 1)
            self.assertFalse(config.adjudication_path.exists())
        with self.subTest("ambiguous sans acceptable_labels"):
            config = self.make_config(invalid_ambiguous=True)
            self.assertEqual(self.run_quietly(config), 1)
            self.assertFalse(config.adjudication_path.exists())

    def test_manual_kappa(self):
        self.assertAlmostEqual(
            merge.manual_cohen_kappa(["a", "a", "b", "b"], ["a", "b", "b", "b"], ["a", "b"]),
            0.5,
        )
        self.assertIsNone(merge.manual_cohen_kappa(["a", "a"], ["a", "a"], ["a"]))

    def test_misalignment_detection(self):
        aya_list = [
            merge.Annotation("1", "fr", "texte a", "order_tracking", False, [], "", Path("a"), 2),
            merge.Annotation("2", "fr", "texte b", "delivery_issue", False, [], "", Path("a"), 3),
        ]
        mohammed_list = [
            merge.Annotation("2", "fr", "texte b", "order_tracking", False, [], "", Path("m"), 2),
            merge.Annotation("1", "fr", "texte a", "delivery_issue", False, [], "", Path("m"), 3),
        ]
        result = merge.detect_misalignment(
            aya_list,
            mohammed_list,
            {row.id: row for row in aya_list},
            {row.id: row for row in mohammed_list},
        )
        self.assertTrue(result["suspected"])
        self.assertTrue(result["same_positional_labels"])
        self.assertFalse(result["same_text_order"])
        self.assertEqual(result["per_id_agreement"], 0)

    def test_top_confusions_and_validation(self):
        config = self.make_config(mohammed_labels={"INT-9001": "delivery_issue"})
        candidates = merge.load_candidates(config)
        split = merge.load_split(config)
        codes, _ = merge.load_intents(config)
        annotations, errors, _warnings, _misalignment, _paths = merge.validate_inputs(
            config, candidates, split, codes
        )
        self.assertEqual(errors, [])
        agreement = merge.analyze_agreement(annotations, split, codes)
        self.assertEqual(agreement["ensemble"]["n"], 4)
        self.assertEqual(agreement["ensemble"]["agreements"], 3)
        self.assertIn(
            ("order_tracking", "delivery_issue", 1),
            agreement["ensemble"]["top_confusions"],
        )

    def test_single_annotator_does_not_read_mohammed_or_write_adjudication(self):
        config = self.make_config(include_mohammed=False)
        self.assertFalse((config.blind_dir / "annotate_mohammed_done.csv").exists())
        self.assertEqual(self.run_quietly(config, single_annotator=True), 0)

        report = config.report_path.read_text(encoding="utf-8")
        self.assertIn("annotateur unique (Aya) ; accord inter-annotateurs non mesuré", report)
        self.assertIn("non mesuré (annotateur unique)", report)
        self.assertIn("NON APPLICABLE", report)
        self.assertNotIn("deux annotateurs", report.lower())
        self.assertNotIn("taux d'accord", report.lower())
        self.assertIsNone(re.search(r"κ\s*[=:]\s*[-+]?\d", report))
        self.assertFalse(config.adjudication_path.exists())
        self.assertFalse(config.dataset_jsonl.exists())
        self.assertFalse(config.dataset_csv.exists())

    def test_single_annotator_build_has_null_second_annotator_and_status(self):
        config = self.make_config(include_mohammed=False)
        self.assertEqual(
            self.run_quietly(config, build=True, single_annotator=True), 0
        )
        dataset = [
            json.loads(line)
            for line in config.dataset_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(dataset), 8)
        by_id = {row["id"]: row for row in dataset}
        targets = {row["id"]: row["target_intent"] for row in BASE}
        for identifier in VAL_TEST_IDS:
            row = by_id[identifier]
            self.assertIsNone(row["annotator_2"])
            self.assertFalse(row["adjudicated"])
            self.assertEqual(row["annotation_status"], "single_annotator")
            self.assertEqual(row["intent"], targets[identifier])
        for identifier in SPOT_IDS:
            row = by_id[identifier]
            self.assertIsNone(row["annotator_2"])
            self.assertFalse(row["adjudicated"])
            self.assertNotIn("annotation_status", row)
        self.assertEqual(by_id["INT-9001"]["created_at"], "2026-11-12")
        with config.dataset_csv.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, merge.DATASET_CSV_FIELDS)
            self.assertEqual(len(list(reader)), 8)
        self.assertFalse(config.adjudication_path.exists())
        report = config.report_path.read_text(encoding="utf-8")
        self.assertIn("écrit : 8 lignes", report)

    def test_single_annotator_lists_target_differences_without_correcting(self):
        config = self.make_config(
            include_mohammed=False, aya_labels={"INT-9001": "delivery_issue"}
        )
        self.assertEqual(self.run_quietly(config, single_annotator=True), 0)
        report = config.report_path.read_text(encoding="utf-8")
        self.assertIn("Différences val/test : **1/4**", report)
        self.assertIn("| val | INT-9001 |", report)
        self.assertIn("delivery_issue", report)
        self.assertIn("order_tracking", report)

        self.assertEqual(
            self.run_quietly(config, build=True, single_annotator=True), 0
        )
        dataset = {
            row["id"]: row
            for row in (
                json.loads(line)
                for line in config.dataset_jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        self.assertEqual(dataset["INT-9001"]["intent"], "delivery_issue")
        self.assertEqual(dataset["INT-9001"]["annotation_status"], "single_annotator")

    def test_single_annotator_train_contradiction_is_preserved(self):
        config = self.make_config(
            include_mohammed=False, spot_labels={"INT-9005": "delivery_issue"}
        )
        self.assertEqual(
            self.run_quietly(config, build=True, single_annotator=True), 0
        )
        dataset = {
            row["id"]: row
            for row in (
                json.loads(line)
                for line in config.dataset_jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        row = dataset["INT-9005"]
        self.assertEqual(row["intent"], "delivery_issue")
        self.assertIn("Sondage Aya", row["notes"])
        self.assertIn("cible : order_tracking", row["notes"])
        self.assertIsNone(row["annotator_2"])
        self.assertNotIn("annotation_status", row)
        report = config.report_path.read_text(encoding="utf-8")
        self.assertIn("Différences train sondé : **1/4**", report)

    def test_single_annotator_validation_error_stops_before_writing(self):
        config = self.make_config(
            include_mohammed=False, invalid_ambiguous=True
        )
        self.assertEqual(self.run_quietly(config, single_annotator=True), 1)
        self.assertFalse(config.report_path.exists())
        self.assertFalse(config.dataset_jsonl.exists())
        self.assertFalse(config.adjudication_path.exists())

    def test_parser_accepts_single_annotator_flag(self):
        args = merge.build_parser().parse_args(["--single-annotator", "--build"])
        self.assertTrue(args.single_annotator)
        self.assertTrue(args.build)


if __name__ == "__main__":
    unittest.main(verbosity=2)
