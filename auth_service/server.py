import os
import sqlite3
import hashlib
import secrets
import json
import time
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from jwt_auth import generate_jwt_token, decode_jwt_token, get_domain_from_email, extract_jwt_from_request
except ImportError:
    from auth_service.jwt_auth import generate_jwt_token, decode_jwt_token, get_domain_from_email, extract_jwt_from_request

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

SECRETS_DIR = os.environ.get("SECRETS_DIR", os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "secrets")))
os.makedirs(SECRETS_DIR, exist_ok=True)
DB_PATH = os.path.join(SECRETS_DIR, "auth.db")

LOGGING_SERVICE_URL = os.environ.get("LOGGING_SERVICE_URL", "http://logging:8006/api/logs")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def log_to_logging_container(invoker, recipient, event_type, short_desc, payload, status="success"):
    try:
        url = LOGGING_SERVICE_URL
        # In local non-docker dev, fallback to localhost if logging host not resolved
        if "logging:8006" in url and not os.environ.get("RUNNING_IN_DOCKER"):
            url = url.replace("logging:8006", "127.0.0.1:8006")
        
        requests.post(url, json={
            "invoker": invoker,
            "recipient": recipient,
            "type": event_type,
            "short_description": short_desc,
            "payload": payload,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, timeout=2)
    except Exception as e:
        # Avoid crashing auth if logging service is starting up
        pass

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'User',
        status TEXT NOT NULL DEFAULT 'Active',
        domain TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Ensure status and domain columns exist if migrated
    cursor.execute("PRAGMA table_info(users)")
    cols = [r["name"] for r in cursor.fetchall()]
    if "status" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
    if "domain" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN domain TEXT")

    # User access/requests logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        request_type TEXT NOT NULL,
        status TEXT NOT NULL,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # API keys table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_name TEXT NOT NULL,
        key_hash TEXT UNIQUE NOT NULL,
        key_prefix TEXT NOT NULL,
        creator_email TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        containers TEXT NOT NULL,     -- JSON array of container names
        access_levels TEXT NOT NULL,  -- JSON array of access levels corresponding to containers
        status TEXT NOT NULL DEFAULT 'active' -- active, inactive, delete
    );
    """)

    # API key activity logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_key_activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_id INTEGER,
        key_name TEXT NOT NULL,
        key_prefix TEXT,
        container_name TEXT,
        access_level TEXT,
        action_type TEXT NOT NULL,
        status TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()

    # Seed initial activity logs for pre-existing keys if none exist
    cursor.execute("SELECT id, key_name, key_prefix, containers, access_levels, created_at FROM api_keys")
    existing_keys = cursor.fetchall()
    for ek in existing_keys:
        cursor.execute("SELECT id FROM api_key_activity_logs WHERE key_id = ?", (ek["id"],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO api_key_activity_logs (key_id, key_name, key_prefix, container_name, access_level, action_type, status, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ek["id"], ek["key_name"], ek["key_prefix"],
                ek["containers"], ek["access_levels"],
                "Key Generation", "Success", "Configured Container API Key generated", "127.0.0.1", ek["created_at"]
            ))
    conn.commit()

    # Seed default Admin account if not present (Admin has no domain)
    cursor.execute("SELECT id FROM users WHERE email = 'admin'")
    hashed_admin = generate_password_hash("admin123")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, status, domain, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("admin", hashed_admin, "Admin", "Active", None, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        print("Initialized default admin account: admin / admin123")
    else:
        cursor.execute("UPDATE users SET password_hash = ?, role = 'Admin', status = 'Active', domain = NULL WHERE email = 'admin'", (hashed_admin,))
        conn.commit()

    # Seed test domain 1: user@example-a.com
    cursor.execute("SELECT id FROM users WHERE email = 'user@example-a.com'")
    hashed_a = generate_password_hash("password123")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, status, domain, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("user@example-a.com", hashed_a, "User", "Active", "example-a.com", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        print("Initialized test domain 1 user: user@example-a.com / password123")
    else:
        cursor.execute("UPDATE users SET password_hash = ?, domain = 'example-a.com', status = 'Active' WHERE email = 'user@example-a.com'", (hashed_a,))
        conn.commit()

    # Seed test domain 2: user@sample-b.com
    cursor.execute("SELECT id FROM users WHERE email = 'user@sample-b.com'")
    hashed_b = generate_password_hash("password123")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, status, domain, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("user@sample-b.com", hashed_b, "User", "Active", "sample-b.com", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        print("Initialized test domain 2 user: user@sample-b.com / password123")
    else:
        cursor.execute("UPDATE users SET password_hash = ?, domain = 'sample-b.com', status = 'Active' WHERE email = 'user@sample-b.com'", (hashed_b,))
        conn.commit()

    # Purge any deleted keys
    cursor.execute("DELETE FROM api_keys WHERE status = 'delete'")
    conn.commit()

    conn.close()

init_db()

def record_api_key_activity(key_id, key_name, key_prefix, container_name, access_level, action_type, status, details="", ip_address="127.0.0.1", created_at=None):
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO api_key_activity_logs (key_id, key_name, key_prefix, container_name, access_level, action_type, status, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (key_id, key_name, key_prefix, str(container_name or ""), str(access_level or ""), action_type, status, str(details or ""), ip_address, created_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging api key activity: {e}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "auth_service", "port": 8001})

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""
    client_ip = request.remote_addr or data.get("ip_address", "127.0.0.1")

    if not username or not password:
        return jsonify({"status": "failed", "error": "Username and password required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"status": "failed", "error": "User already exists"}), 400

    hashed = generate_password_hash(password)
    now_iso = datetime.now(timezone.utc).isoformat()
    user_domain = get_domain_from_email(username)
    # When a new user account is created, it is initially set to "Locked" status.
    cursor.execute(
        "INSERT INTO users (email, password_hash, role, status, domain, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (username, hashed, "User", "Locked", user_domain, now_iso)
    )
    cursor.execute(
        "INSERT INTO user_activity_logs (user_email, request_type, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, "New User Registration", "Success (Locked)", client_ip, now_iso)
    )
    conn.commit()
    conn.close()

    log_to_logging_container(
        invoker=username,
        recipient="auth_service",
        event_type="user_registration",
        short_desc="New user registered with Locked status",
        payload={"username": username, "status": "Locked", "ip": client_ip}
    )

    return jsonify({"status": "success", "message": "Account created with Locked status. Please contact the administrator to unlock."}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""
    client_ip = request.remote_addr or data.get("ip_address", "127.0.0.1")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (username,))
    user = cursor.fetchone()

    status = "Failed"
    success = False
    role = "User"
    user_status = "Active"
    error_msg = "Invalid username or password."

    if user and check_password_hash(user["password_hash"], password):
        user_status = dict(user).get("status", "Active")
        if user_status == "Locked":
            status = "Locked"
            error_msg = "Account is Locked. Please contact the administrator."
        else:
            status = "Success"
            success = True
            role = user["role"]

    # Record user access log
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "INSERT INTO user_activity_logs (user_email, request_type, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
        (username or "unknown", "Login", status, client_ip, now_iso)
    )
    conn.commit()
    conn.close()

    # Stream log to Logging container
    log_to_logging_container(
        invoker=username or "anonymous",
        recipient="auth_service",
        event_type="user_login",
        short_desc=f"User login attempt: {status}",
        payload={"username": username, "status": status, "role": role, "ip": client_ip},
        status="success" if success else "failure"
    )

    if success:
        user_domain = dict(user).get("domain") or get_domain_from_email(username)
        # Create multi-tenant JWT token
        jwt_token = generate_jwt_token(email=username, role=role, domain=user_domain)
        return jsonify({
            "status": "success",
            "token": jwt_token,
            "jwt_token": jwt_token,
            "session_token": jwt_token,
            "user": {
                "email": username,
                "domain": user_domain,
                "role": role,
                "status": user_status,
                "storage_backend": "SQLite (auth_service/secrets/auth.db)"
            }
        })
    elif status == "Locked":
        return jsonify({"status": "failed", "error": error_msg, "is_locked": True}), 403
    else:
        return jsonify({"status": "failed", "error": error_msg}), 401

@app.route("/api/auth/validate_token", methods=["POST", "GET"])
def validate_token_route():
    token = extract_jwt_from_request(request)
    if not token:
        return jsonify({"valid": False, "error": "Missing JWT token"}), 401
    payload = decode_jwt_token(token)
    if not payload:
        return jsonify({"valid": False, "error": "Invalid or expired JWT token"}), 403
    return jsonify({
        "valid": True,
        "email": payload.get("email"),
        "domain": payload.get("domain"),
        "role": payload.get("role", "User"),
        "claims": payload,
        "user": payload
    })

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "unknown")
    client_ip = request.remote_addr or data.get("ip_address", "127.0.0.1")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_activity_logs (user_email, request_type, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, "Logout", "Success", client_ip, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()

    log_to_logging_container(
        invoker=username,
        recipient="auth_service",
        event_type="user_logout",
        short_desc="User logout",
        payload={"username": username, "ip": client_ip}
    )

    return jsonify({"status": "success"})

# User Management APIs
@app.route("/api/users", methods=["GET"])
def list_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, role, status, created_at FROM users ORDER BY id ASC")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"users": users})

@app.route("/api/users/<int:user_id>/status", methods=["PUT"])
def update_user_status(user_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ["Active", "Locked"]:
        return jsonify({"error": "Invalid status"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "user_id": user_id, "new_status": new_status})

@app.route("/api/users/<int:user_id>/role", methods=["PUT"])
def update_user_role(user_id):
    data = request.get_json(silent=True) or {}
    new_role = data.get("role")
    if new_role not in ["Admin", "Editor", "User"]:
        return jsonify({"error": "Invalid role"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "user_id": user_id, "new_role": new_role})

@app.route("/api/users/<int:user_id>/reset_password", methods=["POST"])
def reset_password(user_id):
    data = request.get_json(silent=True) or {}
    new_password = data.get("password") or "admin123"
    hashed = generate_password_hash(new_password)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, user_id))
    cursor.execute(
        "INSERT INTO user_activity_logs (user_email, request_type, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
        (row["email"], "Password Reset", "Success", request.remote_addr, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Password reset successfully for {row['email']}"})

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Deleted user {row['email']}"})

@app.route("/api/users", methods=["POST"])
def admin_create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "User")
    status = data.get("status", "Active")
    if role not in ["Admin", "Editor", "User"]:
        role = "User"
    if status not in ["Active", "Locked"]:
        status = "Active"

    if not username or not password:
        return jsonify({"status": "failed", "error": "Username and password are required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"status": "failed", "error": "User already exists"}), 400

    hashed = generate_password_hash(password)
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "INSERT INTO users (email, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, hashed, role, status, now_iso)
    )
    user_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO user_activity_logs (user_email, request_type, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, "Create User", "Success", request.remote_addr, now_iso)
    )
    conn.commit()
    conn.close()

    log_to_logging_container(
        invoker="admin",
        recipient="auth_service",
        event_type="user_creation",
        short_desc=f"Admin created user {username}",
        payload={"username": username, "role": role, "status": status}
    )

    return jsonify({"status": "success", "message": f"User {username} created successfully", "user_id": user_id}), 201

@app.route("/api/users/bulk_delete", methods=["POST"])
def bulk_delete_users():
    data = request.get_json(silent=True) or {}
    user_ids = data.get("user_ids", [])
    if not user_ids:
        return jsonify({"error": "No user IDs provided"}), 400

    conn = get_db()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in user_ids)
    cursor.execute(f"SELECT id, email FROM users WHERE id IN ({placeholders})", user_ids)
    users_to_delete = cursor.fetchall()
    now_iso = datetime.now(timezone.utc).isoformat()
    for u in users_to_delete:
        cursor.execute(
            "INSERT INTO user_activity_logs (user_email, request_type, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
            (u["email"], "Delete User", "Success", request.remote_addr, now_iso)
        )
    cursor.execute(f"DELETE FROM users WHERE id IN ({placeholders})", user_ids)
    conn.commit()
    conn.close()

    log_to_logging_container(
        invoker="admin",
        recipient="auth_service",
        event_type="user_bulk_deletion",
        short_desc=f"Deleted {len(user_ids)} users",
        payload={"user_ids": user_ids, "deleted_count": len(user_ids)}
    )

    return jsonify({"status": "success", "deleted_count": len(user_ids)})

@app.route("/api/users/activity_logs", methods=["GET"])
def get_user_activity_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_email, request_type, status, ip_address, created_at FROM user_activity_logs ORDER BY id DESC")
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"activity_logs": logs})

# API Keys Management
@app.route("/api/keys", methods=["GET"])
def list_keys():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, key_name, key_prefix, creator_email, created_at, expires_at, containers, access_levels, status FROM api_keys WHERE status != 'delete' ORDER BY id DESC")
    keys = []
    for r in cursor.fetchall():
        item = dict(r)
        try:
            item["containers"] = json.loads(item["containers"])
            item["access_levels"] = json.loads(item["access_levels"])
        except Exception:
            item["containers"] = []
            item["access_levels"] = []
        keys.append(item)
    conn.close()
    return jsonify({"keys": keys})

@app.route("/api/keys", methods=["POST"])
def generate_key():
    data = request.get_json(silent=True) or {}
    key_name = data.get("key_name", "Default Key")
    creator = data.get("creator_email", "admin")
    containers = data.get("containers", [])
    access_levels = data.get("access_levels", [])
    expires_at = data.get("expires_at")

    if not expires_at:
        # Default 1 year from now
        expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

    # Generate key: key-<32 random hex>
    raw_secret = secrets.token_hex(16)
    full_key = f"key-{raw_secret}"
    key_prefix = full_key[:8] + "..."
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO api_keys (key_name, key_hash, key_prefix, creator_email, created_at, expires_at, containers, access_levels, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (
        key_name,
        key_hash,
        key_prefix,
        creator,
        datetime.now(timezone.utc).isoformat(),
        expires_at,
        json.dumps(containers),
        json.dumps(access_levels)
    ))
    key_id = cursor.lastrowid
    conn.commit()
    conn.close()

    record_api_key_activity(
        key_id=key_id,
        key_name=key_name,
        key_prefix=key_prefix,
        container_name=",".join(containers),
        access_level=",".join(access_levels),
        action_type="Key Generation",
        status="Success",
        details=f"Containers: {', '.join(containers) if containers else 'None'}; Access: {', '.join(access_levels) if access_levels else 'None'}",
        ip_address=request.remote_addr or "127.0.0.1"
    )

    log_to_logging_container(
        invoker=creator,
        recipient="auth_service",
        event_type="api_key_generation",
        short_desc=f"Generated API key '{key_name}'",
        payload={"key_name": key_name, "containers": containers, "access_levels": access_levels}
    )

    return jsonify({
        "status": "success",
        "key_id": key_id,
        "api_key": full_key,
        "key_name": key_name,
        "key_prefix": key_prefix,
        "expires_at": expires_at
    }), 201

@app.route("/api/keys/<int:key_id>", methods=["PUT"])
def update_key(key_id):
    data = request.get_json(silent=True) or {}
    key_name = data.get("key_name")
    expires_at = data.get("expires_at")
    status = data.get("status")
    containers = data.get("containers")
    access_levels = data.get("access_levels")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
    existing_key = cursor.fetchone()
    if not existing_key:
        conn.close()
        return jsonify({"error": "API key not found"}), 404

    updates = []
    params = []
    if key_name:
        updates.append("key_name = ?")
        params.append(key_name)
    if expires_at:
        updates.append("expires_at = ?")
        params.append(expires_at)
    if status:
        updates.append("status = ?")
        params.append(status)
    if containers is not None:
        updates.append("containers = ?")
        params.append(json.dumps(containers))
    if access_levels is not None:
        updates.append("access_levels = ?")
        params.append(json.dumps(access_levels))

    if not updates:
        conn.close()
        return jsonify({"error": "No updates provided"}), 400

    params.append(key_id)
    cursor.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    record_api_key_activity(
        key_id=key_id,
        key_name=key_name or existing_key["key_name"],
        key_prefix=existing_key["key_prefix"],
        container_name=",".join(containers) if containers is not None else existing_key["containers"],
        access_level=",".join(access_levels) if access_levels is not None else existing_key["access_levels"],
        action_type="Key Updated",
        status="Success",
        details=f"Updated: {', '.join(updates)}",
        ip_address=request.remote_addr or "127.0.0.1"
    )

    return jsonify({"status": "success", "key_id": key_id})

@app.route("/api/keys/<int:key_id>", methods=["DELETE"])
def delete_key(key_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "API key not found"}), 404

    cursor.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()

    record_api_key_activity(
        key_id=key_id,
        key_name=row["key_name"],
        key_prefix=row["key_prefix"],
        container_name=row["containers"],
        access_level=row["access_levels"],
        action_type="Key Deleted",
        status="Success",
        details="API key deleted",
        ip_address=request.remote_addr or "127.0.0.1"
    )

    return jsonify({"status": "success", "message": "API key deleted"})

@app.route("/api/keys/bulk_delete", methods=["POST"])
def bulk_delete_keys():
    data = request.get_json(silent=True) or {}
    key_ids = data.get("key_ids", [])
    if not key_ids:
        return jsonify({"error": "No key IDs provided"}), 400
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in key_ids)
    cursor.execute(f"SELECT * FROM api_keys WHERE id IN ({placeholders})", key_ids)
    keys_to_delete = cursor.fetchall()
    for k in keys_to_delete:
        record_api_key_activity(
            key_id=k["id"],
            key_name=k["key_name"],
            key_prefix=k["key_prefix"],
            container_name=k["containers"],
            access_level=k["access_levels"],
            action_type="Key Deleted",
            status="Success",
            details="Bulk deleted API key",
            ip_address=request.remote_addr or "127.0.0.1"
        )
    cursor.execute(f"DELETE FROM api_keys WHERE id IN ({placeholders})", key_ids)
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "deleted_count": len(key_ids)})

@app.route("/api/keys/<int:key_id>/activities", methods=["GET"])
def get_key_activities_by_id(key_id):
    key_prefix = request.args.get("key_prefix")
    conn = get_db()
    cursor = conn.cursor()
    if key_prefix:
        cursor.execute(
            "SELECT * FROM api_key_activity_logs WHERE key_id = ? AND key_prefix = ? ORDER BY id DESC",
            (key_id, key_prefix)
        )
    else:
        cursor.execute(
            "SELECT * FROM api_key_activity_logs WHERE key_id = ? ORDER BY id DESC",
            (key_id,)
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({"status": "success", "key_id": key_id, "activities": rows})

@app.route("/api/keys/activities", methods=["GET"])
def get_all_key_activities():
    key_name = request.args.get("key_name")
    key_prefix = request.args.get("key_prefix")
    conn = get_db()
    cursor = conn.cursor()
    if key_name and key_prefix:
        cursor.execute(
            "SELECT * FROM api_key_activity_logs WHERE key_name = ? AND key_prefix = ? ORDER BY id DESC",
            (key_name, key_prefix)
        )
    elif key_prefix:
        cursor.execute(
            "SELECT * FROM api_key_activity_logs WHERE key_prefix = ? ORDER BY id DESC",
            (key_prefix,)
        )
    elif key_name:
        cursor.execute(
            "SELECT * FROM api_key_activity_logs WHERE key_name = ? ORDER BY id DESC",
            (key_name,)
        )
    else:
        cursor.execute("SELECT * FROM api_key_activity_logs ORDER BY id DESC LIMIT 200")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({"status": "success", "activities": rows})

@app.route("/api/auth/validate_key", methods=["POST"])
def validate_key():
    data = request.get_json(silent=True) or {}
    api_key = data.get("api_key", "").strip()
    target_container = data.get("container", "").lower()
    required_level = data.get("access_level", "read").lower()
    invoker_container = data.get("invoker", "unknown")
    req_type = data.get("request_type", "api_call")
    client_ip = request.remote_addr or data.get("ip_address", "127.0.0.1")

    # Check if incoming key/token is a JWT
    token_to_check = api_key or extract_jwt_from_request(request)
    jwt_payload = decode_jwt_token(token_to_check) if token_to_check else None
    if jwt_payload:
        user_domain = jwt_payload.get("domain")
        user_role = jwt_payload.get("role", "User")
        return jsonify({
            "valid": True,
            "jwt": True,
            "key_name": "JWT-" + (jwt_payload.get("email") or "user"),
            "email": jwt_payload.get("email"),
            "domain": user_domain,
            "access_level": "Admin" if (user_role == "Admin" or user_domain is None) else "Read",
            "containers": ["all"]
        })

    # If development bypass or empty key handling
    if not api_key:
        result = "Failed: Missing API key"
        log_to_logging_container(
            invoker=invoker_container,
            recipient="auth_service",
            event_type="api_key_validation",
            short_desc=result,
            payload={"invoker": invoker_container, "container": target_container, "result": "failure"},
            status="failure"
        )
        return jsonify({"valid": False, "error": "API key required"}), 401

    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE key_hash = ? AND status = 'active'", (key_hash,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        # Check master root key bypass if configured in env
        master_key = os.environ.get("MASTER_API_KEY", "")
        if master_key and api_key == master_key:
            return jsonify({"valid": True, "access_level": "Admin", "containers": ["all"]})

        log_to_logging_container(
            invoker=invoker_container,
            recipient="auth_service",
            event_type="api_key_validation",
            short_desc="Failed: Invalid or inactive API key",
            payload={"invoker": invoker_container, "container": target_container, "result": "failure"},
            status="failure"
        )
        return jsonify({"valid": False, "error": "Invalid or inactive API key"}), 403

    # Check expiration
    expires_at = row["expires_at"]
    if expires_at and datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc):
        record_api_key_activity(
            key_id=row["id"],
            key_name=row["key_name"],
            key_prefix=row["key_prefix"],
            container_name=target_container,
            access_level=required_level,
            action_type=req_type or "API Key Access",
            status="Expired",
            details=f"Key expired on {expires_at}",
            ip_address=client_ip
        )
        return jsonify({"valid": False, "error": "API key expired"}), 403

    containers = json.loads(row["containers"]) if row["containers"] else []
    access_levels = json.loads(row["access_levels"]) if row["access_levels"] else []

    # Map container to level
    allowed = False
    granted_level = "None"
    
    # If key applies to all containers
    if "all" in [c.lower() for c in containers]:
        allowed = True
        granted_level = access_levels[0] if access_levels else "Admin"
    else:
        for idx, c in enumerate(containers):
            if c.lower() == target_container:
                granted_level = access_levels[idx] if idx < len(access_levels) else "Read"
                allowed = True
                break

    # Access level hierarchy: Admin > Write > Read
    level_weights = {"read": 1, "write": 2, "admin": 3}
    if allowed:
        user_weight = level_weights.get(granted_level.lower(), 1)
        req_weight = level_weights.get(required_level.lower(), 1)
        if user_weight < req_weight:
            allowed = False

    resp_data = {
        "valid": bool(allowed),
        "key_name": row["key_name"],
        "access_level": granted_level,
        "containers": containers
    } if allowed else {"valid": False, "error": f"Permission denied for container {target_container}"}

    record_api_key_activity(
        key_id=row["id"],
        key_name=row["key_name"],
        key_prefix=row["key_prefix"],
        container_name=target_container,
        access_level=granted_level if allowed else required_level,
        action_type=req_type or "API Key Access",
        status="Success" if allowed else "Permission Denied",
        details=f"Target: {target_container}, Invoker: {invoker_container}",
        ip_address=client_ip
    )

    log_to_logging_container(
        invoker=invoker_container or row["key_name"],
        recipient=target_container or "auth_service",
        event_type="api_key_access",
        short_desc=f"API key access ({target_container}): {'Success' if allowed else 'Permission Denied'}",
        payload={
            "container_name": target_container,
            "user_name_or_key_name": row["creator_email"] if invoker_container == "web_ui" else row["key_name"],
            "ip_address": client_ip,
            "request_type": req_type,
            "date_time": datetime.now(timezone.utc).isoformat(),
            "result": "success" if allowed else "failure",
            "request_payload": data,
            "response_payload": resp_data
        },
        status="success" if allowed else "failure"
    )

    if allowed:
        return jsonify(resp_data)
    else:
        return jsonify(resp_data), 403

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=port)

