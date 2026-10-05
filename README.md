# Agent With RAG (Enterprise Autonomous Architecture)

An enterprise multi-container web application and autonomous AI Agent platform with dynamic Retrieval-Augmented Generation (RAG), FastMCP tool orchestration, ChromaDB vector storage, Ollama local embedding, and comprehensive telemetry/audit logging.

---

## 1. What This System Does

* **Multi-Tenant Architecture:** Identity is tied to email addresses. The email domain determines tenant isolation across RAG documents and tool data sources. Global administrators (`admin`) operate domain-free with full system-wide access.
* **Unified JWT Authentication:** When a user logs in, a cryptographically signed JSON Web Token (JWT) is issued containing tenant claims (`sub`, `email`, `role`, `domain`). Individual container token creation has been decommissioned; the login JWT token serves as the primary authentication across all microservices (`agents`, `doc_rag`, `tools`).
* **Domain-Specific RAG Knowledge Isolation:** Vector similarity search and document statistics in `doc_RAG` are strictly partitioned by tenant domain (`example-a.com`, `sample-b.com`, or unrestricted for Admin).
* **Domain-Specific CSV Tool Access:**
  * `example-a.com`: Granted access to `tools/data/employee_database.csv` (employee registry).
  * `sample-b.com`: Granted access to `tools/data/customer_database.csv` (customer purchase registry).
  * `Admin`: Granted unrestricted access to both CSV databases.
* **Autonomous Multi-Turn Reasoning:** Executes goal-oriented conversational workflows using either a **Custom Agent** (with tool execution loops up to a configurable turn limit) or a **Google ADK Agent** (via Google AI Studio GenAI SDK).
* **Dynamic Skill & Tool Invocation:** Intercepts structured JSON tool calls from LLMs and invokes procedural FastMCP tools (employee registry search, customer registry search, stock market analysis, weather/time lookup, document retrieval).
* **Dual-Collection Vector Store (`doc_RAG`):** Powered by ChromaDB and local Ollama embeddings (`nomic-embed-text`, `bge-m3`) across two isolated collections:
  * `skill`: Semantic discovery and prompt augmentation for procedural skills.
  * `document`: High-precision chunked semantic document retrieval with tenant isolation.
* **Granular Authentication & RBAC (`auth_service`):** SQLite-backed credential and API key management with role-based access control (`Admin`, `Editor`, `User`), token expiration, and inter-container permission scoping.
* **Real-Time Container Topology (`Container Mgr`):** Visual interactive system architecture diagram with live CPU/RAM metrics, health status, and administrative container lifecycle operations (`Start`, `Stop`, `Restart`, `Shutdown All`).
* **Comprehensive Telemetry & Audit Logs (`logging`):** Centralized append-only JSON logging capturing full raw payloads, latency distributions (TTFT, ITL, TPS, TPOT), and user conversation histories.

---

## 2. Architecture & Container Port Assignments

The platform runs as 7 decoupled microservices orchestrated via Docker Compose:

| Service | Directory | TCP Port | Protocol | Purpose |
|---|---|---|---|---|
| **Web UI** | `web_ui/` | **8000** | HTTP / Flask | 6-Page responsive web interface & Docker orchestrator |
| **Auth Service** | `auth_service/` | **8001** | HTTP REST | SQLite authentication, multi-tenant accounts, JWT issuing |
| **Agents** | `agents/` | **8002** | FastMCP (async HTTP) | Custom & Google ADK Agent multi-turn reasoning loops |
| **Doc & Skills RAG** | `doc_RAG/` | **8003** | FastMCP (async HTTP) | ChromaDB vector store with tenant domain isolation |
| **Ollama Embeddings** | `ollama` | **11434** | REST API | Official Ollama daemon generating dense vector embeddings |
| **Tools** | `tools/` | **8005** | FastMCP (async HTTP) | Domain-scoped CSV databases (employee & customer) & market tools |
| **Logging** | `logging/` | **8006** | HTTP REST | Centralized audit logs, conversation history, and telemetry |

