# RAG evaluation set — human review sheet

> Review by Aya. The 25 answerable questions are sampled with `SEED = 42`; all 14 out-of-corpus questions are included. No timestamp is stored.

For each question, check three things:

1. The reference answer is fully supported by the gold passages and uses no outside knowledge.
2. Every number in the answer appears in a gold passage.
3. The question sounds like a real NovaShop customer question and does not copy a section title.

After review, set `reviewed_by` in `data/annotations/rag_eval.jsonl` (for example `"aya"`). Do not edit the gold passages by hand: rerun `python scripts/build_rag_eval.py build`.

## RET-0004 — semantic / fr

**Question:** Combien de temps ai-je pour changé d'avis après avoir reçu mon colis ?

**Reference answer:** Vous disposez de 14 jours calendaires à compter de la réception du colis. Le jour de réception compte comme jour 0 et, si le 14e jour tombe un dimanche ou un jour férié, le délai est prolongé au premier jour ouvrable suivant.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 2. Délai de retour ». Faute légère volontaire (style §4). Question chiffrée.

**Gold passages:**

### `POL-01#c2` — 2. Délai de retour

```text
Le client dispose de **14 jours calendaires** à compter de la date de réception du colis pour demander un retour. Ce délai est un choix commercial de NovaShop. Il ne prive pas le client des garanties légales décrites dans la politique de garantie (POL-04). Le jour de la réception, tel qu'enregistré par le transporteur, compte comme jour 0. Si le 14e jour tombe un dimanche ou un jour férié, le délai est prolongé jusqu'au premier jour ouvrable suivant.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0005 — procedural / en

**Question:** I've already sent my return parcel — what happen after the quality team receives it?

**Reference answer:** The quality team inspects the product within 48 hours of receipt. The refund or exchange is then initiated under the refund policy (POL-02).

**Note:** Faute légère volontaire (style §4). Question chiffrée.

**Gold passages:**

### `POL-01#c6` — 6. Procedure

```text
1. Open a request from the customer account, under "My orders", or contact support.
2. Support checks eligibility and issues a return authorisation (RET-XXXXXX) within 24 business hours.
3. The customer drops the parcel at a relay point (definition: POL-03, section 9) or hands the product over in store.
4. The quality team inspects the product within 48 hours of receipt.
5. The refund or exchange is initiated according to the refund policy (POL-02).
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0012 — lexical / fr

**Question:** Puis-je récupérer ma commande dans une boutique et combien de temps ai-je pour le faire ?

**Reference answer:** Le retrait est gratuit dans les boutiques de Casablanca, Rabat et Marrakech. Vous disposez de 7 jours pour récupérer votre commande après réception du code de retrait.

**Note:** Question chiffrée.

**Gold passages:**

### `POL-03#c5` — 5. Retrait en magasin

```text
Le retrait gratuit est disponible dans les boutiques de Casablanca, Rabat et Marrakech. Le client reçoit un code de retrait et dispose de **7 jours** pour récupérer sa commande. Passé ce délai, la commande est remboursée ou réexpédiée à la demande du client.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0014 — semantic / fr

**Question:** Combien de temps mon colis peut-il rester disponible chez le commerçant partenaire ?

**Reference answer:** Le colis est conservé 5 jours ouvrés à compter de sa mise à disposition. Passé ce délai, il retourne à l'entrepôt et le client est contacté.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 9. Points relais ». Question chiffrée.

**Gold passages:**

### `POL-03#c9` — 9. Points relais

```text
Le **point relais** est un commerce partenaire (tabac, supérette, boutique de quartier) conventionné par NovaShop pour la remise et le dépôt des colis. Il permet de livrer un client absent de son domicile et de déposer un retour sans se rendre dans une boutique NovaShop.

- Le client choisit son point relais au moment de la commande, parmi ceux proposés pour sa ville.
- Le colis est conservé **5 jours ouvrés** à compter de sa mise à disposition.
- Le retrait se fait sur présentation du numéro de commande et d'une pièce d'identité.
- Les colis dépassant 20 kg ou 100 cm de côté ne sont pas acceptés en point relais.
- Passé le délai de conservation, le colis retourne à l'entrepôt et le client est contacté dans les conditions de la section 4.

Le point relais est également le mode de dépôt d'un retour décrit dans POL-01, section 6, et dans PRO-02, section 6.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0015 — procedural / en

**Question:** My parcel is late — how long after the maximum delay can I asked for an investigation?

**Reference answer:** A parcel is considered late when the maximum time for its area has been exceeded by 3 business days. You can then request a carrier investigation, answered within 48 hours.

**Note:** Faute légère volontaire (style §4). Question chiffrée.

**Gold passages:**

### `POL-03#c6` — 6. Delivery delay

