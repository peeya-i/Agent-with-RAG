import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from agent_router.embeddings import EmbeddingEngine
from agent_router.registry import AgentRegistry, AgentInfo
from agent_router.router import VectorRouter, SIMILARITY_THRESHOLD
import agent_router.server as router_srv
import agent_tech_support.server as tech_srv

def test_embedding_engine():
    engine = EmbeddingEngine()
    vec1 = engine.embed_text("Docker container crashed with code 137 OOMKilled on startup")
    vec2 = engine.embed_text("The Docker process died with exit code 137 out of memory error")
    vec3 = engine.embed_text("What is the recipe for chocolate chip cookies?")

    assert vec1 is not None and len(vec1) > 0
    assert vec2 is not None and len(vec2) > 0
    assert vec3 is not None and len(vec3) > 0

    # Semantic similarity between related tech support prompts should be high
    sim_tech = engine.compute_similarity(vec1, vec2)
    sim_unrelated = engine.compute_similarity(vec1, vec3)

    assert sim_tech > sim_unrelated
    assert sim_tech > 0.20

def test_agent_registry():
    registry = AgentRegistry()

    default_agent = AgentInfo(
        id="default-agent",
        name="Default Agent",
        description="Handles general questions",
        url="http://agents:8002",
        status="up",
        is_default=True
    )
    registry.register(default_agent)

    specialist = AgentInfo(
        id="specialist-agent",
        name="Specialist Agent",
        description="Handles technical issues",
        url="http://agent_tech_support:8007",
        sample_prompts=["HTTP 500 error", "Docker crashed"],
        status="up",
        is_default=False
    )
    registry.register(specialist)

    assert len(registry.list_all_agents()) == 2
    assert registry.get_default_agent().id == "default-agent"
    assert registry.get_agent("specialist-agent").is_available is True

    # Test turn down
    registry.turn_down("specialist-agent")
    assert registry.get_agent("specialist-agent").is_available is False
    assert len(registry.list_available_agents()) == 1

    # Test turn up
    registry.turn_up("specialist-agent")
    assert registry.get_agent("specialist-agent").is_available is True

    # Default agent cannot be deleted
    with pytest.raises(ValueError):
        registry.unregister("default-agent")

    # Specialist can be unregistered
    assert registry.unregister("specialist-agent") is True
    assert len(registry.list_all_agents()) == 1

def test_vector_router_threshold_and_fallback():
    registry = AgentRegistry()

    default_agent = AgentInfo(
        id="agents-default",
        name="Default Multi-Tool & RAG Agent",
        description="General assistant and fallback",
        url="http://agents:8002",
        status="up",
        is_default=True
    )
    registry.register(default_agent)

    tech_agent = AgentInfo(
        id="agent-tech-support",
        name="Technical Support Specialist",
        description="Diagnoses technical software issues, API errors, HTTP 500 status codes, database connection timeouts, Docker container crashes",
        url="http://agent_tech_support:8007",
        sample_prompts=[
            "Our microservice is throwing HTTP 504 Gateway Timeout on PostgreSQL queries.",
            "The Docker container crashed with code 137 OOMKilled on startup.",
            "Why is my webhook receiving TLS handshake failed errors from the server?",
            "How do I debug connection pool exhaustion in high-throughput endpoints?"
        ],
        status="up",
        is_default=False
    )
    registry.register(tech_agent)

    router = VectorRouter(registry=registry, threshold=0.50)

    # 1. High match query for tech support specialist (> 50% threshold)
    tech_query = "The Docker container crashed with code 137 OOMKilled on startup"
    target, score, ranked, is_fallback, explanation, _ = router.decide_route(tech_query)

    assert target is not None
    assert target.id == "agent-tech-support"
    assert score > 0.50
    assert is_fallback is False

    # 2. General / unrelated query that does NOT exceed 50% threshold -> falls back to default agent
    general_query = "What is the capital of Australia and the population of Sydney?"
    target, score, ranked, is_fallback, explanation, _ = router.decide_route(general_query)

    assert target is not None
    assert target.id == "agents-default"
    assert is_fallback is True
    assert "Defaulting to primary agents container" in explanation

    # 3. Tech query when specialized agent is turned DOWN -> falls back to default agent
    registry.turn_down("agent-tech-support")
    target, score, ranked, is_fallback, explanation, _ = router.decide_route(tech_query)

    assert target is not None
    assert target.id == "agents-default"
    assert is_fallback is True
    assert "DOWN" in explanation

def test_router_server_endpoints():
    client = router_srv.app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["service"] == "agents-router"
    assert data["port"] == 8004
    assert data["threshold"] == 0.50

    # List agents
    res = client.get("/api/router/agents")
    assert res.status_code == 200
    agents = res.get_json()["agents"]
    assert len(agents) >= 2
    agent_ids = [a["id"] for a in agents]
    assert "agents-default" in agent_ids
    assert "agent-tech-support" in agent_ids

    # Dynamic registration
    reg_res = client.post("/api/router/agents/register", json={
        "id": "agent-unit-test",
        "name": "Unit Test Agent",
        "url": "http://localhost:9999",
        "description": "Performs automated unit test verifications",
        "sample_prompts": ["Run pytest on microservices", "Execute test suite"],
        "status": "up"
    })
    assert reg_res.status_code == 201

    # Toggle status
    status_res = client.post("/api/router/agents/agent-unit-test/status", json={"status": "down"})
    assert status_res.status_code == 200
    assert status_res.get_json()["new_status"] == "down"

    # Test route endpoint
    test_res = client.post("/api/router/test_route", json={
        "message": "The Docker container crashed with code 137 OOMKilled on startup"
    })
    assert test_res.status_code == 200
    route_data = test_res.get_json()
    assert route_data["selected_agent"]["id"] == "agent-tech-support"
    assert route_data["similarity_score"] > 0.50
    assert route_data["is_default_fallback"] is False

    # Test threshold getting and setting
    th_get = client.get("/api/router/threshold")
    assert th_get.status_code == 200
    assert "threshold" in th_get.get_json()

    th_set = client.post("/api/router/threshold", json={"threshold": 0.65})
    assert th_set.status_code == 200
    assert th_set.get_json()["threshold"] == 0.65

    # Reset threshold back to 0.50
    client.post("/api/router/threshold", json={"threshold": 0.50})

    # Cleanup unit test agent
    del_res = client.delete("/api/router/agents/agent-unit-test")
    assert del_res.status_code == 200

def test_tech_support_agent_service():
    client = tech_srv.app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["port"] == 8007

    # Chat execution with multi-turn conversation context
    chat_res = client.post("/api/agent/chat", json={
        "message": "Docker container exited with code 137 OOMKilled",
        "conversation_id": "conv_test_tech_1",
        "history": [
            {"role": "user", "content": "Hello, my microservice is crashing"},
            {"role": "assistant", "content": "I can help troubleshoot microservice crashes."}
        ]
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.get_json()
    assert "response" in chat_data
    assert "Technical Support" in chat_data.get("agent_type", "")
    assert len(chat_data["response"]) > 0
