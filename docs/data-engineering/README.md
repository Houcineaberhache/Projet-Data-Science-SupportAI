# SupportAI — Corpus documentaire & guidelines d'annotation

Livrables de la **tâche 1 — Étudiant 1 (Data Engineer & Dataset Manager)**.

> Collecter 30 à 50 documents de support, vérifier les licences, définir les guidelines d'annotation.

🇬🇧 English version: [`README.en.md`](README.en.md)

## Livrables

| Fichier | Contenu |
| --- | --- |
| `data/source_manifest.csv` | Manifeste de 81 lignes : 74 fichiers de langue (37 documents × 2 langues) + 7 références externes, avec licence, statut de vérification, usage autorisé et SHA-256 |
| `docs/annotation_guidelines.md` / `.en.md` | Guide d'annotation complet : taxonomie, règles de décision, barèmes retrieval et RAG, contrôle qualité |
| `docs/data_schema.md` | Schéma de données : front matter, colonnes du manifeste, enregistrements JSONL, formats FAQ |
| `data/raw/corpus/fr/`, `data/raw/corpus/en/` | Les 37 documents de la base de connaissances NovaShop, dans les deux langues (Markdown, front matter YAML) — source de rédaction |
| `data/processed/documents/` | Les mêmes documents livrés en **PDF**, **Word (.docx)** et **FAQ (JSON, JSONL, CSV)** |
| `data/processed/extracted/documents.jsonl` | Sortie du pipeline d'ingestion : texte extrait, nettoyé, avec métadonnées |
| `data/processed/cleaned_corpus.jsonl` | Corpus nettoyé, normalisé et dédupliqué (522 enregistrements, sans en-têtes répétés) |
| `data/processed/chunked_corpus.jsonl` | Corpus découpé en chunks prêts pour le retrieval/RAG (678 chunks, clé `(chunk_id, language)`) — généré par `python scripts/chunk_corpus.py` |
| `data/annotations/intents.csv` | Taxonomie bilingue machine-lisible : 13 intentions + `out_of_scope` |
| `docs/reports/corpus_stats.md` | Statistiques du corpus (générées) |
| `docs/reports/extraction_report.md` | Rapport d'extraction : couverture, OCR, contrôles d'accents (généré) |
| `scripts/manage_corpus.py` | Générateur de manifeste + validateur qualité, avec contrôle de parité FR/EN |
| `scripts/build_sources.py` | Génère les livrables PDF / DOCX / FAQ depuis le Markdown |
| `scripts/extract_documents.py` | Pipeline PDF / DOCX / FAQ → nettoyage → JSONL |

## Chiffres clés

- **37 documents** par langue, **74 fichiers**, **35 918 mots** (~48 490 tokens)
- **74 livrables** dans les formats demandés : 28 PDF, 30 DOCX, 16 FAQ (JSON/JSONL/CSV)
- **522 enregistrements** extraits et nettoyés dans `data/processed/extracted/documents.jsonl`
- 10 politiques · 8 FAQ · 6 guides produits · 4 procédures · 5 documents internes · 4 synthèses réglementaires
- 7 références externes **non indexées**, documentées pour leurs licences
- 0 erreur de validation, 0 doublon exact, parité FR/EN vérifiée

## Arborescence

```
.
├── data/
│   ├── raw/corpus/{fr,en}/          # 74 documents Markdown (37 × 2 langues)
│   ├── processed/documents/         # 74 livrables PDF / DOCX / FAQ
│   │   ├── pdf/{fr,en}/             # 28 PDF (politiques, synthèses)
│   │   ├── docx/{fr,en}/            # 30 DOCX (procédures, internes, guides)
│   │   ├── faq/{fr,en}/             # 16 FAQ (6 JSON, 6 JSONL, 4 CSV)
│   │   └── manifest_documents.csv
│   ├── processed/extracted/
│   │   └── documents.jsonl          # 522 enregistrements extraits
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

## Utilisation

```bash
# 1. Générer les livrables PDF / DOCX / FAQ depuis les sources Markdown
python scripts/build_sources.py

# 2. Régénérer le manifeste (empreintes, comptages, statistiques)
python scripts/manage_corpus.py build

# 3. Contrôler le corpus (front matter, doublons, PII, parité FR/EN)
python scripts/manage_corpus.py validate

# 4. Extraire, nettoyer et exporter en JSONL
python scripts/extract_documents.py

# 5. Nettoyer, normaliser et dédupliquer le corpus
python scripts/clean_corpus.py