```text
A parcel is considered late when the maximum time for its area has been exceeded by **3 business days**. The customer may then:

1. request a carrier investigation (answer within 48 hours);
2. cancel and obtain a full refund if the parcel cannot be located;
3. wait for delivery with a 50 MAD store credit as compensation.

In case of delay caused by exceptional circumstances (strike, severe weather, force majeure), NovaShop informs the customer and offers a new deadline or a refund, without penalty.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0018 — lexical / fr

**Question:** Combien de temps prend une réparation en atelier partenaire ?

**Reference answer:** Une réparation en atelier partenaire prend 7 à 14 jours ouvrés. Si elle dépasse 21 jours ouvrés, le client peut demander un remplacement ou un remboursement intégral.

**Note:** Question chiffrée.

**Gold passages:**

### `POL-04#c6` — 6. Délais de réparation

```text
| Situation | Délai indicatif |
| --- | --- |
| Accessoire remplaçable en stock | 48 heures |
| Réparation en atelier partenaire | 7 à 14 jours ouvrés |
| Retour fabricant | 14 à 21 jours ouvrés |

Si la réparation dépasse 21 jours ouvrés, le client peut demander un remplacement ou un remboursement intégral.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0028 — lexical / fr

**Question:** Quel délai prévoir lorsqu'un appareil doit repartir en usine ?

**Reference answer:** Un retour fabricant prend 14 à 21 jours ouvrés. Au-delà de 21 jours ouvrés, vous pouvez demander un remplacement ou un remboursement.

**Note:** Question chiffrée.

**Gold passages:**

### `FAQ-05#c5` — Combien de temps prend une réparation ?

```text
48 heures pour un accessoire disponible en stock, 7 à 14 jours ouvrés en atelier partenaire, 14 à 21 jours ouvrés en cas de retour fabricant. Au-delà de 21 jours ouvrés, vous pouvez demander un remplacement ou un remboursement.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0029 — semantic / fr

**Question:** Est-ce possible de confier mon appareil à un réparateur indépendant sans annuler mes droits ?

**Reference answer:** Une réparation par un tiers non agréé met fin à la garantie commerciale NovaShop pour le dommage concerné. Les réparations hors réseau agréé sont donc déconseillées pendant la période de garantie.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « Puis-je faire réparer mon produit ailleurs sans perdre la garantie ? ».

**Gold passages:**

### `FAQ-05#c9` — Puis-je faire réparer mon produit ailleurs sans perdre la garantie ?

```text
Une réparation par un tiers non agréé met fin à la garantie commerciale NovaShop pour le dommage concerné. Les réparations hors réseau agréé sont donc déconseillées pendant la période de garantie.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0030 — procedural / en

**Question:** I lost my receipt — can I still proof that the product is under warranty?

**Reference answer:** The order number or the account history serves as proof of purchase. Contact support to obtain a duplicate invoice.

**Note:** Faute légère volontaire (style §4).

**Gold passages:**

### `FAQ-05#c11` — What should I do if I lose my invoice?

```text
The order number or the account history serves as proof of purchase. Contact support to obtain a duplicate invoice.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0032 — semantic / fr

**Question:** Je me suis trompé dans mon panier, puis-je encore le corriger une fois validé ?

**Reference answer:** Oui, tant que la commande n'a pas été remise au transporteur. Depuis « Mes commandes », utilisez le bouton « Modifier » ou contactez le support ; après expédition, seule une annulation avec retour est possible.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « Puis-je modifier ma commande après validation ? ».

**Gold passages:**

### `FAQ-01#c4` — Puis-je modifier ma commande après validation ?

```text
Oui, tant que la commande n'a pas été remise au transporteur. Depuis « Mes commandes », utilisez le bouton « Modifier » ou contactez le support. Après expédition, seule une annulation avec retour est possible. Voir POL-08.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0036 — semantic / fr

**Question:** Je ne serai pas chez moi à l'arrivé du transporteur, que va-t-il se passer ?

**Reference answer:** Le transporteur effectue une seconde tentative. Après deux échecs, le colis retourne à l'entrepôt et le client choisit entre une réexpédition à 39 MAD et un remboursement, sans remboursement des frais initiaux.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « Que se passe-t-il si je suis absent lors de la livraison ? ». Faute légère volontaire (style §4). Question chiffrée. Réponse répartie sur 2 chunks.

**Gold passages:**

### `FAQ-02#c5` — Que se passe-t-il si je suis absent lors de la livraison ?

