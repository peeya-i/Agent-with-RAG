# Walkthrough: Agents Router Fix, Multi-Turn Chat, Context Evidence & Horizontal Stats

We have resolved the `agents_router` container crash loop and completed all requested features across the Agents Router, Chat interface, and multi-turn context management.

---

## 1. Key Changes Implemented

### 🛠️ 1. Fixed `agents_router` Crash Loop
- **Root Cause**: Inside the container (`WORKDIR /app`), files are located directly at `/app/server.py`, `/app/embeddings.py`, etc. Top-level imports using `from agent_router.embeddings ...` caused `ModuleNotFoundError: No module named 'agent_router'`.
- **Fix**: Implemented dual fallback imports in [agent_router/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/server.py), [agent_router/registry.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/registry.py), and [agent_router/router.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/router.py). The container started and remained healthy:
  ```
  agents-router   Up (0.0.0.0:8004->8004/tcp)
  ```

### 📊 2. Agents Page: Horizontal Statistics Cards
- Replaced vertical stacking with a horizontal metric card grid layout (`.metric-tiles-grid` with 4 columns):
  - **🤖 Registered Agents**: Total count of registered agents.
  - **🟢 Active Agents (UP)**: Count of operational agents.
  - **🔴 Offline Agents (DOWN)**: Count of offline agents.
  - **⚡ Routing Threshold**: Configurable minimum routing threshold percentage.

### 🎯 3. Configurable Minimum Routing Threshold
- Added a dedicated text box (`#routerThresholdInput`) and **Set** button in the header of the Agents page.
- Added `GET /api/router/threshold` and `POST /api/router/threshold` to [agent_router/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/server.py) and proxied through [web_ui/app.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/app.py).
- Allows dynamic adjustment (e.g. from `0.50` to `0.65`) without container restarts. When matches fall below this threshold, the router automatically routes to the default agent.

### 🔍 4. Retrieved Context Evidence: Routed Agent & Similarity Score
- In the **Retrieved Context Evidence** right card of the Chat page:
  - Displays a top card for the **Routed Agent** showing:
    - **Agent Title & ID** (e.g. `Technical Support & DevOps Specialist`).
    - **Similarity Score** (percentage and raw float, e.g. `99.4% (0.9937)`).
    - **Routing Match Status** badge (`Specialized Match (> 50%)` vs `Default Fallback (<= 50%)`).
    - **Routing Explanation**.
  - Displays matched procedural **Skills** and **Document chunks** if any were used.

### 💬 5. Multi-Turn Context & "Chat" Card with "New Session"
- **Card Title**: Changed the card title to **"Chat"**.
- **New Session Button**: Added a **"New Session"** button to the right of "Chat" (`#btnNewChatSession`):
  - Clears `chatSessionHistory` context in memory.
  - Generates a new `conversation_id`.
  - Clears the message history and restores the welcome view with quick prompts.
  - Clears the context evidence card.
- **Context Passing**:
  - Maintained `chatSessionHistory` across turns in [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js).
  - Passed `history` payload to `/api/chat`.
  - [agents/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agents/server.py), [agents/custom_agent/custom_agent.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agents/custom_agent/custom_agent.py), and [agent_tech_support/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_tech_support/server.py) format and prepend prior turns into prompt context so subsequent prompts maintain continuity.

---

## 2. Verification Results

### Automated Unit & Integration Tests
Ran `pytest tests/`:
```
tests/test_agents_router.py .....                                        [ 35%]
tests/test_microservices.py ...s.....                                    [100%]
================== 13 passed, 1 skipped in 40.95s ===================
```

### Live Docker Cluster Status
All 9 containers are running and healthy:
```
NAMES                STATUS          PORTS
web-ui-service       Up              0.0.0.0:8000->8000/tcp
agent-tech-support   Up              0.0.0.0:8007->8007/tcp
agents-router        Up              0.0.0.0:8004->8004/tcp
agents-service       Up              0.0.0.0:8002->8002/tcp
doc-rag-service      Up              0.0.0.0:8003->8003/tcp
tools-service        Up              0.0.0.0:8005->8005/tcp
auth-service         Up              0.0.0.0:8001->8001/tcp
logging-service      Up              0.0.0.0:8006->8006/tcp
ollama-embedding     Up              0.0.0.0:11434->11434/tcp
```

