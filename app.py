"""Core Flask Orchestrator for Agent-with-RAG application."""
import atexit
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, List

from flask import Flask, render_template, request, jsonify, send_from_directory
import requests

import config
from services.log_service import get_log_service
from services.ollama_service import get_ollama_service
from services.vector_store import get_vector_store
from services.llm_service import get_llm_service
from services.skill_manager import get_skill_manager
from services.telemetry_service import get_telemetry_service
from services.agent_orchestrator import get_agent_orchestrator
from services.google_adk_agent import get_google_adk_agent

app = Flask(
    __name__,
    template_folder=str(config.TEMPLATES_DIR),
    static_folder=str(config.STATIC_DIR),
)

# Initialize service singletons
logger = get_log_service()
ollama = get_ollama_service()
vector_store = get_vector_store()
llm_service = get_llm_service()
skill_manager = get_skill_manager()
telemetry = get_telemetry_service()
custom_agent = get_agent_orchestrator()
adk_agent = get_google_adk_agent()

# Startup Routine:
# 1. Check Ollama running; start if needed
# 2. Sync skills directory to ChromaDB skills_store
# 3. Seed sample documents if database is empty
def initialize_system():
    print("[Agent-with-RAG] Initializing system...")
    ollama_ready = ollama.ensure_running()
    if ollama_ready:
        print(f"[Agent-with-RAG] Ollama is active (model: {ollama.active_model}). Started by app: {ollama.started_by_app}")
    else:
        print("[Agent-with-RAG] Warning: Ollama service could not be connected or started.")

    # Synchronize skills into skills vector database
    try:
        res = skill_manager.scan_and_sync_skills()
        print(f"[Agent-with-RAG] Skills synced: {res['added']} added, {res['skipped']} already indexed.")
    except Exception as e:
        print(f"[Agent-with-RAG] Skill sync warning: {e}")

    # Seed sample_docs if documents store is empty
    try:
        stats = vector_store.get_database_statistics()
        if stats["total_documents"] == 0 and config.SAMPLE_DOCS_DIR.exists():
            print("[Agent-with-RAG] Ingesting initial sample_docs into document vector store...")
            for doc_file in config.SAMPLE_DOCS_DIR.iterdir():
                if doc_file.is_file() and doc_file.suffix.lower() in [".md", ".txt", ".pdf"]:
                    content = doc_file.read_text(encoding="utf-8", errors="ignore")
                    vector_store.add_document(doc_name=doc_file.name, content=content)
            print("[Agent-with-RAG] Sample documents ingested.")
    except Exception as e:
        print(f"[Agent-with-RAG] Initial docs ingestion warning: {e}")

# Register shutdown hook
def cleanup_resources():
    print("[Agent-with-RAG] Running shutdown cleanup...")
    ollama.shutdown()

atexit.register(cleanup_resources)

# -----------------------------------------------------------------------------
# Frontend Route
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -----------------------------------------------------------------------------
# System & Health API
# -----------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def api_health():
    """Periodically check Agent API health and status of all supporting services."""
    ollama_ok = ollama.is_running()
    vector_ok = vector_store.skills_col is not None and vector_store.docs_col is not None
    llm_ok = bool(config.GEMINI_API_KEY)
    
    agent_status = "Online" if (ollama_ok and vector_ok and llm_ok) else "Degraded"
    if not ollama_ok:
        agent_status = "Ollama Offline"
    elif not llm_ok:
        agent_status = "API Key Missing"

    return jsonify({
        "status": agent_status,
        "services": {
            "agent": "Healthy" if agent_status == "Online" else "Degraded",
            "ollama": "Running" if ollama_ok else "Stopped",
            "ollama_active_model": ollama.active_model,
            "ollama_started_by_app": ollama.started_by_app,
            "vector_store": "Connected" if vector_ok else "Error",
            "llm_provider": "Configured" if llm_ok else "Missing Key",
            "default_model": config.DEFAULT_LLM_MODEL,
        }
    })

@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """Graceful system shutdown requiring exact confirmation text."""
    data = request.get_json() or {}
    confirmation = data.get("confirmation", "").strip()
    
    if confirmation != "Shutdown the service":
        return jsonify({
            "error": "Confirmation phrase mismatch. Must type 'Shutdown the service'.",
            "status": "forbidden"
        }), 400

    print("[Agent-with-RAG] Shutdown confirmed by user. Terminating services...")
    
    def delayed_exit():
        time.sleep(1.0)
        cleanup_resources()
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=delayed_exit, daemon=True).start()
    return jsonify({
        "status": "shutting_down",
        "message": "Shutdown sequence initiated. Closing all services started by the app."
    })

