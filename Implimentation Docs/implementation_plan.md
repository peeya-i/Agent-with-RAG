# Implementation Plan - AI Agent with RAG Web Application

Implement the complete web application specified in `SPECIFICATION.md` to manage an AI Agent with RAG capabilities, supporting dual ChromaDB vector stores, local Ollama embeddings, Google AI Studio LLMs, a Custom Multi-Turn Agent, a Google ADK LlmAgent, live telemetry, and full audit logging.

## User Review Required

> [!IMPORTANT]
> **Ollama Service Management**: The application will detect whether Ollama is already running on port 11434 (`ollama serve`). If already running, the app will not shut it down upon exit. If started by the app, it will cleanly terminate Ollama on shutdown.
> 
> **Default Model**: Per specification, `DEFAULT_LLM_MODEL = "gemma-4-26b-a4b-it"` is set in `config.py`. The app dynamically queries Google AI Studio API for all active text-generation models (`'generateContent' in supported_actions`) to populate the model selector.
>
> **Dual Vector Store**: ChromaDB will manage two distinct collections:
> 1. `skills_store`: stores full `SKILL.md` content indexed by skill name and description vectors.
> 2. `documents_store`: stores chunked documents with chunk deduplication and document-level deletion.

---

## Architecture Overview

```
Agent-with-RAG/
├── database/                   # Persistent ChromaDB storage & log.json
│   └── log.json
├── sample_docs/                # Domain documents for RAG
│   ├── agent_and_rag.md
│   ├── company_marketing_strategy.md
│   └── financial_report.md
├── services/                   # Modular backend service layer
│   ├── __init__.py
│   ├── ollama_service.py       # Ollama process lifecycle, embedder listing & pulling
│   ├── vector_store.py         # Dual ChromaDB collections (skills + documents)
│   ├── llm_service.py          # Google AI Studio API wrapper & Custom endpoint handler
│   ├── skill_manager.py        # Skill parser, directory scanner & execution dispatcher
│   ├── agent_orchestrator.py   # Custom Agent multi-turn planner & executor
│   ├── google_adk_agent.py     # Google ADK LlmAgent integration
│   ├── telemetry_service.py    # Metric aggregation, token velocity & TTFT tracking
│   └── log_service.py          # Audit event logger with JSON persistence & key redaction
├── skills/                     # Domain procedural skills
│   ├── time-weather-skill/
│   │   ├── SKILL.md
│   │   └── scripts/env_tools.py
│   ├── person-information-skill/
│   │   ├── SKILL.md
│   │   ├── data/registry.csv   # 20 flat-file records
│   │   └── scripts/person_search.py
│   ├── stock-market-skill/
│   │   ├── SKILL.md
│   │   └── scripts/stock_search.py
│   └── document-search-skill/
│       ├── SKILL.md
│       └── scripts/doc_search.py
├── static/
│   ├── css/style.css           # Premium dark-mode styling with glassmorphism
│   ├── js/app.js               # Reactive UI controller for all 4 pages
│   ├── js/chart.umd.min.js     # Chart.js library for telemetry visualization
│   └── images/                 # Tab and app GIF icons
├── templates/
│   └── index.html              # 4-page single-page application layout
├── tests/                      # Pytest automated test suite
│   ├── test_vector_store.py
│   ├── test_skills.py
│   ├── test_logging_telemetry.py
│   └── test_api_endpoints.py
├── app.py                      # Core Flask Orchestrator & REST endpoints
├── config.py                   # Centralized configuration & environment loader
├── requirements.txt            # Dependency declarations
└── README.md                   # Installation, execution & user guide
```

---

## Proposed Changes

### Configuration & Dependencies

#### [NEW] [config.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/config.py)
- Load environment variables from `.env` via `python-dotenv`:
  - `GEMINI_API_KEY`: API key for Google AI Studio / Gemini API.
  - `PORT`: Default web app port (default `5000` if absent in `.env`).
