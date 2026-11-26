# Dataset Card — SupportAI Intent Dataset

## Identité

- **Nom** : SupportAI Intent Dataset
- **Version** : 1.0
- **Fichiers** : `data/annotations/intent_dataset.jsonl`, `data/annotations/intent_dataset.csv`
- **Langues** : français (`fr`) et anglais (`en`)
- **Source** : données **synthétiques** générées pour le projet NovaShop fictif ; aucun client réel, aucune donnée personnelle.
- **Usage** : entraînement, validation et évaluation de la classification d'intentions du projet SupportAI.

## Version et gel

- **Gel courant** : **v1.1** — `data/frozen/v1.1/`, licence `NovaShop-Proprietary-Synthetic` (statut `internal_verified`, redistribution hors projet à confirmer), graine `42`, statut d'annotation `single_annotator`.
- **Gel historique** : **v1.0** — `data/frozen/v1.0/` conservé intégralement ; rapport archivé dans `docs/reports/freeze_report_v1.0.md`.
- **Fichiers gelés** : `split_ids.json`, `intent_test.jsonl`, `intent_test_inputs.jsonl`, `intent_val.jsonl`, `rag_eval.jsonl`, `robustness_eval.jsonl`, `MANIFEST.json`.
- **Sources gelées v1.1** : `data/annotations/intent_dataset_v1.1.jsonl` (SHA-256 `1dd83e5e7c03a8c40c31d9e2a0daa1b52cf677ff1475ebee795d892da2e80dbd`), `data/annotations/rag_eval.jsonl` (`78e94300d610db7a1280adbd107a2b14a335e54c580cd443006c81dde6959eda`), `data/annotations/robustness_eval.jsonl` (`2b487ee17ca9f2b4ecb2373917164c00c396019860fdb79837713ede11a17c99`) et `data/processed/chunked_corpus.jsonl` (`57b0515b2efaa02519372710426e5ccad4858fe140eb8ad61e2a6ac153b80f6e`). La source v1.0 `data/annotations/intent_dataset.jsonl` (`c8c98ed852abd9c46dbfe48d3ab56e2b2d1cdc040881220da84105d134627ecf`) reste inchangée.
- **Empreintes des listes d'ids v1.1** : train `c39929c7f6a34c0aa56f6547e08399468b3d763663c5f1fa16f6fbb9a5011569`, test `14cd552bc682c141c66f7230e568994279a0122c806a2e81ab3c3fefa9ac1dd1`, validation `57e96ecbeca390b97d1c6e86b7fdf85f021aec662c3ac3ac3e21433f943c44d4`.
- **Empreintes des fichiers gelés v1.1** : `intent_test.jsonl` `dce0fe099df745e52b60ff0e5f6fd1995fdb550d7601ba9ac5ac5825d46fd304`, `intent_test_inputs.jsonl` `8f60a7ea7effc6deb636bd596552e94fa045e15f9e350da331a88e2aa36acca1`, `intent_val.jsonl` `e53a00c169954508567587b95837e60cd4325c72e603cd123e88e4d9220ad31c`.
- **Vérification** : `python scripts/freeze_test_sets.py verify --version 1.1` et `--version 1.0` recalculent les empreintes et rejouent les contrôles a→g ; tout écart donne un code de sortie non nul.
- **Rapport** : `docs/reports/freeze_report.md` et `docs/reports/freeze_report_v1.1.md` (sans horodatage).
- **Décision sur les signalements de traduction** : `INT-0445` / `INT-0421` est une **fuite de traduction confirmée** ; en v1.1, `INT-0421` est regroupé avec `INT-0445` dans le split `test` sans changer son texte ni son étiquette. `INT-0445` / `INT-0223` reste un **cas légitime** (seul `14` est partagé, intentions `warranty_claim` vs `return_request`). Aucun exemple n'est supprimé.

### Différences v1.0 → v1.1

| Élément | v1.0 | v1.1 |
| --- | --- | ---: |
| Effectif train | 392 | 391 |
| Effectif val | 84 | 84 |
| Effectif test | 84 | 85 |
| Source intentions | `intent_dataset.jsonl` | `intent_dataset_v1.1.jsonl` |
| `INT-0421` | train | test |
| `INT-0445` | test | test |
| Fuite TR-0001 | présente | corrigée |
| `intent_test.jsonl` | `088b67d8…` | `dce0fe09…` |