```text
Le transporteur effectue une seconde tentative. Après deux échecs, le colis retourne à l'entrepôt. Le client est contacté pour choisir entre une réexpédition (39 MAD) et un remboursement, les frais de livraison initiaux n'étant pas remboursés.
```

### `POL-03#c4` — 4. Livraison à domicile

```text
Le transporteur contacte le client par téléphone avant la livraison. Le client doit être joignable et présenter une pièce d'identité pour les commandes supérieures à 3 000 MAD.

Après **deux tentatives infructueuses**, le colis est retourné à l'entrepôt. Le client est alors contacté pour choisir entre une nouvelle expédition (frais de 39 MAD) et un remboursement (frais de livraison initiaux non remboursés).
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0055 — lexical / fr

**Question:** Jusqu'à quand puis-je annuler ma commande avant l'expédition ?

**Reference answer:** Une commande peut être annulée tant qu'elle n'est pas remise au transporteur : 2 heures maximum après confirmation pour une commande passée en journée, ou jusqu'à 22h00 le jour même pour une commande passée avant 16h00. L'annulation est immédiate en attente de paiement, possible avant préparation après paiement confirmé, et possible en préparation si le colis n'est pas scellé.

**Note:** Question chiffrée. Réponse répartie sur 2 chunks.

**Gold passages:**

### `POL-08#c1` — 1. Délai utile

```text
**Version :** 1.0 · **Entrée en vigueur :** 1er septembre 2026

Une commande peut être annulée ou modifiée **tant qu'elle n'est pas remise au transporteur**. En pratique, la fenêtre est de :

- 2 heures maximum après la confirmation pour les commandes passées en journée ;
- jusqu'à 22h00 le jour même pour les commandes passées avant 16h00 ;
- aucune modification possible après l'envoi du courriel « Commande expédiée ».
```

### `POL-08#c2` — 2. Statuts permettant l'annulation

```text
| Statut de commande | Annulation possible |
| --- | --- |
| En attente de paiement | Oui, immédiate |
| Paiement confirmé | Oui, avant préparation |
| En préparation | Oui, si le colis n'est pas scellé |
| Expédiée | Non — utiliser le retour (POL-01) |
| Livrée | Non — utiliser le retour (POL-01) |
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0065 — semantic / en

**Question:** Which models comes without a charger in the box?

**Reference answer:** The charger is not included with the Lite and X5 models. The X5 Pro and Max do include a charger.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 3. Box contents ». Faute légère volontaire (style §4). Question chiffrée.

**Gold passages:**

### `CAT-01#c3` — 3. Box contents

```text
Each smartphone is supplied with: the device, a USB-C cable, a SIM ejector tool and documentation. The power adapter is not included on the Lite and X5 models, in line with the manufacturer's policy.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0070 — procedural / fr

**Question:** Puis-je installer d'avantage de mémoire après l'achat ?

**Reference answer:** La RAM est soudée sur l'Air 14 et l'Ultra 13, donc non extensible. Le SSD est remplaçable sur le Pro 15 et l'Essential 15.

**Note:** Faute légère volontaire (style §4). Question chiffrée.

**Gold passages:**

### `CAT-02#c5` — 5. Extension et entretien

```text
- RAM soudée sur Air 14 et Ultra 13 : non extensible.
- SSD remplaçable sur Pro 15 et Essential 15.
- Nettoyage des ventilateurs recommandé tous les 12 mois en environnement poussiéreux.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0072 — semantic / fr

**Question:** Combien de temps tiennent mes écouteurs avant de devoir les recharger ?

**Reference answer:** Les NovaBuds Pro offrent 8 heures d'écoute, plus 24 heures avec le boîtier. Les NovaBuds Lite offrent 6 heures, plus 18 heures avec le boîtier.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 1. Gammes disponibles ». Question chiffrée.

**Gold passages:**

### `CAT-03#c1` — 1. Gammes disponibles

