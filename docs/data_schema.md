# Data schema — Data Engineering (Task 1)

> Generated from the actual files in this repository. Every path below is relative to the repository root.

## 1. Layout

| Path | Content |
| --- | --- |
| `data/raw/corpus/fr/`, `data/raw/corpus/en/` | 37 Markdown documents per language, YAML front matter |
| `data/processed/documents/{pdf,docx,faq}/{fr,en}/` | 74 generated deliverables (28 PDF, 30 DOCX, 16 FAQ) |
| `data/processed/documents/manifest_documents.csv` | Traceability of the 74 deliverables |
| `data/processed/extracted/documents.jsonl` | 522 extracted, cleaned records |
| `data/annotations/intents.csv` | Bilingual intent taxonomy (13 intents + `out_of_scope`) |
| `data/source_manifest.csv` | Master manifest: 74 documents + 7 external references |
| `docs/reports/` | Generated quality reports and annotation logs |
| `scripts/` | Build, validate, extract and test pipeline |

## 2. Corpus Markdown

### 2.1 Naming

`{DOC_ID}_{slug}.md`, for example `POL-01_politique-retours.md` (FR) and
`POL-01_returns-exchanges.md` (EN). The `doc_id` is identical in both languages;
only the slug differs.

### 2.2 YAML front matter

Required for every file (validated):

| Field | Type | Example | Rule |
| --- | --- | --- | --- |
| `doc_id` | string | `POL-01` | Unique per language; must match the filename prefix |
| `title` | string | `Politique de retours` | Non-empty |
| `category` | enum | `policies` | `policies`, `faq`, `procedures`, `internal_operations`, `product_guides`, `legal_summaries` |
| `doc_type` | string | `policy` | Lowercase, stable across languages |
| `language` | enum | `fr` | Must match the parent folder |
| `version` | string | `1.0` | Same in both languages |
| `effective_date` | date | `2026-09-01` | ISO `YYYY-MM-DD`, same in both languages |
| `owner` | string | `NovaShop` | Same in both languages |
| `sensitivity` | enum | `public` | Same in both languages |
| `source_type` | enum | `synthetic` | `synthetic` for all NovaShop documents |

Optional: `review_status` (used by the four `REG-*` summaries).

### 2.3 Body

Short `##` sections, one topic per section. The section count must be identical
in FR and EN. Tables are allowed and are extracted as text by the DOCX reader.

## 3. `data/source_manifest.csv`

- Encoding: UTF-8 with BOM, comma separated.
- 81 rows = 74 `knowledge_base_document` + 7 `external_reference`.
- Primary key: **(`doc_id`, `language`)**.

35 columns:

```
doc_id, record_type, title, category, doc_type, language, variant,
translation_of, version, effective_date, owner, author, source_type,
source_origin, source_url, license, license_url, license_status,
verified_by, verified_on, reuse_permission, attribution_required,
attribution_text, contains_pii, sensitivity, index_in_rag,
chunking_profile, review_status, word_count, est_tokens, sha256,
relative_path, document_format, document_path, notes
```

Key fields:

| Field | Meaning |
| --- | --- |
| `record_type` | `knowledge_base_document` or `external_reference` |
| `variant` | `original` (FR) or `translation` (EN) |
| `translation_of` | `doc_id` of the French original, empty for originals |
| `license_status` | `verified`, `verified_link_only`, `presumed_public_domain`, `pending_verification`, `internal_verified` |
| `license` | `NovaShop-Proprietary-Synthetic` for internal documents |
| `index_in_rag` | `yes` for the 74 corpus documents, `no` for the 7 external references |
| `review_status` | `approved` for the 74 documents, `verified` for the external references |
| `chunking_profile` | Chunking strategy expected at indexing time |
| `sha256` | SHA-256 of the source Markdown file |
| `relative_path` | Corpus path (`data/raw/corpus/{fr,en}/...`) |
| `document_format` | `pdf`, `docx`, `json`, `jsonl`, `csv` |
| `document_path` | Generated deliverable path |

## 4. `data/processed/documents/manifest_documents.csv`

One row per generated deliverable (74 rows).

```
doc_id, language, format, relative_path, source_path, title,
category, units, source_words, size_bytes, sha256
```

`units` is the number of extraction units the deliverable will produce
(pages for PDF, sections for DOCX, Q/A pairs for FAQ).

## 5. `data/processed/extracted/documents.jsonl`

One JSON object per line, one line per extraction unit: 522 records
(56 PDF pages, 274 DOCX sections, 192 FAQ pairs).

