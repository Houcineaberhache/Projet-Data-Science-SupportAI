"""Pydantic models for the RAG generation service contract."""
from pydantic import BaseModel, Field

from schemas.retrieval import SourceDocument


class RAGRequest(BaseModel):
    """Request sent to the RAG generation service."""

    question: str
    context_documents: list[SourceDocument] = Field(default_factory=list)


class RAGResponse(BaseModel):
    """Response returned by the RAG generation service."""

    answer: str
    is_abstained: bool = False
    sources: list[SourceDocument] = Field(default_factory=list)
