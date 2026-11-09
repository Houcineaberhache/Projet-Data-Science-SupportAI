# Rapport de nettoyage et de normalisation du corpus

> Généré par `scripts/clean_corpus.py`. Ne pas modifier à la main.
> Aucun horodatage : le rapport est reproductible octet pour octet.

- Enregistrements en entrée : **522**
- Enregistrements en sortie : **522**
- Doublons exacts supprimés : **0**
- Quasi-doublons signalés : **0**

## 1. Volumes entrée / sortie

| Langue | Format | Entrée rec. | Entrée mots | Entrée car. | Sortie rec. | Sortie mots | Sortie car. |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| en | csv | 24 | 802 | 4 730 | 24 | 802 | 4 730 |
| en | docx | 137 | 6 312 | 37 754 | 137 | 5 922 | 35 159 |
| en | json | 35 | 1 375 | 8 006 | 35 | 1 375 | 8 006 |
| en | jsonl | 37 | 1 389 | 8 294 | 37 | 1 389 | 8 294 |
| en | pdf | 28 | 6 853 | 42 639 | 28 | 6 380 | 39 518 |
| fr | csv | 24 | 882 | 5 474 | 24 | 882 | 5 474 |
| fr | docx | 137 | 6 719 | 39 997 | 137 | 6 329 | 37 402 |
| fr | json | 35 | 1 506 | 9 231 | 35 | 1 506 | 9 231 |
| fr | jsonl | 37 | 1 525 | 9 446 | 37 | 1 525 | 9 446 |
| fr | pdf | 28 | 7 540 | 46 806 | 28 | 7 039 | 43 616 |
| **Total** | | **522** | **34 903** | **212 377** | **522** | **33 149** | **200 876** |

## 2. Compteurs par étape

| Étape | Indicateur | Valeur |
| --- | --- | ---: |
| Normalisation | Enregistrements modifiés | 0 |
| En-têtes / pieds de page | Enregistrements touchés | 60 |
| En-têtes / pieds de page | Segments supprimés | 140 |
| En-têtes / pieds de page | Caractères supprimés (segments) | 11 305 |
| Global | Delta mots entrée − sortie | 1 754 |
| Global | Delta caractères entrée − sortie | 11 501 |
| Motif | `Référence … · version … · entrée en vigueur …` | 58 |
| Motif | `Document fictif — …` (en-tête) | 58 |
| Motif | `Document fictif` / `Fictional document` (pied) | 2 |
| Motif | Préfixe `Version … Effective date` / `Entrée en vigueur` | 20 |
| Motif | Séparateur `____` | 2 |
| Reflow PDF | Enregistrements reflowés | 56 |
| Doublons | Doublons exacts supprimés | 0 |
| Doublons | Quasi-doublons signalés | 0 |
| Titres seuls | Enregistrements conservés | 17 |

## 3. Contrôles automatiques

| # | Contrôle | Résultat | Valeur |
| ---: | --- | --- | --- |
| 1 | Sans perte de mots | OK | 522 enregistrements vérifiés, 0 écart(s) |
| 2 | Aucun en-tête résiduel | OK | 0 résidu(s) |
| 3 | Espaces et Unicode | OK | 522 enregistrements, 0 problème(s) |
| 4 | Structure des titres | OK | 486/486 titres conservés |
| 5 | Volumes et parité | OK | 522 en sortie / 522 attendus, 261 FR / 261 EN, parité OK, identifiants uniques |
| 6 | Valeurs métier | OK | 522 enregistrements, 0 écart(s) |
| 7 | Déterminisme | OK | sha256 identique (09e2fc3a00dd494d…) |

## 4. Doublons exacts supprimés

Aucun.

## 5. Quasi-doublons signalés

Aucun.

## 6. Lignes fréquentes non couvertes

Aucune ligne présente dans ≥ 20 enregistrements hors motifs BOILERPLATE.

## 7. Exemples avant / après

### 1. `POL-01:en:pdf:p2` — PDF EN

- Format : `pdf` · langue : `en`

**Segments supprimés**

```text
____________________________________________________________
```

```text
Fictional document — NovaShop is an imaginary company created for the SupportAI educational
project. Prices, addresses and identifiers are invented and do not refer to any real company.
```

**Avant**

```text
- Change-of-mind return: 39 MAD shipping fee, deducted from the refund.
- Return of a faulty, wrong or damaged-on-delivery product: free, upon presentation of
photos. A product damaged in transit is handled under POL-09.
- In-store return: free, no shipping fee.
6. Procedure
1. Open a request from the customer account, under "My orders", or contact support.
2. Support checks eligibility and issues a return authorisation (RET-XXXXXX) within 24
business hours.
3. The customer drops the parcel at a relay point (definition: POL-03, section 9) or hands
the product over in store.
4. The quality team…
```

**Après**

