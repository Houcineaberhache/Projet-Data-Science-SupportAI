"""Entraîne les 3 modèles, évalue (CV groupée + test manuel), sauvegarde modèles et rapports.

Usage : python -m intent_clf.train
"""
import json

import joblib
import numpy as np
import pandas as pd

from .nlp_core import ROOT, load_data, load_pilot, make_pipelines, cv_predict, metrics

MODELS = ROOT / "models"
REPORTS = ROOT / "reports"


def main():
    MODELS.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    train, test = load_data()
    pilot = load_pilot()
    print("Pilot 20 :", "trouvé" if pilot is not None else "absent (évaluation ignorée)")
    pipes, backend = make_pipelines()
    print(f"Embedding backend: {backend}")

    results, errors = {}, []
    for name, pipe in pipes.items():
        oof = cv_predict(pipe, train)
        pipe.fit(train["text"], train["intent"])
        pred = pipe.predict(test["text"])
        results[name] = {"cv_grouped": metrics(train["intent"], oof), "test_manual": metrics(test["intent"], pred)}
        if pilot is not None:
            results[name]["pilot_20"] = metrics(pilot["intent"], pipe.predict(pilot["text"]))
        joblib.dump(pipe, MODELS / f"{name}.joblib")
        wrong = test[pred != test["intent"]].copy()
        wrong["predicted"] = pred[pred != test["intent"]]
        wrong["model"] = name
        errors.append(wrong)
        print(name, {k: round(v, 3) for k, v in results[name]["test_manual"].items()})

    best = max(results, key=lambda n: results[n]["cv_grouped"]["f1_macro"])  # sélection sur CV, pas sur le test
    # Seuil de confiance : percentile 10 des confiances OOF correctes du meilleur modèle (rejet des cas douteux)
    from sklearn.model_selection import GroupKFold, cross_val_predict
    proba = cross_val_predict(pipes[best], train["text"], train["intent"], groups=train["template_id"],
                              cv=GroupKFold(n_splits=5),
                              method="predict_proba" if hasattr(pipes[best].steps[-1][1], "predict_proba") else "decision_function")
    if proba.min() < 0 or proba.max() > 1.0001 or not hasattr(pipes[best].steps[-1][1], "predict_proba"):
        from .nlp_core import softmax
        proba = softmax(proba * 3.0)
    classes = np.array(sorted(train["intent"].unique()))
    correct = classes[proba.argmax(1)] == train["intent"].values
    threshold = float(np.percentile(proba.max(1)[correct], 10))

    config = {"best_model": best, "embedding_backend": backend, "confidence_threshold": round(threshold, 3),
              "classes": list(classes)}
    (MODELS / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False))
    (REPORTS / "metrics.json").write_text(json.dumps(results, indent=2))
    pd.concat(errors).to_csv(REPORTS / "errors_test_manual.csv", index=False)
    print("Best (by grouped CV macro-F1):", best, "| threshold:", config["confidence_threshold"])


if __name__ == "__main__":
    main()
