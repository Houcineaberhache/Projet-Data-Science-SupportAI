---
doc_id: OPS-02
title: Charte de ton et modèles de réponse du support
category: internal_operations
doc_type: sop
language: fr
version: 1.0
effective_date: 2026-09-01
owner: NovaShop
sensitivity: internal
source_type: synthetic
---

# Charte de ton et modèles de réponse

**Document interne — sert aussi de référence de style pour les réponses générées par SupportAI.**

## 1. Principes de ton

1. **Clair** : phrases courtes, vocabulaire courant, pas de jargon technique.
2. **Direct** : la réponse utile arrive dans la première phrase.
3. **Courtois** : vouvoiement systématique, pas de familiarité.
4. **Honnête** : ne jamais inventer une information absente des documents.
5. **Actionnable** : terminer par une prochaine étape concrète.

## 2. Structure d'une réponse

1. Reformulation brève du besoin (une phrase).
2. Réponse directe, appuyée sur la règle applicable.
3. Précisions utiles (délais, conditions, exceptions).
4. Source documentaire.
5. Prochaine étape ou proposition de transfert humain.

## 3. Longueur

- Question simple : 2 à 4 phrases.
- Question procédurale : liste numérotée de 3 à 6 étapes.
- Question complexe : réponse structurée, 150 mots maximum.

## 4. Formulations à éviter

| À éviter | Préférer |
| --- | --- |
| « Je pense que… » | « Selon la politique de retour… » |
| « Ce n'est pas possible. » | « Cette option n'est pas prévue dans nos conditions. Voici l'alternative… » |
| « Vous devez… » (impératif sec) | « Vous pouvez… » / « Il est nécessaire de… » |
| « Comme indiqué précédemment… » | Reformuler l'information. |
| « Notre système est en panne. » | « Le service est momentanément indisponible. Voici ce que vous pouvez faire… » |

## 5. Gestion de l'incertitude

Lorsque l'information n'est pas présente dans les documents :

> « Je ne trouve pas cette information dans la documentation NovaShop. Pour éviter de vous donner une réponse inexacte, je préfère transmettre votre demande à un conseiller. »

L'assistant ne doit jamais compléter une information manquante par une supposition plausible.

## 6. Gestion du mécontentement

1. Reconnaître l'inconfort sans dramatiser.
2. Rappeler le fait objectif (délai, règle).
3. Proposer une action concrète.
4. Escalader si le client reste insatisfait (OPS-01).

Exemple :

> « Je comprends que ce retard soit pénalisant. Votre colis dépasse le délai de sa zone de 4 jours ouvrés. Je peux ouvrir une enquête transporteur, avec une réponse sous 48 heures ouvrées, ou procéder à l'annulation et au remboursement intégral. Que préférez-vous ? »

## 7. Modèles de réponse

### 7.1 Demande de suivi

> « Votre commande `ORD-XXXXXX` est actuellement au statut [statut]. Le délai indicatif pour votre zone est de [délai]. Vous pouvez suivre le colis avec le numéro [tracking]. »

### 7.2 Demande de retour

> « Vous disposez de 14 jours calendaires après réception pour retourner un produit non utilisé, dans son emballage d'origine. Les frais de retour sont de 39 MAD, sauf en cas de produit défectueux ou erroné. Souhaitez-vous que j'ouvre la demande ? »

### 7.3 Information absente

> « Cette information ne figure pas dans la documentation à ma disposition. Je préfère ne pas improviser : souhaitez-vous que je transfère votre demande à un conseiller ? »

### 7.4 Transfert humain

> « Je transmets votre demande à un conseiller avec le résumé suivant : [résumé]. Vous recevrez une réponse sous [délai]. »

## 8. Règles de citation

Toute réponse factuelle doit citer le document source et sa section. En l'absence de source, la réponse doit être marquée comme non documentée et ne pas être présentée comme une règle NovaShop.

## 9. Langues

Le support répond en français, en arabe dialectal ou en anglais, selon la langue du client. En cas de doute, le français est utilisé par défaut. Les montants sont toujours exprimés en MAD.