```text
- Change-of-mind return: 39 MAD shipping fee, deducted from the refund.
- Return of a faulty, wrong or damaged-on-delivery product: free, upon presentation of photos. A product damaged in transit is handled under POL-09.
- In-store return: free, no shipping fee.
6. Procedure
1. Open a request from the customer account, under "My orders", or contact support.
2. Support checks eligibility and issues a return authorisation (RET-XXXXXX) within 24 business hours.
3. The customer drops the parcel at a relay point (definition: POL-03, section 9) or hands the product over in store.
4. The quality team…
```

### 2. `POL-02:en:pdf:p1` — PDF EN

- Format : `pdf` · langue : `en`

**Segments supprimés**

```text
Référence POL-02 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
```

```text
Version: 1.0 · Effective date: 1 September 2026
```

**Avant**

```text
Refund policy
Référence POL-02 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
Version: 1.0 · Effective date: 1 September 2026
1. General principles
NovaShop issues a refund in three situations:
1. A return accepted under the returns policy (POL-01).
2. An order cancelled before shipment (POL-08).
3. A product not delivered or delivered damaged, after the carrier investigation (POL-09).
A refund can never exceed the amount actually paid by the customer, including delivery fees
when NovaSho…
```

**Après**

```text
Refund policy
1. General principles
NovaShop issues a refund in three situations:
1. A return accepted under the returns policy (POL-01).
2. An order cancelled before shipment (POL-08).
3. A product not delivered or delivered damaged, after the carrier investigation (POL-09).
A refund can never exceed the amount actually paid by the customer, including delivery fees when NovaShop is responsible.
2. Processing times
Step | Maximum time
Request opened and validated | 24 business hours
Returned product received | 2 to 5 business days
Quality inspection | 48 hours
Refund issued | 2 business days a…
```

### 3. `POL-03:en:pdf:p1` — PDF EN

- Format : `pdf` · langue : `en`

**Segments supprimés**

```text
Référence POL-03 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
```

```text
Version: 1.0 · Effective date: 1 September 2026
```

**Avant**

```text
Shipping and delivery policy
Référence POL-03 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
Version: 1.0 · Effective date: 1 September 2026
1. Areas served
NovaShop delivers throughout Morocco through its network of logistics partners. Areas are
grouped into three categories:
Area | Main cities | Indicative time
Area A | Casablanca, Rabat, Salé, Témara, Mohammedia | 24 to 48 hours
Area B | Marrakech, Fès, Tanger, Agadir, Meknès, Oujda, Kénitra, Tétouan | 2 to 4 business
days
Area C | Oth…
```

**Après**

```text
Shipping and delivery policy
1. Areas served
NovaShop delivers throughout Morocco through its network of logistics partners. Areas are grouped into three categories:
Area | Main cities | Indicative time
Area A | Casablanca, Rabat, Salé, Témara, Mohammedia | 24 to 48 hours
Area B | Marrakech, Fès, Tanger, Agadir, Meknès, Oujda, Kénitra, Tétouan | 2 to 4 business
days
Area C | Other cities and rural areas | 3 to 6 business days
Times run from payment confirmation, not from order placement. An order placed after 16:00 or on a Sunday is processed on the next business day.
2. Delivery fees
Order va…
```

### 4. `POL-01:fr:pdf:p1` — PDF FR

- Format : `pdf` · langue : `fr`

**Segments supprimés**

```text
Référence POL-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
```

```text
Version : 1.0 · Entrée en vigueur : 1er septembre 2026 
```

**Avant**

```text
Politique de retours et d'échanges
Référence POL-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
Version : 1.0 · Entrée en vigueur : 1er septembre 2026 Périmètre : commandes passées sur
novashop.ma et en boutique NovaShop (Maroc).
1. Objet
La présente politique définit les conditions dans lesquelles un client peut retourner ou
échanger un produit acheté auprès de NovaShop. Elle s'applique à l'ensemble des catégories
vendues : smartphones, ordinateurs portables, audio, accessoires inform…
```

**Après**

```text
Politique de retours et d'échanges
Périmètre : commandes passées sur novashop.ma et en boutique NovaShop (Maroc).
1. Objet
La présente politique définit les conditions dans lesquelles un client peut retourner ou échanger un produit acheté auprès de NovaShop. Elle s'applique à l'ensemble des catégories vendues : smartphones, ordinateurs portables, audio, accessoires informatiques, montres connectées et tablettes.
2. Délai de retour
Le client dispose de 14 jours calendaires à compter de la date de réception du colis pour demander un retour. Ce délai est un choix commercial de NovaShop. Il ne pri…
```

### 5. `POL-01:fr:pdf:p2` — PDF FR

- Format : `pdf` · langue : `fr`

**Segments supprimés**

```text
____________________________________________________________
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique
SupportAI. Prix, adresses et identifiants sont inventés et ne désignent aucune entreprise
réelle.
```