| Field | Type | Meaning |
| --- | --- | --- |
| `doc_id` | string | Document identifier |
| `language` | `fr` / `en` | Language of the record |
| `format` | `pdf` / `docx` / `json` / `jsonl` / `csv` | Source format |
| `category` | string | Corpus category |
| `title` | string | Document title |
| `source_path` | string | Path of the extracted file |
| `source_sha256` | string | SHA-256 of the source file |
| `extracted_at` | ISO 8601 | Extraction timestamp (UTC) |
| `record_id` | string | `{doc_id}:{language}:{format}:{unit_id}` |
| `unit_type` | `page` / `section` / `qa` | Granularity |
| `unit_id` | string | `p1`, `s3`, `q7`… |
| `page` | integer or null | PDF page number |
| `section` | string or null | DOCX section heading |
| `text` | string | Cleaned text |
| `needs_ocr` | boolean | True when a PDF page has fewer than 40 extractable characters |
| `warnings` | list | Non-blocking extraction warnings |
| `extractor` | string | `pypdf`, `ooxml-stdlib`, `faq-json`, `faq-jsonl`, `faq-csv` |
| `char_count` | integer | Characters in `text` |
| `word_count` | integer | Words in `text` |

## 5.1 `data/processed/cleaned_corpus.jsonl`

Cleaned, normalized and deduplicated version of `documents.jsonl`: **522
records**, same order, same identity fields, **no timestamp**. Produced by
`scripts/clean_corpus.py`; two runs produce byte-identical files.

| Field | Type | Example | Values / notes |
| --- | --- | --- | --- |
| `record_id` | string | `POL-01:en:pdf:p1` | `{doc_id}:{language}:{format}:{unit_id}`, unique |
| `doc_id` | string | `POL-01` | Document identifier |
| `language` | `fr` / `en` | `en` | 261 records per language |
| `format` | `pdf` / `docx` / `json` / `jsonl` / `csv` | `pdf` | Source format |
| `category` | string | `policies` | Corpus category |
| `title` | string | `Returns and exchanges policy` | Document title |
| `source_path` | string | `data/processed/documents/pdf/en/POL-01_returns-exchanges.pdf` | Extracted source file |
| `source_sha256` | string | `52a8d826…` | SHA-256 of the source file (64 hex characters) |
| `unit_type` | `page` / `section` / `qa_pair` | `page` | Extraction granularity |
| `unit_id` | string | `p1`, `s3`, `FAQ-01-Q01` | Unit identifier inside the document |
| `page` | integer or null | `1` | PDF page number, `null` otherwise |
| `section` | string or null | `2. Return window` | DOCX section heading, `null` for PDF and FAQ |
| `text` | string | `Returns and exchanges policy\nScope: …` | Normalized text, without repeated headers |
| `char_count` | integer | `4700` | Characters in `text` |
| `word_count` | integer | `743` | Words in `text` |
| `cleaning` | object | see below | Applied steps and traceability |

The `cleaning` object records what happened to the record:

| Field | Type | Example | Values / notes |
| --- | --- | --- | --- |
| `steps` | list of strings | `["normalisation", "entetes", "reflow_pdf"]` | Applied steps, in order: `normalisation`, `entetes`, `reflow_pdf`, `quasi_doublon`, `titre_seul` |
| `removed` | list of strings | `["Référence POL-01 · version 1.0 · …", "Document fictif — …"]` | Exact removed segments, in order (empty when nothing was removed) |
| `reflowed` | boolean | `true` | `true` when PDF hard line breaks were joined |
| `heading_only` | boolean | `false` | `true` for a `section` of at most 8 words without final punctuation; kept as-is |
| `near_duplicate_of` | string or null | `null` | `record_id` of the earlier near-duplicate (word-trigram Jaccard ≥ 0.90, same language); near-duplicates are never removed |

## 5.2 `data/processed/chunked_corpus.jsonl`

Chunks ready for retrieval/RAG, produced from the raw Markdown corpus by
`scripts/chunk_corpus.py`: **678 records** (339 FR + 339 EN), no timestamp,
byte-identical across two runs. The unique key is **`(chunk_id, language)`**.
One `##` section produces one chunk; a section over 300 words is split by
paragraphs into `.1`, `.2`, … parts. The current corpus has no such split
(maximum section: 221 words).

