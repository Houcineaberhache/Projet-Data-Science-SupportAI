# Annotation aveugle des intentions — SupportAI

Tu annotes **seul(e)**, sans consulter l'autre annotateur et sans ouvrir le fichier privé `intent_candidates.jsonl`.

## Fichiers à remplir

- `annotate_aya.csv` ou `annotate_mohammed.csv` : 168 exemples de validation et de test.
- `spotcheck_train_aya.csv` : 56 exemples de train pour le contrôle qualité.

Les colonnes `intent`, `ambiguous`, `acceptable_labels` et `notes` sont **vides** : c'est à toi de les remplir.

## Avant de commencer

Lis `docs/annotation_guidelines.md` :

- §5.2 Choix de l'étiquette
- §5.3 Frontières entre classes
- §5.4 Cas ambigus
- Annexe B Checklist de l'annotateur

## Valeurs autorisées pour `intent`

`order_tracking`, `order_change_cancel`, `delivery_issue`, `return_request`, `refund_status`,
`payment_info`, `payment_issue`, `technical_support`, `warranty_claim`, `product_info`,
`promotion_loyalty`, `account_privacy`, `human_support`, `out_of_scope`.

Une seule étiquette principale par exemple. Si deux annotateurs formés peuvent raisonnablement
choisir deux étiquettes différentes et qu'aucune règle du guide ne tranche, mets `ambiguous=true`
et renseigne `acceptable_labels` avec les codes possibles. Sinon, applique la règle et laisse
`ambiguous=false` avec `acceptable_labels` vide.

## Consignes pratiques

- Ne consulte ni l'autre annotateur, ni le fichier privé des questions candidates.
- Sauvegarde ton fichier toutes les 50 lignes.
- Ajoute une note dans `notes` pour les cas difficiles.
- Quand tu as terminé, renvoie le fichier sous le nom `annotate_<prénom>_done.csv`
  (par exemple `annotate_aya_done.csv` ou `annotate_mohammed_done.csv`).
- Pour le sondage train, renvoie `spotcheck_train_aya_done.csv`.

Ne modifie pas les colonnes `id`, `language` et `text`.
