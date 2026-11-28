# Multi-stage build for the NLP intent-classifier service (FastAPI)
#
# Les modèles (*.joblib) ne sont pas versionnés (.gitignore) : ils sont entraînés
# pendant la construction de l'image à partir de data/train.csv (≈ 1-2 min).
#
# Build : docker build -t supportai-nlp ml/nlp
# Vrais embeddings SBERT (ajoute ~2 Go : torch) : docker build --build-arg WITH_SBERT=1 ...
#   -> inutile tant que le meilleur modèle est le Linear SVM TF-IDF (cf. models/config.json).

# Stage 1: Build stage (dépendances + entraînement)
FROM python:3.11-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

ARG WITH_SBERT=0
RUN if [ "$WITH_SBERT" = "1" ]; then pip install --no-cache-dir sentence-transformers; fi

COPY intent_clf ./intent_clf
COPY data ./data
COPY api ./api
RUN python -m intent_clf.train

# Stage 2: Production runtime stage
FROM python:3.11-slim AS runner

WORKDIR /app

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=appuser:appgroup /app /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