**Avant**

```text
5. Frais de retour
- Retour pour changement d'avis : 39 MAD de frais de transport, déduits du remboursement.
- Retour pour produit défectueux, erroné ou endommagé à la livraison : gratuit, sur
présentation de photos. Un produit abîmé pendant le transport est traité selon POL-09.
- Retour en boutique : gratuit, sans frais de transport.
6. Procédure
1. Ouvrir une demande depuis l'espace client, rubrique « Mes commandes », ou contacter le
support.
2. Le support vérifie l'éligibilité et génère un bon de retour (RET-XXXXXX) sous 24 heures
ouvrées.
3. Le client dépose le colis dans un point relais (…
```

**Après**

```text
5. Frais de retour
- Retour pour changement d'avis : 39 MAD de frais de transport, déduits du remboursement.
- Retour pour produit défectueux, erroné ou endommagé à la livraison : gratuit, sur présentation de photos. Un produit abîmé pendant le transport est traité selon POL-09.
- Retour en boutique : gratuit, sans frais de transport.
6. Procédure
1. Ouvrir une demande depuis l'espace client, rubrique « Mes commandes », ou contacter le support.
2. Le support vérifie l'éligibilité et génère un bon de retour (RET-XXXXXX) sous 24 heures ouvrées.
3. Le client dépose le colis dans un point relais (…
```

### 6. `CAT-01:en:docx:s1` — DOCX

- Format : `docx` · langue : `en`

**Segments supprimés**

```text
Référence CAT-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
```

**Avant**

```text
Product guide — Smartphones

Référence CAT-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop

Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.

This page presents the NovaShop smartphone range, the selection criteria and the associated conditions. Prices are in MAD, including all taxes, and may change.
```

**Après**

```text
Product guide — Smartphones

This page presents the NovaShop smartphone range, the selection criteria and the associated conditions. Prices are in MAD, including all taxes, and may change.
```

### 7. `CAT-01:fr:docx:s1` — DOCX

- Format : `docx` · langue : `fr`

**Segments supprimés**

```text
Référence CAT-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
```

**Avant**

```text
Guide produits — Smartphones

Référence CAT-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop

Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.

Cette page présente la gamme de smartphones NovaShop, les critères de choix et les conditions associées. Les prix sont en MAD, toutes taxes comprises, et peuvent évoluer.
```

**Après**

```text
Guide produits — Smartphones

Cette page présente la gamme de smartphones NovaShop, les critères de choix et les conditions associées. Les prix sont en MAD, toutes taxes comprises, et peuvent évoluer.
```

### 8. `FAQ-01:en:json:FAQ-01-Q01` — FAQ

- Format : `json` · langue : `en`

**Segments supprimés**

Aucun.

**Avant**

```text
How do I place an order?

Add the items to the basket, click "Checkout", enter your address and phone number, choose the delivery method and payment method, then confirm. You immediately receive a confirmation email containing your order number in the format ORD-XXXXXX.
```

**Après**

```text
How do I place an order?

Add the items to the basket, click "Checkout", enter your address and phone number, choose the delivery method and payment method, then confirm. You immediately receive a confirmation email containing your order number in the format ORD-XXXXXX.
```

### 9. `OPS-01:en:docx:s3` — Titre seul

- Format : `docx` · langue : `en`

**Segments supprimés**

Aucun.

**Avant**

```text
2. Levels
```

**Après**

```text
2. Levels
```

### 10. `POL-01:en:pdf:p1` — Préfixe Version … Scope

- Format : `pdf` · langue : `en`

**Segments supprimés**

```text
Référence POL-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
```

```text
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
```

```text
Version: 1.0 · Effective date: 1 September 2026 
```

**Avant**

```text
Returns and exchanges policy
Référence POL-01 · version 1.0 · entrée en vigueur 2026-09-01 · NovaShop
Document fictif — NovaShop est une société imaginaire créée pour le projet pédagogique SupportAI.
Version: 1.0 · Effective date: 1 September 2026 Scope: orders placed on novashop.ma and in
NovaShop stores (Morocco).
1. Purpose
This policy defines the conditions under which a customer may return or exchange a product
purchased from NovaShop. It applies to every category sold: smartphones, laptops, audio,
computer accessories, smartwatches and tablets.
2. Return window
The customer has 14 calend…
```

**Après**

```text
Returns and exchanges policy
Scope: orders placed on novashop.ma and in NovaShop stores (Morocco).
1. Purpose
This policy defines the conditions under which a customer may return or exchange a product purchased from NovaShop. It applies to every category sold: smartphones, laptops, audio, computer accessories, smartwatches and tablets.
2. Return window
The customer has 14 calendar days from the date of delivery to request a return. This period is a commercial choice made by NovaShop. It does not affect the legal guarantees described in the warranty policy (POL-04).
The delivery date recorded b…
```
