"""Telemetry service for system throughput, token velocity, and latency metrics."""
import json
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import config

_LOCK = threading.Lock()
TELEMETRY_FILE = config.DATABASE_DIR / "telemetry.json"

class TelemetryService:
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or TELEMETRY_FILE
        self._ensure_file()

    def _ensure_file(self):
        if not self.data_file.exists():
            with _LOCK:
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump([], f)

    def _read_records(self) -> List[Dict[str, Any]]:
        if not self.data_file.exists():
            return []
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_records(self, records: List[Dict[str, Any]]):
        temp = self.data_file.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        temp.replace(self.data_file)

    def record_invocation(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        elapsed_ms: float,
        is_error: bool = False,
        ttft_ms: Optional[float] = None,
    ):
        """Record a single LLM invocation event."""
        now = datetime.now()
        
        # Estimate TTFT and ITL if not streamed
        # In non-streaming requests, TTFT is typically ~30-40% of latency
        est_ttft = ttft_ms if ttft_ms is not None else (elapsed_ms * 0.35 if not is_error and output_tokens > 0 else 0)
        generation_time_ms = max(0, elapsed_ms - est_ttft)
        itl_ms = (generation_time_ms / output_tokens) if output_tokens > 1 else generation_time_ms

        entry = {
            "timestamp": now.isoformat(),
            "epoch": now.timestamp(),
            "model": model,
            "input_tokens": max(0, input_tokens),
            "output_tokens": max(0, output_tokens),
            "elapsed_ms": round(elapsed_ms, 2),
            "is_error": is_error,
            "ttft_ms": round(est_ttft, 2),
            "itl_ms": round(itl_ms, 2),
        }

        with _LOCK:
            records = self._read_records()
            records.append(entry)
            self._write_records(records)

    def get_used_models(self) -> List[str]:
        """List distinct models that have recorded invocations."""
        with _LOCK:
            records = self._read_records()
        models = set(r.get("model", "") for r in records if r.get("model"))
        return sorted(list(models))

    def get_metrics(
        self,
        model_filter: str = "All Models",
        interval: str = "15 min",
        time_range: str = "1 day",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate telemetry metrics and timeseries buckets for Chart.js."""
        with _LOCK:
            all_records = self._read_records()

        now = datetime.now()
        
        # Calculate time cutoff
        if time_range == "Last hr":
            start_cutoff = now - timedelta(hours=1)
            end_cutoff = now
        elif time_range == "1 day":
            start_cutoff = now - timedelta(days=1)
            end_cutoff = now
        elif time_range == "Week":
            start_cutoff = now - timedelta(days=7)
            end_cutoff = now
        elif time_range == "Month":
            start_cutoff = now - timedelta(days=30)
            end_cutoff = now
        elif time_range == "Custom" and start_date and end_date:
            try:
                start_cutoff = datetime.fromisoformat(start_date)
                end_cutoff = datetime.fromisoformat(end_date) + timedelta(days=1)
            except Exception:
                start_cutoff = now - timedelta(days=1)
                end_cutoff = now
        else:
            start_cutoff = now - timedelta(days=1)
            end_cutoff = now

        # Filter records
        filtered = []
        for r in all_records:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except Exception:
                continue

            if not (start_cutoff <= ts <= end_cutoff):
                continue

            if model_filter != "All Models" and r.get("model") != model_filter:
                continue

            filtered.append(r)

        # Summary statistics
        total_prompts = len(filtered)
        total_responses = sum(1 for r in filtered if not r.get("is_error"))
        total_errors = sum(1 for r in filtered if r.get("is_error"))
        total_input_tokens = sum(r.get("input_tokens", 0) for r in filtered)
        total_output_tokens = sum(r.get("output_tokens", 0) for r in filtered)

        # Performance metrics
        valid_responses = [r for r in filtered if not r.get("is_error") and r.get("output_tokens", 0) > 0]
        
        if valid_responses:
            avg_ttft = round(sum(r.get("ttft_ms", 0) for r in valid_responses) / len(valid_responses), 1)
            avg_itl = round(sum(r.get("itl_ms", 0) for r in valid_responses) / len(valid_responses), 1)
            
            total_sec = sum(r.get("elapsed_ms", 1) / 1000.0 for r in valid_responses)
            tps = round(total_output_tokens / total_sec, 2) if total_sec > 0 else 0.0
            tpot = round(sum(r.get("elapsed_ms", 0) / r.get("output_tokens", 1) for r in valid_responses) / len(valid_responses), 2)
        else:
            avg_ttft = 0.0
            avg_itl = 0.0
            tps = 0.0
            tpot = 0.0

        # Bucket aggregation for Charts
        interval_minutes = 15
        if interval == "1 min":
            interval_minutes = 1
        elif interval == "15 min":
            interval_minutes = 15
        elif interval == "1 hr":
            interval_minutes = 60
        elif interval == "1 day":
            interval_minutes = 1440

        interval_delta = timedelta(minutes=interval_minutes)
        buckets: Dict[str, Dict[str, Any]] = {}

        # Pre-seed buckets across the range
        curr = start_cutoff
        while curr <= end_cutoff:
            b_key = curr.strftime("%H:%M" if interval_minutes < 1440 else "%b %d")
            buckets[b_key] = {
                "label": b_key,
                "prompts": 0,
                "responses": 0,
                "errors": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
            curr += interval_delta
            if len(buckets) > 60:  # Cap max bucket visual count for crisp charts
                break

        for r in filtered:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
                b_key = ts.strftime("%H:%M" if interval_minutes < 1440 else "%b %d")
                if b_key not in buckets:
                    buckets[b_key] = {
                        "label": b_key,
                        "prompts": 0,
                        "responses": 0,
                        "errors": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }
                b = buckets[b_key]
                b["prompts"] += 1
                if r.get("is_error"):
                    b["errors"] += 1
                else:
                    b["responses"] += 1
                b["input_tokens"] += r.get("input_tokens", 0)
                b["output_tokens"] += r.get("output_tokens", 0)
            except Exception:
                continue

        labels = list(buckets.keys())
        prompts_series = [buckets[k]["prompts"] for k in labels]
        responses_series = [buckets[k]["responses"] for k in labels]
        errors_series = [buckets[k]["errors"] for k in labels]
        in_tokens_series = [buckets[k]["input_tokens"] for k in labels]
        out_tokens_series = [buckets[k]["output_tokens"] for k in labels]

        return {
            "summary": {
                "total_prompts": total_prompts,
                "total_responses": total_responses,
                "total_errors": total_errors,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
            },
            "performance": {
                "ttft_ms": avg_ttft,
                "itl_ms": avg_itl,
                "tps": tps,
                "tpot_ms": tpot,
            },
            "charts": {
                "labels": labels,
                "prompts": prompts_series,
                "responses": responses_series,
                "errors": errors_series,
                "input_tokens": in_tokens_series,
                "output_tokens": out_tokens_series,
            },
            "used_models": self.get_used_models(),
        }

# Singleton instance
_TELEMETRY_SERVICE: Optional[TelemetryService] = None

def get_telemetry_service() -> TelemetryService:
    global _TELEMETRY_SERVICE
    if _TELEMETRY_SERVICE is None:
        _TELEMETRY_SERVICE = TelemetryService()
    return _TELEMETRY_SERVICE
