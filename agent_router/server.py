import os
import sys
import time
import threading
import logging
from datetime import datetime, timezone
from typing import Dict, Any
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Setup path to import local modules and jwt_auth
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [current_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AgentsRouter] %(message)s")
logger = logging.getLogger("agents_router")

try:
    from embeddings import EmbeddingEngine
    from registry import AgentRegistry, AgentInfo
    from router import VectorRouter, SIMILARITY_THRESHOLD
except (ImportError, ModuleNotFoundError):
    from agent_router.embeddings import EmbeddingEngine
    from agent_router.registry import AgentRegistry, AgentInfo
    from agent_router.router import VectorRouter, SIMILARITY_THRESHOLD

try:
    from jwt_auth import decode_jwt_token
except ImportError:
    try:
        from ..jwt_auth import decode_jwt_token
    except Exception:
        decode_jwt_token = lambda t: {}

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

# Service configuration
PORT = int(os.environ.get("PORT", 8004))
AGENTS_URL = os.environ.get("AGENTS_URL", "http://agents:8002")
TECH_SUPPORT_URL = os.environ.get("TECH_SUPPORT_URL", "http://agent_tech_support:8007")
LOGGING_URL = os.environ.get("LOGGING_URL", "http://logging:8006")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Initialize router components
embedding_engine = EmbeddingEngine(api_key=GEMINI_API_KEY)
registry = AgentRegistry(embedding_engine=embedding_engine)
router = VectorRouter(
    registry=registry,
    embedding_engine=embedding_engine,
    threshold=SIMILARITY_THRESHOLD,
    gemini_api_key=GEMINI_API_KEY,
    logging_url=os.environ.get("LOGGING_URL", "http://logging:8006")
)

def resolve_url(url, host, port):
    if not os.environ.get("RUNNING_IN_DOCKER") and f"{host}:{port}" in url:
        return url.replace(f"{host}:{port}", f"127.0.0.1:{port}")
    return url

def log_event(invoker, recipient, event_type, desc, payload, conv_id=None, status="success", duration_ms=0, model="", user=None, domain=None, target=None):
    try:
        url = resolve_url(LOGGING_URL, "logging", 8006)
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
        requests.post(f"{url}/api/logs", json=req_json, timeout=2)
    except Exception:
        pass

def seed_default_agents():
    """Initializes the registry with the default agents container and initial tech support specialist."""
    logger.info("Registering initial default and specialized agents...")
    
    # 1. Primary Agents Container (Default Fallback)
    default_agent = AgentInfo(
        id="agents-default",
        name="Default Multi-Tool & RAG Agent",
        description=(
            "Primary multi-tool agent supporting Document RAG retrieval, skill tool execution, "
            "weather forecasts, stock market queries, mathematical calculations, and general conversation."
        ),
        url=resolve_url(AGENTS_URL, "agents", 8002),
        sample_prompts=[
            "What is the weather forecast for Seattle tomorrow?",
            "Calculate 145 multiplied by 82 minus 300.",
            "Summarize the technical architecture document from RAG storage.",
            "Look up the latest stock price and valuation for NVDA.",
            "Help me write an introductory email to the team.",
        ],
        status="up",
        is_default=True,
        metadata={"role": "default_fallback", "container": "agents", "port": 8002, "registration_type": "Hard Coded"}
    )
    default_agent.agent_type = "Hard Coded"
    registry.register(default_agent)

    # 2. Specialized Technical Support Agent
    tech_agent = AgentInfo(
        id="agent-tech-support",
        name="Technical Support & DevOps Specialist",
        description=(
            "Diagnoses technical software issues, API errors, HTTP 500 status codes, database connection timeouts, "
            "Docker container crashes, Kubernetes pod restarts, microservice latency, authentication header failures, "
            "and system crash log analysis."
        ),
        url=resolve_url(TECH_SUPPORT_URL, "agent_tech_support", 8007),
        sample_prompts=[
            "Our microservice is throwing HTTP 504 Gateway Timeout on PostgreSQL queries.",
            "How do I resolve 'Invalid Authentication Token' when sending requests to the API gateway?",
            "The Docker container crashed with code 137 OOMKilled on startup.",
            "Why is my webhook receiving TLS handshake failed errors from the server?",
            "How do I debug connection pool exhaustion in high-throughput endpoints?",
            "Can you explain why the worker process threw a segmentation fault in Python?",
            "Docker container logs show exit code 1 with fatal python exception.",
            "Database connection failed with host unreachable error.",
        ],
        status="up",
        is_default=False,
        metadata={"role": "specialized_tech_support", "container": "agent_tech_support", "port": 8007, "registration_type": "API Registered"}
    )
    tech_agent.agent_type = "API Registered"
    registry.register(tech_agent)

    # 3. Load all manually configured agents from the mounted volume storage file upon starting
    manual_loaded = registry.load_manual_agents()
    logger.info(f"Loaded {len(manual_loaded)} manually configured agents upon starting.")

