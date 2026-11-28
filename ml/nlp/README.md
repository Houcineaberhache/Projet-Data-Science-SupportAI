# ml/nlp — Classification d'intentions (SupportAI / NovaShop)

Module de l'Étudiant 3 (NLP & ML). Il classe chaque message client parmi les **14 intentions officielles** (`data/annotations/intents.csv`, règles dans `docs/annotation_guidelines.md`) et indique au backend où l'envoyer.

## Structure
```
ml/nlp/
  data/        intents.json (14 intentions + route proposée) · train.csv (synthétique) · test_manual.csv
  intent_clf/  build_dataset.py · nlp_core.py · train.py · inference.py · check_intents.py
  models/      tfidf_lr · tfidf_svm · embed_lr (.joblib) + config.json
  reports/     metrics.json · errors_test_manual.csv · confusion_matrix_best.png
  notebooks/   model_comparison.ipynb (exécuté) · colab_run.ipynb (exécution complète sur Google Colab)
  api/main.py  API FastAPI · tests/test_api.py
```
Toutes les commandes se lancent **depuis `ml/nlp/`**. `Dockerfile` + `requirements-serve.txt` : image du service.

## Utilisation
```bash
cd ml/nlp
pip install -r requirements.txt
python -m intent_clf.check_intents   # vérifie que les noms = intents.csv officiel
python -m intent_clf.build_dataset   # (re)génère les données synthétiques
python -m intent_clf.train           # entraîne, évalue (CV, test manuel, pilot 20), sauvegarde
uvicorn api.main:app --port 8002     # API (docs : /docs) — 8001 est pris par le service MCP
pytest -q
```

### Sur Google Colab (recommandé : vrais embeddings, et si votre PC bloque pandas/scikit-learn)
Ouvrir [`notebooks/colab_run.ipynb`](https://colab.research.google.com/github/Houcineaberhache/Projet-Data-Science-SupportAI/blob/main/ml/nlp/notebooks/colab_run.ipynb) dans Colab puis *Exécution → Tout exécuter*. Il clone la branche, entraîne avec le vrai modèle SBERT, lance les tests, affiche le tableau de résultats et produit un zip à remettre dans le dépôt.

### Intégration (Docker)
Le service est déclaré dans `docker-compose.yml` (service `nlp`, hôte `:8002` → conteneur `:8000`) et le backend l'appelle via `NLP_SERVICE_URL=http://nlp:8000/classify` (valeur par défaut). L'image entraîne les modèles à la construction (les `.joblib` ne sont pas versionnés) :
```bash
docker compose up --build nlp backend     # ou : docker build -t supportai-nlp ml/nlp
curl -X POST localhost:8002/classify -H "Content-Type: application/json" -d '{"text":"Où est ma commande ORD123 ?"}'
```
Si le service est injoignable, `backend/services/nlp_client.py` retombe sur son mock à mots-clés (3 s de timeout). Le backend n'utilise aujourd'hui que `intent == "order_tracking"` ; les champs `route`, `low_confidence` et `order_id` renvoyés par l'API ne sont pas encore exploités.

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
- Darija en alphabet latin : peu de données, orthographe non standardisée. Le score élevé en darija sur le test manuel (0,96, 24 phrases) est un **artefact** (mêmes auteur et vocabulaire restreint pour gabarits et test), pas une preuve de facilité ; EN 0,75 et FR 0,88 sur le même test.

## Points à valider avec l'équipe (décisions de design de ma part)
Vérifié contre `docs/annotation_guidelines.md` (§5.2, §5.3 et annexe A) : les 14 intentions et les frontières (retard/non-reçu/cassé → `delivery_issue`, « où est ma commande » → `order_tracking`, priorité `refund_status` > `return_request` > `order_tracking`) sont respectées par mes données. Restent deux **trous de taxonomie** :
1. **Informations générales de livraison** (« Livrez-vous à Dakhla ? », frais, délais, zones) : l'arbre de décision ne traite que les demandes sur *une commande précise* ; aucune classe ne couvre ce cas, très fréquent en e-commerce. Ces exemples sont **exclus** de l'entraînement, donc le modèle les classe au hasard. Options : (a) ajouter une classe (les guidelines imposent alors de ré-annoter le jeu de test et d'incrémenter la version), (b) les rattacher à `product_info`/`payment_info` par une règle explicite, (c) accepter `out_of_scope` (mais cela enverrait de vraies questions clients vers le fallback).
2. **Plaintes sans demande d'agent** (« votre service est nul ») : `human_support` = demande *explicite* d'un agent ; l'arbre renvoie sinon à `out_of_scope`. Même question : règle explicite à écrire dans les guidelines.
3. **Routes** proposées dans `data/intents.json` (ex. `payment_issue` → `human_handoff`) : à valider avec le backend.
4. **Frontières** les plus confuses dans les tests : `order_tracking` ↔ `delivery_issue`, `refund_status` ↔ `return_request`, code promo refusé au paiement (`promotion_loyalty` vs `payment_issue`).
5. Données réelles/annotées par l'équipe : les ajouter au test (et à l'entraînement) dès que disponibles.