- Constants:
  - `DEFAULT_LLM_MODEL = "gemma-4-26b-a4b-it"`
  - `DEFAULT_EMBEDDER = "bge-m3"` (fallback to available Ollama models e.g. `nomic-embed-text` / `all-minilm`)
  - `DEFAULT_TEMPERATURE = 0.7`
  - `DEFAULT_MAX_TOKENS = 4096`
  - `DEFAULT_MAX_TURNS = 3`
  - `DEFAULT_RAG_CHUNKS = 5`
  - `DEFAULT_SKILL_THRESHOLD = 0.2`
  - `DEFAULT_DOC_THRESHOLD = 0.3`
  - Paths for database, sample docs, skills, logs.

#### [NEW] [requirements.txt](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/requirements.txt)
- `flask`, `python-dotenv`, `google-genai`, `google-adk`, `chromadb`, `requests`, `psutil`, `pydantic`, `pytest`.

---

### Backend Service Layer (`services/`)

#### [NEW] [services/log_service.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/log_service.py)
- Manages `database/log.json` with thread-safe file persistence.
- Formats each event record: `timestamp` (ISO format), `conversation_id`, `event_type` (`agent`, `skill search`, `document search`, `tool`, `ollama vector`, `LLM`), `invoker`, `target`, `short_description`, `payload` (unredacted except for API keys replaced with `****`), `elapsed_ms`.
- Separate log entries for request and response.
- Query API: filter by conversation ID, aggregate conversation summaries, clear logs.

#### [NEW] [services/ollama_service.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/ollama_service.py)
- Health check against Ollama daemon (`http://localhost:11434/api/tags`).
- Automatically launches `ollama serve` if not running, records `started_by_app = True`.
- Provides shutdown method that only terminates Ollama if `started_by_app == True`.
- Model catalogue: list installed models and available models with dimensions, context window, size, status (`Installed`, `Active`, `Available to Pull`).
- Embedding generator: calls Ollama `/api/embeddings`, logs first 50 chars of chunk to `log_service`.
- Model switcher: pull new model, switch active embedder.

#### [NEW] [services/vector_store.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/vector_store.py)
- Wraps ChromaDB `PersistentClient(path="database/chroma")`.
- `skills_store` collection:
  - Vectorizes `name + " " + description`.
  - Stores complete `SKILL.md` text and metadata.
  - Queries by embedding with cosine distance/threshold filtering.
- `documents_store` collection:
  - Chunks text by `chunk_size` and `chunk_overlap`.
  - Deduplicates chunks via content hashing before adding.
  - Documents listing: document name, chunk count, character count.
  - Delete document by source name.
  - Reset database and clear collections.

#### [NEW] [services/llm_service.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/llm_service.py)
- Google AI Studio API client (`google.genai.Client`).
- Active model discovery: queries `client.models.list()`, filters for `generateContent` capability, checks input/output token limits.
- Model invocation: supports streaming/non-streaming generation with temperature, max tokens, system instruction.
- Custom endpoint support: sends standard OpenAI-compatible completions payload to user-specified endpoint.
- Redacts API keys from logs while logging full input prompt and full model response to `log_service`.

#### [NEW] [services/skill_manager.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/skill_manager.py)
- Scans `skills/` directory on startup and on demand ("Update Skills Database").
- Parses YAML frontmatter and markdown sections in `SKILL.md`.
- Synchronizes with `skills_store` vector database (skips already indexed skills).
- Dynamic tool dispatcher: safely imports and executes tool functions from `skills/<skill_name>/scripts/` or `tools/`.