# Tests du nettoyage et des extracteurs
python scripts/test_extraction.py
```

La génération des livrables et la gestion du corpus n'utilisent que la bibliothèque standard. L'extraction PDF utilise **PyMuPDF** ou **pdfplumber** s'ils sont installés, sinon **pypdf** ; l'extraction DOCX utilise **python-docx** si disponible, sinon un analyseur OOXML intégré. Le pipeline reste donc exécutable sans dépendance obligatoire.

## Choix de conception

### 1. NovaShop est fictif, donc les documents sont rédigés par l'équipe

Importer des pages d'aide d'Amazon ou d'Etsy aurait deux conséquences : un risque juridique (contenus sous copyright) et une incohérence documentaire (des règles qui ne correspondent pas à nos données de commandes). Les 37 documents sont donc **rédigés pour le projet** et couverts par `NovaShop-Proprietary-Synthetic`.

### 2. Les deux langues sont traitées à égalité, pas comme un ajout

Chaque document existe en original français et en traduction anglaise avec le **même `doc_id`, la même structure de sections et les mêmes chiffres**. Le validateur l'impose : il compare le nombre de sections, la catégorie, la version, la sensibilité et l'ensemble des valeurs numériques entre les deux variantes. Cela rend les expériences de retrieval cross-lingue (question FR → passage EN) mesurables plutôt qu'anecdotiques.

Les colonnes `variant` et `translation_of` identifient l'original et ses traductions.

### 3. Les sources externes existent, mais ne sont pas indexées

Les 7 références externes (`EXT-01` à `EXT-07`) servent à documenter une licence, comparer une formulation ou fournir un benchmark. Elles portent `index_in_rag = no` : une loi marocaine ou un article Wikipédia n'est pas une règle NovaShop, et l'injecter dans le RAG produirait des réponses hors périmètre.

### 4. La vérification de licence est un champ, pas une affirmation

`license_status` distingue `verified`, `verified_link_only`, `presumed_public_domain`, `pending_verification` et `internal_verified`. Aucune source n'est déclarée vérifiée sans que la vérification ait été faite.

### 5. Les synthèses réglementaires ne citent aucun article non vérifié

`REG-01` à `REG-04` sont des synthèses internes. Elles décrivent des principes et des obligations, **sans affirmer de numéro d'article ni de délai légal précis**. Le délai de 14 jours est présenté comme un choix commercial de NovaShop, pas comme le minimum légal. Un assistant qui inventerait « l'article 44 » produirait exactement l'hallucination que le projet cherche à mesurer.

### 6. Le corpus est conçu pour le découpage

Chaque document est structuré par sections `##` courtes et son `chunking_profile` indique la stratégie attendue :

| Profil | Fichiers | Découpage |
| --- | --- | --- |
| `policy_clause` | 20 | 1 section = 1 chunk |
| `qa_pair` | 16 | 1 question + réponse = 1 chunk |
| `catalogue_section` | 12 | 1 gamme ou 1 section = 1 chunk |
| `procedure_steps` | 8 | 1 étape ou 1 bloc = 1 chunk |
| `legal_clause` | 8 | 1 principe = 1 chunk |
| `sop_section` | 6 | 1 section = 1 chunk |
| `answer_template` | 2 | 1 modèle de réponse = 1 chunk |
| `reference_table` | 2 | 1 ligne de statut = 1 chunk |

### 7. Trois formats d'entrée, un seul JSONL de sortie

Le cahier des charges impose des documents **PDF**, **Word (.docx)** et **FAQ (JSON, JSONL, CSV)**. Le Markdown de `data/raw/corpus/` reste la source de rédaction — versionnable, lisible en diff, et seule surface contrôlée par le validateur de parité FR/EN — puis `build_sources.py` en dérive les livrables et `extract_documents.py` les réingère.

| Catégorie | Format livré | Fichiers |
| --- | --- | ---: |
| Politiques (10 × 2 langues) | PDF | 20 |
| Synthèses réglementaires (4 × 2) | PDF | 8 |
| Procédures (4 × 2) | DOCX | 8 |
| Opérations internes (5 × 2) | DOCX | 10 |
| Guides produits (6 × 2) | DOCX | 12 |
| FAQ (8 × 2) | JSON (6), JSONL (6), CSV (4) | 16 |

Ce choix n'est pas décoratif : il exerce les trois lecteurs sur des structures réellement différentes. Un PDF n'a pas de sections, seulement des pages ; un DOCX a des titres, des paragraphes et des tableaux ; une FAQ est déjà segmentée en paires. Le pipeline conserve cette granularité :

- **PDF** → un enregistrement par page, avec numéro de page ;
- **DOCX** → un enregistrement par section, titres et tableaux inclus ;
- **FAQ** → un enregistrement par paire question/réponse, avec identifiant et catégorie.

Chaque enregistrement porte `doc_id`, `language`, `title`, `category`, `source_path`, l'empreinte SHA-256 du fichier source, l'extracteur utilisé et l'horodatage. Le nettoyage conserve les accents, la ponctuation française et les valeurs métier (14 jours, 39 MAD, 5 %) : il ne supprime que les espaces insécables, caractères invisibles, caractères de contrôle et lignes vides superflues.

Trois contrôles sont publiés dans `docs/reports/extraction_report.md` : couverture mots extraits / mots source (0,92 à 0,97, aucune troncature), conservation des accents (260/261 enregistrements FR), et détection OCR (0 page signalée). Le seuil d'alerte OCR est de 40 caractères extractibles par page.


## Cohérence du contenu

Les faits métier sont identiques dans tous les documents et dans les deux langues :

- Retour : 14 jours calendaires, 39 MAD de frais sauf défaut
- Remboursement : 7 à 15 jours ouvrés, avoir majoré de 5 %
- Livraison : zones A/B/C, gratuite dès 500 MAD, COD +25 MAD
- Garantie : 12 mois (6 mois accessoires, 3 mois câbles)
- Support : lundi–samedi, 9h–19h, trois boutiques

Cette cohérence est ce qui permet de mesurer la fidélité du RAG : si deux documents se contredisent, le système doit le signaler, pas choisir au hasard.

## Points en attente

- [ ] Production des jeux annotés (`intent_dataset`, `retrieval_eval`, `rag_eval`, `ner_dataset`, `sentiment_dataset`, `urgency_dataset`)
- [ ] Calcul du kappa de Cohen après double annotation
- [ ] Ajout d'un catalogue produits complet (100–200 références) — les guides `CAT-*` n'en couvrent que 25
- [ ] Ajout de la mention « document fictif » sur l'ensemble des livrables

## Avertissement

NovaShop, ses adresses, numéros de téléphone, identifiants ICE/RC et produits sont **entièrement fictifs**. Ils ne désignent aucune entreprise réelle et ne doivent pas être présentés comme authentiques.