```text
| Référence | Modèle | Type | Autonomie | Prix | Garantie |
| --- | --- | --- | --- | --- | --- |
| AU-301 | NovaSound ANC Over-Ear | Casque circum-aural Bluetooth | 30 h (ANC actif) | 899 MAD | 12 mois |
| AU-302 | NovaBuds Pro | Écouteurs intra-auriculaires | 8 h + 24 h boîtier | 449 MAD | 12 mois |
| AU-303 | NovaBuds Lite | Écouteurs intra-auriculaires | 6 h + 18 h boîtier | 199 MAD | 12 mois |
| AU-304 | NovaSound Mini Speaker | Enceinte portable | 12 h | 349 MAD | 12 mois |
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0076 — semantic / fr

**Question:** Mon ordinateur n'a pas de port USB-C, puis-je quand même utiliser la souris sans fil ?

**Reference answer:** Oui, la souris AC-402 fonctionne avec Windows, macOS, Linux et certains appareils Android disposant d'un port USB-A. Elle se connecte via son récepteur USB.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 2. Compatibilité ». Question chiffrée.

**Gold passages:**

### `CAT-04#c2` — 2. Compatibilité

```text
- **AC-401** : smartphones, tablettes et ordinateurs compatibles USB-C Power Delivery. Charge jusqu'à 65 W.
- **AC-402** : Windows, macOS, Linux et certains appareils Android disposant d'un port USB-A.
- **AC-403** : connexion filaire USB, compatible Windows, macOS et Linux. Disposition AZERTY.
- **AC-404** : nécessite un port USB-C avec DisplayPort Alt Mode pour la sortie vidéo.
- **AC-406** : charge simultanée de deux appareils, sortie maximale 20 W par port.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0078 — procedural / fr

**Question:** Que faire avant de transporter mon ordinateur avec le hub branché ?

**Reference answer:** Débranchez le hub avant de transporter l'ordinateur. Ne démontez pas le chargeur et n'exposez pas la batterie externe à plus de 40 °C.

**Note:** Question chiffrée.

**Gold passages:**

### `CAT-04#c3` — 3. Précautions d'usage

```text
- Utiliser un câble certifié pour la charge rapide ; un câble non certifié limite la puissance.
- Ne pas exposer une batterie externe à une température supérieure à 40 °C.
- Débrancher le hub avant de transporter l'ordinateur.
- Ne pas démonter un chargeur : risque d'électrocution et perte de garantie.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0082 — procedural / fr

**Question:** Comment changer le bracelet de ma montre ?

**Reference answer:** Oui, les bracelets sont standard : 20 mm, ou 22 mm sur la WR-503.

**Note:** Question chiffrée.

**Gold passages:**

### `CAT-05#c7` — 7. Questions fréquentes

```text
**Puis-je nager avec la NovaWatch SE ?** Elle résiste aux éclaboussures, mais la natation n'est pas recommandée (3 ATM).

**Le GPS fonctionne-t-il sans téléphone ?** Oui sur WR-501. Les autres modèles utilisent le GPS du téléphone.

**Puis-je changer le bracelet ?** Oui, bracelets standard 20 mm (22 mm sur WR-503).

**La montre est-elle compatible avec deux téléphones ?** Non, un seul téléphone appairé à la fois.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0087 — lexical / en

**Question:** What are the opening hours of the Casablanca store?

**Reference answer:** The Casablanca store is open Monday to Saturday, 10:00 to 20:00. It is closed on Sundays and national public holidays.

**Note:** Question chiffrée.

**Gold passages:**

### `OPS-04#c1` — 1. Store network

```text
| City | Address (fictional) | Phone (fictional) | Hours |
| --- | --- | --- | --- |
| Casablanca | 42, boulevard Zerktouni, Maârif | +212 5 22 00 00 01 | Mon–Sat 10:00–20:00 |
| Rabat | 18, avenue Hassan II, Agdal | +212 5 37 00 00 02 | Mon–Sat 10:00–20:00 |
| Marrakech | 7, avenue Mohammed VI, Guéliz | +212 5 24 00 00 03 | Mon–Sat 10:00–20:00 |

Stores are closed on Sundays and national public holidays.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0095 — lexical / en

**Question:** How long is my account data kept after I stop using it?

**Reference answer:** Account data is kept for the life of the account, then 3 years after the last login. Invoices are kept for 10 years and support records for 2 years.

**Note:** Question chiffrée.

**Gold passages:**

### `FAQ-07#c6` — How long is my data kept?

