---
doc_id: OPS-01
title: Matrice d'escalade et niveaux de support
category: internal_operations
doc_type: sop
language: fr
version: 1.0
effective_date: 2026-09-01
owner: NovaShop
sensitivity: internal
source_type: synthetic
---

# Matrice d'escalade et niveaux de support

**Document interne — non communicable au client.**

## 1. Rôle de ce document

Cette matrice définit qui traite quel type de demande, dans quel délai, et selon quels critères un dossier change de niveau. Elle sert de référence à l'assistant SupportAI pour décider quand proposer un transfert vers un agent humain.

## 2. Niveaux

### N1 — Conseiller support

Traite : information produit, suivi de commande, conditions de retour, délais de livraison, questions de paiement courantes, création de dossier SAV.

Délai cible : réponse immédiate, résolution sous 24 heures ouvrées.

### N2 — Spécialiste

Traite : litiges de remboursement, colis perdus, désaccords sur un diagnostic SAV, gestes commerciaux jusqu'à 500 MAD, incidents transporteur.

Délai cible : 48 heures ouvrées.

### N3 — Responsable support

Traite : gestes commerciaux supérieurs à 500 MAD, menaces juridiques, réclamations formelles, incidents médiatiques, suspicions de fraude organisée.

Délai cible : 5 jours ouvrés.

## 3. Critères d'escalade automatique

| Critère | Niveau cible |
| --- | --- |
| Montant en jeu > 3 000 MAD | N2 |
| Client insatisfait après 2 réponses | N2 |
| Délai de résolution dépassé de 48 h | N2 puis N3 |
| Mention d'avocat, de tribunal ou d'association de consommateurs | N3 |
| Suspicion de fraude ou de faux signalement | N3 |
| Données personnelles compromises | N3 + DPO |
| Demande hors périmètre du support | N1 → redirection |

## 4. Transfert vers un agent humain

L'assistant SupportAI doit proposer un transfert humain, sans attendre que le client le demande, dans les cas suivants :

1. Le client exprime une détresse ou une urgence (colis volé, données compromises).
2. La demande porte sur un montant supérieur à 3 000 MAD.
3. Le client conteste une décision déjà communiquée.
4. La question sort du périmètre documentaire et aucune source fiable n'est trouvée.
5. Le client demande explicitement une personne.
6. Le sujet est juridique, médical ou lié à la sécurité.

## 5. Règles de traçabilité

Chaque escalade doit contenir : identifiant de commande, résumé du problème en 2 lignes, actions déjà tentées, niveau cible, motif d'escalade. Un dossier sans ces éléments est renvoyé au niveau précédent.

## 6. Indicateurs suivis

- Taux d'escalade par niveau.
- Délai moyen de première réponse.
- Taux de résolution au premier contact.
- Taux de réouverture sous 7 jours.
- Satisfaction après escalade.

## 7. Articulation avec SupportAI

L'assistant peut résoudre les demandes N1 documentées. Il ne doit jamais :

- promettre un remboursement hors politique ;
- confirmer une décision de garantie avant diagnostic ;
- divulguer des informations d'une autre commande ;
- prendre un engagement de délai non confirmé par le transporteur.

En cas de doute, l'assistant cite la source documentaire et propose le transfert humain.
