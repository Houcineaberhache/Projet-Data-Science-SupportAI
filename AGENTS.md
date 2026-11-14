# AGENTS.md — SupportAI

## Objet du dépôt

SupportAI est un projet académique de support client intelligent : classification
d'intentions, retrieval lexical et sémantique, RAG avec citations, évaluation et
application web. Le corpus NovaShop est **fictif** et les données d'annotation
sont **synthétiques**.

## Sources de vérité

- `docs/annotation_guidelines.md` : règles d'annotation et contrôles qualité.
- `docs/data_schema.md` : schémas des corpus, annotations et jeux d'évaluation.
- `data/annotations/intents.csv` : taxonomie des 14 codes d'intention.
- `data/processed/chunked_corpus.jsonl` : chunks indexables du corpus.
- `docs/data-engineering/README.md` : livrables et commandes data engineering.
- `dataset_card.md` : provenance, composition et limites du dataset d'intentions.

## Règles de travail

- **Pas de commit ni de push** sans demande explicite.
- **Pas d'installation de package** sans demande explicite ; privilégier la
  bibliothèque standard quand c'est possible.
- Ne pas modifier `data/raw/`, `data/processed/`, le corpus ou les règles métier
  sans demande explicite.
- Ne jamais committer de secrets, identifiants, données personnelles ou index
  vectoriels locaux.
- Préserver la parité FR/EN du corpus et des livrables.
- Pour le RAG, n'utiliser que les chunks dont `index_in_rag == true` ; les
  références externes ne sont pas des règles NovaShop.
- Les rapports générés ne contiennent pas d'horodatage. Les commandes et les
  résultats réels doivent être reproductibles.

## Annotation des intentions

- Lire `docs/annotation_guidelines.md` §5.2 à §5.7 et §12.4 avant toute
  modification.
- Une seule étiquette principale par exemple. Si l'ambiguïté n'est pas résolue
  par une règle, utiliser `ambiguous=true` et renseigner `acceptable_labels`.
- Ne pas exposer `data/annotations/_private/` aux annotateurs et ne pas utiliser
  les cibles privées pour remplacer silencieusement une étiquette.
- Les fichiers canoniques sont :
  - `data/annotations/blind/annotate_aya_done.csv` (Aya, val/test) ;
  - `data/annotations/blind/spotcheck_train_aya_done.csv` (Aya, sondage train) ;
  - `data/annotations/blind/annotate_mohammed.csv` (feuille vide pour Mohammed) ;
  - `data/annotations/blind/annotate_mohammed_done.csv` (retour attendu de Mohammed).
- Le mode courant est **annotateur unique (Aya)** : aucun kappa n'est mesuré,
  aucune file d'arbitrage n'est produite, et le jeu de test n'est pas gelé.
- Les corrections de relecture sont appliquées dans les fichiers d'annotation ;
  le script de fusion ne remplace jamais une étiquette automatiquement.

## Commandes utiles

```bash
# Corpus et extraction
python scripts/manage_corpus.py validate
python scripts/manage_corpus.py build
python scripts/extract_documents.py
python scripts/clean_corpus.py
python scripts/chunk_corpus.py

# Annotation des intentions
python scripts/merge_annotations.py --single-annotator
python scripts/merge_annotations.py --build --single-annotator
python tests/test_merge_annotations.py

# Jeu d'évaluation RAG
python scripts/build_rag_eval.py validate
python scripts/build_rag_eval.py build
python tests/test_rag_eval.py
```

## Structure utile

```text
backend/              API et services
data/raw/             corpus source
data/processed/       corpus extrait, nettoyé, chunké
data/annotations/     taxonomie, annotations, jeux d'évaluation
docs/                 guidelines, schémas, rapports
ml/                   NLP, retrieval, RAG
scripts/              pipelines et validateurs
tests/                tests Python
```
