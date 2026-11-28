"""Génère data/train.csv (gabarits + bruit) et data/test_manual.csv (phrases écrites à la main).

Usage : python -m intent_clf.build_dataset
Le jeu de test est volontairement rédigé séparément des gabarits afin de mesurer la
généralisation réelle (et non la mémorisation des gabarits).
"""
import random
import re
import unicodedata
from pathlib import Path

import pandas as pd

SEED = 42
PER_INTENT = 70
DATA = Path(__file__).resolve().parent.parent / "data"

PROD = {
    "fr": ["casque Bluetooth", "écouteurs sans fil", "ordinateur portable", "smartphone", "chargeur rapide",
           "souris sans fil", "clavier mécanique", "tablette", "powerbank", "montre connectée",
           "câble USB-C", "écran 24 pouces"],
    "en": ["wireless headphones", "laptop", "smartphone", "fast charger", "wireless mouse",
           "mechanical keyboard", "tablet", "power bank", "smartwatch", "USB-C cable",
           "24-inch monitor", "Bluetooth speaker"],
    "ma": ["casque", "écouteurs", "laptop", "téléphone", "chargeur", "souris", "clavier", "tablette",
           "powerbank", "smartwatch", "câble USB-C", "écran"],
}
CITIES = ["Casablanca", "Rabat", "Marrakech", "Agadir", "Tanger", "Fès", "Oujda", "Tétouan",
          "Meknès", "Laâyoune", "Dakhla", "Kénitra"]

