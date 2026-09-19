"""Dual ChromaDB Vector Store managing skills and documents collections."""
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import chromadb
from chromadb.config import Settings
import config
from services.ollama_service import get_ollama_service
from services.log_service import get_log_service

class VectorStore:
    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or config.CHROMA_DB_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.ollama = get_ollama_service()
        self.logger = get_log_service()

        # Initialize collections
        self.skills_col = self.client.get_or_create_collection(
            name="skills_store",
            metadata={"hnsw:space": "cosine"}
        )
        self.docs_col = self.client.get_or_create_collection(
            name="documents_store",
            metadata={"hnsw:space": "cosine"}
        )

    # -------------------------------------------------------------------------
    # Skills Vector Store Operations
    # -------------------------------------------------------------------------
    def add_skill(
        self,
        skill_name: str,
        description: str,
        full_content: str,
        metadata: Optional[Dict[str, Any]] = None,
        conversation_id: str = "system"
    ):
        """Index a skill record using embedding of 'name + description' and full SKILL.md."""
        embed_input = f"{skill_name}: {description}"
        vector = self.ollama.get_embedding(embed_input, conversation_id=conversation_id)
        
        meta = metadata or {}
        meta.update({
            "name": skill_name,
            "description": description[:500],
        })

        # Sanitize metadata values to primitive types for Chroma
        clean_meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in meta.items()}

        self.skills_col.upsert(
            ids=[skill_name],
            embeddings=[vector],
            documents=[full_content],
            metadatas=[clean_meta]
        )

    def skill_exists(self, skill_name: str) -> bool:
        """Check if skill is already in the database."""
        res = self.skills_col.get(ids=[skill_name])
        return bool(res and res.get("ids"))

    def query_skills(
        self,
        query: str,
        threshold: float = config.DEFAULT_SKILL_THRESHOLD,
        top_k: int = 5,
        conversation_id: str = "system"
    ) -> List[Dict[str, Any]]:
        """Query skills store and filter by cosine similarity threshold."""
        start_time = time.time()
        vectorizer_name = self.ollama.active_model
        
        # Log skill search request
        self.logger.log_event(
            conversation_id=conversation_id,
            event_type="skill search",
            invoker="Agent Orchestrator",
            target="Skills Vector Store",
            short_description=f"Skill search query: '{query}' (threshold={threshold})",
            payload={"query": query, "threshold": threshold, "vectorizer": vectorizer_name},
        )

        try:
            query_vector = self.ollama.get_embedding(query, conversation_id=conversation_id)
            results = self.skills_col.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            elapsed_ms = (time.time() - start_time) * 1000

            matched_skills = []
            if results and results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    skill_id = results["ids"][0][i]
                    doc = results["documents"][0][i] if results["documents"] else ""
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    
                    # Cosine similarity score = 1.0 - cosine_distance
                    similarity = round(max(0.0, min(1.0, 1.0 - distance)), 4)
                    
                    if similarity >= threshold:
                        matched_skills.append({
                            "skill_name": skill_id,
                            "similarity": similarity,
                            "content": doc,
                            "metadata": meta,
                            "description": meta.get("description", ""),
                        })

            # Sort by similarity descending
            matched_skills.sort(key=lambda x: x["similarity"], reverse=True)

            # Log skill search response
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="skill search",
                invoker="Skills Vector Store",
                target="Agent Orchestrator",
                short_description=f"Found {len(matched_skills)} skill(s) above threshold {threshold}",
                payload={
                    "vectorizer": vectorizer_name,
                    "matched_count": len(matched_skills),
                    "skills": [
                        {"name": s["skill_name"], "similarity": s["similarity"]}
                        for s in matched_skills
                    ],
                },
                elapsed_ms=elapsed_ms,
            )

            return matched_skills

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="skill search",
                invoker="Skills Vector Store",
                target="Agent Orchestrator",
                short_description=f"Skill search failed: {str(e)}",
                payload={"error": str(e), "vectorizer": vectorizer_name},
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            return []

    # -------------------------------------------------------------------------
    # Document Vector Store Operations
    # -------------------------------------------------------------------------
    def chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """Partition text into chunks with defined character size and overlap."""
        if not text:
            return []
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= text_len:
                break
            start += max(1, chunk_size - chunk_overlap)
            
        return chunks

    def add_document(
        self,
        doc_name: str,
        content: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        conversation_id: str = "system"
    ) -> Dict[str, Any]:
        """Chunk and ingest a document with strict chunk deduplication."""
        raw_chunks = self.chunk_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        # Deduplication check: compute content hash for each chunk
        seen_hashes = set()
        unique_chunks = []
        for ch in raw_chunks:
            ch_hash = hashlib.sha256(ch.encode("utf-8")).hexdigest()
            if ch_hash not in seen_hashes:
                seen_hashes.add(ch_hash)
                unique_chunks.append((ch_hash, ch))

        added_chunks = 0
        total_chars = len(content)

        for idx, (ch_hash, ch_text) in enumerate(unique_chunks):
            chunk_id = f"{doc_name}#chunk_{idx}_{ch_hash[:8]}"
            # Verify if identical chunk already exists in collection
            existing = self.docs_col.get(ids=[chunk_id])
            if existing and existing.get("ids"):
                continue

            vector = self.ollama.get_embedding(ch_text, conversation_id=conversation_id)
            self.docs_col.upsert(
                ids=[chunk_id],
                embeddings=[vector],
                documents=[ch_text],
                metadatas=[{
                    "doc_name": doc_name,
                    "chunk_index": idx,
                    "char_count": len(ch_text),
                    "hash": ch_hash,
                }]
            )
            added_chunks += 1

        return {
            "doc_name": doc_name,
            "chunks_created": len(unique_chunks),
            "chunks_added": added_chunks,
            "total_chars": total_chars,
        }

    def delete_document(self, doc_name: str) -> int:
        """Delete all chunks belonging to a document."""
        # Find all chunk IDs with matching metadata doc_name
        res = self.docs_col.get(where={"doc_name": doc_name})
        ids_to_delete = res.get("ids", [])
        if ids_to_delete:
            self.docs_col.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    def query_documents(
        self,
        query: str,
        top_k: int = config.DEFAULT_RAG_CHUNKS,
        threshold: float = config.DEFAULT_DOC_THRESHOLD,
        conversation_id: str = "system"
    ) -> List[Dict[str, Any]]:
        """Query documents store and return results grouped by document."""
        start_time = time.time()
        
        # Log document search request
        self.logger.log_event(
            conversation_id=conversation_id,
            event_type="document search",
            invoker="Agent",
            target="Documents Vector Store",
            short_description=f"Document search: '{query}' (threshold={threshold})",
            payload={"query": query, "top_k": top_k, "threshold": threshold},
        )

        try:
            query_vector = self.ollama.get_embedding(query, conversation_id=conversation_id)
            results = self.docs_col.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            elapsed_ms = (time.time() - start_time) * 1000

            doc_groups: Dict[str, Dict[str, Any]] = {}
            if results and results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    doc_text = results["documents"][0][i] if results["documents"] else ""
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    similarity = round(max(0.0, min(1.0, 1.0 - distance)), 4)
                    
                    if similarity >= threshold:
                        doc_name = meta.get("doc_name", "Unknown Document")
                        if doc_name not in doc_groups:
                            doc_groups[doc_name] = {
                                "doc_name": doc_name,
                                "highest_similarity": similarity,
                                "chunks": [],
                            }
                        
                        doc_groups[doc_name]["chunks"].append({
                            "chunk_id": results["ids"][0][i],
                            "similarity": similarity,
                            "text": doc_text,
                            "index": meta.get("chunk_index", 0),
                        })
                        if similarity > doc_groups[doc_name]["highest_similarity"]:
                            doc_groups[doc_name]["highest_similarity"] = similarity

            # Format sorted list of documents
            grouped_results = list(doc_groups.values())
            grouped_results.sort(key=lambda x: x["highest_similarity"], reverse=True)

            # Log document search response
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="document search",
                invoker="Documents Vector Store",
                target="Agent",
                short_description=f"Retrieved context from {len(grouped_results)} document(s)",
                payload={
                    "total_documents": len(grouped_results),
                    "documents": [
                        {"doc_name": d["doc_name"], "chunks_count": len(d["chunks"]), "top_score": d["highest_similarity"]}
                        for d in grouped_results
                    ]
                },
                elapsed_ms=elapsed_ms,
            )

            return grouped_results

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="document search",
                invoker="Documents Vector Store",
                target="Agent",
                short_description=f"Document search failed: {str(e)}",
                payload={"error": str(e)},
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            return []

    def get_ingested_documents(self) -> List[Dict[str, Any]]:
        """List all ingested documents with chunk count and total character count."""
        res = self.docs_col.get(include=["metadatas"])
        docs_summary: Dict[str, Dict[str, Any]] = {}
        
        if res and res.get("metadatas"):
            for meta in res["metadatas"]:
                doc_name = meta.get("doc_name", "Unknown Document")
                chars = int(meta.get("char_count", 0))
                if doc_name not in docs_summary:
                    docs_summary[doc_name] = {
                        "doc_name": doc_name,
                        "chunk_count": 0,
                        "total_chars": 0,
                    }
                docs_summary[doc_name]["chunk_count"] += 1
                docs_summary[doc_name]["total_chars"] += chars

        return sorted(docs_summary.values(), key=lambda x: x["doc_name"])

    def get_database_statistics(self) -> Dict[str, Any]:
        """Calculate statistics: chunk count, document count, and database disk size in MB."""
        ingested = self.get_ingested_documents()
        total_chunks = sum(d["chunk_count"] for d in ingested)
        total_docs = len(ingested)

        # Calculate directory size in MB
        total_bytes = 0
        if self.persist_dir.exists():
            for root, _, files in os.walk(self.persist_dir):
                for f in files:
                    fp = Path(root) / f
                    total_bytes += fp.stat().st_size

        size_mb = round(total_bytes / (1024 * 1024), 2)
        return {
            "total_chunks": total_chunks,
            "total_documents": total_docs,
            "db_size_mb": size_mb,
            "skills_count": self.skills_col.count(),
        }

    def reset_database(self):
        """Clear all records from documents vector database."""
        try:
            self.client.delete_collection("documents_store")
        except Exception:
            pass
        self.docs_col = self.client.get_or_create_collection(
            name="documents_store",
            metadata={"hnsw:space": "cosine"}
        )

    def reset_skills_database(self):
        """Clear all records from skills vector database."""
        try:
            self.client.delete_collection("skills_store")
        except Exception:
            pass
        self.skills_col = self.client.get_or_create_collection(
            name="skills_store",
            metadata={"hnsw:space": "cosine"}
        )

# Singleton instance
_VECTOR_STORE: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = VectorStore()
    return _VECTOR_STORE
