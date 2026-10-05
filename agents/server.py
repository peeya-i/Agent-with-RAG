import os
import sys
import json
import time
from datetime import datetime, timezone
import requests
from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv

# Try loading secrets/.env first, then root .env
SECRETS_DIR = os.environ.get("SECRETS_DIR", os.path.join(os.path.dirname(__file__), "secrets"))
env_path = os.path.join(SECRETS_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [current_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from custom_agent.custom_agent import CustomAgent
    from genai.google_adk_agent import GoogleADKAgent
    from skills_loader import scan_and_load_skills
except ModuleNotFoundError:
    from agents.custom_agent.custom_agent import CustomAgent
    from agents.genai.google_adk_agent import GoogleADKAgent
    from agents.skills_loader import scan_and_load_skills

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

DOC_RAG_URL = os.environ.get("DOC_RAG_URL", "http://doc_rag:8003")
TOOLS_URL = os.environ.get("TOOLS_URL", "http://tools:8005")
LOGGING_URL = os.environ.get("LOGGING_URL", "http://logging:8006")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it")

custom_agent = CustomAgent(doc_rag_url=DOC_RAG_URL, tools_url=TOOLS_URL, logging_url=LOGGING_URL, gemini_api_key=GEMINI_API_KEY)
adk_agent = GoogleADKAgent(doc_rag_url=DOC_RAG_URL, tools_url=TOOLS_URL, logging_url=LOGGING_URL, gemini_api_key=GEMINI_API_KEY)

try:
    from jwt_auth import decode_jwt_token, extract_jwt_from_request
except ImportError:
    from agents.jwt_auth import decode_jwt_token, extract_jwt_from_request

def validate_agent_request_auth(api_key, invoker="web_ui"):
    if not api_key:
        return True, "No key provided"

    # Check if api_key is a valid JWT token
    jwt_p = decode_jwt_token(api_key)
    if jwt_p:
        return True, "Valid JWT"

    try:
        url = AUTH_SERVICE_URL
        if not os.environ.get("RUNNING_IN_DOCKER") and "auth_service:8001" in url:
            url = url.replace("auth_service:8001", "127.0.0.1:8001")
        resp = requests.post(url, json={
            "api_key": api_key,
            "container": "agents",
            "access_level": "read",
            "invoker": invoker
        }, timeout=2)
        if resp.status_code == 200 and resp.json().get("valid"):
            return True, "Valid"
        return False, resp.json().get("error", "Unauthorized")
    except Exception as e:
        return True, f"Bypass: {e}"

# Load API keys previously configured for agent services from secrets/keys
KEYS_FILE = os.path.join(SECRETS_DIR, "keys")
def load_agent_keys():
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
            print(f"[Agents] Error reading keys file: {e}")
    return keys

configured_agent_keys = load_agent_keys()

# Scan skills on startup from agents/skills/
SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "skills"))
loaded_skills = []

@app.before_request
def initial_startup_scan():
    global loaded_skills
    if not hasattr(app, "_skills_scanned"):
        app._skills_scanned = True
        try:
            rag_key = load_agent_keys().get("doc_rag")
            loaded_skills = scan_and_load_skills(SKILLS_DIR, doc_rag_url=DOC_RAG_URL, api_key=rag_key)
            print(f"[Agents] Initialized and loaded {len(loaded_skills)} skills to doc_RAG: {loaded_skills}")
        except Exception as e:
            print(f"[Agents] Startup skills scan deferred: {e}")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "agents", "port": 8002})

