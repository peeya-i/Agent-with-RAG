# Telemetry Dashboard Implementation Plan

Add a comprehensive, interactive **Telemetry** page to the Agent with RAG application, positioned between **Vector DB Ingestion** and **Audit Logs & DB Explorer**, to monitor LLM model invocations, prompt/response counts, error tracking, token metrics, and time-series line graphs.

## User Review Required

> [!NOTE]
> - Chart.js has been placed locally in `static/js/chart.umd.min.js` to guarantee 100% offline air-gapped support without requiring external CDN access.
> - The top tab sequence will become:
>   1. **1. Chat**
>   2. **2. Vector DB Ingestion**
>   3. **3. Telemetry**
>   4. **4. Audit Logs & DB Explorer**
> - The existing log database `database/logs.json` will be leveraged as the source of truth for telemetry, parsing all LLM events (`google_ai_studio_gemma`, `custom_model_api`, `LLM`, etc.) for model name, prompt tokens, candidate tokens, duration, and error status.

---

## Proposed Changes

### Backend Telemetry Service & Endpoint

#### [NEW] [services/telemetry_service.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/services/telemetry_service.py)
- Create a dedicated telemetry extraction and aggregation service:
  - `get_telemetry_data(model=None, interval="15m", time_range="1d", start_date=None, end_date=None) -> Dict[str, Any]`
  - Parses `database/logs.json` for LLM invocation records.
  - Extracts model identities to populate the available model catalog.
  - Computes top summary statistics:
    - **Total Prompts**: Count of all LLM requests.
    - **Total Response**: Count of successful responses (`status == "success"`).
    - **Total Errors**: Count of error responses (`status == "error"` or exception logged).
    - **Total Input Tokens**: Sum of `prompt_token_count` / `prompt_tokens`.
    - **Total Output Tokens**: Sum of `candidates_token_count` / `completion_tokens`.
  - Discretizes events into time buckets across the selected time range (`1h`, `1d`, `week`, `month`, `custom`) based on the selected interval (`1m`, `15m`, `1h`, `1d`).
  - Formats labels and data arrays for Chart.js ingestion.

#### [MODIFY] [app.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/app.py)
- Add route `GET /api/telemetry`:
  - Accepts query parameters: `model`, `interval`, `time_range`, `start_date`, `end_date`.
  - Calls `services.telemetry_service.get_telemetry_data(...)` and returns JSON.

---

### User Interface & Templates

#### [MODIFY] [templates/index.html](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/templates/index.html)
- Include `<script src="/static/js/chart.umd.min.js"></script>` in `<head>`.
- In `<nav class="top-nav-tabs">`:
  - Insert **[📊 3. Telemetry]** button between **Vector DB Ingestion** and **Audit Logs**.
  - Renumber Audit Logs button to **[📜 4. Audit Logs & DB Explorer]**.
- Add `<section class="page-view" id="pageTelemetry" role="tabpanel">`:
  - **Top Bar Controls**:
    - Dropdown `<select id="telemetryModelSelect">` (Default: "All Models") to filter by model.
    - Button `<button id="btnRefreshTelemetry">` ("Refresh Telemetry").
  - **Top 5 Statistic Cards Grid**:
    - **Total Prompts** (`#statTotalPrompts`)
    - **Total Response** (`#statTotalResponses`)
    - **Total Errors** (`#statTotalErrors`)
    - **Total Input Tokens** (`#statTotalInputTokens`)
    - **Total Output Tokens** (`#statTotalOutputTokens`)
  - **Dual Graphs Card**:
    - Control Toolbar:
      - Aggregation/Update Interval dropdown (`#telemetryIntervalSelect`): `1 min`, `15 min` (default), `1 hr`, `1 day`.
      - Time Range dropdown (`#telemetryTimeRangeSelect`): `Last hr`, `1 day` (default), `Week`, `Month`, `Custom`.
      - Custom date container (`#telemetryCustomDates`): `telemetryStartDate` & `telemetryEndDate` calendar pickers, with "Apply" button.
    - Dual plot canvas grid:
      - **Left Plot**: Line graph of Prompts, Responses, and Errors per interval.
      - **Right Plot**: Line graph of Input Tokens and Output Tokens per interval.
  - **Educational Reference Card**:
    - Displays the requested text verbatim:
      > **Other Important Statistic not Available for Low Performance Computer:**
      > - **Time to First Token (TTFT):** The duration between a user sending a prompt and receiving the very first token. This is the most critical metric for perceived speed in streaming applications.
      > - **Inter-Token Latency (ITL):** The average time elapsed between generating each subsequent token.
      > - **Tokens Per Second (TPS):** The throughput speed of the model generation (often measured per request or aggregated across the server).
      > - **Time Per Output Token (TPOT):** The total time taken to generate the response divided by the number of output tokens.

---

### Stylesheet & Client-side Logic

#### [MODIFY] [static/css/style.css](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/static/css/style.css)
- Add styling for telemetry metrics cards (stat numbers, icons, gradient badges).
- Add dual-plot container responsive grid (two equal-width side-by-side charts on desktop, stacked on mobile).
- Add styling for the interval/range controls bar and custom date picker row.
- Add styling for the educational card with clean callout boxes and typography.

#### [MODIFY] [static/js/app.js](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/static/js/app.js)
- Extend `switchTab` to support `'pageTelemetry'`.
- Implement `loadTelemetry(isInitial=false)`:
  - Fetches `/api/telemetry` with active filters (`model`, `interval`, `time_range`, `start_date`, `end_date`).
  - Populates the model dropdown dynamically on initial load while preserving selection.
  - Updates the 5 summary stat values.
  - Initializes or updates the dual Chart.js instances (`requestsChart` and `tokensChart`) with smooth gradients and custom tooltips.
- Add event handlers:
  - `handleTelemetryModelChange()`
  - `handleTelemetryIntervalChange()`
  - `handleTelemetryTimeRangeChange()` (shows/hides `#telemetryCustomDates`)
  - `applyCustomDates()`
  - `refreshTelemetry()`

---

### Verification Plan

#### Automated Tests
- Create automated unit and integration tests in [tests/test_telemetry.py](file:///home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/tests/test_telemetry.py):
  1. `test_telemetry_endpoint_structure`: Verify `GET /api/telemetry` returns 200 with `models`, `summary`, and `time_series`.
  2. `test_telemetry_model_filtering`: Verify filtering by a specific model vs `all`.
  3. `test_telemetry_interval_and_range`: Test combinations of `1m`, `15m`, `1h`, `1d` and `1h`, `1d`, `week`, `month`, `custom`.
  4. `test_html_telemetry_elements`: Verify DOM elements, 4 tabs in correct order, dropdowns, canvas elements, and exact educational card text.
- Run complete test suites:
  - `.venv/bin/python -m unittest tests/test_telemetry.py`
  - `.venv/bin/python -m unittest tests/test_private_rag.py`

#### Live Verification
- Query `http://127.0.0.1:8005/` in the browser or via curl:
  - Verify `GET /api/telemetry` returns data.
  - Confirm tab switching between Ingestion, Telemetry, and Audit Logs.
  - Verify charts render smoothly.
