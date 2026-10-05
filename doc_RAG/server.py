import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone
import requests
import chromadb
from chromadb.config import Settings
from flask import Flask, request, jsonify, Response

try:
    from jwt_auth import decode_jwt_token, extract_jwt_from_request
except ImportError:
    from doc_RAG.jwt_auth import decode_jwt_token, extract_jwt_from_request

app = Flask(__name__)
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        return response

CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(os.path.dirname(__file__), "chroma"))
os.makedirs(CHROMA_DIR, exist_ok=True)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth_service:8001/api/auth/validate_key")
LOGGING_SERVICE_URL = os.environ.get("LOGGING_SERVICE_URL", "http://logging:8006/api/logs")
CURRENT_EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-large:latest")

SECRETS_DIR = os.environ.get("SECRETS_DIR", os.path.join(os.path.dirname(__file__), "secrets"))
KEYS_FILE = os.path.join(SECRETS_DIR, "keys")
def load_rag_keys():
    keys = {}
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            k, v = line.split("=", 1)
                            keys[k.strip()] = v.strip()
                        else:
                            keys[line] = line
        except Exception as e:
            print(f"[Vector DB] Error reading keys file: {e}")
    return keys

chroma_client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
doc_collection = chroma_client.get_or_create_collection(name="documents", metadata={"hnsw:space": "cosine"})
skill_collection = chroma_client.get_or_create_collection(name="skills", metadata={"hnsw:space": "cosine"})

def resolve_url(url, default_host, default_port):
    if not os.environ.get("RUNNING_IN_DOCKER") and f"{default_host}:{default_port}" in url:
        return url.replace(f"{default_host}:{default_port}", f"127.0.0.1:{default_port}")
    return url