seed_default_agents()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "agents-router",
        "port": PORT,
        "registered_agents_count": len(registry.list_all_agents()),
        "threshold": round(router.threshold, 4),
    })

@app.route("/api/router/threshold", methods=["GET", "POST"])
def router_threshold():
    """Gets or dynamically updates the minimum routing threshold."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if "threshold" not in data:
            return jsonify({"status": "error", "message": "Missing 'threshold' field"}), 400
        try:
            val = float(data["threshold"])
            if val < 0.0 or val > 1.0:
                return jsonify({"status": "error", "message": "Threshold must be between 0.0 and 1.0"}), 400
            router.threshold = val
            logger.info(f"Routing threshold updated to {router.threshold:.4f}")
            return jsonify({
                "status": "success",
                "threshold": round(router.threshold, 4),
                "threshold_percent": f"{round(router.threshold * 100, 1)}%",
                "message": f"Routing threshold updated to {router.threshold:.2f}"
            })
        except (ValueError, TypeError) as e:
            return jsonify({"status": "error", "message": f"Invalid threshold value: {e}"}), 400

    return jsonify({
        "status": "success",
        "threshold": round(router.threshold, 4),
        "threshold_percent": f"{round(router.threshold * 100, 1)}%"
    })

@app.route("/api/router/selector", methods=["GET", "POST"])
@app.route("/api/router/model", methods=["GET", "POST"])
def router_selector():
    """Gets or dynamically updates the active agent selector and embedding model for routing."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        new_sel = data.get("selector_type") or data.get("type")
        new_model = data.get("model") or data.get("active_model")
        thresh = data.get("threshold")

        if thresh is not None:
            try:
                router.threshold = float(thresh)
            except Exception:
                pass

        if new_model in ["main_llm", "llm", "Main LLM select"] or new_sel == "llm":
            router.selector_type = "llm"
            router.active_model = "main_llm"
            logger.info("Router active selector updated to 'Main LLM select'")
        elif new_sel in ["ollama_llm", "local_llm"] or (new_model and (str(new_model).startswith("local:") or str(new_model).startswith("Local "))):
            clean_m = str(new_model).replace("local:", "").replace("Local ", "").strip()
            router.selector_type = "ollama_llm"
            router.active_model = clean_m
            logger.info(f"Router active selector updated to Local Ollama LLM '{clean_m}'")
        elif new_model:
            router.selector_type = "embedding"
            router.active_model = new_model
            embedding_engine.model = new_model
            logger.info(f"Router active selector updated to embedding model '{new_model}'")
        elif new_sel == "embedding":
            router.selector_type = "embedding"

        return jsonify({
            "status": "success",
            "selector_type": getattr(router, "selector_type", "embedding"),
            "active_model": getattr(router, "active_model", "bge-large"),
            "threshold": round(router.threshold, 4),
            "message": f"Router selector updated to {router.selector_type} ({router.active_model})"
        })

    return jsonify({
        "status": "success",
        "selector_type": getattr(router, "selector_type", "embedding"),
        "active_model": getattr(router, "active_model", getattr(embedding_engine, "model", "bge-large")),
        "threshold": round(router.threshold, 4),
    })

