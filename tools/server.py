import os
import csv
import json
import time
from datetime import datetime, timezone
import requests
from flask import Flask, request, jsonify, Response

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

import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from scripts.employee_search import seed_employee_data, search_employees
    from scripts.customer_search import seed_customer_data, search_customers
    from scripts.stock_analysis import analyze_stocks
    from jwt_auth import decode_jwt_token, extract_jwt_from_request
except ImportError:
    from tools.scripts.employee_search import seed_employee_data, search_employees
    from tools.scripts.customer_search import seed_customer_data, search_customers
    from tools.scripts.stock_analysis import analyze_stocks
    import sys
    from pathlib import Path
    _parent = str(Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from jwt_auth import decode_jwt_token, extract_jwt_from_request

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
CSV_PATH = os.path.join(DATA_DIR, "employee_database.csv")
EMPLOYEE_CSV_PATH = CSV_PATH
CUSTOMER_CSV_PATH = os.path.join(DATA_DIR, "customer_database.csv")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth_service:8001/api/auth/validate_key")
LOGGING_SERVICE_URL = os.environ.get("LOGGING_SERVICE_URL", "http://logging:8006/api/logs")
SECRETS_DIR = os.environ.get("SECRETS_DIR", os.path.join(os.path.dirname(__file__), "secrets"))
KEYS_FILE = os.path.join(SECRETS_DIR, "keys")

def load_tools_keys():
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
            print(f"[Tools] Error reading keys file: {e}")
    return keys

# Seed employee database and customer database on startup if needed
try:
    seed_employee_data(EMPLOYEE_CSV_PATH)
    seed_customer_data(CUSTOMER_CSV_PATH)
except Exception as e:
    print(f"[Tools] Database seeding note: {e}")


# Curated equities basket for stock search
TRACKED_TICKERS = [
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "base_price": 118.50, "change_pct": 5.82},
    {"symbol": "AAPL", "name": "Apple Inc.", "base_price": 224.30, "change_pct": 1.25},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "base_price": 432.10, "change_pct": -0.84},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "base_price": 164.75, "change_pct": 3.14},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "base_price": 186.20, "change_pct": 2.45},
    {"symbol": "TSLA", "name": "Tesla Inc.", "base_price": 242.60, "change_pct": -4.68},
    {"symbol": "META", "name": "Meta Platforms Inc.", "base_price": 512.90, "change_pct": 4.10},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "base_price": 149.80, "change_pct": 6.35},
    {"symbol": "INTC", "name": "Intel Corporation", "base_price": 19.45, "change_pct": -5.92},
    {"symbol": "AVGO", "name": "Broadcom Inc.", "base_price": 168.20, "change_pct": 3.75},
    {"symbol": "CRM", "name": "Salesforce Inc.", "base_price": 252.10, "change_pct": -1.15},
    {"symbol": "PLTR", "name": "Palantir Technologies", "base_price": 36.40, "change_pct": 8.42},
    {"symbol": "SMCI", "name": "Super Micro Computer", "base_price": 44.50, "change_pct": -7.85},
    {"symbol": "QCOM", "name": "Qualcomm Inc.", "base_price": 165.90, "change_pct": -2.30},
    {"symbol": "ARM", "name": "Arm Holdings plc", "base_price": 138.70, "change_pct": 5.12},
]

