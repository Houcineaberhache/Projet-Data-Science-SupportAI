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

## 9. `intent_candidates` / feuilles d'annotation

### 9.1 `data/annotations/_private/intent_candidates.jsonl`

Source privée des questions d'intention, **ignorée par Git** via
`data/annotations/_private/`. Elle contient **560 lignes** : 14 intentions ×
40 questions, avec 24 FR + 16 EN par intention. Les annotateurs ne doivent
pas ouvrir ce fichier.

| Field | Type | Example | Values / notes |
| --- | --- | --- | --- |
| `id` | string | `INT-0101` | `INT-` + 4 chiffres, unique ; les ids `INT-0001` à `INT-0020` du pilote ne sont pas réutilisés |
| `text` | string | `ma commande est où ?` | Message brut, 4 à 40 mots, sans darija/arabe/arabizi |
| `language` | `fr` / `en` | `fr` | Langue du message |
| `target_intent` | string | `order_tracking` | Un des 14 codes de `data/annotations/intents.csv` |
| `case_type` | string | `boundary` | `typical`, `boundary`, `typo`, `short` ou `long` |
| `source` | string | `synthetic` | Toujours `synthetic` pour ce lot |

Le contrôle `python scripts/prepare_intent_annotation.py validate` vérifie les
volumes, la longueur, la langue, les doublons exacts et quasi-doublons
(Jaccard sur trigrammes ≥ 0,8), l'absence de 6 mots consécutifs repris des
exemples/guidelines, l'absence de copie du pilote, l'équilibre des classes,
les 6 cas `boundary` par intention et la part de `typo` (15 % ±5 points).

### 9.2 `data/annotations/_private/intent_split.csv`

Découpage déterministe (`SEED = 42`) stratifié par intention et par langue :
FR 24 → 17 train / 4 val / 3 test ; EN 16 → 11 train / 2 val / 3 test.
Total : **392 train / 84 val / 84 test**. Le fichier contient deux colonnes :

| Field | Type | Example | Values / notes |
| --- | --- | --- | --- |
| `id` | string | `INT-0101` | Référence vers `intent_candidates.jsonl` |
| `split` | string | `train` | `train`, `val` ou `test` |

Aucun quasi-doublon (Jaccard ≥ 0,8) n'est séparé entre deux splits.

### 9.3 `data/annotations/blind/*.csv`

Feuilles d'annotation **aveugles** : elles ne contiennent ni `target_intent`,
ni `case_type`, ni `split`, et les colonnes d'annotation sont vides.

| File | Rows (hors en-tête) | Content |
| --- | --- | --- |
| `annotate_aya.csv` | 168 | Tous les exemples val + test, ordre mélangé avec `SEED = 42` |
| `annotate_mohammed.csv` | 168 | Mêmes ids, ordre mélangé avec `SEED = 43` |
| `spotcheck_train_aya.csv` | 56 | 4 exemples train par intention (2 FR + 2 EN), tirage déterministe |

Colonnes communes : `id,language,text,intent,ambiguous,acceptable_labels,notes`.
Les quatre dernières colonnes sont vides ; `intent` doit être rempli avec un
des 14 codes, et `ambiguous=true` doit être accompagné d'au moins un code dans
`acceptable_labels`. Le fichier `README_annotation.md` rappelle les consignes
et ne révèle aucune étiquette cible.

Les feuilles rendues par les annotateurs sont cherchées dans `blind/` sous les
noms canoniques `annotate_aya_done.csv`, `annotate_mohammed_done.csv` et
`spotcheck_train_aya_done.csv`. À défaut, le script de fusion accepte les
exports Google Sheets `annotate_aya - annotate_aya.csv.csv`,
`annotate_mohammed - annotate_mohammed.csv.csv` et
`spotcheck_train_aya - spotcheck_train_aya.csv.csv`.

## 10. Fusion des annotations et `intent_dataset`

La fusion est produite par `scripts/merge_annotations.py`. Le script ne choisit
jamais une étiquette. Il propose deux modes :

- **deux annotateurs** : Aya et Mohammed ; les désaccords sont écrits dans une
  file d'arbitrage humaine, et `--build` refuse de produire le dataset tant que
  cette file n'est pas complète ;
- **annotateur unique (`--single-annotator`)** : Aya et le sondage train
  seulement, sans kappa et sans file d'arbitrage ; voir §10.6.

### 10.1 `docs/reports/adjudication_log.csv`

Une ligne par désaccord entre Aya et Mohammed sur les exemples val + test.

