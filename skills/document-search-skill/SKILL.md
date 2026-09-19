---
name: document-search-skill
description: Get the list of text chunks from the document vector database. Use this tool whenever the user asks questions about company documents, marketing strategy, financial reports, Agent and RAG architecture, or any topic that requires factual information from the private knowledge base.
triggers:
  - search documents for [topic]
  - what does the document say about [topic]
  - marketing strategy
  - financial report
  - agent and RAG architecture
  - information about [topic] from docs
---

# Document Search Skill

## Description
Performs semantic similarity retrieval against the private ChromaDB document vector database, returning the most relevant text chunks, similarity scores, and document source titles.

## SOP & Tool Execution
When the user asks for information contained in the private document repository:
1. Formulate a search `query` based on the user's intent.
2. Specify the maximum number of chunks (`top_k`, default: 5) and similarity `threshold` (default: 0.3).
3. Invoke `doc_search.query_documents`:
```json
{
  "tool": "doc_search.query_documents",
  "arguments": {
    "query": "Agentic RAG architecture and workflows",
    "top_k": 5,
    "threshold": 0.3
  }
}
```
4. Synthesize the returned document chunks into an accurate, grounded response with source citations.
