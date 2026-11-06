# SupportAI — Document corpus & annotation guidelines

Deliverables for **Task 1 — Student 1 (Data Engineer & Dataset Manager)**.

> Collect 30 to 50 support documents, verify licences, define annotation guidelines.

🇫🇷 Version française : [`README.md`](README.md)

## Deliverables

| File | Content |
| --- | --- |
| `data/source_manifest.csv` | Manifest of 81 rows: 74 language files (37 documents × 2 languages) + 7 external references, with licence, verification status, permitted use and SHA-256 |
| `docs/annotation_guidelines.md` / `.en.md` | Full annotation guide: taxonomy, decision rules, retrieval and RAG scales, quality control |
| `docs/data_schema.md` | Data schema: front matter, manifest columns, JSONL records, FAQ formats |
| `data/raw/corpus/fr/`, `data/raw/corpus/en/` | The 37 NovaShop knowledge-base documents, in both languages (Markdown, YAML front matter) — authoring source |
| `data/processed/documents/` | The same documents delivered as **PDF**, **Word (.docx)** and **FAQ (JSON, JSONL, CSV)** |
| `data/processed/extracted/documents.jsonl` | Ingestion pipeline output: extracted, cleaned text with metadata |
| `data/annotations/intents.csv` | Machine-readable bilingual taxonomy: 13 intents + `out_of_scope` |
| `docs/reports/corpus_stats.md` | Corpus statistics (generated) |
| `docs/reports/extraction_report.md` | Extraction report: coverage, OCR, accent checks (generated) |
| `scripts/manage_corpus.py` | Manifest builder + quality validator, including FR/EN parity checks |
| `scripts/build_sources.py` | Generates the PDF / DOCX / FAQ deliverables from Markdown |
| `scripts/extract_documents.py` | PDF / DOCX / FAQ → cleaning → JSONL pipeline |

## Key figures

- **37 documents** per language, **74 files**, **35 918 words** (~48 490 tokens)
- **74 deliverables** in the required formats: 28 PDF, 30 DOCX, 16 FAQ (JSON/JSONL/CSV)
- **522 records** extracted and cleaned in `data/processed/extracted/documents.jsonl`
- 10 policies · 8 FAQs · 6 product guides · 4 procedures · 5 internal documents · 4 regulatory summaries
- 7 external references, **not indexed**, documented for their licences
- 0 validation errors, 0 exact duplicates, FR/EN parity verified

## Structure

```
.
├── data/
│   ├── raw/corpus/{fr,en}/          # 74 Markdown documents (37 × 2 languages)
│   ├── processed/documents/         # 74 deliverables in PDF / DOCX / FAQ
│   │   ├── pdf/{fr,en}/             # 28 PDF (policies, summaries)
│   │   ├── docx/{fr,en}/            # 30 DOCX (procedures, internal ops, guides)
│   │   ├── faq/{fr,en}/             # 16 FAQ (6 JSON, 6 JSONL, 4 CSV)
│   │   └── manifest_documents.csv
│   ├── processed/extracted/
│   │   └── documents.jsonl          # 522 extracted records
│   ├── annotations/intents.csv
│   └── source_manifest.csv
├── docs/
│   ├── annotation_guidelines.md / .en.md
│   ├── data_schema.md
│   ├── data-engineering/README.md / README.en.md
│   └── reports/
│       ├── corpus_stats.md
│       ├── extraction_report.md
│       ├── annotation_decisions.md
│       └── adjudication_log.csv
└── scripts/
    ├── manage_corpus.py
    ├── build_sources.py
    ├── extract_documents.py
    └── test_extraction.py
```

## Usage

```bash
# 1. Generate the PDF / DOCX / FAQ deliverables from the Markdown sources
python scripts/build_sources.py

# 2. Regenerate the manifest (fingerprints, counts, statistics)
python scripts/manage_corpus.py build

# 3. Check the corpus (front matter, duplicates, PII, FR/EN parity)
python scripts/manage_corpus.py validate

# 4. Extract, clean and export to JSONL
python scripts/extract_documents.py

# Tests for cleaning and extractors
python scripts/test_extraction.py
```

Deliverable generation and corpus management use the standard library only. PDF extraction uses **PyMuPDF** or **pdfplumber** when installed, otherwise **pypdf**; DOCX extraction uses **python-docx** when available, otherwise a built-in OOXML parser. The pipeline therefore runs with no mandatory third-party dependency.

## Design decisions

### 1. NovaShop is fictional, so the documents are written by the team

Importing help pages from Amazon or Etsy would have two consequences: a legal risk (copyrighted content) and a documentary inconsistency (rules that do not match our order data). The 37 documents are therefore **written for the project** and covered by `NovaShop-Proprietary-Synthetic`.

### 2. Both languages are first-class, not an afterthought

