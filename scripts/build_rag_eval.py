"""Validate and build the 140-question RAG evaluation set.

Subcommands
-----------
validate : run the seven checks required by the task and print OK/KO.
build    : validate, then write the passage-enriched JSONL, the report and the
           human review sheet. The script never edits a gold answer and never
           copies a passage by hand: passages are read from chunked_corpus.jsonl.

Standard library only.
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "processed" / "chunked_corpus.jsonl"
RAG_PATH = ROOT / "data" / "annotations" / "rag_eval.jsonl"
ROB_PATH = ROOT / "data" / "annotations" / "robustness_eval.jsonl"
WITH_PASSAGES_PATH = ROOT / "data" / "annotations" / "rag_eval_with_passages.jsonl"
INTENTS_PATH = ROOT / "data" / "annotations" / "intents.csv"
CANDIDATES_PATH = ROOT / "data" / "annotations" / "_private" / "intent_candidates.jsonl"
REPORT_PATH = ROOT / "docs" / "reports" / "rag_eval_report.md"
REVIEW_PATH = ROOT / "docs" / "reports" / "rag_eval_review.md"

ALLOWED_DOCS = (
    [f"FAQ-{i:02d}" for i in range(1, 9)]
    + [f"POL-{i:02d}" for i in range(1, 11)]
    + [f"PRO-{i:02d}" for i in range(1, 5)]
    + [f"CAT-{i:02d}" for i in range(1, 7)]
    + ["OPS-04", "REG-04"]
)
ALLOWED_DOC_SET = set(ALLOWED_DOCS)

EXPECTED_TYPES = {
    "lexical": 42,
    "semantic": 56,
    "procedural": 28,
    "out_of_corpus": 14,
}
EXPECTED_LANGS = {"fr": 84, "en": 56}
EXPECTED_TYPE_LANG = {
    ("lexical", "fr"): 28,
    ("lexical", "en"): 14,
    ("semantic", "fr"): 40,
    ("semantic", "en"): 16,
    ("procedural", "fr"): 8,
    ("procedural", "en"): 20,
    ("out_of_corpus", "fr"): 8,
    ("out_of_corpus", "en"): 6,
}
ROB_CATEGORIES = {
    "explicit_answer": 10,
    "no_answer": 8,
    "ambiguous": 6,
    "rephrasing": 6,
    "human_handoff": 5,
}

RAG_FIELDS = [
    "id", "question", "language", "intent", "answerable", "gold_doc_ids",
    "gold_chunk_ids", "gold_relevance", "gold_answer", "question_type",
    "expected_behavior", "source", "reviewed_by", "notes",
]
ROB_FIELDS = [
    "id", "question", "language", "category", "expected_behavior",
    "gold_chunk_ids", "notes",
]

FR_EN_STOPWORDS = set(
    """a au aux avec ce ces dans de des du elle en et eux il je la le les leur
    lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que
    qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y
    the a an and are as at be by can do does for from has have how i if in is it
    my of on or our that the this to was what when where which who why will with
    you your""".split()
)


def load_jsonl(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_corpus():
    rows = load_jsonl(CORPUS_PATH)
    return {(r["chunk_id"], r["language"]): r for r in rows}


def load_intents():
    with INTENTS_PATH.open(encoding="utf-8-sig", newline="") as f:
        return {row["intent_id"] for row in csv.DictReader(f)}


def ascii_fold(text):
    text = text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def tokens(text, min_len=1):
    return [t for t in re.findall(r"[a-z0-9]+", ascii_fold(text)) if len(t) >= min_len]


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def normalize_question(text):
    return " ".join(tokens(text, 1))


def normalize_number(token):
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
        return token.replace(",", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        return token.replace(".", "")
    return token.replace(",", ".")


def numbers(text):
    text = text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    text = re.sub(r"(?<=\d)[ \u00a0\u202f]+(?=\d)", "", text)
    return [normalize_number(t) for t in re.findall(r"\d+(?:[.,]\d+)*", text)]


def sentence_count(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return len([p for p in parts if p.strip()])


def question_words(text):
    return [t for t in tokens(text, 3) if t not in FR_EN_STOPWORDS]


def nearest_chunks(question, language, corpus, limit=3):
    q = set(question_words(question))
    scored = []
    for (chunk_id, lang), rec in corpus.items():
        if lang != language:
            continue
        if rec.get("audience") != "customer" or not rec.get("index_in_rag"):
            continue
        if rec.get("doc_id") not in ALLOWED_DOC_SET:
            continue
        c = set(question_words(rec.get("section_heading", "") + " " + rec.get("text", "")))
        if not q or not c:
            score = 0.0
        else:
            score = len(q & c) / len(q | c)
        scored.append((score, chunk_id, rec))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:limit]


def add_check(checks, name, ok, details=None):
    checks.append({"name": name, "ok": bool(ok), "details": details or []})


def validate_data(rag, rob, corpus, intents, verbose=True):
    checks = []

    # 1. Structure, counts and values.
    problems = []
    if len(rag) != 140:
        problems.append(f"rag_eval has {len(rag)} rows, expected 140")
    if len(rob) != 35:
        problems.append(f"robustness_eval has {len(rob)} rows, expected 35")
    if len({r.get("id") for r in rag}) != len(rag):
        problems.append("duplicate RET ids")
    expected_ids = [f"RET-{i:04d}" for i in range(1, 141)]
    if sorted(r.get("id") for r in rag) != expected_ids:
        problems.append("RET ids are not exactly RET-0001..RET-0140")
    if len({r.get("id") for r in rob}) != len(rob):
        problems.append("duplicate ROB ids")
    expected_rob_ids = [f"ROB-{i:03d}" for i in range(1, 36)]
    if sorted(r.get("id") for r in rob) != expected_rob_ids:
        problems.append("ROB ids are not exactly ROB-001..ROB-035")

    type_counts = Counter(r.get("question_type") for r in rag)
    lang_counts = Counter(r.get("language") for r in rag)
    type_lang_counts = Counter((r.get("question_type"), r.get("language")) for r in rag)
    if dict(type_counts) != EXPECTED_TYPES:
        problems.append(f"type counts {dict(type_counts)} != {EXPECTED_TYPES}")
    if dict(lang_counts) != EXPECTED_LANGS:
        problems.append(f"language counts {dict(lang_counts)} != {EXPECTED_LANGS}")
    if dict(type_lang_counts) != EXPECTED_TYPE_LANG:
        problems.append(f"type x language counts {dict(type_lang_counts)} != {EXPECTED_TYPE_LANG}")

    for row in rag:
        missing = [f for f in RAG_FIELDS if f not in row]
        extra = [f for f in row if f not in RAG_FIELDS]
        if missing:
            problems.append(f"{row.get('id')}: missing fields {missing}")
        if extra:
            problems.append(f"{row.get('id')}: unexpected fields {extra}")
        if row.get("language") not in ("fr", "en"):
            problems.append(f"{row.get('id')}: bad language {row.get('language')!r}")
        if row.get("question_type") not in EXPECTED_TYPES:
            problems.append(f"{row.get('id')}: bad question_type {row.get('question_type')!r}")
        if row.get("intent") not in intents:
            problems.append(f"{row.get('id')}: unknown intent {row.get('intent')!r}")
        if row.get("source") != "synthetic":
            problems.append(f"{row.get('id')}: source must be 'synthetic'")
        if row.get("reviewed_by") is not None:
            problems.append(f"{row.get('id')}: reviewed_by must stay null")
        if not isinstance(row.get("answerable"), bool):
            problems.append(f"{row.get('id')}: answerable must be boolean")
        if not isinstance(row.get("notes"), str):
            problems.append(f"{row.get('id')}: notes must be a string")
        q = row.get("question") or ""
        wc = len(q.split())
        if not 4 <= wc <= 40:
            problems.append(f"{row.get('id')}: question has {wc} words, expected 4..40")
        if re.search(r"[\u0600-\u06ff]", q):
            problems.append(f"{row.get('id')}: Arabic script in question")
        if row.get("answerable"):
            if row.get("expected_behavior") != "answer_with_citation":
                problems.append(f"{row.get('id')}: answerable question must use answer_with_citation")
            if not isinstance(row.get("gold_answer"), str) or not row["gold_answer"].strip():
                problems.append(f"{row.get('id')}: answerable question needs a gold_answer")
            elif sentence_count(row["gold_answer"]) > 3:
                problems.append(f"{row.get('id')}: gold_answer has more than 3 sentences")
        else:
            if row.get("question_type") != "out_of_corpus":
                problems.append(f"{row.get('id')}: only out_of_corpus may be unanswerable")
            if row.get("expected_behavior") != "abstain_and_offer_human":
                problems.append(f"{row.get('id')}: unanswerable question must abstain")
            if row.get("gold_answer") is not None:
                problems.append(f"{row.get('id')}: unanswerable question must have null gold_answer")

    for row in rob:
        missing = [f for f in ROB_FIELDS if f not in row]
        extra = [f for f in row if f not in ROB_FIELDS]
        if missing:
            problems.append(f"{row.get('id')}: missing fields {missing}")
        if extra:
            problems.append(f"{row.get('id')}: unexpected fields {extra}")
        if row.get("language") not in ("fr", "en"):
            problems.append(f"{row.get('id')}: bad language {row.get('language')!r}")
        if row.get("category") not in ROB_CATEGORIES:
            problems.append(f"{row.get('id')}: bad category {row.get('category')!r}")
        q = row.get("question") or ""
        wc = len(q.split())
        if not 1 <= wc <= 40:
            problems.append(f"{row.get('id')}: question has {wc} words, expected 1..40")
        if re.search(r"[\u0600-\u06ff]", q):
            problems.append(f"{row.get('id')}: Arabic script in question")
        if not isinstance(row.get("expected_behavior"), str) or not row["expected_behavior"].strip():
            problems.append(f"{row.get('id')}: missing expected_behavior")
        if not isinstance(row.get("gold_chunk_ids"), list):
            problems.append(f"{row.get('id')}: gold_chunk_ids must be a list")
        if not isinstance(row.get("notes"), str):
            problems.append(f"{row.get('id')}: notes must be a string")

    rob_counts = Counter(r.get("category") for r in rob)
    if dict(rob_counts) != ROB_CATEGORIES:
        problems.append(f"robustness categories {dict(rob_counts)} != {ROB_CATEGORIES}")

    add_check(checks, "1. Structure, ids, types, languages and field values", not problems, problems)

    # 2. Gold chunks exist, are customer/indexable, and doc ids agree.
    problems = []
    for row in rag:
        rid = row.get("id")
        chunks = row.get("gold_chunk_ids")
        rel = row.get("gold_relevance")
        docs = row.get("gold_doc_ids")
        if not isinstance(chunks, list) or not isinstance(rel, dict) or not isinstance(docs, list):
            problems.append(f"{rid}: gold_chunk_ids/gold_relevance/gold_doc_ids have wrong types")
            continue
        if list(rel.keys()) != chunks:
            problems.append(f"{rid}: gold_relevance keys do not match gold_chunk_ids order")
        for cid in chunks:
            key = (cid, row.get("language"))
            rec = corpus.get(key)
            if rec is None:
                problems.append(f"{rid}: {cid} does not exist for language {row.get('language')}")
                continue
            if rec.get("audience") != "customer":
                problems.append(f"{rid}: {cid} is not audience=customer")
            if not rec.get("index_in_rag"):
                problems.append(f"{rid}: {cid} is not index_in_rag")
            if rec.get("doc_id") not in ALLOWED_DOC_SET:
                problems.append(f"{rid}: {cid} belongs to non-allowed doc {rec.get('doc_id')}")
            if rel.get(cid) not in (1, 2):
                problems.append(f"{rid}: {cid} relevance must be 1 or 2")
        expected_docs = list(dict.fromkeys(cid.split("#", 1)[0] for cid in chunks))
        if docs != expected_docs:
            problems.append(f"{rid}: gold_doc_ids {docs} != {expected_docs}")
    for row in rob:
        for cid in row.get("gold_chunk_ids", []):
            rec = corpus.get((cid, row.get("language")))
            if rec is None:
                problems.append(f"{row.get('id')}: {cid} does not exist for language {row.get('language')}")
            elif rec.get("audience") != "customer" or not rec.get("index_in_rag"):
                problems.append(f"{row.get('id')}: {cid} is not a customer/indexable chunk")
    add_check(checks, "2. Gold chunks exist, are customer/indexable and docs agree", not problems, problems)

    # 3. Answerability consistency.
    problems = []
    for row in rag:
        rid = row.get("id")
        chunks = row.get("gold_chunk_ids") or []
        rel = row.get("gold_relevance") or {}
        if row.get("answerable") is False:
            if chunks:
                problems.append(f"{rid}: unanswerable question has gold chunks")
            if row.get("gold_answer") is not None:
                problems.append(f"{rid}: unanswerable question has a gold answer")
            if row.get("gold_doc_ids"):
                problems.append(f"{rid}: unanswerable question has gold docs")
        elif row.get("answerable") is True:
            if not chunks:
                problems.append(f"{rid}: answerable question has no gold chunk")
            if not any(rel.get(cid) == 2 for cid in chunks):
                problems.append(f"{rid}: answerable question needs at least one relevance-2 chunk")
    add_check(checks, "3. answerable=false => empty/null; answerable=true => relevance 2", not problems, problems)

    # 4. Every number in gold_answer appears in the gold chunks.
    problems = []
    numeric_questions = 0
    for row in rag:
        if not row.get("answerable"):
            continue
        answer = row.get("gold_answer") or ""
        answer_nums = numbers(answer)
        if answer_nums:
            numeric_questions += 1
        gold_text = "\n".join(
            corpus[(cid, row["language"])]["text"]
            for cid in row["gold_chunk_ids"]
            if (cid, row["language"]) in corpus
        )
        gold_nums = set(numbers(gold_text))
        missing = [n for n in answer_nums if n not in gold_nums]
        if missing:
            problems.append(f"{row['id']}: numbers absent from gold chunks: {missing}")
    if numeric_questions < 20:
        problems.append(f"only {numeric_questions} numeric questions, expected >= 20")
    add_check(checks, "4. Every number in gold_answer is grounded in a gold chunk", not problems, problems)

    # 5. Question vs section heading, and semantic keyword ban.
    problems = []
    for row in rag:
        if not row.get("answerable"):
            continue
        q_tokens = set(tokens(row["question"]))
        for cid in row["gold_chunk_ids"]:
            rec = corpus.get((cid, row["language"]))
            if rec is None:
                continue
            heading = rec.get("section_heading", "")
            h_tokens = set(tokens(heading))
            score = jaccard(q_tokens, h_tokens)
            if score >= 0.6:
                problems.append(f"{row['id']}: Jaccard {score:.2f} with heading {heading!r}")
            if row["question_type"] == "semantic":
                banned = sorted(t for t in h_tokens if len(t) >= 5 and t in q_tokens)
                if banned:
                    problems.append(f"{row['id']}: semantic question contains heading words {banned}")
    add_check(checks, "5. Question != section title; semantic questions avoid title keywords", not problems, problems)

    # 6. Exact and quasi duplicates.
    problems = []
    candidates = load_jsonl(CANDIDATES_PATH) if CANDIDATES_PATH.exists() else []
    candidate_rows = [
        {"id": c["id"], "question": c["text"], "language": c["language"]}
        for c in candidates
    ]

    def compare(left, right, label, compare_same_list=False):
        exact = {}
        pairs = []
        for i, a in enumerate(left):
            na = normalize_question(a["question"])
            exact.setdefault((a["language"], na), []).append(a["id"])
            start = i + 1 if compare_same_list else 0
            for b in right[start:]:
                if a["language"] != b["language"]:
                    continue
                if a["id"] == b["id"]:
                    continue
                score = jaccard(tokens(a["question"]), tokens(b["question"]))
                if score >= 0.8:
                    pairs.append((score, a["id"], b["id"], a["question"], b["question"]))
        for (lang, _), ids in exact.items():
            if len(ids) > 1:
                problems.append(f"{label}: exact duplicate ({lang}): {ids}")
        for score, aid, bid, aq, bq in sorted(pairs, key=lambda x: (-x[0], x[1], x[2])):
            problems.append(f"{label}: Jaccard {score:.2f} {aid} / {bid}: {aq!r} <> {bq!r}")

    compare(rag, rag, "rag_eval", compare_same_list=True)
    compare(rob, rob, "robustness_eval", compare_same_list=True)
    compare(rag, rob, "rag_eval vs robustness_eval")
    compare(rag, candidate_rows, "rag_eval vs intent_candidates")
    compare(rob, candidate_rows, "robustness_eval vs intent_candidates")
    add_check(checks, "6. No exact duplicate and no quasi-duplicate (Jaccard >= 0.8)", not problems, problems)

    # 7. Nearest chunks for each out-of-corpus question (human control).
    ooc_details = []
    for row in rag:
        if row.get("answerable") is not False:
            continue
        nearest = nearest_chunks(row["question"], row["language"], corpus, limit=3)
        ooc_details.append((row["id"], row["question"], row["language"], nearest))
    add_check(
        checks,
        "7. Out-of-corpus questions: three nearest chunks shown for human control",
        True,
        [f"{len(ooc_details)} out-of-corpus questions checked; see the list below."],
    )

    if verbose:
        print("RAG evaluation validation")
        print("=" * 78)
        for check in checks:
            print(f"[{'OK' if check['ok'] else 'KO'}] {check['name']}")
            for detail in check["details"]:
                print(f"     - {detail}")
        print()
        print("Out-of-corpus nearest chunks (word-overlap control)")
        print("-" * 78)
        for rid, question, lang, nearest in ooc_details:
            print(f"{rid} [{lang}] {question}")
            for score, cid, rec in nearest:
                heading = rec.get("section_heading", "")
                snippet = " ".join(rec.get("text", "").split())[:180]
                print(f"   {score:.3f}  {cid}  {heading}  | {snippet}")
            print()

    return checks, ooc_details, numeric_questions


def distribution_rows(rag):
    type_counts = Counter(r["question_type"] for r in rag)
    lang_counts = Counter(r["language"] for r in rag)
    matrix = Counter((r["question_type"], r["language"]) for r in rag)
    return type_counts, lang_counts, matrix


def primary_doc_coverage(rag):
    counts = Counter()
    for row in rag:
        if row.get("answerable") and row.get("gold_doc_ids"):
            counts[row["gold_doc_ids"][0]] += 1
    return counts


def build_outputs(rag, rob, corpus, checks, ooc_details, numeric_questions):
    # Passage-enriched JSONL, copied from the corpus.
    with WITH_PASSAGES_PATH.open("w", encoding="utf-8", newline="\n") as f:
        for row in rag:
            passages = []
            for cid in row["gold_chunk_ids"]:
                rec = corpus[(cid, row["language"])]
                passages.append({
                    "chunk_id": rec["chunk_id"],
                    "doc_id": rec["doc_id"],
                    "section_heading": rec["section_heading"],
                    "text": rec["text"],
                })
            out = dict(row)
            out["gold_passages"] = passages
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    type_counts, lang_counts, matrix = distribution_rows(rag)
    doc_counts = primary_doc_coverage(rag)
    multi_chunk = sum(1 for r in rag if len(r["gold_chunk_ids"]) > 1)
    numeric = sum(
        1 for r in rag
        if r.get("answerable") and numbers(r.get("gold_answer") or "")
    )
    typo_count = sum(1 for r in rag if "Faute légère volontaire" in r.get("notes", ""))

    lines = []
    lines.append("# RAG evaluation set — build report")
    lines.append("")
    lines.append("> Deterministic report. No timestamp is stored.")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("| File | Rows | Content |")
    lines.append("| --- | ---: | --- |")
    lines.append(f"| `data/annotations/rag_eval.jsonl` | {len(rag)} | Questions, gold chunks, relevance and reference answers |")
    lines.append(f"| `data/annotations/robustness_eval.jsonl` | {len(rob)} | Robustness cases, outside the 140-question set |")
    lines.append(f"| `data/annotations/rag_eval_with_passages.jsonl` | {len(rag)} | Same rows plus `gold_passages` copied from the corpus |")
    lines.append(f"| `docs/reports/rag_eval_review.md` | 39 | 25 sampled questions + all 14 out-of-corpus questions |")
    lines.append("")
    lines.append("## Distribution")
    lines.append("")
    lines.append("| Question type | FR | EN | Total |")
    lines.append("| --- | ---: | ---: | ---: |")
    for qtype in ("lexical", "semantic", "procedural", "out_of_corpus"):
        lines.append(
            f"| `{qtype}` | {matrix[(qtype, 'fr')]} | {matrix[(qtype, 'en')]} | {type_counts[qtype]} |"
        )
    lines.append(f"| **Total** | **{lang_counts['fr']}** | **{lang_counts['en']}** | **{len(rag)}** |")
    lines.append("")
    lines.append(f"- Multi-chunk questions (relevance 2 + 1): **{multi_chunk}** (threshold: 15)")
    lines.append(f"- Questions whose reference answer contains a number: **{numeric}** (threshold: 20)")
    lines.append(f"- Questions with one deliberate light typo: **{typo_count}** (~15 % style target)")
    lines.append("")
    lines.append("## Coverage by customer document")
    lines.append("")
    lines.append("Primary document = first gold document of an answerable question. The 14 out-of-corpus questions have no document.")
    lines.append("")
    lines.append("| Document | Questions |")
    lines.append("| --- | ---: |")
    for doc in ALLOWED_DOCS:
        lines.append(f"| `{doc}` | {doc_counts[doc]} |")
    lines.append(f"| **Total answerable** | **{sum(doc_counts.values())}** |")
    lines.append("")
    lines.append("## Validation checks")
    lines.append("")
    lines.append("| # | Check | Result |")
    lines.append("| ---: | --- | --- |")
    for i, check in enumerate(checks, 1):
        result = "OK" if check["ok"] else "KO"
        lines.append(f"| {i} | {check['name']} | **{result}** |")
    lines.append("")
    lines.append("All seven checks are expected to be OK before `build` writes this report.")
    lines.append("")
    lines.append("## Out-of-corpus questions and nearest chunks")
    lines.append("")
    lines.append("The three nearest customer/indexable chunks are shown by word overlap. They are controls, not gold evidence: none of them answers the question.")
    lines.append("")
    for rid, question, lang, nearest in ooc_details:
        lines.append(f"### {rid} [{lang}]")
        lines.append("")
        lines.append(f"**Question:** {question}")
        lines.append("")
        lines.append("| Overlap | Chunk | Heading |")
        lines.append("| ---: | --- | --- |")
        for score, cid, rec in nearest:
            lines.append(f"| {score:.3f} | `{cid}` | {rec.get('section_heading', '')} |")
        lines.append("")
    lines.append("## What was not done")
    lines.append("")
    lines.append("- `reviewed_by` is still `null` for every row. Aya performs the final human review.")
    lines.append("- No retrieval metric (Recall@k, MRR, nDCG) was computed: this task builds the evaluation set, it does not run a retriever.")
    lines.append("- The contradictory and prompt-injection robustness categories are out of scope for this task.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # Human review sheet: 25 answerable sampled with seed 42 + all OOC.
    answerable = [r for r in rag if r["answerable"]]
    sampled = random.Random(42).sample(answerable, 25)
    review_rows = sorted(sampled + [r for r in rag if not r["answerable"]], key=lambda r: r["id"])

    lines = []
    lines.append("# RAG evaluation set — human review sheet")
    lines.append("")
    lines.append("> Review by Aya. The 25 answerable questions are sampled with `SEED = 42`; all 14 out-of-corpus questions are included. No timestamp is stored.")
    lines.append("")
    lines.append("For each question, check three things:")
    lines.append("")
    lines.append("1. The reference answer is fully supported by the gold passages and uses no outside knowledge.")
    lines.append("2. Every number in the answer appears in a gold passage.")
    lines.append("3. The question sounds like a real NovaShop customer question and does not copy a section title.")
    lines.append("")
    lines.append("After review, set `reviewed_by` in `data/annotations/rag_eval.jsonl` (for example `\"aya\"`). Do not edit the gold passages by hand: rerun `python scripts/build_rag_eval.py build`.")
    lines.append("")
    for row in review_rows:
        lines.append(f"## {row['id']} — {row['question_type']} / {row['language']}")
        lines.append("")
        lines.append(f"**Question:** {row['question']}")
        lines.append("")
        if row["answerable"]:
            lines.append(f"**Reference answer:** {row['gold_answer']}")
            if row.get("notes"):
                lines.append("")
                lines.append(f"**Note:** {row['notes']}")
        else:
            lines.append("**Reference answer:** none (out of corpus).")
            lines.append("")
            lines.append(f"**Verification note:** {row['notes']}")
        lines.append("")
        lines.append("**Gold passages:**")
        lines.append("")
        if not row["gold_chunk_ids"]:
            lines.append("_No gold passage. This question must trigger abstention and a human handoff._")
            lines.append("")
        for cid in row["gold_chunk_ids"]:
            rec = corpus[(cid, row["language"])]
            lines.append(f"### `{cid}` — {rec.get('section_heading', '')}")
            lines.append("")
            lines.append("```text")
            lines.append(rec["text"].rstrip("\n"))
            lines.append("```")
            lines.append("")
        lines.append("- [ ] Answer grounded in the passages")
        lines.append("- [ ] Numbers verified")
        lines.append("- [ ] Natural customer question")
        lines.append("")
    REVIEW_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "build"))
    args = parser.parse_args()

    rag = load_jsonl(RAG_PATH)
    rob = load_jsonl(ROB_PATH)
    corpus = load_corpus()
    intents = load_intents()
    checks, ooc_details, numeric_questions = validate_data(rag, rob, corpus, intents, verbose=True)
    ok = all(c["ok"] for c in checks)

    if args.command == "validate":
        print("RESULT:", "OK" if ok else "KO")
        raise SystemExit(0 if ok else 1)

    if not ok:
        print("BUILD ABORTED: validation is KO. Fix the issues above and rerun.")
        raise SystemExit(1)

    build_outputs(rag, rob, corpus, checks, ooc_details, numeric_questions)
    print("BUILD OK")
    print(f"wrote {WITH_PASSAGES_PATH.relative_to(ROOT)}")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"wrote {REVIEW_PATH.relative_to(ROOT)}")
    print("sha256:")
    for path in (RAG_PATH, ROB_PATH, WITH_PASSAGES_PATH, REPORT_PATH, REVIEW_PATH):
        print(f"  {sha256(path)}  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