T = {
 "order_tracking": {
  "fr": ["Où en est ma commande {oid} ?", "Je voudrais suivre ma commande", "Comment je peux suivre mon colis ?",
         "Quand vais-je recevoir mon {prod} ?", "Statut de la commande {oid} svp",
         "Pouvez-vous me donner le numéro de suivi de ma commande ?", "Est-ce que ma commande a été expédiée ?",
         "Suivi colis {oid}", "Où est mon {prod} ?", "J'ai commandé un {prod} hier, quand sera-t-il livré ?",
         "Où trouver mon lien de suivi ?"],
  "en": ["Where is my order {oid}?", "I want to track my order", "How can I track my parcel?",
         "When will my {prod} arrive?", "What's the status of order {oid}?",
         "Can you give me the tracking number for {oid}?", "Has my package been shipped?", "Track my parcel {oid}",
         "Order status please", "I ordered a {prod} yesterday, when will it be delivered?",
         "Where can I find my tracking link?"],
  "ma": ["Fin wsalat commande dyali {oid} ?", "Bghit nchouf fin wsl colis dyali", "Waqtach ghadi twsalni {prod} ?",
         "Wach commande dyali tsiftat ?", "Suivi dyal commande {oid} 3afak", "Fin hiya commande dyali",
         "Numéro de suivi dyal colis dyali ?"]},
 "order_change_cancel": {
  "fr": ["Je veux annuler ma commande {oid}", "Comment annuler ma commande ?",
         "Puis-je modifier l'adresse de livraison de ma commande ?", "J'ai commandé par erreur, je veux annuler",
         "Je voudrais changer le {prod} de ma commande {oid}", "Est-il encore possible d'annuler ma commande ?",
         "Modifier ma commande {oid} svp", "Je me suis trompé d'adresse, puis-je la corriger ?",
         "Annulation commande {oid}", "Puis-je ajouter un article à ma commande ?"],
  "en": ["I want to cancel my order {oid}", "How do I cancel my order?",
         "Can I change the delivery address of my order?", "I ordered by mistake, I want to cancel",
         "I'd like to change the {prod} in my order {oid}", "Is it still possible to cancel my order?",
         "Please modify my order {oid}", "I entered the wrong address, can I fix it?", "Cancel order {oid}",
         "Can I add an item to my order?"],
  "ma": ["Bghit nanuli commande dyali {oid}", "Kifach nanuli commande ?",
         "Wach n9der nbddel l'adresse dyal livraison ?", "Dert commande b ghalat, bghit nanuliha",
         "Bghit nbddel {prod} f commande {oid}", "Wach mazal momkin nanuli commande ?",
         "Ghlt f l'adresse, wach n9der nsal7ha ?"]},
 "delivery_issue": {
  "fr": ["Ma commande {oid} n'est toujours pas arrivée", "Mon colis est en retard",
         "J'ai commandé un {prod} il y a 12 jours et je n'ai rien reçu", "Mon colis est arrivé cassé",
         "Le livreur n'est pas venu", "Mon colis a été livré au mauvais endroit",
         "Le colis est marqué livré mais je ne l'ai pas reçu", "Mon colis est perdu",
         "Le carton de mon {prod} était ouvert à la livraison", "Ça fait 10 jours et je n'ai rien reçu",
         "Le {prod} est arrivé endommagé"],
  "en": ["My order {oid} still hasn't arrived", "My package is late",
         "I ordered a {prod} 12 days ago and received nothing", "My parcel arrived damaged",
         "The courier never showed up", "My package was delivered to the wrong address",
         "It says delivered but I never got it", "My parcel is lost",
         "The box of my {prod} was open when delivered", "It's been 10 days and nothing arrived",
         "The {prod} arrived broken"],
  "ma": ["Commande {oid} mazal ma wslatch", "Colis dyali t3attal bzaf", "Colis wsl m9ttae3", "Livreur ma jach",
         "Colis t livra f blasa machi hiya", "Colis dyali daya3", "Dert commande men 10 iyam o mazal ma wslatch",
         "Wsl {prod} mkser"]},
 "return_request": {
  "fr": ["Comment puis-je retourner mon {prod} ?", "Je veux renvoyer mon {prod}", "Quelle est votre politique de retour ?",
         "Combien de jours pour retourner un produit ?", "Le {prod} ne me convient pas, je voudrais le retourner",
         "Je souhaite échanger mon {prod}", "Puis-je retourner un article ouvert ?", "Comment faire un retour ?",
         "J'ai reçu un {prod} défectueux, je veux le renvoyer", "Qui paie les frais de retour ?",
         "Je veux rendre ma commande {oid}", "Y a-t-il une étiquette de retour ?"],
  "en": ["How can I return my {prod}?", "I want to send back my {prod}", "What is your return policy?",
         "How many days do I have to return an item?", "I'd like to exchange my {prod}",
         "Can I return an opened product?", "How do I start a return?",
         "I received a damaged {prod} and want to return it", "Who pays for return shipping?",
         "I want to return order {oid}", "Return my {prod}"],
  "ma": ["Kifach n3awd nrje3 {prod} dyali ?", "Bghit nrajje3 {prod}", "Ch7al dyal l'ayam bach n9der nrje3 produit ?",
         "Bghit n'echangi {prod} dyali", "Wach n9der nrje3 produit mfthouh ?", "Kifach ndir retour l commande {oid} ?"]},
 "refund_status": {
  "fr": ["Quand vais-je être remboursé ?", "Où en est mon remboursement pour la commande {oid} ?",
         "Je n'ai pas encore reçu mon remboursement", "Combien de temps pour un remboursement ?",
         "Mon remboursement n'est pas arrivé sur ma carte", "J'attends le remboursement de mon {prod}",
         "Statut du remboursement {oid}", "Le remboursement est-il fait ?", "Comment suis-je remboursé ?"],
  "en": ["When will I get my refund?", "Where is my refund for order {oid}?", "I haven't received my refund yet",
         "How long does a refund take?", "My refund hasn't shown up on my card",
         "I'm waiting for the refund for my {prod}", "Refund status for {oid}", "Has my refund been processed?",
         "How will I be refunded?", "Still no refund"],
  "ma": ["Waqtach ghadi yrj3o lia flous ?", "Remboursement dyal commande {oid} fin wsl ?",
         "Mazal ma wslni remboursement", "Ch7al kayakhod remboursement ?", "Flous dyali ma rj3ouch l carte",
         "Wach remboursement t3ml ?"]},
 "payment_info": {
  "fr": ["Quels moyens de paiement acceptez-vous ?", "Puis-je payer à la livraison ?",
         "Acceptez-vous les cartes Visa et Mastercard ?", "Peut-on payer en plusieurs fois ?",
         "Le paiement par carte est-il sécurisé ?", "Puis-je payer par virement bancaire ?",
         "Acceptez-vous le paiement en espèces ?", "Comment obtenir ma facture ?",
         "Proposez-vous le paiement en 3 fois pour un {prod} ?", "Comment payer ma commande ?",
         "Puis-je avoir une facture pour mon entreprise ?"],
  "en": ["What payment methods do you accept?", "Can I pay cash on delivery?", "Do you accept Visa and Mastercard?",
         "Can I pay in installments?", "Is card payment secure?", "Can I pay by bank transfer?",
         "How do I get my invoice?", "Do you offer installments for a {prod}?", "How do I pay for my order?",
         "Can I get an invoice for my company?"],
  "ma": ["Chno hiya toro9 dyal l'khlas ?", "Wach n9der n5ls 3nd l'istilam ?", "Wach katakhdo carte Visa ?",
         "Wach n9der n5ls b tl9sit ?", "L'khlas b carte amen ?", "Kifach nakhod facture dyali ?", "N5ls cash ?"]},
 "payment_issue": {
  "fr": ["Ma carte a été refusée au paiement", "J'ai été débité deux fois pour la même commande",
         "Mon paiement a été refusé, pourquoi ?", "Ma carte est bloquée sur votre site",
         "Le montant débité est incorrect", "Je conteste un prélèvement sur ma carte",
         "Le paiement a échoué mais j'ai été débité", "Erreur lors du paiement de ma commande {oid}",
         "Mon paiement ne passe pas"],
  "en": ["My card was declined at checkout", "I was charged twice", "My payment was declined, why?",
         "My card is blocked on your site", "The amount charged is wrong", "I want to dispute a charge on my card",
         "Payment failed but I was charged", "Error when paying for order {oid}", "My payment won't go through"],
  "ma": ["Carte dyali t refusat f l'khlas", "T7sbt 3liya joj mrat", "L'khlas ma daz ch w t5ls lflous",
         "Carte dyali bloquée", "Lmontant li t5ssem ghalat", "L'khlas b carte ma khdamch"]},
 "technical_support": {
  "fr": ["Mon {prod} ne s'allume plus", "Mon {prod} ne charge plus", "Comment appairer mon {prod} ?",
         "Mon {prod} est planté", "Le wifi de mon {prod} ne marche pas",
         "Où trouver le mode d'emploi de mon {prod} ?", "Comment réinitialiser mon {prod} ?",
         "Mon {prod} chauffe beaucoup", "Le bluetooth de mon {prod} ne se connecte plus",
         "Mon {prod} redémarre tout seul"],
  "en": ["My {prod} won't turn on", "My {prod} won't charge anymore", "How do I pair my {prod}?",
         "My {prod} is frozen", "The wifi on my {prod} doesn't work",
         "Where can I find the user manual for my {prod}?", "How do I reset my {prod}?",
         "My {prod} gets very hot", "The bluetooth on my {prod} won't connect", "My {prod} keeps restarting"],
  "ma": ["{prod} dyali ma bqach kaykhdem", "{prod} ma kayshl3ch", "Kifach nconnecti {prod} dyali ?",
         "{prod} dyali bloqué", "Wifi dyal {prod} ma khdamch", "Kifach n3awd nsayb {prod} ?", "{prod} kayskhon bzaf"]},
 "warranty_claim": {
  "fr": ["Mon {prod} ne fonctionne plus, il est sous garantie ?", "Comment faire jouer la garantie ?",
         "Quelle est la durée de garantie de ce {prod} ?", "La garantie couvre-t-elle l'écran cassé ?",
         "Je veux réparer mon {prod} sous garantie", "Que couvre la garantie ?",
         "Où envoyer mon {prod} en panne pour le SAV ?", "Batterie de mon {prod} défectueuse, garantie ?",
         "Je veux un échange sous garantie pour mon {prod}", "Mon {prod} est tombé en panne après 3 mois, c'est couvert ?"],
  "en": ["My {prod} stopped working, is it under warranty?", "How do I make a warranty claim?",
         "How long is the warranty on this {prod}?", "Does the warranty cover a cracked screen?",
         "I want to get my {prod} repaired under warranty", "What does the warranty cover?",
         "Where do I send my faulty {prod} for after-sales service?", "Defective battery on my {prod}, warranty?",
         "I want a warranty exchange for my {prod}", "My {prod} broke after 3 months, is it covered?"],
  "ma": ["{prod} dyali twqef 3la lkhdma, wach fih garantie ?", "Kifach nstafed mn la garantie ?",
         "Ch7al dyal garantie f had {prod} ?", "Wach garantie katghati l'écran mkser ?",
         "Bghit nsalah {prod} f garantie", "Wach SAV kayssalhou {prod} ?"]},
 "product_info": {
  "fr": ["Quelles sont les caractéristiques de ce {prod} ?", "Quelle est l'autonomie de la batterie du {prod} ?",
         "Ce {prod} est-il compatible avec iPhone ?", "Quelle est la capacité de stockage de ce {prod} ?",
         "Le {prod} est-il étanche ?", "Pouvez-vous me conseiller un {prod} pour le gaming ?",
         "Quelle différence entre ces deux {prod} ?", "Quel {prod} me recommandez-vous pour un budget limité ?",
         "Ce {prod} est-il neuf ou reconditionné ?", "Le {prod} est-il disponible ?", "Quel est le prix du {prod} ?",
         "Avez-vous encore du stock de {prod} ?", "Combien coûte le {prod} ?",
         "Quand le {prod} sera-t-il de nouveau en stock ?", "Avez-vous le {prod} en noir ?"],
  "en": ["What are the specs of this {prod}?", "How long does the battery of the {prod} last?",
         "Is this {prod} compatible with iPhone?", "What's the storage capacity of this {prod}?",
         "Is the {prod} waterproof?", "Can you recommend a {prod} for gaming?",
         "What's the difference between these two {prod}?", "Which {prod} do you recommend on a budget?",
         "Is this {prod} new or refurbished?", "Is the {prod} available?", "What is the price of the {prod}?",
         "Do you still have the {prod} in stock?", "How much does the {prod} cost?",
         "When will the {prod} be back in stock?", "Do you have the {prod} in black?"],
  "ma": ["Chno homa les caractéristiques dyal had {prod} ?", "Ch7al kat3ish batterie dyal {prod} ?",
         "Wach had {prod} compatible m3a iPhone ?", "Chno ta9tarh 3lina {prod} l gaming ?",
         "Ch7al dyal stockage f had {prod} ?", "Wach {prod} kayn f stock ?", "Ch7al taman dyal {prod} ?",
         "Wach mazal 3ndkom {prod} ?", "B ch7al {prod} ?", "Waqtach ghadi yrj3 {prod} f stock ?"]},
 "promotion_loyalty": {
  "fr": ["Avez-vous des codes promo ?", "Y a-t-il des promotions en ce moment ?", "Mon code promo ne fonctionne pas",
         "Quand ont lieu les soldes ?", "Avez-vous une réduction pour les étudiants ?",
         "Comment utiliser un code de réduction ?", "Y a-t-il une promo sur les {prod} ?",
         "Proposez-vous un programme de fidélité ?", "Puis-je cumuler deux codes promo ?",
         "Black Friday : quelles offres sur les {prod} ?", "Comment utiliser mes points ?",
         "Combien de points de fidélité ai-je ?", "J'ai une carte cadeau, comment l'utiliser ?",
         "Ma promotion n'a pas été appliquée"],
  "en": ["Do you have any promo codes?", "Are there any promotions right now?", "My promo code doesn't work",
         "When are the sales?", "Do you have a student discount?", "How do I use a discount code?",
         "Is there a deal on {prod}?", "Do you have a loyalty program?", "Can I combine two promo codes?",
         "Black Friday: what offers on {prod}?", "How do I use my points?", "How many loyalty points do I have?",
         "I have a gift card, how do I use it?", "My promotion wasn't applied"],
  "ma": ["Wach kayn chi code promo ?", "Wach kayn promotions daba ?", "Code promo dyali ma khdamch",
         "Waqtach kaybda soldes ?", "Wach kayn réduction l tolba ?", "Kifach nsta3ml code réduction ?",
         "Wach kayn promo 3la {prod} ?", "Black Friday chno homa les offres ?", "Kifach nsta3ml les points dyali ?"]},
 "account_privacy": {
  "fr": ["Comment supprimer mon compte ?", "J'ai oublié mon mot de passe", "Quelles données personnelles collectez-vous ?",
         "Je veux me désinscrire de la newsletter", "Comment modifier l'adresse email de mon compte ?",
         "Je veux que mes données soient supprimées", "Utilisez-vous des cookies ?",
         "Comment changer mon mot de passe ?", "Comment accéder à mes données personnelles ?",
         "Je n'arrive pas à me connecter à mon compte"],
  "en": ["How do I delete my account?", "I forgot my password", "What personal data do you collect?",
         "I want to unsubscribe from the newsletter", "How do I change the email on my account?",
         "I want my data deleted", "Do you use cookies?", "How do I change my password?",
         "How can I access my personal data?", "I can't log into my account"],
  "ma": ["Kifach nms7 compte dyali ?", "Nsit mot de passe", "Chno hiya les données li kat jm3o 3liya ?",
         "Bghit n'unsubscribi mn newsletter", "Kifach nbddel email dyal compte ?", "Bghit tms7o données dyali",
         "Ma9drtch ndkhol l compte dyali"]},
 "human_support": {
  "fr": ["Je veux parler à un conseiller", "Passez-moi un agent humain", "Je veux parler à un responsable",
         "Passez-moi quelqu'un de réel", "Je ne veux pas parler à un robot", "Pouvez-vous me transférer à un humain ?",
         "Je préfère parler à une vraie personne", "Un agent s'il vous plaît",
         "Personne ne répond à mes messages, je veux un responsable"],
  "en": ["I want to speak to a human agent", "Let me talk to a representative", "I want to talk to a manager",
         "Put me through to a real person", "I don't want to talk to a bot", "Can you transfer me to a human?",
         "I'd rather speak to a real person", "An agent please",
         "Nobody answers my messages, I want a manager"],
  "ma": ["Bghit nhdr m3a chi wa7d mn l'équipe", "Bghit agent machi robot", "Bghit nchouf responsable",
         "Khllini nhdr m3a chi bnadem", "Ma bghitch robot, bghit chi wa7d", "Wach t9dro t7wlouni l chi agent ?"]},
 "out_of_scope": {
  "fr": ["Quel temps fait-il à {city} ?", "Peux-tu me raconter une blague ?", "Qui a gagné le match hier ?",
         "Donne-moi une recette de tajine", "Comment réparer ma voiture ?", "Quelle est la capitale du Japon ?",
         "Peux-tu m'aider à écrire mon CV ?", "Où acheter des billets d'avion ?", "Comment perdre du poids ?",
         "Quel est le meilleur restaurant à {city} ?", "Qui est le président des États-Unis ?",
         "Comment installer Windows sur mon PC ?", "Quel est le cours du bitcoin ?",
         "Bonjour", "Salut", "Bonsoir, vous êtes là ?", "Merci beaucoup", "Merci pour votre aide", "Super, merci !",
         "Au revoir", "Bonne journée", "Hello", "Coucou", "Ok merci, c'est noté", "Parfait, merci", "Test"],
  "en": ["What's the weather like in {city}?", "Tell me a joke", "Who won the football match yesterday?",
         "Give me a tajine recipe", "How do I fix my car?", "What is the capital of Japan?",
         "Can you help me write my resume?", "Where can I buy plane tickets?", "How do I lose weight?",
         "What's the best restaurant in {city}?", "Who is the president of the United States?",
         "How do I install Windows on my PC?", "What is the price of bitcoin?",
         "Hello", "Hi there", "Good evening", "Thank you so much", "Thanks for your help", "Great, thanks!",
         "Goodbye", "Have a nice day", "Hey", "Ok thanks", "Perfect, thank you", "Is anyone there?", "Test"],
  "ma": ["Kifach l'jaw f {city} ?", "Goul lia chi nokta", "Chkon rba7 l match lbare7 ?", "3tini wasfat tajine",
         "Kifach nsalah tomobil dyali ?", "Chno hiya 3asimat l yaban ?", "3awnni nkteb CV",
         "Fin n9der nchri bitaq tayyara ?", "Ach hiya a7sen restaurant f {city} ?",
         "Salam", "Salam alaykom", "Marhba", "Choukran bzaf", "Choukran 3la l mosa3ada", "Mrc bzaf", "Bslama",
         "Nhark mbarek", "Ahlan", "Waxxa choukran"]},
}