| Colonne | Type | Valeur |
| --- | --- | --- |
| `id` | string | `INT-XXXX`, référence à `intent_candidates.jsonl` |
| `text` | string | Texte de l'exemple |
| `intent_aya` | string | Étiquette choisie par Aya |
| `intent_mohammed` | string | Étiquette choisie par Mohammed |
| `adjudicated_intent` | string | Vide tant que l'arbitrage humain n'a pas tranché ; sinon un des 14 codes |
| `arbiter` | string | Vide tant que l'arbitrage n'a pas été rendu |
| `date` | date | Vide tant que l'arbitrage n'a pas été rendu |
| `justification` | string | Vide tant que l'arbitrage n'a pas été rendu |

Lors du premier passage, le script sauvegarde l'ancien journal dans
`docs/reports/adjudication_log.previous.csv` avant de le remplacer. Si le
journal courant est vide mais que la version de `HEAD` contient encore des
lignes, cette version est sauvegardée. Les passages suivants conservent cette
sauvegarde existante.

### 10.2 `data/annotations/intent_dataset.jsonl`

Une ligne par exemple, au format §5.5 des guidelines. Le fichier n'est écrit
que par `python scripts/merge_annotations.py --build`.

| Champ | Type | Valeur |
| --- | --- | --- |
| `id` | string | `INT-XXXX` |
| `text` | string | Texte brut |
| `language` | `fr` / `en` | Langue de l'exemple |
| `intent` | string | Deux annotateurs : accord Aya/Mohammed, adjudication, ou cible train. Annotateur unique : étiquette d'Aya pour val/test, cible train sauf contradiction du sondage |
| `acceptable_labels` | list | Labels acceptables si ambiguïté, sinon `[]` |
| `ambiguous` | boolean | `true` si l'annotateur a marqué l'exemple ambigu |
| `source` | string | Toujours `synthetic` |
| `split` | `train` / `val` / `test` | Depuis `intent_split.csv` |
| `annotator_1` | string | `aya` |
| `annotator_2` | string / null | `mohammed` pour val/test en mode deux annotateurs ; `null` en mode annotateur unique et pour train |
| `adjudicated` | boolean | `true` pour un désaccord val/test arbitré en mode deux annotateurs ; `false` en mode annotateur unique |
| `notes` | string | Contradiction du sondage train, désaccord arbitré, ou note d'Aya |
| `created_at` | date | Date du jour au moment du build |
| `annotation_status` | string / absent | `single_annotator` sur les lignes val/test en mode annotateur unique ; absent sinon |

Règle train : `intent` = `target_intent` du fichier privé, sauf si le sondage
Aya contredit cette cible ; dans ce cas l'étiquette d'Aya est conservée et la
contradiction est signalée dans le rapport et dans `notes`.

### 10.3 `data/annotations/intent_dataset.csv`

Export léger : `id,text,language,intent,split`.

### 10.4 `docs/reports/intent_dataset_report.md`

Rapport sans horodatage : tailles par split/langue/intention, contrôles qualité
§12.4 (OK/KO), limites et commandes de reproduction. En mode deux annotateurs,
il ajoute l'accord observé, le kappa (val, test, ensemble), le kappa par
intention, la matrice de confusion, les paires les plus confondues, la file
d'arbitrage et le sondage train vs cible. En mode annotateur unique, il remplace
ces éléments par la mention « annotateur unique (Aya) ; accord inter-annotateurs
non mesuré », une liste de cohérence avec les cibles et le statut
`NON APPLICABLE` pour le kappa.

### 10.5 État courant

Le mode deux annotateurs reste disponible mais bloqué : le fichier de Mohammed
est invalide (colonne `intent` copiée sans réalignement) et n'est pas utilisé.
L'ancien passage avait mesuré **148 désaccords** et un kappa global de
**0,043** avant la relecture des étiquettes d'Aya ; ces chiffres ne décrivent
plus l'état courant.

Le dataset courant est produit en **mode annotateur unique**. Aya a annoté les
168 exemples val/test et le sondage de 56 exemples train. `--build
--single-annotator` a écrit **560 lignes** : 392 train, 84 val, 84 test. Les 168
lignes val/test portent `annotation_status = "single_annotator"`,
`annotator_2 = null` et `adjudicated = false`. Deux cas de carte cadeau
(`INT-0321`, `INT-0325`) restent ambigus avec `promotion_loyalty` et
`acceptable_labels = ["payment_info", "promotion_loyalty"]`. Aucun kappa n'est
calculé et aucune file d'arbitrage n'est produite. Le jeu de test n'est pas gelé.

Commandes :

