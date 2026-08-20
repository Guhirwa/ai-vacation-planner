"""
knowledge_service.py

Handles ingestion and retrieval of travel knowledge documents.
Documents are chunked, embedded using a local sentence-transformers model,
and stored in ChromaDB for semantic search during itinerary generation.
"""

from sentence_transformers import SentenceTransformer
from app.vector_db import get_knowledge_collection
from app.config import settings

# Load the embedding model once at module level to avoid reloading on every call
_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split a long text into overlapping chunks for embedding.

    Args:
        text: The raw text to split.
        chunk_size: Maximum number of characters per chunk.
        overlap: Number of characters to overlap between consecutive chunks
                 so context is not lost at chunk boundaries.

    Returns:
        A list of text chunks.
    """
    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


async def add_document(
    destination: str,
    content: str,
    source: str = "manual",
) -> int:
    """Chunk a travel document and store all chunks in the vector store.

    Args:
        destination: The destination the document is about (e.g. "Paris").
        content: The full text content of the document.
        source: Where the document came from (e.g. "manual", "guide", "tips").

    Returns:
        The number of chunks stored.
    """
    chunks = chunk_text(content)
    if not chunks:
        return 0

    embeddings = _embedding_model.encode(chunks).tolist()
    ids = [f"{destination.lower()}_{source}_{index}" for index in range(len(chunks))]
    metadatas = [
        {"destination": destination.lower(), "source": source, "chunk_index": index}
        for index in range(len(chunks))
    ]

    collection = get_knowledge_collection()
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return len(chunks)


async def search_knowledge(
    destination: str,
    query: str | None = None,
) -> str:
    """Search the knowledge base for travel information about a destination.

    Args:
        destination: The destination to search for.
        query: Optional additional search query. If not provided, searches
               by destination name alone.

    Returns:
        A single string of the most relevant knowledge chunks joined by
        double newlines, ready to inject into the LLM prompt. Returns an
        empty string if no results are found.
    """
    search_text = f"{destination} {query}" if query else destination
    query_embedding = _embedding_model.encode([search_text]).tolist()

    collection = get_knowledge_collection()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=settings.knowledge_top_k,
        where={"destination": destination.lower()},
    )

    documents = results.get("documents") or [[]]
    matched_chunks = documents[0]
    if not matched_chunks:
        return ""
    return "\n\n".join(matched_chunks)
