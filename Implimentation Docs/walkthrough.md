# Walkthrough: AI Agent with RAG Web Application

The AI Agent with RAG web application has been implemented according to [SPECIFICATION.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/SPECIFICATION.md).

---

## 🏗️ Architecture & Changes Implemented

### 1. Centralized Configuration & Environment (`config.py`)
- Reads `GEMINI_API_KEY` and `PORT` from [.env](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/.env) (default port 8005).
- Supports CLI override `--port <port>`.
- Defines `DEFAULT_LLM_MODEL = "gemma-4-26b-a4b-it"`.
- Sets default parameters: temperature (0.7), max tokens (4096), max turns (3), RAG chunks (5), skill threshold (0.2), doc threshold (0.3).

### 2. Dual ChromaDB Vector Store (`services/vector_store.py`)
- **`skills_store`**: Embeds `name: description` from `SKILL.md` and indexes complete markdown instructions. Supports cosine similarity threshold queries.
- **`documents_store`**: Ingests files/URLs with configurable character chunk size and overlap. Enforces SHA-256 chunk deduplication. Supports document-level deletion and database reset.

### 3. Ollama Embedding Lifecycle (`services/ollama_service.py`)
- Automatically detects running Ollama instances on port 11434 (`started_by_app = False`).
- Starts daemon if offline and cleanly shuts it down on exit if started by the app.
- Manages models: `bge-m3`, `nomic-embed-text`, `all-minilm`, `bge-large`.
- Logs first 50 characters of embedded text chunks per specification.

### 4. Google AI Studio & Custom Models (`services/llm_service.py`)
- Dynamically queries Google AI Studio API for all active text-generation models (`generateContent` action) and extracts token limits.
- Supports custom OpenAI-compatible HTTP endpoints (`http://127.0.0.1:8000/v1/chat/completions`).
- Logs full model prompts and responses to the audit event trace while redacting sensitive API keys.

### 5. Dual Agents
- **Custom Agent (`services/agent_orchestrator.py`)**: Multi-turn ReAct reasoning loop that queries skills, plans tool calls in structured JSON (`{"tool": "...", "arguments": {...}}`), observes tool execution results, and synthesizes answers within `max_turns`.
- **Google ADK Agent (`services/google_adk_agent.py`)**: Integrates Google ADK `LlmAgent` and runner executing tool callables with event tracing.

### 6. Domain Skills & Tools
1. [time-weather-skill](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/time-weather-skill/): Real-time weather and local time via Open-Meteo.
2. [person-information-skill](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/person-information-skill/): 20 personnel records in `registry.csv`.
3. [stock-market-skill](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/stock-market-skill/): Top stock gainers and losers.
4. [document-search-skill](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/document-search-skill/): Semantic ChromaDB chunk retrieval.

### 7. Rich 4-Page Frontend GUI
- **Page 1: Chat & Knowledge Synthesis**: Interactive chat with anchored "Show Logs" detail box, component bubbles (`Agent`, `Tools`, `RAG`, `Skills`), elapsed times, and grouped retrieved document evidence.
- **Page 2: Vector DB Ingestion**: Document ingestion with 5 sample URLs, collapsible chunk parameters, deduplication, document table with delete buttons, and stern warning embedder model switcher.
- **Page 3: Telemetry**: Line charts for throughput and token velocity alongside TTFT, ITL, TPS, and TPOT metrics.
- **Page 4: Audit Log & Event**: 7-row scrollable conversation selector, event trace table, and detailed JSON payload inspector modal.
- **Header & Modals**: Animated health status dot, light red "Shutdown" button with confirmation typing (`Shutdown the service`), and tab/app GIF icons.

---

## 🧪 Verification & Results

### 1. Automated Pytest Suite
Ran all 17 automated tests across vector store, skills, logging, telemetry, and REST endpoints:
```bash
.venv/bin/python3 -m pytest tests/ -v
```
**Result**:
```
tests/test_api_endpoints.py::test_health_endpoint PASSED                 [  5%]
tests/test_api_endpoints.py::test_models_endpoint PASSED                 [ 11%]
tests/test_api_endpoints.py::test_skills_endpoint PASSED                 [ 17%]
tests/test_api_endpoints.py::test_vectordb_stats_endpoint PASSED         [ 23%]
tests/test_api_endpoints.py::test_telemetry_endpoint PASSED              [ 29%]
tests/test_api_endpoints.py::test_logs_endpoint PASSED                   [ 35%]
tests/test_logging_telemetry.py::test_api_key_redaction PASSED           [ 41%]
tests/test_logging_telemetry.py::test_event_logging PASSED               [ 47%]
tests/test_logging_telemetry.py::test_telemetry_metrics_calculation PASSED [ 52%]
tests/test_skills.py::test_person_registry_search_by_name PASSED         [ 58%]
tests/test_skills.py::test_person_registry_search_by_job PASSED          [ 64%]
tests/test_skills.py::test_stock_performers_gainers PASSED               [ 70%]
tests/test_skills.py::test_stock_performers_losers PASSED                [ 76%]
tests/test_skills.py::test_weather_skill_structure PASSED                [ 82%]
tests/test_skills.py::test_skill_manager_execution PASSED                [ 88%]
tests/test_vector_store.py::test_chunking_logic PASSED                   [ 94%]
tests/test_vector_store.py::test_document_ingestion_and_deduplication PASSED [100%]

======================== 17 passed in 3.95s ========================
```

### 2. Live API Endpoint Verifications
- **Health Check (`GET /api/health`)**:
  ```json
  {
    "services": {
      "agent": "Healthy",
      "default_model": "gemma-4-26b-a4b-it",
      "llm_provider": "Configured",
      "ollama": "Running",
      "ollama_active_model": "bge-m3",
      "ollama_started_by_app": false,
      "vector_store": "Connected"
    },
    "status": "Online"
  }
  ```
- **Custom Agent Multi-Turn Execution (`POST /api/chat`)**:
  - Query: *"Find Lucas Dubois in the registry and tell me his job title and city."*
  - Matched: `person-information-skill` (score: 0.4189).
  - Executed: `person_search.query_person_registry(keyword="Lucas Dubois", field="name")`.
  - Response: *"Lucas Dubois is the Chief AI Architect and lives in Paris."* (in 2 turns).
- **RAG Knowledge Retrieval (`POST /api/chat`)**:
  - Query: *"What is Agentic RAG according to our documents?"*
  - Matched: `document-search-skill`.
  - Executed: `doc_search.query_documents` against ChromaDB `documents_store`.
  - Response: Cites `agent_and_rag.md` with grounded definitions.
- **Telemetry (`GET /api/telemetry`)**:
  - Total prompts: 7, Total input tokens: 6,204, Output tokens: 432.
  - Latency: TTFT 1,187 ms, TPS 18.2 tok/s, TPOT 85.2 ms/tok.
- **Audit Logs (`GET /api/logs`)**:
  - 54 individual events logged to `database/log.json` with key redaction and conversation grouping.