```bash
python scripts/merge_annotations.py --single-annotator
python scripts/merge_annotations.py --build --single-annotator
python scripts/merge_annotations.py          # mode deux annotateurs
python scripts/merge_annotations.py --build  # mode deux annotateurs, après arbitrage
python tests/test_merge_annotations.py
```

### 10.6 Mode annotateur unique (`--single-annotator`)

Entrées canoniques : `annotate_aya_done.csv` pour val/test et
`spotcheck_train_aya_done.csv` pour le train. Le fichier de Mohammed n'est ni lu
ni ouvert. La feuille vide `annotate_mohammed.csv` reste disponible pour le
second annotateur ; son retour attendu est `annotate_mohammed_done.csv`.

- **Validation** : mêmes contrôles que le mode deux annotateurs (ids attendus,
  14 codes, aucune ligne vide, `ambiguous=true` implique
  `acceptable_labels` non vide, textes et langues conformes au fichier privé).
- **Aucun kappa** : aucune valeur n'est écrite. Le contrôle global vaut
  `non mesuré (annotateur unique)` et son statut est `NON APPLICABLE`.
- **Aucune file d'arbitrage** : le script ne lit ni n'écrit
  `adjudication_log.csv` dans ce mode.
- **Contrôle de cohérence** : comparaison des étiquettes d'Aya aux
  `target_intent` pour val, test et le sondage train. Chaque différence est
  listée dans le rapport avec `id`, texte, étiquette d'Aya et cible. Le script
  ne corrige aucune étiquette automatiquement ; les corrections de relecture
  sont appliquées dans les fichiers d'annotation. C'est une liste de relecture
  pour Aya.
- **Build** : `intent_dataset.jsonl` et `.csv` contiennent 560 lignes. Pour
  val/test, `intent` est l'étiquette d'Aya, `annotator_1 = "aya"`,
  `annotator_2 = null`, `adjudicated = false` et
  `annotation_status = "single_annotator"`. Pour train, `intent` est
  `target_intent`, sauf contradiction du sondage où l'étiquette d'Aya est
  conservée et signalée dans `notes`.
- **Limites** : pas de kappa, risque de biais de l'annotateur unique, jeu de
  test non double-annoté, jeu de test non gelé.

Après la relecture, le contrôle de cohérence liste **2 différences** :
**0/168** en val/test et **2/56** dans le sondage train. Les deux lignes
concernent des cartes cadeaux (`INT-0321`, `INT-0325`) : l'étiquette
`promotion_loyalty` est conservée, la cible `payment_info` est jugée discutable,
et les lignes sont marquées ambigues avec
`acceptable_labels = ["payment_info", "promotion_loyalty"]`. Ces différences ne
sont pas des désaccords inter-annotateurs et ne sont pas arbitrées
automatiquement.

## 11. Jeu d'évaluation RAG et jeu de robustesse

Ces deux jeux sont validés par `scripts/build_rag_eval.py` (bibliothèque
standard uniquement), qui construit aussi les passages et les rapports. Ils ne
modifient ni le corpus ni les règles métier.

### 11.1 `data/annotations/rag_eval.jsonl`

140 questions, une par ligne, UTF-8/LF. Les questions ne portent que sur les
chunks `audience = customer` et `index_in_rag = true` des documents autorisés
(`FAQ-01..08`, `POL-01..10`, `PRO-01..04`, `CAT-01..06`, `OPS-04`, `REG-04`).

| Champ | Type | Valeur |
| --- | --- | --- |
| `id` | string | `RET-0001` à `RET-0140` |
| `question` | string | Question client, 4 à 40 mots |
| `language` | `fr` / `en` | Langue de la question et des chunks gold |
| `intent` | string | Un des 14 codes de `data/annotations/intents.csv` |
| `answerable` | boolean | `false` uniquement pour `out_of_corpus` |
| `gold_doc_ids` | list | Documents des chunks gold, sans doublon |
| `gold_chunk_ids` | list | Chunks gold, ordre de pertinence décroissante |
| `gold_relevance` | object | `{chunk_id: 2}` suffisant, `{chunk_id: 1}` partiel |
| `gold_answer` | string / null | Réponse de référence, 1 à 3 phrases ; `null` si hors corpus |
| `question_type` | enum | `lexical`, `semantic`, `procedural`, `out_of_corpus` |
| `expected_behavior` | string | `answer_with_citation` ou `abstain_and_offer_human` |
| `source` | string | Toujours `synthetic` |
| `reviewed_by` | null / string | Reste `null` jusqu'à la relecture humaine par Aya |
| `notes` | string | Justification, contrôle grep ou note de conception |

