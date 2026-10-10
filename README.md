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
* **Semantic Vector Routing (`agents_router`):** Vector embedding engine with cosine similarity and deterministic local fallback that analyzes prompts from Web UI. Routes to specialized agents (e.g. `agent_tech_support`) when similarity exceeds 50% (> 0.50) and agent status is UP. Defaults to the primary `agents` container for general queries or whenever match is <= 50%.
* **Specialized Product Tech Support Agent (`agent_tech_support`):** Dedicated domain agent for product troubleshooting, DevOps, Docker container crash log inspection (exit 137 OOMKilled), microservice timeouts, and database connection debugging. Dynamically auto-registers with the router upon container turn-up.
* **Agents Router Management GUI (`Agents` Tab):** Positioned between VectorDB and Telemetry, displays real-time directory of all registered agents with operational status badges (UP/DOWN), interactive semantic prompt routing simulator, and dynamic onboarding form/modal ("Add New Agent") to manually link new agent containers.
* **Unified Single `jwt_auth.py` Architecture:** A single copy of `jwt_auth.py` is maintained at the repository root and volume-mounted into all containers via `docker-compose.yml`, eliminating code duplication while guaranteeing full host and container interoperability.

---

## 2. Architecture & Container Port Assignments

The platform runs as 9 decoupled microservices orchestrated via Docker Compose:

| Service | Directory | TCP Port | Protocol | Purpose |
|---|---|---|---|---|
| **Web UI** | `web_ui/` | **8000** | HTTP / Flask | 7-Page responsive web interface & Docker orchestrator |
| **Auth Service** | `auth_service/` | **8001** | HTTP REST | SQLite authentication, multi-tenant accounts, JWT issuing |
| **Agents (Default)** | `agents/` | **8002** | FastMCP / HTTP REST | Default fallback agent multi-turn reasoning loops, tool & RAG synthesis |
| **Doc & Skills RAG** | `doc_RAG/` | **8003** | FastMCP (async HTTP) | ChromaDB vector store with tenant domain isolation |
| **Agents Router** | `agent_router/` | **8004** | HTTP REST | Vector embedding routing (> 50% threshold) & dynamic agent registry |
| **Tools** | `tools/` | **8005** | FastMCP (async HTTP) | Domain-scoped CSV databases (employee & customer) & market tools |
| **Logging** | `logging/` | **8006** | HTTP REST | Centralized audit logs, conversation history, and telemetry |
| **Tech Support Agent**| `agent_tech_support/`| **8007** | HTTP REST | Specialized technical support & DevOps diagnostics agent |
| **Ollama Embeddings** | `ollama` | **11434** | REST API | Official Ollama daemon generating dense vector embeddings |

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

### 🛡️ Role-Based Access Control (RBAC) & Multi-Tenant Access Matrix

| Role | Scope / Domain | Chat & Telemetry | Log Viewer Access | VectorDB Management | Ingest Documents / Skills | Manage Domain Users | Container Orchestration | JWT Activities Access |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **User** | Domain-bound (e.g., `user@example-a.com`) | ✅ Full access | 🔍 View only logs generated by own session | 👁️ View global & own org loaded vectors | ❌ Read-Only (Ingestion disabled) | ❌ No access | ❌ Hidden | 🔑 View own initial JWT requests |
| **Editor** | Domain-bound (e.g., `editor@example-a.com`) | ✅ Full access | 🔍 View only logs generated by own session | 👁️ View global & own org loaded vectors | ✅ Upload documents / skills for own domain | ❌ No access | ❌ Hidden | 🔑 View own initial JWT requests |
| **Admin (Domain)** | Domain-bound (e.g., `admin-1@example-a.com`) | ✅ Full access | 🔍 View logs of all users in own domain | 👁️ View global & own org loaded vectors | ✅ Upload documents / skills for own domain | ✅ Full management for users in own domain | ❌ Hidden (Host container protection) | 🔑 View initial JWT requests in own domain |
| **Admin (Global)** | No domain (`admin`) | ✅ Full access | 🔍 View all system logs across all domains | 👁️ View all vectors across all tenants | ✅ Upload documents / skills (Global or domain) | ✅ Full management across all domains | ✅ Full access to Container Mgr | 🔑 View all initial JWT requests across all tenants |

- **User**: Can use the chat and view the telemetry page. Can only view logs that they generate. In the VectorDB Mgnt page, can view the list of global data and data loaded by their org, but cannot load documents.
- **Editor**: Can do everything the User can do, plus load documents and skills into the VectorDB page for their own domain.
- **Admin (Domain)** (e.g. `admin-1@example-a.com` with domain role): Can do everything the Editor can do and view logs of all users in their domain. Can manage user accounts for their domain in the "Password Mgnt & JWT" page and view initial JWT requests for users in their domain.
- **Admin (Global)** (`admin` with no domain): Global administrator able to manage everything across all domains and host containers.

