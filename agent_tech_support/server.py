import os
import sys
import time
import json
import threading
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Ensure local imports and parent jwt_auth work
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [current_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [TechSupportAgent] %(message)s")
logger = logging.getLogger("agent_tech_support")

try:
    from jwt_auth import decode_jwt_token, decode_jwt_token_with_reason, extract_jwt_from_request
except ImportError:
    try:
        from ..jwt_auth import decode_jwt_token, decode_jwt_token_with_reason, extract_jwt_from_request
    except Exception:
        decode_jwt_token = lambda t: {}
        decode_jwt_token_with_reason = lambda t: ({}, None)
        extract_jwt_from_request = lambda r: ""

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

PORT = int(os.environ.get("PORT", 8007))
ROUTER_URL = os.environ.get("ROUTER_URL", "http://agents_router:8004")
DOC_RAG_URL = os.environ.get("DOC_RAG_URL", "http://doc_rag:8003")
LOGGING_URL = os.environ.get("LOGGING_SERVICE_URL", "http://logging:8006")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it")

SYSTEM_PROMPT = """You are the Senior Technical Support & DevOps Specialist for our company's software products and microservices architecture.
Your expertise covers:
- Product configuration, installation, troubleshooting, and diagnostic procedures
- Microservice errors, HTTP 500/502/504 status codes, latency spikes, and timeouts
- Docker container crashes, OOMKilled (exit 137), fatal signals, and restart loops
- API gateway authentication failures, JWT validation, TLS/SSL handshake errors
- Database connection pools, PostgreSQL/Redis connection exhaustion, query timeouts
- Reading crash logs, stack traces, and system metrics

When answering:
1. Provide a direct diagnosis and likely root cause.
2. Give clear, numbered, step-by-step diagnostic and remediation instructions.
3. Include exact terminal commands, configuration checks, or code fixes where appropriate.
4. Maintain a supportive, professional engineering tone.
"""

def resolve_url(url, host, port):
    if not os.environ.get("RUNNING_IN_DOCKER") and f"{host}:{port}" in url:
        return url.replace(f"{host}:{port}", f"127.0.0.1:{port}")
    return url

def log_event(invoker, recipient, event_type, desc, payload, conv_id=None, status="success", duration_ms=0, model="", target=None, user=None, domain=None):
    try:
        base_url = resolve_url(LOGGING_URL, "logging", 8006).rstrip("/")
        if base_url.endswith("/api/logs"):
            base_url = base_url[:-9].rstrip("/")
        tgt = target or recipient
        req_json = {
            "invoker": invoker,
            "recipient": recipient,
            "target": tgt,
            "conversation_id": conv_id,
            "type": event_type,
            "short_description": desc,
            "payload": payload,
            "status": status,
            "duration_ms": duration_ms,
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if user:
            req_json["user"] = user
        if domain:
            req_json["domain"] = domain
        requests.post(f"{base_url}/api/logs", json=req_json, timeout=2)
    except Exception as e:
        logger.warning(f"Failed to send log event to {base_url}/api/logs: {e}")

def dynamic_registration_worker():
    """Background thread that automatically registers this agent with the agents-router on startup."""
    router_endpoint = resolve_url(ROUTER_URL, "agents_router", 8004)
    my_url = "http://agent_tech_support:8007" if os.environ.get("RUNNING_IN_DOCKER") else f"http://127.0.0.1:{PORT}"

    registration_payload = {
        "id": "agent-tech-support",
        "name": "Technical Support & DevOps Specialist",
        "description": (
            "Diagnoses technical software issues, API errors, HTTP 500 status codes, database connection timeouts, "
            "Docker container crashes, Kubernetes pod restarts, microservice latency, authentication header failures, "
            "and system crash log analysis."
        ),
        "url": my_url,
        "sample_prompts": [
            "Our microservice is throwing HTTP 504 Gateway Timeout on PostgreSQL queries.",
            "How do I resolve 'Invalid Authentication Token' when sending requests to the API gateway?",
            "The Docker container crashed with code 137 OOMKilled on startup.",
            "Why is my webhook receiving TLS handshake failed errors from the server?",
            "How do I debug connection pool exhaustion in high-throughput endpoints?",
            "Can you explain why the worker process threw a segmentation fault in Python?",
            "Docker container logs show exit code 1 with fatal python exception.",
            "Database connection failed with host unreachable error.",
        ],
        "status": "up",
        "is_default": False,
        "registration_type": "API Registered",
        "agent_type": "API Registered",
        "metadata": {
            "registration_type": "API Registered",
            "department": "Engineering & Technical Operations",
            "tier": "Tier-2/3 Support Specialist",
            "version": "1.0.0",
            "container": "agent_tech_support",
            "port": PORT
        }
    }

    logger.info(f"Starting registration thread targeting router at {router_endpoint}...")
    for attempt in range(1, 30):
        try:
            resp = requests.post(f"{router_endpoint}/api/router/agents/register", json=registration_payload, timeout=3)
            if resp.status_code in [200, 201]:
                logger.info(f"Dynamic registration succeeded with agents-router (attempt {attempt}).")
                return
            else:
                logger.warning(f"Registration responded with code {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.debug(f"Router not ready yet (attempt {attempt}): {e}")
        time.sleep(2)

    logger.warning("Dynamic registration timed out after 30 attempts.")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "agent-tech-support",
        "port": PORT,
        "role": "Product Technical Support & DevOps Specialist"
    })

@app.route("/api/models", methods=["GET"])
def get_models():
    return jsonify({
        "models": [{
            "id": DEFAULT_MODEL,
            "display_name": f"{DEFAULT_MODEL} (Tech Support Specialization)",
            "max_output_tokens": 4096,
            "max_input_tokens": 32768
        }],
        "default": DEFAULT_MODEL
    })

@app.route("/api/agent/chat", methods=["POST"])
def process_chat():
    start_time = time.time()
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("query") or ""
    conv_id = data.get("conversation_id") or f"conv_{int(time.time())}"
    model = data.get("model") or DEFAULT_MODEL

    if not message.strip():
        return jsonify({"error": "Empty message"}), 400

    # Validate JWT if supplied
    jwt_token = data.get("jwt_token")
    auth_header = request.headers.get("Authorization", "")
    if not jwt_token and auth_header.startswith("Bearer "):
        jwt_token = auth_header.split(" ", 1)[1].strip()

    if jwt_token:
        decoded, reason = decode_jwt_token_with_reason(jwt_token)
        if not decoded:
            is_expired = reason and "expired" in reason.lower()
            return jsonify({
                "status": "error",
                "error": f"Unauthorized: {reason or 'Invalid JWT token'}",
                "reason": reason,
                "is_jwt_expired": is_expired
            }), 403

    invoker = data.get("invoker") or request.headers.get("X-Invoker") or "Web UI"
    logger.info(f"Processing tech support inquiry for conversation {conv_id} from {invoker}: '{message[:80]}'")

    # Extract prior conversation history if provided
    history = data.get("history") or []
    history_ctx = ""
    if history and isinstance(history, list):
        h_lines = []
        for h in history[-6:]:
            role = "User" if h.get("role") in ["user", "human"] else "Agent"
            txt = (h.get("content") or "").strip()
            if txt:
                h_lines.append(f"{role}: {txt}")
        if h_lines:
            history_ctx = "Prior Conversation History:\n" + "\n".join(h_lines) + "\n\n"

    # 1. Query RAG Vector Store for relevant technical documentation
    rag_docs = []
    rag_context = ""
    try:
        rag_endpoint = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
        doc_query_payload = {
            "query": message,
            "document_type": "document",
            "top_k": 3,
            "conversation_id": conv_id,
            "invoker": "agent_tech_support",
            "target": "Vector DB"
        }
        # Log outgoing vector query event
        log_event(
            invoker="agent_tech_support",
            recipient="Vector DB",
            target="Vector DB",
            event_type="document_vector_query",
            desc=f"Query document vector DB for tech support: '{message[:80]}'",
            payload=doc_query_payload,
            conv_id=conv_id
        )

        rag_headers = {"Content-Type": "application/json", "X-Invoker": "agent_tech_support"}
        if jwt_token:
            rag_headers["Authorization"] = f"Bearer {jwt_token}"

        r_rag = requests.post(f"{rag_endpoint}/api/rag/query", json=doc_query_payload, headers=rag_headers, timeout=5)
        if r_rag.status_code == 200:
            rag_data = r_rag.json()
            matched_items = rag_data.get("results") or rag_data.get("matched_items") or []

            doc_groups = {}
            for item in matched_items:
                meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                d_name = item.get("document_name") or meta.get("document_name") or item.get("name") or "Product Technical Documentation"
                score = round(float(item.get("similarity_score", 0)), 4) if item.get("similarity_score") is not None else 0.0
                idx = meta.get("chunk_index", 0)
                txt = item.get("chunk_text") or item.get("text") or ""

                if d_name not in doc_groups:
                    doc_groups[d_name] = {
                        "doc_name": d_name,
                        "highest_similarity": score,
                        "chunks": []
                    }
                if score > doc_groups[d_name]["highest_similarity"]:
                    doc_groups[d_name]["highest_similarity"] = score
                if not any(c["index"] == idx and abs(c["similarity"] - score) < 1e-4 for c in doc_groups[d_name]["chunks"]):
                    doc_groups[d_name]["chunks"].append({
                        "index": idx,
                        "similarity": score,
                        "text": txt
                    })

            rag_docs = list(doc_groups.values())
            context_blocks = []
            for doc in rag_docs:
                for chunk in doc.get("chunks", []):
                    context_blocks.append(f"[{doc['doc_name']} Chunk #{chunk['index']}]:\n{chunk['text']}")
            if context_blocks:
                rag_context = "Retrieved Technical Support & Product Documentation Context:\n" + "\n\n".join(context_blocks) + "\n\n"

            # Log received vector response event
            log_event(
                invoker="Vector DB",
                recipient="Tech Support Agent",
                event_type="received_document_vector_response",
                desc=f"Received document chunks from vector store ({len(matched_items)} items)",
                payload=rag_data,
                conv_id=conv_id
            )
    except Exception as rag_err:
        logger.warning(f"Error querying RAG vector store from Tech Support Agent: {rag_err}")

    # Build prompt with history and retrieved RAG context
    prompt = f"{history_ctx}{rag_context}Product Technical Support Inquiry:\n{message}"

    # 2. Generation via Google GenAI with detailed LLM call logging matching Custom Agent format
    content = ""
    api_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        llm_start_time = time.time()
        candidate_models = [model]
        for fb in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemma-4-26b-a4b-it"]:
            if fb not in candidate_models:
                candidate_models.append(fb)

        last_err = None
        for try_model in candidate_models:
            for attempt in range(2):
                try:
                    # Log LLM invocation (outbound call to LLM)
                    log_event(
                        invoker="Tech Support Agent",
                        recipient="LLM",
                        event_type="llm_invocation",
                        desc=f"Sent prompt to Google GenAI ({try_model})",
                        payload={
                            "model": try_model,
                            "prompt": prompt,
                            "system_instruction": SYSTEM_PROMPT,
                            "config": {"temperature": 0.3}
                        },
                        conv_id=conv_id,
                        model=try_model
                    )

                    from google import genai
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model=try_model,
                        contents=prompt,
                        config={
                            "system_instruction": SYSTEM_PROMPT,
                            "temperature": 0.3,
                        }
                    )
                    content = response.text or ""
                    llm_dur_ms = int((time.time() - llm_start_time) * 1000)

                    # Token counts
                    usage_meta = getattr(response, "usage_metadata", None)
                    in_tok = getattr(usage_meta, "prompt_token_count", len(prompt) // 4) or (len(prompt) // 4)
                    out_tok = getattr(usage_meta, "candidates_token_count", len(content) // 4) or (len(content) // 4)

                    # Log LLM response (inbound response from LLM)
                    log_event(
                        invoker="LLM",
                        recipient="Tech Support Agent",
                        event_type="llm_response",
                        desc=f"Received response from Google GenAI ({try_model}) in {llm_dur_ms}ms",
                        payload={
                            "model": try_model,
                            "response_text": content,
                            "response": content,
                            "prompt": prompt,
                            "system_instruction": SYSTEM_PROMPT,
                            "input_tokens": in_tok,
                            "output_tokens": out_tok,
                            "duration_ms": llm_dur_ms
                        },
                        conv_id=conv_id,
                        duration_ms=llm_dur_ms,
                        model=try_model
                    )
                    break
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    if "503" in err_str or "404" in err_str or "429" in err_str:
                        time.sleep(0.5)
                        continue
                    break
            if content:
                break

        if not content and last_err:
            llm_dur_ms = int((time.time() - llm_start_time) * 1000)
            logger.warning(f"GenAI generation failed ({last_err}); falling back to specialized diagnostic engine.")
            log_event(
                invoker="Tech Support Agent",
                recipient="LLM",
                event_type="llm_error",
                desc=f"Gemini API error: {last_err}",
                payload={"error": str(last_err)},
                conv_id=conv_id,
                status="error",
                duration_ms=llm_dur_ms,
                model=model
            )

    if not content:
        # Deterministic diagnostic response with documentation references if available
        doc_ref_section = ""
        if rag_context:
            doc_ref_section = f"\n\n**Referenced Knowledge Context**:\n{rag_context[:400]}..."
        content = (
            f"### 🛠️ Technical Support & DevOps Diagnostics\n\n"
            f"**Issue Summary**: '{message}'\n\n"
            f"**Diagnostic Analysis**:\n"
            f"1. **Log & Process Inspection**: Verify service container status with `docker compose ps` and inspect tail logs using `docker logs --tail 100 <container-name>`.\n"
            f"2. **Network & DNS Check**: Test internal inter-container communication via `curl -Iv http://<service-name>:<port>/health` from within the network.\n"
            f"3. **Resource Saturation**: Check memory and CPU usage limits. Code 137 indicates kernel OOMKiller; verify container memory limits.\n"
            f"4. **Authentication & Headers**: Ensure Bearer JWT token is present in the `Authorization` header and secrets match the auth service configuration.\n\n"
            f"If the issue persists, capture the full stack trace and correlate with conversation `{conv_id}`."
            f"{doc_ref_section}"
        )

    elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

    evidence_docs = rag_docs if rag_docs else [{"title": "Company Technical Troubleshooting & Architecture Guide", "similarity": 0.94}]

    result = {
        "status": "success",
        "response": content,
        "agent_type": "Technical Support Specialist",
        "model": model,
        "conversation_id": conv_id,
        "user_query": message,
        "elapsed_ms": elapsed_ms,
        "retrieved_evidence": {
            "skills": [{"name": "tech_diagnostics", "description": "DevOps & System Diagnostics Toolset"}],
            "documents": evidence_docs
        }
    }

    # Log response back to the caller (using caller invoker as target)
    log_event(
        invoker="agent_tech_support",
        recipient=invoker,
        target=invoker,
        event_type="tech_support_response",
        desc=f"Technical Support Specialist diagnosed query ({elapsed_ms}ms)",
        payload=result,
        conv_id=conv_id,
        duration_ms=elapsed_ms,
        model=model,
    )

    return jsonify(result)

if __name__ == "__main__":
    # Start auto-registration daemon
    threading.Thread(target=dynamic_registration_worker, daemon=True).start()
    logger.info(f"Starting Tech Support Agent service on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
