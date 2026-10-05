import sys
import os
import json
import time
import pytest

import importlib.util

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def load_service(name, rel_path):
    path = os.path.join(BASE_DIR, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# 1. Test Logging Service
def test_logging_service():
    logging_srv = load_service("test_logging_module", "logging/server.py")
    client = logging_srv.app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["port"] == 8006

    # Ingest log
    ingest_res = client.post("/api/logs", json={
        "type": "test_event",
        "invoker": "unit_test",
        "recipient": "logging",
        "conversation_id": "test_conv_123",
        "payload": {"data": "test_payload", "api_key": "secret_key_123"},
        "short_description": "Unit test log"
    })
    assert ingest_res.status_code == 201

    # Query logs
    q_res = client.post("/api/logs/query", json={"conversation_id": "test_conv_123"})
    assert q_res.status_code == 200
    logs = q_res.get_json().get("logs", [])
    assert len(logs) >= 1
    # Verify API key was redacted
    assert logs[0]["payload"]["api_key"] == "****"

    # Stats
    stats_res = client.get("/api/logs/stats")
    assert stats_res.status_code == 200
    assert stats_res.get_json()["total_logs"] >= 1

# 2. Test Auth Service
def test_auth_service():
    import auth_service.server as auth_srv
    client = auth_srv.app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["port"] == 8001

    # Login with seed admin credentials -> yields JWT with role Admin and domain None
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200
    data = login_res.get_json()
    assert data["status"] == "success"
    assert data["user"]["role"] == "Admin"
    assert "jwt_token" in data
    assert data["user"]["domain"] is None

    # Login with example-a.com user
    res_a = client.post("/api/auth/login", json={"username": "user@example-a.com", "password": "password123"})
    assert res_a.status_code == 200
    data_a = res_a.get_json()
    assert data_a["user"]["domain"] == "example-a.com"
    token_a = data_a["jwt_token"]

    # Login with sample-b.com user
    res_b = client.post("/api/auth/login", json={"username": "user@sample-b.com", "password": "password123"})
    assert res_b.status_code == 200
    data_b = res_b.get_json()
    assert data_b["user"]["domain"] == "sample-b.com"
    token_b = data_b["jwt_token"]

    # Validate tokens via validate_token endpoint
    val_a = client.post("/api/auth/validate_token", json={"token": token_a})
    assert val_a.status_code == 200
    assert val_a.get_json()["claims"]["domain"] == "example-a.com"

    val_b = client.post("/api/auth/validate_token", json={"token": token_b})
    assert val_b.status_code == 200
    assert val_b.get_json()["claims"]["domain"] == "sample-b.com"

    # Bad login
    bad_res = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert bad_res.status_code == 401
    assert "Invalid username or password" in bad_res.get_json()["error"]

    # Register new user (initially Locked per specification)
    uname = f"testuser_{int(time.time() * 1000)}@example-a.com"
    reg_res = client.post("/api/auth/register", json={"username": uname, "password": "password123"})
    assert reg_res.status_code == 201

    # Attempt login with locked account -> must fail with 403 and Locked error
    locked_login = client.post("/api/auth/login", json={"username": uname, "password": "password123"})
    assert locked_login.status_code == 403
    assert "Account is Locked" in locked_login.get_json()["error"]

    # List users to find user id
    users_res = client.get("/api/users")
    assert users_res.status_code == 200
    users = users_res.get_json()["users"]
    new_user = next((u for u in users if u["email"] == uname), None)
    assert new_user is not None
    assert new_user["status"] == "Locked"

    # Unlock user via status endpoint
    unlock_res = client.put(f"/api/users/{new_user['id']}/status", json={"status": "Active"})
    assert unlock_res.status_code == 200

    # Successful login after unlocking
    unlocked_login = client.post("/api/auth/login", json={"username": uname, "password": "password123"})
    assert unlocked_login.status_code == 200
    assert unlocked_login.get_json()["status"] == "success"

    # Verify JWT token generated upon login
    login_data = unlocked_login.get_json()
    assert "jwt_token" in login_data
    jwt_tok = login_data["jwt_token"]
    from jwt_auth import decode_jwt_token
    payload = decode_jwt_token(jwt_tok)
    assert payload is not None
    assert payload.get("email") == uname

    # Test Admin Create User validation (empty fails)
    fail_create = client.post("/api/users", json={"username": "", "password": ""})
    assert fail_create.status_code == 400

    # Test Admin Create User success
    admin_uname = f"created_user_{int(time.time() * 1000)}"
    create_res = client.post("/api/users", json={
        "username": admin_uname,
        "password": "pass123_secure",
        "role": "User",
        "status": "Active"
    })
    assert create_res.status_code == 201
    created_id = create_res.get_json()["user_id"]

    # Test Bulk Delete Users
    bulk_del = client.post("/api/users/bulk_delete", json={"user_ids": [created_id]})
    assert bulk_del.status_code == 200
    assert bulk_del.get_json()["deleted_count"] == 1

# 3. Test Tools Service
def test_tools_service():
    import tools.server as tools_srv
    client = tools_srv.app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["port"] == 8005

    # List tools
    tools_list = client.get("/api/tools/list").get_json()["tools"]
    assert len(tools_list) >= 3

    # Employee search tool (single keyword backward compatibility)
    emp_res = client.post("/api/tools/call", json={
        "tool": "person_search.query_person_registry",
        "arguments": {"keyword": "Dubois", "field": "name"},
        "conversation_id": "test_conv"
    })
    assert emp_res.status_code == 200
    emp_data = emp_res.get_json()["result"]
    assert emp_data["count"] >= 1
    assert "Lucas Dubois" in [r["name"] for r in emp_data["results"]]

    # Employee search tool (list of search texts)
    emp_multi_res = client.post("/api/tools/call", json={
        "tool": "person_search.query_person_registry",
        "arguments": {"keywords": ["Dubois", "Berlin"], "field": "all"},
        "conversation_id": "test_conv"
    })
    assert emp_multi_res.status_code == 200
    emp_multi_data = emp_multi_res.get_json()["result"]
    assert emp_multi_data["count"] >= 2
    matched_names = [r["name"] for r in emp_multi_data["results"]]
    assert "Lucas Dubois" in matched_names
    assert "Elena Rostova" in matched_names

    # Customer search tool
    cust_res = client.post("/api/tools/call", json={
        "tool": "customer_search.query_customer_registry",
        "arguments": {"keywords": ["Canada", "Germany"], "field": "all"},
        "conversation_id": "test_conv"
    })
    assert cust_res.status_code == 200
    cust_data = cust_res.get_json()["result"]
    assert cust_data["status"] == "success"
    assert cust_data["total_matches"] >= 1

    # Test Multi-tenant CSV access via JWT tokens
    from jwt_auth import generate_jwt_token
    token_example_a = generate_jwt_token(email="user@example-a.com", role="User", domain="example-a.com")
    token_sample_b = generate_jwt_token(email="user@sample-b.com", role="User", domain="sample-b.com")
    token_admin = generate_jwt_token(email="admin", role="Admin", domain=None)

    # 1. example-a.com access: employee_database.csv OK, customer_database.csv Forbidden (403)
    resp_emp_a = client.get("/api/tools/data/employee_database.csv", headers={"Authorization": f"Bearer {token_example_a}"})
    assert resp_emp_a.status_code == 200

    resp_cust_a = client.get("/api/tools/data/customer_database.csv", headers={"Authorization": f"Bearer {token_example_a}"})
    assert resp_cust_a.status_code == 403

    # 2. sample-b.com access: customer_database.csv OK, employee_database.csv Forbidden (403)
    resp_cust_b = client.get("/api/tools/data/customer_database.csv", headers={"Authorization": f"Bearer {token_sample_b}"})
    assert resp_cust_b.status_code == 200

    resp_emp_b = client.get("/api/tools/data/employee_database.csv", headers={"Authorization": f"Bearer {token_sample_b}"})
    assert resp_emp_b.status_code == 403

    # 3. Admin access: Both OK
    resp_emp_admin = client.get("/api/tools/data/employee_database.csv", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_emp_admin.status_code == 200

    resp_cust_admin = client.get("/api/tools/data/customer_database.csv", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_cust_admin.status_code == 200

# 4. Test Doc RAG Service
def test_doc_rag_service():
    pytest.importorskip("chromadb")
    os.environ["CHROMA_DIR"] = "/tmp/test_chroma_pytest"
    doc_rag_srv = load_service("test_doc_rag_module", "doc_RAG/server.py")
    client = doc_rag_srv.app.test_client()

    from jwt_auth import generate_jwt_token
    token_a = generate_jwt_token(email="user@example-a.com", role="User", domain="example-a.com")
    token_b = generate_jwt_token(email="user@sample-b.com", role="User", domain="sample-b.com")
    token_admin = generate_jwt_token(email="admin", role="Admin", domain=None)

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["port"] == 8003

    # 1. Add Documents with domain tags
    add_a = client.post("/api/rag/add", json={
        "type": "document",
        "name": "example_a_roadmap",
        "text": "Secret product roadmap for example-a.com tenant.",
        "domain": "example-a.com"
    }, headers={"Authorization": f"Bearer {token_a}"})
    assert add_a.status_code == 200

    add_b = client.post("/api/rag/add", json={
        "type": "document",
        "name": "sample_b_financials",
        "text": "Confidential financial statements for sample-b.com tenant.",
        "domain": "sample-b.com"
    }, headers={"Authorization": f"Bearer {token_b}"})
    assert add_b.status_code == 200

    # 2. List Documents filtered by tenant domain
    list_a = client.get("/api/rag/list", headers={"Authorization": f"Bearer {token_a}"}).get_json()
    doc_names_a = [d["doc_name"] for d in list_a.get("documents", [])]
    assert "example_a_roadmap" in doc_names_a
    assert "sample_b_financials" not in doc_names_a

    list_b = client.get("/api/rag/list", headers={"Authorization": f"Bearer {token_b}"}).get_json()
    doc_names_b = [d["doc_name"] for d in list_b.get("documents", [])]
    assert "sample_b_financials" in doc_names_b
    assert "example_a_roadmap" not in doc_names_b

    list_admin = client.get("/api/rag/list", headers={"Authorization": f"Bearer {token_admin}"}).get_json()
    doc_names_admin = [d["doc_name"] for d in list_admin.get("documents", [])]
    assert "example_a_roadmap" in doc_names_admin
    assert "sample_b_financials" in doc_names_admin

    # 3. Add New Skill
    add_skill_res = client.post("/api/rag/add", json={
        "user_id": "test_admin",
        "type": "skill",
        "name": "spec_test_skill",
        "text": "A skill to analyze system logs and telemetry.",
        "vector_text": "analyze system logs and telemetry"
    })
    assert add_skill_res.status_code == 200
    assert add_skill_res.get_json()["status"] == "success"

    # 4. Query Documents with tenant filtering
    q_a = client.post("/api/rag/query", json={
        "type": "document",
        "query": "roadmap financials",
        "threshold": 0.0
    }, headers={"Authorization": f"Bearer {token_a}"})
    assert q_a.status_code == 200
    res_a_names = [item.get("document_name") for item in q_a.get_json().get("results", [])]
    assert "sample_b_financials" not in res_a_names

    # 5. Delete Document
    del_res = client.post("/api/rag/delete", json={
        "user_id": "test_admin",
        "type": "document",
        "name": "example_a_roadmap"
    }, headers={"Authorization": f"Bearer {token_admin}"})
    assert del_res.status_code == 200


# 5. Test Agents Service
def test_agents_service():
    agents_srv = load_service("test_agents_module", "agents/server.py")
    client = agents_srv.app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["port"] == 8002

    # Models list
    models_res = client.get("/api/agents/models")
    assert models_res.status_code == 200
    assert len(models_res.get_json().get("models", [])) >= 1

    # Skills list
    skills_res = client.get("/api/agents/skills")
    assert skills_res.status_code == 200

# 6. Test Web UI
def test_web_ui_routes():
    web_app = load_service("test_web_ui_module", "web_ui/app.py")
    client = web_app.app.test_client()

    # Index page
    res = client.get("/")
    assert res.status_code == 200
    assert b"Agent With RAG" in res.data
    assert b"page-chat" in res.data
    assert b"page-containers" in res.data
    assert b"page-auth" in res.data
    assert b"loginModal" in res.data
    assert b"btnRefreshSessionJwt" in res.data
    assert b"btnRefreshJwtActivities" in res.data

# 7. Test Person Information Skill & Employee Search Modularity
def test_person_information_skill_modular():
    person_search_mod = load_service(
        "test_person_search_module",
        "agents/skills/person-information-skill/scripts/person_search.py"
    )
    query_person_registry = person_search_mod.query_person_registry
    normalize_search_terms = person_search_mod.normalize_search_terms
    filter_person_records = person_search_mod.filter_person_records

    from tools.scripts.employee_search import search_employees, normalize_search_terms as norm_emp, filter_records

    # Test normalization
    assert normalize_search_terms([" Lucas ", "  PARIS "]) == ["lucas", "paris"]
    assert normalize_search_terms(" Dubois ") == ["dubois"]
    assert normalize_search_terms([]) == []

    # Test skill query with list of search texts
    res = query_person_registry(keywords=["Lucas Dubois", "Berlin"])
    assert res["status"] == "success"
    assert res["total_matches"] == 2
    names = [r["name"] for r in res["results"]]
    assert "Lucas Dubois" in names
    assert "Elena Rostova" in names

    # Test deduplication when multiple terms match the same entry
    res_dedup = query_person_registry(keywords=["Lucas Dubois", "Paris", "France", "Chief AI Architect"])
    assert res_dedup["status"] == "success"
    lucas_matches = [r for r in res_dedup["results"] if r["name"] == "Lucas Dubois"]
    assert len(lucas_matches) == 1, "Lucas Dubois should only appear once despite matching all 4 terms"

    # Test modular search_employees from tools
    emp_matches = search_employees(keywords=["Paris", "Tokyo"])
    assert len(emp_matches) >= 2
    emp_names = [e["name"] for e in emp_matches]
    assert "Lucas Dubois" in emp_names
    assert "Kenji Takahashi" in emp_names

# 8. Test Customer Information Skill & Customer Search Modularity
def test_customer_information_skill_modular():
    cust_search_mod = load_service(
        "test_cust_search_module",
        "agents/skills/customer-information-skill/scripts/customer_search.py"
    )
    query_customer_registry = cust_search_mod.query_customer_registry
    from tools.scripts.customer_search import search_customers, load_customer_database

    # Verify 20 customers, address with country info, and 3-5 products purchased
    records = load_customer_database()
    assert len(records) == 20, f"Expected 20 customers, got {len(records)}"
    for r in records:
        assert r.get("name"), "Customer must have a name"
        assert r.get("address"), "Customer must have an address"
        assert r.get("country"), "Customer must have country info"
        import re
        prods = [p.strip() for p in re.split(r"[,;]", r.get("products_purchased", "")) if p.strip()]
        assert 3 <= len(prods) <= 5, f"Customer {r['name']} must have 3-5 products, got {len(prods)}"

    # Test search via skill
    res = query_customer_registry(keywords=["Canada", "Australia"])
    assert res["status"] == "success"
    assert res["total_matches"] >= 1
    for match in res["results"]:
        assert match["country"] in ["Canada", "Australia"]

    # Test modular search_customers from tools
    matches = search_customers(keywords=["France"])
    assert len(matches) >= 1
    assert all(m["country"] == "France" for m in matches)

# 9. Test RBAC, VectorDB Types, Prompt Sender, and Domain Scoping
def test_rbac_and_multitenancy_extensions():
    import auth_service.server as auth_srv
    auth_client = auth_srv.app.test_client()

    # Verify seed accounts
    res_admin_a = auth_client.post("/api/auth/login", json={"username": "admin-1@example-a.com", "password": "password123"})
    assert res_admin_a.status_code == 200
    user_admin_a = res_admin_a.get_json()["user"]
    assert user_admin_a["role"] == "Admin"
    assert user_admin_a["domain"] == "example-a.com"

    res_editor_a = auth_client.post("/api/auth/login", json={"username": "editor@example-a.com", "password": "password123"})
    assert res_editor_a.status_code == 200
    user_editor_a = res_editor_a.get_json()["user"]
    assert user_editor_a["role"] == "Editor"
    assert user_editor_a["domain"] == "example-a.com"

    res_user_a = auth_client.post("/api/auth/login", json={"username": "user@example-a.com", "password": "password123"})
    assert res_user_a.status_code == 200
    user_user_a = res_user_a.get_json()["user"]
    assert user_user_a["role"] == "User"
    assert user_user_a["domain"] == "example-a.com"

    # Domain Admin user list is scoped to example-a.com
    list_res = auth_client.get("/api/users?domain=example-a.com&role=Admin")
    assert list_res.status_code == 200
    users = list_res.get_json().get("users", [])
    assert all(u.get("domain") == "example-a.com" for u in users)
    emails = [u["email"] for u in users]
    assert "admin-1@example-a.com" in emails
    assert "user@example-a.com" in emails
    assert "admin-2@sample-b.com" not in emails

    # Domain Admin cannot delete user in another domain
    list_all = auth_client.get("/api/users")
    user_b = next(u for u in list_all.get_json()["users"] if u["email"] == "user@sample-b.com")
    del_res = auth_client.delete(f"/api/users/{user_b['id']}?domain=example-a.com&role=Admin")
    assert del_res.status_code == 403

    # Test Logging Service user sender & domain scoping
    logging_srv = load_service("test_logging_module_2", "logging/server.py")
    log_client = logging_srv.app.test_client()

    log_client.post("/api/logs", json={
        "type": "chat_interaction",
        "invoker": "web_ui",
        "recipient": "agent",
        "conversation_id": "conv_user_a_1",
        "user": "user@example-a.com",
        "domain": "example-a.com",
        "payload": {"prompt": "Hello from user A", "response": "Hi A!"},
        "short_description": "User A interaction"
    })
    log_client.post("/api/logs", json={
        "type": "chat_interaction",
        "invoker": "web_ui",
        "recipient": "agent",
        "conversation_id": "conv_user_b_1",
        "user": "user@sample-b.com",
        "domain": "sample-b.com",
        "payload": {"prompt": "Hello from user B", "response": "Hi B!"},
        "short_description": "User B interaction"
    })

    # User A only sees their own conversations
    conv_a = log_client.get("/api/conversations?user=user@example-a.com&role=User&domain=example-a.com")
    assert conv_a.status_code == 200
    c_list_a = conv_a.get_json().get("conversations", [])
    c_ids_a = [c["conversation_id"] for c in c_list_a]
    assert "conv_user_a_1" in c_ids_a
    assert "conv_user_b_1" not in c_ids_a

    # Domain Admin for example-a.com sees conv_user_a_1 but not conv_user_b_1
    conv_admin_a = log_client.get("/api/conversations?user=admin-1@example-a.com&role=Admin&domain=example-a.com")
    assert conv_admin_a.status_code == 200
    c_ids_admin = [c["conversation_id"] for c in conv_admin_a.get_json().get("conversations", [])]
    assert "conv_user_a_1" in c_ids_admin
    assert "conv_user_b_1" not in c_ids_admin

    # Global Admin sees both
    conv_global = log_client.get("/api/conversations?user=admin&role=Admin")
    assert conv_global.status_code == 200
    c_ids_global = [c["conversation_id"] for c in conv_global.get_json().get("conversations", [])]
    assert "conv_user_a_1" in c_ids_global
    assert "conv_user_b_1" in c_ids_global

    # Test doc_RAG routing for type "Skills" vs "Documents"
    doc_rag_srv = load_service("test_doc_rag_module_2", "doc_RAG/server.py")
    doc_client = doc_rag_srv.app.test_client()

    add_skill_res = doc_client.post("/api/rag/documents/add", json={
        "name": "troubleshooting_guide",
        "complete_text": "Steps to resolve network timeouts and retry logic.",
        "type": "Skills",
        "domain": "example-a.com"
    })
    assert add_skill_res.status_code == 200
    assert add_skill_res.get_json()["status"] == "success"

    add_doc_res = doc_client.post("/api/rag/documents/add", json={
        "name": "annual_review_2026",
        "complete_text": "Company financial summary and corporate milestones.",
        "type": "Documents",
        "domain": "example-a.com"
    })
    assert add_doc_res.status_code == 200
    assert add_doc_res.get_json()["status"] == "success"

    # Test JWT Activities endpoint in Web UI
    web_app_jwt = load_service("test_web_ui_jwt", "web_ui/app.py")
    web_client_jwt = web_app_jwt.app.test_client()
    with web_client_jwt.session_transaction() as sess:
        sess["user"] = {"email": "admin@example-a.com", "role": "Admin", "domain": "example-a.com"}
    jwt_acts_res = web_client_jwt.get("/api/jwt/activities")
    assert jwt_acts_res.status_code == 200
    assert "activities" in jwt_acts_res.get_json()

    # Test Web UI role restriction on VectorDB ingestion
    web_app = load_service("test_web_ui_module_2", "web_ui/app.py")
    web_client = web_app.app.test_client()
    with web_client.session_transaction() as sess:
        sess["user"] = {"email": "user@example-a.com", "role": "User", "domain": "example-a.com"}
        sess["user_role"] = "User"
        sess["user_domain"] = "example-a.com"

    ingest_user_res = web_client.post("/api/vectordb/ingest", json={
        "source": "https://example.com/test.txt",
        "type": "Documents"
    })
    assert ingest_user_res.status_code == 403
    assert "cannot" in ingest_user_res.get_json().get("error", "").lower() or "not permitted" in ingest_user_res.get_json().get("error", "").lower()

