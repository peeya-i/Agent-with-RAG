# Agent With RAG

An enterprise-grade AI Agent management application featuring Retrieval-Augmented Generation (RAG) capabilities, local vector embeddings, Google AI Studio integration, dual agent orchestrators (Custom Multi-Turn Agent and Google ADK LlmAgent), live inference telemetry, and comprehensive audit event tracing.

---

## 🌟 Features

- **Dual Vector Store Architecture**: ChromaDB persistent vector database maintaining distinct collections for:
  - **Skills Store (`skills_store`)**: Indexes domain procedural skill metadata (`name` + `description`) and complete `SKILL.md` definitions.
  - **Documents Store (`documents_store`)**: Indexes partitioned domain documents with chunk deduplication and document-level lifecycle management.
- **Local Ollama Vectorization**: Seamless local vector embedding generation (`bge-m3`, `nomic-embed-text`, `all-minilm`, `bge-large`) with automatic daemon lifecycle management.
- **Google AI Studio Integration**: Dynamic discovery of active text generation models with configurable temperature, token constraints, and custom OpenAI-compatible endpoint support. Default model: `DEFAULT_LLM_MODEL=gemma-4-26b-a4b-it`.
- **Dual Autonomous Agents**:
  - **Custom Multi-Turn Agent**: ReAct-style loop evaluating domain skills, executing procedural tools dynamically via structured JSON actions, observing tool results, and synthesizing verified final answers up to configurable `max_turns`.
  - **Google ADK Agent**: Google ADK `LlmAgent` and runner executing bound Python procedural tool callables.
- **Domain Procedural Skills**:
  1. `time-weather-skill`: Real-time weather conditions and local time via Open-Meteo (no API key required).
  2. `person-information-skill`: Personnel search over 20 flat-file records in `registry.csv` by name, city, country, or job title.
  3. `stock-market-skill`: Top equity gainers (highest % increase) and losers (lowest % decrease) tracking.
  4. `document-search-skill`: Semantic document chunk retrieval from ChromaDB.
- **Rich 4-Page Dark-Themed GUI**:
  1. **Chat & Knowledge Synthesis**: Interactive chat with expandable "Show Logs" detail box featuring component bubbles (Agent, Tools, RAG, Skills) and retrieved evidence cards.
  2. **Vector DB Ingestion**: URL or directory ingestion with sample links, collapsible chunking settings, document deletion, and safe embedder model switching.
  3. **Telemetry**: Line charts for throughput and token velocity alongside TTFT, ITL, TPS, and TPOT metrics.
  4. **Audit Log & Event**: 7-row scrollable conversation selector and event drill-down inspector with full unredacted JSON viewer.

---

## 📂 Directory Architecture

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
│   ├── ollama_service.py       # Ollama daemon lifecycle & embeddings
│   ├── vector_store.py         # Dual ChromaDB collections
│   ├── llm_service.py          # Google AI Studio API & Custom endpoints
│   ├── skill_manager.py        # Skill scanner & dynamic tool runner
│   ├── agent_orchestrator.py   # Custom Multi-Turn Agent
│   ├── google_adk_agent.py     # Google ADK LlmAgent
│   ├── telemetry_service.py    # Metric aggregation & timeseries
│   └── log_service.py          # Audit event logger with key redaction
├── skills/                     # Domain procedural skills
│   ├── time-weather-skill/
│   │   ├── SKILL.md
│   │   └── scripts/env_tools.py
│   ├── person-information-skill/
│   │   ├── SKILL.md
│   │   ├── data/registry.csv
│   │   └── scripts/person_search.py
│   ├── stock-market-skill/
│   │   ├── SKILL.md
│   │   └── scripts/stock_search.py
│   └── document-search-skill/
│       ├── SKILL.md
│       └── scripts/doc_search.py
├── static/
│   ├── css/style.css           # Modern glassmorphism dark theme
│   ├── js/app.js               # Reactive UI controller
│   ├── js/chart.umd.min.js     # Offline Chart.js library
│   └── images/                 # Animated GIF icons
├── templates/
│   └── index.html              # Single-page application shell
├── tests/                      # Pytest automated test suite
├── app.py                      # Core Orchestrator & REST endpoints
├── config.py                   # Centralized configuration & environment loader
├── requirements.txt            # Package declarations
└── README.md                   # System documentation & user guide
```

---

## ⚙️ Installation

### 1. Prerequisites
- **Python 3.10+** (Python 3.14 recommended)
- **Ollama**: Installed locally on system (`curl -fsSL https://ollama.com/install.sh | sh`)
- **Google AI Studio API Key**: Required for Gemini / Gemma models.

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Create or edit `.env` in the root directory:
```bash
GEMINI_API_KEY=your_google_ai_studio_key_here
PORT=8005
```