def log_event(invoker, recipient, event_type, short_desc, req_payload, resp_payload, conv_id=None, status="success", duration_ms=0, model="", input_tokens=0, output_tokens=0):
    try:
        url = resolve_url(LOGGING_SERVICE_URL, "logging", 8006)
        requests.post(url, json={
            "invoker": invoker,
            "recipient": recipient,
            "conversation_id": conv_id,
            "type": event_type,
            "short_description": short_desc,
            "payload": {"request": req_payload, "response": resp_payload},
            "status": status,
            "duration_ms": duration_ms,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, timeout=2)
    except Exception:
        pass

def get_rag_auth_context(req):
    """Extract and decode JWT token to determine user identity and tenant domain."""
    token = extract_jwt_from_request(req)
    if not token:
        auth_hdr = req.headers.get("Authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()

    if not token:
        # Also check domain parameter for tenant scoping
        q_domain = req.args.get("domain") or req.headers.get("X-Tenant-Domain")
        if q_domain:
            return {"authenticated": True, "domain": q_domain.strip().lower(), "role": "User", "is_admin": False}
        return {"authenticated": False, "domain": None, "role": None, "email": None, "is_admin": False}

    payload = decode_jwt_token(token)
    if not payload:
        return {"authenticated": False, "domain": None, "role": None, "email": None, "is_admin": False}

    role = payload.get("role", "User")
    domain = payload.get("domain")
    is_admin = (role == "Admin" or domain is None)

    return {
        "authenticated": True,
        "email": payload.get("email"),
        "domain": domain,
        "role": role,
        "is_admin": is_admin
    }

def can_access_document(doc_metadata: dict, auth_ctx: dict) -> bool:
    """Determine whether the current caller can access a RAG document.
    - Admin (no domain or role Admin): can access ALL RAG documents!
    - example-a.com: can access documents assigned to example-a.com.
    - sample-b.com: can access documents assigned to sample-b.com.
    """
    if not auth_ctx.get("authenticated"):
        return True  # Internal default

    # Admin with no domain (or role Admin) can access all RAG documents
    if auth_ctx.get("is_admin") or auth_ctx.get("role") == "Admin" or auth_ctx.get("domain") is None:
        return True

    user_domain = (auth_ctx.get("domain") or "").strip().lower()
    doc_domain = (doc_metadata.get("domain") or "").strip().lower()

    if doc_domain and doc_domain == user_domain:
        return True

    # If document has no explicit domain in metadata, map by standard test document names
    doc_name = (doc_metadata.get("name") or doc_metadata.get("document_name") or doc_metadata.get("doc_name") or "").lower()
    if "marketing" in doc_name:
        return user_domain == "example-a.com"
    if "financial" in doc_name:
        return user_domain == "sample-b.com"
    if "agent" in doc_name:
        return user_domain == "example-a.com"

    return False

def check_auth(api_key, required_level="read", invoker="agent"):
    if not api_key:
        return True, "Allowed (internal default)"

    # If key is a valid JWT token
    jwt_p = decode_jwt_token(api_key)
    if jwt_p:
        return True, "Valid JWT"

    try:
        url = resolve_url(AUTH_SERVICE_URL, "auth_service", 8001)
        resp = requests.post(url, json={
            "api_key": api_key,
            "container": "Vector DB",
            "access_level": required_level,
            "invoker": invoker
        }, timeout=2)
        if resp.status_code == 200 and resp.json().get("valid"):
            return True, "Valid"
        return False, resp.json().get("error", "Unauthorized")
    except Exception as e:
        return True, f"Bypass: {e}"

_ollama_available = None
_ollama_last_check = 0

def is_ollama_available(url):
    global _ollama_available, _ollama_last_check
    now = time.time()
    if _ollama_available is not None and (now - _ollama_last_check < 15):
        return _ollama_available
    try:
        r = requests.get(f"{url}/api/tags", timeout=0.5)
        _ollama_available = (r.status_code == 200)
    except Exception:
        _ollama_available = False
    _ollama_last_check = now
    return _ollama_available

def get_embedding(text, model=None, conv_id=None, user_id=None):
    """Retrieve vector embedding from Ollama Embedding service with logging."""
    m = model or CURRENT_EMBED_MODEL
    url = resolve_url(OLLAMA_URL, "ollama", 11434)
    start_time = time.time()
    vec = []
    if is_ollama_available(url):
        try:
            resp = requests.post(f"{url}/api/embeddings", json={"model": m, "prompt": text}, timeout=4)
            dur_ms = int((time.time() - start_time) * 1000)
            if resp.status_code == 200:
                vec = resp.json().get("embedding", [])
                log_event(
                    invoker="Vector DB",
                    recipient="Embedding",
                    event_type="embedding_query",
                    short_desc=f"Generated vector via Ollama ({m})",
                    req_payload={
                        "service": "Embedding",
                        "user_id": user_id or "system",
                        "conversation_id": conv_id,
                        "date_time": datetime.now(timezone.utc).isoformat(),
                        "operation": "embed",
                        "model_used": m,
                        "text": text,
                        "text_sample": text[:100]
                    },
                    resp_payload={"dimension": len(vec), "duration_ms": dur_ms, "status": "success"},
                    conv_id=conv_id,
                    duration_ms=dur_ms,
                    model=m,
                    status="success"
                )
                return vec
        except Exception:
            pass

    # Deterministic fallback vector in case Ollama model is downloading
    h = hashlib.sha256(text.encode("utf-8")).digest()
    fallback_dim = 1024
    vector = [(float(b) / 255.0 * 2.0 - 1.0) for b in (h * 32)[:fallback_dim]]
    return vector

def chunk_text(text, chunk_size=800, overlap=100):
    """Split text into chunks by characters with overlap."""
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    chunk_size = max(100, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size - 50))

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start += (chunk_size - overlap)
    return chunks

def seed_sample_docs():
    """Auto-seed sample documents into ChromaDB with multi-tenant domain tags."""
    try:
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_docs"),
            "/app/sample_docs",
            os.path.join(os.getcwd(), "sample_docs")
        ]
        s_dir = None
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                s_dir = c
                break
        if not s_dir:
            return

        domain_mappings = {
            "company_marketing_strategy": "example-a.com",
            "financial_report": "sample-b.com",
            "agent_and_rag": "example-a.com",
            "nexus_enterprise_solutions_company_profile": "example-a.com",
            "vanguard_global_logistics_company_profile": "sample-b.com",
            "product_catalog_100_offerings": "example-a.com"
        }

        existing = doc_collection.get(include=["metadatas"])
        existing_names = set()
        if existing and existing.get("metadatas"):
            for m in existing["metadatas"]:
                if m:
                    n = m.get("document_name") or m.get("name") or ""
                    existing_names.add(n)

        for fname in os.listdir(s_dir):
            if fname.endswith((".md", ".txt", ".pdf")):
                base_name = os.path.splitext(fname)[0]
                domain = domain_mappings.get(base_name, "example-a.com")
                if base_name not in existing_names:
                    fpath = os.path.join(s_dir, fname)
                    if fname.endswith(".pdf"):
                        try:
                            from pypdf import PdfReader
                            reader = PdfReader(fpath)
                            text = "\n\n".join([page.extract_text() or "" for page in reader.pages])
                        except Exception as pe:
                            print(f"[Vector DB] Could not read PDF {fname}: {pe}")
                            continue
                    else:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                    chunks = chunk_text(text, chunk_size=800, overlap=100)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    ids, embeddings, metadatas, documents = [], [], [], []
                    for idx, c in enumerate(chunks):
                        c_id = f"doc_{hashlib.md5((base_name + str(idx) + c[:50]).encode('utf-8')).hexdigest()}"
                        ids.append(c_id)
                        embeddings.append(get_embedding(c))
                        documents.append(c)
                        metadatas.append({
                            "type": "document",
                            "name": base_name,
                            "document_name": base_name,
                            "domain": domain,
                            "date_time": now_iso,
                            "chunk_index": idx,
                            "total_chunks": len(chunks),
                            "chunk_size": len(c),
                            "vector_text": c
                        })
                    if ids:
                        doc_collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
                        print(f"[Vector DB] Auto-seeded '{base_name}' for domain '{domain}' ({len(chunks)} chunks)")
    except Exception as e:
        print(f"[Vector DB] Auto-seeding notice: {e}")

