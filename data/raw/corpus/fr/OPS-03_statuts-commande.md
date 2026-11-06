---
doc_id: OPS-03
title: Référentiel des statuts de commande
category: internal_operations
doc_type: sop
language: fr
version: 1.0
effective_date: 2026-09-01
owner: NovaShop
sensitivity: internal
source_type: synthetic
---

# Référentiel des statuts de commande

**Document interne — référence pour le support et pour la simulation de suivi.**

## 1. Cycle de vie d'une commande

```
créée → paiement_en_attente → paiement_confirmé → en_préparation
      → expédiée → en_livraison → livrée
                              ↘ retour_en_cours → retour_reçu → remboursée
      ↘ annulée
```

## 2. Table des statuts

| Code technique | Libellé client | Description | Actions possibles |
| --- | --- | --- | --- |
| `created` | Commande enregistrée | Commande créée, paiement non initié | Payer, annuler |
| `pending_payment` | En attente de paiement | Paiement non confirmé | Payer, annuler |
| `paid` | Paiement confirmé | Paiement validé, préparation à venir | Annuler, modifier |
| `preparing` | En préparation | Colis en cours de préparation | Annuler si non scellé |
| `shipped` | Expédiée | Colis remis au transporteur | Suivre, demander un retour |
| `out_for_delivery` | En cours de livraison | Colis en tournée | Suivre |
| `delivered` | Livrée | Colis remis | Retour, SAV, facture |
| `delivery_failed` | Tentative échouée | Client absent ou injoignable | Reprogrammer |
| `return_pending` | Retour demandé | Bon de retour émis | Déposer le colis |
| `return_in_transit` | Retour en cours | Colis en retour | Attendre le contrôle |
| `return_received` | Retour reçu | Colis reçu à l'entrepôt | Attendre le contrôle qualité |
| `refunded` | Remboursée | Remboursement émis | Attendre le crédit bancaire |
| `cancelled` | Annulée | Commande annulée | Remboursement selon POL-02 |
| `on_hold` | En vérification | Contrôle antifraude | Contacter le support |

## 3. Règles de transition

- `created → pending_payment` : dès l'initialisation du paiement.
- `pending_payment → paid` : confirmation du prestataire de paiement.
- `paid → preparing` : prise en charge par l'entrepôt, sous 24 h ouvrées.
- `preparing → shipped` : remise au transporteur, génération du tracking.
- `shipped → delivered` : confirmation de livraison par le transporteur.
- `delivered → return_pending` : demande de retour validée (POL-01).
- Toute transition est horodatée et journalisée.

## 4. Délais d'alerte

| Statut | Seuil d'alerte |
| --- | --- |
| `paid` | 24 h sans passage à `preparing` |
| `preparing` | 48 h sans passage à `shipped` |
| `shipped` | 3 jours ouvrés sans mise à jour |
| `return_received` | 48 h sans contrôle qualité |
| `refunded` | 8 jours ouvrés sans confirmation bancaire |

Un dépassement de seuil crée automatiquement une tâche de supervision.

## 5. Correspondance avec les données de commande

Chaque commande possède : `order_id` (`ORD-` + 6 chiffres), `customer_id` (`CUST-` + 4 chiffres), `product_id` (`PROD-` ou référence catalogue), `status`, `created_at`, `estimated_delivery`, `tracking_number`.

## 6. Cas particuliers

- **Commande multi-colis** : le statut global est celui du colis le moins avancé. Le détail par colis est disponible dans l'espace client.
- **Commande annulée après paiement** : le statut passe à `cancelled` puis à `refunded` après émission du remboursement.
- **Commande contestée par la banque** : passage en `on_hold` jusqu'à résolution du litige.

## 7. Usage par SupportAI

L'assistant peut lire le statut courant et l'expliquer. Il ne peut pas modifier un statut. Toute demande de modification est transférée à un agent (OPS-01).
