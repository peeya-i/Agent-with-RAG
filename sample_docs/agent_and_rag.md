# AI Agents and Retrieval-Augmented Generation (RAG)

## Overview of Agentic AI
Artificial Intelligence agents represent an evolution from passive text completion models to autonomous entities capable of reasoning, planning, and taking sequential actions in an environment. While standard large language models (LLMs) rely entirely on parametric knowledge stored within their weights during training, AI Agents utilize procedural tools, external APIs, and dynamic memory stores to accomplish complex multi-step objectives.

## The Role of Retrieval-Augmented Generation (RAG)
Retrieval-Augmented Generation bridges the gap between static model weights and dynamic private knowledge. In a traditional RAG pipeline:
1. **Ingestion & Chunking**: Source documents such as PDFs, markdown files, technical specifications, and knowledge bases are partitioned into semantically meaningful chunks with defined character sizes and overlap.
2. **Vector Embedding**: Each chunk is transformed into a dense floating-point vector using an embedding model (such as Ollama's `bge-m3`, `nomic-embed-text`, or `all-minilm`).
3. **Vector Indexing**: High-dimensional vectors and corresponding text chunks are stored in an indexed vector database like ChromaDB, enabling rapid approximate nearest neighbor (ANN) retrieval using cosine similarity or Euclidean distance metrics.
4. **Context Injection**: When a user submits a query, the query is vectorized using the identical embedding model. The top-k most relevant chunks exceeding a similarity threshold are retrieved and injected directly into the LLM system prompt as verified evidence.

## Agentic Workflows vs Classic RAG
Classic RAG operates as a rigid single-turn pipeline: Retrieve -> Augment -> Generate. In contrast, an **Agentic RAG** system treats retrieval as an active procedural tool. The agent's reasoning engine determines:
- Whether retrieval is even necessary for the user's intent.
- Which specific knowledge collection or skill vector store should be queried.
- Whether the retrieved context is sufficient, or if follow-up search queries, sub-queries, or alternate procedural tools (like real-time weather, stock search, or database queries) must be invoked.
- How to synthesize contradictory or fragmented pieces of evidence into a coherent, verifiable answer.

## Tool Orchestration and Multi-Turn Reasoning
In advanced orchestrators (like Google ADK and Custom Multi-Turn ReAct loops), agents evaluate intermediate observations before producing the final response. Limiting reasoning loops to a configured `max_turns` prevents infinite cycling while ensuring deterministic task execution.