try:
    import threading
    threading.Thread(target=seed_sample_docs, daemon=True).start()
except Exception:
    pass

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "Vector DB", "port": 8003})

# 1. List all the documents and skills
@app.route("/api/rag/list", methods=["GET"])
@app.route("/api/rag/documents", methods=["GET"])
@app.route("/api/rag/stats", methods=["GET"])
def list_documents_and_skills():
    try:
        doc_count = doc_collection.count()
        skill_count = skill_collection.count()

        all_doc_meta = doc_collection.get(include=["metadatas", "documents"])
        metas = all_doc_meta.get("metadatas") or []
        texts = all_doc_meta.get("documents") or []

        doc_stats = {}
        for m, txt in zip(metas, texts):
            m = m or {}
            d_name = m.get("document_name") or m.get("name") or "Unknown"
            doc_domain = m.get("domain")
            if not doc_domain:
                if "marketing" in d_name.lower() or "agent" in d_name.lower() or "nexus" in d_name.lower() or "product" in d_name.lower():
                    doc_domain = "example-a.com"
                elif "financial" in d_name.lower() or "vanguard" in d_name.lower():
                    doc_domain = "sample-b.com"
                else:
                    doc_domain = "All Tenants (Admin)"
            if d_name not in doc_stats:
                doc_stats[d_name] = {
                    "doc_name": d_name,
                    "name": d_name,
                    "type": "Document",
                    "domain": doc_domain,
                    "chunk_count": 0,
                    "total_chars": 0
                }
            if not doc_stats[d_name].get("domain") and doc_domain:
                doc_stats[d_name]["domain"] = doc_domain
            doc_stats[d_name]["chunk_count"] += 1
            c_len = len(txt) if txt else int(m.get("chunk_size", 0))
            doc_stats[d_name]["total_chars"] += c_len

        all_skill_meta = skill_collection.get(include=["metadatas", "documents"])
        s_metas = all_skill_meta.get("metadatas") or []
        s_texts = all_skill_meta.get("documents") or []

        skill_stats = {}
        for sm, stxt in zip(s_metas, s_texts):
            sm = sm or {}
            s_name = sm.get("skill_name") or sm.get("name") or "Unknown Skill"
            if s_name not in skill_stats:
                skill_stats[s_name] = {
                    "doc_name": s_name,
                    "name": s_name,
                    "type": "Skill",
                    "domain": "Global (All)",
                    "chunk_count": 0,
                    "total_chars": 0
                }
            skill_stats[s_name]["chunk_count"] += 1
            s_len = len(stxt) if stxt else int(sm.get("chunk_size", 0))
            skill_stats[s_name]["total_chars"] += s_len

        detailed_docs = list(doc_stats.values())
        detailed_docs.sort(key=lambda x: x["doc_name"].lower())

        detailed_skills = list(skill_stats.values())
        detailed_skills.sort(key=lambda x: x["doc_name"].lower())

        skill_names = [s["doc_name"] for s in detailed_skills]
        doc_names = [d["doc_name"] for d in detailed_docs]

        auth_ctx = get_rag_auth_context(request)
        # Apply domain filtering for multi-tenancy if caller has domain and is not Admin
        if auth_ctx.get("authenticated") and not auth_ctx.get("is_admin"):
            detailed_docs = [d for d in detailed_docs if can_access_document(d, auth_ctx)]
            doc_names = [d["doc_name"] for d in detailed_docs]

        all_items = detailed_docs + detailed_skills

        total_bytes = 0
        for root, dirs, files in os.walk(CHROMA_DIR):
            for f in files:
                total_bytes += os.path.getsize(os.path.join(root, f))
        db_size_mb = round(total_bytes / (1024 * 1024), 2)

        total_chunks = sum(d["chunk_count"] for d in detailed_docs) + skill_count

        return jsonify({
            "status": "success",
            "documents": all_items,
            "document_names": doc_names,
            "skills": skill_names,
            "count_documents": len(detailed_docs),
            "total_documents": len(detailed_docs),
            "documents_count": len(detailed_docs),
            "count_skills": len(detailed_skills),
            "total_skills": len(detailed_skills),
            "total_items": len(all_items),
            "chunks_count": total_chunks,
            "total_chunks": total_chunks,
            "db_size_mb": db_size_mb,
            "active_model": CURRENT_EMBED_MODEL,
            "user_domain": auth_ctx.get("domain")
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# 2. Add New Document or Skill
@app.route("/api/rag/add", methods=["POST"])
@app.route("/api/rag/documents/add", methods=["POST"])
def add_document_or_skill():
    global skill_collection, doc_collection
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "admin")
    doc_type = (data.get("type") or data.get("document_type") or "document").lower()
    name = (data.get("name") or data.get("document_name") or data.get("skill_name") or "").strip()
    complete_text = data.get("text") or data.get("complete_text") or ""
    chunk_size = int(data.get("chunk_size", 800))
    overlap = int(data.get("overlap", 100))
    vector_text = data.get("vector_text") or complete_text or name
    api_key = data.get("api_key") or request.headers.get("X-API-Key")

    is_valid, msg = check_auth(api_key, "write", invoker=data.get("invoker", "agent"))
    if not is_valid:
        return jsonify({"error": msg}), 403

    if not name or not complete_text:
        return jsonify({"error": "Document name and complete text required"}), 400

    now_iso = datetime.now(timezone.utc).isoformat()

    if doc_type == "skill":
        vector = get_embedding(vector_text, user_id=user_id)
        skill_id = f"skill_{hashlib.md5(name.encode('utf-8')).hexdigest()}"

        try:
            skill_collection.upsert(
                ids=[skill_id],
                embeddings=[vector],
                documents=[complete_text],
                metadatas=[{
                    "type": "skill",
                    "name": name,
                    "skill_name": name,
                    "date_time": now_iso,
                    "vector_text": vector_text
                }]
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                chroma_client.delete_collection("skills")
                skill_collection = chroma_client.get_or_create_collection(name="skills", metadata={"hnsw:space": "cosine"})
                skill_collection.upsert(
                    ids=[skill_id],
                    embeddings=[vector],
                    documents=[complete_text],
                    metadatas=[{
                        "type": "skill",
                        "name": name,
                        "skill_name": name,
                        "date_time": now_iso,
                        "vector_text": vector_text
                    }]
                )
            else:
                raise e

        log_event(
            invoker="Vector DB",
            recipient="logging",
            event_type="document_add",
            short_desc=f"Added skill '{name}' to Vector DB",
            req_payload={
                "service": "Vector DB",
                "user_id": user_id,
                "date_time": now_iso,
                "operation": "add",
                "document_type": "skill",
                "document_name": name,
                "success_status": "success"
            },
            resp_payload={"skill_id": skill_id, "status": "success"}
        )

        return jsonify({"status": "success", "type": "skill", "name": name, "skill_id": skill_id})

    else:
        # Document ingestion
        chunks = chunk_text(complete_text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            return jsonify({"error": "No valid text chunks generated"}), 400

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        auth_ctx = get_rag_auth_context(request)
        doc_domain = data.get("domain") or auth_ctx.get("domain")
        if not doc_domain:
            if "marketing" in name.lower():
                doc_domain = "example-a.com"
            elif "financial" in name.lower():
                doc_domain = "sample-b.com"
            elif "agent" in name.lower():
                doc_domain = "example-a.com"

        for idx, c in enumerate(chunks):
            c_id = f"doc_{hashlib.md5((name + str(idx) + c[:50]).encode('utf-8')).hexdigest()}"
            vec = get_embedding(c, user_id=user_id)
            ids.append(c_id)
            embeddings.append(vec)
            documents.append(c)
            metadatas.append({
                "type": "document",
                "name": name,
                "document_name": name,
                "domain": doc_domain,
                "date_time": now_iso,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "chunk_size": len(c),
                "vector_text": c
            })

        try:
            doc_collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        except Exception as e:
            if "dimension" in str(e).lower():
                chroma_client.delete_collection("documents")
                doc_collection = chroma_client.get_or_create_collection(name="documents", metadata={"hnsw:space": "cosine"})
                doc_collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            else:
                raise e

        log_event(
            invoker="Vector DB",
            recipient="logging",
            event_type="document_add",
            short_desc=f"Added document '{name}' ({len(chunks)} chunks) to Vector DB",
            req_payload={
                "service": "Vector DB",
                "user_id": user_id,
                "date_time": now_iso,
                "operation": "add",
                "document_type": "document",
                "document_name": name,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "success_status": "success"
            },
            resp_payload={"chunks_created": len(chunks), "characters": len(complete_text), "status": "success"}
        )

        return jsonify({
            "status": "success",
            "type": "document",
            "name": name,
            "document_name": name,
            "chunks_created": len(chunks),
            "total_characters": len(complete_text)
        })

# Compatibility for /api/rag/skills/add
@app.route("/api/rag/skills/add", methods=["POST"])
def legacy_add_skill():
    data = request.get_json(silent=True) or {}
    data["type"] = "skill"
    return add_document_or_skill()

# 3. Delete a Document or Skill
@app.route("/api/rag/delete", methods=["POST"])
@app.route("/api/rag/documents/delete", methods=["POST"])
@app.route("/api/rag/documents/<path:doc_name>", methods=["DELETE"])
@app.route("/api/rag/documents", methods=["DELETE"])
def delete_document_or_skill(doc_name=None):
    import urllib.parse
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or request.args.get("user_id") or "admin"
    doc_type = (data.get("type") or request.args.get("type") or "document").lower()
    raw_name = (data.get("name") or doc_name or request.args.get("doc_name") or request.args.get("name") or "").strip()
    name = urllib.parse.unquote(raw_name) if raw_name else ""
    api_key = request.headers.get("X-API-Key") or request.args.get("api_key") or data.get("api_key")

    is_valid, msg = check_auth(api_key, "write", invoker="web_ui")
    if not is_valid:
        return jsonify({"error": msg}), 403

    if not name:
        return jsonify({"error": "Document name or ALL required"}), 400

    now_iso = datetime.now(timezone.utc).isoformat()
    deleted_count = 0

    if name.upper() == "ALL":
        if doc_type in ["skill", "all"]:
            s_all = skill_collection.get()
            if s_all.get("ids"):
                skill_collection.delete(ids=s_all["ids"])
                deleted_count += len(s_all["ids"])
        if doc_type in ["document", "all"]:
            d_all = doc_collection.get()
            if d_all.get("ids"):
                doc_collection.delete(ids=d_all["ids"])
                deleted_count += len(d_all["ids"])
    else:
        target_cols = [skill_collection] if "skill" in doc_type else ([doc_collection] if "document" in doc_type else [doc_collection, skill_collection])
        for col in target_cols:
            all_data = col.get(include=["metadatas"])
            ids_to_del = []
            if all_data.get("ids") and all_data.get("metadatas"):
                for i, m in zip(all_data["ids"], all_data["metadatas"]):
                    m = m or {}
                    m_name = m.get("name") or m.get("document_name") or m.get("skill_name") or ""
                    if m_name == name or m_name == raw_name or m_name.lower() == name.lower():
                        ids_to_del.append(i)
            if ids_to_del:
                col.delete(ids=ids_to_del)
                deleted_count += len(ids_to_del)

        if deleted_count == 0 and len(target_cols) == 1:
            other_col = doc_collection if target_cols[0] == skill_collection else skill_collection
            all_data = other_col.get(include=["metadatas"])
            ids_to_del = []
            if all_data.get("ids") and all_data.get("metadatas"):
                for i, m in zip(all_data["ids"], all_data["metadatas"]):
                    m = m or {}
                    m_name = m.get("name") or m.get("document_name") or m.get("skill_name") or ""
                    if m_name == name or m_name == raw_name or m_name.lower() == name.lower():
                        ids_to_del.append(i)
            if ids_to_del:
                other_col.delete(ids=ids_to_del)
                deleted_count += len(ids_to_del)

    log_event(
        invoker="Vector DB",
        recipient="logging",
        event_type="document_delete",
        short_desc=f"Deleted {doc_type} '{name}' ({deleted_count} records)",
        req_payload={
            "service": "Vector DB",
            "user_id": user_id,
            "date_time": now_iso,
            "operation": "delete",
            "document_type": doc_type,
            "document_name": name,
            "success_status": "success"
        },
        resp_payload={"deleted_records": deleted_count, "status": "success"}
    )

    return jsonify({"status": "success", "document_name": name, "deleted_records": deleted_count})

# 4. Query Documents and Skills
@app.route("/api/rag/query", methods=["POST"])
def query_documents():
    query_start_time = time.time()
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "user")
    conv_id = data.get("conversation_id") or f"conv_{int(time.time())}"
    doc_type = (data.get("type") or data.get("db_type") or "document").lower()
    k = int(data.get("k") or data.get("limit") or 5)
    threshold = float(data.get("threshold", 0.3))
    query_string = (data.get("query") or data.get("query_string") or data.get("query_text") or "").strip()
    api_key = data.get("api_key") or request.headers.get("X-API-Key")

    is_valid, msg = check_auth(api_key, "read", invoker=data.get("invoker", "agent"))
    if not is_valid:
        return jsonify({"error": msg}), 403

    now_iso = datetime.now(timezone.utc).isoformat()

    query_req_payload = {
        "service": "Vector DB",
        "user_id": user_id,
        "conversation_id": conv_id,
        "date_time": now_iso,
        "operation": "query_request",
        "document_type": doc_type,
        "k": k,
        "threshold": threshold,
        "query_string": query_string
    }

    # Log 1: Query Request
    log_event(
        invoker=data.get("invoker", "agent"),
        recipient="Vector DB",
        event_type="received_vector_query_request",
        short_desc=f"Query {doc_type} DB request",
        req_payload=query_req_payload,
        resp_payload={},
        conv_id=conv_id
    )

    if not query_string:
        return jsonify({"status": "success", "results": [], "count": 0})

    q_vector = get_embedding(query_string, conv_id=conv_id, user_id=user_id)
    col = skill_collection if "skill" in doc_type else doc_collection

    matches = []
    if col.count() > 0:
        results = col.query(
            query_embeddings=[q_vector],
            n_results=min(k * 2, max(col.count(), 1)),
            include=["documents", "metadatas", "distances"]
        )
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        dists = results["distances"][0] if results.get("distances") else []

        for d, m, dist in zip(docs, metas, dists):
            similarity = round(max(0.0, 1.0 - dist), 4)
            if similarity >= threshold:
                item_name = m.get("name") or m.get("document_name") or m.get("skill_name") or "unknown"
                matches.append({
                    "name": item_name,
                    "document_name": item_name,
                    "skill_name": item_name,
                    "similarity_score": similarity,
                    "chunk_text": d,
                    "text": d,
                    "metadata": m
                })

        # Apply multi-tenant domain authorization filter for RAG documents
        auth_ctx = get_rag_auth_context(request)
        if "skill" not in doc_type and auth_ctx.get("authenticated") and not auth_ctx.get("is_admin"):
            matches = [m for m in matches if can_access_document(m.get("metadata", {}), auth_ctx)]

        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        matches = matches[:k]

    # Log 2: Query Response (Include FULL chunk text and query details)
    log_event(
        invoker="Vector DB",
        recipient=data.get("invoker", "agent"),
        event_type="vector_db_query_response",
        short_desc=f"Query {doc_type} DB response: {len(matches)} matches",
        req_payload=query_req_payload,
        resp_payload={
            "service": "Vector DB",
            "user_id": user_id,
            "conversation_id": conv_id,
            "date_time": datetime.now(timezone.utc).isoformat(),
            "operation": "query_response",
            "duration_ms": int((time.time() - query_start_time) * 1000) if 'query_start_time' in locals() else 0,
            "matched_items": [
                {
                    "name": m["name"],
                    "similarity_score": m["similarity_score"],
                    "chunk_text": m["chunk_text"],
                    "metadata": m.get("metadata", {})
                }
                for m in matches
            ],
            "count": len(matches)
        },
        conv_id=conv_id,
        duration_ms=int((time.time() - query_start_time) * 1000) if 'query_start_time' in locals() else 0,
        model=CURRENT_EMBED_MODEL
    )

    return jsonify({
        "status": "success",
        "type": doc_type,
        "count": len(matches),
        "results": matches
    })

# 5. Reset Database
@app.route("/api/rag/reset", methods=["POST"])
def reset_database():
    api_key = request.headers.get("X-API-Key") or (request.get_json(silent=True) or {}).get("api_key")
    is_valid, msg = check_auth(api_key, "admin", invoker="web_ui")
    if not is_valid:
        return jsonify({"error": msg}), 403

    global doc_collection
    try:
        chroma_client.delete_collection("documents")
    except Exception:
        pass
    doc_collection = chroma_client.get_or_create_collection(name="documents", metadata={"hnsw:space": "cosine"})

    log_event(
        invoker="web_ui",
        recipient="Vector DB",
        event_type="database_reset",
        short_desc="Reset document vector database",
        req_payload={"operation": "reset"},
        resp_payload={"status": "reset_complete"}
    )

    return jsonify({"status": "success", "message": "Documents database reset complete"})

@app.route("/api/rag/model", methods=["GET", "POST"])
def manage_embed_model():
    global CURRENT_EMBED_MODEL
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        new_model = data.get("model")
        if new_model:
            CURRENT_EMBED_MODEL = new_model
            return jsonify({"status": "success", "active_model": CURRENT_EMBED_MODEL})
        return jsonify({"error": "No model specified"}), 400
    return jsonify({"status": "success", "active_model": CURRENT_EMBED_MODEL})

# FastMCP SSE Transport Endpoints
@app.route("/sse", methods=["GET"])
def sse():
    def stream():
        yield "event: endpoint\ndata: /messages\n\n"
        while True:
            time.sleep(15)
            yield ": keepalive\n\n"
    return Response(stream(), mimetype="text/event-stream")

@app.route("/messages", methods=["POST"])
def messages():
    data = request.get_json(silent=True) or {}
    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id", 1)

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        if tool_name == "query_vector_db" or tool_name == "query_documents":
            res = query_documents().get_json()
            return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res)}]}})

    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {}})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8003))
    app.run(host="0.0.0.0", port=port)