@app.route("/api/models", methods=["GET"])
@app.route("/api/agents/models", methods=["GET"])
def get_active_models():
    """Query Google AI Studio for active text generation models."""
    api_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    models_list = []

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            raw_models = client.models.list()
            for m in raw_models:
                supported = getattr(m, "supported_actions", []) or []
                if "generateContent" in supported:
                    m_id = m.name.replace("models/", "")
                    models_list.append({
                        "id": m_id,
                        "display_name": getattr(m, "display_name", m_id) or m_id,
                        "max_output_tokens": getattr(m, "output_token_limit", 4096) or 4096,
                        "max_input_tokens": getattr(m, "input_token_limit", 32768) or 32768
                    })
        except Exception as e:
            print(f"[Agents] Error fetching models from Google GenAI: {e}")

    # Ensure default model is always present
    has_default = any(m["id"] == DEFAULT_MODEL for m in models_list)
    if not has_default:
        models_list.insert(0, {
            "id": DEFAULT_MODEL,
            "display_name": DEFAULT_MODEL,
            "max_output_tokens": 32768,
            "max_input_tokens": 262144
        })

    # Sort so default model is first
    models_list.sort(key=lambda x: 0 if x["id"] == DEFAULT_MODEL else 1)

    return jsonify({"models": models_list, "default": DEFAULT_MODEL})

@app.route("/api/agents/skills", methods=["GET"])
def get_loaded_skills():
    return jsonify({"skills": loaded_skills, "count": len(loaded_skills)})

@app.route("/api/agent/chat", methods=["POST"])
def process_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("query") or ""
    conversation_id = data.get("conversation_id") or f"conv_{int(time.time())}"
    agent_type = data.get("agent_type", "Custom Agent")
    model = data.get("model") or DEFAULT_MODEL
    temperature = float(data.get("temperature", 0.7))
    max_tokens = int(data.get("max_tokens", 2048)) if data.get("max_tokens") else 2048
    max_turns = int(data.get("max_turns", 5))
    skill_selector = data.get("skill_selector", "Vector Store Selects")
    skill_threshold = float(data.get("skill_threshold", 0.2))
    doc_threshold = float(data.get("doc_threshold", 0.3))
    max_chunks = int(data.get("max_chunks", 5))
    custom_endpoint = data.get("custom_endpoint") if "custom" in (model or "").lower() else None
    api_key = data.get("api_key") or request.headers.get("X-API-Key")

    if not message.strip():
        return jsonify({"error": "Empty message"}), 400

    auth_header = request.headers.get("Authorization", "")
    jwt_token = data.get("jwt_token")
    if not jwt_token and auth_header.startswith("Bearer "):
        jwt_token = auth_header.split(" ", 1)[1].strip()
    if not jwt_token and api_key and (api_key.startswith("eyJ") or "." in api_key):
        jwt_token = api_key

    # Validate API key or JWT if provided
    token_to_validate = jwt_token or api_key
    if token_to_validate:
        is_valid, msg = validate_agent_request_auth(token_to_validate, invoker="web_ui")
        if not is_valid:
            return jsonify({"status": "error", "error": f"Authorization failed: {msg}"}), 403

    configured_keys = load_agent_keys()
    runner = adk_agent if "ADK" in agent_type else custom_agent

    result = runner.run(
        message=message,
        conversation_id=conversation_id,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        max_turns=max_turns,
        skill_selector=skill_selector,
        skill_threshold=skill_threshold,
        doc_threshold=doc_threshold,
        max_chunks=max_chunks,
        custom_endpoint=custom_endpoint,
        api_key=api_key,
        jwt_token=jwt_token,
        configured_keys=configured_keys
    )

    return jsonify(result)

@app.route("/api/agent/reload_skills", methods=["POST"])
def reload_skills():
    """Triggered by 'Update Skills Database' button in GUI."""
    rag_key = load_agent_keys().get("doc_rag")
    loaded = scan_and_load_skills(SKILLS_DIR, doc_rag_url=DOC_RAG_URL, api_key=rag_key)
    return jsonify({"status": "success", "loaded_skills": loaded, "count": len(loaded)})

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
        if tool_name == "agent_chat":
            res = custom_agent.run(**args)
            return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res)}]}})

    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {}})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    app.run(host="0.0.0.0", port=port)