#### [NEW] [services/agent_orchestrator.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/agent_orchestrator.py)
- Implements the Custom Agent workflow:
  1. Receives message, logs initial `agent` request.
  2. Evaluates skill selection:
     - If "Vector Store": queries `skills_store` using cosine similarity threshold.
     - If "LLM Selected": queries LLM to select applicable skills.
     - If specific skill chosen: loads that skill.
  3. If no skills found: sends direct prompt to LLM to synthesize answer.
  4. If skills found: prompts LLM with user query + up to 2 best matching skills, requesting JSON decision `{"tool": "...", "arguments": {...}}`.
  5. Executes tool via `skill_manager`, logs tool invocation and response.
  6. Sends tool results back to LLM. Repeats up to `max_turns`.
  7. Final LLM call produces synthesized human-friendly answer.
  8. Emits step timing and bubbles (`Agent`, `Tools`, `RAG`, `Skills`) for UI "Show Logs" detail box.

#### [NEW] [services/google_adk_agent.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/google_adk_agent.py)
- Integrates `google.adk.agents.LlmAgent` and `Runner`.
- Binds skills and tools as callables.
- Logs before/after model calls and tool executions to `log_service`.
- Formats response and step telemetry for UI display.

#### [NEW] [services/telemetry_service.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/telemetry_service.py)
- Records metrics per invocation: prompt tokens, output tokens, latency, error status, model name.
- Computes aggregated timeseries (1m, 15m, 1h, 1d intervals) over requested time ranges (Last hr, 1 day, Week, Month, Custom).
- Calculates latency metrics: TTFT (Time to First Token), ITL (Inter-Token Latency), TPS (Tokens Per Second), TPOT (Time Per Output Token).

---

### Skills & Procedural Tools (`skills/`)

#### [NEW] [skills/time-weather-skill/](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/time-weather-skill/)
- `SKILL.md`: Metadata, trigger queries, parameters.
- `scripts/env_tools.py`: Calls Open-Meteo geocoding & forecast API (no API key needed) and local timezone time.

#### [NEW] [skills/person-information-skill/](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/person-information-skill/)
- `SKILL.md`: Metadata and trigger definitions.
- `data/registry.csv`: 20 records (name, city, country, job title).
- `scripts/person_search.py`: Filter registry by name, city, country, or job title.

#### [NEW] [skills/stock-market-skill/](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/stock-market-skill/)
- `SKILL.md`: Metadata for stock queries.
- `scripts/stock_search.py`: Returns highest % gainers or lowest % losers based on question criteria.

#### [NEW] [skills/document-search-skill/](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/skills/document-search-skill/)
- `SKILL.md`: Metadata describing semantic document text retrieval.
- `scripts/doc_search.py`: Queries `documents_store` vector database with threshold.

---

### Sample Documents (`sample_docs/`)

#### [NEW] [sample_docs/agent_and_rag.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/sample_docs/agent_and_rag.md)
- In-depth guide on Agentic workflows, tool routing, and RAG architectures.

#### [NEW] [sample_docs/company_marketing_strategy.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/sample_docs/company_marketing_strategy.md)
- Realistic corporate go-to-market strategy, product positioning, and quarterly marketing KPIs.

#### [NEW] [sample_docs/financial_report.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/sample_docs/financial_report.md)
- Corporate fiscal performance, revenue breakdown, EBITDA, and operational expenditures.

---

### Core Orchestrator & Web Server (`app.py`)

#### [NEW] [app.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/app.py)
- Initializes Flask app, parses `--port` CLI argument (overriding `.env` and default `5000`).
- Initializes `OllamaService`, starts daemon if needed, registers graceful exit handlers.
- Endpoints:
  - `GET /`: Serves `index.html`.
  - `GET /api/health`: Health status of Agent, Ollama, Vector DB, LLM API.
  - `POST /api/shutdown`: Graceful shutdown requiring exact confirmation string `"Shutdown the service"`.
  - `GET /api/models`: Lists active Google AI Studio models and token limits.
  - `POST /api/chat`: Handles chat interaction with either Custom Agent or Google ADK Agent.
  - `GET /api/vectordb/stats`: Ingestion stats (chunk count, doc count, DB size in MB).
  - `POST /api/vectordb/ingest`: Ingests URL or local file with chunk size and overlap, deduplication.
  - `DELETE /api/vectordb/document`: Deletes single document from ChromaDB.
  - `POST /api/vectordb/reset`: Resets document database.
  - `GET /api/vectordb/models`: Lists Ollama embedding models with details and status.
  - `POST /api/vectordb/change-model`: Switches embedder with confirmation, clears data, re-indexes skills.
  - `POST /api/skills/update`: Scans and loads new skills.
  - `GET /api/telemetry`: Returns aggregated metrics and timeseries for Chart.js.
  - `GET /api/logs`: Returns conversation list and event details.
  - `POST /api/logs/clear`: Clears audit log file.