---

## 3. Installation & Prerequisites

### Prerequisites
* **Docker & Docker Compose:** Docker Engine 24+ and Docker Compose v2.
* **Ollama (Optional for Host Mode):** If running outside Docker, Ollama listening on `127.0.0.1:11434`.
* **Google Gemini API Key:** Required for Gemini model synthesis via Google AI Studio.

### Setup Environment
1. Copy or edit `.env` in the repository root:
   ```bash
   cp .env.example .env
   ```
2. Configure your parameters in `.env`:
   ```ini
   PORT=8000
   GEMINI_API_KEY=your_google_ai_studio_api_key_here
   GEMINI_MODEL=gemma-4-26b-a4b-it
   FLASK_SECRET_KEY=change_this_to_a_secure_random_key
   ```

---

## 4. How to Start All Services

### Using Docker Compose (Recommended Production Mode)
Run the following command from the repository root:
```bash
docker compose up -d --build
```
This automatically builds all 6 custom Python microservices, pulls the official Ollama container, configures isolated network bridges, and mounts host persistence volumes.

### Local Development / Native Mode (Without Docker)
You can also launch each microservice directly in Python:
```bash
# Terminal 1: Logging Container
cd logging && python3 server.py

# Terminal 2: Auth Service
cd auth_service && python3 server.py

# Terminal 3: Tools FastMCP Server
cd tools && python3 server.py

# Terminal 4: Doc & Skills RAG Server
cd doc_RAG && python3 server.py

# Terminal 5: Agents FastMCP Server
cd agents && python3 server.py

# Terminal 6: Web UI
cd web_ui && python3 app.py
```

Access the Web Console at: **`http://localhost:8000`**

---

## 5. How to Shutdown All Services

* **Via the Web UI (Any Page):** Click the light red **🛑 Shutdown** button in the top right header, type `Shutdown the services`, and confirm.
* **Via Container Mgr (Admin Only):** Navigate to the **Container Mgr** tab, click **Shutdown All**, type `Shutdown System`, and confirm.
* **Via Terminal (Docker Compose):**
  ```bash
  docker compose down
  ```

---

## 6. User Guide: Exploring the 6 Console Pages

### Initial Login & Multi-Tenant Credentials
1. On opening `http://localhost:8000`, a sign-in modal prompts for email credentials.
2. Default initial seed credentials:
   * **Admin (Global Access):**
     * **Email / Username:** `admin`
     * **Password:** `admin123`
     * **Scope:** No domain (`None`). Access to ALL RAG documents and BOTH CSV databases.
   * **Tenant A (`example-a.com`):**
     * **Email:** `user@example-a.com`
     * **Password:** `password123`
     * **Scope:** Access restricted to `example-a.com` RAG documents and `tools/data/employee_database.csv`.
   * **Tenant B (`sample-b.com`):**
     * **Email:** `user@sample-b.com`
     * **Password:** `password123`
     * **Scope:** Access restricted to `sample-b.com` RAG documents and `tools/data/customer_database.csv`.
3. Click **Ok** to authenticate. A signed JWT token is issued and stored in session storage for all API interactions.

### 🗣️ Page 1: Chat & Knowledge Mgnt
* **Model Selection:** Choose from active Google AI Studio models or select **Custom Model** to specify an OpenAI-compatible endpoint.
* **Hyperparameters:** Tune `Temperature` (0.0–2.0), `Max Tokens` (default 2048), and `Max Turns` (default: 5, range 1–10).
* **Agent Selector:** Toggle between **Custom Agent** and **Google ADK Agent**.
* **Skill Selector:**
  * `Vector Store Selects` (Default): Uses ChromaDB skill matching with configurable `Skill Threshold`.
  * `LLM Selects`: Supplies all skill definitions to the model for cognitive selection.
  * Direct Skill: Forces execution of a designated skill.
* **Inspection Bubbles:** Click **Show Logs** on any completed agent response to expand step-by-step component execution bubbles (Agent, Skills, Tools, RAG, LLM).
* **Retrieved Evidence:** The right card displays semantic chunks retrieved from vector stores matching your query within your tenant domain.