---

## 🚀 Starting the Services

Launch the application directly via Python:
```bash
python3 app.py
```
Or specify a custom port overriding `.env`:
```bash
python3 app.py --port 8005
```

### What Happens on Startup:
1. The app checks whether the local **Ollama** service is running on port 11434. If not running, it automatically starts `ollama serve` in the background.
2. The `skills/` folder is scanned, and all procedural skills are embedded and indexed into the ChromaDB `skills_store`.
3. If the document database is empty, sample documents from `sample_docs/` are automatically chunked, deduplicated, and ingested.
4. The web server binds to the configured port (`http://127.0.0.1:8005`).

---

## 🛑 Shutting Down the Services

### Option A: Via GUI (Recommended)
1. In the web interface, click the light red **"Shutdown"** button at the top-right corner.
2. A confirmation dialog appears. Type the confirmation phrase:
   ```
   Shutdown the service
   ```
3. Click **"Confirm"**. The application will:
   - Terminate the web server process cleanly.
   - Stop the Ollama service **only if** this application started it on startup (preserving instances that were already running).

### Option B: Terminal
Press `Ctrl+C` in the running terminal. The registered shutdown handler will clean up background processes.

---

## 📖 User Guide

### 1. Chat & Knowledge Synthesis (Page 1)
- **Model Configuration**: Select any active text-generation model discovered from Google AI Studio, or select **Custom Model** to specify an OpenAI-compatible HTTP endpoint.
- **Agent Selection**: Choose between **Custom Agent** (multi-turn tool loop) and **Google ADK Agent** (Google ADK `LlmAgent`).
- **Skill Selection**: Select **Vector Store** (default with configurable cosine similarity threshold), **LLM Selected**, or specify an individual skill.
- **Interactive Chat**: Type any query or select a quick prompt.
- **Inspection**:
  - Click **"Show Logs"** anchored at the top right of any agent response detail box to inspect intermediate steps, timing, and raw component outputs.
  - View the **Retrieved Context Evidence** card on the right to inspect exact chunks retrieved from the vector database, grouped by source document.

### 2. Vector DB Ingestion (Page 2)
- **Populate Database**: Enter a web URL or local directory/file path, configure chunk size and overlap, and click **"Populate Vector Database"**. Chunks are deduplicated automatically.
- **Manage Documents**: Inspect ingested documents in the table and delete individual documents using the **Delete** button.
- **Switch Embedder Model**: Select a new embedding model from the dropdown. Follow the confirmation modal prompt (`Change model and delete data`) to pull the model, clear outdated vectors, and re-index skills.
- **Update Skills Database**: Click to scan `skills/` and load new skills into ChromaDB without re-indexing existing ones.

### 3. Telemetry (Page 3)
- Inspect real-time request counts (prompts, responses, errors) and token velocity (input/output tokens).
- Adjust aggregation intervals (1 min, 15 min, 1 hr, 1 day) and time ranges (Last hr, 1 day, Week, Month, Custom date range).
- Review latency diagnostics: **TTFT** (Time to First Token), **ITL** (Inter-Token Latency), **TPS** (Tokens Per Second), and **TPOT** (Time Per Output Token).

### 4. Audit Log & Event (Page 4)
- **User Conversations Table**: Select any conversation row (scrollable up to 7 visible rows) to highlight it.
- **Events Table**: Inspect all individual events recorded during the selected conversation (requests, responses, model calls, vector queries, tool executions).
- **Payload Inspector**: Click on any event row to open a modal dialog showing unredacted JSON payloads formatted for human review.
- **Clear Logs**: Click **"Clear Logs"** and confirm to reset `database/log.json`.

---

## 🧪 Running Automated Tests

Run the complete pytest test suite:
```bash
pytest tests/ -v
```