def get_user_auth_context(req):
    """Extract and decode JWT token to determine user identity and tenant domain."""
    token = extract_jwt_from_request(req)
    if not token:
        # Check Authorization header directly as fallback
        auth_hdr = req.headers.get("Authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()

    if not token:
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

def can_access_csv(csv_name: str, auth_ctx: dict) -> tuple:
    """Check if tenant domain or admin is authorized to access the given CSV.
    - Admin (no domain): access to BOTH employee_database.csv and customer_database.csv.
    - example-a.com: access to employee_database.csv.
    - sample-b.com: access to customer_database.csv.
    """
    clean_name = os.path.basename(csv_name).lower()
    if not auth_ctx.get("authenticated"):
        # Default allow if no token sent in unauthenticated legacy mode, but if domain is present check it
        return True, "No auth context"

    if auth_ctx.get("is_admin") or auth_ctx.get("role") == "Admin" or auth_ctx.get("domain") is None:
        return True, "Admin access granted to all databases"

    domain = (auth_ctx.get("domain") or "").lower()

    if "employee" in clean_name:
        if domain == "example-a.com":
            return True, "Domain example-a.com authorized for employee_database.csv"
        return False, f"Access denied: Domain '{domain}' cannot access employee_database.csv (requires 'example-a.com' or Admin)"

    if "customer" in clean_name:
        if domain == "sample-b.com":
            return True, "Domain sample-b.com authorized for customer_database.csv"
        return False, f"Access denied: Domain '{domain}' cannot access customer_database.csv (requires 'sample-b.com' or Admin)"

    return False, f"Access denied to database {clean_name}"

def check_auth(api_key, invoker="agent"):
    if not api_key:
        return True, "Allowed (internal default)"

    # Validate JWT token
    jwt_payload = decode_jwt_token(api_key)
    if jwt_payload:
        return True, "Valid JWT"

    return False, "Unauthorized: Valid JWT required"

def log_tool_event(conv_id, invoker, tool_name, args, req_payload, resp_payload, status, dur_ms):
    try:
        url = LOGGING_SERVICE_URL
        if "logging:8006" in url and not os.environ.get("RUNNING_IN_DOCKER"):
            url = url.replace("logging:8006", "127.0.0.1:8006")
        requests.post(url, json={
            "invoker": invoker,
            "recipient": "tools",
            "conversation_id": conv_id,
            "type": "tool_call",
            "short_description": f"Tool execution: {tool_name}",
            "payload": {
                "tool": tool_name,
                "arguments": args,
                "request": req_payload,
                "response": resp_payload
            },
            "status": status,
            "duration_ms": dur_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, timeout=2)
    except Exception:
        pass

# TOOL 1: Employee search (Accessible to example-a.com and Admin)
def run_employee_search(keywords=None, field="", keyword=None):
    query_val = keywords if keywords is not None else keyword
    results = search_employees(keywords=query_val, field=field, csv_path=EMPLOYEE_CSV_PATH)
    return {
        "status": "success",
        "count": len(results),
        "total_matches": len(results),
        "results": results,
        "query": query_val,
        "field": field or "all",
        "database": "employee_database.csv",
        "authorized_domain": "example-a.com"
    }

# TOOL 1B: Customer search (Accessible to sample-b.com and Admin)
def run_customer_search(keywords=None, field="", keyword=None):
    query_val = keywords if keywords is not None else keyword
    results = search_customers(keywords=query_val, field=field, csv_path=CUSTOMER_CSV_PATH)
    return {
        "status": "success",
        "count": len(results),
        "total_matches": len(results),
        "results": results,
        "query": query_val,
        "field": field or "all",
        "database": "customer_database.csv",
        "authorized_domain": "sample-b.com"
    }

# TOOL 2: Stock search
def run_stock_search(action="gainers", limit=5, ticker=None):
    clean_act = (action or "gainers").lower().strip()
    limit = int(limit or 5)

    if ticker or clean_act == "quote":
        sym = (ticker or "NVDA").upper().strip()
        # Look in tracked equities
        for item in TRACKED_TICKERS:
            if item["symbol"] == sym:
                return {
                    "action": "quote",
                    "result": {
                        "symbol": item["symbol"],
                        "name": item["name"],
                        "price": round(item["base_price"] * (1 + item["change_pct"] / 100), 2),
                        "change_pct": item["change_pct"]
                    },
                    "status": "success"
                }
        return {"error": f"Ticker '{sym}' not found in active equities", "status": "not_found"}

    basket = []
    for item in TRACKED_TICKERS:
        basket.append({
            "symbol": item["symbol"],
            "name": item["name"],
            "price": round(item["base_price"] * (1 + item["change_pct"] / 100), 2),
            "change_pct": item["change_pct"],
        })

    if "gain" in clean_act or "increase" in clean_act or "high" in clean_act:
        sorted_list = sorted(basket, key=lambda x: x["change_pct"], reverse=True)
        return {
            "action": "highest_percentage_increase",
            "count": min(len(sorted_list), limit),
            "results": sorted_list[:limit],
            "status": "success"
        }
    else:
        sorted_list = sorted(basket, key=lambda x: x["change_pct"])
        return {
            "action": "lowest_percentage_decrease",
            "count": min(len(sorted_list), limit),
            "results": sorted_list[:limit],
            "status": "success"
        }

# TOOL 3: Time & Weather via public Open-Meteo
def run_time_weather(city="Paris"):
    clean_city = (city or "Paris").strip()
    try:
        # Geocode city
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_city}&count=1&language=en&format=json"
        geo_resp = requests.get(geo_url, timeout=4).json()
        if not geo_resp.get("results"):
            return {"error": f"City '{clean_city}' could not be located"}
        
        loc = geo_resp["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        tz = loc.get("timezone", "UTC")
        country = loc.get("country", "")

        # Weather query
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto"
        w_resp = requests.get(w_url, timeout=4).json()
        curr = w_resp.get("current", {})

        return {
            "city": loc["name"],
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "timezone": tz,
            "local_time": curr.get("time"),
            "temperature_c": curr.get("temperature_2m"),
            "temperature_f": round((curr.get("temperature_2m", 0) * 9/5) + 32, 1) if curr.get("temperature_2m") is not None else None,
            "humidity_pct": curr.get("relative_humidity_2m"),
            "wind_speed_kmh": curr.get("wind_speed_10m")
        }
    except Exception as e:
        return {"error": f"Failed to fetch weather: {e}"}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "tools", "port": 8005})

