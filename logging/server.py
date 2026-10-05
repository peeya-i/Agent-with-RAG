import os
import json
import time
import re
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

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

LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "log.json")

def redact_api_keys(data):
    """Recursively redact API keys from data."""
    if isinstance(data, str):
        # Redact common key patterns
        redacted = re.sub(r'(AIzaSy[0-9A-Za-z-_]{33})', '****', data)
        redacted = re.sub(r'(sk-[0-9A-Za-z-_]{20,})', '****', redacted)
        redacted = re.sub(r'(key-[0-9a-fA-F]{32})', '****', redacted)
        return redacted
    elif isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ["api_key", "apikey", "secret", "password"]):
                new_dict[k] = "****"
            else:
                new_dict[k] = redact_api_keys(v)
        return new_dict
    elif isinstance(data, list):
        return [redact_api_keys(item) for item in data]
    return data

def extract_metadata_from_payload(payload):
    dur = 0
    model = ""
    in_tok = 0
    out_tok = 0
    if isinstance(payload, dict):
        resp = payload.get("response", {})
        req = payload.get("request", {})

        # duration
        if isinstance(resp, dict) and resp.get("duration_ms"):
            dur = resp.get("duration_ms", 0)
        elif payload.get("duration_ms"):
            dur = payload.get("duration_ms", 0)
        elif payload.get("elapsed_ms"):
            dur = payload.get("elapsed_ms", 0)
        elif payload.get("latency_ms"):
            dur = payload.get("latency_ms", 0)

        # model
        if isinstance(req, dict) and req.get("model_used"):
            model = req.get("model_used")
        elif isinstance(req, dict) and req.get("model"):
            model = req.get("model")
        elif payload.get("model"):
            model = payload.get("model")
        elif payload.get("model_used"):
            model = payload.get("model_used")

        # tokens
        tok = payload.get("token_usage") or (isinstance(resp, dict) and resp.get("token_usage")) or {}
        if isinstance(tok, dict):
            in_tok = tok.get("prompt_tokens", 0) or tok.get("input_tokens", 0)
            out_tok = tok.get("completion_tokens", 0) or tok.get("output_tokens", 0)
        if not in_tok and payload.get("input_tokens"):
            in_tok = payload.get("input_tokens", 0)
        if not out_tok and payload.get("output_tokens"):
            out_tok = payload.get("output_tokens", 0)

    try:
        dur = int(dur or 0)
    except Exception:
        dur = 0
    try:
        in_tok = int(in_tok or 0)
    except Exception:
        in_tok = 0
    try:
        out_tok = int(out_tok or 0)
    except Exception:
        out_tok = 0

    return dur, str(model or ""), in_tok, out_tok

def get_request_tz():
    tz_off_str = request.args.get("tz_offset")
    if tz_off_str is not None:
        try:
            offset_minutes = int(float(tz_off_str))
            return timezone(timedelta(minutes=-offset_minutes))
        except Exception:
            pass
    try:
        return datetime.now().astimezone().tzinfo or timezone.utc
    except Exception:
        return timezone.utc

def to_local_iso(ts_str, tz=None):
    if not ts_str:
        return ""
    if tz is None:
        tz = get_request_tz()
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts_str

def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            logs = json.loads(content)
            for l in logs:
                if not l.get("duration_ms") or not l.get("model") or not l.get("input_tokens") or not l.get("output_tokens"):
                    dur, m, in_t, out_t = extract_metadata_from_payload(l.get("payload"))
                    if not l.get("duration_ms") and dur:
                        l["duration_ms"] = dur
                    if not l.get("model") and m:
                        l["model"] = m
                    if not l.get("input_tokens") and in_t:
                        l["input_tokens"] = in_t
                    if not l.get("output_tokens") and out_t:
                        l["output_tokens"] = out_t
            return logs
    except Exception as e:
        print(f"Error reading log file: {e}")
        return []

def save_logs(logs):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "logging", "port": 8006})

