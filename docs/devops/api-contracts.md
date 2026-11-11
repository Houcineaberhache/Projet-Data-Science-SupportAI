# SupportAI – External Service API Contracts

The backend acts as an orchestrator. When external AI/ML microservices developed by teammates are ready, they can be plugged in by setting their base endpoint URLs in the environment.

If a service URL is unset, times out (**3-second limit**), or returns an error, the backend automatically and transparently falls back to its local mock logic so the application and UI demo never break.

---

## Configuration

Set these variables in `.env` (or environment / Docker Compose):

| Variable | Target Component | Default | Example |
|---|---|---|---|
| `NLP_SERVICE_URL` | NLP Intent Classification | `""` (mock fallback) | `http://nlp-service:8001/predict` |
| `RETRIEVAL_SERVICE_URL` | Lexical / Semantic Retrieval | `""` (mock fallback) | `http://retrieval-service:8002/retrieve` |
| `RAG_SERVICE_URL` | RAG Generation & Grounding | `""` (mock fallback) | `http://rag-service:8003/generate` |

---

## 1. NLP Intent Classifier Service

- **Method**: `POST`
- **Content-Type**: `application/json`
- **Timeout**: `3.0s`

### Request Body

```json
{
  "text": "Can I return my laptop and get a refund?"
}
```

| Field | Type | Description |
|---|---|---|
| `text` | `string` | The raw incoming user message |

### Response Body (`200 OK`)

```json
{
  "intent": "return_request",
  "confidence": 0.94
}
```

| Field | Type | Description |
|---|---|---|
| `intent` | `string` | Identified intent category (e.g., `return_request`, `order_tracking`, `product_info`, `other`) |
| `confidence` | `float` | Probability score between `0.0` and `1.0` |

---

## 2. Retrieval Service (BM25 / Dense / Hybrid)

- **Method**: `POST`
- **Content-Type**: `application/json`
- **Timeout**: `3.0s`

### Request Body

```json
{
  "query": "What is the return window for electronics?",
  "top_k": 3
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | Required | Search query |
| `top_k` | `integer` | `3` | Maximum number of chunks/documents to return (1-20) |

### Response Body (`200 OK`)

```json
{
  "query": "What is the return window for electronics?",
  "results": [
    {
      "doc_name": "POL-01_returns-exchanges.pdf",
      "snippet": "Products can be returned within 14 calendar days of delivery in their original condition.",
      "score": 0.892
    },
    {
      "doc_name": "FAQ-04_returns-refunds.jsonl",
      "snippet": "To request a return label, visit the support portal with your order ID.",
      "score": 0.741
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `query` | `string` | Echoed search query |
| `results` | `array[object]` | List of ranked document matches |
| `results[].doc_name` | `string` | Source document or chunk identifier |
| `results[].snippet` | `string` | Extracted text context |
| `results[].score` | `float` | Similarity score (higher = more relevant) |

---

## 3. RAG Generation Service

- **Method**: `POST`
- **Content-Type**: `application/json`
- **Timeout**: `3.0s`

### Request Body

```json
{
  "question": "Can I return my product?",
  "context_documents": [
    {
      "doc_name": "POL-01_returns-exchanges.pdf",
      "snippet": "Returns are accepted within 14 days of delivery.",
      "score": 0.89
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `question` | `string` | User's question |
| `context_documents` | `array[object]` | Relevant documents retrieved from the knowledge base |

### Response Body (`200 OK`)

```json
{
  "answer": "You can return your product within 14 days of delivery in its original condition.",
  "is_abstained": false,
  "sources": [
    {
      "doc_name": "POL-01_returns-exchanges.pdf",
      "snippet": "Returns are accepted within 14 days of delivery.",
      "score": 0.89
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `answer` | `string` | Grounded synthesized answer to display to the user |
| `is_abstained` | `boolean` | `true` if the model lacked sufficient evidence or abstained from answering |
| `sources` | `array[object]` | Citations/sources used to support the answer |

---

## Fallback Guarantees

If any microservice:
1. Is not configured (`URL` empty)
2. Cannot be reached (connection refused / DNS error)
3. Exceeds the 3-second timeout
4. Returns a non-200 HTTP status or invalid JSON

The orchestrator logs a warning and immediately falls back to built-in rule heuristics. Simulated order lookups (e.g., `ORD001`) are processed directly by the database and never depend on external services.