### Initial Login & Multi-Tenant Credentials
1. On opening `http://localhost:8000`, a sign-in modal prompts for email credentials.
2. Default initial seed credentials across roles:
   * **Admin (Global Access):**
     * **Email / Username:** `admin` | **Password:** `admin123` | **Scope:** Full access to all documents, all tenants, and both CSV files.
   * **Tenant A (`example-a.com`):**
     * **Domain Admin:** `admin-1@example-a.com` | `password123`
     * **Editor:** `editor@example-a.com` | `password123`
     * **User:** `user@example-a.com` | `password123`
     * **Scope:** Access restricted to `example-a.com` RAG documents and `tools/data/employee_database.csv`.
   * **Tenant B (`sample-b.com`):**
     * **Domain Admin:** `admin-2@sample-b.com` | `password123`
     * **Editor:** `editor@sample-b.com` | `password123`
     * **User:** `user@sample-b.com` | `password123`
     * **Scope:** Access restricted to `sample-b.com` RAG documents and `tools/data/customer_database.csv`.
3. Click **Ok** to authenticate. A signed JWT token is issued and stored in session storage for all API interactions.

### 🗣️ Page 1: Chat & Knowledge Mgnt
* **Card Title & New Session:** The primary conversation card is named **"Chat"** and features a **"New Session"** button to its right. Clicking "New Session" clears conversational context, resets the conversation ID, clears evidence, and restores the initial welcome view.
* **Multi-Turn Conversational Context:** Conversational history from previous turns is preserved and sent in subsequent prompts, allowing the agent to remember context across queries.
* **Model Selection:** Choose from active Google AI Studio models or select **Custom Model** to specify an OpenAI-compatible endpoint.
* **Hyperparameters:** Tune `Temperature` (0.0–2.0), `Max Tokens` (default 2048), and `Max Turns` (default: 5, range 1–10).
* **Agent Selector:** Toggle between **Custom Agent** and **Google ADK Agent**.
* **Skill Selector:**
  * `Vector Store Selects` (Default): Uses ChromaDB skill matching with configurable `Skill Threshold`.
  * `LLM Selects`: Supplies all skill definitions to the model for cognitive selection.
  * Direct Skill: Forces execution of a designated skill.
* **Inspection Bubbles:** Click **Show Logs** on any completed agent response to expand step-by-step component execution bubbles (Agent, Skills, Tools, RAG, LLM).
* **Retrieved Evidence:** The right card displays the **Selected Agent** that processed the prompt, its **similarity score**, routing match status (Specialized Match vs Default Fallback), and detailed routing explanation, alongside matched procedural **Skills** and semantic **Documents**.

### 🛢️ Page 2: VectorDB Mgnt
* **Asymmetric Layout:** Populate Vector Database occupies **40% width**, and Vector Storage Status occupies **60% width**.
* **Database Type Selection:** The Populate card includes a **"Type"** dropdown with options:
  * `Documents` (default): Ingests and chunks data into the document vector database collection.
  * `Skills`: Ingests and chunks data into the skill vector database collection.
* **Role Permissions:**
  * Role "User" has read-only access (can view stored vectors from global and own org; populate controls are disabled with an alert notice).
  * Role "Editor" and "Admin" can populate documents and skills into the VectorDB page for their own domain.
* **Real-time Statistics:** Monitor total ingested document chunks, unique files, and vector DB size in MB scoped to your tenant domain.
* **Storage Status & Reset:** Inspect active document records with their authorized **Tenant Domain** (identifying the organization that stored and retains access to each document, e.g. `example-a.com`, `sample-b.com`, or `All Tenants (Admin)`), delete individual documents, or trigger a full database reset (Admin only).

### 🤖 Page 3: Agents (Agents Router Interface)
* **Horizontal Statistics Cards:** All metrics are displayed as cards arranged horizontally across the page:
  * **Registered Agents:** Total count of agents registered with the vector router.
  * **Active Agents (UP):** Count of online agents ready to receive traffic.
  * **Offline Agents (DOWN):** Count of offline agents (requests automatically skip to fallback).
  * **Routing Threshold:** Active similarity threshold percentage.