@app.route("/api/logs", methods=["POST"])
def ingest_log():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No log payload provided"}), 400

    payload = redact_api_keys(data.get("payload", {}))
    p_dur, p_model, p_in_tok, p_out_tok = extract_metadata_from_payload(payload)

    duration_ms = data.get("duration_ms") or p_dur or 0
    model = data.get("model") or p_model or ""
    input_tokens = data.get("input_tokens") or p_in_tok or 0
    output_tokens = data.get("output_tokens") or p_out_tok or 0

    user = data.get("user") or (payload.get("user") if isinstance(payload, dict) else None) or (payload.get("username") if isinstance(payload, dict) else None) or (payload.get("user_name") if isinstance(payload, dict) else None) or (payload.get("email") if isinstance(payload, dict) else None) or ""
    domain = data.get("domain") or (payload.get("domain") if isinstance(payload, dict) else None) or ""
    if not domain and user and "@" in str(user):
        domain = str(user).split("@")[-1].strip().lower()

    log_entry = {
        "id": f"log_{int(time.time() * 1000)}_{os.urandom(2).hex()}",
        "timestamp": data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "type": data.get("type", "generic"),
        "invoker": data.get("invoker", "unknown"),
        "recipient": data.get("recipient", "unknown"),
        "conversation_id": data.get("conversation_id"),
        "user": user,
        "domain": domain,
        "short_description": data.get("short_description", ""),
        "payload": payload,
        "status": data.get("status", "success"),
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model,
        "is_error": bool(data.get("is_error", False))
    }

    logs = load_logs()
    logs.append(log_entry)
    save_logs(logs)

    return jsonify({"status": "success", "log_id": log_entry["id"]}), 201

@app.route("/api/logs/query", methods=["POST", "GET"])
def query_logs():
    criteria = request.get_json(silent=True) if request.method == "POST" else request.args.to_dict()
    criteria = criteria or {}

    logs = load_logs()
    filtered = []

    entity = criteria.get("entity")
    conv_id = criteria.get("conversation_id")
    event_type = criteria.get("type")
    start_date = criteria.get("start_date")
    end_date = criteria.get("end_date")
    model = criteria.get("model")

    for l in logs:
        if entity and (l.get("invoker") != entity and l.get("recipient") != entity):
            continue
        if conv_id and l.get("conversation_id") != conv_id:
            continue
        if event_type and l.get("type") != event_type:
            continue
        if model and l.get("model") != model:
            continue
        if start_date and l.get("timestamp") < start_date:
            continue
        if end_date and l.get("timestamp") > end_date:
            continue
        filtered.append(l)

    limit = int(criteria.get("limit", len(filtered)))
    return jsonify({"count": len(filtered[:limit]), "logs": filtered[:limit]})

@app.route("/api/logs/stats", methods=["GET"])
def get_stats():
    logs = load_logs()
    file_size_bytes = os.path.getsize(LOG_FILE) if os.path.exists(LOG_FILE) else 0

    per_entity = {}
    for l in logs:
        inv = l.get("invoker", "unknown")
        rec = l.get("recipient", "unknown")
        per_entity[inv] = per_entity.get(inv, 0) + 1
        if rec != "unknown" and rec != inv:
            per_entity[rec] = per_entity.get(rec, 0) + 1

    return jsonify({
        "total_logs": len(logs),
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_bytes / (1024 * 1024), 3),
        "per_entity": per_entity
    })

@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    save_logs([])
    return jsonify({"status": "cleared", "total_logs": 0})

