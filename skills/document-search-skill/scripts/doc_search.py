"""Document search tool for querying the ChromaDB documents vector store."""
from typing import Dict, Any, List, Optional

def query_documents(query: str, top_k: int = 5, threshold: float = 0.3) -> Dict[str, Any]:
    """Retrieve text chunks from the document vector store.
    
    Args:
        query: Query string to embed and search
        top_k: Maximum number of chunks to return (default: 5)
        threshold: Minimum similarity threshold (default: 0.3)
        
    Returns:
        Dictionary with count, chunks grouped by document, and status.
    """
    try:
        from services.vector_store import get_vector_store
        store = get_vector_store()
        results = store.query_documents(query=query, top_k=top_k, threshold=threshold)
        return {
            "query": query,
            "threshold": threshold,
            "count": len(results),
            "results": results,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}

# Aliases
search_documents = query_documents
get_document_chunks = query_documents
