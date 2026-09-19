"""Audit log and event service persisting to database/log.json."""
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import config

_LOCK = threading.Lock()

def redact_sensitive(obj: Any) -> Any:
    """Recursively redact API keys and sensitive tokens."""
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if any(term in k.lower() for term in ["api_key", "apikey", "secret", "token", "password"]):
                clean[k] = "****"
            else:
                clean[k] = redact_sensitive(v)
        return clean
    elif isinstance(obj, list):
        return [redact_sensitive(item) for item in obj]
    elif isinstance(obj, str):
        # Redact known API key patterns if present in strings
        if config.GEMINI_API_KEY and len(config.GEMINI_API_KEY) > 8 and config.GEMINI_API_KEY in obj:
            return obj.replace(config.GEMINI_API_KEY, "****")
        # Match AI Studio / Gemini API key style patterns (e.g. AIzaSy... or AQ....)
        redacted = re.sub(r'(AIzaSy[A-Za-z0-9_-]{20,})', '****', obj)
        redacted = re.sub(r'(AQ\.[A-Za-z0-9_-]{20,})', '****', redacted)
        return redacted
    return obj

class LogService:
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or config.LOG_FILE_PATH
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not self.log_file.exists():
            with _LOCK:
                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)

    def _read_logs_unlocked(self) -> List[Dict[str, Any]]:
        if not self.log_file.exists():
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_logs_unlocked(self, logs: List[Dict[str, Any]]):
        temp_file = self.log_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, default=str)
        temp_file.replace(self.log_file)

    def log_event(
        self,
        conversation_id: str,
        event_type: str,
        invoker: str,
        target: str,
        short_description: str,
        payload: Any,
        elapsed_ms: Optional[float] = None,
        is_error: bool = False,
    ) -> Dict[str, Any]:
        """Record an audit event entry.
        
        Args:
            conversation_id: Unique identifier for conversation
            event_type: One of 'agent', 'skill search', 'document search', 'tool', 'ollama vector', 'LLM'
            invoker: Name of the initiating component (e.g. 'User', 'Custom Agent', 'Google ADK Agent', 'Agent Orchestrator')
            target: Target component (e.g. 'Agent', 'Skills Store', 'Documents Store', 'tool.name', 'Ollama', 'Model Name')
            short_description: Concise human-readable summary
            payload: Full structured data (unredacted except for API keys replaced with ****)
            elapsed_ms: Latency in milliseconds
            is_error: Whether this event represents a failure
        """
        now = datetime.now()
        event_entry = {
            "id": f"evt_{int(now.timestamp() * 1000)}_{os.urandom(2).hex()}",
            "timestamp": now.isoformat(),
            "local_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "conversation_id": conversation_id,
            "event_type": event_type,
            "invoker": invoker,
            "target": target,
            "short_description": short_description,
            "payload": redact_sensitive(payload),
            "elapsed_ms": round(elapsed_ms, 2) if elapsed_ms is not None else None,
            "is_error": is_error,
        }

        with _LOCK:
            logs = self._read_logs_unlocked()
            logs.append(event_entry)
            self._write_logs_unlocked(logs)

        return event_entry

    def get_all_logs(self) -> List[Dict[str, Any]]:
        with _LOCK:
            return self._read_logs_unlocked()

    def get_conversation_events(self, conversation_id: str) -> List[Dict[str, Any]]:
        logs = self.get_all_logs()
        return [evt for evt in logs if evt.get("conversation_id") == conversation_id]

    def get_conversation_summaries(self) -> List[Dict[str, Any]]:
        """Group logs into conversation summaries for the Top Table."""
        logs = self.get_all_logs()
        conversations: Dict[str, Dict[str, Any]] = {}

        for evt in logs:
            cid = evt.get("conversation_id")
            if not cid:
                continue

            if cid not in conversations:
                conversations[cid] = {
                    "conversation_id": cid,
                    "timestamp": evt.get("local_time", ""),
                    "raw_time": evt.get("timestamp", ""),
                    "user_query": "(No user query logged)",
                    "agent_response": "(Pending or In-progress)",
                    "agent_type": "Custom Agent",
                    "event_count": 0,
                    "has_error": False,
                }

            c = conversations[cid]
            c["event_count"] += 1
            if evt.get("is_error"):
                c["has_error"] = True

            evt_type = evt.get("event_type", "").lower()
            invoker = evt.get("invoker", "")
            target = evt.get("target", "")

            # Identify user query
            if (evt_type == "agent" and invoker == "User") or ("query" in evt.get("short_description", "").lower() and invoker == "User"):
                payload = evt.get("payload")
                if isinstance(payload, dict):
                    c["user_query"] = payload.get("message") or payload.get("query") or str(payload)
                elif isinstance(payload, str):
                    c["user_query"] = payload

            # Identify agent response and type
            if evt_type == "agent" and target == "User":
                payload = evt.get("payload")
                c["agent_type"] = invoker or c["agent_type"]
                if isinstance(payload, dict):
                    c["agent_response"] = payload.get("response") or payload.get("text") or str(payload)
                elif isinstance(payload, str):
                    c["agent_response"] = payload

        # Sort conversations descending by timestamp
        sorted_convs = sorted(
            conversations.values(),
            key=lambda x: x.get("raw_time", ""),
            reverse=True
        )
        return sorted_convs

    def get_statistics(self) -> Dict[str, Any]:
        """Aggregate statistics: total prompts, model calls, ollama embeds, avg latency."""
        logs = self.get_all_logs()
        total_user_prompts = 0
        total_model_calls = 0
        total_ollama_embeds = 0
        latencies: List[float] = []

        for evt in logs:
            etype = evt.get("event_type", "").lower()
            invoker = evt.get("invoker", "")
            target = evt.get("target", "")

            if etype == "agent" and invoker == "User":
                total_user_prompts += 1
            elif etype == "llm" and "response" in evt.get("short_description", "").lower():
                total_model_calls += 1
            elif etype == "ollama vector":
                total_ollama_embeds += 1

            if evt.get("elapsed_ms") is not None:
                latencies.append(evt["elapsed_ms"])

        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

        return {
            "total_user_prompts": total_user_prompts,
            "total_model_calls": total_model_calls,
            "total_ollama_embeds": total_ollama_embeds,
            "avg_latency_ms": avg_latency,
            "total_events": len(logs),
        }

    def clear_logs(self):
        """Delete all logs from database/log.json."""
        with _LOCK:
            self._write_logs_unlocked([])

# Singleton instance
_LOG_SERVICE: Optional[LogService] = None

def get_log_service() -> LogService:
    global _LOG_SERVICE
    if _LOG_SERVICE is None:
        _LOG_SERVICE = LogService()
    return _LOG_SERVICE