@app.route("/api/conversations", methods=["GET"])
@app.route("/api/logs", methods=["GET"])
def list_conversations():
    logs = load_logs()
    conversations = {}

    for l in logs:
        cid = l.get("conversation_id")
        if not cid:
            continue
        if cid not in conversations:
            conversations[cid] = {
                "conversation_id": cid,
                "first_seen": l.get("timestamp"),
                "last_seen": l.get("timestamp"),
                "timestamp": l.get("timestamp"),
                "user_query": "",
                "agent_response": "",
                "agent_type": "Custom Agent",
                "events_count": 0,
                "event_count": 0,
                "model": l.get("model", "")
            }
        conv = conversations[cid]
        conv["events_count"] += 1
        conv["event_count"] = conv["events_count"]
        conv["last_seen"] = max(conv["last_seen"], l.get("timestamp") or "")
        conv["timestamp"] = conv["last_seen"]
        if l.get("model") and not conv["model"]:
            conv["model"] = l.get("model")

        payload = l.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        u = l.get("user") or payload.get("user") or payload.get("user_name") or payload.get("username") or payload.get("email")
        if u and not conv.get("user"):
            conv["user"] = u
        d = l.get("domain") or payload.get("domain")
        if not d and u and "@" in str(u):
            d = str(u).split("@")[-1].strip().lower()
        if d and not conv.get("domain"):
            conv["domain"] = d

        # Extract user query or agent response if logged
        l_type = str(l.get("type") or l.get("event_type") or "")

        if any(t in l_type for t in ["chat_request", "user_query", "prompt"]):
            query_text = payload.get("message") or payload.get("query") or payload.get("user_query") or payload.get("prompt")
            if query_text:
                conv["user_query"] = query_text
            agent_t = payload.get("agent_type") or payload.get("agent")
            if agent_t:
                conv["agent_type"] = agent_t
        elif any(t in l_type for t in ["chat_response", "agent_response"]):
            resp_text = payload.get("response") or payload.get("agent_response") or payload.get("answer") or payload.get("text")
            if isinstance(resp_text, str) and resp_text.strip():
                conv["agent_response"] = resp_text
            agent_t = payload.get("agent_type") or payload.get("agent")
            if agent_t:
                conv["agent_type"] = agent_t

        # Fallback if user_query still missing:
        if not conv["user_query"]:
            q = payload.get("user_query") or payload.get("message")
            if q and isinstance(q, str):
                conv["user_query"] = q
            elif isinstance(payload.get("steps"), list):
                for st in payload["steps"]:
                    p_arg = st.get("payload", {}).get("arguments") or st.get("result", {})
                    if isinstance(p_arg, dict) and p_arg.get("city"):
                        conv["user_query"] = f"Weather in {p_arg['city']}"
                        break
                    elif isinstance(p_arg, dict) and p_arg.get("keyword"):
                        conv["user_query"] = f"Person search: {p_arg['keyword']}"
                        break
                    elif isinstance(p_arg, dict) and p_arg.get("query"):
                        conv["user_query"] = str(p_arg["query"])
                        break

        # Fallback if agent_response still missing:
        if not conv["agent_response"]:
            r = payload.get("agent_response") or (payload.get("response") if isinstance(payload.get("response"), str) else None)
            if r and isinstance(r, str) and r.strip():
                conv["agent_response"] = r

    result = list(conversations.values())

    # Role-based filtering of conversations
    req_user = request.args.get("user")
    req_domain = request.args.get("domain")
    req_role = request.args.get("role")

    if req_role in ["User", "Editor"] and req_user:
        result = [c for c in result if (c.get("user") == req_user or c.get("user_email") == req_user)]
    elif req_role == "Admin" and req_domain:
        result = [c for c in result if (c.get("domain") == req_domain or (c.get("user") and str(c.get("user")).endswith("@" + req_domain)))]

    result.sort(key=lambda x: x["last_seen"], reverse=True)

    tz = get_request_tz()
    for conv in result:
        conv["local_timestamp"] = to_local_iso(conv.get("timestamp"), tz)
        conv["local_time"] = conv["local_timestamp"]
        if not conv.get("user"):
            conv["user"] = "anonymous"

    # Compute statistics for Log Viewer Header Pill
    total_prompts = sum(1 for l in logs if any(t in (l.get("type") or "") for t in ["chat_request", "prompt", "llm_request", "user_query"]) and (l.get("type") in ["chat_request", "send_chat_request"] or l.get("invoker") == "Web UI"))
    total_model_calls = sum(1 for l in logs if l.get("type") in ["llm_invocation", "llm_response", "llm_request"] or l.get("recipient") in ["LLM", "Custom LLM"] or l.get("invoker") in ["LLM", "Custom LLM"])
    total_ollama_embeds = sum(1 for l in logs if l.get("type") == "embedding_query" or l.get("recipient") in ["Embedding", "Embedding Service"])
    latencies = [l.get("duration_ms", 0) for l in logs if (l.get("duration_ms") or 0) > 0 and (any(t in (l.get("type") or "") for t in ["llm_response", "chat_response", "embedding_query"]))]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    statistics = {
        "total_user_prompts": total_prompts,
        "total_model_calls": total_model_calls,
        "total_ollama_embeds": total_ollama_embeds,
        "avg_latency_ms": avg_latency
    }

    return jsonify({
        "conversations": result,
        "statistics": statistics
    })

@app.route("/api/conversations/<conversation_id>/events", methods=["GET"])
def conversation_events(conversation_id):
    tz = get_request_tz()
    logs = load_logs()
    events = [l for l in logs if l.get("conversation_id") == conversation_id]
    events.sort(key=lambda x: x.get("timestamp", ""))

    req_user = request.args.get("user")
    req_domain = request.args.get("domain")
    req_role = request.args.get("role")

    if req_role in ["User", "Editor"] and req_user:
        conv_users = {l.get("user") for l in events if l.get("user")}
        if conv_users and req_user not in conv_users:
            return jsonify({"conversation_id": conversation_id, "events": []}), 403
    elif req_role == "Admin" and req_domain:
        conv_domains = {l.get("domain") for l in events if l.get("domain")}
        if conv_domains and req_domain not in conv_domains:
            return jsonify({"conversation_id": conversation_id, "events": []}), 403

    enriched = []
    for l in events:
        e = dict(l)
        e["event_type"] = l.get("type", "generic")
        e["target"] = l.get("recipient", "unknown")
        raw_ts = l.get("timestamp", "")
        e["raw_timestamp"] = raw_ts
        e["local_time"] = to_local_iso(raw_ts, tz)
        e["elapsed_ms"] = l.get("duration_ms", 0)
        e["user"] = l.get("user", "")
        e["domain"] = l.get("domain", "")
        enriched.append(e)
    return jsonify({"conversation_id": conversation_id, "events": enriched})

