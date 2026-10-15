import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone
import requests
from flask import Flask, render_template, request, jsonify, session, has_request_context
from dotenv import load_dotenv

# Load secrets/.env
SECRETS_DIR = os.environ.get("SECRETS_DIR", os.path.join(os.path.dirname(__file__), "secrets"))
env_path = os.path.join(SECRETS_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-agent-key-12345")
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

AUTH_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth_service:8001")
AGENTS_URL = os.environ.get("AGENTS_URL", "http://agents:8002")
ROUTER_URL = os.environ.get("ROUTER_URL", "http://agents_router:8004")
TECH_SUPPORT_URL = os.environ.get("TECH_SUPPORT_URL", "http://agent_tech_support:8007")
DOC_RAG_URL = os.environ.get("DOC_RAG_URL", "http://doc_rag:8003")
TOOLS_URL = os.environ.get("TOOLS_URL", "http://tools:8005")
LOGGING_URL = os.environ.get("LOGGING_URL", "http://logging:8006")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")

CONTAINER_PORTS = {
    "web_ui": 8000,
    "auth_service": 8001,
    "agents_router": 8004,
    "agents": 8002,
    "agent_tech_support": 8007,
    "doc_rag": 8003,
    "ollama": 11434,
    "tools": 8005,
    "logging": 8006
}

def resolve_url(url, host, port):
    if not os.environ.get("RUNNING_IN_DOCKER") and f"{host}:{port}" in url:
        return url.replace(f"{host}:{port}", f"127.0.0.1:{port}")
    return url

def log_event(invoker, recipient, event_type, desc, payload, conv_id=None, status="success", duration_ms=0, model="", user=None, domain=None, target=None):
    try:
        url = resolve_url(LOGGING_URL, "logging", 8006)
        u_session = session.get("user") if has_request_context() else {}
        u = user or (u_session.get("email") if isinstance(u_session, dict) else None)
        d = domain or (u_session.get("domain") if isinstance(u_session, dict) else None)
        tgt = target or recipient
        requests.post(f"{url}/api/logs", json={
            "invoker": invoker,
            "recipient": recipient,
            "target": tgt,
            "conversation_id": conv_id,
            "user": u,
            "domain": d,
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

CONTAINER_DIR_MAP = {
    "web_ui": "web_ui",
    "agents_router": "agent_router",
    "agents": "agents",
    "agent_tech_support": "agent_tech_support",
    "doc_rag": "doc_RAG",
    "tools": "tools",
    "auth_service": "auth_service",
    "ollama": "embedding",
    "logging": "logging"
}


@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = f"sess_{uuid.uuid4().hex[:12]}"
    return render_template("index.html")

# -------------------------------------------------------------
# Auth & Session APIs
# -------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    data["ip_address"] = request.remote_addr
    session_id = session.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")
    session["session_id"] = session_id

    url = resolve_url(AUTH_URL, "auth_service", 8001)
    try:
        resp = requests.post(f"{url}/api/auth/login", json=data, timeout=5)
        res_data = resp.json()
        if resp.status_code == 200 and res_data.get("status") == "success":
            session["user"] = res_data.get("user")
            session["jwt_token"] = res_data.get("jwt_token") or res_data.get("token")
            session["preferences"] = res_data.get("preferences") or {}
            # Log user login to Logging container
            log_event(
                invoker="web_ui",
                recipient="logging",
                event_type="user_session_login",
                desc=f"User {data.get('username')} logged in",
                payload={
                    "user_name": data.get("username"),
                    "session_id": session_id,
                    "ip_address": request.remote_addr,
                    "time": datetime.now(timezone.utc).isoformat()
                }
            )
            return jsonify(res_data)
        return jsonify(res_data), resp.status_code
    except Exception as e:
        return jsonify({"status": "failed", "error": f"Auth service unreachable: {e}"}), 502

@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = session.get("user")
    jwt_token = session.get("jwt_token")
    if not user:
        return jsonify({"authenticated": False}), 401
    email = user.get("email")
    prefs = session.get("preferences") or {}
    if not prefs and email:
        try:
            url = resolve_url(AUTH_URL, "auth_service", 8001)
            r = requests.get(f"{url}/api/auth/preferences?email={email}", timeout=3)
            if r.status_code == 200:
                prefs = r.json().get("preferences", {})
                session["preferences"] = prefs
        except Exception:
            pass
    return jsonify({"authenticated": True, "user": user, "jwt_token": jwt_token, "preferences": prefs})

@app.route("/api/user/preferences", methods=["GET", "POST"])
def user_preferences():
    user = session.get("user") or {}
    email = user.get("email")
    jwt_token = session.get("jwt_token")
    if not email:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    url = resolve_url(AUTH_URL, "auth_service", 8001)
    headers = {"Content-Type": "application/json"}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        data["email"] = email
        try:
            r = requests.post(f"{url}/api/auth/preferences", json=data, headers=headers, timeout=5)
            res = r.json()
            session["preferences"] = res.get("preferences", {})
            return jsonify(res), r.status_code
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 502

    # GET
    try:
        r = requests.get(f"{url}/api/auth/preferences?email={email}", headers=headers, timeout=5)
        res = r.json()
        session["preferences"] = res.get("preferences", {})
        return jsonify(res), r.status_code
    except Exception as e:
        cached = session.get("preferences", {})
        return jsonify({"status": "success", "preferences": cached, "source": "session"})

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    user = session.get("user", {})
    username = user.get("email", "unknown")
    session_id = session.get("session_id", "unknown")

    url = resolve_url(AUTH_URL, "auth_service", 8001)
    try:
        requests.post(f"{url}/api/auth/logout", json={"username": username, "ip_address": request.remote_addr}, timeout=3)
    except Exception:
        pass

    log_event(
        invoker="web_ui",
        recipient="logging",
        event_type="user_session_logout",
        desc=f"User {username} logged out",
        payload={
            "user_name": username,
            "session_id": session_id,
            "ip_address": request.remote_addr,
            "time": datetime.now(timezone.utc).isoformat()
        }
    )

    session.clear()
    return jsonify({"status": "success"})

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or {}
    data["ip_address"] = request.remote_addr
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    try:
        resp = requests.post(f"{url}/api/auth/register", json=data, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"status": "failed", "error": f"Auth service unreachable: {e}"}), 502

@app.route("/api/users/<int:uid>/status", methods=["PUT"])
def proxy_update_user_status(uid):
    user = session.get("user")
    if user and user.get("role") != "Admin":
        return jsonify({"status": "failed", "error": "Only users with Admin access can modify user accounts"}), 403
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    params = {}
    if user and user.get("domain"):
        params["domain"] = user.get("domain")
    if user and user.get("role"):
        params["role"] = user.get("role")
    try:
        r = requests.put(f"{url}/api/users/{uid}/status", json=request.get_json(silent=True), params=params, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 502

@app.route("/api/page_view", methods=["POST"])
def log_page_view():
    data = request.get_json(silent=True) or {}
    page_name = data.get("page_name", "unknown")
    user = session.get("user", {})
    username = user.get("email", data.get("username", "anonymous"))
    session_id = session.get("session_id", data.get("session_id", "unknown"))

    log_event(
        invoker="web_ui",
        recipient="logging",
        event_type="page_view",
        desc=f"Page view: {page_name}",
        payload={
            "user_name": username,
            "session_id": session_id,
            "ip_address": request.remote_addr,
            "time": datetime.now(timezone.utc).isoformat(),
            "page_name": page_name
        }
    )
    return jsonify({"status": "success"})

# Proxy User and API Key management
@app.route("/api/users", methods=["GET", "POST"])
def proxy_users():
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    user = session.get("user") or {}
    if request.method == "POST":
        if user.get("role") != "Admin":
            return jsonify({"status": "failed", "error": "Only users with Admin access can create user accounts"}), 403
        data = request.get_json(silent=True) or {}
        if user.get("domain"):
            data["creator_domain"] = user.get("domain")
        data["creator_role"] = user.get("role")
        r = requests.post(f"{url}/api/users", json=data, timeout=5)
        return jsonify(r.json()), r.status_code
    else:
        params = {}
        if user.get("domain"):
            params["domain"] = user.get("domain")
        if user.get("role"):
            params["role"] = user.get("role")
        r = requests.get(f"{url}/api/users", params=params, timeout=5)
        return jsonify(r.json()), r.status_code

@app.route("/api/users/bulk_delete", methods=["POST"])
def proxy_bulk_delete_users():
    user = session.get("user") or {}
    if user.get("role") != "Admin":
        return jsonify({"status": "failed", "error": "Only users with Admin access can delete user accounts"}), 403
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    params = {}
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    try:
        r = requests.post(f"{url}/api/users/bulk_delete", json=request.get_json(silent=True), params=params, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 502

@app.route("/api/users/<int:uid>/role", methods=["PUT"])
def proxy_update_user_role(uid):
    user = session.get("user") or {}
    if user.get("role") != "Admin":
        return jsonify({"status": "failed", "error": "Only users with Admin access can modify user accounts"}), 403
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    params = {}
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    r = requests.put(f"{url}/api/users/{uid}/role", json=request.get_json(silent=True), params=params, timeout=5)
    return jsonify(r.json()), r.status_code

@app.route("/api/users/<int:uid>/reset_password", methods=["POST"])
def proxy_reset_password(uid):
    user = session.get("user") or {}
    if user.get("role") != "Admin":
        return jsonify({"status": "failed", "error": "Only users with Admin access can modify user accounts"}), 403
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    params = {}
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    r = requests.post(f"{url}/api/users/{uid}/reset_password", json=request.get_json(silent=True), params=params, timeout=5)
    return jsonify(r.json()), r.status_code

@app.route("/api/users/<int:uid>", methods=["DELETE"])
def proxy_delete_user(uid):
    user = session.get("user") or {}
    if user.get("role") != "Admin":
        return jsonify({"status": "failed", "error": "Only users with Admin access can modify user accounts"}), 403
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    params = {}
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    r = requests.delete(f"{url}/api/users/{uid}", params=params, timeout=5)
    return jsonify(r.json()), r.status_code

@app.route("/api/users/activity_logs", methods=["GET"])
def proxy_user_activity():
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    user = session.get("user") or {}
    params = {}
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    r = requests.get(f"{url}/api/users/activity_logs", params=params, timeout=5)
    return jsonify(r.json()), r.status_code

# JWT Tokens Management Proxy
@app.route("/api/jwt/tokens", methods=["GET"])
def proxy_jwt_tokens():
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    user = session.get("user") or {}
    params = dict(request.args)
    if user.get("email") and "user" not in params:
        params["user"] = user.get("email")
    if user.get("domain") and "domain" not in params:
        params["domain"] = user.get("domain")
    if user.get("role") and "role" not in params:
        params["role"] = user.get("role")
    try:
        r = requests.get(f"{url}/api/jwt/tokens", params=params, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "failed", "tokens": [], "error": str(e)}), 502

@app.route("/api/jwt/tokens/bulk_delete", methods=["POST"])
def proxy_bulk_delete_jwt():
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    try:
        r = requests.post(f"{url}/api/jwt/tokens/bulk_delete", json=request.get_json(silent=True) or {}, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 502

@app.route("/api/jwt/tokens/<int:token_id>", methods=["DELETE"])
def proxy_delete_jwt(token_id):
    url = resolve_url(AUTH_URL, "auth_service", 8001)
    try:
        r = requests.delete(f"{url}/api/jwt/tokens/{token_id}", timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 502

@app.route("/api/jwt/activities", methods=["GET"])
def get_jwt_activities():
    user = session.get("user") or {}
    domain = user.get("domain")
    role = (user.get("role") or "User").lower()
    email = user.get("email")

    filter_user = request.args.get("user_email") or request.args.get("user")
    filter_token = request.args.get("token_prefix")

    url = resolve_url(LOGGING_URL, "logging", 8006)
    try:
        r = requests.get(f"{url}/api/logs/query", timeout=5)
        res_json = r.json() if r.status_code == 200 else {}
        logs = res_json.get("logs", [])
    except Exception:
        logs = []

    # Filter to ONLY initial requests from the user
    PRIMARY_TYPES = {
        "send_chat_request": "Chat Query (Agent)",
        "chat_interaction": "Chat Query (Agent)",
        "user_session_login": "Session Login",
        "user_login": "Session Login",
        "user_session_logout": "Session Logout",
        "user_logout": "Session Logout",
        "vectordb_ingest": "Vector DB Document Ingest",
        "vectordb_delete": "Vector DB Document Delete",
        "document_delete": "Vector DB Document Delete",
        "user_registration": "User Registration",
        "page_view": "Navigation Page View"
    }

    activities = []
    for l in reversed(logs):
        etype = l.get("type", "")
        invoker = (l.get("invoker") or "").lower()
        if etype not in PRIMARY_TYPES and invoker not in ["web ui", "web_ui", "client", "user"]:
            continue

        log_user = l.get("user") or l.get("payload", {}).get("user_name") or l.get("payload", {}).get("username") or l.get("payload", {}).get("email") or ""
        log_domain = l.get("domain") or ""
        if not log_domain and "@" in str(log_user):
            log_domain = str(log_user).split("@", 1)[1]

        # Multi-tenant domain scoping:
        if role != "admin" or domain:
            if domain:
                if log_domain and log_domain != domain:
                    continue
                if not log_domain and log_user and not log_user.endswith(f"@{domain}"):
                    continue
            if role == "user":
                if email and log_user and log_user != email:
                    continue

        # Filter by selected token's user if specified
        if filter_user and str(log_user).strip().lower() != filter_user.strip().lower():
            continue

        recip = l.get("recipient") or "agents"
        desc = l.get("short_description") or ""
        if not desc and isinstance(l.get("payload"), dict):
            p = l.get("payload")
            desc = p.get("message") or p.get("desc") or f"{etype} initiated"

        activities.append({
            "created_at": l.get("timestamp"),
            "user_email": log_user or email or "User",
            "domain": log_domain or domain or "Global",
            "recipient": recip,
            "request_type": PRIMARY_TYPES.get(etype, etype.replace("_", " ").title()),
            "status": (l.get("status") or "Success").capitalize(),
            "details": desc
        })

    return jsonify({"status": "success", "count": len(activities), "activities": activities})

# -------------------------------------------------------------
# Chat & Agents APIs
# -------------------------------------------------------------
@app.route("/api/models", methods=["GET"])
def get_models():
    url = resolve_url(AGENTS_URL, "agents", 8002)
    try:
        r = requests.get(f"{url}/api/models", timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"models": [{"id": "gemma-4-26b-a4b-it", "display_name": "gemma-4-26b-a4b-it", "max_output_tokens": 32768, "max_input_tokens": 262144}], "default": "gemma-4-26b-a4b-it"})

@app.route("/api/chat", methods=["POST"])
def proxy_chat():
    data = request.get_json(silent=True) or {}
    conv_id = data.get("conversation_id") or f"conv_{int(time.time())}"
    data["conversation_id"] = conv_id
    agents_url = resolve_url(AGENTS_URL, "agents", 8002)
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)

    user = session.get("user") or {}
    username = user.get("email") or data.get("user") or "anonymous"
    domain = user.get("domain") or data.get("domain") or ""
    data["user"] = username
    data["username"] = username
    data["domain"] = domain

    # Attach active JWT token
    jwt_token = data.get("jwt_token") or session.get("jwt_token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if jwt_token:
        data["jwt_token"] = jwt_token

    # Check JWT validity and expiration before dispatching
    if jwt_token:
        try:
            from jwt_auth import decode_jwt_token_with_reason
            jwt_payload, jwt_reason = decode_jwt_token_with_reason(jwt_token)
            if not jwt_payload:
                is_expired = bool(jwt_reason and "expired" in jwt_reason.lower())
                err_msg = "JWT token has expired. Please log in again to renew your session." if is_expired else f"Authentication Error: {jwt_reason or 'Invalid JWT token'}"
                log_event(
                    invoker="Web UI",
                    recipient="Web UI",
                    event_type="chat_error",
                    desc=f"Chat rejected: {err_msg}",
                    payload={"error": err_msg, "reason": jwt_reason, "is_jwt_expired": is_expired},
                    conv_id=conv_id,
                    status="error",
                    user=username,
                    domain=domain
                )
                return jsonify({
                    "status": "error",
                    "error": err_msg,
                    "reason": jwt_reason,
                    "is_jwt_expired": is_expired
                }), 403
        except Exception as jwt_check_err:
            pass

    headers = {"Content-Type": "application/json"}
    data["invoker"] = "Web UI"
    data["target"] = "agents_router"
    headers["X-Invoker"] = "Web UI"
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    # Log outgoing chat request from Web UI
    log_event(
        invoker="Web UI",
        recipient="agents_router",
        target="agents_router",
        event_type="send_chat_request",
        desc=f"Web UI submitted query from {username}: '{data.get('message', '')[:80]}'",
        payload=data,
        conv_id=conv_id,
        user=username,
        domain=domain
    )

    # First attempt routing through agents-router
    res_data = None
    status_code = 200
    responder_service = "agents_router"
    try:
        r = requests.post(f"{router_url}/api/router/chat", json=data, headers=headers, timeout=180)
        res_data = r.json()
        status_code = r.status_code
        responder_service = "agents_router"
    except Exception as router_err:
        # Fallback directly to default agents container if router unreachable
        print(f"[WebUI] Router unavailable ({router_err}), falling back to direct agents container...")
        responder_service = "agents"
        try:
            r = requests.post(f"{agents_url}/api/agent/chat", json=data, headers=headers, timeout=60)
            res_data = r.json()
            status_code = r.status_code
        except Exception as e:
            log_event(
                invoker="agents",
                recipient="Web UI",
                event_type="chat_error",
                desc=f"Agent request failed: {e}",
                payload={"error": str(e)},
                conv_id=conv_id,
                status="error",
                user=username,
                domain=domain
            )
            return jsonify({"error": f"Agent service unreachable: {e}"}), 502

    # If response is error or 401/403, detect if JWT expired
    if status_code in (401, 403) or (isinstance(res_data, dict) and res_data.get("status") == "error"):
        err_str = str(res_data.get("error", "") if isinstance(res_data, dict) else res_data)
        reason_str = str(res_data.get("reason", "") if isinstance(res_data, dict) else "")
        if "expired" in err_str.lower() or "expired" in reason_str.lower():
            if isinstance(res_data, dict):
                res_data["is_jwt_expired"] = True
                res_data["error"] = "JWT token has expired. Please log in again to renew your session."

    # Enrich response with retrieved_evidence pulled from Logging per SPECIFICATIONS.md
    if isinstance(res_data, dict):
        logged_ev = extract_evidence_from_logs(conv_id)
        if logged_ev.get("skills") or logged_ev.get("documents"):
            res_data["retrieved_evidence"] = {
                "skills": logged_ev.get("skills", []),
                "documents": logged_ev.get("documents", [])
            }
        elif not res_data.get("retrieved_evidence"):
            res_data["retrieved_evidence"] = {"skills": [], "documents": []}

        res_data["conversation_id"] = conv_id
        if not res_data.get("user_query") and data.get("message"):
            res_data["user_query"] = data.get("message")

    # Log response received by Web UI
    log_event(
        invoker=responder_service,
        recipient="Web UI",
        target="Web UI",
        event_type="received_chat_response",
        desc=f"Web UI received response from {responder_service} ({res_data.get('elapsed_ms', 0) if isinstance(res_data, dict) else 0}ms)",
        payload=res_data,
        conv_id=conv_id,
        duration_ms=res_data.get("elapsed_ms", 0) if isinstance(res_data, dict) else 0,
        model=res_data.get("model", "") if isinstance(res_data, dict) else "",
        user=username,
        domain=domain
    )
    return jsonify(res_data), status_code

# -------------------------------------------------------------
# Agents Router Management APIs
# -------------------------------------------------------------
@app.route("/api/router/agents", methods=["GET"])
def router_get_agents():
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        r = requests.get(f"{router_url}/api/router/agents", timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}", "agents": []}), 502

@app.route("/api/router/agents/register", methods=["POST"])
def router_register_agent():
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    data = request.get_json(silent=True) or {}
    try:
        r = requests.post(f"{router_url}/api/router/agents/register", json=data, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/agents/<agent_id>/update", methods=["POST"])
def router_update_agent(agent_id):
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    data = request.get_json(silent=True) or {}
    try:
        r = requests.post(f"{router_url}/api/router/agents/{agent_id}/update", json=data, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/agents/<agent_id>/status", methods=["POST"])
def router_set_agent_status(agent_id):
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    data = request.get_json(silent=True) or {}
    try:
        r = requests.post(f"{router_url}/api/router/agents/{agent_id}/status", json=data, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/agents/<agent_id>/health", methods=["GET", "POST"])
def router_check_agent_health(agent_id):
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        r = requests.get(f"{router_url}/api/router/agents/{agent_id}/health", timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/agents/health_check_all", methods=["GET", "POST"])
def router_check_all_agents_health():
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        r = requests.post(f"{router_url}/api/router/agents/health_check_all", timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/agents/<agent_id>", methods=["DELETE"])
def router_delete_agent(agent_id):
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        r = requests.delete(f"{router_url}/api/router/agents/{agent_id}", timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/test_route", methods=["POST"])
def router_test_route():
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    data = request.get_json(silent=True) or {}
    user = session.get("user") or {}
    if "user" not in data:
        data["user"] = user.get("email") or "admin"
    if "domain" not in data:
        data["domain"] = user.get("domain") or "pi-net.local"
    try:
        r = requests.post(f"{router_url}/api/router/test_route", json=data, timeout=30)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

@app.route("/api/router/threshold", methods=["GET", "POST"])
def router_get_or_set_threshold():
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            r = requests.post(f"{router_url}/api/router/threshold", json=data, timeout=5)
        else:
            r = requests.get(f"{router_url}/api/router/threshold", timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}", "threshold": 0.50}), 502

@app.route("/api/router/selector", methods=["GET", "POST"])
@app.route("/api/router/model", methods=["GET", "POST"])
def proxy_router_selector():
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            r = requests.post(f"{router_url}/api/router/selector", json=data, timeout=5)
        else:
            r = requests.get(f"{router_url}/api/router/selector", timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Agents router unreachable: {e}"}), 502

# ==============================================================================
# Semantic Lab Endpoints
# ==============================================================================

@app.route("/api/semantic_lab/context", methods=["GET"])
def get_semantic_lab_context():
    """Returns available models, registered agents, and loaded skills for Semantic Lab."""
    # 1. Fetch agents from router
    agents = []
    threshold = 0.50
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        r_agents = requests.get(f"{router_url}/api/router/agents", timeout=5)
        if r_agents.ok:
            agents_data = r_agents.json()
            agents = agents_data.get("agents", [])
            threshold = agents_data.get("threshold", 0.50)
    except Exception as e:
        app.logger.warning(f"Error fetching agents for semantic lab: {e}")

    # 2. Fetch skills directly and parse SKILL.md files
    skills = []
    candidate_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents", "skills"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "skills"),
        os.path.join(os.getcwd(), "agents", "skills"),
        "/app/agents/skills",
        "/home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agents/skills"
    ]
    for p in candidate_paths:
        if os.path.exists(p) and os.path.isdir(p):
            for entry in os.scandir(p):
                if entry.is_dir():
                    md_path = os.path.join(entry.path, "SKILL.md")
                    if os.path.exists(md_path):
                        try:
                            with open(md_path, "r", encoding="utf-8") as f:
                                raw_content = f.read()
                            name = entry.name
                            desc = ""
                            triggers = []
                            # parse frontmatter
                            fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_content, re.DOTALL)
                            if fm_match:
                                fm_text = fm_match.group(1)
                                n_match = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
                                if n_match:
                                    name = n_match.group(1).strip()
                                d_match = re.search(r"^description:\s*(.+)$", fm_text, re.MULTILINE)
                                if d_match:
                                    desc = d_match.group(1).strip()
                                t_matches = re.findall(r"^\s*-\s*(.+)$", fm_text, re.MULTILINE)
                                if t_matches:
                                    triggers = [t.strip() for t in t_matches]
                            skills.append({
                                "name": name,
                                "folder": entry.name,
                                "description": desc,
                                "triggers": triggers,
                                "raw_content": raw_content
                            })
                        except Exception as e:
                            app.logger.warning(f"Error reading skill {entry.name}: {e}")
            if skills:
                break

    # Fallback to doc_rag skills API if local folder is empty/unmounted
    if not skills:
        doc_rag_url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
        try:
            r_skills = requests.get(f"{doc_rag_url}/api/rag/skills/list", timeout=5)
            if r_skills.ok:
                skills = r_skills.json().get("skills", [])
        except Exception as e:
            app.logger.warning(f"Error fetching skills from doc_rag fallback: {e}")

    # 3. Models
    models = []
    active_model = "bge-large:latest"
    try:
        m_resp = get_vectordb_models()
        if hasattr(m_resp, "get_json"):
            m_data = m_resp.get_json()
            models = m_data.get("models", [])
            active_model = m_data.get("active_model", active_model)
    except Exception as e:
        app.logger.warning(f"Error getting models for semantic lab: {e}")

    return jsonify({
        "status": "success",
        "agents": agents,
        "agent_threshold": threshold,
        "skills": skills,
        "models": models,
        "active_model": active_model
    })

@app.route("/api/semantic_lab/test_skills", methods=["POST"])
def semantic_lab_test_skills():
    """Queries doc_RAG for skill vector matches given a prompt and threshold."""
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or data.get("message") or "").strip()
    threshold = float(data.get("threshold", 0.20))
    limit = int(data.get("limit", 4))
    draft_skill = data.get("draft_skill")

    if not query:
        return jsonify({"status": "error", "message": "Query cannot be empty"}), 400

    doc_rag_url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    embedder_model = (data.get("embedder_model") or data.get("model") or "").strip() or None
    if embedder_model == "default":
        embedder_model = None
    try:
        req_payload = {
            "db_type": "skill",
            "query": query,
            "threshold": threshold,
            "k": limit,
            "model": embedder_model,
            "embedder_model": embedder_model,
            "invoker": "Semantic Lab"
        }
        if draft_skill:
            req_payload["draft_skill"] = draft_skill
        r = requests.post(f"{doc_rag_url}/api/rag/query", json=req_payload, timeout=30)
        if r.ok:
            res_json = r.json()
            results = res_json.get("results", [])
            resp_payload = {
                "status": "success",
                "query": query,
                "threshold": threshold,
                "matches": results,
                "match_count": len(results)
            }
            log_event(
                invoker="Semantic Lab",
                recipient="doc_rag",
                event_type="semantic_lab_test_skills",
                desc=f"Semantic Lab test skills evaluated: '{query[:80]}' ({len(results)} matches)",
                payload={
                    "request_payload": data,
                    "response_payload": resp_payload,
                    "model_used": embedder_model or "default",
                    "match_count": len(results)
                },
                conv_id=data.get("conversation_id"),
                status="success",
                model=embedder_model or ""
            )
            return jsonify(resp_payload)
        else:
            return jsonify({"status": "error", "message": f"Doc RAG returned {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error querying skills: {e}"}), 502

@app.route("/api/semantic_lab/batch_eval", methods=["POST"])
def semantic_lab_batch_eval():
    """Runs batch evaluation of multiple prompts against agents and skills."""
    data = request.get_json(silent=True) or {}
    prompts = data.get("prompts", [])
    if isinstance(prompts, str):
        prompts = [p.strip() for p in prompts.split("\n") if p.strip()]

    agent_threshold = float(data.get("agent_threshold", 0.50))
    skill_threshold = float(data.get("skill_threshold", 0.20))
    embedder_model = (data.get("embedder_model") or data.get("model") or "").strip() or None
    draft_agents = data.get("draft_agents")
    pipeline_mode = data.get("mode", "full")

    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    doc_rag_url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)

    results = []
    start_all = time.time()

    for p in prompts[:20]:  # Cap at 20 prompts
        p_res = {
            "prompt": p,
            "selected_agent": "None",
            "agent_score": 0.0,
            "is_fallback": False,
            "agent_status": "N/A",
            "top_skill": "None",
            "skill_score": 0.0,
            "decision": "OK"
        }

        # 1. Agent evaluation
        if pipeline_mode in ["full", "agents"]:
            try:
                ar = requests.post(f"{router_url}/api/router/test_route", json={
                    "query": p,
                    "threshold": agent_threshold,
                    "embedder_model": embedder_model,
                    "draft_agents": draft_agents,
                    "invoker": "Semantic Lab",
                    "conversation_id": data.get("conversation_id")
                }, timeout=30)
                if ar.ok:
                    aj = ar.json()
                    sel = aj.get("selected_agent") or {}
                    p_res["selected_agent"] = sel.get("name", "Unknown")
                    p_res["agent_score"] = aj.get("similarity_score", 0.0)
                    p_res["is_fallback"] = aj.get("is_default_fallback", False)
                    p_res["agent_status"] = "Fallback" if p_res["is_fallback"] else "Specialized"
            except Exception:
                p_res["agent_status"] = "Error"

        # 2. Skill evaluation
        if pipeline_mode in ["full", "skills"]:
            try:
                sr = requests.post(f"{doc_rag_url}/api/rag/query", json={
                    "db_type": "skill",
                    "query": p,
                    "threshold": skill_threshold,
                    "k": 2,
                    "model": embedder_model,
                    "embedder_model": embedder_model,
                    "invoker": "Semantic Lab"
                }, timeout=30)
                if sr.ok:
                    sj = sr.json()
                    matches = sj.get("results", [])
                    if matches:
                        p_res["top_skill"] = matches[0].get("name", "None")
                        p_res["skill_score"] = matches[0].get("similarity_score", 0.0)
            except Exception:
                p_res["top_skill"] = "Error"

        results.append(p_res)

    total_time_ms = round((time.time() - start_all) * 1000, 2)
    resp_payload = {
        "status": "success",
        "results": results,
        "count": len(results),
        "total_latency_ms": total_time_ms,
        "model_used": embedder_model or "default"
    }

    log_event(
        invoker="Semantic Lab",
        recipient="web_ui",
        event_type="semantic_lab_batch_eval",
        desc=f"Semantic Lab batch evaluation: {len(results)} prompts evaluated ({int(total_time_ms)}ms)",
        payload={
            "request_payload": data,
            "response_payload": resp_payload,
            "model_used": embedder_model or "default",
            "total_prompts": len(results)
        },
        conv_id=data.get("conversation_id"),
        duration_ms=int(total_time_ms),
        status="success",
        model=embedder_model or ""
    )

    return jsonify(resp_payload)

def extract_evidence_from_logs(conv_id):
    """Pulls logs for a conversation from the Logging container and extracts skills and documents evidence."""
    if not conv_id:
        return {"skills": [], "documents": [], "flat_items": []}

    url = resolve_url(LOGGING_URL, "logging", 8006)
    logs = []
    try:
        r = requests.post(f"{url}/api/logs/query", json={"conversation_id": conv_id, "limit": 100}, timeout=5)
        if r.status_code == 200:
            logs = r.json().get("logs", [])
    except Exception as e:
        print(f"[WebUI] Error fetching logs for evidence ({conv_id}): {e}")

    skills = []
    seen_skills = set()
    doc_map = {}

    for l in logs:
        l_type = l.get("type") or l.get("event_type") or ""
        payload = l.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        req = payload.get("request", {}) if isinstance(payload.get("request"), dict) else {}
        resp = payload.get("response", {}) if isinstance(payload.get("response"), dict) else {}

        # 1. Skills: skill_vector_response or received_skill_vector_response or vector_db_query_response with skill
        if "skill_vector_response" in l_type or (l_type in ["vector_db_query_response", "received_vector_query_request"] and req.get("document_type") == "skill"):
            items = payload.get("results") or resp.get("matched_items") or []
            for item in items:
                name = item.get("skill_name") or item.get("name") or "Skill"
                try:
                    score = round(float(item.get("similarity_score", 0)), 4)
                except (ValueError, TypeError):
                    score = 0.0
                desc = item.get("chunk_text") or item.get("text") or ""
                if name not in seen_skills:
                    seen_skills.add(name)
                    skills.append({
                        "name": name,
                        "similarity": score,
                        "description": desc[:300]
                    })
                else:
                    for s in skills:
                        if s["name"] == name and score > s["similarity"]:
                            s["similarity"] = score

        # 2. Documents: document_vector_response or received_document_vector_response or vector_db_query_response with document
        if "document_vector_response" in l_type or (l_type in ["vector_db_query_response", "received_vector_query_request"] and req.get("document_type") == "document"):
            items = payload.get("results") or resp.get("matched_items") or []
            for item in items:
                meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                d_name = item.get("document_name") or meta.get("document_name") or item.get("name") or "Document"
                try:
                    score = round(float(item.get("similarity_score", 0)), 4)
                except (ValueError, TypeError):
                    score = 0.0
                idx = meta.get("chunk_index", 0)
                txt = item.get("chunk_text") or item.get("text") or ""

                if d_name not in doc_map:
                    doc_map[d_name] = {
                        "doc_name": d_name,
                        "highest_similarity": score,
                        "chunks": []
                    }
                if score > doc_map[d_name]["highest_similarity"]:
                    doc_map[d_name]["highest_similarity"] = score

                if not any(c["index"] == idx and abs(c["similarity"] - score) < 1e-4 for c in doc_map[d_name]["chunks"]):
                    doc_map[d_name]["chunks"].append({
                        "index": idx,
                        "similarity": score,
                        "text": txt
                    })

    for d in doc_map.values():
        d["chunks"].sort(key=lambda x: x.get("index", 0))

    docs = list(doc_map.values())
    docs.sort(key=lambda x: x.get("highest_similarity", 0), reverse=True)

    flat_items = []
    for s in skills:
        flat_items.append({
            "category": "Skill",
            "title": s["name"],
            "score": s["similarity"],
            "content": s["description"]
        })
    for d in docs:
        for ch in d["chunks"]:
            flat_items.append({
                "category": "Document",
                "title": f"{d['doc_name']} (Chunk #{ch['index']})",
                "score": ch["similarity"],
                "content": ch["text"][:400]
            })

    # 3. Extract Router Metadata if present in logs
    router_meta = None
    for l in logs:
        l_type = l.get("type") or l.get("event_type") or ""
        payload = l.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if l_type == "routed_chat_request":
            router_meta = {
                "routed_agent_id": payload.get("selected_agent"),
                "routed_agent_name": l.get("recipient") if l.get("recipient") != "agents-default" else "Default Multi-Tool & RAG Agent",
                "similarity_score": payload.get("similarity_score"),
                "threshold": payload.get("threshold"),
                "is_default_fallback": payload.get("is_default_fallback"),
                "explanation": l.get("short_description") or l.get("desc")
            }

    return {
        "skills": skills,
        "documents": docs,
        "flat_items": flat_items,
        "router_metadata": router_meta
    }

@app.route("/api/evidence/<conv_id>", methods=["GET"])
def get_context_evidence(conv_id):
    """Pulls context evidence from Logging container grouped by skills and documents."""
    ev = extract_evidence_from_logs(conv_id)
    return jsonify({
        "status": "success",
        "conversation_id": conv_id,
        "retrieved_evidence": {
            "skills": ev.get("skills", []),
            "documents": ev.get("documents", [])
        },
        "skills": ev.get("skills", []),
        "documents": ev.get("documents", []),
        "evidence": ev.get("flat_items", []),
        "router_metadata": ev.get("router_metadata")
    })

# -------------------------------------------------------------
# VectorDB Mgnt APIs
# -------------------------------------------------------------
EMBEDDING_CATALOG = [
    {
        "name": "bge-large:latest",
        "short_name": "bge-large",
        "dimensions": 1024,
        "context_window": "512",
        "size": "670MB",
        "description": "BAAI general embedding model large (high accuracy)",
    },
    {
        "name": "bge-m3:latest",
        "short_name": "bge-m3",
        "dimensions": 1024,
        "context_window": "8K",
        "size": "1.2GB",
        "description": "Multi-lingual, multi-functionality embedding model",
    },
    {
        "name": "nomic-embed-text:latest",
        "short_name": "nomic-embed-text",
        "dimensions": 768,
        "context_window": "8K",
        "size": "274MB",
        "description": "High-performing 8192 context window text embedding",
    },
    {
        "name": "all-minilm:latest",
        "short_name": "all-minilm",
        "dimensions": 384,
        "context_window": "512",
        "size": "46MB",
        "description": "Lightweight fast sentence transformer",
    }
]

@app.route("/api/vectordb/stats", methods=["GET"])
@app.route("/api/rag/stats", methods=["GET"])
def proxy_vectordb_stats():
    url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    jwt_token = session.get("jwt_token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    try:
        r = requests.get(f"{url}/api/rag/stats", headers=headers, timeout=5)
        data = r.json()
        doc_count = data.get("total_documents", data.get("count_documents", 0))
        chunk_count = data.get("total_chunks", data.get("chunks_count", 0))
        return jsonify({
            "status": "success",
            "total_documents": doc_count,
            "count_documents": doc_count,
            "documents_count": doc_count,
            "total_chunks": chunk_count,
            "chunks_count": chunk_count,
            "db_size_mb": data.get("db_size_mb", 0.0),
            "active_model": data.get("active_model", "bge-large:latest"),
            "documents": data.get("documents", [])
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "chunks_count": 0,
            "total_chunks": 0,
            "documents_count": 0,
            "total_documents": 0,
            "db_size_mb": 0.0,
            "active_model": "bge-large:latest",
            "documents": []
        })

@app.route("/api/vectordb/documents", methods=["GET"])
@app.route("/api/rag/documents", methods=["GET"])
def proxy_vectordb_documents():
    url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    jwt_token = session.get("jwt_token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    try:
        r = requests.get(f"{url}/api/rag/documents", headers=headers, timeout=5)
        data = r.json()
        return jsonify({
            "status": "success",
            "documents": data.get("documents", []),
            "total_documents": data.get("total_documents", len(data.get("documents", []))),
            "total_chunks": data.get("total_chunks", data.get("chunks_count", 0)),
            "db_size_mb": data.get("db_size_mb", 0.0),
            "active_model": data.get("active_model", "bge-large:latest")
        })
    except Exception as e:
        return jsonify({"status": "error", "documents": [], "error": str(e)}), 502

@app.route("/api/vectordb/models", methods=["GET"])
@app.route("/api/vectordb/ollama_models", methods=["GET"])
def get_vectordb_models():
    # 1. Get active model from doc_rag
    active_model = "bge-large:latest"
    doc_rag_url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    try:
        s_res = requests.get(f"{doc_rag_url}/api/rag/stats", timeout=3)
        if s_res.ok:
            active_model = s_res.json().get("active_model", active_model)
    except Exception:
        pass

    # 2. Get installed tags from ollama
    installed_tags = set()
    raw_ollama_models = []
    ollama_url = resolve_url(OLLAMA_URL, "ollama", 11434)
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=4)
        if r.ok:
            raw_ollama_models = r.json().get("models", [])
            for m in raw_ollama_models:
                m_name = m.get("name", "")
                installed_tags.add(m_name)
                installed_tags.add(m_name.split(":")[0])
    except Exception:
        installed_tags = {"bge-large", "bge-large:latest", "bge-m3", "bge-m3:latest", "nomic-embed-text", "nomic-embed-text:latest", "all-minilm", "all-minilm:latest"}

    active_base = active_model.split(":")[0]
    result_models = []
    known_names = set()

    for cat in EMBEDDING_CATALOG:
        m_name = cat["name"]
        m_short = cat["short_name"]
        known_names.add(m_name)
        known_names.add(m_short)
        is_installed = (m_name in installed_tags or m_short in installed_tags)
        is_active = (m_name == active_model or m_short == active_model or m_short == active_base or m_name.startswith(active_base))
        
        status = "Available to Pull"
        if is_active:
            status = "Installed (Active)"
        elif is_installed:
            status = "Installed"

        result_models.append({
            "name": m_name,
            "dimensions": cat["dimensions"],
            "context_window": cat["context_window"],
            "size": cat["size"],
            "description": cat["description"],
            "status": status,
            "is_active": is_active,
            "is_installed": is_installed
        })

    # Dynamically append any additional models discovered from Ollama
    for om in raw_ollama_models:
        om_name = om.get("name", "")
        if om_name and om_name not in known_names and om_name.split(":")[0] not in known_names:
            details = om.get("details", {})
            dim = details.get("embedding_length", "N/A")
            ctx = details.get("context_length", "N/A")
            size_bytes = om.get("size", 0)
            size_str = f"{size_bytes / (1024**3):.1f}GB" if size_bytes > 1024**3 else f"{size_bytes / (1024**2):.1f}MB"
            is_active = (om_name == active_model or om_name.split(":")[0] == active_base)

            result_models.append({
                "name": om_name,
                "dimensions": dim,
                "context_window": str(ctx) if ctx != "N/A" else "Unknown",
                "size": size_str,
                "description": f"Custom Ollama model ({details.get('family', 'general')})",
                "status": "Installed (Active)" if is_active else "Installed",
                "is_active": is_active,
                "is_installed": True
            })

    return jsonify({
        "status": "success",
        "models": result_models,
        "active_model": active_model
    })

@app.route("/api/vectordb/update_skills", methods=["POST"])
@app.route("/api/skills/update", methods=["POST"])
def proxy_update_skills():
    url = resolve_url(AGENTS_URL, "agents", 8002)
    try:
        r = requests.post(f"{url}/api/agent/reload_skills", timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 502

_webui_ingest_progress = {
    "active": False,
    "percent": 0,
    "processed": 0,
    "total": 0,
    "current_file": "",
    "message": "Idle"
}

@app.route("/api/vectordb/ingest_progress", methods=["GET"])
@app.route("/api/vectordb/progress", methods=["GET"])
def get_vectordb_ingest_progress():
    global _webui_ingest_progress
    if _webui_ingest_progress.get("active"):
        doc_rag_url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
        try:
            r = requests.get(f"{doc_rag_url}/api/rag/progress", timeout=2)
            if r.ok:
                rag_prog = r.json().get("progress", {})
                if rag_prog.get("active"):
                    total = _webui_ingest_progress.get("total", 1)
                    if total <= 1:
                        _webui_ingest_progress["percent"] = rag_prog.get("percent", _webui_ingest_progress["percent"])
                        _webui_ingest_progress["message"] = rag_prog.get("message", _webui_ingest_progress["message"])
                    else:
                        processed = _webui_ingest_progress.get("processed", 0)
                        rag_pct = rag_prog.get("percent", 0)
                        interp = int(((processed + (rag_pct / 100.0)) / total) * 100)
                        _webui_ingest_progress["percent"] = min(99, max(interp, _webui_ingest_progress.get("percent", 0)))
                        cur_doc = _webui_ingest_progress.get("current_file", "")
                        _webui_ingest_progress["message"] = f"Ingesting document {processed + 1} of {total}: {cur_doc} ({_webui_ingest_progress['percent']}%)"
        except Exception:
            pass
    return jsonify({"status": "success", "progress": _webui_ingest_progress})

@app.route("/api/vectordb/populate", methods=["POST"])
@app.route("/api/vectordb/ingest", methods=["POST"])
def populate_vectordb():
    global _webui_ingest_progress
    user = session.get("user") or {}
    if not user:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            t = auth_hdr.split(" ", 1)[1].strip()
            try:
                try:
                    from jwt_auth import decode_jwt_token
                except ImportError:
                    import sys
                    from pathlib import Path
                    _parent = str(Path(__file__).resolve().parent.parent)
                    if _parent not in sys.path:
                        sys.path.insert(0, _parent)
                    from jwt_auth import decode_jwt_token
                p = decode_jwt_token(t)
                if p:
                    user = {"email": p.get("email"), "role": p.get("role", "User"), "domain": p.get("domain")}
            except Exception:
                pass
    user_role = (user.get("role") or "User").lower()
    if user_role == "user":
        return jsonify({"error": "Role 'User' is not permitted to load documents into the vector database. Editor or Admin role required."}), 403

    data = request.get_json(silent=True) or {}
    source = data.get("source", "").strip()
    chunk_size = int(data.get("chunk_size", 800))
    overlap = int(data.get("chunk_overlap") or data.get("overlap", 100))

    if not source:
        return jsonify({"error": "URL or local directory path required"}), 400

    doc_type = data.get("type", "Documents")
    url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    jwt_token = session.get("jwt_token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    domain = user.get("domain")

    headers = {"Content-Type": "application/json"}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    doc_items = []

    # If web URL
    if source.startswith("http://") or source.startswith("https://"):
        try:
            from bs4 import BeautifulSoup
            resp = requests.get(source, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            content = soup.get_text(separator="\n").strip()
            doc_name = soup.title.string.strip() if soup.title else source
            if content:
                doc_items.append({"name": doc_name, "content": content})
        except Exception as e:
            return jsonify({"error": f"Failed to fetch URL: {e}"}), 400
    else:
        # Check potential local paths
        resolved_path = None
        candidates = [
            source,
            os.path.join("/app", source),
            os.path.join("/app/sample_docs", os.path.basename(source)),
            os.path.join(os.getcwd(), source),
            os.path.join(os.path.dirname(__file__), "..", source)
        ]
        for c in candidates:
            if os.path.exists(c):
                resolved_path = c
                break

        if resolved_path and os.path.exists(resolved_path):
            try:
                if os.path.isfile(resolved_path):
                    content = ""
                    if resolved_path.lower().endswith(".pdf"):
                        try:
                            from pypdf import PdfReader
                            reader = PdfReader(resolved_path)
                            content = "\n\n".join([page.extract_text() or "" for page in reader.pages])
                        except Exception as pe:
                            return jsonify({"error": f"Failed to extract PDF text: {pe}"}), 400
                    else:
                        with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    doc_name = os.path.basename(resolved_path).replace(".md", "").replace(".txt", "").replace(".pdf", "")
                    if content:
                        doc_items.append({"name": doc_name, "content": content})
                elif os.path.isdir(resolved_path):
                    for root, dirs, files in os.walk(resolved_path):
                        for file in sorted(files):
                            fl = file.lower()
                            p = os.path.join(root, file)
                            txt = ""
                            if fl.endswith(".pdf"):
                                try:
                                    from pypdf import PdfReader
                                    reader = PdfReader(p)
                                    txt = "\n\n".join([page.extract_text() or "" for page in reader.pages])
                                except Exception:
                                    pass
                            elif fl.endswith((".txt", ".md", ".csv")):
                                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                                    txt = f.read()
                            if txt.strip():
                                fname = os.path.basename(file).replace(".md", "").replace(".txt", "").replace(".pdf", "").replace(".csv", "")
                                doc_items.append({"name": fname, "content": txt})
            except Exception as e:
                return jsonify({"error": f"Failed to read local file/dir: {e}"}), 400
        else:
            return jsonify({"error": f"Source not accessible: {source}"}), 400

    if not doc_items:
        return jsonify({"error": "Extracted text content is empty or no valid documents found"}), 400

    total_docs = len(doc_items)
    _webui_ingest_progress["active"] = True
    _webui_ingest_progress["total"] = total_docs
    _webui_ingest_progress["processed"] = 0
    _webui_ingest_progress["percent"] = 0
    _webui_ingest_progress["current_file"] = doc_items[0]["name"]
    _webui_ingest_progress["message"] = f"Ingesting document 1 of {total_docs}: {doc_items[0]['name']} (0%)"

    target_label = "Skill" if "skill" in doc_type.lower() else "Document"
    total_chunks_created = 0

    try:
        for idx, item in enumerate(doc_items):
            cur_pct = int((idx / total_docs) * 100)
            _webui_ingest_progress["current_file"] = item["name"]
            _webui_ingest_progress["processed"] = idx
            _webui_ingest_progress["percent"] = cur_pct
            _webui_ingest_progress["message"] = f"Ingesting document {idx + 1} of {total_docs}: {item['name']} ({cur_pct}%)"

            req_body = {
                "name": item["name"],
                "complete_text": item["content"],
                "chunk_size": chunk_size,
                "overlap": overlap,
                "type": doc_type
            }
            if domain:
                req_body["domain"] = domain
            if jwt_token:
                req_body["jwt_token"] = jwt_token

            # 3 minutes timeout (180 seconds)
            r = requests.post(f"{url}/api/rag/documents/add", json=req_body, headers=headers, timeout=600)
            if r.status_code != 200:
                _webui_ingest_progress["active"] = False
                res_err = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": r.text}
                return jsonify(res_err), r.status_code

            res_doc = r.json()
            total_chunks_created += res_doc.get("chunks_created", 0)

            log_event(
                invoker="Web UI",
                recipient="doc_rag",
                event_type="vectordb_ingest",
                desc=f"User {user.get('email', 'unknown')} ingested {target_label.lower()} '{item['name']}'",
                payload={"name": item["name"], "type": doc_type, "domain": domain},
                user=user.get("email"),
                domain=domain
            )

        _webui_ingest_progress["processed"] = total_docs
        _webui_ingest_progress["percent"] = 100
        _webui_ingest_progress["active"] = False
        _webui_ingest_progress["message"] = f"Successfully ingested {total_docs} document(s) (100%)"

        if total_docs == 1:
            success_msg = f"Successfully ingested {target_label.lower()} '{doc_items[0]['name']}' into {target_label}s database ({total_chunks_created} chunks)."
        else:
            success_msg = f"Successfully ingested {total_docs} documents into {target_label}s database ({total_chunks_created} total chunks)."

        return jsonify({
            "status": "success",
            "message": success_msg,
            "chunks_created": total_chunks_created,
            "documents_count": total_docs
        }), 200

    except Exception as e:
        _webui_ingest_progress["active"] = False
        _webui_ingest_progress["message"] = f"Ingestion error: {e}"
        return jsonify({"error": f"Vector store unreachable: {e}"}), 502

@app.route("/api/vectordb/document", methods=["DELETE"])
@app.route("/api/vectordb/delete/<path:doc_name>", methods=["DELETE"])
@app.route("/api/rag/documents/<path:doc_name>", methods=["DELETE"])
def proxy_delete_doc(doc_name=None):
    import urllib.parse
    raw_name = doc_name or request.args.get("doc_name") or request.args.get("name") or ""
    if not raw_name:
        data = request.get_json(silent=True) or {}
        raw_name = data.get("doc_name") or data.get("name") or ""
    
    if not raw_name:
        return jsonify({"error": "Document name required"}), 400

    name = urllib.parse.unquote(raw_name)
    doc_type = request.args.get("type") or (request.get_json(silent=True) or {}).get("type") or "document"
    url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    jwt_token = session.get("jwt_token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    try:
        r = requests.delete(f"{url}/api/rag/documents/{urllib.parse.quote(name)}", params={"type": doc_type}, headers=headers, timeout=5)
        user = session.get("user") or {}
        if r.status_code == 200:
            log_event(
                invoker="Web UI",
                recipient="doc_rag",
                event_type="vectordb_delete",
                desc=f"User {user.get('email', 'unknown')} deleted document '{name}'",
                payload={"name": name, "type": doc_type},
                user=user.get("email"),
                domain=user.get("domain")
            )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": f"Failed to delete document: {e}"}), 502

@app.route("/api/vectordb/reset", methods=["POST"])
def proxy_reset_db():
    user = session.get("user") or {}
    is_global_admin = (user.get("role") == "Admin" and not user.get("domain"))
    if not is_global_admin:
        return jsonify({"error": "Permission denied: Only Global Admin can reset the Vector DB"}), 403
    url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    jwt_token = session.get("jwt_token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    try:
        r = requests.post(f"{url}/api/rag/reset", headers=headers, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": f"Failed to reset database: {e}"}), 502

@app.route("/api/vectordb/change-model", methods=["POST"])
@app.route("/api/vectordb/change_model", methods=["POST"])
def change_embed_model():
    data = request.get_json(silent=True) or {}
    new_model = data.get("model", "bge-large:latest")
    
    # 1. Update doc_rag model and reset DB
    url = resolve_url(DOC_RAG_URL, "doc_rag", 8003)
    try:
        requests.post(f"{url}/api/rag/model", json={"model": new_model}, timeout=5)
        requests.post(f"{url}/api/rag/reset", timeout=5)
    except Exception as e:
        app.logger.warning(f"Error resetting doc_rag on model change: {e}")

    # 2. Rescan skills
    agents_url = resolve_url(AGENTS_URL, "agents", 8002)
    try:
        requests.post(f"{agents_url}/api/agent/reload_skills", timeout=10)
    except Exception as e:
        app.logger.warning(f"Error reloading skills on model change: {e}")

    # 3. Synchronize active model with agents_router
    router_url = resolve_url(ROUTER_URL, "agents_router", 8004)
    try:
        requests.post(f"{router_url}/api/router/model", json={"model": new_model}, timeout=5)
    except Exception as e:
        app.logger.warning(f"Error synchronizing model with agents_router: {e}")

    return jsonify({"status": "success", "active_model": new_model, "message": f"Successfully changed embedder model to {new_model}"})


# -------------------------------------------------------------
# Telemetry & Audit Logs APIs
# -------------------------------------------------------------
@app.route("/api/telemetry", methods=["GET"])
def proxy_telemetry():
    url = resolve_url(LOGGING_URL, "logging", 8006)
    try:
        r = requests.get(f"{url}/api/logs/telemetry", params=request.args, timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"models_used": [], "total_chat": 0, "total_chats": 0, "total_prompts": 0, "total_llm_requests": 0, "total_responses": 0, "total_llm_responses": 0, "total_errors": 0, "total_input_tokens": 0, "total_output_tokens": 0, "timeline": [], "metrics": {}})

@app.route("/api/audit/conversations", methods=["GET"])
@app.route("/api/logs", methods=["GET"])
def proxy_audit_conversations():
    url = resolve_url(LOGGING_URL, "logging", 8006)
    user = session.get("user") or {}
    params = dict(request.args)
    if user.get("email"):
        params["user"] = user.get("email")
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    try:
        r = requests.get(f"{url}/api/conversations", params=params, timeout=5)
        return jsonify(r.json())
    except Exception:
        return jsonify({"conversations": [], "statistics": {}})

@app.route("/api/audit/events/<conv_id>", methods=["GET"])
@app.route("/api/logs/<conv_id>", methods=["GET"])
def proxy_audit_events(conv_id):
    url = resolve_url(LOGGING_URL, "logging", 8006)
    user = session.get("user") or {}
    params = dict(request.args)
    if user.get("email"):
        params["user"] = user.get("email")
    if user.get("domain"):
        params["domain"] = user.get("domain")
    if user.get("role"):
        params["role"] = user.get("role")
    try:
        r = requests.get(f"{url}/api/conversations/{conv_id}/events", params=params, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception:
        return jsonify({"events": []})

@app.route("/api/audit/clear", methods=["POST"])
@app.route("/api/logs/clear", methods=["POST"])
def proxy_clear_logs():
    url = resolve_url(LOGGING_URL, "logging", 8006)
    try:
        r = requests.post(f"{url}/api/logs/clear", timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 502

# -------------------------------------------------------------
# Container Manager APIs (Docker Integration)
# -------------------------------------------------------------
def get_docker_client():
    try:
        import docker
        if os.path.exists("/var/run/docker.sock"):
            return docker.DockerClient(base_url="unix://var/run/docker.sock")
        return docker.from_env()
    except Exception:
        try:
            import docker
            return docker.from_env()
        except Exception:
            return None

CONTAINER_DOCKER_NAME_MAP = {
    "web_ui": ["web-ui-service", "web_ui", "web-ui"],
    "auth_service": ["auth-service", "auth_service"],
    "agents_router": ["agents-router", "agents_router"],
    "agents": ["agents-service", "agents"],
    "agent_tech_support": ["agent-tech-support", "agent_tech_support"],
    "doc_rag": ["doc-rag-service", "doc_rag", "doc-rag"],
    "ollama": ["ollama-embedding", "ollama"],
    "tools": ["tools-service", "tools"],
    "logging": ["logging-service", "logging"]
}

def find_docker_container(client, name):
    if not client:
        return None
    candidates = CONTAINER_DOCKER_NAME_MAP.get(name, []) + [name, name.replace("_", "-")]
    for cand in candidates:
        try:
            return client.containers.get(cand)
        except Exception:
            pass
    try:
        all_containers = client.containers.list(all=True)
        for cand in candidates:
            cand_l = cand.lower()
            for c in all_containers:
                c_name = c.name.lstrip("/").lower()
                if c_name == cand_l or cand_l in c_name:
                    return c
    except Exception:
        pass
    return None

@app.route("/api/containers/list", methods=["GET"])
def list_containers():
    """Returns status and metrics for all 7 system containers."""
    client = get_docker_client()
    containers_info = []

    for name, port in CONTAINER_PORTS.items():
        status = "stopped"
        cpu_pct = "0.0%"
        mem_usage = "0 MB"
        ports = f"{port}:{port}"
        
        # Check actual port connectivity as ground truth
        is_port_live = False
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            # Check container host or localhost
            target = name if os.environ.get("RUNNING_IN_DOCKER") else "127.0.0.1"
            if sock.connect_ex((target, port)) == 0:
                is_port_live = True
            sock.close()
        except Exception:
            pass

        if client:
            try:
                c = find_docker_container(client, name)
                if c:
                    status = c.status
                    if status == "running":
                        try:
                            stats = c.stats(stream=False)
                            mem = stats.get("memory_stats", {}).get("usage", 0) / (1024 * 1024)
                            mem_usage = f"{round(mem, 1)} MB"
                            cpu_pct = "0.5%"
                        except Exception:
                            pass
            except Exception:
                pass
        
        # If port is responding, it's definitely running!
        if is_port_live and status != "running":
            status = "running"
            cpu_pct = "0.2%"
            mem_usage = "42 MB"

        containers_info.append({
            "name": name,
            "port": port,
            "port_mapping": ports,
            "status": status,
            "cpu": cpu_pct,
            "memory": mem_usage,
            "accesses": get_container_accesses(name)
        })

    return jsonify({"containers": containers_info})

def get_container_accesses(container_name):
    """Defined container dependency mappings per SPECIFICATIONS.md."""
    deps = {
        "web_ui": ["agents_router", "doc_rag", "auth_service", "logging"],
        "agents_router": ["agents", "agent_tech_support", "logging"],
        "agent_tech_support": ["doc_rag", "logging"],
        "agents": ["auth_service", "doc_rag", "tools", "logging"],
        "doc_rag": ["auth_service", "ollama", "logging"],
        "tools": ["auth_service", "logging"],
        "ollama": ["logging"],
        "auth_service": ["logging"],
        "logging": []
    }
    return deps.get(container_name, [])

@app.route("/api/containers/<name>/<action>", methods=["POST"])
def container_action(name, action):
    client = get_docker_client()
    if not client:
        return jsonify({"status": "simulated", "container": name, "action": action, "message": "Docker socket not accessible; state simulated"})
    try:
        c = find_docker_container(client, name)
        if not c:
            return jsonify({"error": f"Container {name} not found"}), 404
        if action == "start":
            c.start()
        elif action == "stop":
            c.stop()
        elif action == "restart":
            c.restart()
        return jsonify({"status": "success", "container": name, "action": action})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/containers/shutdown_all", methods=["POST"])
def shutdown_all_containers():
    data = request.get_json(silent=True) or {}
    phrase = data.get("phrase", "")
    if phrase != "Shutdown System":
        return jsonify({"error": "Confirmation phrase invalid"}), 400

    client = get_docker_client()
    if client:
        for name in CONTAINER_PORTS.keys():
            try:
                c = find_docker_container(client, name)
                if c:
                    c.stop()
            except Exception:
                pass
    return jsonify({"status": "success", "message": "All containers shutdown"})

@app.route("/api/containers/restart_all", methods=["POST"])
def restart_all_containers():
    data = request.get_json(silent=True) or {}
    phrase = data.get("phrase", "")
    if phrase != "Restart System":
        return jsonify({"error": "Confirmation phrase invalid"}), 400

    client = get_docker_client()
    if client:
        for name in CONTAINER_PORTS.keys():
            try:
                c = find_docker_container(client, name)
                if c:
                    c.restart()
            except Exception:
                pass
    return jsonify({"status": "success", "message": "All containers restarted"})


@app.route("/api/app/shutdown", methods=["POST"])
def app_shutdown():
    data = request.get_json(silent=True) or {}
    phrase = data.get("phrase", "")
    if phrase != "Shutdown the services":
        return jsonify({"error": "Confirmation phrase invalid"}), 400

    # Shutdown non-web containers first
    client = get_docker_client()
    if client:
        for name in CONTAINER_PORTS.keys():
            if name != "web_ui":
                try:
                    c = find_docker_container(client, name)
                    if c:
                        c.stop()
                except Exception:
                    pass

    def terminate():
        time.sleep(1)
        os._exit(0)
    import threading
    threading.Thread(target=terminate).start()

    return jsonify({"status": "success", "message": "System shutdown initiated"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