@app.route("/api/router/agents", methods=["GET"])
def list_agents():
    """Returns all registered agents with their live statuses and metadata."""
    agents = registry.list_all_agents()
    return jsonify({
        "status": "success",
        "count": len(agents),
        "threshold": round(router.threshold, 4),
        "agents": [a.to_dict() for a in agents]
    })

@app.route("/api/router/agents/register", methods=["POST"])
def register_agent():
    """Dynamic registration endpoint used by agent containers on startup or via Web UI."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("id") or data.get("agent_id")
    name = data.get("name") or data.get("agent_name")
    url = data.get("url") or data.get("endpoint")
    description = data.get("description", "")
    sample_prompts = data.get("sample_prompts", [])
    status = data.get("status", "up")
    is_default = bool(data.get("is_default", False))
    registration_type = (
        data.get("registration_type")
        or data.get("agent_type")
        or (data.get("metadata", {}).get("registration_type") if isinstance(data.get("metadata"), dict) else None)
        or ("Hard Coded" if is_default else "API Registered")
    )

    if not agent_id or not name or not url:
        return jsonify({"status": "error", "message": "Missing required fields: id, name, url"}), 400

    # Format sample_prompts if string was supplied
    if isinstance(sample_prompts, str):
        sample_prompts = [p.strip() for p in sample_prompts.split("\n") if p.strip()]

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["registration_type"] = registration_type

    agent = AgentInfo(
        id=agent_id.strip(),
        name=name.strip(),
        description=description.strip(),
        url=url.strip(),
        sample_prompts=sample_prompts,
        status=status,
        is_default=is_default,
        metadata=metadata
    )
    agent.agent_type = registration_type

    registered = registry.register(agent, auto_embed=True)
    logger.info(f"Agent dynamically registered: {registered.id} ({registered.name}, Type: {registered.agent_type}) at {registered.url}")

    log_event(
        invoker="AgentRegistry",
        recipient="logging",
        event_type="agent_registered",
        desc=f"Agent '{registered.name}' ({registered.id}) registered as {registered.agent_type} at {registered.url}",
        payload=registered.to_dict(),
    )

    return jsonify({
        "status": "success",
        "message": f"Agent '{registered.name}' registered successfully.",
        "agent": registered.to_dict()
    }), 201

@app.route("/api/router/agents/<agent_id>/update", methods=["POST"])
def update_agent(agent_id):
    """Updates an existing agent's details (allowed for Manually Added agents)."""
    agent = registry.get_agent(agent_id)
    if not agent:
        return jsonify({"status": "error", "message": f"Agent '{agent_id}' not found"}), 404

    agent_type = getattr(agent, "agent_type", agent.metadata.get("registration_type", ""))
    if agent_type != "Manually Added":
        return jsonify({
            "status": "error",
            "message": f"Only 'Manually Added' agents can be modified (this agent is '{agent_type}')."
        }), 403

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    url = data.get("url")
    description = data.get("description")
    sample_prompts = data.get("sample_prompts")
    status = data.get("status")

    if name:
        agent.name = name.strip()
    if url:
        agent.url = url.strip().rstrip("/")
    if description is not None:
        agent.description = description.strip()
    if status in ["up", "down"]:
        agent.status = status
    if sample_prompts is not None:
        if isinstance(sample_prompts, str):
            agent.sample_prompts = [p.strip() for p in sample_prompts.split("\n") if p.strip()]
        elif isinstance(sample_prompts, list):
            agent.sample_prompts = [str(p).strip() for p in sample_prompts if str(p).strip()]

    # Re-embed agent text
    try:
        agent.embedding = registry.embedding_engine.embed_text(agent.get_embedding_text())
        if agent.sample_prompts:
            agent.sample_embeddings = [registry.embedding_engine.embed_text(p) for p in agent.sample_prompts]
        else:
            agent.sample_embeddings = []
    except Exception as e:
        logger.warning(f"Error re-embedding agent '{agent_id}': {e}")

    # Persist changes if this is a manually added agent
    if getattr(agent, "agent_type", "") == "Manually Added" or (agent.metadata and agent.metadata.get("registration_type") == "Manually Added"):
        registry.save_manual_agents()

    logger.info(f"Agent '{agent_id}' updated successfully.")
    return jsonify({
        "status": "success",
        "message": f"Agent '{agent.name}' updated successfully.",
        "agent": agent.to_dict()
    })