@app.route("/api/logs/telemetry", methods=["GET"])
def get_telemetry():
    tz = get_request_tz()
    tz_shift = int(tz.utcoffset(None).total_seconds()) if tz.utcoffset(None) else 0

    model_filter = request.args.get("model")
    raw_interval = (request.args.get("interval") or "15m").strip().lower()
    raw_range = (request.args.get("range") or request.args.get("time_range") or "1d").strip().lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Normalize interval
    if "1 min" in raw_interval or "1m" in raw_interval:
        bucket_seconds = 60
    elif "15 min" in raw_interval or "15m" in raw_interval:
        bucket_seconds = 900
    elif "1 hr" in raw_interval or "1h" in raw_interval or "hour" in raw_interval:
        bucket_seconds = 3600
    elif "1 day" in raw_interval or "1d" in raw_interval or "day" in raw_interval:
        bucket_seconds = 86400
    else:
        bucket_seconds = 900

    logs = load_logs()

    # Determine time bounds (timezone-aware)
    now = datetime.now(timezone.utc)
    end_bound = now
    if "last hr" in raw_range or "1h" in raw_range or "hour" in raw_range:
        cutoff = now - timedelta(hours=1)
    elif "1 day" in raw_range or "1d" in raw_range or "day" in raw_range:
        cutoff = now - timedelta(days=1)
    elif "week" in raw_range or "7d" in raw_range:
        cutoff = now - timedelta(days=7)
    elif "month" in raw_range or "30d" in raw_range:
        cutoff = now - timedelta(days=30)
    elif "custom" in raw_range:
        if start_date:
            try:
                if len(start_date) == 10:
                    cutoff = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                else:
                    cutoff = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except Exception:
                cutoff = now - timedelta(days=7)
        else:
            cutoff = now - timedelta(days=7)

        if end_date:
            try:
                if len(end_date) == 10:
                    end_bound = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                else:
                    end_bound = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except Exception:
                end_bound = now
        else:
            end_bound = now
    else:
        cutoff = now - timedelta(days=1)

    # Filter logs
    relevant = []
    models_used = set()
    total_chat = 0
    total_llm_requests = 0
    total_llm_responses = 0
    total_errors = 0
    total_input_tokens = 0
    total_output_tokens = 0
    latencies = []

    for l in logs:
        m = l.get("model")
        if m:
            models_used.add(m)
        if model_filter and model_filter != "All Models" and m != model_filter:
            continue

        ts_str = l.get("timestamp")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts < cutoff or ts > end_bound:
                continue
        except Exception:
            continue

        relevant.append(l)

        # Counting
        l_type = (l.get("type") or "").strip()
        is_chat_req = ("chat_request" in l_type or l_type == "user_query") and l_type != "received_chat_request"
        is_llm_req = "llm_invocation" in l_type or l_type == "llm_request"
        is_llm_resp = l_type == "llm_response" or ("llm_response" in l_type and l_type != "received_llm_response")

        if is_chat_req:
            total_chat += 1
        if is_llm_req:
            total_llm_requests += 1
        if is_llm_resp:
            total_llm_responses += 1

        if l.get("is_error") or l.get("status") in ["error", "failure"]:
            total_errors += 1

        in_tok = l.get("input_tokens", 0)
        out_tok = l.get("output_tokens", 0)
        total_input_tokens += in_tok
        total_output_tokens += out_tok

        dur = l.get("duration_ms", 0)
        if dur > 0 and (is_llm_resp or any(t in l_type for t in ["chat_response", "embedding_query"]) or l.get("recipient") in ["LLM", "Custom LLM"] or l.get("invoker") in ["LLM", "Custom LLM"]):
            latencies.append(dur)

    # Initialize continuous timeline buckets across requested time window
    start_epoch = int(cutoff.timestamp())
    end_epoch = int(end_bound.timestamp())

    start_local = start_epoch + tz_shift
    b_start_local = start_local - (start_local % bucket_seconds)
    b_start_epoch = b_start_local - tz_shift

    end_local = end_epoch + tz_shift
    b_end_local = end_local - (end_local % bucket_seconds)
    b_end_epoch = b_end_local - tz_shift

    step_seconds = bucket_seconds
    total_steps = ((b_end_epoch - b_start_epoch) // step_seconds) + 1 if step_seconds > 0 else 1
    if total_steps > 200:
        step_seconds = max(bucket_seconds, (b_end_epoch - b_start_epoch) // 100)

    buckets = {}
    cur_epoch = b_start_epoch
    span_seconds = end_epoch - start_epoch
    while cur_epoch <= b_end_epoch:
        dt_local = datetime.fromtimestamp(cur_epoch, tz)
        if bucket_seconds >= 86400 or span_seconds > 86400 * 2:
            b_key = dt_local.strftime("%m-%d" if bucket_seconds >= 86400 else "%m-%d %H:%M")
        else:
            b_key = dt_local.strftime("%H:%M")

        buckets[cur_epoch] = {
            "time": b_key,
            "local_time": b_key,
            "epoch": cur_epoch,
            "chat_requests": 0,
            "llm_requests": 0,
            "llm_responses": 0,
            "prompts": 0,
            "responses": 0,
            "errors": 0,
            "input_tokens": 0,
            "output_tokens": 0
        }
        cur_epoch += step_seconds

    # Populate buckets from relevant logs
    for l in relevant:
        try:
            ts = datetime.fromisoformat(l.get("timestamp").replace("Z", "+00:00"))
            epoch = int(ts.timestamp())
            local_epoch = epoch + tz_shift
            b_local_epoch = local_epoch - (local_epoch % step_seconds)
            b_epoch = b_local_epoch - tz_shift

            if b_epoch in buckets:
                lt = (l.get("type") or "").strip()
                if ("chat_request" in lt or lt == "user_query") and lt != "received_chat_request":
                    buckets[b_epoch]["chat_requests"] += 1
                if "llm_invocation" in lt or lt == "llm_request":
                    buckets[b_epoch]["llm_requests"] += 1
                    buckets[b_epoch]["prompts"] += 1
                if lt == "llm_response" or ("llm_response" in lt and lt != "received_llm_response"):
                    buckets[b_epoch]["llm_responses"] += 1
                    buckets[b_epoch]["responses"] += 1
                if l.get("is_error") or l.get("status") in ["error", "failure"]:
                    buckets[b_epoch]["errors"] += 1

                buckets[b_epoch]["input_tokens"] += (l.get("input_tokens") or 0)
                buckets[b_epoch]["output_tokens"] += (l.get("output_tokens") or 0)
        except Exception:
            continue

    timeline = [buckets[k] for k in sorted(buckets.keys())]

    charts = {
        "labels": [b["time"] for b in timeline],
        "epochs": [b["epoch"] for b in timeline],
        "chat_requests": [b["chat_requests"] for b in timeline],
        "llm_requests": [b["llm_requests"] for b in timeline],
        "llm_responses": [b["llm_responses"] for b in timeline],
        "errors": [b["errors"] for b in timeline],
        "prompts": [b["llm_requests"] for b in timeline],
        "responses": [b["llm_responses"] for b in timeline],
        "input_tokens": [b["input_tokens"] for b in timeline],
        "output_tokens": [b["output_tokens"] for b in timeline]
    }

    summary = {
        "total_chat": total_chat,
        "total_chats": total_chat,
        "total_prompts": total_llm_requests,
        "total_llm_requests": total_llm_requests,
        "total_responses": total_llm_responses,
        "total_llm_responses": total_llm_responses,
        "total_errors": total_errors,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens
    }

    # Metrics: TTFT, ITL, TPS, TPOT
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0
    tps = round(total_output_tokens / (sum(latencies) / 1000), 2) if (latencies and sum(latencies) > 0) else 0
    tpot = round((sum(latencies) / total_output_tokens), 2) if total_output_tokens > 0 else 0
    ttft = round(avg_latency * 0.35, 1)  # Estimated TTFT based on avg latency
    itl = round(tpot * 0.8, 1)

    performance = {
        "avg_latency_ms": round(avg_latency, 1),
        "ttft_ms": ttft,
        "itl_ms": itl,
        "tps": tps,
        "tpot_ms": tpot
    }

    return jsonify({
        "used_models": sorted(list(models_used)),
        "models_used": sorted(list(models_used)),
        "summary": summary,
        "total_chat": total_chat,
        "total_chats": total_chat,
        "total_prompts": total_llm_requests,
        "total_llm_requests": total_llm_requests,
        "total_responses": total_llm_responses,
        "total_llm_responses": total_llm_responses,
        "total_errors": total_errors,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "performance": performance,
        "metrics": performance,
        "charts": charts,
        "timeline": timeline
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8006))
    app.run(host="0.0.0.0", port=port)