@app.route("/api/tools/list", methods=["GET"])
def list_tools():
    auth_ctx = get_user_auth_context(request)
    return jsonify({
        "tools": [
            {
                "name": "person_search.query_person_registry",
                "aliases": ["employee_search", "query_person_registry", "person_search"],
                "description": "Searches for employees and staff in employee_database.csv by search terms across name, city, country, or job title. Accessible to domain 'example-a.com' and Admin.",
                "database": "employee_database.csv",
                "authorized_domain": "example-a.com",
                "parameters": {
                    "keywords": "array of strings (or single string: search terms across name, city, country, or role)",
                    "field": "string (optional: 'name', 'city', 'country', 'job_title', 'all')"
                }
            },
            {
                "name": "customer_search.query_customer_registry",
                "aliases": ["customer_search", "query_customer_registry", "customer_registry"],
                "description": "Searches for customer records in customer_database.csv by search terms across name, address, city, country, or products purchased. Accessible to domain 'sample-b.com' and Admin.",
                "database": "customer_database.csv",
                "authorized_domain": "sample-b.com",
                "parameters": {
                    "keywords": "array of strings (or single string: search terms across name, address, city, country, or products)",
                    "field": "string (optional: 'name', 'address', 'city', 'country', 'products_purchased', 'all')"
                }
            },
            {
                "name": "stock_search.query_stocks",
                "aliases": ["stock_search", "query_stocks", "get_stock_performers"],
                "description": "Retrieve stocks with highest percentage increase or lowest percentage decrease, or get quotes for a ticker.",
                "parameters": {
                    "action": "string ('gainers' for highest % increase, 'losers' for lowest % decrease, 'quote')",
                    "limit": "integer (number of stocks to return, default 5)",
                    "ticker": "string (optional ticker symbol when action is 'quote')"
                }
            },
            {
                "name": "time_weather.get_current_weather",
                "aliases": ["time_weather", "get_current_weather"],
                "description": "Get current time, temperature, humidity, and weather conditions for a specified city.",
                "parameters": {
                    "city": "string (name of the city e.g. 'Tokyo', 'Paris', 'New York')"
                }
            }
        ],
        "user_domain": auth_ctx.get("domain"),
        "role": auth_ctx.get("role")
    })