```text
Account data is kept for the lifetime of the account, then 3 years after the last login. Invoices are kept for 10 years. Support records are kept for 2 years.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0109 — semantic / fr

**Question:** Que puis-je faire si je veux consulter ou corriger ce que vous savez sur moi ?

**Reference answer:** Vous disposez d'un droit d'accès, de rectification, d'opposition et d'effacement dans les limites des obligations légales. Une demande est traitée sous 30 jours et une pièce d'identité peut être demandée.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 6. Droits des personnes ». Question chiffrée.

**Gold passages:**

### `POL-06#c6` — 6. Droits des personnes

```text
Conformément à la loi marocaine n° 09-08 relative à la protection des personnes physiques à l'égard du traitement des données à caractère personnel, le client dispose des droits suivants :

- droit d'accès à ses données ;
- droit de rectification ;
- droit d'opposition pour motif légitime ;
- droit à l'effacement, dans les limites des obligations légales de conservation ;
- droit de retirer son consentement à tout moment pour le marketing.

Une demande est traitée sous **30 jours**. Une pièce d'identité peut être demandée pour vérifier l'identité du demandeur.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0113 — semantic / fr

**Question:** Le statut reste identique depuis un moment, quelles options s'offrent à moi ?

**Reference answer:** Si le statut ne change pas pendant plus de 3 jours ouvrés en phase « Expédiée », vérifiez le suivi chez le transporteur, contactez le support avec le numéro de commande, puis demandez une enquête si le colis n'est pas localisé. L'enquête transporteur répond sous 48 heures ouvrées.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 5. Suivi bloqué ». Question chiffrée. Réponse répartie sur 2 chunks.

**Gold passages:**

### `PRO-01#c5` — 5. Suivi bloqué

```text
Si le statut ne change pas pendant plus de **3 jours ouvrés** en phase « Expédiée », le client peut :

1. vérifier le suivi sur le site du transporteur avec le numéro de tracking ;
2. contacter le support avec le numéro de commande ;
3. demander l'ouverture d'une enquête si le colis n'est pas localisé.
```

### `POL-09#c4` — 4. Colis non reçu

```text
Un colis est déclaré non reçu lorsque :

- le suivi indique « livré » mais le client n'a rien reçu ;
- le suivi est bloqué depuis plus de 5 jours ouvrés ;
- le transporteur a retourné le colis à l'entrepôt.

Le support ouvre alors une enquête transporteur. La réponse intervient sous **48 heures ouvrées**. Trois issues sont possibles :

| Résultat de l'enquête | Solution proposée |
| --- | --- |
| Colis retrouvé | Réexpédition immédiate, frais offerts |
| Colis perdu, responsabilité transporteur | Remplacement ou remboursement intégral |
| Colis livré à une autre adresse par erreur du client | Réexpédition facturée 39 MAD |
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0118 — procedural / en

**Question:** I am not satisfied with the answer — how do I file a formal complaint and when will I hear back?

**Reference answer:** Send a formal complaint by email with the subject “COMPLAINT”. A written response is provided within 10 business days.

**Note:** Question chiffrée.

**Gold passages:**

### `PRO-04#c9` — 9. Formal complaint

```text
If the customer is not satisfied with the answer, they may file a formal complaint by email with the subject "COMPLAINT". A written answer is provided within **10 business days**. See OPS-05.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0123 — lexical / fr

**Question:** Quel est le capital social de NovaShop SARL ?

**Reference answer:** Le capital social de NovaShop SARL est de 500 000 MAD. La société a son siège au 42, boulevard Zerktouni, Maârif, Casablanca.

**Note:** Question chiffrée.

**Gold passages:**

### `REG-04#c1` — 1. Éditeur du site

```text
**Document de démonstration. NovaShop est une société fictive créée pour un projet pédagogique.**

| Information | Valeur (fictive) |
| --- | --- |
| Raison sociale | NovaShop SARL |
| Forme juridique | Société à responsabilité limitée |
| Siège social | 42, boulevard Zerktouni, Maârif, Casablanca, Maroc |
| Capital social | 500 000 MAD |
| ICE | 000000000000000 (valeur de démonstration) |
| RC | Casablanca 000000 (valeur de démonstration) |
| Patente | 00000000 (valeur de démonstration) |
| Courriel | `contact@novashop.ma` |
| Téléphone | +212 5 22 00 00 00 (fictif) |
| Directeur de publication | Direction NovaShop (fictif) |

Ces identifiants sont volontairement neutres : ils ne correspondent à aucune entreprise réelle.
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0124 — semantic / fr

**Question:** Qui héberge le site novashop.ma ?

**Reference answer:** Le site est hébergé par NovaHost SARL, dont l'adresse est à Casablanca, au Maroc. Son téléphone est le +212 5 22 00 00 09.

**Note:** Question sémantique : aucun mot de 5 lettres ou plus du titre « 2. Hébergement ». Question chiffrée.

**Gold passages:**

### `REG-04#c2` — 2. Hébergement

