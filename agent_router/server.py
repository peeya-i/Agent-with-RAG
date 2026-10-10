import os
import sys
import time
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
router = VectorRouter(registry=registry, embedding_engine=embedding_engine, threshold=SIMILARITY_THRESHOLD)

def resolve_url(url, host, port):
    if not os.environ.get("RUNNING_IN_DOCKER") and f"{host}:{port}" in url:
        return url.replace(f"{host}:{port}", f"127.0.0.1:{port}")
    return url

def log_event(invoker, recipient, event_type, desc, payload, conv_id=None, status="success", duration_ms=0, model=""):
    try:
        url = resolve_url(LOGGING_URL, "logging", 8006)
        requests.post(f"{url}/api/logs", json={
            "invoker": invoker,
            "recipient": recipient,
            "conversation_id": conv_id,
            "type": event_type,
            "short_description": desc,
            "payload": payload,
            "status": status,
            "duration_ms": duration_ms,
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, timeout=2)
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
        metadata={"role": "default_fallback", "container": "agents", "port": 8002}
    )
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
        metadata={"role": "specialized_tech_support", "container": "agent_tech_support", "port": 8007}
    )
    registry.register(tech_agent)

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

    if not agent_id or not name or not url:
        return jsonify({"status": "error", "message": "Missing required fields: id, name, url"}), 400

    # Format sample_prompts if string was supplied
    if isinstance(sample_prompts, str):
        sample_prompts = [p.strip() for p in sample_prompts.split("\n") if p.strip()]

    agent = AgentInfo(
        id=agent_id.strip(),
        name=name.strip(),
        description=description.strip(),
        url=url.strip(),
        sample_prompts=sample_prompts,
        status=status,
        is_default=is_default,
        metadata=data.get("metadata", {})
    )

    registered = registry.register(agent, auto_embed=True)
    logger.info(f"Agent dynamically registered: {registered.id} ({registered.name}) at {registered.url}")

    log_event(
        invoker="AgentRegistry",
        recipient="logging",
        event_type="agent_registered",
        desc=f"Agent '{registered.name}' ({registered.id}) dynamically registered at {registered.url}",
        payload=registered.to_dict(),
    )

    return jsonify({
        "status": "success",
        "message": f"Agent '{registered.name}' registered successfully.",
        "agent": registered.to_dict()
    }), 201

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

@app.route("/api/router/test_route", methods=["POST"])
def test_route():
    """Tests semantic prompt routing without executing the LLM."""
    data = request.get_json(silent=True) or {}
    query = data.get("message") or data.get("query") or ""
    if not query.strip():
        return jsonify({"status": "error", "message": "Query cannot be empty"}), 400

    target_agent, top_score, ranked, is_fallback, explanation, route_ms = router.decide_route(query)

    return jsonify({
        "status": "success",
        "query": query,
        "selected_agent": target_agent.to_dict() if target_agent else None,
        "similarity_score": round(top_score, 4),
        "similarity_percent": f"{round(top_score * 100, 1)}%",
        "threshold": round(router.threshold, 4),
        "is_default_fallback": is_fallback,
        "explanation": explanation,
        "routing_latency_ms": round(route_ms, 2),
        "ranked_scores": [s.to_dict() for s in ranked]
    })

@app.route("/api/router/chat", methods=["POST"])
def router_chat():
    """Main routing endpoint: determines target agent via vector embeddings and executes prompt."""
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("query") or ""
    conv_id = data.get("conversation_id") or f"conv_{int(time.time())}"
    data["conversation_id"] = conv_id

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
        headers=forward_headers
    )

    resp_data = routing_result.response_data or {}

    # Log routing decision to centralized logging service
    log_event(
        invoker="agents_router",
        recipient=routing_result.selected_agent.id if routing_result.selected_agent else "agents-default",
        event_type="routed_chat_request",
        desc=routing_result.explanation,
        payload={
            "query": message,
            "selected_agent": routing_result.selected_agent.id if routing_result.selected_agent else None,
            "similarity_score": routing_result.similarity_score,
            "threshold": round(router.threshold, 4),
            "is_default_fallback": routing_result.is_default_fallback,
            "routing_latency_ms": routing_result.routing_latency_ms,
            "total_latency_ms": routing_result.total_latency_ms,
        },
        conv_id=conv_id,
        duration_ms=routing_result.routing_latency_ms,
    )

    # Return response payload directly to preserve Web UI compatibility
    return jsonify(resp_data)

if __name__ == "__main__":
    logger.info(f"Starting Agents Router service on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