| Field | Type | Example | Values / notes |
| --- | --- | --- | --- |
| `chunk_id` | string | `POL-01#c2` | `<DOC_ID>#c<n>`, where `n` is the section order; `.1`, `.2` suffix only when split |
| `doc_id` | string | `POL-01` | Document identifier, identical in FR and EN |
| `language` | `fr` / `en` | `en` | 339 chunks per language |
| `chunk_index` | integer | `2` | Sequential chunk order inside the document and language |
| `part` | integer or null | `null` | `null` when the section is not split; `1..N` otherwise |
| `doc_title` | string | `Returns and exchanges policy` | Title from the YAML front matter |
| `category` | string | `policies` | Corpus category |
| `doc_type` | string | `policy` | Document type from the front matter |
| `chunking_profile` | string | `policy_clause` | Profile from `data/source_manifest.csv` |
| `section_heading` | string | `2. Return window` | Full `##` heading, including its number when present |
| `section_number` | string or null | `2` | Leading section number; `null` for FAQ questions |
| `text` | string | `The customer has **14 calendar days** …` | Section body without the `#` title, the fictif block or the `##` heading; the preamble, when present, is kept in the first section |
| `text_for_embedding` | string | `Returns and exchanges policy — 2. Return window\nThe customer has …` | Exactly `<doc_title> — <section_heading>\n<text>` |
| `word_count` | integer | `69` | Whitespace-separated words in `text` (heading excluded) |
| `est_tokens` | integer | `93` | `round(word_count × 1.35)` |
| `has_table` | boolean | `false` | `true` when the chunk contains a Markdown table; tables are never split |
| `cross_refs` | list of strings | `["POL-04"]` | Cited `POL`/`REG`/`PRO`/`OPS`/`CAT`/`FAQ-NN` references, sorted and deduplicated |
| `amounts_mad` | list of strings | `["39"]` | Amounts before `MAD`, spaces removed, sorted numerically and deduplicated |
| `version` | string | `1.0` | Front matter version |
| `effective_date` | string | `2026-09-01` | Front matter effective date |
| `sensitivity` | `public` / `internal` | `public` | Front matter sensitivity |
| `audience` | `customer` / `internal` | `customer` | `customer` when `sensitivity` is `public`, otherwise `internal` |
| `index_in_rag` | boolean | `true` | Manifest policy; set to `false` for `too_short` chunks |
| `exclusion_reason` | string or null | `null` | `null`, or `too_short` when the chunk is excluded from indexing |
| `license` | string | `NovaShop-Proprietary-Synthetic` | Licence from the manifest |
| `source_path` | string | `data/raw/corpus/en/POL-01_returns-exchanges.md` | Raw Markdown source |
| `source_sha256` | string | `e3b0c442…` | SHA-256 of the raw Markdown file (64 hex characters) |

The `too_short` decision is applied to the FR/EN pair of the same `chunk_id`:
both variants are excluded together when their heading plus text is under 15
words. This yields exactly **6 lines** (3 IDs × 2 languages):
`POL-01#c9`, `REG-02#c8` and `REG-03#c9`. All other chunks keep
`index_in_rag: true` and `exclusion_reason: null`.

## 6. FAQ formats

The same 8 FAQ documents are delivered in three shapes.

**JSON** (FAQ-01 to FAQ-03) — one object per document:

```json
{
  "doc_id": "FAQ-01",
  "title": "FAQ — Commandes et suivi",
  "language": "fr",
  "category": "faq",
  "version": "1.0",
  "questions": [
    {"id": "FAQ-01-Q01", "question": "...", "answer": "..."}
  ]
}
```

**JSONL** (FAQ-04 to FAQ-06) — one object per Q/A pair:

```json
{"doc_id": "FAQ-04", "title": "...", "language": "fr", "category": "faq",
 "version": "1.0", "id": "FAQ-04-Q01", "question": "...", "answer": "..."}
```

**CSV** (FAQ-07, FAQ-08) — header:

```
doc_id,language,id,title,category,version,question,answer
```

## 7. Invariants enforced by `scripts/manage_corpus.py validate`

- Front matter present and complete; `doc_id` matches the filename.
- `language` matches the parent folder.
- At least 120 words per document; at least 5 questions per FAQ.
- No `lorem ipsum`, no `TODO`, no IBAN or card number.
- No near-duplicate document pair (Jaccard > 0.30).
- FR/EN parity: same category, `doc_type`, version, `effective_date`,
  sensitivity, section count and numeric values; length ratio between 0.60 and 1.25.
- SHA-256 declared in the manifest matches the current file.

## 8. Reproduce

```bash
python scripts/build_sources.py        # Markdown -> PDF / DOCX / FAQ
python scripts/manage_corpus.py build  # manifest + statistics
python scripts/manage_corpus.py validate
python scripts/extract_documents.py    # PDF / DOCX / FAQ -> JSONL
python scripts/test_extraction.py      # 14 unit tests
```

The extraction step preserves accents and French punctuation, and flags PDF
pages that would need OCR instead of silently returning empty text.