### 🛢️ Page 2: VectorDB Mgnt (Editor / Admin Only)
* **Real-time Statistics:** Monitor total ingested document chunks, unique files, and vector DB size in MB scoped to your tenant domain.
* **Update Skills Database:** Scans the `skills/` directory and synchronizes new `SKILL.md` definitions into the ChromaDB skill collection.
* **Populate Vector Database:** Enter a URL or local directory path, adjust `Chunk Size` and `Overlap`, and ingest custom files tagged to your tenant domain.
* **Storage Status & Reset:** Inspect active document records with their authorized **Tenant Domain** (identifying the organization that stored and retains access to each document, e.g. `example-a.com`, `sample-b.com`, or `All Tenants (Admin)`), delete individual documents, or trigger a full database reset.

### 📊 Page 3: Telemetry
* **Throughput & Velocity Graphs:** Track Request Throughput (prompts, responses, errors) and Token Velocity (input and output tokens) across selectable intervals (1 min, 15 min, 1 hr, 1 day) and ranges.
* **Hardware-Agnostic Latency Metrics:** View calculated Time to First Token (TTFT), Inter-Token Latency (ITL), Tokens Per Second (TPS), and Time Per Output Token (TPOT).

### 📝 Page 4: Audit Logs & Events (Editor / Admin Only)
* **User Conversations Table:** Browse conversation sessions, user queries, agent types, and event counts.
* **Events for Conversation Table:** Select any conversation row to view chronologically sorted event traces.
* **Event Inspector:** Click any event row to open the interactive JSON inspector modal with copyable prompt/response payloads.

### 🚢 Page 5: Container Mgr (Admin Only)
* **Visual Topology Canvas:** Live drawing illustrating container interconnectivity and runtime state (light green for active, light red for stopped).
* **Interactive Node Control:** Click or right-click any container node to inspect port mappings, dependencies, and trigger `Start` or `Stop`.
* **Global Controls:** Use `Restart All` or `Shutdown All` for bulk orchestration.
* **Unified Authentication:** Individual container key files have been decommissioned in favor of login JWT tokens.

### 🔑 Page 6: Passwords & API Keys
* **Current Account Info:** View your active email, assigned role, and SQLite storage backend path.
* **Passwords Sub-Tab (Admin Only):**
  * **User Account Directory Access Control:** Only users with `Admin` access can make any changes to User accounts (changing roles, toggling Active/Locked status, resetting passwords, creating new users, and deleting users).
  * **Create New User:** Clicking **Create New User** opens a popup window prompting for email/username and password with **Cancel** and **Create** buttons.
  * **User Selection & Bulk Deletion:** Each username has an individual checkbox, with a "Select All" checkbox in the column header. A **Delete Users** button next to **Create New User** is enabled only when one or more user checkboxes are checked.
  * **User Access Activity Table:** Tracks all login attempts, logouts, registration events, and password resets.
* **API Keys & Multi-Tenant JWT Tokens Sub-Tab (Admin Only):**
  * **Active Multi-Tenant Session & JWT Token Inspector:** Displays the currently logged-in user email, role, tenant domain, permitted RAG documents, and permitted tools CSV file (`employee_database.csv` vs `customer_database.csv`), along with the raw encoded JWT token and a "Copy Token" button.
  * **Configured Container API Keys (Legacy / Service Access):** View existing API keys and their status.
  * **Interactive Key Activity Inspection:** Clicking any row highlights the selected key and displays historical events in the secondary **API Key Activities** table below.

---

## 7. Sample Skills and Tools Included