## Licence

- **Source confirmée** : `data/source_manifest.csv` déclare `NovaShop-Proprietary-Synthetic` pour les **74 fichiers de langue** (statut `internal_verified`, `reuse_permission = full_text_index`). Le corpus est rédigé par l'équipe SupportAI pour NovaShop, société fictive.
- **Références externes** : les 7 entrées `EXT-01` à `EXT-07` ne sont pas indexées et conservent leurs propres licences (`Official-Text-No-Reuse-Claimed`, `EU-Reuse-Decision-2011-833`, `Public-Domain-US-Government`, `CC-BY-4.0`, `CC-BY-SA-4.0`). Elles ne sont pas des règles NovaShop et ne font pas l'objet d'une réutilisation de texte dans les jeux.
- **Jeux dérivés** : `intent_dataset`, `intent_dataset_v1.1`, `rag_eval`, `robustness_eval` et les gels `v1.0` / `v1.1` n'ont pas de licence distincte explicite dans le dépôt. Ils héritent des conditions du corpus synthétique interne ; toute **redistribution hors du projet** reste à confirmer par le propriétaire du projet.
- Le `MANIFEST.json` du gel enregistre la licence source, son statut, sa source et cette réserve. Aucune licence externe n'a été inventée pour remplacer l'ancien placeholder.

## Provenance

- **Taxonomie** : `data/annotations/intents.csv` — 13 intentions + `out_of_scope`.
- **Guidelines** : `docs/annotation_guidelines.md`, version commit `83f8ff9f6b62620cda88018ea01905d0438e7513` (§5.2–5.7 et §12.4).
- **Schéma** : `docs/data_schema.md` §10.
- **Script de construction** : `python scripts/merge_annotations.py --build --single-annotator --today 2026-11-14` (la date explicite est nécessaire pour reproduire `created_at`).
- **Rapport** : `docs/reports/intent_dataset_report.md` (sans horodatage).
- **Gel v1.0** : commit git `04b6a3ce3a7803d7e1fc004aae0cd87d46dc2d87` (dépôt sale au gel, voir `MANIFEST.json`), commit des guidelines `83f8ff9f6b62620cda88018ea01905d0438e7513`, SHA-256 des guidelines `44c60cc722fa6a785d53b2dd246e10c3ef833af86c8f48d28b9cfce80614c35e`. Les données restent générées pour NovaShop, société fictive ; aucune donnée client réelle n'est incluse.
- **Gel v1.1** : même commit git et mêmes guidelines ; source d'intentions corrigée `data/annotations/intent_dataset_v1.1.jsonl` générée par `scripts/apply_translation_split_fix.py`. Le `MANIFEST.json` v1.1 enregistre le groupe `TR-0001`, les sources des deux exemples et la stratégie de regroupement.
- **Annotation** : Aya uniquement pour les 168 exemples val/test et le sondage de 56 exemples train. Le fichier de Mohammed n'est pas utilisé (colonne `intent` copiée sans réalignement).
- **Relecture** : 34 étiquettes corrigées dans `annotate_aya_done.csv` et `spotcheck_train_aya_done.csv` ; 2 cas de carte cadeau conservés en `promotion_loyalty` et marqués ambigus.

## Composition des splits

| Split | FR | EN | Total |
| --- | ---: | ---: | ---: |
| Train | 237 | 154 | 391 |
| Validation | 56 | 28 | 84 |
| Test | 43 | 42 | 85 |
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
| `warranty_claim` | 27 | 6 | 7 | 40 |
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

## Étiquetage

- Une seule étiquette principale par exemple, portée par `intent` ; `acceptable_labels` liste uniquement les alternatives jugées acceptables par les guidelines.
- Les cas ambigus (`ambiguous = true`, ici `INT-0321` et `INT-0325`) conservent leurs deux libellés acceptables ; le gel ne corrige ni ne supprime ces exemples.
- Mode courant : annotateur unique (Aya). Aucun kappa n'est mesuré et aucune file d'arbitrage n'est produite ; le gel versionné remplace l'absence de gel historique sans changer les étiquettes.
- Les sources d'annotation ne sont pas modifiées par le gel. `intent_test_inputs.jsonl` retire uniquement `intent`, `acceptable_labels`, `ambiguous`, `notes`, `annotator_*` et `adjudicated` pour éviter toute fuite d'étiquette.
- Les paires signalées par les contrôles de fuite par traduction sont laissées telles quelles et transmises à la revue humaine (`docs/reports/freeze_report.md`).