TEST = {
 "order_tracking": [
  "Can you check the shipping status of ORD482 for me", "Bonjour, j'aimerais savoir où se trouve mon colis",
  "Je n'ai pas reçu de mail de suivi après mon achat", "When does my laptop get delivered",
  "Fin wsl lcommande dyali, tsiftat wla la ?", "Où puis-je voir le suivi de mon colis ?",
  "How do I know where my package currently is", "Wach n9der nchouf fin wsl colis dyali",
  "Quand est-ce que mon casque sera expédié ?", "Please send me the tracking link for my order"],
 "order_change_cancel": [
  "I placed the wrong order, please cancel it before it ships", "Peut-on changer l'adresse de livraison avant l'expédition ?",
  "Bghit nbddel numéro téléphone f commande dyali", "Annulez ma commande s'il vous plaît, je l'ai passée en double",
  "Can I switch the colour of the item I just ordered?", "J'ai commandé deux fois par erreur, annulez la deuxième",
  "How do I stop my order from being shipped", "Wach n9der nwqef l commande 9bel ma tsift ?",
  "Je veux ajouter un câble à ma commande en cours", "Is it too late to cancel? I ordered 10 minutes ago"],
 "delivery_issue": [
  "Ma commande n'est toujours pas livrée, ça fait 8 jours", "Delivery delayed, what's going on with my order?",
  "Colis dyali t3attal 3la l maw3id", "Mon colis est bloqué à Casablanca depuis 3 jours",
  "The delivery guy left my parcel at the wrong building", "Le livreur m'a appelé mais personne n'a livré",
  "My package came with a broken screen", "Le colis est arrivé complètement écrasé",
  "Colis wsl lia mkser w mfthouh", "Tracking says delivered but there's nothing at my door"],
 "return_request": [
  "J'ai changé d'avis, je peux renvoyer l'article ?", "What's the procedure to send an item back",
  "Le produit reçu ne correspond pas à la description, je voudrais le rendre", "Is there a 14-day return window?",
  "Bghit nrje3 l'article, ma 3jbnich", "Can I swap my headphones for a different colour?",
  "Quelles sont les conditions pour un retour ?", "Do I need the original box to return something?",
  "Peut-on retourner un téléphone déjà déballé ?", "Kifach nsift l'article b retour ?"],
 "refund_status": [
  "I returned my keyboard two weeks ago, still waiting for my money back", "Mon remboursement a-t-il été validé ?",
  "Combien de jours faut-il pour que l'argent revienne sur ma carte ?", "Refund not received for ORD317",
  "Wach t'rembourssa lcommande dyali ?", "Vous m'avez promis un remboursement mais rien n'est arrivé",
  "How many days until the money is back in my bank account?", "Je voudrais connaître l'état de mon remboursement",
  "Flous dyal l'article li rje3t mazal ma wslouni", "Will the refund go to my original payment method?"],
 "payment_info": [
  "Vous acceptez PayPal ?", "Can I use a CMI card to pay online", "Peut-on payer en cash au livreur ?",
  "Wach kaynin facilités de paiement ?", "Is it possible to split the payment into 3 installments?",
  "Do you take Apple Pay?", "Est-ce qu'on peut payer par virement ?", "Ach men tari9a dyal khlas kayn ?",
  "Is my credit card information safe on your site?", "Où puis-je télécharger ma facture ?"],
 "payment_issue": [
  "Mon paiement par carte ne passe pas, que faire ?", "I got a charge on my card but the order didn't go through",
  "Ma banque a débité deux fois le même montant", "Carte dyali t rfdat 3nd l'khlas",
  "The checkout keeps saying transaction failed", "Le montant prélevé ne correspond pas au prix affiché",
  "I see two payments for one order on my statement", "Erreur « paiement refusé » alors que ma carte est valide",
  "L'khlas ma daz ch, flous tkhssmo", "My bank blocked the payment to your site"],
 "technical_support": [
  "Mon casque fait un bruit étrange", "Mon PC portable ne démarre plus", "My phone keeps freezing since the update",
  "Comment connecter mes écouteurs en Bluetooth ?", "How do I factory reset my smartwatch",
  "Tilifon dyali ma bqach kay'chargi", "Mon écran clignote", "The keyboard doesn't type some keys",
  "Souris dyali ma kat'connectach", "Where can I download the manual for my tablet"],
 "warranty_claim": [
  "Do I need the receipt to claim warranty?", "L'écran de mon téléphone a des lignes vertes après 5 mois, c'est couvert ?",
  "Je peux envoyer mon casque défectueux en SAV ?", "The battery of my laptop drains in one hour, covered by warranty?",
  "Kifach ndir réclamation l garantie dyal laptop ?", "Combien de temps dure la garantie sur les smartphones ?",
  "My charger stopped charging after two weeks, can it be replaced under warranty?",
  "Mon PC portable a 8 mois, la batterie est morte, c'est sous garantie ?",
  "T7ra tilifon dyali, wach garantie katghatih ?", "Is accidental damage covered?"],
 "product_info": [
  "Ce laptop a combien de RAM ?", "Does this phone support 5G", "Le casque a-t-il une réduction de bruit active ?",
  "Wach had telephone fih 128 go wla 256 ?", "What colors does the smartwatch come in?",
  "Je cherche un PC portable léger pour étudiant, que me conseillez-vous ?", "Vous avez des iPhone en stock ?",
  "Price of your cheapest laptop?", "C'est combien le casque noir ?", "Cet article est indisponible, il revient quand ?"],
 "promotion_loyalty": [
  "Il y a un coupon pour ma première commande ?", "Any discount for buying two items",
  "Le code BLACK20 est refusé au paiement", "Wach kayn tkhfid f had simana ?",
  "Are there Black Friday deals on laptops this year?", "Does the newsletter give a welcome voucher?",
  "Comment utiliser mes points de fidélité ?", "Can I redeem my loyalty points on this order?",
  "Chno hiya les offres dyal had chhar ?", "I can't apply my coupon at checkout"],
 "account_privacy": [
  "J'ai oublié mon mot de passe, comment le réinitialiser ?", "Please delete all my personal data",
  "Kifach nms7 compte dyali nmhaya ?", "Comment me désinscrire de vos emails promotionnels ?",
  "How do I update my phone number in my account?", "Quelles informations personnelles conservez-vous sur moi ?",
  "Ma9drtch nconnecti l compte dyali", "I can't log in, it says wrong password",
  "Do you share my data with third parties?", "Je veux fermer mon compte définitivement"],
 "human_support": [
  "Je souhaite joindre un vrai conseiller", "Can I get a call back from someone please",
  "Ma 3andkom 7ta chi wa7d yjawb ? Bghit nhdr m3a chi bnadem", "Please escalate my case to a supervisor",
  "Personne ne me répond depuis trois jours, je veux un responsable", "Je veux un humain, pas un chatbot",
  "Transfer me to customer service, a real person", "Bghit n3ayet l chi agent bnadem",
  "Passez-moi votre service client s'il vous plaît", "Give me a human please"],
 "out_of_scope": [
  "Bonjour, bonne soirée", "Thanks a lot, that solved my problem", "Salam labas ?", "Merci, c'est réglé",
  "Ok bye", "Quel est le meilleur film de l'année ?", "Can you recommend a good book", "Chkon hwa rais d France ?",
  "What's the exchange rate of the euro today?", "Is it going to rain tomorrow in Agadir?"],
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def add_noise(s, rng):
    ops = rng.sample(["lower", "accents", "punct", "typo", "polite"], k=rng.choice([1, 2]))
    for op in ops:
        if op == "lower":
            s = s.lower()
        elif op == "accents":
            s = strip_accents(s)
        elif op == "punct":
            s = re.sub(r"[?!.,;:]", "", s)
        elif op == "typo" and len(s) > 6:
            i = rng.randrange(1, len(s) - 2)
            s = s[:i] + s[i + 1] + s[i] + s[i + 2:] if rng.random() < 0.5 else s[:i] + s[i + 1:]
        elif op == "polite":
            s = s.rstrip(" ?!.") + " " + rng.choice(["svp", "stp", "please", "3afak", "merci"])
    return s.strip()


def fill(tpl, lang, rng):
    return tpl.format(prod=rng.choice(PROD[lang]), city=rng.choice(CITIES), oid=f"ORD{rng.randint(100, 999)}")


def build_train():
    rng = random.Random(SEED)
    rows = []
    for intent, langs in T.items():
        pool, seen = [], set()
        for lang, tpls in langs.items():
            for ti, tpl in enumerate(tpls):
                tid = f"{intent}|{lang}|{ti}"
                n_fills = 4 if "{" in tpl else 1
                for _ in range(n_fills):
                    base = fill(tpl, lang, rng)
                    for variant in (base, add_noise(base, rng)):
                        if variant.lower() not in seen:
                            seen.add(variant.lower())
                            pool.append({"text": variant, "intent": intent, "lang": lang, "template_id": tid})
        rng.shuffle(pool)
        rows.extend(pool[:PER_INTENT])
    df = pd.DataFrame(rows).sample(frac=1, random_state=SEED).reset_index(drop=True)
    return df


DARIJA_TOKENS = {
    "wach", "kifach", "bghit", "ch7al", "chhal", "chno", "waqtach", "mazal", "dyal", "dyali", "choukran", "salam",
    "kayn", "kaynin", "chkon", "n9der", "m3a", "bzaf", "wsl", "wslat", "wslouni", "t3attal", "nrje3", "nbddel",
    "flous", "khlas", "l'khlas", "tsiftat", "nsift", "nwqef", "nms7", "nmhaya", "nconnecti", "bnadem", "agent",
    "3andkom", "7ta", "yjawb", "3ayet", "n3ayet", "nchouf", "ma9drtch", "ach", "hwa", "tilifon", "t7ra", "tkhfid",
    "simana", "chhar", "hiya", "li", "rje3t", "3nd", "daz", "tkhssmo", "t'rembourssa", "3la", "9bel", "tsift", "ma3",
    "kay'chargi", "kat'connectach", "mkser", "mfthouh", "lcommande", "ghadi", "daya3", "n3awd",
    "labas", "rfdat", "t", "mrc", "bslama", "marhba", "ahlan", "waxxa", "maw3id", "3jbnich", "ma", "khdamch",
}
# 'ma', 'li', 't', 'agent', 'ach'... sont ambigus (français/anglais) : on exige >= 2 jetons darija non ambigus.
AMBIGUOUS = {"ma", "li", "t", "agent", "ach", "3la", "hiya"}
FR_HINT = re.compile(r"[éèàçùêôû]|\b(je|vous|mon|est|le|la|les|un|une|peut|peut-on|quel|quelle|quand|combien|comment|"
                     r"puis-je|mes|ce|cet|pas|que|qui|pour|dans|sur|avec|j'ai|c'est|il|elle|ne|se)\b")


def detect_lang(t):
    toks = re.findall(r"[a-z0-9']+", t.lower())
    darija = [w for w in toks if w in DARIJA_TOKENS and w not in AMBIGUOUS]
    if len(darija) >= 1 and not re.search(r"[éèàçùêôû]", t) and len(darija) >= max(1, len(toks) // 6):
        return "ma"
    if FR_HINT.search(t.lower()):
        return "fr"
    return "en"


def build_test():
    rows = [{"text": t, "intent": intent, "lang": detect_lang(t)} for intent, texts in TEST.items() for t in texts]
    return pd.DataFrame(rows)


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    tr, te = build_train(), build_test()
    tr.to_csv(DATA / "train.csv", index=False)
    te.to_csv(DATA / "test_manual.csv", index=False)
    overlap = set(tr.text.str.lower()) & set(te.text.str.lower())
    print(f"train={len(tr)} test_manual={len(te)} exact-overlap={len(overlap)}")
    print(tr.intent.value_counts().to_string())
    print(tr.lang.value_counts().to_string())
    print(te.lang.value_counts().to_string())