1. **`time-weather-skill`:** Real-time weather and local time lookup for any city worldwide using the free Open-Meteo public service.
2. **`person-information-skill`:** Employee registry lookups across 30 records (`tools/data/employee_database.csv`) using a list of search texts (or single search text) across name, city, country, or job title. Accessible to `example-a.com` and Admin.
3. **`customer-information-skill`:** Customer registry lookups across 20 records (`tools/data/customer_database.csv`) with name, address with country info, and 3-5 products purchased. Accessible to `sample-b.com` and Admin.
4. **`stock-market-skill`:** Real-time stock queries for top percentage gainers, losers, or equity quotes.
5. **`document-search-skill`:** Vector search for top-$k$ text chunks from the ingested ChromaDB knowledge store with multi-tenant domain isolation.

---

## 8. Sample Knowledge Documents & PDF Catalog (`sample_docs/`)

The platform includes six pre-configured reference knowledge documents in `sample_docs/` for multi-tenant RAG retrieval and evaluation:

### Markdown Reference Documents (~3,000 words each)
1. **`sample_docs/agent_and_rag.md`**: Comprehensive architectural treatise on autonomous multi-turn reasoning loops, cognitive tool orchestration, and vector retrieval. Tagged to domain `example-a.com`.
2. **`sample_docs/company_marketing_strategy.md`**: Enterprise marketing expansion, multi-channel customer acquisition, and brand equity growth roadmap. Tagged to domain `example-a.com`.
3. **`sample_docs/financial_report.md`**: Audited annual corporate financial statements, balance sheets, and cash flow operations. Tagged to domain `sample-b.com`.

### Extended Company Profiles in PDF (4,000+ Words Each)
4. **`sample_docs/nexus_enterprise_solutions_company_profile.pdf`**:
   - **Scope & Word Count:** **4,602 words** across 8 pages with professional two-pass 'Page X of Y' headers and footers.
   - **Content:** Corporate governance, 2012–2026 milestones, autonomous agent RAG architecture, vector quantization, multi-tenant cryptographic isolation, audited financials (FY2021–FY2025), zero-trust security & SOC 2 / ISO certifications, ESG initiatives, global office directory, and AI terminology lexicon.
   - **Multi-Tenant Access:** Tagged to domain `example-a.com` (and Admin).
5. **`sample_docs/vanguard_global_logistics_company_profile.pdf`**:
   - **Scope & Word Count:** **4,334 words** across 8 pages with professional two-pass 'Page X of Y' headers and footers.
   - **Content:** Multimodal freight operations (ocean container ships, Boeing 777F cargo aircraft, intermodal Class I rail, electric drayage), 240 automated robotic ASRS distribution centers, predictive Horizon AI engine, biopharma cryogenic cold-chain (-80°C to -196°C), dangerous goods safety, audited financials (FY2021–FY2025), fleet decarbonization (SBTi net-zero 2040), global marine port coordinates, and multimodal glossary.
   - **Multi-Tenant Access:** Tagged to domain `sample-b.com` (and Admin).

### Enterprise Product Offerings Catalog (100 Products with Volume Pricing)
6. **`sample_docs/product_catalog_100_offerings.pdf`**:
   - **Offerings Count:** Exactly **100 enterprise products** (`PRD-001` through `PRD-100`) spanning AI compute, data switches, optical transceivers, NVMe arrays, HSM security modules, software licenses, IoT sensors, cooling systems, and warehouse robotics.
   - **Table Columns:** `Item ID`, `Product Name`, `Product Description`, `Qty 1 Price (Base)`, `Qty 10+ Price (-10%)`, `Qty 100+ Price (-30%)`.
   - **Tiered Volume Discount Rules:**
     - **Quantity 1**: Base Unit Price.
     - **Quantity 10 or more**: Automatic 10% price drop (`Base Price * 0.90`).
     - **Quantity 100 or more**: Automatic 30% price drop (`Base Price * 0.70`).

### Reproducibility & Generation Scripts
All sample PDF documents can be deterministically regenerated using the automated build script:
```bash
python scripts/build_all_sample_pdfs.py
```
This script compiles the structured data modules (`scripts/nexus_profile_data.py`, `scripts/vanguard_profile_data.py`, `scripts/product_catalog_data.py`), verifies word counts (>= 4,000 words), asserts volume pricing discount formulas, and formats the output documents with ReportLab.
