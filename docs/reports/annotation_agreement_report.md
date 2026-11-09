# Rapport d'accord inter-annotateurs — annotation pilote des intentions

> Généré par `scripts/calculate_kappa.py` à partir de `data/annotations/pilot_20_annotation_sheet.csv`.
> Aucun horodatage : le rapport est reproductible à partir des fichiers d'entrée.

## 1. Contexte

Le projet **SupportAI** (NovaShop, e-commerce fictif) construit un assistant de support bilingue FR/EN. Le chantier A des guidelines porte sur la classification d'intentions. Un pilote de **20 exemples** a été annoté par **deux annotateurs** pour vérifier la fiabilité de la taxonomie avant l'annotation à grande échelle.

- Référentiel : `data/annotations/intents.csv` — **14 codes** (13 intentions + `out_of_scope`).
- Feuille pilote : `data/annotations/pilot_20_annotation_sheet.csv` — **20 exemples**.
- Langues : **en : 8, fr : 12**.
- Annotateurs : **2** (`annotator_1_intent`, `annotator_2_intent`).
- SHA-256 de la feuille : `9f2ffdfc002259c33d7083196ad15dbe36ab97e02fe6b03666188e2ad57a251e`.

## 2. Méthode

- **Accord observé** : proportion d'exemples où les deux annotateurs ont choisi le même code.
- **Cohen's kappa** : `sklearn.metrics.cohen_kappa_score` (scikit-learn `1.9.1`).
- Formule : κ = (p_o − p_e) / (1 − p_e), où p_o est l'accord observé et p_e l'accord attendu au hasard.
- **Interprétation** : échelle de Landis & Koch (1981).

## 3. Résultats

| Indicateur | Valeur |
| --- | ---: |
| Exemples annotés | 20 |
| Annotateurs | 2 |
| Accords | 20 |
| Désaccords | 0 |
| Taux d'accord | 100,00 % |
| Cohen's kappa | 1,000 |
| Interprétation | accord presque parfait (0,81–1,00) |

### Répartition par intention

| Code | Exemples | Accords | Désaccords |
| --- | ---: | ---: | ---: |
| `account_privacy` | 1 | 1 | 0 |
| `delivery_issue` | 2 | 2 | 0 |
| `human_support` | 1 | 1 | 0 |
| `order_change_cancel` | 2 | 2 | 0 |
| `order_tracking` | 2 | 2 | 0 |
| `out_of_scope` | 1 | 1 | 0 |
| `payment_info` | 1 | 1 | 0 |
| `payment_issue` | 2 | 2 | 0 |
| `product_info` | 1 | 1 | 0 |
| `promotion_loyalty` | 1 | 1 | 0 |
| `refund_status` | 2 | 2 | 0 |
| `return_request` | 1 | 1 | 0 |
| `technical_support` | 1 | 1 | 0 |
| `warranty_claim` | 2 | 2 | 0 |
| **Total** | **20** | **20** | **0** |

## 4. Interprétation

Le kappa de **1,000** correspond à un **accord presque parfait (0,81–1,00)** au sens de Landis & Koch. Les deux annotateurs ont choisi le même code sur **20/20** exemples, soit **100,00 %** d'accord. Le seuil cible des guidelines (§5.7) est **κ ≥ 0,75** : le pilote le dépasse.

Ce résultat doit toutefois être lu avec prudence : un accord parfait sur un petit échantillon ne prouve pas que la taxonomie sera aussi fiable sur des cas réels plus variés. Il n'y a aucun désaccord à analyser, donc le pilote ne permet pas d'identifier les frontières de classes encore fragiles.

## 5. Limites

- **Taille de l'échantillon** : 20 exemples pour 14 classes, soit 1 à 2 exemples par classe. Les estimations sont instables et ne sont pas représentatives de la distribution réelle.
- **Niveau d'accord** : κ = 1,000. L'absence de désaccord empêche d'analyser les confusions entre classes.
- **Indépendance non documentée** : le CSV ne précise pas si les deux annotateurs ont travaillé indépendamment, ni leur identité. Si les annotations ont été produites ensemble ou à partir de la même référence, le kappa surestime l'accord inter-annotateurs. **Cette indépendance doit être confirmée.**
- **Échantillon équilibré par construction** : le pilote couvre volontairement chaque intention (1 à 2 exemples), ce qui diffère de la distribution réelle et influence le kappa (sensibilité à la prévalence).
- **Colonne dupliquée** : l'en-tête contient deux colonnes `ambiguous_oui_non_1` (mêmes valeurs sur toutes les lignes). Le calcul n'utilise que les colonnes `annotator_*`, mais le schéma doit être corrigé.
- **Pas de kappa par classe** : avec 1 à 2 exemples par classe, un kappa par intention n'est pas interprétable. Seul le kappa global est rapporté.
- **Exemple ambigu** : `INT-0020` est marqué ambigu (`oui`) ; les deux annotateurs sont d'accord. Les guidelines (§5.4) prévoient que les exemples ambigus ne comptent pas dans les métriques principales ; le calcul global les inclut. Une analyse de sensibilité est fournie ci-dessous.

### Sensibilité : exclusion de l'exemple ambigu

| Périmètre | Exemples | Accords | Taux | Kappa |
| --- | ---: | ---: | ---: | ---: |
| Tous les exemples | 20 | 20 | 100,00 % | 1,000 |
| Hors exemple(s) ambigu(s) | 19 | 19 | 100,00 % | 1,000 |

Le résultat est inchangé : l'exemple ambigu ne modifie pas le kappa.

## 6. Vérification des guidelines

`docs/annotation_guidelines.md` a été examiné :

- Codes de `intents.csv` présents dans les guidelines : **14/14**.
- Sections clés : frontières OK, cas ambigus OK, accord OK.
- Chaque intention possède un libellé et un exemple type ; les définitions complètes sont dans `intents.csv`, comme indiqué par les guidelines.

Aucune réécriture des guidelines n'a été nécessaire. Les libellés français de la table §5.1 sont parfois des variantes de ceux de `intents.csv` (par exemple « Modification / annulation » vs « Modification ou annulation »), mais les **codes** — identifiants canoniques — correspondent exactement.

## 7. Prochaines étapes

1. **Confirmer l'indépendance** des deux annotateurs et documenter leur identité et le protocole (aveugle, même version des guidelines).
2. **Corriger le schéma** : supprimer ou renommer la colonne dupliquée `ambiguous_oui_non_1` ; figer la version de la feuille pilote.
3. **Étendre l'échantillon** à 100–200 exemples stratifiés, en incluant des cas frontières et ambigus représentatifs de la distribution réelle.
4. **Double annotation aveugle** et calcul du kappa global et par classe ; consigner les désaccords dans `docs/reports/adjudication_log.csv`.
5. **Décider** : si κ ≥ 0,75, figer les guidelines v1.1 et lancer l'annotation complète ; sinon, réviser les définitions des classes conflictuelles et ré-annoter.
6. **Publier** ce rapport et demander la validation de l'équipe NLP/Data (ClickUp).

## 8. Reproductibilité

```bash
python scripts/calculate_kappa.py
```

Le script valide les colonnes, les valeurs manquantes et les codes d'intention, puis calcule le kappa et régénère ce rapport. Il ne modifie jamais la feuille d'annotation.