### Multi-Turn Dialogue & Routing Test
Verified via API:
- **Turn 1**: Query `"The Docker container crashed with code 137 OOMKilled on startup"`:
  - Routed to: `Technical Support & DevOps Specialist` (score: `0.9937`, `is_default_fallback: False`).
- **Turn 2**: Follow-up query `"Can you give me the exact command to inspect memory limits?"` with Turn 1 in `history`:
  - Successfully acknowledged prior context and delivered targeted memory limit inspection commands.

---

## 3. Directory Modals, Card Order, "Hard Coded" Types & Container Control

### 🤖 Add New Agent Popup & Health Check
- Clicking **"Add New Agent"** opens a popup modal requesting the Agent Identifier, Display Name, Container URI, Description, Sample Prompts, and Operational Status.
- Two bottom buttons: **Cancel** and **Add**.
- Clicking **Cancel** closes the popup window and returns to the Agents page.
- Clicking **Add** registers the agent with `registration_type: "Manually Added"`, closes the modal immediately, dispatches a live Health check (`POST /api/router/agents/<id>/health`), and updates the status.

### 📐 Card Order Reordering
- In [web_ui/templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/templates/index.html), reordered cards so that the **"Test Semantic Prompt Routing (Vector Similarity)"** card is situated directly **above** the **"Registered Agents Directory & Real-time Status"** table card.

### 🏷️ Agent Types ("Hard Coded", "API Registered", "Manually Added")
- In the third column ("Role / Type") of the directory table, the agent type badge is rendered below the role:
  - **`Hard Coded`**: The default agent defined in code (`agents-default`).
  - **`API Registered`**: Specialized agent registered dynamically via API (`agent-tech-support`).
  - **`Manually Added`**: Agent registered via the Add New Agent button.

---

## 4. Add New Agent Popup Window, Tech Support RAG & LLM Logging

### 🪟 1. "Add New Agent" Popup Window Fix
- **Explicit Inline Triggers & Cache-Busting**: Added inline click handlers (`onclick="if(window.openAddAgentModal)window.openAddAgentModal();"`) in [web_ui/templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/templates/index.html) and cache-busted the script bundle with `app.js?v=20261011_03`.
- **Global Window Functions**: Exported `window.openAddAgentModal`, `window.closeAddAgentModal`, and `window.submitAddAgentModal` to global scope in [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js).
- **Parameters & URI Label**: Modal displays parameters including **URI \*** (`#inputNewAgentUrl`).
- **Bottom Buttons**: Strictly configured with **Cancel** and **Add**:
  - **Cancel**: Closes the popup window and returns to the Agents page.
  - **Add**: Validates input, registers the agent with `registration_type: "Manually Added"`, immediately closes the popup window, dispatches the health check (`POST /api/router/agents/<id>/health`), and refreshes the directory to display the live operational status.

### 📚 2. Tech Support Agent RAG Vector Store Integration
- Integrated `DOC_RAG_URL` (`http://doc_rag:8003`) into [agent_tech_support/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_tech_support/server.py).
- Upon receiving a chat query, the Tech Support Agent queries `/api/rag/query` with `document_type="document"` and logs:
  - `document_vector_query`: Outbound query to the Vector DB.
  - `received_document_vector_response`: Inbound response containing relevant document chunks.
- Retrieved documentation chunks are assembled and injected into the prompt context and returned in `retrieved_evidence["documents"]`.

### 📝 3. Tech Support Agent LLM Call & Response Logging
- Implemented Google GenAI invocation and response logging in [agent_tech_support/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_tech_support/server.py) matching the exact schema used by Custom Agent:
  - `llm_invocation`: `invoker: "Tech Support Agent"`, `recipient: "LLM"`, payload containing `model`, `prompt`, `system_instruction`, and `config`.
  - `llm_response`: `invoker: "LLM"`, `recipient: "Tech Support Agent"`, payload containing `model`, `prompt`, `system_instruction`, `response`, `response_text`, `input_tokens`, `output_tokens`, and `duration_ms`.
  - `llm_error`: Error payload if upstream generation fails during model failover.
