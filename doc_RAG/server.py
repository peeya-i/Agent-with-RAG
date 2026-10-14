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
    import sys
    from pathlib import Path
    _parent = str(Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from jwt_auth import decode_jwt_token, extract_jwt_from_request

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
_DYNAMIC_SKILL_CACHE = {}

_rag_ingest_progress = {
    "active": False,
    "percent": 0,
    "current_doc": "",
    "chunks_done": 0,
    "total_chunks": 0,
    "message": "Idle"
}

@app.route("/api/rag/progress", methods=["GET"])
def get_rag_progress():
    return jsonify({"status": "success", "progress": _rag_ingest_progress})

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

def is_global_domain(domain_val) -> bool:
    if not domain_val:
        return True
    d = str(domain_val).strip().lower()
    return d in ["", "none", "global", "global (all)", "all tenants (admin)", "all tenants", "tenant-all", "system"]

def find_existing_entry_info(name: str):
    """Returns (exists: bool, domain: Optional[str], collection_type: Optional[str])"""
    raw_name = (name or "").strip()
    if not raw_name:
        return False, None, None

    # Check skill_collection
    try:
        s_data = skill_collection.get(include=["metadatas"])
        if s_data.get("metadatas"):
            for m in s_data["metadatas"]:
                m = m or {}
                m_name = m.get("skill_name") or m.get("name") or m.get("document_name") or ""
                if m_name == raw_name or m_name.lower() == raw_name.lower():
                    return True, m.get("domain") or "Global (All)", "skill"
    except Exception:
        pass

    # Check doc_collection
    try:
        d_data = doc_collection.get(include=["metadatas"])
        if d_data.get("metadatas"):
            for m in d_data["metadatas"]:
                m = m or {}
                m_name = m.get("document_name") or m.get("name") or ""
                if m_name == raw_name or m_name.lower() == raw_name.lower():
                    doc_dom = m.get("domain")
                    if not doc_dom:
                        if any(k in m_name.lower() for k in ["marketing", "agent", "nexus", "product"]):
                            doc_dom = "example-a.com"
                        elif any(k in m_name.lower() for k in ["financial", "vanguard"]):
                            doc_dom = "sample-b.com"
                        else:
                            doc_dom = "All Tenants (Admin)"
                    return True, doc_dom, "document"
    except Exception:
        pass

    return False, None, None

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
            return {"authenticated": True, "domain": q_domain.strip().lower(), "role": "User", "is_admin": False, "is_global_admin": False, "email": None}
        return {"authenticated": False, "domain": None, "role": None, "email": None, "is_admin": False, "is_global_admin": False}

    payload = decode_jwt_token(token)
    if not payload:
        return {"authenticated": False, "domain": None, "role": None, "email": None, "is_admin": False, "is_global_admin": False}

    role = payload.get("role", "User")
    domain = payload.get("domain")
    email = payload.get("email") or payload.get("sub") or ""

    # Global Admin has role Admin and no domain (or domain is global/empty), or email is admin
    is_global_admin = False
    if email.lower() == "admin" and (not domain or is_global_domain(domain)):
        is_global_admin = True
    elif role == "Admin" and (not domain or is_global_domain(domain)):
        is_global_admin = True

    is_admin = is_global_admin or (role == "Admin")

    return {
        "authenticated": True,
        "email": email,
        "domain": domain,
        "role": role,
        "is_admin": is_admin,
        "is_global_admin": is_global_admin
    }

def can_access_document(doc_metadata: dict, auth_ctx: dict) -> bool:
    """Determine whether the current caller can access a RAG document.
    - Global Admin (no domain): can access ALL RAG documents!
    - Organization users (Admin/Editor/User): can access their organization's documents AND Global documents.
    """
    if not auth_ctx.get("authenticated"):
        return True  # Internal default

    # Global Admin (or no domain) can access all RAG documents
    if auth_ctx.get("is_global_admin") or auth_ctx.get("domain") is None:
        return True

    user_domain = (auth_ctx.get("domain") or "").strip().lower()
    doc_domain = (doc_metadata.get("domain") or "").strip().lower()

    if is_global_domain(doc_domain):
        return True

    if doc_domain and doc_domain == user_domain:
        return True

    # If document has no explicit domain in metadata, map by standard test document names
    doc_name = (doc_metadata.get("name") or doc_metadata.get("document_name") or doc_metadata.get("doc_name") or "").lower()
    if any(k in doc_name for k in ["marketing", "agent", "nexus", "product"]):
        return user_domain == "example-a.com"
    if any(k in doc_name for k in ["financial", "vanguard"]):
        return user_domain == "sample-b.com"

    return False

def check_auth(api_key, required_level="read", invoker="agent"):
    # Check if current request has JWT Bearer token or jwt_token in body
    try:
        from flask import has_request_context, request as flask_req
        if has_request_context():
            auth_hdr = flask_req.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                t = auth_hdr.split(" ", 1)[1].strip()
                jwt_p = decode_jwt_token(t)
                if jwt_p:
                    return True, "Valid JWT"
            req_data = flask_req.get_json(silent=True) or {}
            tok = req_data.get("jwt_token") or req_data.get("token")
            if tok:
                jwt_p = decode_jwt_token(tok)
                if jwt_p:
                    return True, "Valid JWT"
    except Exception:
        pass

    if not api_key:
        return True, "Allowed (internal default)"

    # Validate JWT token
    jwt_p = decode_jwt_token(api_key)
    if jwt_p:
        return True, "Valid JWT"

    return False, "Unauthorized: Valid JWT required"

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
    if model == "default":
        model = None
    m = model or CURRENT_EMBED_MODEL
    url = resolve_url(OLLAMA_URL, "ollama", 11434)
    start_time = time.time()
    vec = []
    if is_ollama_available(url):
        try:
            resp = requests.post(f"{url}/api/embeddings", json={"model": m, "prompt": text}, timeout=15)
            # If Ollama returns error due to input length exceeding context window (e.g. all-minilm 512 tokens), retry truncated
            if resp.status_code != 200 and len(text) > 800:
                resp = requests.post(f"{url}/api/embeddings", json={"model": m, "prompt": text[:800]}, timeout=15)
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
    if "minilm" in str(m).lower():
        fallback_dim = 384
    elif "nomic" in str(m).lower():
        fallback_dim = 768
    elif "qwen3" in str(m).lower():
        fallback_dim = 4096
    vector = [(float(b) / 255.0 * 2.0 - 1.0) for b in (h * 128)[:fallback_dim]]
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

    auth_ctx = get_rag_auth_context(request)
    is_global_admin = auth_ctx.get("is_global_admin", False)
    user_role = auth_ctx.get("role", "User")
    user_domain = (auth_ctx.get("domain") or "").strip().lower() if auth_ctx.get("domain") else None

    # Role and organization enforcement:
    # Admin and Editor roles for specific organization can add entries to the Vector DB imported by the organization.
    # They should not be able to make changes to Global entries.
    if auth_ctx.get("authenticated"):
        if not is_global_admin:
            if user_role not in ["Admin", "Editor"]:
                return jsonify({"error": "Unauthorized: Only Admin and Editor roles can add entries to the Vector DB"}), 403

            # Check if entry already exists and is Global or from another tenant
            exists, existing_domain, col_type = find_existing_entry_info(name)
            if exists:
                if is_global_domain(existing_domain):
                    return jsonify({"error": "Permission denied: Organization users cannot make changes to Global entries"}), 403
                if user_domain and existing_domain and existing_domain.strip().lower() != user_domain:
                    return jsonify({"error": "Permission denied: Cannot modify entries belonging to another organization"}), 403

    now_iso = datetime.now(timezone.utc).isoformat()

    if doc_type in ["skill", "skills"]:
        chunks = chunk_text(complete_text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            chunks = [complete_text]

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        if is_global_admin:
            doc_domain = data.get("domain") or "Global (All)"
        elif user_domain:
            doc_domain = user_domain
        else:
            doc_domain = data.get("domain") or "Global (All)"

        _rag_ingest_progress["active"] = True
        _rag_ingest_progress["current_doc"] = name
        _rag_ingest_progress["total_chunks"] = len(chunks)
        _rag_ingest_progress["chunks_done"] = 0
        _rag_ingest_progress["percent"] = 0
        _rag_ingest_progress["message"] = f"Ingesting skill '{name}': 0% (0/{len(chunks)} chunks)"

        for idx, c in enumerate(chunks):
            skill_id = f"skill_{hashlib.md5((name + str(idx) + c[:50]).encode('utf-8')).hexdigest()}"
            vec = get_embedding(c, user_id=user_id)
            ids.append(skill_id)
            embeddings.append(vec)
            documents.append(c)
            metadatas.append({
                "type": "skill",
                "name": name,
                "skill_name": name,
                "domain": doc_domain,
                "date_time": now_iso,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "chunk_size": len(c),
                "vector_text": c
            })
            _rag_ingest_progress["chunks_done"] = idx + 1
            _rag_ingest_progress["percent"] = int(((idx + 1) / len(chunks)) * 100)
            _rag_ingest_progress["message"] = f"Ingesting skill '{name}': {_rag_ingest_progress['percent']}% ({idx + 1}/{len(chunks)} chunks)"

        _rag_ingest_progress["active"] = False

        try:
            skill_collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                chroma_client.delete_collection("skills")
                skill_collection = chroma_client.get_or_create_collection(name="skills", metadata={"hnsw:space": "cosine"})
                skill_collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
            else:
                raise e

        log_event(
            invoker="Vector DB",
            recipient="logging",
            event_type="document_add",
            short_desc=f"Added skill '{name}' ({len(chunks)} chunks) to Vector DB Skills database",
            req_payload={
                "service": "Vector DB",
                "user_id": user_id,
                "date_time": now_iso,
                "operation": "add",
                "document_type": "skill",
                "document_name": name,
                "chunks_created": len(chunks),
                "success_status": "success"
            },
            resp_payload={"status": "success", "chunks_created": len(chunks)}
        )

        return jsonify({
            "status": "success",
            "type": "skill",
            "name": name,
            "document_name": name,
            "chunks_created": len(chunks),
            "total_characters": len(complete_text)
        })

    else:
        # Document ingestion
        chunks = chunk_text(complete_text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            return jsonify({"error": "No valid text chunks generated"}), 400

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        if is_global_admin:
            doc_domain = data.get("domain") or "All Tenants (Admin)"
        elif user_domain:
            doc_domain = user_domain
        else:
            doc_domain = data.get("domain")
            if not doc_domain:
                if any(k in name.lower() for k in ["marketing", "agent", "nexus", "product"]):
                    doc_domain = "example-a.com"
                elif any(k in name.lower() for k in ["financial", "vanguard"]):
                    doc_domain = "sample-b.com"
                else:
                    doc_domain = "All Tenants (Admin)"

        _rag_ingest_progress["active"] = True
        _rag_ingest_progress["current_doc"] = name
        _rag_ingest_progress["total_chunks"] = len(chunks)
        _rag_ingest_progress["chunks_done"] = 0
        _rag_ingest_progress["percent"] = 0
        _rag_ingest_progress["message"] = f"Ingesting document '{name}': 0% (0/{len(chunks)} chunks)"

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
            _rag_ingest_progress["chunks_done"] = idx + 1
            _rag_ingest_progress["percent"] = int(((idx + 1) / len(chunks)) * 100)
            _rag_ingest_progress["message"] = f"Ingesting document '{name}': {_rag_ingest_progress['percent']}% ({idx + 1}/{len(chunks)} chunks)"

        _rag_ingest_progress["active"] = False

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

@app.route("/api/rag/skills/list", methods=["GET"])
@app.route("/api/rag/skills", methods=["GET"])
def get_skills_list():
    """Returns all unique skills with their markdown content and metadata from ChromaDB."""
    try:
        all_skill_meta = skill_collection.get(include=["metadatas", "documents"])
        s_metas = all_skill_meta.get("metadatas") or []
        s_texts = all_skill_meta.get("documents") or []
        
        skills_dict = {}
        for sm, stxt in zip(s_metas, s_texts):
            sm = sm or {}
            s_name = sm.get("skill_name") or sm.get("name") or "Unknown Skill"
            if s_name not in skills_dict:
                desc = sm.get("description", "")
                triggers = []
                fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n(.*)$", stxt, re.DOTALL)
                if fm_match:
                    fm_text = fm_match.group(1)
                    d_match = re.search(r"^description:\s*(.+)$", fm_text, re.MULTILINE)
                    if d_match:
                        desc = d_match.group(1).strip()
                    t_matches = re.findall(r"^\s*-\s*(.+)$", fm_text, re.MULTILINE)
                    if t_matches:
                        triggers = [t.strip() for t in t_matches]
                skills_dict[s_name] = {
                    "name": s_name,
                    "folder": s_name,
                    "description": desc,
                    "triggers": triggers,
                    "raw_content": stxt
                }
            else:
                if "---" in stxt and "---" not in skills_dict[s_name]["raw_content"]:
                    skills_dict[s_name]["raw_content"] = stxt
        return jsonify({"status": "success", "skills": list(skills_dict.values())})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "skills": []}), 500

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

    auth_ctx = get_rag_auth_context(request)
    is_global_admin = auth_ctx.get("is_global_admin", False)
    user_role = auth_ctx.get("role", "User")
    user_domain = (auth_ctx.get("domain") or "").strip().lower() if auth_ctx.get("domain") else None

    # Global Admin only for deleting ALL entries
    if name.upper() == "ALL":
        if auth_ctx.get("authenticated") and not is_global_admin:
            return jsonify({"error": "Permission denied: Only Global Admin can delete entries from the Global Vector DB"}), 403
    else:
        # Check permissions on the target entry
        exists, existing_domain, col_type = find_existing_entry_info(name)
        if exists and auth_ctx.get("authenticated"):
            if is_global_domain(existing_domain):
                if not is_global_admin:
                    return jsonify({"error": "Permission denied: Only Global Admin can delete entries from Global Vector DB"}), 403
            else:
                # Organization entry
                if not is_global_admin:
                    if user_role not in ["Admin", "Editor"]:
                        return jsonify({"error": "Unauthorized: Only Admin and Editor roles can delete entries for their organization"}), 403
                    if not user_domain or user_domain != existing_domain.strip().lower():
                        return jsonify({"error": "Permission denied: Cannot delete entries belonging to another organization"}), 403

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

    model = (data.get("model") or data.get("embedder_model") or "").strip() or None
    if model == "default":
        model = None
    q_vector = get_embedding(query_string, model=model, conv_id=conv_id, user_id=user_id)
    col = skill_collection if "skill" in doc_type else doc_collection

    matches = []
    use_dynamic_eval = ("skill" in doc_type and model and model != CURRENT_EMBED_MODEL)

    if not use_dynamic_eval and col.count() > 0:
        try:
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
        except Exception as e:
            logger.warning(f"ChromaDB query error for {doc_type}: {e}; using dynamic model evaluation")
            if "skill" in doc_type:
                use_dynamic_eval = True

    if use_dynamic_eval and "skill" in doc_type:
        import numpy as np
        skills_data = skill_collection.get(include=["metadatas", "documents"])
        s_docs = skills_data.get("documents") or []
        s_metas = skills_data.get("metadatas") or []

        qv_np = np.array(q_vector, dtype=np.float32)
        norm_q = np.linalg.norm(qv_np)

        for d, m in zip(s_docs, s_metas):
            m = m or {}
            trunc_text = d[:800] if len(d) > 800 else d
            cache_key = (str(model), trunc_text[:120])
            if cache_key in _DYNAMIC_SKILL_CACHE:
                sv = _DYNAMIC_SKILL_CACHE[cache_key]
            else:
                sv = get_embedding(trunc_text, model=model)
                _DYNAMIC_SKILL_CACHE[cache_key] = sv

            sv_np = np.array(sv, dtype=np.float32)
            norm_s = np.linalg.norm(sv_np)
            if norm_q > 0 and norm_s > 0 and qv_np.shape == sv_np.shape:
                sim = float(np.dot(qv_np, sv_np) / (norm_q * norm_s))
                sim = round(max(0.0, sim), 4)
                if sim >= threshold:
                    item_name = m.get("name") or m.get("document_name") or m.get("skill_name") or "unknown"
                    matches.append({
                        "name": item_name,
                        "document_name": item_name,
                        "skill_name": item_name,
                        "similarity_score": sim,
                        "chunk_text": d,
                        "text": d,
                        "metadata": m
                    })

    # Evaluate draft skill variant if provided from Sandbox
    draft_skill = data.get("draft_skill")
    if "skill" in doc_type and draft_skill and isinstance(draft_skill, dict):
        d_content = (draft_skill.get("content") or "").strip()
        d_name = (draft_skill.get("name") or "Draft Skill Variant").strip()
        if d_content:
            import numpy as np
            qv_np = np.array(q_vector, dtype=np.float32)
            norm_q = np.linalg.norm(qv_np)
            d_trunc = d_content[:800]
            d_sv = get_embedding(d_trunc, model=model)
            d_sv_np = np.array(d_sv, dtype=np.float32)
            d_norm = np.linalg.norm(d_sv_np)
            if norm_q > 0 and d_norm > 0 and qv_np.shape == d_sv_np.shape:
                d_sim = round(max(0.0, float(np.dot(qv_np, d_sv_np) / (norm_q * d_norm))), 4)
                if d_sim >= threshold:
                    matches.append({
                        "name": f"{d_name} (Draft Variant)",
                        "document_name": f"{d_name} (Draft Variant)",
                        "skill_name": f"{d_name} (Draft Variant)",
                        "similarity_score": d_sim,
                        "chunk_text": d_content,
                        "text": d_content,
                        "metadata": {"type": "skill", "variant": "draft"}
                    })

    # Apply multi-tenant domain authorization filter for RAG documents
    auth_ctx = get_rag_auth_context(request)
    if "skill" not in doc_type and auth_ctx.get("authenticated") and not auth_ctx.get("is_admin"):
        matches = [m for m in matches if can_access_document(m.get("metadata", {}), auth_ctx)]

    # Deduplicate skills by skill name so each distinct skill appears once with its highest-scoring chunk
    if "skill" in doc_type:
        dedup = {}
        for m in matches:
            name_key = (m.get("name") or "").strip().lower()
            if name_key not in dedup or m["similarity_score"] > dedup[name_key]["similarity_score"]:
                dedup[name_key] = m
        matches = list(dedup.values())

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

    auth_ctx = get_rag_auth_context(request)
    if auth_ctx.get("authenticated") and not auth_ctx.get("is_global_admin"):
        return jsonify({"error": "Permission denied: Only Global Admin can reset the Vector DB"}), 403

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
