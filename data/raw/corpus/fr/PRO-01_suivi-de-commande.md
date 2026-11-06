---
doc_id: PRO-01
title: Procédure de suivi de commande
category: procedures
doc_type: procedure
language: fr
version: 1.0
effective_date: 2026-09-01
owner: NovaShop
sensitivity: public
source_type: synthetic
---

# Procédure — Suivre sa commande

**Public :** client · **Durée :** 2 minutes

## 1. Où trouver le numéro de commande

Le numéro de commande figure dans le courriel de confirmation, au format `ORD-` suivi de 6 chiffres (exemple : `ORD-100234`). Il est également visible dans l'espace client, rubrique « Mes commandes ».

## 2. Suivi en ligne

1. Se connecter à novashop.ma.
2. Ouvrir « Mon compte » puis « Mes commandes ».
3. Cliquer sur la commande concernée.
4. Consulter la timeline de suivi et le numéro de tracking du transporteur.

## 3. Suivi sans compte

Une commande passée en invité peut être suivie depuis la page « Suivre ma commande », en saisissant le numéro de commande **et** l'adresse courriel utilisée lors de l'achat.

## 4. Comprendre les statuts

| Statut affiché | Signification |
| --- | --- |
| En attente de paiement | Commande créée, paiement non confirmé |
| Paiement confirmé | Paiement validé, préparation à venir |
| En préparation | Colis en cours de préparation en entrepôt |
| Expédiée | Colis remis au transporteur, suivi actif |
| En cours de livraison | Colis en tournée de livraison |
| Livrée | Colis remis au client |
| Retour en cours | Colis en retour vers l'entrepôt |
| Annulée | Commande annulée, remboursement selon POL-02 |

Le référentiel complet des statuts est décrit dans OPS-03.

## 5. Suivi bloqué

Si le statut ne change pas pendant plus de **3 jours ouvrés** en phase « Expédiée », le client peut :

1. vérifier le suivi sur le site du transporteur avec le numéro de tracking ;
2. contacter le support avec le numéro de commande ;
3. demander l'ouverture d'une enquête si le colis n'est pas localisé.

## 6. Numéro de suivi introuvable

Le numéro de suivi est généré lors de la remise au transporteur. Il peut apparaître avec un décalage de quelques heures. S'il est absent 24 heures après le statut « Expédiée », le support régénère la notification.

## 7. Modification d'adresse en cours de livraison

Après expédition, NovaShop ne peut plus modifier l'adresse. Le client doit contacter directement le transporteur avec le numéro de suivi. Voir POL-08, section 5.

## 8. Commande livrée mais non reçue

Il s'agit d'un incident, traité par POL-09, section 4. Le client ne doit pas ouvrir de nouveau litige de paiement avant la fin de l'enquête transporteur.

## 9. Délais à connaître

| Zone | Délai indicatif |
| --- | --- |
| A (Casablanca, Rabat) | 24 à 48 h |
| B (grandes villes) | 2 à 4 jours ouvrés |
| C (autres zones) | 3 à 6 jours ouvrés |

Le détail des zones et des frais figure dans POL-03.