Répartition : **42 lexical, 56 semantic, 28 procedural, 14 out_of_corpus** ;
**84 FR + 56 EN**. Chaque document client a au moins 2 questions et aucun n'en
a plus de 12. Le jeu contient **17 questions multi-chunks** (relevance 2 + 1),
**88 questions chiffrées** et **21 questions avec une faute légère volontaire**
(environ 15 %, conformément au style §4). Une question `semantic` ne reprend aucun mot de
5 lettres ou plus du titre de sa section ; une question ne copie jamais un
titre (Jaccard < 0,6).

Les 14 questions `out_of_corpus` ont `answerable = false`,
`gold_chunk_ids = []`, `gold_answer = null` et
`expected_behavior = "abstain_and_offer_human"`. Leurs termes clés ont été
cherchés dans tout le corpus avant écriture ; les notes documentent le
résultat, y compris les cas où le terme existe dans un autre sens (par exemple
« par téléphone » pour le contact du transporteur, ou « écran cassé » pour
l'exclusion de garantie sans tarif de réparation).

### 11.2 `data/annotations/robustness_eval.jsonl`

35 cas, une par ligne. Ce jeu est séparé des 140 questions RAG.

| Champ | Type | Valeur |
| --- | --- | --- |
| `id` | string | `ROB-001` à `ROB-035` |
| `question` | string | Question ou message client |
| `language` | `fr` / `en` | Langue du message |
| `category` | enum | `explicit_answer`, `no_answer`, `ambiguous`, `rephrasing`, `human_handoff` |
| `expected_behavior` | string | Comportement attendu, rédigé avant le test |
| `gold_chunk_ids` | list | Chunks gold pour `explicit_answer` / `rephrasing`, sinon `[]` |
| `notes` | string | Justification du cas |

Répartition : **10 explicit_answer, 8 no_answer, 6 ambiguous, 6 rephrasing,
5 human_handoff**. Les catégories `contradictory` et `prompt_injection` sont
hors périmètre de cette tâche. Aucun document piégé ou contradictoire n'a été
ajouté au corpus.

### 11.3 `data/annotations/rag_eval_with_passages.jsonl`

Même contenu que `rag_eval.jsonl`, plus un champ `gold_passages`. Chaque
passage est **copié par le script** depuis `data/processed/chunked_corpus.jsonl` :
`{chunk_id, doc_id, section_heading, text}`. Le script ne retape jamais un
passage. Ce fichier est destiné à Fatima pour l'indexation et l'évaluation du
retrieval.

### 11.4 Rapports

- `docs/reports/rag_eval_report.md` : répartitions, couverture par document,
  résultats des sept contrôles, questions hors corpus et trois chunks les plus
  proches. Aucun horodatage.
- `docs/reports/rag_eval_review.md` : fiche de relecture humaine. 25 questions
  tirées avec `SEED = 42` et les 14 questions hors corpus, avec la réponse de
  référence et le texte des chunks gold. Aya y coche les contrôles et renseigne
  ensuite `reviewed_by`.

### 11.5 Contrôles exécutés par `validate`

1. 140 lignes, ids uniques, répartitions par type, langue et document, champs
   et valeurs valides.
2. Chaque `gold_chunk_id` existe pour la langue de la question, est
   `customer`, `index_in_rag` et appartient à un document autorisé ;
   `gold_doc_ids` est cohérent.
3. `answerable = false` implique des chunks vides et `gold_answer = null` ;
   `answerable = true` implique au moins un chunk à relevance 2.
4. Chaque nombre de `gold_answer` figure dans les chunks gold, après
   normalisation des espaces, espaces insécables et virgules de milliers.
5. Jaccard question / titre de section < 0,6 ; une question `semantic` ne
   contient aucun mot de 5 lettres ou plus du titre.
6. Aucun doublon exact ni quasi-doublon (Jaccard ≥ 0,8), y compris contre
   `robustness_eval.jsonl` et `_private/intent_candidates.jsonl`.
7. Pour chaque question hors corpus, affichage des trois chunks les plus
   proches par recouvrement de mots, pour contrôle humain.

### 11.6 Commandes et état courant

```bash
python scripts/build_rag_eval.py validate   # sept contrôles OK/KO
python scripts/build_rag_eval.py build      # passages, rapport, fiche de relecture
python tests/test_rag_eval.py
```

Au dernier passage, les sept contrôles sont **OK**. `reviewed_by` reste `null`
pour les 140 lignes : la relecture humaine par Aya n'est pas encore faite. Le
jeu de robustesse ne contient pas encore de résultats de modèle : il définit
les comportements attendus avant tout test.