@app.route("/api/tools/call", methods=["POST"])
def call_tool():
    start_time = time.time()
    data = request.get_json(silent=True) or {}
    tool_name = (data.get("tool") or data.get("name") or "").strip()
    arguments = data.get("arguments") or {}
    conv_id = data.get("conversation_id")
    api_key = data.get("api_key") or request.headers.get("X-API-Key")
    invoker = data.get("invoker", "agent")

    # Extract auth context for domain-specific CSV access control
    auth_ctx = get_user_auth_context(request)
    if not auth_ctx.get("authenticated") and api_key:
        jwt_p = decode_jwt_token(api_key)
        if jwt_p:
            auth_ctx = {
                "authenticated": True,
                "email": jwt_p.get("email"),
                "domain": jwt_p.get("domain"),
                "role": jwt_p.get("role", "User"),
                "is_admin": (jwt_p.get("role") == "Admin" or jwt_p.get("domain") is None)
            }

    resp_data = None
    status = "success"

    # Match tool by name or alias
    clean_tool = tool_name.lower().replace("-", "_")
    if any(k in clean_tool for k in ["customer"]):
        allowed, reason = can_access_csv("customer_database.csv", auth_ctx)
        if not allowed:
            return jsonify({"status": "error", "error": f"Authorization failed: {reason}", "database": "customer_database.csv"}), 403
        kw = arguments.get("keywords") if "keywords" in arguments else (arguments.get("keyword") or arguments.get("texts") or arguments.get("name") or arguments.get("query") or "")
        field = arguments.get("field") or ""
        resp_data = run_customer_search(keywords=kw, field=field)
    elif any(k in clean_tool for k in ["person", "employee", "registry"]):
        allowed, reason = can_access_csv("employee_database.csv", auth_ctx)
        if not allowed:
            return jsonify({"status": "error", "error": f"Authorization failed: {reason}", "database": "employee_database.csv"}), 403
        kw = arguments.get("keywords") if "keywords" in arguments else (arguments.get("keyword") or arguments.get("texts") or arguments.get("name") or arguments.get("query") or "")
        field = arguments.get("field") or ""
        resp_data = run_employee_search(keywords=kw, field=field)
    elif any(k in clean_tool for k in ["stock", "equity", "ticker"]):
        act = arguments.get("action") or ("gainers" if "gain" in clean_tool else "losers" if "lose" in clean_tool else "gainers")
        lim = arguments.get("limit") or 5
        ticker = arguments.get("ticker")
        resp_data = run_stock_search(action=act, limit=lim, ticker=ticker)
    elif any(k in clean_tool for k in ["weather", "time", "metro"]):
        city = arguments.get("city") or arguments.get("location") or "Paris"
        resp_data = run_time_weather(city=city)
    else:
        status = "error"
        resp_data = {"error": f"Unknown tool: '{tool_name}'"}

    duration_ms = int((time.time() - start_time) * 1000)

    # Log tool invocation to Logging container
    log_tool_event(
        conv_id=conv_id,
        invoker=invoker,
        tool_name=tool_name,
        args=arguments,
        req_payload=data,
        resp_payload=resp_data,
        status=status,
        dur_ms=duration_ms
    )

    return jsonify({
        "status": status,
        "tool": tool_name,
        "result": resp_data,
        "duration_ms": duration_ms
    })

# FastMCP SSE Transport Endpoints
@app.route("/sse", methods=["GET"])
def sse_endpoint():
    """FastMCP Server-Sent Events endpoint."""
    def event_stream():
        yield f"event: endpoint\ndata: /messages\n\n"
        while True:
            time.sleep(15)
            yield f": keepalive\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/messages", methods=["POST"])
def mcp_messages():
    """FastMCP async HTTP message handler."""
    data = request.get_json(silent=True) or {}
    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id", 1)

    if method == "tools/list":
        tools_list = list_tools().get_json()["tools"]
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools_list}
        })
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        res = call_tool_direct(tool_name, args)
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": json.dumps(res)}]}
        })

    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {}})

@app.route("/api/tools/data/<path:csv_name>", methods=["GET"])
def get_csv_data(csv_name):
    """Retrieve raw CSV records strictly enforcing multi-tenant domain authorization."""
    auth_ctx = get_user_auth_context(request)
    allowed, reason = can_access_csv(csv_name, auth_ctx)
    if not allowed:
        return jsonify({"status": "error", "error": reason}), 403

    target_path = os.path.join(DATA_DIR, os.path.basename(csv_name))
    if not os.path.exists(target_path):
        return jsonify({"status": "error", "error": f"File {csv_name} not found"}), 404

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return jsonify({
            "status": "success",
            "file": os.path.basename(csv_name),
            "count": len(rows),
            "rows": rows
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def call_tool_direct(tool_name, args):
    clean = tool_name.lower()
    if "customer" in clean:
        kw = args.get("keywords") if "keywords" in args else args.get("keyword", "")
        return run_customer_search(keywords=kw, field=args.get("field", ""))
    elif "person" in clean or "employee" in clean:
        kw = args.get("keywords") if "keywords" in args else args.get("keyword", "")
        return run_employee_search(keywords=kw, field=args.get("field", ""))
    elif "stock" in clean:
        return run_stock_search(args.get("action", "gainers"), args.get("limit", 5), args.get("ticker"))
    elif "weather" in clean or "time" in clean:
        return run_time_weather(args.get("city", "Paris"))
    return {"error": "Tool not found"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8005))
    app.run(host="0.0.0.0", port=port)