# -----------------------------------------------------------------------------
# Models API
# -----------------------------------------------------------------------------
@app.route("/api/models", methods=["GET"])
def api_models():
    """Return active Google AI Studio text generation models."""
    models = llm_service.get_active_models()
    return jsonify({
        "default_model": config.DEFAULT_LLM_MODEL,
        "models": models,
        "default_custom_endpoint": config.DEFAULT_CUSTOM_ENDPOINT,
    })

# -----------------------------------------------------------------------------
# Skills API
# -----------------------------------------------------------------------------
@app.route("/api/skills", methods=["GET"])
def api_skills():
    """Return list of available skills."""
    skills = skill_manager.list_available_skills()
    return jsonify({"skills": skills})

@app.route("/api/skills/update", methods=["POST"])
def api_skills_update():
    """Scan skills/ folder and load new skills not currently in database."""
    res = skill_manager.scan_and_sync_skills()
    return jsonify({
        "status": "success",
        "result": res,
        "message": f"Scanned {res['scanned']} skills. Added {res['added']} new skills. Skipped {res['skipped']}."
    })

# -----------------------------------------------------------------------------
# Chat & Knowledge Synthesis API
# -----------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Process chat message with either Custom Agent or Google ADK Agent."""
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    agent_choice = data.get("agent", "Custom Agent")
    model = data.get("model", config.DEFAULT_LLM_MODEL)
    temperature = float(data.get("temperature", config.DEFAULT_TEMPERATURE))
    max_tokens = int(data.get("max_tokens", config.DEFAULT_MAX_TOKENS))
    max_turns = min(10, max(1, int(data.get("max_turns", config.DEFAULT_MAX_TURNS))))
    rag_chunks = int(data.get("rag_chunks", config.DEFAULT_RAG_CHUNKS))
    skill_mode = data.get("skill_mode", "Vector Store")
    skill_threshold = float(data.get("skill_threshold", config.DEFAULT_SKILL_THRESHOLD))
    doc_threshold = float(data.get("doc_threshold", config.DEFAULT_DOC_THRESHOLD))
    custom_endpoint = data.get("custom_endpoint") if model == "Custom Model" else None

    # Dispatch to selected agent
    if "ADK" in agent_choice:
        result = adk_agent.process_message(
            message=message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_turns=max_turns,
            rag_chunks=rag_chunks,
            skill_mode=skill_mode,
            skill_threshold=skill_threshold,
            doc_threshold=doc_threshold,
            custom_endpoint=custom_endpoint,
        )
    else:
        result = custom_agent.process_message(
            message=message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_turns=max_turns,
            rag_chunks=rag_chunks,
            skill_mode=skill_mode,
            skill_threshold=skill_threshold,
            doc_threshold=doc_threshold,
            custom_endpoint=custom_endpoint,
        )

    return jsonify(result)

# -----------------------------------------------------------------------------
# Vector DB Ingestion API
# -----------------------------------------------------------------------------
@app.route("/api/vectordb/stats", methods=["GET"])
def api_vectordb_stats():
    """Return database statistics (chunks, docs, size in MB)."""
    stats = vector_store.get_database_statistics()
    stats["active_model"] = ollama.active_model
    return jsonify(stats)

@app.route("/api/vectordb/documents", methods=["GET"])
def api_vectordb_documents():
    """List ingested documents."""
    docs = vector_store.get_ingested_documents()
    return jsonify({"documents": docs})

