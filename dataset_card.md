# Dataset Card — SupportAI Intent Dataset

## Identité

- **Nom** : SupportAI Intent Dataset
- **Version** : 1.0
- **Fichiers** : `data/annotations/intent_dataset.jsonl`, `data/annotations/intent_dataset.csv`
- **Langues** : français (`fr`) et anglais (`en`)
- **Source** : données **synthétiques** générées pour le projet NovaShop fictif ; aucun client réel, aucune donnée personnelle.
- **Usage** : entraînement, validation et évaluation de la classification d'intentions du projet SupportAI.

## Provenance

- **Taxonomie** : `data/annotations/intents.csv` — 13 intentions + `out_of_scope`.
- **Guidelines** : `docs/annotation_guidelines.md`, version commit `8d5c6a2a655a8dd04c8fc4dc9cea7e4928784d7e` (§5.2–5.7 et §12.4).
- **Schéma** : `docs/data_schema.md` §10.
- **Script de construction** : `scripts/merge_annotations.py --build --single-annotator`.
- **Rapport** : `docs/reports/intent_dataset_report.md` (sans horodatage).
- **Annotation** : Aya uniquement pour les 168 exemples val/test et le sondage de 56 exemples train. Le fichier de Mohammed n'est pas utilisé (colonne `intent` copiée sans réalignement).
- **Relecture** : 34 étiquettes corrigées dans `annotate_aya_done.csv` et `spotcheck_train_aya_done.csv` ; 2 cas de carte cadeau conservés en `promotion_loyalty` et marqués ambigus.

## Composition des splits

| Split | FR | EN | Total |
| --- | ---: | ---: | ---: |
| Train | 238 | 154 | 392 |
| Validation | 56 | 28 | 84 |
| Test | 42 | 42 | 84 |
| **Total** | **336** | **224** | **560** |

| Intention | Train | Val | Test | Total |
| --- | ---: | ---: | ---: | ---: |
| `order_tracking` | 28 | 6 | 6 | 40 |
| `order_change_cancel` | 28 | 6 | 6 | 40 |
| `delivery_issue` | 28 | 6 | 6 | 40 |
| `return_request` | 28 | 6 | 6 | 40 |
| `refund_status` | 28 | 6 | 6 | 40 |
| `payment_info` | 26 | 6 | 6 | 38 |
| `payment_issue` | 28 | 6 | 6 | 40 |
| `technical_support` | 28 | 6 | 6 | 40 |
| `warranty_claim` | 28 | 6 | 6 | 40 |
| `product_info` | 28 | 6 | 6 | 40 |
| `promotion_loyalty` | 30 | 6 | 6 | 42 |
| `account_privacy` | 28 | 6 | 6 | 40 |
| `human_support` | 28 | 6 | 6 | 40 |
| `out_of_scope` | 28 | 6 | 6 | 40 |

## Schéma

`intent_dataset.jsonl` contient une ligne par exemple avec les champs :
`id`, `text`, `language`, `intent`, `acceptable_labels`, `ambiguous`, `source`,
`split`, `annotator_1`, `annotator_2`, `adjudicated`, `notes`, `created_at`.
Les lignes val/test ajoutent `annotation_status = "single_annotator"`.

`intent_dataset.csv` est l'export léger : `id,text,language,intent,split`.

## Annotation

**Val/test annotés par un seul annotateur (Aya). Accord inter-annotateurs non mesuré (κ ≥ 0,75 non vérifié).**

- 168 lignes val/test : `annotator_1 = "aya"`, `annotator_2 = null`, `adjudicated = false`, `annotation_status = "single_annotator"`.
- 392 lignes train : `intent` = `target_intent`, sauf 2 contradictions du sondage où l'étiquette d'Aya est conservée.
- 2 cas ambigus : `INT-0321` et `INT-0325` (cartes cadeaux), `intent = "promotion_loyalty"`, `acceptable_labels = ["payment_info", "promotion_loyalty"]`.
- Aucun kappa de Cohen n'est calculé ; le contrôle est marqué `NON APPLICABLE`.
- Aucune file d'arbitrage n'est produite en mode annotateur unique.

## Limites

- **Pas de kappa** : l'accord inter-annotateurs n'est pas mesuré ; le seuil de 0,75 n'est pas vérifié.
- **Biais de l'annotateur unique** : les étiquettes val/test reflètent la lecture d'une seule personne.
- **Jeu de test non double-annoté** : sa qualité inter-annotateurs reste inconnue.
- **Jeu de test non gelé** : le gel et l'empreinte SHA-256 relèvent de la tâche « Freeze test datasets ».
- **Déséquilibre léger** : `payment_info` = 38 exemples, `promotion_loyalty` = 42, les autres classes = 40.
- **Fichier de Mohammed non utilisé** : la feuille vide `data/annotations/blind/annotate_mohammed.csv` est prête ; le retour attendu sera `annotate_mohammed_done.csv`.
- **Données synthétiques** : le dataset ne contient aucune donnée client réelle et ne doit pas être présenté comme tel.

## Reproductibilité

```bash
python scripts/merge_annotations.py --single-annotator
python scripts/merge_annotations.py --build --single-annotator
python tests/test_merge_annotations.py
```
