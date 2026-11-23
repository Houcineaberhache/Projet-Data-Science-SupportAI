# ml/nlp — Classification d'intentions (SupportAI / NovaShop)

Module de l'Étudiant 3 (NLP & ML). Il classe chaque message client parmi les **14 intentions officielles** (`data/annotations/intents.csv`, règles dans `docs/annotation_guidelines.md`) et indique au backend où l'envoyer.

## Structure
```
ml/nlp/
  data/        intents.json (14 intentions + route proposée) · train.csv (synthétique) · test_manual.csv
  intent_clf/  build_dataset.py · nlp_core.py · train.py · inference.py · check_intents.py
  models/      tfidf_lr · tfidf_svm · embed_lr (.joblib) + config.json
  reports/     metrics.json · errors_test_manual.csv · confusion_matrix_best.png
  notebooks/   model_comparison.ipynb (exécuté)
  api/main.py  API FastAPI · tests/test_api.py
```
Toutes les commandes se lancent **depuis `ml/nlp/`**.

## Utilisation
```bash
cd ml/nlp
pip install -r requirements.txt
python -m intent_clf.check_intents   # vérifie que les noms = intents.csv officiel
python -m intent_clf.build_dataset   # (re)génère les données synthétiques
python -m intent_clf.train           # entraîne, évalue (CV, test manuel, pilot 20), sauvegarde
uvicorn api.main:app --port 8001     # API (docs : /docs)
pytest -q
```

## Contrat d'API (pour le backend)
`POST /classify` `{"text": "...", "top_k": 3}` →
```json
{"intent": "order_change_cancel", "confidence": 0.98, "low_confidence": false, "route": "order_api",
 "needs_order_id": true, "order_id": "ORD555", "top_k": [...], "model": "tfidf_svm"}
```
Autres : `POST /classify/batch`, `GET /intents`, `GET /health`.
`route` ∈ `rag | order_api | human_handoff | canned | fallback`. Confiance sous le seuil → `fallback`.
Les salutations/remerciements sont une sous-partie d'`out_of_scope` (officiel) ; une règle simple les route vers `canned`.

> Les **routes sont une proposition** du module NLP (colonne `route` de `data/intents.json`), à valider avec le backend. Choix à discuter : `payment_issue` → `human_handoff` (donnée sensible), `delivery_issue` → `order_api`.

## Résultats
| Modèle | CV groupée F1 macro | Test manuel (140) accuracy | Test manuel F1 macro | Pilot 20 accuracy |
|---|---|---|---|---|
| TF-IDF + LogReg | 0,701 | 0,836 | 0,834 | 0,95 |
| **TF-IDF + Linear SVM** | **0,733** | **0,843** | **0,842** | 0,95 |
| Embeddings + LogReg (repli LSA) | 0,708 | 0,771 | 0,776 | 0,95 |

Le pilot 20 n'a que 20 phrases (1 erreur = 5 points) : il ne départage pas les modèles. Détail par classe, matrice de confusion, analyse d'erreurs et courbe seuil/couverture : voir le notebook.

## Limites (honnêteté scientifique)
- **Données d'entraînement synthétiques** (gabarits + bruit) : un split aléatoire donnerait des scores gonflés ; d'où la CV groupée par gabarit et un test manuel indépendant (10 phrases par intention, rédigées par le même auteur que les gabarits).
- **Embeddings** : le modèle multilingue pré-entraîné n'était pas téléchargeable dans l'environnement où le code a été exécuté ; un **repli LSA** (SVD sur TF-IDF caractères) a été utilisé, qui n'est *pas* un vrai embedding sémantique. Sur une machine avec accès à Hugging Face, `python -m intent_clf.train` bascule automatiquement sur `paraphrase-multilingual-MiniLM-L12-v2`. La conclusion « SVM > embeddings » ne vaut donc pas pour de vrais embeddings.
- Seuil de confiance calculé sur la CV synthétique ; scores SVM non calibrés. À recalibrer sur de vraies requêtes.
- Darija en alphabet latin : peu de données, orthographe non standardisée.

## Points à valider avec l'équipe (décisions de design de ma part)
1. **Demandes d'information livraison** (« Livrez-vous à Dakhla ? », frais/délais) : aucune des 14 intentions ne les couvre explicitement (`order_tracking` = suivi d'une commande existante). Ces exemples sont **exclus** de l'entraînement ; le modèle les classera donc arbitrairement. Vérifier ce que disent les guidelines (POL-03 / FAQ) et trancher.
2. **Plaintes sans demande d'humain** (« votre service est nul ») : `human_support` = demande *explicite* d'un agent. Ces phrases ne sont pas dans l'entraînement ; à clarifier (hors périmètre ? `human_support` ?).
3. **Frontières** les plus confuses dans les tests : `order_tracking` ↔ `delivery_issue`, `refund_status` ↔ `return_request`, code promo refusé au paiement (`promotion_loyalty` vs `payment_issue`).
4. Données réelles/annotées par l'équipe : les ajouter au test (et à l'entraînement) dès que disponibles.
