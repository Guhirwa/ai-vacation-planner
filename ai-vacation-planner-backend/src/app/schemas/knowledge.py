"""
knowledge.py

Pydantic schemas for the knowledge base API.
"""

from pydantic import BaseModel


class KnowledgeCreate(BaseModel):
    """Request schema for adding a document to the knowledge base."""

    destination: str
    content: str
    source: str = "manual"


class KnowledgeAddResponse(BaseModel):
    """Response schema returned after a document is added to the knowledge base."""

    destination: str
    chunks_stored: int
    message: str = "Knowledge added successfully"


class KnowledgeSearchResponse(BaseModel):
    """Response schema for a knowledge base search query."""
    destination: str
    query: str | None = None
    results: str