@app.route("/api/vectordb/ingest", methods=["POST"])
def api_vectordb_ingest():
    """Ingest content from a URL or local directory/file path."""
    data = request.get_json() or {}
    source = data.get("source", "").strip()
    chunk_size = int(data.get("chunk_size", 1000))
    chunk_overlap = int(data.get("chunk_overlap", 200))

    if not source:
        return jsonify({"error": "Source URL or path is required."}), 400

    content = ""
    doc_name = ""

    # Check if URL
    if source.startswith("http://") or source.startswith("https://"):
        try:
            resp = requests.get(source, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return jsonify({"error": f"Failed to fetch URL: HTTP {resp.status_code}"}), 400
            content = resp.text
            doc_name = source.split("/")[-1] or "webpage.html"
            if "?" in doc_name:
                doc_name = doc_name.split("?")[0]
        except Exception as e:
            return jsonify({"error": f"Error fetching URL: {str(e)}"}), 400
    else:
        # Local file or directory
        p = Path(source)
        if not p.is_absolute():
            p = config.BASE_DIR / source

        if p.is_file():
            content = p.read_text(encoding="utf-8", errors="ignore")
            doc_name = p.name
        elif p.is_dir():
            # Ingest all files in directory
            results = []
            for f in p.iterdir():
                if f.is_file() and f.suffix.lower() in [".txt", ".md", ".json", ".csv"]:
                    f_content = f.read_text(encoding="utf-8", errors="ignore")
                    res = vector_store.add_document(
                        doc_name=f.name,
                        content=f_content,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )
                    results.append(res)
            return jsonify({
                "status": "success",
                "message": f"Ingested {len(results)} files from directory {p.name}",
                "details": results
            })
        else:
            return jsonify({"error": f"Local path not found: {source}"}), 400

    # Ingest single document
    res = vector_store.add_document(
        doc_name=doc_name,
        content=content,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return jsonify({
        "status": "success",
        "message": f"Successfully ingested {doc_name} ({res['chunks_added']} chunks added)",
        "details": res
    })

@app.route("/api/vectordb/document", methods=["DELETE"])
def api_vectordb_delete_document():
    """Delete a single document from the database."""
    doc_name = request.args.get("doc_name", "").strip()
    if not doc_name:
        return jsonify({"error": "Document name is required."}), 400

    deleted_count = vector_store.delete_document(doc_name)
    return jsonify({
        "status": "success",
        "doc_name": doc_name,
        "deleted_chunks": deleted_count,
    })

@app.route("/api/vectordb/reset", methods=["POST"])
def api_vectordb_reset():
    """Reset the document vector database."""
    vector_store.reset_database()
    return jsonify({"status": "success", "message": "Documents vector database cleared."})

@app.route("/api/vectordb/models", methods=["GET"])
def api_vectordb_models():
    """List available and installed Ollama embedding models."""
    models = ollama.list_available_models()
    return jsonify({
        "active_model": ollama.active_model,
        "models": models,
    })

@app.route("/api/vectordb/change-model", methods=["POST"])
def api_vectordb_change_model():
    """Switch embedder model, delete DB data, pull model, and re-import skills."""
    data = request.get_json() or {}
    new_model = data.get("model", "").strip()
    confirmation = data.get("confirmation", "").strip()

    if not new_model:
        return jsonify({"error": "Target model is required."}), 400

    if confirmation != "Change model and delete data":
        return jsonify({"error": "Must type exact confirmation phrase: 'Change model and delete data'"}), 400

    # 1. Reset vector databases
    vector_store.reset_database()
    vector_store.reset_skills_database()

    # 2. Switch model in Ollama
    success = ollama.set_active_model(new_model)
    if not success:
        return jsonify({"error": f"Failed to pull or activate model {new_model} in Ollama."}), 500

    # 3. Re-scan and import skills
    skills_res = skill_manager.scan_and_sync_skills(force_all=True)

    return jsonify({
        "status": "success",
        "active_model": ollama.active_model,
        "message": f"Active embedder switched to {new_model}. Database cleared and {skills_res['added']} skills re-indexed.",
    })

# -----------------------------------------------------------------------------
# Telemetry API
# -----------------------------------------------------------------------------
@app.route("/api/telemetry", methods=["GET"])
def api_telemetry():
    """Return aggregated telemetry data for charts and stats."""
    model_filter = request.args.get("model", "All Models")
    interval = request.args.get("interval", "15 min")
    time_range = request.args.get("time_range", "1 day")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    metrics = telemetry.get_metrics(
        model_filter=model_filter,
        interval=interval,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
    )
    return jsonify(metrics)

# -----------------------------------------------------------------------------
# Audit Log & Events API
# -----------------------------------------------------------------------------
@app.route("/api/logs", methods=["GET"])
def api_logs():
    """Return conversation summaries and statistics."""
    summaries = logger.get_conversation_summaries()
    stats = logger.get_statistics()
    return jsonify({
        "conversations": summaries,
        "statistics": stats,
    })

@app.route("/api/logs/<conversation_id>", methods=["GET"])
def api_conversation_events(conversation_id: str):
    """Return all audit events for a specific conversation."""
    events = logger.get_conversation_events(conversation_id)
    return jsonify({"conversation_id": conversation_id, "events": events})

@app.route("/api/logs/clear", methods=["POST"])
def api_logs_clear():
    """Clear all audit logs."""
    logger.clear_logs()
    return jsonify({"status": "success", "message": "All audit logs cleared."})

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = config.get_configured_port()
    initialize_system()
    print(f"\n==================================================")
    print(f"  Agent-with-RAG Server starting on port {port}")
    print(f"  Web Interface: http://127.0.0.1:{port}")
    print(f"==================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
