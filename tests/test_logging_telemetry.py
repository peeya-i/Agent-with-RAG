"""Unit tests for audit logging, API key redaction, and telemetry calculation."""
import os
import pytest
from services.log_service import get_log_service, redact_sensitive
from services.telemetry_service import get_telemetry_service

def test_api_key_redaction():
    fake_key = "AIzaSyD98374829374892374982374982374"
    payload = {
        "api_key": fake_key,
        "nested": {"token": "secret_12345", "query": f"Using key {fake_key}"},
        "safe_field": "hello world",
    }
    redacted = redact_sensitive(payload)
    assert redacted["api_key"] == "****"
    assert redacted["nested"]["token"] == "****"
    assert fake_key not in redacted["nested"]["query"]
    assert "****" in redacted["nested"]["query"]
    assert redacted["safe_field"] == "hello world"

def test_event_logging():
    logger = get_log_service()
    cid = "test_conv_123"
    evt = logger.log_event(
        conversation_id=cid,
        event_type="tool",
        invoker="TestRunner",
        target="MockTool",
        short_description="Running unit test tool",
        payload={"param": 1},
        elapsed_ms=12.5,
    )
    assert evt["conversation_id"] == cid
    assert evt["event_type"] == "tool"
    assert evt["elapsed_ms"] == 12.5

    # Retrieve events
    events = logger.get_conversation_events(cid)
    assert any(e["id"] == evt["id"] for e in events)

def test_telemetry_metrics_calculation():
    tel = get_telemetry_service()
    tel.record_invocation(
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        elapsed_ms=500.0,
        is_error=False,
    )
    metrics = tel.get_metrics(model_filter="All Models", time_range="Last hr")
    assert "summary" in metrics
    assert "performance" in metrics
    assert metrics["summary"]["total_prompts"] >= 1
    assert metrics["performance"]["tps"] >= 0
