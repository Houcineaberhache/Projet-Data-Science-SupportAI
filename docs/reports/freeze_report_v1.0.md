# Rapport de gel des jeux de test — SupportAI

- Version : **v1.0**
- Dossier : `data/frozen/v1.0/`
- Licence : **NovaShop-Proprietary-Synthetic** (`internal_verified`)
- Source de la licence : `data/source_manifest.csv`
- Note de licence : Licence confirmée pour les 74 fichiers de langue du corpus (reuse_permission=full_text_index). Les 7 références externes ne sont pas indexées et gardent leurs licences propres. Les jeux dérivés (intent_dataset, rag_eval, robustness_eval, gel v1.0) n'ont pas de licence distincte explicite dans le dépôt ; la redistribution hors projet reste à confirmer.
- Statut d'annotation : `single_annotator`
- Graine : `42`
- Horodatage : aucun (rapport reproductible).

## Contrôles anti-fuite

| Contrôle | Description | Résultat |
| --- | ---: | ---: |
| a | ids uniques et union complète | OK |
| b | aucun texte exact test ↔ train/val | OK |
| c | aucun quasi-doublon test ↔ train/val (Jaccard ≥ 0,80) | OK |
| d | aucun identifiant de commande ni numéro identifiant partagé | OK |
| e | recherche de fuite par traduction (signalement) | OK |
| f | aucun doublon RAG/robustesse ↔ intentions | OK |
| g | gold_chunk_id valides, customer et indexés | OK |

Le contrôle **e** est non bloquant : il signale des paires à revoir ; aucune étiquette ni aucun texte n'est corrigé par le script.

## Paires à revue humaine

### Paires Jaccard 0,60–0,80

- Aucune paire.

### Fuite par traduction (signalements)

- INT-0445 (en) ↔ INT-0223 (val, fr) — 14 ; 14
- INT-0445 (en) ↔ INT-0421 (train, fr) — 14 ; 14, pc

### Décision d'analyse des signalements

- Cas légitime : seul le nombre 14 est partagé ; les intentions diffèrent (`warranty_claim` vs `return_request`) et il n'y a pas de traduction. L'exemple est conservé tel quel.
- Fuite de traduction confirmée : même intention `warranty_claim`, même nombre 14 mois et même propos (batterie couverte par la garantie) en EN et en FR. Aucun exemple n'est modifié dans v1.0 ; une décision humaine est requise avant toute nouvelle version.

### Nombres courts partagés (non bloquants)

- 14 : INT-0445 ↔ INT-0223, INT-0421

## Effectifs figés

| Split | Total | FR | EN | SHA-256 de la liste d'ids |
| --- | ---: | ---: | ---: | ---: |
| train | 392 | 238 | 154 | 023dc82a37778ce3ef2d97642ab9567697344fd8ca6ea731dbec96a0eee2e5cc |
| val | 84 | 56 | 28 | 57e96ecbeca390b97d1c6e86b7fdf85f021aec662c3ac3ac3e21433f943c44d4 |
| test | 84 | 42 | 42 | 889f326a8b812173d916e86396e8e7f11c10a7b410d1aa4394c0af07d2b86925 |

Total général : **560** exemples (336 FR, 224 EN).

## Fichiers gelés

| Fichier | Lignes | Octets | SHA-256 |
| --- | ---: | ---: | ---: |
| intent_test.jsonl | 84 | 36601 | 088b67d803a23c46167a672c8a777ea304294dd4813ac44b70bf688f859392ee |
| intent_test_inputs.jsonl | 84 | 18552 | 5084d6de4884faa2dbfcbcf954bfba46efc1c8447d6b89f4ef274a44d6fc0a30 |
| intent_val.jsonl | 84 | 36744 | e53a00c169954508567587b95837e60cd4325c72e603cd123e88e4d9220ad31c |
| rag_eval.jsonl | 140 | 90117 | 78e94300d610db7a1280adbd107a2b14a335e54c580cd443006c81dde6959eda |
| robustness_eval.jsonl | 35 | 9141 | 2b487ee17ca9f2b4ecb2373917164c00c396019860fdb79837713ede11a17c99 |
| split_ids.json | 606 | 12265 | 9cdfcc09c765addcf03d138c5b17b32ba2d63aa6459b77a54bcf4dd99c8ece15 |

## Empreintes des sources

| Source | Lignes | SHA-256 |
| --- | ---: | ---: |
| chunked_corpus | 678 | 57b0515b2efaa02519372710426e5ccad4858fe140eb8ad61e2a6ac153b80f6e |
| intent_dataset | 560 | c8c98ed852abd9c46dbfe48d3ab56e2b2d1cdc040881220da84105d134627ecf |
| rag_eval | 140 | 78e94300d610db7a1280adbd107a2b14a335e54c580cd443006c81dde6959eda |
| robustness_eval | 35 | 2b487ee17ca9f2b4ecb2373917164c00c396019860fdb79837713ede11a17c99 |

## Provenance git

- Commit courant : `04b6a3ce3a7803d7e1fc004aae0cd87d46dc2d87`
- État : **dirty**
- Commit des guidelines : `83f8ff9f6b62620cda88018ea01905d0438e7513`
- SHA-256 des guidelines : `44c60cc722fa6a785d53b2dd246e10c3ef833af86c8f48d28b9cfce80614c35e`

## Commandes

```bash
python scripts/freeze_test_sets.py freeze           # premier gel uniquement
python scripts/freeze_test_sets.py verify
python scripts/freeze_test_sets.py freeze           # doit refuser d'ecraser v1.0
sha256sum data/frozen/v1.0/*                        # ou hashlib si sha256sum est absent
python tests/test_freeze.py
git status --short
```
