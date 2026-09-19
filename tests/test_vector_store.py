"""Unit tests for ChromaDB Vector Store operations and deduplication."""
import pytest
from services.vector_store import get_vector_store

def test_chunking_logic():
    store = get_vector_store()
    text = "A" * 2500
    chunks = store.chunk_text(text, chunk_size=1000, chunk_overlap=200)
    assert len(chunks) == 3
    assert len(chunks[0]) == 1000

def test_document_ingestion_and_deduplication():
    store = get_vector_store()
    doc_name = "test_doc_dedup.txt"
    content = "Agentic RAG combines active tool reasoning with vector retrieval from private stores."

    # First ingestion
    res1 = store.add_document(doc_name=doc_name, content=content)
    assert res1["chunks_added"] >= 1

    # Ingest same doc content again - duplicate chunks should not be re-added
    res2 = store.add_document(doc_name=doc_name, content=content)
    assert res2["chunks_added"] == 0

    # Cleanup
    store.delete_document(doc_name)
