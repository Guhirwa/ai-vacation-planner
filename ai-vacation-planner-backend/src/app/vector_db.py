"""
vector_db.py

Initialises the ChromaDB persistent client and exposes the travel knowledge
base collection. All services that need to read from or write to the vector
store import get_knowledge_collection() from here.
"""

import chromadb
from app.config import settings

KNOWLEDGE_COLLECTION_NAME = "travel_knowledge"


def get_knowledge_collection() -> chromadb.Collection:
    """Initialise a persistent ChromaDB client and return the travel knowledge
    base collection, creating it if it does not already exist.

    Returns:
        The ChromaDB Collection instance for the travel knowledge base.
    """
    client = chromadb.PersistentClient(path=settings.chroma_persist_path)
    return client.get_or_create_collection(name=KNOWLEDGE_COLLECTION_NAME)