@app.route("/api/router/agents/<agent_id>", methods=["DELETE"])
def unregister_agent(agent_id):
    """Unregisters an agent from the router."""
    try:
        success = registry.unregister(agent_id)
        if success:
            return jsonify({"status": "success", "message": f"Agent '{agent_id}' unregistered."})
        return jsonify({"status": "error", "message": f"Agent '{agent_id}' not found."}), 404
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/router/agents/<agent_id>/status", methods=["POST"])
def set_agent_status(agent_id):
    """Updates an agent's operational status ('up' or 'down')."""
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    agent = registry.get_agent(agent_id)
    if not agent:
        return jsonify({"status": "error", "message": f"Agent '{agent_id}' not found"}), 404

    if not new_status:
        # Toggle status if not provided
        new_status = "down" if agent.status == "up" else "up"

    updated = registry.set_status(agent_id, new_status)
    return jsonify({
        "status": "success",
        "agent_id": agent_id,
        "new_status": updated.status,
        "is_available": updated.is_available
    })

@app.route("/api/router/agents/<agent_id>/health", methods=["POST", "GET"])
def check_agent_health(agent_id):
    """Pings the target agent container to verify live connectivity."""
    result = registry.check_health(agent_id)
    return jsonify(result)

@app.route("/api/router/agents/health_check_all", methods=["POST", "GET"])
def check_all_agents_health():
    """Pings all target agent containers to verify live connectivity."""
    results = registry.check_all_health()
    return jsonify({"status": "success", "results": results})

def background_health_checker():
    """Periodically probes all registered agents every 30 seconds to maintain actual status."""
    time.sleep(2)
    while True:
        try:
            registry.check_all_health()
        except Exception as e:
            logger.error(f"Error in background_health_checker: {e}")
        time.sleep(30)

health_checker_thread = threading.Thread(target=background_health_checker, daemon=True)
health_checker_thread.start()