## Utilisation autorisée / interdite

**Autorisé**

- Entraîner sur `train`, régler les hyperparamètres sur `val` et évaluer uniquement sur `intent_test.jsonl` ou `intent_test_inputs.jsonl`.
- Utiliser `rag_eval.jsonl` et `robustness_eval.jsonl` pour l'évaluation RAG, avec pour seul contexte les chunks `index_in_rag = true` et `audience = customer`.
- Relire les paires signalées dans le rapport de gel et documenter toute décision dans une nouvelle version.

**Interdit**

- Modifier, réécrire ou compléter un fichier d'un gel existant (`v1.0` ou `v1.1`) ; toute évolution exige une nouvelle version.
- Entraîner, sélectionner un modèle ou injecter dans un prompt les étiquettes du test, y compris via `intent_test_inputs.jsonl`.
- Réintroduire les champs retirés dans les entrées de test ou utiliser les cibles privées pour corriger silencieusement une étiquette.
- Ouvrir ou utiliser `data/annotations/_private/` dans un pipeline d'évaluation public.
- Présenter NovaShop ou ses données comme une entreprise ou des clients réels.

## Règle de changement

- Toute modification des sources, de la taxonomie, des guidelines ou des contrôles impose un nouveau gel versionné (`v1.2`, `v1.3`, …) ; `v1.0` et `v1.1` restent intacts.
- `python scripts/freeze_test_sets.py freeze --version X` refuse d'écraser `data/frozen/vX/` : il faut changer la version, jamais forcer l'écriture.
- `MANIFEST.json` enregistre les empreintes des sources et des fichiers gelés, le commit git courant, l'état du dépôt, le commit des guidelines, la licence, la graine, le statut d'annotation et le résultat des contrôles a→g, sans horodatage.

## Limites

- **Pas de kappa** : l'accord inter-annotateurs n'est pas mesuré ; le seuil de 0,75 n'est pas vérifié.
- **Biais de l'annotateur unique** : les étiquettes val/test reflètent la lecture d'une seule personne.
- **Jeu de test non double-annoté** : sa qualité inter-annotateurs reste inconnue.
- **Jeu de test gelé en v1.1** : empreintes, contrôles a→g et paires à revue humaine dans `docs/reports/freeze_report.md` ; l'état v1.0 reste archivé dans `docs/reports/freeze_report_v1.0.md`.
- **Déséquilibre léger** : `payment_info` = 38 exemples, `promotion_loyalty` = 42, les autres classes = 40.
- **Fichier de Mohammed non utilisé** : la feuille vide `data/annotations/blind/annotate_mohammed.csv` est prête ; le retour attendu sera `annotate_mohammed_done.csv`.
- **Données synthétiques** : le dataset ne contient aucune donnée client réelle et ne doit pas être présenté comme tel.

## Reproductibilité

```bash
python scripts/merge_annotations.py --single-annotator
python scripts/merge_annotations.py --build --single-annotator --today 2026-11-14
python tests/test_merge_annotations.py

# Gel v1.0 historique : une seule fois depuis un dépôt propre, puis vérification
python scripts/freeze_test_sets.py freeze --version 1.0
python scripts/freeze_test_sets.py verify --version 1.0

# Gel v1.1 courant
python scripts/apply_translation_split_fix.py
python scripts/freeze_test_sets.py freeze --version 1.1
python scripts/freeze_test_sets.py verify --version 1.1
python tests/test_freeze.py
python tests/test_translation_leak.py
```

La date `2026-11-14` est celle des `created_at` des gels `v1.0` et `v1.1`. Sans `--today`, `merge_annotations.py` utilise la date courante : les données changent et le gel doit être rejeté. Le script de correction ne modifie que `split` et écrit une source dérivée ; il ne touche ni à `intent_dataset.jsonl` ni aux annotations.