Each document exists as a French original and an English translation with the **same `doc_id`, the same section structure and the same figures**. The validator enforces this: it compares section counts, category, version, sensitivity and the set of numeric values between the two variants. This makes cross-lingual retrieval experiments (FR question → EN passage) measurable rather than anecdotal.

`variant` and `translation_of` columns identify the original and its translations.

### 3. External sources are documented but not indexed

The 7 external references (`EXT-01` to `EXT-07`) serve to document a licence, compare wording or provide a benchmark. They carry `index_in_rag = no`: a Moroccan law or a Wikipedia article is not a NovaShop rule, and injecting it into the RAG pipeline would produce out-of-scope answers.

### 4. Licence verification is a field, not a claim

`license_status` distinguishes `verified`, `verified_link_only`, `presumed_public_domain`, `pending_verification` and `internal_verified`. No source is declared verified unless the verification was actually performed.

### 5. Regulatory summaries quote no unverified article

`REG-01` to `REG-04` are internal summaries. They describe principles and obligations **without asserting any article number or exact legal deadline**. The 14-day period is presented as a NovaShop commercial choice, not as the legal minimum. An assistant that invented "article 44" would produce exactly the hallucination the project aims to measure.

### 6. The corpus is designed for chunking

Each document is structured into short `##` sections, and its `chunking_profile` states the expected strategy:

| Profile | Files | Splitting |
| --- | --- | --- |
| `policy_clause` | 20 | 1 section = 1 chunk |
| `qa_pair` | 16 | 1 question + answer = 1 chunk |
| `catalogue_section` | 12 | 1 range or section = 1 chunk |
| `procedure_steps` | 8 | 1 step or block = 1 chunk |
| `legal_clause` | 8 | 1 principle = 1 chunk |
| `sop_section` | 6 | 1 section = 1 chunk |
| `answer_template` | 2 | 1 response template = 1 chunk |
| `reference_table` | 2 | 1 status row = 1 chunk |

### 7. Three input formats, one JSONL output

The brief requires **PDF**, **Word (.docx)** and **FAQ (JSON, JSONL, CSV)** documents. The Markdown in `data/raw/corpus/` remains the authoring source — versionable, diff-friendly, and the only surface checked by the FR/EN parity validator — then `build_sources.py` derives the deliverables and `extract_documents.py` re-ingests them.

| Category | Delivered format | Files |
| --- | --- | ---: |
| Policies (10 × 2 languages) | PDF | 20 |
| Regulatory summaries (4 × 2) | PDF | 8 |
| Procedures (4 × 2) | DOCX | 8 |
| Internal operations (5 × 2) | DOCX | 10 |
| Product guides (6 × 2) | DOCX | 12 |
| FAQ (8 × 2) | JSON (6), JSONL (6), CSV (4) | 16 |

The choice is not cosmetic: it exercises the three readers on genuinely different structures. A PDF has no sections, only pages; a DOCX has headings, paragraphs and tables; an FAQ is already split into pairs. The pipeline preserves that granularity:

- **PDF** → one record per page, with page number;
- **DOCX** → one record per section, headings and tables included;
- **FAQ** → one record per question/answer pair, with identifier and category.

Every record carries `doc_id`, `language`, `title`, `category`, `source_path`, the source file's SHA-256, the extractor used and a timestamp. Cleaning preserves accents, French punctuation and business values (14 days, 39 MAD, 5 %): it only removes non-breaking spaces, invisible characters, control characters and superfluous blank lines.

Three checks are published in `docs/reports/extraction_report.md`: extracted/source word coverage (0.92 to 0.97, no truncation), accent preservation (260/261 French records), and OCR detection (0 pages flagged). The OCR alert threshold is 40 extractable characters per page.


## Content consistency

Business facts are identical across all documents and both languages:

- Returns: 14 calendar days, 39 MAD fee unless faulty
- Refunds: 7 to 15 business days, store credit increased by 5 %
- Delivery: areas A/B/C, free from 500 MAD, cash on delivery +25 MAD
- Warranty: 12 months (6 months accessories, 3 months cables)
- Support: Monday–Saturday, 9:00–19:00, three stores

This consistency is what makes RAG faithfulness measurable: if two documents contradict each other, the system must flag it, not pick one at random.

## Pending items

- [ ] Production of the annotated datasets (`intent_dataset`, `retrieval_eval`, `rag_eval`, `ner_dataset`, `sentiment_dataset`, `urgency_dataset`)
- [ ] Cohen's kappa calculation after double annotation
- [ ] Full product catalogue (100–200 references) — the `CAT-*` guides cover only 25
- [ ] Addition of the "fictional document" notice to all deliverables

## Disclaimer

NovaShop, its addresses, phone numbers, ICE/RC identifiers and products are **entirely fictional**. They do not refer to any real company and must not be presented as authentic.