@app.route("/api/router/test_route", methods=["POST"])
def test_route():
    """Tests semantic prompt routing without executing the LLM."""
    data = request.get_json(silent=True) or {}
    query = data.get("message") or data.get("query") or ""
    if not query.strip():
        return jsonify({"status": "error", "message": "Query cannot be empty"}), 400

    threshold = data.get("threshold")
    threshold_val = float(threshold) if threshold is not None else None
    embedder_model = data.get("embedder_model") or data.get("model")
    if embedder_model == "default":
        embedder_model = None
    selector_type = data.get("selector_type") or data.get("agent_selector")

    # Optional ephemeral draft agents for What-If sandbox evaluation:
    # Start with all registered agents so none are lost!
    candidate_agents = list(registry.list_all_agents())
    draft_agents_data = data.get("draft_agents")
    if draft_agents_data and isinstance(draft_agents_data, list):
        for d in draft_agents_data:
            try:
                draft_obj = AgentInfo.from_dict(d)
                candidate_agents = [a for a in candidate_agents if a.id != draft_obj.id]
                candidate_agents.append(draft_obj)
            except Exception as e:
                logger.warning(f"Error parsing draft agent: {e}")

    invoker = data.get("invoker") or "Semantic Lab"
    conv_id = data.get("conversation_id") or f"conv_sem_lab_{int(time.time())}"
    user = data.get("user") or data.get("username") or "admin"
    domain = data.get("domain") or "pi-net.local"

    target_agent, top_score, ranked, is_fallback, explanation, route_ms = router.decide_route(
        query,
        threshold=threshold_val,
        candidate_agents=candidate_agents,
        model=embedder_model,
        conv_id=conv_id,
        selector_type=selector_type,
    )

    effective_thresh = threshold_val if threshold_val is not None else router.threshold

    # Find top specialized candidate for clarity
    spec_ranked = [s for s in ranked if not s.is_default]
    top_spec = spec_ranked[0] if spec_ranked else None

    # Enrich ranked results with embedding_text and sample_prompts for inspector
    ranked_dicts = []
    for s in ranked:
        s_dict = s.to_dict()
        agent_obj = next((a for a in candidate_agents if a.id == s.agent_id), None)
        if not agent_obj:
            agent_obj = registry.get_agent(s.agent_id)
        if agent_obj:
            s_dict["embedding_text"] = agent_obj.get_embedding_text()
            s_dict["sample_prompts"] = agent_obj.sample_prompts
            s_dict["description"] = agent_obj.description
        ranked_dicts.append(s_dict)

    model_name = embedder_model or getattr(router, "last_model_used", None) or getattr(embedding_engine, "model", "bge-large:latest")
    is_ollama_llm = bool(
        selector_type in ["ollama_llm", "local_llm"]
        or (embedder_model and (str(embedder_model).startswith("local:") or str(embedder_model).startswith("Local ")))
        or getattr(router, "last_selector_type", None) == "ollama_llm"
    )
    is_llm = bool(selector_type == "llm" or embedder_model in ["main_llm", "llm", "Main LLM select"] or getattr(router, "last_selector_type", None) == "llm")
    if is_ollama_llm or getattr(router, "selector_type", None) == "ollama_llm":
        raw_m = str(embedder_model or getattr(router, "active_model", "deepseek-r1:1.5b")).replace("local:", "").replace("Local ", "").strip()
        model_name = f"Local {raw_m}"
    elif is_llm or getattr(router, "selector_type", None) == "llm":
        model_name = "Main LLM select"
    resp_payload = {
        "status": "success",
        "query": query,
        "model_used": model_name,
        "selected_agent": target_agent.to_dict() if target_agent else None,
        "similarity_score": round(top_score, 4),
        "similarity_percent": f"{round(top_score * 100, 1)}%",
        "top_specialized_agent": top_spec.to_dict() if top_spec else None,
        "top_specialized_score": round(top_spec.score, 4) if top_spec else 0.0,
        "threshold": round(effective_thresh, 4),
        "is_default_fallback": is_fallback,
        "explanation": explanation,
        "routing_latency_ms": round(route_ms, 2),
        "ranked_scores": ranked_dicts
    }
    # Log Semantic Lab test route evaluation
    log_event(
        invoker="agents_router",
        recipient="agents_router",
        target="agents_router",
        event_type="agent_router",
        desc=f"Agent Router evaluated test route: '{query[:80]}' -> '{target_agent.name if target_agent else 'None'}' using {model_name} ({round(route_ms)}ms)",
        payload={
            "request": data,
            "response": resp_payload,
            "request_payload": data,
            "response_payload": resp_payload,
            "model_used": model_name,
            "selected_agent": target_agent.name if target_agent else "None",
            "similarity_score": round(top_score, 4),
            "is_default_fallback": is_fallback
        },
        conv_id=conv_id,
        duration_ms=int(route_ms),
        status="success",
        model=model_name,
        user=user,
        domain=domain
    )

    return jsonify(resp_payload)

@app.route("/api/router/chat", methods=["POST"])
def router_chat():
    """Main routing endpoint: determines target agent via vector embeddings or LLM and executes prompt."""
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("query") or ""
    conv_id = data.get("conversation_id") or f"conv_{int(time.time())}"
    data["conversation_id"] = conv_id
    invoker = data.get("invoker") or request.headers.get("X-Invoker") or "Web UI"
    user = data.get("user") or data.get("username") or "admin"
    domain = data.get("domain") or "pi-net.local"

    if not message.strip():
        return jsonify({"status": "error", "message": "Message cannot be empty"}), 400

    # Extract headers to forward
    forward_headers = {}
    auth_header = request.headers.get("Authorization", "")
    jwt_token = data.get("jwt_token")
    if jwt_token and not auth_header:
        forward_headers["Authorization"] = f"Bearer {jwt_token}"
    elif auth_header:
        forward_headers["Authorization"] = auth_header

    # Perform routing and execution
    routing_result = router.route_and_execute(
        query=message,
        payload=data,
        headers=forward_headers,
        conv_id=conv_id
    )

    resp_data = routing_result.response_data or {}
    status_code = getattr(routing_result, "status_code", 200) or 200

    return jsonify(resp_data), status_code

if __name__ == "__main__":
    logger.info(f"Starting Agents Router service on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