---

### Frontend UI (`templates/` & `static/`)

#### [NEW] [templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/templates/index.html)
- 4 full-page views switched with top tabs:
  1. **Chat & Knowledge Synthesis**: Left card ("Chat with the Agent"), Right card ("Retrieved Context Evidence").
  2. **Vector DB Ingestion**: Left card ("Populate Vector Database" with 5 sample URLs), Right card ("Vector Storage Status"), Bottom table ("Available Embedding Models").
  3. **Telemetry**: Header controls & filters, Top card ("System Throughput & Token Velocity" with two line charts), Bottom card (TTFT, ITL, TPS, TPOT).
  4. **Audit Log & Event**: Top table (scrollable user conversations, max 7 rows visible), Bottom table (events for selected conversation with payload popup dialog).
- Modals:
  - Shutdown confirmation (requires typing "Shutdown the service").
  - Change Embedder model warning modal.
  - Clear logs confirmation modal.
  - Detailed event JSON inspector modal.

#### [NEW] [static/css/style.css](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/static/css/style.css)
- Ultra-clean dark theme with slate/indigo accents, glassmorphism cards, glowing status badges, smooth micro-animations.
- Responsive split-card layouts.

#### [NEW] [static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/static/js/app.js)
- Comprehensive UI controller: tab switching, API polling, chat streaming/display, collapsible "Show Logs" detail boxes with component bubbles, Chart.js telemetry rendering, event table selection, modal handlers.

---

### Automated Tests (`tests/`)

#### [NEW] [tests/test_vector_store.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/tests/test_vector_store.py)
- Tests chunking, deduplication, skills indexing, and threshold querying.

#### [NEW] [tests/test_skills.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/tests/test_skills.py)
- Tests weather skill, person search registry, stock search, and doc search tools.

#### [NEW] [tests/test_logging_telemetry.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/tests/test_logging_telemetry.py)
- Tests event logging, API key redaction, telemetry calculation (TTFT, TPS, TPOT).

#### [NEW] [tests/test_api_endpoints.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/tests/test_api_endpoints.py)
- Tests Flask API endpoints with `app.test_client()`.

---

## Verification Plan

### Automated Tests
1. Run test suite using pytest:
   ```bash
   .venv/bin/python3 -m pytest tests/ -v
   ```
   Ensure all tests for vector store, skills, logging, telemetry, and API endpoints pass cleanly.

### Manual Verification
1. Launch app using configured port from `.env` (8005):
   ```bash
   .venv/bin/python3 app.py
   ```
2. Verify Ollama startup check and model enumeration from Google AI Studio.
3. Ingest `sample_docs/` into ChromaDB and verify stats and deduplication.
4. Test Chat with Custom Agent and Google ADK Agent:
   - Test question triggering weather skill ("What is the weather in Tokyo?").
   - Test question triggering person info skill ("Find Lucas Dubois in the registry").
   - Test question triggering RAG doc search ("What is Agentic RAG?").
   - Inspect "Show Logs" collapsible box with component bubbles and elapsed times.
   - Inspect Retrieved Context Evidence card.
5. Verify Telemetry page: aggregation intervals, time range filters, line charts, TTFT/TPS metrics.
6. Verify Audit Log & Event page: conversation table selection, event detail popup with formatted JSON.
7. Verify Shutdown modal: test typing exact text "Shutdown the service", verify button unlocks.
