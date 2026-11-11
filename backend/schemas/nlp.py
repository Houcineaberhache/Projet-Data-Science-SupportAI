"""Pydantic models for the NLP intent-classification service contract."""
from pydantic import BaseModel


class NLPRequest(BaseModel):
    """Request sent to the NLP intent-classifier service."""

    text: str


class NLPResponse(BaseModel):
    """Response returned by the NLP intent-classifier service."""

    intent: str
    confidence: float