- Verified logs recorded in the `logging` service for live conversation events.

### 🖱️ Row Click Inspection & Editing
- Clicking any row in the directory table opens the details modal.
- If the agent is **Manually Added**, its parameters (Name, URI, Description, Prompts, Status) are editable and can be saved via **Save Changes** (calling `POST /api/router/agents/<id>/update`).
- If the agent is **Hard Coded** or **API Registered**, fields are read-only with a contextual notice tag.

### 🛑 Container Stop Fix for Tech Support Agent
- Added container alias mapping (`agent_tech_support` -> `agent-tech-support`) and `find_docker_container()` in [web_ui/app.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/app.py) so clicking **"Stop Container"** in the Container Details modal cleanly locates and stops the container.

---

## 5. Agent Page Buttons & Chat Conversation ID Fixes

### 🛠️ 1. Fixed Agent Page Buttons & Trapped Modal
- **Root Cause**: In [web_ui/templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/templates/index.html), `#containerDetailModal` was missing its closing `</div>` tag. As a result, `#addAgentModal` was accidentally nested inside `#containerDetailModal`. Because `#containerDetailModal` has the class `.hidden` (`display: none !important`), `#addAgentModal` was permanently invisible regardless of whether `#btnOpenAddAgentModal` attempted to display it.
- **Fix**:
  - Closed `#containerDetailModal` properly before `#addAgentModal`.
  - Added explicit inline `onclick` triggers to all buttons on the Agents page (`#btnSetThreshold`, `#btnRefreshAgents`, `#btnOpenAddAgentModal`, `#btnTestRoute`).
  - Exported all handlers (`window.updateRoutingThreshold`, `window.loadAgentsData`, `window.openAddAgentModal`, `window.closeAddAgentModal`, `window.submitAddAgentModal`, `window.testSemanticRoute`) on `window` in [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js).

### 🔒 2. Fixed Conversation ID Hijacking Across Turns
- **Root Cause**:
  1. In [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js), `selectConversation(cid)` in the Audit Logs viewer was executing `window.currentActiveConversationId = cid;`. Whenever the user navigated to the Audit Logs page or whenever Audit Logs auto-refreshed, the active Chat conversation ID was overwritten with the selected audit log conversation ID.
  2. In [agent_tech_support/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_tech_support/server.py), the outbound query to `doc_rag` (`/api/rag/query`) did not forward `conversation_id`, causing `doc_rag` to generate a new 10-digit timestamp ID (`conv_{int(time.time())}`).
- **Fix**:
  - Created isolated state variable `activeChatConversationId` exclusively for the Chat page session.
  - Removed `window.currentActiveConversationId = cid;` from `selectConversation(cid)` so that inspecting or refreshing Audit Logs never alters the ongoing chat session.
  - Forwarded `conversation_id: conv_id` in `agent_tech_support/server.py` to `doc_rag`.
  - Enforced `res_data["conversation_id"] = conv_id` in [web_ui/app.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/app.py) and [agent_router/router.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/router.py).
  - Verified multi-turn conversations stay under the exact same conversation ID across all turns without changing.

---

## 6. Status Dropdown Removal & 30-Second Actual Status Health Check

### ❌ 1. Removed Status Dropdown from "Add New Agent" Popup
- Removed `<select id="selectNewAgentStatus">` and its container `<div class="form-group">` from `#addAgentModal` in [web_ui/templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/templates/index.html).
- The user is no longer asked to manually specify "UP" or "DOWN" when creating an agent.
- Updated `submitAddAgentModal()` and `openAddAgentModal()` in [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js):
  - Agent registration defaults initially to `"up"`.
  - Immediately dispatches an active `/health` check ping to verify the real status of the target agent and refresh the directory table.

### ⏱️ 2. Actual Status Display & 30-Second Automatic Health Checks
- **Accurate Real Status Resolution**:
  - Updated `AgentRegistry.check_health()` in [agent_router/registry.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/registry.py) to set `agent.status = "up"` on HTTP 200 and `agent.status = "down"` on unreachable / error states.
  - Added `AgentRegistry.check_all_health()` to probe all registered agents.
