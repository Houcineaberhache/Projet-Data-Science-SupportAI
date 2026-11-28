# Multi-stage build for the NLP intent-classifier service (FastAPI)
#
# Les modèles (*.joblib) ne sont pas versionnés (.gitignore) : ils sont entraînés
# pendant la construction de l'image à partir de data/train.csv (≈ 1-2 min).
#
# Build : docker build -t supportai-nlp ml/nlp
# Par défaut : sans PyTorch, `train` retient le Linear SVM TF-IDF (modèle servi).
# Vrais embeddings SBERT (image beaucoup plus lourde : torch) : docker build --build-arg WITH_SBERT=1 ...
#   -> `train` retient alors le meilleur modèle par CV, soit les embeddings (cf. README, « Modèle servi »).

# Stage 1: Build stage (dépendances + entraînement)
FROM python:3.11-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

ARG WITH_SBERT=0
RUN if [ "$WITH_SBERT" = "1" ]; then pip install --no-cache-dir sentence-transformers; fi

# Cache Hugging Face dans /opt/hf : le modèle téléchargé au build est recopié dans l'image finale
ENV HF_HOME=/opt/hf
RUN mkdir -p /opt/hf

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
COPY --from=builder --chown=appuser:appgroup /opt/hf /opt/hf
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
