"""Pydantic models for the Retrieval service contract."""
from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """Retrieved document snippet with source metadata and relevance score."""

    doc_name: str
    snippet: str
    score: float


class RetrievalRequest(BaseModel):
    """Request sent to the Retrieval (BM25 / vector search) service."""

    query: str
    top_k: int = Field(default=3, ge=1, le=20)


class RetrievalResponse(BaseModel):
    """Response returned by the Retrieval service."""

    query: str
    results: list[SourceDocument] = Field(default_factory=list)
