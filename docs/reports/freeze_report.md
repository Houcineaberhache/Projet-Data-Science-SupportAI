# Rapport de gel des jeux de test — SupportAI

- Version : **v1.1**
- Dossier : `data/frozen/v1.1/`
- Note de version : Correction de la fuite de traduction TR-0001 : `INT-0421` rejoint `INT-0445` dans `test`. Aucune suppression, aucun texte ni étiquette modifié. `INT-0445` / `INT-0223` reste un cas légitime documenté.
- Licence : **NovaShop-Proprietary-Synthetic** (`internal_verified`)
- Source de la licence : `data/source_manifest.csv`
- Note de licence : Licence confirmée pour les 74 fichiers de langue du corpus (reuse_permission=full_text_index). Les 7 références externes ne sont pas indexées et gardent leurs licences propres. Les jeux dérivés (intent_dataset, rag_eval, robustness_eval, gel v1.1) n'ont pas de licence distincte explicite dans le dépôt ; la redistribution hors projet reste à confirmer.
- Statut d'annotation : `single_annotator`
- Graine : `42`
- Horodatage : aucun (rapport reproductible).

## Correction de la fuite de traduction

- Groupe : `TR-0001`
- Stratégie : Regrouper les exemples traduits dans le même split ; seul le champ `split` est modifié, aucun texte ni étiquette n'est touché.
- Split cible : `test`

| Id | Langue | Split v1.0 | Split v1.1 | Source |
| --- | ---: | ---: | ---: | ---: |
| INT-0421 | fr | train | test | `data/annotations/_private/intent_candidates.jsonl` |
| INT-0445 | en | test | test | `data/annotations/blind/annotate_aya_done.csv` |

- Cas légitime conservé : INT-0445, INT-0223 — Intentions différentes (`warranty_claim` vs `return_request`) ; seul le nombre 14 est partagé.

## Comparaison v1.0 / v1.1

| Élément | v1.0 | v1.1 |
| --- | ---: | ---: |
| Effectif train | 392 | 391 |
| Effectif val | 84 | 84 |
| Effectif test | 84 | 85 |
| Source intent SHA-256 | c8c98ed852abd9c46dbfe48d3ab56e2b2d1cdc040881220da84105d134627ecf | 1dd83e5e7c03a8c40c31d9e2a0daa1b52cf677ff1475ebee795d892da2e80dbd |
| intent_test SHA-256 | 088b67d803a23c46167a672c8a777ea304294dd4813ac44b70bf688f859392ee | dce0fe099df745e52b60ff0e5f6fd1995fdb550d7601ba9ac5ac5825d46fd304 |
| Fuite TR-0001 | INT-0445 (test) / INT-0421 (train) | corrigée : INT-0421 et INT-0445 tous deux en test |

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

### Décision d'analyse des signalements

- Cas légitime : seul le nombre 14 est partagé ; les intentions diffèrent (`warranty_claim` vs `return_request`) et il n'y a pas de traduction. L'exemple est conservé tel quel.
- Fuite de traduction confirmée : même intention `warranty_claim`, même nombre 14 mois et même propos (batterie couverte par la garantie) en EN et en FR. Dans v1.0, aucun exemple n'est modifié ; en v1.1, `INT-0421` est regroupé avec `INT-0445` dans le split `test` sans changer son texte ni son étiquette.

### Nombres courts partagés (non bloquants)

- 14 : INT-0421, INT-0445 ↔ INT-0223

## Effectifs figés

| Split | Total | FR | EN | SHA-256 de la liste d'ids |
| --- | ---: | ---: | ---: | ---: |
| train | 391 | 237 | 154 | c39929c7f6a34c0aa56f6547e08399468b3d763663c5f1fa16f6fbb9a5011569 |
| val | 84 | 56 | 28 | 57e96ecbeca390b97d1c6e86b7fdf85f021aec662c3ac3ac3e21433f943c44d4 |
| test | 85 | 43 | 42 | 14cd552bc682c141c66f7230e568994279a0122c806a2e81ab3c3fefa9ac1dd1 |

Total général : **560** exemples (336 FR, 224 EN).

## Fichiers gelés

| Fichier | Lignes | Octets | SHA-256 |
| --- | ---: | ---: | ---: |
| intent_test.jsonl | 85 | 36941 | dce0fe099df745e52b60ff0e5f6fd1995fdb550d7601ba9ac5ac5825d46fd304 |
| intent_test_inputs.jsonl | 85 | 18741 | 8f60a7ea7effc6deb636bd596552e94fa045e15f9e350da331a88e2aa36acca1 |
| intent_val.jsonl | 84 | 36744 | e53a00c169954508567587b95837e60cd4325c72e603cd123e88e4d9220ad31c |
| rag_eval.jsonl | 140 | 90117 | 78e94300d610db7a1280adbd107a2b14a335e54c580cd443006c81dde6959eda |
| robustness_eval.jsonl | 35 | 9141 | 2b487ee17ca9f2b4ecb2373917164c00c396019860fdb79837713ede11a17c99 |
| split_ids.json | 606 | 12265 | 7218e940a7c6133cd9234edcb1178dec01257ddc14e10d8b7795e3c3f7fa0a78 |

## Empreintes des sources

| Source | Lignes | SHA-256 |
| --- | ---: | ---: |
| chunked_corpus | 678 | 57b0515b2efaa02519372710426e5ccad4858fe140eb8ad61e2a6ac153b80f6e |
| intent_dataset | 560 | 1dd83e5e7c03a8c40c31d9e2a0daa1b52cf677ff1475ebee795d892da2e80dbd |
| rag_eval | 140 | 78e94300d610db7a1280adbd107a2b14a335e54c580cd443006c81dde6959eda |
| robustness_eval | 35 | 2b487ee17ca9f2b4ecb2373917164c00c396019860fdb79837713ede11a17c99 |

## Provenance git

- Commit courant : `04b6a3ce3a7803d7e1fc004aae0cd87d46dc2d87`
- État : **dirty**
- Commit des guidelines : `83f8ff9f6b62620cda88018ea01905d0438e7513`
- SHA-256 des guidelines : `44c60cc722fa6a785d53b2dd246e10c3ef833af86c8f48d28b9cfce80614c35e`

## Commandes

```bash
python scripts/freeze_test_sets.py freeze --version 1.1  # premier gel uniquement
python scripts/freeze_test_sets.py verify --version 1.1
python scripts/freeze_test_sets.py verify --version 1.0  # gel historique
python scripts/freeze_test_sets.py freeze --version 1.1  # doit refuser d'ecraser
sha256sum data/frozen/v1.1/*                        # ou hashlib si sha256sum est absent
python tests/test_freeze.py
python tests/test_translation_leak.py
git status --short
```
