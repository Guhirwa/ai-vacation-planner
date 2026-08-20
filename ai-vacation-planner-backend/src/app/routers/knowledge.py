"""
knowledge.py

Router for the travel knowledge base API.
Exposes endpoints for adding documents and searching the knowledge base.
"""

from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeAddResponse,
    KnowledgeSearchResponse,
)
from app.services.knowledge_service import add_document, search_knowledge

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post("", response_model=KnowledgeAddResponse, status_code=status.HTTP_201_CREATED)
@router.post(
    "/",
    response_model=KnowledgeAddResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_knowledge(
    knowledge: KnowledgeCreate,
    current_user: User = Depends(get_current_user),
) -> KnowledgeAddResponse:
    """Add a travel knowledge document to the vector store.

    Args:
        knowledge: The document payload (destination, content, source).
        current_user: The authenticated user, injected via dependency.

    Returns:
        The number of chunks stored and a confirmation message.
    """
    chunks_stored = await add_document(
        destination=knowledge.destination,
        content=knowledge.content,
        source=knowledge.source,
    )
    return KnowledgeAddResponse(destination=knowledge.destination, chunks_stored=chunks_stored)


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search(
    destination: str,
    query: str | None = None,
    current_user: User = Depends(get_current_user),
) -> KnowledgeSearchResponse:
    """Search the knowledge base for travel information about a destination.

    Args:
        destination: The destination to search for.
        query: Optional additional search text to refine the query.
        current_user: The authenticated user, injected via dependency.

    Returns:
        The matched knowledge chunks joined into a single string.
    """
    results = await search_knowledge(destination=destination, query=query)
    return KnowledgeSearchResponse(destination=destination, query=query, results=results)
