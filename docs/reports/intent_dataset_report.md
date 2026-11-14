# Rapport de fusion des annotations d'intentions — SupportAI

> Généré par `scripts/merge_annotations.py --single-annotator`. Aucun horodatage : le rapport est reproductible à partir des fichiers d'entrée.
> Version des guidelines : commit `8d5c6a2a655a8dd04c8fc4dc9cea7e4928784d7e` (`docs/annotation_guidelines.md`, identique à HEAD).

## 1. Contexte et protocole

**Annotation : annotateur unique (Aya) ; accord inter-annotateurs non mesuré.**

Seule Aya a annoté les 168 exemples de validation et de test, puis réalisé le sondage sur 56 exemples de train. Aucun second annotateur n'est disponible. Le fichier de Mohammed n'est ni lu ni utilisé dans ce mode.

- Exemples : **560** (train 392, val 84, test 84).
- Langues : FR et EN ; les identifiants sont partagés entre les langues.
- Annotateur : **Aya uniquement**.
- Fichiers d'entrée : aya = `data/annotations/blind/annotate_aya_done.csv`, spotcheck = `data/annotations/blind/spotcheck_train_aya_done.csv`.
- Statut du build : **écrit : 560 lignes**.

Aucun kappa de Cohen n'est calculé. Aucune file d'arbitrage n'est produite. Les étiquettes ne sont pas remplacées automatiquement ; les corrections de relecture sont appliquées dans les fichiers d'annotation.

## 2. Validation des fichiers

- Les fichiers d'entrée Aya et sondage train sont présents et lisibles.
- Tous les identifiants attendus sont présents : 168 pour Aya val/test, 56 pour le sondage train.
- Toutes les étiquettes appartiennent aux 14 codes de `intents.csv`.
- Aucune ligne vide.
- Chaque ligne `ambiguous=true` possède au moins un code dans `acceptable_labels`.
- **Résultat : OK.**

## 3. Contrôle de cohérence avec les cibles

Ce contrôle n'est pas une mesure inter-annotateurs. Il compare les étiquettes d'Aya aux `target_intent` du fichier privé, sans correction automatique.

- Différences val/test : **0/168**.
- Différences train sondé : **2/56**.
- Total : **2/224** comparaisons annotées.

| Périmètre | id | Texte | Étiquette Aya | Cible |
| --- | --- | --- | --- | --- |
| train (sondage) | INT-0321 | peut-on payer avec une carte cadeau et une carte bancaire ensemble ? | promotion_loyalty | payment_info |
| train (sondage) | INT-0325 | can a gift card be used to pay for an order? | promotion_loyalty | payment_info |

Les étiquettes listées ci-dessus restent inchangées dans les fichiers d'annotation. Les corrections de relecture sont appliquées directement dans `annotate_aya_done.csv` et `spotcheck_train_aya_done.csv` ; ce rapport ne liste que les différences restantes. Cette liste est une file de relecture pour Aya, pas une file d'arbitrage automatique. Pour le train, l'étiquette d'Aya est conservée dans le dataset en cas de contradiction.

Les cas restants marqués `ambiguous=true` sont `INT-0321`, `INT-0325` ; `acceptable_labels` contient les deux codes possibles.

## 4. Dataset

- Statut : **écrit : 560 lignes**.
- Lignes val/test : `intent` = étiquette d'Aya, `annotator_1 = "aya"`, `annotator_2 = null`, `adjudicated = false`, `annotation_status = "single_annotator"`.
- Lignes train : `intent` = `target_intent`, sauf contradiction du sondage où l'étiquette d'Aya est conservée et signalée dans `notes`.
- Export CSV : `data/annotations/intent_dataset.csv` (`id,text,language,intent,split`).

### 4.1 Par split et par langue

| Split | FR | EN | Total |
| --- | --- | --- | --- |
| train | 238 | 154 | 392 |
| val | 56 | 28 | 84 |
| test | 42 | 42 | 84 |
| **Total** | 336 | 224 | 560 |

### 4.2 Par split et par intention

| Intention | Train | Val | Test | Total |
| --- | --- | --- | --- | --- |
| order_tracking | 28 | 6 | 6 | 40 |
| order_change_cancel | 28 | 6 | 6 | 40 |
| delivery_issue | 28 | 6 | 6 | 40 |
| return_request | 28 | 6 | 6 | 40 |
| refund_status | 28 | 6 | 6 | 40 |
| payment_info | 26 | 6 | 6 | 38 |
| payment_issue | 28 | 6 | 6 | 40 |
| technical_support | 28 | 6 | 6 | 40 |
| warranty_claim | 28 | 6 | 6 | 40 |
| product_info | 28 | 6 | 6 | 40 |
| promotion_loyalty | 30 | 6 | 6 | 42 |
| account_privacy | 28 | 6 | 6 | 40 |
| human_support | 28 | 6 | 6 | 40 |
| out_of_scope | 28 | 6 | 6 | 40 |

Les effectifs val/test sont ceux des étiquettes d'Aya, sans arbitrage ni double annotation.

## 5. Contrôles qualité §12.4

| Contrôle | Valeur | Seuil | Statut | Portée |
| --- | --- | --- | --- | --- |
| ≥ 25 exemples par classe (train) | min=26 | ≥ 25 | OK | 392 exemples train |
| Classe majoritaire (train) | promotion_loyalty = 30 (7,65 %) | < 30 % | OK | 392 exemples train |
| Taux d'exemples ambigus | 2/560 (0,36 %) | < 10 % | OK | 560 exemples |
| Doublons exacts | 0 | 0 | OK | textes normalisés |
| Quasi-doublons (Jaccard trigrammes ≥ 0,8) | 0 | 0 | OK | 560 exemples |
| Kappa de Cohen global (val+test) | non mesuré (annotateur unique) | ≥ 0,75 | NON APPLICABLE | annotateur unique |
| Fuite de paraphrase entre splits | 0 | 0 | OK | paires Jaccard ≥ 0,8 |
| Indépendance des annotations | NON APPLICABLE (annotateur unique) | non applicable | NON APPLICABLE | un seul annotateur |

## 6. Limites

- Aucun kappa n'est calculé : l'accord inter-annotateurs n'est pas mesuré et le seuil de 0,75 n'est pas vérifié.
- Risque de biais de l'annotateur unique : les étiquettes val/test reflètent la lecture d'une seule personne.
- Le jeu de test n'est pas double-annoté ; sa qualité inter-annotateurs reste inconnue.
- Le jeu de test n'est pas gelé dans cette tâche : le gel et l'empreinte SHA-256 relèvent de la tâche « Freeze test datasets ».
- Le fichier de Mohammed est invalide (colonne `intent` copiée sans réalignement) et n'est pas utilisé.
- Aucun commit ni push n'a été effectué. Le rapport ne contient pas d'horodatage.

## 7. Reproductibilité

```bash
python scripts/merge_annotations.py --single-annotator
python scripts/merge_annotations.py --build --single-annotator
python tests/test_merge_annotations.py
```
