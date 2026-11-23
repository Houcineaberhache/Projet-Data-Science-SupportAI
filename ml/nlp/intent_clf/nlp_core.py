"""Briques communes : chargement des données, pipelines, évaluation.

Trois familles de modèles comparées :
  1. tfidf_lr   : TF-IDF (mots 1-2 + caractères 2-5) + Régression Logistique
  2. tfidf_svm  : mêmes features + Linear SVM
  3. embed_lr   : embeddings de phrases + Régression Logistique
                  - backend 'sbert'  : sentence-transformers multilingue (si le modèle est téléchargeable)
                  - backend 'lsa'    : repli hors-ligne = TF-IDF caractères -> SVD (LSA) -> L2
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import Normalizer
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parent.parent
SEED = 42
SBERT_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def repo_root():
    """Racine du monorepo (dossier contenant data/annotations), ou None si le module est utilisé hors dépôt."""
    for p in ROOT.parents:
        if (p / "data" / "annotations").is_dir():
            return p
    return None


def load_data():
    train = pd.read_csv(ROOT / "data" / "train.csv")
    test = pd.read_csv(ROOT / "data" / "test_manual.csv")
    return train, test


def load_pilot():
    """Pilot 20 annoté par l'équipe (data/annotations/pilot_20_annotation_sheet.csv, séparateur ';').
    Étiquette de référence = annotator_1_intent. Retourne None si le fichier est absent."""
    rr = repo_root()
    f = rr / "data" / "annotations" / "pilot_20_annotation_sheet.csv" if rr else None
    if f is None or not f.exists():
        return None
    df = pd.read_csv(f, sep=";", encoding="utf-8-sig")
    df = df.rename(columns={"annotator_1_intent": "intent", "language": "lang"})
    df = df.dropna(subset=["text", "intent"])
    return df[["id", "text", "intent", "lang", "ambiguous_oui_non"]].reset_index(drop=True)


def _tfidf_union():
    return FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, strip_accents="unicode",
                                 sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True, strip_accents="unicode",
                                 sublinear_tf=True, min_df=2)),
    ])


class SentenceEncoder(BaseEstimator, TransformerMixin):
    """Transformeur sklearn autour de sentence-transformers (sans entraînement)."""

    def __init__(self, model_name=SBERT_NAME):
        self.model_name = model_name

    def fit(self, X, y=None):
        self._load()
        return self

    def _load(self):
        if not hasattr(self, "_model") or self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def transform(self, X):
        self._load()
        return self._model.encode(list(X), normalize_embeddings=True, show_progress_bar=False)

    def __getstate__(self):
        d = self.__dict__.copy()
        d["_model"] = None
        return d


def sbert_available():
    try:
        from sentence_transformers import SentenceTransformer
        SentenceTransformer(SBERT_NAME)
        return True
    except Exception:
        return False


def make_pipelines(embed_backend="auto", C_lr=10.0, C_svm=1.0, lsa_dim=150):
    if embed_backend == "auto":
        embed_backend = "sbert" if sbert_available() else "lsa"
    if embed_backend == "sbert":
        emb = Pipeline([("enc", SentenceEncoder()),
                        ("clf", LogisticRegression(C=C_lr, max_iter=2000, class_weight="balanced"))])
    else:
        emb = Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), strip_accents="unicode",
                                      sublinear_tf=True, min_df=2)),
            ("svd", TruncatedSVD(n_components=lsa_dim, random_state=SEED)),
            ("norm", Normalizer()),
            ("clf", LogisticRegression(C=C_lr, max_iter=2000, class_weight="balanced")),
        ])
    models = {
        "tfidf_lr": Pipeline([("feats", _tfidf_union()),
                              ("clf", LogisticRegression(C=C_lr, max_iter=2000, class_weight="balanced"))]),
        "tfidf_svm": Pipeline([("feats", _tfidf_union()),
                               ("clf", LinearSVC(C=C_svm, class_weight="balanced", random_state=SEED))]),
        "embed_lr": emb,
    }
    return models, embed_backend


def cv_predict(model, train, n_splits=5):
    """Prédictions out-of-fold avec GroupKFold sur template_id : aucun gabarit n'est vu à la fois
    en train et en validation (évite l'optimisme dû aux quasi-doublons)."""
    gkf = GroupKFold(n_splits=n_splits)
    return cross_val_predict(model, train["text"], train["intent"], groups=train["template_id"], cv=gkf)


def metrics(y_true, y_pred):
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    pw, rw, fw, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
    return {"accuracy": accuracy_score(y_true, y_pred), "precision_macro": p, "recall_macro": r, "f1_macro": f,
            "f1_weighted": fw}


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def predict_proba_any(model, texts):
    """Probabilités pour LR ; softmax(decision_function) pour SVM (score de confiance, non calibré)."""
    clf = model.steps[-1][1]
    if hasattr(clf, "predict_proba"):
        return model.predict_proba(texts)
    return softmax(model.decision_function(texts) * 3.0)