```text
| Information | Valeur (fictive) |
| --- | --- |
| Hébergeur | NovaHost SARL (fictif) |
| Adresse | Casablanca, Maroc |
| Téléphone | +212 5 22 00 00 09 (fictif) |
```

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0127 — out_of_corpus / fr

**Question:** Proposez-vous un service de reprise pour mon ancien téléphone ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : aucun service de reprise ou de rachat n'est décrit dans les documents client. Vérification grep : « reprise » n'apparaît que dans « entreprise ».

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0128 — out_of_corpus / fr

**Question:** Puis-je acheter une extension de garantie de 24 mois ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : les durées de garantie sont fixées par catégorie dans POL-04 et FAQ-05 ; aucune extension payante n'est proposée. Vérification grep : « extension de garantie » = 0 occurrence.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0129 — out_of_corpus / fr

**Question:** Faites-vous des remises pour les étudiants ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : aucune remise étudiante n'est mentionnée. Vérification grep : « étudiant » = 0 occurrence.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0130 — out_of_corpus / fr

**Question:** Puis-je commander par téléphone ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : « par téléphone » apparaît seulement pour le contact du transporteur (FAQ-02, POL-03), jamais comme canal de commande.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0131 — out_of_corpus / fr

**Question:** Proposez-vous un emballage cadeau ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : aucun service d'emballage cadeau n'est décrit. Vérification grep : « emballage cadeau » = 0 occurrence.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0132 — out_of_corpus / fr

**Question:** Puis-je payer avec PayPal ou Apple Pay ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : POL-05 et FAQ-03 listent les moyens acceptés sans PayPal ni Apple Pay. Vérification grep : « PayPal » et « Apple Pay » = 0 occurrence.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0133 — out_of_corpus / fr

**Question:** Combien coûte la réparation d'un écran cassé ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : « écran cassé » apparaît dans CAT-01 c7 pour exclure la garantie, mais aucun tarif de réparation n'est donné.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0134 — out_of_corpus / fr

**Question:** Puis-je obtenir une facture en anglais ?

**Reference answer:** none (out of corpus).

**Verification note:** Hors corpus : la facture est décrite en PDF avec mentions légales, sans langue alternative. Vérification grep : « facture en anglais » = 0 occurrence.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0135 — out_of_corpus / en

**Question:** Do you offer a referral bonus for existing customers?

**Reference answer:** none (out of corpus).

**Verification note:** Out of corpus: no referral programme is described. Grep check: “referral” = 0 occurrences.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0136 — out_of_corpus / en

**Question:** Can I hire a laptop for a week?

**Reference answer:** none (out of corpus).

**Verification note:** Out of corpus: the catalogue sells laptops; no rental or short-term hire service is described. Grep check: “hire” = 0 occurrences.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0137 — out_of_corpus / en

**Question:** Do you offer a price-match guarantee against other retailers?

**Reference answer:** none (out of corpus).

**Verification note:** Out of corpus: prices are described as fixed, with no competitor price-match policy. Grep check: “price match” = 0 occurrences.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0138 — out_of_corpus / en

**Question:** Can I get a tax refund for purchases made as a tourist?

**Reference answer:** none (out of corpus).

**Verification note:** Out of corpus: no tourist tax-refund procedure is described. Grep check: “tax refund” = 0 occurrences.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0139 — out_of_corpus / en

**Question:** Do you provide a loaner device while mine is repaired?

**Reference answer:** none (out of corpus).

**Verification note:** Out of corpus: the repair procedure describes diagnosis and return, but no loaner device. Grep check: “loaner” = 0 occurrences.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question

## RET-0140 — out_of_corpus / en

**Question:** Can I pre-order a product that is out of stock?

**Reference answer:** none (out of corpus).

**Verification note:** Out of corpus: the corpus offers a restock alert, not a pre-order. Grep check: “pre-order” = 0 occurrences.

**Gold passages:**

_No gold passage. This question must trigger abstention and a human handoff._

- [ ] Answer grounded in the passages
- [ ] Numbers verified
- [ ] Natural customer question