- **Backend 30-Second Background Checker**:
  - In [agent_router/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/server.py), launched a background daemon thread (`health_checker_thread`) that executes `registry.check_all_health()` every 30 seconds.
  - Added endpoint `POST/GET /api/router/agents/health_check_all` in `agent_router/server.py` and proxied it through [web_ui/app.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/app.py).
- **STATUS Column in Registered Agents Directory Table**:
  - Updated `statusBadge` in [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js) to display the actual live status:
    - **`🟢 UP`** (Healthy) when the agent is responding to health checks.
    - **`🔴 DOWN`** (Offline / Unreachable) with reason tooltip when unreachable or erroring.
  - Horizontal metric cards ("Active Agents", "Offline Agents") accurately reflect the actual live health state.
- **Frontend 30-Second Periodic Polling**:
  - In [web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js), configured `setInterval` to trigger `POST /api/router/agents/health_check_all` and refresh `loadAgentsData()` every 30 seconds.
  - Wired `#btnRefreshAgents` to also run the health check sweep on demand.

---

## 7. Chrome Password Prompt Fix, Manual Agent Volume Persistence & Documentation Sync

### 🛡️ 1. Chrome Password Manager Autofill Prompt Fix
- **Root Cause**: Inputs in `#addAgentModal` were not wrapped in a dedicated `<form>` and buttons lacked explicit `type="button"`, causing browsers to default them to `type="submit"`. On modal dismiss/cancel, Chrome's credential heuristic scanned the DOM, paired the un-isolated text inputs (`#inputNewAgentId`, `#inputNewAgentName`) with hidden password inputs from login/registration modals, and prompted: *"Save password for..."*.
- **Fix**:
  - Enclosed the modal body and footer inside an explicit `<form id="formAddAgent" autocomplete="off" onsubmit="event.preventDefault(); return false;">` in [web_ui/templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/templates/index.html).
  - Added `autocomplete="off"` and `data-lpignore="true"` to each input and textarea.
  - Added explicit `type="button"` to `#btnCloseAddAgentModalX`, `#btnCancelAddAgent`, and `#btnSubmitAddAgent`.
  - In `closeAddAgentModal()` ([web_ui/static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/web_ui/static/js/app.js)), added form reset logic to clear field state on close.

### 💾 2. Mounted Volume Persistence for Manually Configured Agents
- **Mounted Volume**:
  - In [docker-compose.yml](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/docker-compose.yml), mounted host directory `./agent_router/data:/app/data` to the `agents_router` container and defined `AGENTS_DATA_DIR=/app/data`.
- **Persistent Storage**:
  - Added `save_manual_agents()` and `load_manual_agents()` to `AgentRegistry` in [agent_router/registry.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/registry.py).
  - All manually configured agents (`registration_type: "Manually Added"`) are serialized to and read from `/app/data/manual_agents.json`.
- **Load Upon Starting**:
  - In `seed_default_agents()` ([agent_router/server.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/agent_router/server.py)), `registry.load_manual_agents()` automatically registers all manual agents from the JSON file on startup.
- **Entry Removal on Delete**:
  - When `unregister(agent_id)` is invoked (e.g. clicking the delete button `🗑️`), the agent is removed from memory and `save_manual_agents()` immediately updates the file, removing the entry.
- **Automated Test**:
  - Added `test_manual_agents_persistence` to [tests/test_agents_router.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/tests/test_agents_router.py) validating persistence, restart re-loading, and entry removal on deletion.

### 📄 3. Documentation Synchronization
- Synchronized [SPECIFICATIONS.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/SPECIFICATIONS.md), [SPECIFICATIONS_GEN.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/SPECIFICATIONS_GEN.md), and [README.md](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/README.md) with current architecture:
  - Added `./agent_router/data/manual_agents.json` volume persistence specifications.
  - Documented Tab 3 ("Agents Router Interface") with horizontal metric cards, routing threshold controls, actual status resolution (`🟢 UP` / `🔴 DOWN`), 30-second periodic checks, and card ordering.
  - Updated "Chat" card naming, "New Session" button, and multi-turn context passing.
  - Documented "Add New Agent" modal changes (status dropdown removed, Chrome autofill isolation).