* **Configurable Routing Threshold:** Text box (`#routerThresholdInput`) allows setting the minimum Routing Threshold dynamically (default: `0.50`). When prompts match below this threshold, or if the top specialized agent is DOWN, the router falls back to the default `agents` container.
* **Registered Agents Directory:** Live status table with UP/DOWN badges, container endpoint URLs, role/type, handled query counters, status toggling, health ping, and agent deletion.
* **Dynamic & Manual Registration:** Agent containers auto-register upon startup via `POST /api/router/agents/register` or manually via the "Add New Agent" modal.
* **Test Semantic Route:** Interactive prompt simulator calculating vector embeddings and displaying real-time agent similarity rankings.

### 📊 Page 4: Telemetry
* Accessible by all authenticated users (User, Editor, Domain Admin, Global Admin).
* **Throughput & Velocity Graphs:** Track Request Throughput (prompts, responses, errors) and Token Velocity (input and output tokens) across selectable intervals (1 min, 15 min, 1 hr, 1 day) and ranges.
* **Hardware-Agnostic Latency Metrics:** View calculated Time to First Token (TTFT), Inter-Token Latency (ITL), Tokens Per Second (TPS), and Time Per Output Token (TPOT).

### 📝 Page 5: Log Viewer (Audit Logs & Events)
* **Prompt Sender in Logs:** All agent executions, chat events, and model interactions record the name of the user who sends the prompt (`user` and `domain`).
* **Role Scoping:**
  * Users and Editors view only logs that they generate.
  * Domain Admins view logs of all users in their domain.
  * Global Admin views all logs across all domains.
* **User Conversations Table:** Browse conversation sessions, user queries, agent responses, agent types, and event counts. Includes a dedicated **User / Sender** column.
* **Events for Conversation Table:** Select any conversation row to view chronologically sorted event traces with full JSON inspection.

### 🚢 Page 6: Container Mgr (Global Admin Only)
* **Access Control:** Visible and accessible strictly to the Global Admin (`admin` with no domain). Hidden for domain administrators, editors, and users to prevent unauthorized host orchestration.
* **Visual Topology Canvas:** Live drawing illustrating container interconnectivity and runtime state (light green for active, light red for stopped).
* **Interactive Node Control:** Click or right-click any container node to inspect port mappings, dependencies, and trigger `Start` or `Stop`.
* **Global Controls:** Use `Restart All` or `Shutdown All` for bulk orchestration.

### 🔑 Page 7: Password Mgnt & JWT
* **Global Refresh Control:** Click the **Refresh** button (`#btnRefreshAuth`) in the header to update all tables across both sub-tabs simultaneously.
* **Passwords Sub-Tab (Admin Only):**
  * **User Account Directory Access Control:** Administrators can manage User accounts (changing roles, toggling Active/Locked status, resetting passwords, creating new users, and deleting users). Domain Admins manage users in their domain; Global Admin manages all users.
  * **Create New User:** Clicking **Create New User** opens a popup window prompting for email/username and password with **Cancel** and **Create** buttons.
  * **User Selection & Bulk Deletion:** Each username has an individual checkbox, with a "Select All" checkbox in the column header. A **Delete Users** button next to **Create New User** is enabled only when one or more user checkboxes are checked.
  * **User Access Activity Table:** Tracks all login attempts, logouts, registration events, and password resets.
* **JWT (JSON Web Token) Sub-Tab:**
  * **Active Multi-Tenant Session & JWT Token:**
    * Displays active login email, tenant domain, permitted RAG documents, and permitted Tools CSV files.
    * Features a **Refresh** button to scan and display the active session and keys.
    * Displays the full encoded JWT token with a **Copy Token** button.
  * **JWT List (Active Tokens):**
    * Replaces the legacy services matrix. Displays all active tokens with columns: Checkbox (`[ ]`), User Name, Token Suffix, Generated Date/Time, Expiry Date/Time, and Status.
    * Includes a **Select All** checkbox in the table header.
    * **Delete Selected JWT:** Enabled when 1+ tokens are checked. Displays a confirmation popup modal before deleting/revoking tokens from the list and database.
    * **Interactive Row Filtering:** Clicking any row highlights it and filters the "JWT Activities:" table below strictly for that token/user. Clicking the row again deselects it and restores the view to all tokens.
  * **JWT Activities: Initial User Requests:**
    * Lists the usage of the JWT from the user, displaying only the initial requests initiated by the user (chat queries, document ingest/delete, logins, logouts, page views).
    * Sub-calls between internal containers are excluded to keep focus strictly on the user's primary requests.
    * Domain-scoped for Domain Admins and user-scoped for standard Users. Global Admin can view all initial user requests across tenants.
    * Fully linked with the centralized Logging Service so raw events and activities show up immediately in both the Log Viewer and JWT Activities.

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
