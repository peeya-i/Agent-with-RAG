/**
 * Agent With RAG - Web Application Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global State
  let currentActiveTab = 'page-chat';
  let activeEmbedderModel = 'bge-m3';
  let availableModelsData = [];
  let chartThroughputInstance = null;
  let chartTokensInstance = null;
  let selectedConversationId = null;
  let currentConversationsCache = [];
  let currentEventsCache = [];

  // Helper: Format ISO timestamp or epoch seconds to local time string (YYYY-MM-DD HH:mm:ss)
  function formatToLocalTime(tsInput) {
    if (!tsInput) return '-';
    try {
      const d = (typeof tsInput === 'number')
        ? new Date(tsInput > 1e11 ? tsInput : tsInput * 1000)
        : new Date(tsInput);
      if (isNaN(d.getTime())) return String(tsInput);
      const pad = n => String(n).padStart(2, '0');
      const year = d.getFullYear();
      const month = pad(d.getMonth() + 1);
      const day = pad(d.getDate());
      const hours = pad(d.getHours());
      const minutes = pad(d.getMinutes());
      const seconds = pad(d.getSeconds());
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
      return String(tsInput);
    }
  }

  // DOM Elements - Navigation & Header
  const navTabs = document.querySelectorAll('.nav-tab');
  const pageViews = document.querySelectorAll('.page-view');
  const statusDot = document.getElementById('statusDot');
  const statusSummary = document.getElementById('statusSummary');
  const tooltipAgent = document.getElementById('tooltipAgent');
  const tooltipOllama = document.getElementById('tooltipOllama');
  const tooltipEmbedder = document.getElementById('tooltipEmbedder');
  const tooltipVector = document.getElementById('tooltipVector');
  const tooltipLlm = document.getElementById('tooltipLlm');

  // DOM Elements - Shutdown Modal
  const btnShutdown = document.getElementById('btnShutdown');
  const shutdownModal = document.getElementById('shutdownModal');
  const shutdownConfirmInput = document.getElementById('shutdownConfirmInput');
  const btnCancelShutdown = document.getElementById('btnCancelShutdown');
  const btnConfirmShutdown = document.getElementById('btnConfirmShutdown');

  // DOM Elements - Page 1 (Chat)
  const chatModel = document.getElementById('chatModel');
  const customEndpointBox = document.getElementById('customEndpointBox');
  const customEndpoint = document.getElementById('customEndpoint');
  const chatTemperature = document.getElementById('chatTemperature');
  const chatMaxTokens = document.getElementById('chatMaxTokens');
  const agentChoice = document.getElementById('agentChoice');
  const chatMaxTurns = document.getElementById('chatMaxTurns');
  const chatRagChunks = document.getElementById('chatRagChunks');
  const chatSkills = document.getElementById('chatSkills');
  const skillThresholdBox = document.getElementById('skillThresholdBox');
  const chatSkillThreshold = document.getElementById('chatSkillThreshold');
  const docThresholdInput = document.getElementById('docThresholdInput');
  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');
  const btnSendMessage = document.getElementById('btnSendMessage');
  const evidenceContainer = document.getElementById('evidenceContainer');

  // DOM Elements - Page 2 (Ingestion)
  const embedderSelect = document.getElementById('embedderSelect');
  const btnUpdateSkills = document.getElementById('btnUpdateSkills');
  const statChunksCount = document.getElementById('statChunksCount');
  const statDocsCount = document.getElementById('statDocsCount');
  const statDbSize = document.getElementById('statDbSize');
  const ingestSourceInput = document.getElementById('ingestSourceInput');
  const btnToggleChunking = document.getElementById('btnToggleChunking');
  const chunkingContent = document.getElementById('chunkingContent');
  const inputChunkSize = document.getElementById('inputChunkSize');
  const inputChunkOverlap = document.getElementById('inputChunkOverlap');
  const btnPopulateDb = document.getElementById('btnPopulateDb');
  const ingestSpinner = document.getElementById('ingestSpinner');
  const btnResetDb = document.getElementById('btnResetDb');
  const storageStatusBanner = document.getElementById('storageStatusBanner');
  const ingestedDocsTbody = document.getElementById('ingestedDocsTbody');
  const availableModelsTbody = document.getElementById('availableModelsTbody');

  // DOM Elements - Change Model Modal
  const changeModelModal = document.getElementById('changeModelModal');
  const modalTargetModelName = document.getElementById('modalTargetModelName');
  const changeModelConfirmInput = document.getElementById('changeModelConfirmInput');
  const btnCancelChangeModel = document.getElementById('btnCancelChangeModel');
  const btnConfirmChangeModel = document.getElementById('btnConfirmChangeModel');
  let pendingModelSwitch = null;

  // DOM Elements - Page 3 (Telemetry)
  const telemetryModelFilter = document.getElementById('telemetryModelFilter');
  const btnRefreshTelemetry = document.getElementById('btnRefreshTelemetry');
  const telTotalChat = document.getElementById('telTotalChat');
  const telTotalPrompts = document.getElementById('telTotalPrompts');
  const telTotalResponses = document.getElementById('telTotalResponses');
  const telTotalErrors = document.getElementById('telTotalErrors');
  const telTotalInTokens = document.getElementById('telTotalInTokens');
  const telTotalOutTokens = document.getElementById('telTotalOutTokens');
  const telIntervalSelect = document.getElementById('telIntervalSelect');
  const telRangeSelect = document.getElementById('telRangeSelect');
  const customDateBoxes = document.getElementById('customDateBoxes');
  const telStartDate = document.getElementById('telStartDate');
  const telEndDate = document.getElementById('telEndDate');
  const valTtft = document.getElementById('valTtft');
  const valItl = document.getElementById('valItl');
  const valTps = document.getElementById('valTps');
  const valTpot = document.getElementById('valTpot');

  // DOM Elements - Page 4 (Audit Log)
  const btnClearLogs = document.getElementById('btnClearLogs');
  const btnRefreshLogs = document.getElementById('btnRefreshLogs');
  const auditTotalPrompts = document.getElementById('auditTotalPrompts');
  const auditModelCalls = document.getElementById('auditModelCalls');
  const auditOllamaEmbeds = document.getElementById('auditOllamaEmbeds');
  const auditAvgLatency = document.getElementById('auditAvgLatency');
  const conversationsTbody = document.getElementById('conversationsTbody');
  const eventsTbody = document.getElementById('eventsTbody');
  const selectedConvBadge = document.getElementById('selectedConvBadge');
  const clearLogsModal = document.getElementById('clearLogsModal');
  const btnCancelClearLogs = document.getElementById('btnCancelClearLogs');
  const btnConfirmClearLogs = document.getElementById('btnConfirmClearLogs');

  // DOM Elements - Event Detail Modal
  const eventDetailModal = document.getElementById('eventDetailModal');
  const eventModalMeta = document.getElementById('eventModalMeta');
  const eventModalPromptContainer = document.getElementById('eventModalPromptContainer');
  const eventModalResponseContainer = document.getElementById('eventModalResponseContainer');
  const eventModalJson = document.getElementById('eventModalJson');
  const btnCloseEventModal = document.getElementById('btnCloseEventModal');
  const btnCloseEventModal2 = document.getElementById('btnCloseEventModal2');
  const btnCopyJson = document.getElementById('btnCopyJson');

  // ---------------------------------------------------------------------------
  // Tab Navigation (Single Consolidated Handler)
  // ---------------------------------------------------------------------------
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-target');
      if (!targetId) return;

      navTabs.forEach(t => t.classList.remove('active'));
      pageViews.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPage = document.getElementById(targetId);
      if (targetPage) targetPage.classList.add('active');

      currentActiveTab = targetId;

      const label = tab.querySelector('.tab-label') ? tab.querySelector('.tab-label').textContent : targetId;
      if (typeof logPageView === 'function') logPageView(label);

      // Automatically reload view data when browsing into page
      if (targetId === 'page-telemetry') {
        loadTelemetryData();
      } else if (targetId === 'page-audit') {
        loadAuditLogs();
      } else if (targetId === 'page-ingest') {
        if (typeof loadIngestionData === 'function') loadIngestionData();
        if (typeof loadIngestionStats === 'function') loadIngestionStats();
      } else if (targetId === 'page-agents') {
        if (typeof loadAgentsData === 'function') loadAgentsData();
      } else if (targetId === 'page-containers') {
        if (typeof loadContainers === 'function') loadContainers();
      } else if (targetId === 'page-auth') {
        if (typeof loadUsers === 'function') loadUsers();
        if (typeof loadUserActivity === 'function') loadUserActivity();
        if (typeof refreshActiveSessionJwt === 'function') refreshActiveSessionJwt();
        if (typeof loadJwtTokens === 'function') loadJwtTokens();
        if (typeof loadJwtActivities === 'function') loadJwtActivities();
      }
    });
  });

  // ---------------------------------------------------------------------------
  // System Health Monitoring
  // ---------------------------------------------------------------------------
  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error('Health check failed');
      const data = await res.json();
      
      const s = data.services || {};
      tooltipAgent.textContent = s.agent || 'Unknown';
      tooltipOllama.textContent = `${s.ollama || 'Offline'} (${s.ollama_active_model || 'bge-m3'})`;
      tooltipEmbedder.textContent = s.ollama_active_model || 'bge-m3';
      tooltipVector.textContent = s.vector_store || 'Disconnected';
      tooltipLlm.textContent = s.llm_provider || 'Not Configured';

      if (data.status === 'Online') {
        statusDot.className = 'status-dot online';
        statusSummary.textContent = `Agent: Online (${s.ollama_active_model || 'bge-m3'})`;
      } else if (data.status === 'Degraded') {
        statusDot.className = 'status-dot degraded';
        statusSummary.textContent = 'Agent: Degraded';
      } else {
        statusDot.className = 'status-dot offline';
        statusSummary.textContent = `Agent: ${data.status}`;
      }
    } catch (e) {
      statusDot.className = 'status-dot offline';
      statusSummary.textContent = 'Agent: Offline';
    }
  }

  // Periodic health check every 5 seconds
  checkHealth();
  setInterval(checkHealth, 5000);

  // ---------------------------------------------------------------------------
  // Shutdown Confirmation Flow
  // ---------------------------------------------------------------------------
  btnShutdown.addEventListener('click', () => {
    shutdownConfirmInput.value = '';
    btnConfirmShutdown.disabled = true;
    shutdownModal.classList.remove('hidden');
    shutdownConfirmInput.focus();
  });

  shutdownConfirmInput.addEventListener('input', () => {
    btnConfirmShutdown.disabled = (shutdownConfirmInput.value.trim() !== 'Shutdown the services');
  });

  btnCancelShutdown.addEventListener('click', () => {
    shutdownModal.classList.add('hidden');
  });

  btnConfirmShutdown.addEventListener('click', async () => {
    btnConfirmShutdown.disabled = true;
    btnConfirmShutdown.textContent = 'Shutting down...';
    try {
      await fetch('/api/shutdown', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmation: 'Shutdown the services', phrase: 'Shutdown the services' }),
      });
      document.body.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;background:#0a0e17;color:#f1f5f9;font-family:sans-serif;">
          <h2 style="margin-bottom:1rem;color:#f87171;">Application & Services Terminated</h2>
          <p style="color:#94a3b8;">All services started by Agent-with-RAG have been safely shut down. You may close this tab.</p>
        </div>
      `;
    } catch (e) {
      alert('Shutdown initiated.');
    }
  });

  // ---------------------------------------------------------------------------
  // Page 1: Chat Initialization & Logic
  // ---------------------------------------------------------------------------
  async function loadModelsAndSkills() {
    try {
      // 1. Fetch LLM models
      const mRes = await fetch('/api/models');
      if (mRes.ok) {
        const mData = await mRes.json();
        availableModelsData = mData.models || [];
        chatModel.innerHTML = '';

        const defModel = mData.default || mData.default_model;
        availableModelsData.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `${m.id} (Max tokens: ${m.max_output_tokens || m.output_token_limit || 4096})`;
          if (m.id === defModel) {
            opt.selected = true;
          }
          chatModel.appendChild(opt);
        });

        // Add Custom Model option
        const customOpt = document.createElement('option');
        customOpt.value = 'Custom Model';
        customOpt.textContent = 'Custom Model (HTTP Endpoint)';
        chatModel.appendChild(customOpt);

        updateTokenConstraints();
      }

      // 2. Fetch Skills
      const sRes = await fetch('/api/skills');
      if (sRes.ok) {
        const sData = await sRes.json();
        const skillsList = sData.skills || [];
        
        // Reset skills dropdown options preserving Vector Store Selects and LLM Selects
        chatSkills.innerHTML = `
          <option value="Vector Store Selects" selected>Vector Store Selects (Default)</option>
          <option value="LLM Selects">LLM Selects</option>
        `;
        skillsList.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.name;
          opt.textContent = `Skill: ${s.name}`;
          chatSkills.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Failed to load models or skills:', e);
    }
  }

  function updateTokenConstraints() {
    const selected = chatModel.value;
    if (selected === 'Custom Model') {
      customEndpointBox.classList.remove('hidden');
      chatMaxTokens.max = 32768;
    } else {
      customEndpointBox.classList.add('hidden');
      const found = availableModelsData.find(m => m.id === selected);
      if (found) {
        chatMaxTokens.max = found.output_token_limit;
        if (parseInt(chatMaxTokens.value) > found.output_token_limit) {
          chatMaxTokens.value = found.output_token_limit;
        }
      }
    }
  }

  chatModel.addEventListener('change', updateTokenConstraints);

  // Skill mode selection handler
  chatSkills.addEventListener('change', () => {
    if (chatSkills.value === 'Vector Store Selects' || chatSkills.value === 'Vector Store') {
      skillThresholdBox.classList.remove('hidden');
    } else {
      skillThresholdBox.classList.add('hidden');
    }
  });

  // Quick prompt chips
  document.querySelectorAll('.btn-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      chatInput.value = btn.getAttribute('data-prompt');
      chatInput.focus();
    });
  });

  // Conversational session history and router metadata state
  let chatSessionHistory = [];
  let lastRouterMetadata = null;

  // New Session button to clear context and start new chat
  const btnNewChatSession = document.getElementById('btnNewChatSession');
  if (btnNewChatSession) {
    btnNewChatSession.addEventListener('click', () => {
      chatSessionHistory = [];
      lastRouterMetadata = null;
      window.currentActiveConversationId = 'conv_' + Date.now();
      selectedConversationId = window.currentActiveConversationId;
      chatMessages.innerHTML = `
        <div class="chat-welcome">
          <div class="welcome-icon">💡</div>
          <h3>AI Agent with RAG Ready</h3>
          <p>Ask a question about the weather, personnel records, stock movements, or search our private knowledge documents.</p>
          <div class="quick-prompts">
            <button class="btn-chip" data-prompt="What is the current weather and local time in Tokyo?">🌤️ Weather in Tokyo</button>
            <button class="btn-chip" data-prompt="Find Lucas Dubois in the person registry and show his job title.">👤 Lucas Dubois</button>
            <button class="btn-chip" data-prompt="Which stocks have the highest percentage increase today?">📈 Top Gainers</button>
            <button class="btn-chip" data-prompt="What is Agentic RAG and how does it compare to classic RAG?">📚 Agentic RAG</button>
          </div>
        </div>
      `;
      chatMessages.querySelectorAll('.btn-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          chatInput.value = btn.getAttribute('data-prompt');
          sendMessage();
        });
      });
      renderEvidence({}, null);
      chatInput.value = '';
      chatInput.focus();
    });
  }

  // Chat message sending
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  btnSendMessage.addEventListener('click', sendMessage);

  async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = '';
    const welcome = chatMessages.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // 1. Append User Message Bubble
    appendUserMessage(text);

    // Track user message in conversational session history
    chatSessionHistory.push({ role: 'user', content: text });

    // 2. Append Pending Agent Bubble
    const pendingAgentBubble = appendPendingAgentBubble();
    btnSendMessage.disabled = true;

    try {
      const isCustomModel = (chatModel.value || '').toLowerCase().includes('custom');
      const activeConvId = window.currentActiveConversationId || ('conv_' + Date.now());
      window.currentActiveConversationId = activeConvId;

      const payload = {
        message: text,
        conversation_id: activeConvId,
        history: chatSessionHistory.slice(-10), // Pass multi-turn context to next prompt
        agent: agentChoice.value,
        model: chatModel.value,
        temperature: parseFloat(chatTemperature.value) || 0.7,
        max_tokens: parseInt(chatMaxTokens.value) || 2048,
        max_turns: parseInt(chatMaxTurns.value) || 5,
        rag_chunks: parseInt(chatRagChunks.value) || 5,
        skill_mode: chatSkills.value,
        skill_threshold: parseFloat(chatSkillThreshold.value) || 0.2,
        doc_threshold: parseFloat(docThresholdInput.value) || 0.3,
        custom_endpoint: isCustomModel ? customEndpoint.value.trim() : null,
      };

      const jwtToken = sessionStorage.getItem('jwtToken') || '';
      const chatHeaders = { 'Content-Type': 'application/json' };
      if (jwtToken) {
        chatHeaders['Authorization'] = `Bearer ${jwtToken}`;
        payload.jwt_token = jwtToken;
      }

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: chatHeaders,
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Server error processing message.');

      // Track assistant response in session history
      if (data.response) {
        chatSessionHistory.push({ role: 'model', content: data.response });
      }

      // Update pending bubble with full response and detail box
      updateAgentBubble(pendingAgentBubble, data);

      if (data.conversation_id) {
        window.currentActiveConversationId = data.conversation_id;
        selectedConversationId = data.conversation_id;
      }

      // Track router metadata if returned
      if (data.router_metadata) {
        lastRouterMetadata = data.router_metadata;
      }

      // Render retrieved context evidence in Right Card with selected Agent & similarity score
      if (data.retrieved_evidence && (data.retrieved_evidence.skills?.length || data.retrieved_evidence.documents?.length)) {
        renderEvidence(data.retrieved_evidence, data.router_metadata || lastRouterMetadata);
      } else if (data.conversation_id) {
        await loadContextEvidence(data.conversation_id, data.router_metadata || lastRouterMetadata);
      } else {
        renderEvidence({}, data.router_metadata || lastRouterMetadata);
      }

    } catch (err) {
      pendingAgentBubble.querySelector('.message-bubble').textContent = `Error: ${err.message}`;
      pendingAgentBubble.querySelector('.message-bubble').style.borderColor = 'rgba(239, 68, 68, 0.4)';
    } finally {
      btnSendMessage.disabled = false;
      chatInput.focus();
    }
  }

  function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendPendingAgentBubble() {
    const row = document.createElement('div');
    row.className = 'message-row agent';
    row.innerHTML = `
      <div class="message-bubble" style="color:var(--text-muted);">
        <span class="spinner-icon">⏳</span> Reasoning and executing tools...
      </div>
    `;
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return row;
  }

  function updateAgentBubble(row, data) {
    const bubble = row.querySelector('.message-bubble');
    bubble.innerHTML = formatMarkdownText(data.response || '(No response text)');

    // Display Agents Router decision badge if router metadata present
    if (data.router_metadata) {
      const rm = data.router_metadata;
      const routerBadge = document.createElement('div');
      routerBadge.style.cssText = 'font-size:0.75rem; color:#94a3b8; margin-top:8px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.1); display:flex; align-items:center; flex-wrap:wrap; gap:6px;';
      routerBadge.innerHTML = `<span style="color:#38bdf8;">🔀 Agents Router:</span> <strong>${escapeHtml(rm.routed_agent_name || rm.routed_agent_id)}</strong> ` +
        (rm.similarity_score > 0 ? `<span class="badge" style="background:#1e293b; color:#34d399; font-size:0.7rem; font-weight:600;">${Math.round(rm.similarity_score * 100)}% Match</span>` : '') +
        (rm.is_default_fallback ? `<span class="badge" style="background:#065f46; color:#a7f3d0; font-size:0.7rem;">Default Fallback (&le; 50%)</span>` : `<span class="badge" style="background:#581c87; color:#e9d5ff; font-size:0.7rem;">Specialized (&gt; 50%)</span>`);
      bubble.appendChild(routerBadge);
    }

    // Create Detail Box with anchored "Show Logs" button
    const detailBox = document.createElement('div');
    detailBox.className = 'agent-detail-box';

    const steps = data.steps || [];
    let bubblesHtml = '';

    steps.forEach(st => {
      const compClass = (st.component || 'agent').toLowerCase();
      bubblesHtml += `
        <div class="step-bubble ${compClass}" title="${escapeHtml(st.title)}">
          <span>${st.icon || '🔹'}</span>
          <span>${escapeHtml(st.component)}</span>
          <span class="elapsed">${st.elapsed_ms || 0}ms</span>
        </div>
      `;
    });

    let logsHtml = '';
    steps.forEach(st => {
      logsHtml += `
        <div class="step-log-item">
          <strong>${st.icon || '🔹'} [${escapeHtml(st.component)}] ${escapeHtml(st.title)}</strong> (${st.elapsed_ms || 0}ms)<br>
          <span style="color:var(--text-muted);">${escapeHtml(st.summary || '')}</span>
          <pre style="margin-top:4px;white-space:pre-wrap;color:#93c5fd;">${escapeHtml(st.logs || '')}</pre>
        </div>
      `;
    });

    detailBox.innerHTML = `
      <div class="detail-box-header">
        <div class="component-bubbles-row">${bubblesHtml}</div>
        <button class="btn-show-logs">Show Logs</button>
      </div>
      <div class="detail-box-content">${logsHtml || '<p>No intermediate step logs recorded.</p>'}</div>
    `;

    // Toggle expand / collapse on click
    const btnShowLogs = detailBox.querySelector('.btn-show-logs');
    const detailContent = detailBox.querySelector('.detail-box-content');

    btnShowLogs.addEventListener('click', () => {
      const isExpanded = detailContent.classList.contains('expanded');
      if (isExpanded) {
        detailContent.classList.remove('expanded');
        btnShowLogs.textContent = 'Show Logs';
      } else {
        detailContent.classList.add('expanded');
        btnShowLogs.textContent = 'Hide Logs';
      }
    });

    row.appendChild(detailBox);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function renderEvidence(evidence, routerMeta) {
    if (!evidence) evidence = {};
    if (evidence.retrieved_evidence) evidence = evidence.retrieved_evidence;
    let skills = evidence.skills || [];
    let docs = evidence.documents || [];

    // Fallback: if flat evidence array is provided instead of skills/documents
    if (skills.length === 0 && docs.length === 0 && Array.isArray(evidence.evidence) && evidence.evidence.length > 0) {
      evidence.evidence.forEach(item => {
        if (item.category === 'Skill') {
          skills.push({
            name: item.title,
            similarity: item.score,
            description: item.content
          });
        } else {
          const docName = (item.title || '').split(' (Chunk')[0] || 'Document';
          let d = docs.find(x => x.doc_name === docName);
          if (!d) {
            d = { doc_name: docName, highest_similarity: item.score, chunks: [] };
            docs.push(d);
          }
          if (item.score > d.highest_similarity) d.highest_similarity = item.score;
          d.chunks.push({ index: 0, similarity: item.score, text: item.content });
        }
      });
    }

    if (!routerMeta && lastRouterMetadata) {
      routerMeta = lastRouterMetadata;
    }

    if (skills.length === 0 && docs.length === 0 && !routerMeta) {
      evidenceContainer.innerHTML = `
        <div class="empty-placeholder">
          <span class="empty-icon">📂</span>
          <p>No vector store context retrieved for this conversation.</p>
        </div>
      `;
      return;
    }

    let html = '';

    // Render Router Selection Evidence if routerMeta is available
    if (routerMeta) {
      const scorePct = routerMeta.similarity_score !== undefined && routerMeta.similarity_score !== null
        ? `${(routerMeta.similarity_score * 100).toFixed(1)}%` 
        : 'N/A';
      const isDefault = Boolean(routerMeta.is_default_fallback);
      const threshVal = typeof routerMeta.threshold === 'number' ? (routerMeta.threshold * 100).toFixed(0) : '50';
      const statusLabel = isDefault 
        ? `Default Fallback (≤ ${threshVal}%)` 
        : `Specialized Match (> ${threshVal}%)`;
      const badgeStyle = isDefault 
        ? 'background:#065f46; color:#a7f3d0; border:1px solid #10b981;' 
        : 'background:#581c87; color:#e9d5ff; border:1px solid #a855f7;';

      html += `
        <div class="evidence-doc-group" style="border: 1px solid rgba(56, 189, 248, 0.4); background: rgba(15, 23, 42, 0.75); margin-bottom: 14px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
          <div class="evidence-doc-header" style="background: rgba(56, 189, 248, 0.12); padding: 8px 12px; border-bottom: 1px solid rgba(56, 189, 248, 0.25);">
            <div class="evidence-doc-title" style="display: flex; align-items: center; gap: 7px;">
              <span style="font-size: 1.15rem;">🤖</span>
              <strong style="color: #38bdf8; font-size: 0.88rem;">Routed Agent: ${escapeHtml(routerMeta.routed_agent_name || routerMeta.routed_agent_id || 'Agent')}</strong>
            </div>
            <span class="similarity-badge" style="background: #0284c7; color: #ffffff; font-weight: 700; padding: 2px 8px; font-size: 0.75rem;">
              ${scorePct} Match
            </span>
          </div>
          <div class="evidence-doc-body" style="padding: 10px 12px; font-size: 0.8rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="color: #94a3b8; font-size: 0.75rem;">Routing Match Status:</span>
              <span class="badge" style="${badgeStyle} font-size: 0.72rem; font-weight: 600; padding: 2px 8px;">${statusLabel}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.75rem; color: #94a3b8;">
              <span>Similarity Score: <strong style="color: #34d399; font-family: var(--font-mono);">${routerMeta.similarity_score !== undefined ? Number(routerMeta.similarity_score).toFixed(4) : '0.0000'}</strong></span>
              <span>Min Routing Threshold: <strong style="color: #38bdf8; font-family: var(--font-mono);">${(routerMeta.threshold || 0.50).toFixed(2)}</strong></span>
            </div>
            ${routerMeta.explanation ? `<div style="color: #cbd5e1; font-style: italic; font-size: 0.75rem; background: rgba(0,0,0,0.3); padding: 6px 10px; border-radius: 4px; border-left: 2px solid #38bdf8; margin-top: 4px;">${escapeHtml(routerMeta.explanation)}</div>` : ''}
          </div>
        </div>
      `;
    }

    // Render Skills evidence
    if (skills.length > 0) {
      html += `
        <div class="evidence-doc-group">
          <div class="evidence-doc-header">
            <div class="evidence-doc-title"><span>⚡</span> Skills Vector Store Matches</div>
            <span class="similarity-badge">${skills.length} matched</span>
          </div>
          <div class="evidence-doc-body">
            ${skills.map(s => {
              const scoreDisplay = typeof s.similarity === 'number' ? s.similarity.toFixed(4) : (s.similarity || '0.0000');
              return `
                <div class="evidence-chunk-item">
                  <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                    <strong style="color:#fde047;">${escapeHtml(s.name)}</strong>
                    <span style="color:var(--text-muted);font-size:0.75rem;">Score: ${scoreDisplay}</span>
                  </div>
                  <div style="color:var(--text-secondary);font-size:0.75rem;">${escapeHtml(s.description || '')}</div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }

    // Render Documents evidence grouped by document
    if (docs.length > 0) {
      docs.forEach(doc => {
        const chunks = doc.chunks || [];
        const topScore = typeof doc.highest_similarity === 'number' ? doc.highest_similarity.toFixed(4) : (doc.highest_similarity || '0.0000');
        html += `
          <div class="evidence-doc-group">
            <div class="evidence-doc-header">
              <div class="evidence-doc-title"><span>📄</span> ${escapeHtml(doc.doc_name)}</div>
              <span class="similarity-badge">Top Match: ${topScore}</span>
            </div>
            <div class="evidence-doc-body">
              ${chunks.map(ch => {
                const chunkScore = typeof ch.similarity === 'number' ? ch.similarity.toFixed(4) : (ch.similarity || '0.0000');
                return `
                  <div class="evidence-chunk-item">
                    <div style="display:flex;justify-content:space-between;margin-bottom:3px;font-size:0.72rem;color:var(--text-muted);">
                      <span>Chunk #${ch.index !== undefined ? ch.index : 0}</span>
                      <span>Similarity: ${chunkScore}</span>
                    </div>
                    <div>${escapeHtml(ch.text)}</div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      });
    }

    if (skills.length === 0 && docs.length === 0 && routerMeta) {
      html += `
        <div style="text-align: center; color: var(--text-muted); font-size: 0.78rem; padding: 10px 0; border-top: 1px dashed rgba(255,255,255,0.1);">
          No Skills or Documents retrieved for this turn.
        </div>
      `;
    }

    evidenceContainer.innerHTML = html;
  }

  // ---------------------------------------------------------------------------
  // Page 2: Ingestion Logic
  // ---------------------------------------------------------------------------
  async function loadIngestionData() {
    try {
      const jwtToken = sessionStorage.getItem('jwtToken') || '';
      const vHeaders = jwtToken ? { 'Authorization': `Bearer ${jwtToken}` } : {};

      // 1. Stats
      const sRes = await fetch('/api/vectordb/stats', { headers: vHeaders });
      if (sRes.ok) {
        const sData = await sRes.json();
        statChunksCount.textContent = (sData.total_chunks !== undefined ? sData.total_chunks : (sData.chunks_count || 0));
        statDocsCount.textContent = (sData.total_documents !== undefined ? sData.total_documents : (sData.count_documents || sData.documents_count || 0));
        statDbSize.textContent = sData.db_size_mb || '0.0';
        activeEmbedderModel = sData.active_model || 'bge-large:latest';
      }

      // 2. Ingested Docs
      const dRes = await fetch('/api/vectordb/documents', { headers: vHeaders });
      if (dRes.ok) {
        const dData = await dRes.json();
        const docs = dData.documents || [];
        if (docs.length === 0) {
          ingestedDocsTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No documents or skills ingested.</td></tr>`;
        } else {
          ingestedDocsTbody.innerHTML = docs.map(d => {
            const name = typeof d === 'string' ? d : (d.doc_name || d.name || 'Unknown');
            const type = (typeof d === 'object' && d.type) ? d.type : (name.endsWith('-skill') ? 'Skill' : 'Document');
            const chunks = (typeof d === 'object' && d.chunk_count !== undefined) ? d.chunk_count : 1;
            const chars = (typeof d === 'object' && d.total_chars !== undefined) ? Number(d.total_chars) : 0;
            const domain = (typeof d === 'object' && d.domain)
              ? d.domain
              : (type === 'Skill' ? 'Global (All)' : 'All Tenants (Admin)');
            const typeBadge = type === 'Skill'
              ? '<span class="badge" style="background:#065f46;color:#6ee7b7;font-size:0.75rem;">Skill</span>'
              : '<span class="badge" style="background:#1e3a8a;color:#93c5fd;font-size:0.75rem;">Document</span>';
            const domainBadge = domain === 'example-a.com'
              ? `<span class="badge" style="background:#0f172a;border:1px solid #38bdf8;color:#38bdf8;font-size:0.75rem;padding:2px 8px;border-radius:4px;font-family:monospace;">${escapeHtml(domain)}</span>`
              : (domain === 'sample-b.com'
                ? `<span class="badge" style="background:#0f172a;border:1px solid #a855f7;color:#c084fc;font-size:0.75rem;padding:2px 8px;border-radius:4px;font-family:monospace;">${escapeHtml(domain)}</span>`
                : `<span class="badge" style="background:#0f172a;border:1px solid #10b981;color:#34d399;font-size:0.75rem;padding:2px 8px;border-radius:4px;font-family:monospace;">${escapeHtml(domain)}</span>`);
            return `
            <tr>
              <td>${typeBadge}</td>
              <td><strong>${escapeHtml(name)}</strong></td>
              <td>${domainBadge}</td>
              <td>${chunks}</td>
              <td>${chars.toLocaleString()}</td>
              <td>
                <button class="btn-table-delete" data-doc="${escapeHtml(name)}" data-type="${escapeHtml(type.toLowerCase())}">Delete</button>
              </td>
            </tr>
          `;
          }).join('');

          // Bind delete buttons
          ingestedDocsTbody.querySelectorAll('.btn-table-delete').forEach(btn => {
            btn.addEventListener('click', async () => {
              const docName = btn.getAttribute('data-doc');
              const docType = btn.getAttribute('data-type') || 'document';
              if (confirm(`Delete ${docType} '${docName}' from vector store?`)) {
                await fetch(`/api/vectordb/document?doc_name=${encodeURIComponent(docName)}&type=${encodeURIComponent(docType)}`, { method: 'DELETE' });
                loadIngestionData();
              }
            });
          });
        }
      }

      // 3. Models
      const mRes = await fetch('/api/vectordb/models');
      if (mRes.ok) {
        const mData = await mRes.json();
        const models = mData.models || [];
        
        // Update Embedder Select dropdown
        embedderSelect.innerHTML = '';
        models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = `${m.name} (${m.status})`;
          if (m.is_active) opt.selected = true;
          embedderSelect.appendChild(opt);
        });

        // Update Models Table
        availableModelsTbody.innerHTML = models.map(m => `
          <tr>
            <td><strong>${escapeHtml(m.name)}</strong></td>
            <td>${m.dimensions}</td>
            <td>${m.context_window}</td>
            <td>${escapeHtml(m.size)}</td>
            <td>${escapeHtml(m.description)}</td>
            <td>
              <span class="status-badge ${m.is_active ? 'active' : (m.is_installed ? 'installed' : 'available')}">
                ${m.status}
              </span>
            </td>
          </tr>
        `).join('');
      }
    } catch (e) {
      console.error('Failed to load ingestion data:', e);
    }
  }

  // Sample URLs click
  document.querySelectorAll('.btn-sample-url, .btn-sample_url').forEach(btn => {
    btn.addEventListener('click', () => {
      ingestSourceInput.value = btn.getAttribute('data-url');
      ingestSourceInput.focus();
    });
  });

  // Collapsible toggle
  btnToggleChunking.addEventListener('click', () => {
    chunkingContent.classList.toggle('hidden');
    const arrow = btnToggleChunking.querySelector('.collapsible-arrow');
    arrow.textContent = chunkingContent.classList.contains('hidden') ? '▼' : '▲';
  });

  // Populate DB Button
  btnPopulateDb.addEventListener('click', async () => {
    const source = ingestSourceInput.value.trim();
    if (!source) {
      alert('Please enter a URL or local path.');
      return;
    }

    btnPopulateDb.disabled = true;
    ingestSpinner.classList.remove('hidden');
    storageStatusBanner.innerHTML = '<span class="status-indicator-busy">⏳ Ingestion in progress...</span>';

    try {
      const res = await fetch('/api/vectordb/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: source,
          type: (document.getElementById('ingestTypeSelect') ? document.getElementById('ingestTypeSelect').value : 'Documents'),
          chunk_size: parseInt(inputChunkSize.value) || 1000,
          chunk_overlap: parseInt(inputChunkOverlap.value) || 200,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Ingestion failed');

      alert(data.message || 'Ingestion complete!');
      ingestSourceInput.value = '';
      loadIngestionData();
    } catch (err) {
      alert(`Ingestion error: ${err.message}`);
    } finally {
      btnPopulateDb.disabled = false;
      ingestSpinner.classList.add('hidden');
      storageStatusBanner.innerHTML = '<span class="status-indicator-idle">Idle (Ready)</span>';
    }
  });

  // Reset DB Button
  btnResetDb.addEventListener('click', async () => {
    if (confirm('Are you sure you want to reset the document vector database? All ingested chunks will be removed.')) {
      await fetch('/api/vectordb/reset', { method: 'POST' });
      loadIngestionData();
    }
  });

  // Update Skills Database Button
  btnUpdateSkills.addEventListener('click', async () => {
    btnUpdateSkills.disabled = true;
    btnUpdateSkills.textContent = 'Updating...';
    try {
      const res = await fetch('/api/skills/update', { method: 'POST' });
      const data = await res.json();
      alert(data.message || 'Skills updated!');
      loadIngestionData();
      loadModelsAndSkills();
    } catch (e) {
      alert('Failed to update skills.');
    } finally {
      btnUpdateSkills.disabled = false;
      btnUpdateSkills.innerHTML = '<span class="icon">🔄</span> Update Skills Database';
    }
  });

  // Change Embedder Model Dropdown with Stern Warning
  embedderSelect.addEventListener('change', () => {
    const targetModel = embedderSelect.value;
    if (targetModel === activeEmbedderModel) return;

    pendingModelSwitch = targetModel;
    modalTargetModelName.textContent = targetModel;
    changeModelConfirmInput.value = '';
    btnConfirmChangeModel.disabled = true;
    changeModelModal.classList.remove('hidden');
    changeModelConfirmInput.focus();
  });

  changeModelConfirmInput.addEventListener('input', () => {
    btnConfirmChangeModel.disabled = (changeModelConfirmInput.value.trim() !== 'Change model and delete data');
  });

  btnCancelChangeModel.addEventListener('click', () => {
    changeModelModal.classList.add('hidden');
    embedderSelect.value = activeEmbedderModel;
    pendingModelSwitch = null;
  });

  btnConfirmChangeModel.addEventListener('click', async () => {
    if (!pendingModelSwitch) return;
    btnConfirmChangeModel.disabled = true;
    btnConfirmChangeModel.textContent = 'Switching...';

    try {
      const res = await fetch('/api/vectordb/change-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: pendingModelSwitch,
          confirmation: 'Change model and delete data',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to change embedder model');

      alert(data.message || 'Embedder model switched successfully!');
      activeEmbedderModel = data.active_model;
      changeModelModal.classList.add('hidden');
      loadIngestionData();
      checkHealth();
    } catch (e) {
      alert(`Error: ${e.message}`);
      embedderSelect.value = activeEmbedderModel;
    } finally {
      btnConfirmChangeModel.disabled = false;
      btnConfirmChangeModel.textContent = 'Delete Data';
      pendingModelSwitch = null;
    }
  });

  // ---------------------------------------------------------------------------
  // Page 3: Telemetry & Charts
  // ---------------------------------------------------------------------------
  async function loadTelemetryData() {
    try {
      const params = new URLSearchParams({
        model: telemetryModelFilter.value,
        interval: telIntervalSelect.value,
        time_range: telRangeSelect.value,
        tz_offset: new Date().getTimezoneOffset(),
      });

      if (telRangeSelect.value === 'Custom' && telStartDate.value && telEndDate.value) {
        params.append('start_date', telStartDate.value);
        params.append('end_date', telEndDate.value);
      }

      const res = await fetch(`/api/telemetry?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch telemetry data');
      const data = await res.json();

      // 1. Update Used Models Dropdown
      const usedModels = data.used_models || data.models_used || [];
      const currentSelected = telemetryModelFilter.value;
      telemetryModelFilter.innerHTML = '<option value="All Models">All Models</option>';
      usedModels.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        if (m === currentSelected) opt.selected = true;
        telemetryModelFilter.appendChild(opt);
      });

      // 2. Summary stats
      const s = data.summary || data || {};
      if (telTotalChat) {
        telTotalChat.textContent = (s.total_chat !== undefined ? s.total_chat : (s.total_chats || 0)).toLocaleString();
      }
      telTotalPrompts.textContent = (s.total_llm_requests !== undefined ? s.total_llm_requests : (s.total_prompts || 0)).toLocaleString();
      telTotalResponses.textContent = (s.total_llm_responses !== undefined ? s.total_llm_responses : (s.total_responses || 0)).toLocaleString();
      telTotalErrors.textContent = (s.total_errors || 0).toLocaleString();
      telTotalInTokens.textContent = (s.total_input_tokens || 0).toLocaleString();
      telTotalOutTokens.textContent = (s.total_output_tokens || 0).toLocaleString();

      // 3. Performance stats
      const p = data.performance || data.metrics || {};
      valTtft.textContent = `${p.ttft_ms || 0} ms`;
      valItl.textContent = `${p.itl_ms || 0} ms`;
      valTps.textContent = `${p.tps || 0} tok/s`;
      valTpot.textContent = `${p.tpot_ms || 0} ms/tok`;

      // 4. Render Charts
      renderTelemetryCharts(data.charts || {});

    } catch (e) {
      console.error('Failed to load telemetry:', e);
    }
  }

  function renderTelemetryCharts(chartsData) {
    const rawLabels = chartsData.labels || [];
    const epochs = chartsData.epochs || [];
    const chatRequests = chartsData.chat_requests || [];
    const llmRequests = chartsData.llm_requests || chartsData.prompts || [];
    const llmResponses = chartsData.llm_responses || chartsData.responses || [];
    const errors = chartsData.errors || [];
    const inTokens = chartsData.input_tokens || [];
    const outTokens = chartsData.output_tokens || [];

    // Format chart labels to local time
    const pad = n => String(n).padStart(2, '0');
    const isDaily = telIntervalSelect && (telIntervalSelect.value === '1 day' || telIntervalSelect.value.includes('day'));
    const isMultiDay = telRangeSelect && (['Week', 'Month', 'Custom'].includes(telRangeSelect.value));
    const labels = (epochs && epochs.length === rawLabels.length) ? epochs.map(ep => {
      const d = new Date(ep * 1000);
      if (isDaily) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      if (isMultiDay) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
      return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }) : rawLabels;

    // Safely destroy existing Chart instances before creating new ones
    try {
      if (chartThroughputInstance) {
        chartThroughputInstance.destroy();
        chartThroughputInstance = null;
      }
    } catch (e) {
      chartThroughputInstance = null;
    }
    try {
      if (chartTokensInstance) {
        chartTokensInstance.destroy();
        chartTokensInstance = null;
      }
    } catch (e) {
      chartTokensInstance = null;
    }

    const chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } },
        tooltip: {
          callbacks: {
            title: function(context) {
              const idx = context && context[0] ? context[0].dataIndex : 0;
              if (epochs && epochs[idx]) {
                return formatToLocalTime(epochs[idx]);
              }
              return context && context[0] ? context[0].label : '';
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748b', font: { family: 'Inter', size: 10 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748b', font: { family: 'Inter', size: 10 } },
        },
      },
    };

    // Chart 1: Throughput
    const ctx1 = document.getElementById('chartThroughput');
    if (ctx1 && window.Chart) {
      chartThroughputInstance = new Chart(ctx1, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Chat Requests',
              data: chatRequests,
              borderColor: '#f59e0b',
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              tension: 0.3,
              fill: false,
            },
            {
              label: 'LLM Requests',
              data: llmRequests,
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              tension: 0.3,
              fill: false,
            },
            {
              label: 'LLM Responses',
              data: llmResponses,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              tension: 0.3,
              fill: false,
            },
            {
              label: 'Errors',
              data: errors,
              borderColor: '#ef4444',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              tension: 0.3,
              fill: false,
            },
          ],
        },
        options: chartOptions,
      });
    }

    // Chart 2: Tokens
    const ctx2 = document.getElementById('chartTokens');
    if (ctx2 && window.Chart) {
      chartTokensInstance = new Chart(ctx2, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Input Tokens',
              data: inTokens,
              borderColor: '#8b5cf6',
              backgroundColor: 'rgba(139, 92, 246, 0.1)',
              tension: 0.3,
              fill: true,
            },
            {
              label: 'Output Tokens',
              data: outTokens,
              borderColor: '#06b6d4',
              backgroundColor: 'rgba(6, 182, 212, 0.1)',
              tension: 0.3,
              fill: true,
            },
          ],
        },
        options: chartOptions,
      });
    }
  }

  btnRefreshTelemetry.addEventListener('click', loadTelemetryData);
  telemetryModelFilter.addEventListener('change', loadTelemetryData);
  telIntervalSelect.addEventListener('change', loadTelemetryData);
  
  telRangeSelect.addEventListener('change', () => {
    if (telRangeSelect.value === 'Custom') {
      customDateBoxes.classList.remove('hidden');
      if (!telStartDate.value || !telEndDate.value) {
        const today = new Date();
        const past = new Date(today.getTime() - 7 * 24 * 3600 * 1000);
        telEndDate.value = today.toISOString().split('T')[0];
        telStartDate.value = past.toISOString().split('T')[0];
      }
      loadTelemetryData();
    } else {
      customDateBoxes.classList.add('hidden');
      if (telRangeSelect.value === 'Last hr') {
        telIntervalSelect.value = '1 min';
      } else if (telRangeSelect.value === '1 day') {
        telIntervalSelect.value = '15 min';
      } else if (telRangeSelect.value === 'Week') {
        telIntervalSelect.value = '1 hr';
      } else if (telRangeSelect.value === 'Month') {
        telIntervalSelect.value = '1 day';
      }
      loadTelemetryData();
    }
  });

  telStartDate.addEventListener('change', loadTelemetryData);
  telEndDate.addEventListener('change', loadTelemetryData);

  // ---------------------------------------------------------------------------
  // Page 4: Audit Logs & Events
  // ---------------------------------------------------------------------------
  async function loadAuditLogs() {
    try {
      const params = new URLSearchParams({
        tz_offset: new Date().getTimezoneOffset()
      });
      const res = await fetch(`/api/logs?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch logs');
      const data = await res.json();

      // Stats
      const st = data.statistics || {};
      auditTotalPrompts.textContent = st.total_user_prompts || 0;
      auditModelCalls.textContent = st.total_model_calls || 0;
      auditOllamaEmbeds.textContent = st.total_ollama_embeds || 0;
      auditAvgLatency.textContent = st.avg_latency_ms || '0.0';

      // Conversations Table
      currentConversationsCache = data.conversations || [];
      if (currentConversationsCache.length === 0) {
        conversationsTbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No conversations recorded yet.</td></tr>`;
        eventsTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No conversation events to display.</td></tr>`;
        selectedConvBadge.textContent = 'None Selected';
        return;
      }

      conversationsTbody.innerHTML = currentConversationsCache.map(c => {
        const rawTs = c.local_timestamp || c.timestamp || c.last_seen || c.first_seen || '';
        const localTs = formatToLocalTime(rawTs);
        const evCount = c.event_count !== undefined ? c.event_count : (c.events_count || 0);
        const userName = c.user || c.username || 'anonymous';
        return `
        <tr class="conv-row ${c.conversation_id === selectedConversationId ? 'selected-row' : ''}" data-cid="${escapeHtml(c.conversation_id)}">
          <td><span style="font-family:var(--font-mono);font-size:0.75rem;">${escapeHtml(localTs)}</span></td>
          <td><code style="color:#a5b4fc;">${escapeHtml(c.conversation_id)}</code></td>
          <td><span class="badge" style="background:#4338ca;color:#e0e7ff;font-size:0.75rem;">${escapeHtml(userName)}</span></td>
          <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(c.user_query || '')}</td>
          <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(c.agent_response || '')}</td>
          <td><span class="badge">${escapeHtml(c.agent_type || 'Custom Agent')}</span></td>
          <td><strong>${evCount}</strong></td>
        </tr>
      `;
      }).join('');

      // Bind row clicks
      conversationsTbody.querySelectorAll('.conv-row').forEach(row => {
        row.addEventListener('click', () => {
          const cid = row.getAttribute('data-cid');
          selectConversation(cid);
        });
      });

      // Auto-select first conversation if none selected
      if (!selectedConversationId && currentConversationsCache.length > 0) {
        selectConversation(currentConversationsCache[0].conversation_id);
      } else if (selectedConversationId) {
        selectConversation(selectedConversationId);
      }

    } catch (e) {
      console.error('Failed to load audit logs:', e);
    }
  }

  async function selectConversation(cid) {
    selectedConversationId = cid;
    window.currentActiveConversationId = cid;
    selectedConvBadge.textContent = cid;
    loadContextEvidence(cid);

    // Highlight row
    conversationsTbody.querySelectorAll('.conv-row').forEach(row => {
      if (row.getAttribute('data-cid') === cid) {
        row.classList.add('selected-row');
      } else {
        row.classList.remove('selected-row');
      }
    });

    // Fetch conversation events
    try {
      const params = new URLSearchParams({
        tz_offset: new Date().getTimezoneOffset()
      });
      const res = await fetch(`/api/logs/${encodeURIComponent(cid)}?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to load events');
      const data = await res.json();
      currentEventsCache = data.events || [];

      if (currentEventsCache.length === 0) {
        eventsTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No events recorded for this conversation.</td></tr>`;
        return;
      }

      eventsTbody.innerHTML = currentEventsCache.map((evt, idx) => {
        const rawTime = evt.local_time || evt.raw_timestamp || evt.timestamp || '';
        const localTime = formatToLocalTime(rawTime);
        const eventType = evt.event_type || evt.type || 'generic';
        const invoker = evt.invoker || 'unknown';
        const target = evt.target || evt.recipient || 'unknown';
        const desc = evt.short_description || '';
        return `
          <tr class="event-row" data-idx="${idx}">
            <td><span style="font-family:var(--font-mono);font-size:0.75rem;">${escapeHtml(localTime)}</span></td>
            <td><span class="step-bubble ${eventType.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(eventType)}</span></td>
            <td><strong>${escapeHtml(invoker)}</strong></td>
            <td>${escapeHtml(target)}</td>
            <td>${escapeHtml(desc)}</td>
          </tr>
        `;
      }).join('');

      // Bind click to open detail inspector
      eventsTbody.querySelectorAll('.event-row').forEach(row => {
        row.addEventListener('click', () => {
          const idx = parseInt(row.getAttribute('data-idx'));
          const evt = currentEventsCache[idx];
          if (evt) showEventDetailModal(evt);
        });
      });

    } catch (e) {
      eventsTbody.innerHTML = `<tr><td colspan="5" class="text-danger">Error loading events: ${e.message}</td></tr>`;
    }
  }

  function extractPromptAndResponse(evt) {
    const payload = evt.payload || {};
    let prompt = null;
    let response = null;

    // Check payload.request and payload.response (standard inter-container format)
    if (payload.request !== undefined && payload.request !== null) {
      if (typeof payload.request === 'object' && Object.keys(payload.request).length > 0) {
        prompt = payload.request;
      } else if (typeof payload.request === 'string' && payload.request.trim() !== '') {
        prompt = payload.request;
      }
    }
    if (payload.response !== undefined && payload.response !== null) {
      if (typeof payload.response === 'object' && Object.keys(payload.response).length > 0) {
        response = payload.response;
      } else if (typeof payload.response === 'string' && payload.response.trim() !== '') {
        response = payload.response;
      }
    }

    // Extract Prompt / Input
    if (prompt === null) {
      if (payload.prompt !== undefined && payload.prompt !== null) {
        prompt = payload.prompt;
        if (payload.system_instruction && typeof prompt === 'string') {
          prompt = `[System Instruction]\n${payload.system_instruction}\n\n[User Prompt]\n${prompt}`;
        }
      } else if (payload.message !== undefined && payload.message !== null) {
        prompt = payload.message;
      } else if (payload.query !== undefined && payload.query !== null) {
        prompt = payload.query;
      } else if (payload.arguments !== undefined && payload.arguments !== null) {
        prompt = payload.arguments;
      } else if (payload.text !== undefined && payload.text !== null) {
        prompt = payload.text;
      } else if (payload.text_sample !== undefined && payload.text_sample !== null) {
        prompt = payload.text_sample;
      } else if (payload.input !== undefined && payload.input !== null) {
        prompt = payload.input;
      }
    }

    // Extract Response / Output
    if (response === null) {
      if (payload.response_text !== undefined && payload.response_text !== null) {
        response = payload.response_text;
      } else if (payload.response !== undefined && payload.response !== null) {
        response = payload.response;
      } else if (payload.result !== undefined && payload.result !== null) {
        response = payload.result;
      } else if (payload.matches !== undefined && payload.matches !== null) {
        response = payload.matches;
      } else if (payload.results !== undefined && payload.results !== null) {
        response = payload.results;
      } else if (payload.matched_items !== undefined && payload.matched_items !== null) {
        response = payload.matched_items;
      } else if (payload.steps !== undefined && payload.steps !== null) {
        response = payload.steps;
      } else if (payload.output !== undefined && payload.output !== null) {
        response = payload.output;
      } else if (payload.raw_response !== undefined && payload.raw_response !== null) {
        response = payload.raw_response;
      }
    }

    // Contextual fallback: if neither is set, use description for prompt
    if (prompt === null && response === null && evt.short_description) {
      prompt = evt.short_description;
    }

    return { prompt, response };
  }

  function renderFormattedContent(content, container) {
    if (!container) return;

    if (content === null || content === undefined || content === '') {
      container.innerHTML = `<div class="text-muted-box">None recorded for this event step.</div>`;
      return;
    }

    // Determine if content is JSON or a JSON string
    let isJson = false;
    let parsedObj = null;

    if (typeof content === 'object') {
      isJson = true;
      parsedObj = content;
    } else if (typeof content === 'string') {
      const trimmed = content.trim();
      if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
        try {
          parsedObj = JSON.parse(trimmed);
          isJson = true;
        } catch (e) {
          isJson = false;
        }
      }
    }

    if (isJson && parsedObj !== null) {
      const jsonStr = JSON.stringify(parsedObj, null, 2);
      container.innerHTML = `
        <div class="json-viewer-container">
          <div class="json-viewer-header">
            <span><i class="fas fa-code"></i> JSON Viewer</span>
            <button type="button" class="btn-copy">📋 Copy</button>
          </div>
          <pre class="json-code-block">${escapeHtml(jsonStr)}</pre>
        </div>
      `;
      const copyBtn = container.querySelector('.btn-copy');
      if (copyBtn) {
        copyBtn.addEventListener('click', () => {
          navigator.clipboard.writeText(jsonStr);
          copyBtn.textContent = '✅ Copied!';
          setTimeout(() => { copyBtn.textContent = '📋 Copy'; }, 2000);
        });
      }
    } else {
      const textStr = typeof content === 'string' ? content : String(content);
      container.innerHTML = `
        <div class="human-readable-text-box">
          <div class="text-box-header">
            <span><i class="fas fa-align-left"></i> Human Readable Text</span>
            <button type="button" class="btn-copy">📋 Copy</button>
          </div>
          <div class="text-box-content">${escapeHtml(textStr)}</div>
        </div>
      `;
      const copyBtn = container.querySelector('.btn-copy');
      if (copyBtn) {
        copyBtn.addEventListener('click', () => {
          navigator.clipboard.writeText(textStr);
          copyBtn.textContent = '✅ Copied!';
          setTimeout(() => { copyBtn.textContent = '📋 Copy'; }, 2000);
        });
      }
    }
  }

  function showEventDetailModal(evt) {
    const rawTime = evt.local_time || evt.raw_timestamp || evt.timestamp || '';
    const formattedLocalTime = formatToLocalTime(rawTime);
    eventModalMeta.innerHTML = `
      <div><span style="color:var(--text-muted);">Event ID:</span> <code>${escapeHtml(evt.id || '')}</code></div>
      <div><span style="color:var(--text-muted);">Time (Local):</span> <strong>${escapeHtml(formattedLocalTime)}</strong></div>
      <div><span style="color:var(--text-muted);">Event Type:</span> <strong style="color:#60a5fa;">${escapeHtml(evt.event_type || '')}</strong></div>
      <div><span style="color:var(--text-muted);">Latency:</span> <strong>${evt.elapsed_ms ? `${evt.elapsed_ms} ms` : 'N/A'}</strong></div>
      <div><span style="color:var(--text-muted);">Invoker:</span> <strong>${escapeHtml(evt.invoker || '')}</strong></div>
      <div><span style="color:var(--text-muted);">Target:</span> <strong>${escapeHtml(evt.target || '')}</strong></div>
      <div style="grid-column: span 2;"><span style="color:var(--text-muted);">Description:</span> <strong>${escapeHtml(evt.short_description || '')}</strong></div>
    `;

    const { prompt, response } = extractPromptAndResponse(evt);
    renderFormattedContent(prompt, eventModalPromptContainer);
    renderFormattedContent(response, eventModalResponseContainer);

    const jsonText = JSON.stringify(evt.payload || {}, null, 2);
    eventModalJson.textContent = jsonText;
    eventDetailModal.classList.remove('hidden');
  }

  btnCloseEventModal.addEventListener('click', () => eventDetailModal.classList.add('hidden'));
  btnCloseEventModal2.addEventListener('click', () => eventDetailModal.classList.add('hidden'));

  btnCopyJson.addEventListener('click', () => {
    navigator.clipboard.writeText(eventModalJson.textContent);
    btnCopyJson.textContent = '✅ Copied!';
    setTimeout(() => { btnCopyJson.textContent = '📋 Copy'; }, 2000);
  });

  // Clear Logs Modal Flow
  btnClearLogs.addEventListener('click', () => {
    clearLogsModal.classList.remove('hidden');
  });

  btnCancelClearLogs.addEventListener('click', () => {
    clearLogsModal.classList.add('hidden');
  });

  btnConfirmClearLogs.addEventListener('click', async () => {
    try {
      await fetch('/api/logs/clear', { method: 'POST' });
      clearLogsModal.classList.add('hidden');
      selectedConversationId = null;
      loadAuditLogs();
    } catch (e) {
      alert('Failed to clear logs.');
    }
  });

  btnRefreshLogs.addEventListener('click', loadAuditLogs);

  // ---------------------------------------------------------------------------
  // Utility Functions
  // ---------------------------------------------------------------------------
  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatMarkdownText(text) {
    if (!text) return '';
    let clean = escapeHtml(text);
    // Bold
    clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Code blocks
    clean = clean.replace(/```([\s\S]*?)```/g, '<pre style="background:rgba(0,0,0,0.4);padding:8px;border-radius:6px;overflow-x:auto;">$1</pre>');
    // Inline code
    clean = clean.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 5px;border-radius:4px;color:#93c5fd;">$1</code>');
    // Newlines to br
    clean = clean.replace(/\n/g, '<br>');
    return clean;
  }

  // ---------------------------------------------------------------------------
  // ---------------------------------------------------------------------------
  // AUTHENTICATION & LOGIN FLOW
  // ---------------------------------------------------------------------------
  const loginModal = document.getElementById('loginModal');
  const loginUsername = document.getElementById('loginUsername');
  const loginPassword = document.getElementById('loginPassword');
  const btnLoginOk = document.getElementById('btnLoginOk');
  const btnLoginCancel = document.getElementById('btnLoginCancel');
  const btnOpenRegisterModal = document.getElementById('btnOpenRegisterModal');
  const loginErrorMsg = document.getElementById('loginErrorMsg');

  const registerModal = document.getElementById('registerModal');
  const regUsername = document.getElementById('regUsername');
  const regPassword = document.getElementById('regPassword');
  const btnRegAdd = document.getElementById('btnRegAdd');
  const btnRegCancel = document.getElementById('btnRegCancel');
  const registerAlertMsg = document.getElementById('registerAlertMsg');

  const exitScreen = document.getElementById('exitScreen');
  const btnReopenApp = document.getElementById('btnReopenApp');

  const headerUserEmail = document.getElementById('headerUserEmail');
  const headerUserRole = document.getElementById('headerUserRole');
  const btnLogout = document.getElementById('btnLogout');
  const tabVector = document.getElementById('tabVector');
  const tabAudit = document.getElementById('tabAudit');
  const tabContainers = document.getElementById('tabContainers');
  const tabAuth = document.getElementById('tabAuth');
  const adminAuthSection = document.getElementById('adminAuthSection');
  const profileEmail = document.getElementById('profileEmail');
  const profileRole = document.getElementById('profileRole');

  let currentUser = JSON.parse(sessionStorage.getItem('currentUser') || 'null');
  let currentJwt = sessionStorage.getItem('jwtToken') || '';

  function updateJwtDisplay(user, jwtToken) {
    const emailEl = document.getElementById('jwtUserEmail');
    const domainEl = document.getElementById('jwtUserDomain');
    const ragAccessEl = document.getElementById('jwtRagAccess');
    const csvAccessEl = document.getElementById('jwtCsvAccess');
    const tokenDisplayEl = document.getElementById('jwtTokenDisplay');
    const statusBadge = document.getElementById('jwtStatusBadge');

    if (!user) {
      if (tokenDisplayEl) tokenDisplayEl.textContent = 'No active JWT token';
      return;
    }

    const email = user.email || 'admin';
    const domain = user.domain || (email.includes('@') ? email.split('@')[1] : null);
    const isAdmin = (user.role === 'Admin') || (!domain && email === 'admin');

    if (emailEl) emailEl.textContent = email;
    if (domainEl) {
      domainEl.textContent = domain ? `@${domain}` : 'None (Global Admin)';
      domainEl.style.color = domain ? '#38bdf8' : '#fbbf24';
    }
    if (ragAccessEl) {
      ragAccessEl.textContent = isAdmin ? 'All RAG Documents (Global Access)' : `${domain} Domain Documents Only`;
    }
    if (csvAccessEl) {
      if (isAdmin) {
        csvAccessEl.textContent = 'Both (employee_database.csv & customer_database.csv)';
      } else if (domain === 'example-a.com') {
        csvAccessEl.textContent = 'tools/data/employee_database.csv';
      } else if (domain === 'sample-b.com') {
        csvAccessEl.textContent = 'tools/data/customer_database.csv';
      } else {
        csvAccessEl.textContent = 'No CSV assigned';
      }
    }
    if (tokenDisplayEl) {
      tokenDisplayEl.textContent = jwtToken || 'JWT Token generated at login';
    }
    if (statusBadge) {
      statusBadge.textContent = domain ? `Tenant: ${domain}` : 'Admin (All Tenants)';
    }

    const btnCopy = document.getElementById('btnCopySessionJwt');
    if (btnCopy) {
      btnCopy.onclick = () => {
        if (jwtToken) {
          navigator.clipboard.writeText(jwtToken);
          btnCopy.textContent = '✓ Copied!';
          setTimeout(() => { btnCopy.textContent = '📋 Copy Token'; }, 2000);
        }
      };
    }
  }

  function applyRolePermissions(user) {
    if (!user) return;
    const role = (user.role || 'User').toLowerCase();
    const domain = user.domain || '';
    const isGlobalAdmin = (role === 'admin' && !domain);

    if (headerUserEmail) headerUserEmail.textContent = user.email || 'admin';
    if (headerUserRole) {
      headerUserRole.textContent = user.role || 'User';
      headerUserRole.className = `user-profile-badge badge-${role}`;
    }

    if (profileEmail) profileEmail.textContent = user.email || 'admin';
    if (profileRole) {
      profileRole.textContent = user.role || 'User';
      profileRole.className = `user-profile-badge badge-${role}`;
    }

    // Common tabs
    if (tabVector) tabVector.style.display = '';
    if (tabAudit) tabAudit.style.display = '';
    if (tabAuth) tabAuth.style.display = '';

    // Container Mgr tab: only Global Admin has access to host container orchestration
    if (tabContainers) {
      tabContainers.style.display = isGlobalAdmin ? '' : 'none';
    }

    // Password & API Mgnt -> User Accounts Management table:
    // Global Admin and Domain Admins can manage user accounts. Editors and Users cannot.
    if (adminAuthSection) {
      adminAuthSection.style.display = (role === 'admin') ? '' : 'none';
    }
    const nonAdminNotice = document.getElementById('nonAdminNotice');
    if (nonAdminNotice) {
      nonAdminNotice.style.display = (role === 'admin') ? 'none' : '';
    }

    // VectorDB Ingestion permissions:
    // Role "User" cannot load documents (read-only view of global & org data).
    // Role "Editor" and "Admin" can populate VectorDB.
    const userNotice = document.getElementById('userIngestNotice');
    if (role === 'user') {
      if (btnPopulateDb) {
        btnPopulateDb.disabled = true;
        btnPopulateDb.style.opacity = '0.5';
        btnPopulateDb.style.cursor = 'not-allowed';
        btnPopulateDb.title = 'Users cannot ingest documents';
      }
      if (ingestSourceInput) ingestSourceInput.disabled = true;
      if (userNotice) userNotice.classList.remove('hidden');
      if (btnResetDb) {
        btnResetDb.disabled = true;
        btnResetDb.style.opacity = '0.5';
        btnResetDb.style.cursor = 'not-allowed';
      }
    } else {
      if (btnPopulateDb) {
        btnPopulateDb.disabled = false;
        btnPopulateDb.style.opacity = '';
        btnPopulateDb.style.cursor = '';
        btnPopulateDb.title = '';
      }
      if (ingestSourceInput) ingestSourceInput.disabled = false;
      if (userNotice) userNotice.classList.add('hidden');
      if (btnResetDb) {
        btnResetDb.disabled = (role !== 'admin');
        btnResetDb.style.opacity = (role !== 'admin') ? '0.5' : '';
        btnResetDb.style.cursor = (role !== 'admin') ? 'not-allowed' : '';
      }
    }
  }

  if (currentUser) {
    applyRolePermissions(currentUser);
    updateJwtDisplay(currentUser, currentJwt);
  }

  async function handleLogin() {
    loginErrorMsg.classList.add('hidden');
    loginErrorMsg.style.color = '#ef4444';
    const u = loginUsername.value.trim();
    const p = loginPassword.value;

    if (!u || !p) {
      loginErrorMsg.textContent = 'Please enter both username and password.';
      loginErrorMsg.classList.remove('hidden');
      return;
    }

    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p })
      });
      const data = await resp.json();

      if (resp.ok && data.status === 'success') {
        currentUser = data.user;
        currentJwt = data.jwt_token || data.token || '';
        sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
        sessionStorage.setItem('jwtToken', currentJwt);
        loginModal.style.display = 'none';
        applyRolePermissions(currentUser);
        updateJwtDisplay(currentUser, currentJwt);
        logPageView('Chat & Knowledge Mgnt');
        loadIngestionData();
      } else {
        if (resp.status === 403 || data.is_locked || (data.error && data.error.includes('Locked'))) {
          loginErrorMsg.textContent = 'Account is Locked. Please contact the administrator.';
        } else {
          loginErrorMsg.textContent = 'Invalid username or password.';
        }
        loginErrorMsg.classList.remove('hidden');
        loginPassword.value = '';
        loginPassword.focus();
      }
    } catch (e) {
      loginErrorMsg.textContent = 'Connection to authentication service failed.';
      loginErrorMsg.classList.remove('hidden');
    }
  }

  btnLoginOk.addEventListener('click', handleLogin);
  loginPassword.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleLogin(); });

  // Cancel on Login window: display "Thank you for using the app" and exit
  btnLoginCancel.addEventListener('click', () => {
    loginModal.style.display = 'none';
    if (exitScreen) exitScreen.classList.remove('hidden');
  });

  if (btnReopenApp) {
    btnReopenApp.addEventListener('click', () => {
      exitScreen.classList.add('hidden');
      loginModal.style.display = 'flex';
      loginUsername.focus();
    });
  }

  // Create New Account flow
  if (btnOpenRegisterModal) {
    btnOpenRegisterModal.addEventListener('click', () => {
      if (regUsername) regUsername.value = '';
      if (regPassword) regPassword.value = '';
      if (registerAlertMsg) registerAlertMsg.classList.add('hidden');
      if (registerModal) registerModal.classList.remove('hidden');
      if (regUsername) regUsername.focus();
    });
  }

  if (btnRegCancel) {
    btnRegCancel.addEventListener('click', () => {
      if (registerModal) registerModal.classList.add('hidden');
    });
  }

  if (btnRegAdd) {
    btnRegAdd.addEventListener('click', async () => {
      const u = regUsername.value.trim();
      const p = regPassword.value;
      if (!u || !p) {
        registerAlertMsg.textContent = 'Please enter both username and password.';
        registerAlertMsg.style.color = '#ef4444';
        registerAlertMsg.classList.remove('hidden');
        return;
      }
      try {
        const resp = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: u, password: p })
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
          registerModal.classList.add('hidden');
          loginUsername.value = u;
          loginPassword.value = '';
          loginErrorMsg.textContent = 'Account created with Locked status. Please contact the administrator to unlock.';
          loginErrorMsg.style.color = '#f59e0b';
          loginErrorMsg.classList.remove('hidden');
        } else {
          registerAlertMsg.textContent = data.error || 'Failed to create account.';
          registerAlertMsg.style.color = '#ef4444';
          registerAlertMsg.classList.remove('hidden');
        }
      } catch (e) {
        registerAlertMsg.textContent = 'Failed to connect to authentication service.';
        registerAlertMsg.style.color = '#ef4444';
        registerAlertMsg.classList.remove('hidden');
      }
    });
  }

  // Logout button: close current tab and go to login window
  if (btnLogout) {
    btnLogout.addEventListener('click', async () => {
      try {
        await fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      } catch (e) {}
      sessionStorage.removeItem('currentUser');
      currentUser = null;
      loginErrorMsg.classList.add('hidden');
      loginPassword.value = '';
      loginModal.style.display = 'flex';
      loginUsername.focus();
    });
  }

  if (currentUser) {
    loginModal.style.display = 'none';
    applyRolePermissions(currentUser);
  } else {
    loginModal.style.display = 'flex';
  }

  function logPageView(pageName) {
    fetch('/api/page_view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_name: pageName, username: currentUser ? currentUser.email : 'anonymous' })
    }).catch(() => {});
  }

  // ---------------------------------------------------------------------------
  // PAGE 5: CONTAINER MANAGER
  // ---------------------------------------------------------------------------
  let containersCache = [];
  const containerDetailModal = document.getElementById('containerDetailModal');
  const modalContainerName = document.getElementById('modalContainerName');
  const modalContainerStatus = document.getElementById('modalContainerStatus');
  const modalContainerPort = document.getElementById('modalContainerPort');
  const modalContainerDepsList = document.getElementById('modalContainerDepsList');
  const modalContainerActionBtnContainer = document.getElementById('modalContainerActionBtnContainer');
  const btnCloseContainerModal = document.getElementById('btnCloseContainerModal');
  const btnCloseContainerModalX = document.getElementById('btnCloseContainerModalX');

  const btnShutdownAllContainers = document.getElementById('btnShutdownAllContainers');
  const shutdownAllModal = document.getElementById('shutdownAllModal');
  const shutdownAllConfirmInput = document.getElementById('shutdownAllConfirmInput');
  const btnCancelShutdownAll = document.getElementById('btnCancelShutdownAll');
  const btnConfirmShutdownAll = document.getElementById('btnConfirmShutdownAll');

  const btnRestartAllContainers = document.getElementById('btnRestartAllContainers');
  const restartAllModal = document.getElementById('restartAllModal');
  const restartAllConfirmInput = document.getElementById('restartAllConfirmInput');
  const btnCancelRestartAll = document.getElementById('btnCancelRestartAll');
  const btnConfirmRestartAll = document.getElementById('btnConfirmRestartAll');

  async function loadContainers() {
    try {
      const resp = await fetch('/api/containers/list');
      const data = await resp.json();
      containersCache = data.containers || [];
      renderTopology();
    } catch (e) {
      console.error('Failed to load containers', e);
    }
  }

  function renderTopology() {
    containersCache.forEach(c => {
      const g = document.getElementById(`node-${c.name}`);
      if (!g) return;

      const isRunning = (c.status === 'running');
      if (isRunning) {
        g.classList.add('node-active');
        g.classList.remove('node-stopped');
      } else {
        g.classList.add('node-stopped');
        g.classList.remove('node-active');
      }

      const statusText = g.querySelector('.node-status');
      if (statusText) {
        statusText.textContent = `${isRunning ? 'Active' : 'Stopped'} • Port ${c.port}`;
      }

      const metricText = document.getElementById(`metric-${c.name}`);
      if (metricText) {
        metricText.textContent = `CPU: ${c.cpu} | ${c.memory}`;
      }

      // Attach interaction handlers
      g.onclick = () => openContainerDetail(c);
      g.oncontextmenu = (e) => { e.preventDefault(); openContainerDetail(c); };
    });
  }

  const btnSaveContainerKeys = document.getElementById('btnSaveContainerKeys');
  let currentDetailContainer = null;

  async function openContainerDetail(c) {
    currentDetailContainer = c;
    modalContainerName.textContent = c.name;
    const isRunning = (c.status === 'running');
    modalContainerStatus.textContent = isRunning ? 'Active (Running)' : 'Stopped / Inactive';
    modalContainerStatus.className = `badge ${isRunning ? 'badge-user' : 'badge-admin'}`;
    modalContainerPort.textContent = c.port_mapping || `${c.port}:${c.port}`;

    const notice = document.getElementById('modalContainerKeyNotice');
    if (notice) {
      notice.style.display = isRunning ? 'none' : 'flex';
    }

    modalContainerDepsList.innerHTML = '';
    const accesses = c.accesses || [];
    if (accesses.length === 0) {
      modalContainerDepsList.innerHTML = '<span class="text-muted" style="font-size:0.85rem;">No outgoing inter-container connections.</span>';
    } else {
      accesses.forEach(dep => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:#182234; padding:8px 12px; border-radius:4px; gap:8px;';
        row.innerHTML = `<span style="font-weight: 500;">🔗 ${dep}</span> 
          <span class="badge" style="background:#0369a1; color:#bae6fd; font-size:0.75rem;">JWT Authenticated</span>`;
        modalContainerDepsList.appendChild(row);
      });
    }

    if (btnSaveContainerKeys) {
      btnSaveContainerKeys.style.display = 'none';
    }

    modalContainerActionBtnContainer.innerHTML = '';
    const actionBtn = document.createElement('button');
    if (isRunning) {
      actionBtn.className = 'btn-stop-action';
      actionBtn.textContent = 'Stop Container';
      actionBtn.onclick = () => triggerContainerAction(c.name, 'stop');
    } else {
      actionBtn.className = 'btn-start-action';
      actionBtn.textContent = 'Start Container';
      actionBtn.onclick = async () => {
        await saveContainerKeysFromModal(c.name);
        triggerContainerAction(c.name, 'start');
      };
    }
    modalContainerActionBtnContainer.appendChild(actionBtn);

    containerDetailModal.classList.remove('hidden');
  }

  async function saveContainerKeysFromModal(containerName) {
    const inputs = modalContainerDepsList.querySelectorAll('.container-key-input');
    const keysObj = {};
    inputs.forEach(inp => {
      const dep = inp.getAttribute('data-dep');
      if (dep) {
        keysObj[dep] = inp.value.trim();
      }
    });

    try {
      const resp = await fetch(`/api/containers/${containerName}/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: keysObj })
      });
      if (resp.ok) {
        if (btnSaveContainerKeys) {
          btnSaveContainerKeys.textContent = '✓ Saved!';
          setTimeout(() => {
            if (btnSaveContainerKeys) btnSaveContainerKeys.textContent = 'Save Keys';
          }, 2000);
        }
      } else {
        alert('Failed to save container keys');
      }
    } catch (e) {
      alert(`Error saving container keys: ${e}`);
    }
  }

  async function triggerContainerAction(name, act) {
    try {
      await fetch(`/api/containers/${name}/${act}`, { method: 'POST' });
      containerDetailModal.classList.add('hidden');
      loadContainers();
    } catch (e) {
      alert(`Action ${act} failed: ${e}`);
    }
  }

  btnCloseContainerModal.onclick = () => containerDetailModal.classList.add('hidden');
  btnCloseContainerModalX.onclick = () => containerDetailModal.classList.add('hidden');

  // Shutdown All Containers
  btnShutdownAllContainers.onclick = () => {
    shutdownAllConfirmInput.value = '';
    btnConfirmShutdownAll.disabled = true;
    shutdownAllModal.classList.remove('hidden');
  };
  btnCancelShutdownAll.onclick = () => shutdownAllModal.classList.add('hidden');
  shutdownAllConfirmInput.oninput = () => {
    btnConfirmShutdownAll.disabled = (shutdownAllConfirmInput.value.trim() !== 'Shutdown System');
  };
  btnConfirmShutdownAll.onclick = async () => {
    try {
      await fetch('/api/containers/shutdown_all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phrase: 'Shutdown the services' })
      });
      shutdownAllModal.classList.add('hidden');
      alert('All system containers shut down.');
      loadContainers();
    } catch (e) {
      alert('Failed to shut down containers');
    }
  };

  // Restart All Containers
  btnRestartAllContainers.onclick = () => {
    restartAllConfirmInput.value = '';
    btnConfirmRestartAll.disabled = true;
    restartAllModal.classList.remove('hidden');
  };
  btnCancelRestartAll.onclick = () => restartAllModal.classList.add('hidden');
  restartAllConfirmInput.oninput = () => {
    btnConfirmRestartAll.disabled = (restartAllConfirmInput.value.trim() !== 'Restart System');
  };
  btnConfirmRestartAll.onclick = async () => {
    try {
      await fetch('/api/containers/restart_all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phrase: 'Restart System' })
      });
      restartAllModal.classList.add('hidden');
      alert('All system containers restart initiated.');
      loadContainers();
    } catch (e) {
      alert('Failed to restart containers');
    }
  };

  // ---------------------------------------------------------------------------
  // PAGE 6: PASSWORDS & API KEYS
  // ---------------------------------------------------------------------------
  const tabBtnPasswords = document.getElementById('tabBtnPasswords');
  const tabBtnApiKeys = document.getElementById('tabBtnApiKeys');
  const subtabPasswords = document.getElementById('subtab-passwords');
  const subtabApiKeys = document.getElementById('subtab-apikeys');

  const btnRefreshAuth = document.getElementById('btnRefreshAuth');
  if (btnRefreshAuth) {
    btnRefreshAuth.addEventListener('click', async () => {
      await Promise.all([
        typeof loadUsers === 'function' ? loadUsers() : Promise.resolve(),
        typeof loadUserActivity === 'function' ? loadUserActivity() : Promise.resolve(),
        typeof refreshActiveSessionJwt === 'function' ? refreshActiveSessionJwt() : Promise.resolve(),
        typeof loadJwtTokens === 'function' ? loadJwtTokens() : Promise.resolve(),
        typeof loadJwtActivities === 'function' ? loadJwtActivities() : Promise.resolve()
      ]);
    });
  }

  tabBtnPasswords.onclick = () => {
    tabBtnPasswords.classList.add('active');
    tabBtnApiKeys.classList.remove('active');
    subtabPasswords.classList.add('active');
    subtabApiKeys.classList.remove('active');
    if (typeof loadUsers === 'function') loadUsers();
    if (typeof loadUserActivity === 'function') loadUserActivity();
  };

  tabBtnApiKeys.onclick = () => {
    tabBtnApiKeys.classList.add('active');
    tabBtnPasswords.classList.remove('active');
    subtabApiKeys.classList.add('active');
    subtabPasswords.classList.remove('active');
    if (typeof refreshActiveSessionJwt === 'function') refreshActiveSessionJwt();
    if (typeof loadJwtTokens === 'function') loadJwtTokens();
    if (typeof loadJwtActivities === 'function') loadJwtActivities();
  };

  // Users Table & Management
  const usersTbody = document.getElementById('usersTbody');
  const selectAllUsers = document.getElementById('selectAllUsers');
  const btnDeleteSelectedUsers = document.getElementById('btnDeleteSelectedUsers');
  const btnOpenCreateUserModal = document.getElementById('btnOpenCreateUserModal');
  const createUserModal = document.getElementById('createUserModal');
  const btnCloseCreateUserModalX = document.getElementById('btnCloseCreateUserModalX');
  const btnCancelCreateUser = document.getElementById('btnCancelCreateUser');
  const btnConfirmCreateUser = document.getElementById('btnConfirmCreateUser');
  const createUserNameInput = document.getElementById('createUserNameInput');
  const createUserPasswordInput = document.getElementById('createUserPasswordInput');
  const createUserAlertMsg = document.getElementById('createUserAlertMsg');

  let selectedUserIds = new Set();
  let currentLoadedUsers = [];

  async function loadUsers() {
    try {
      const resp = await fetch('/api/users');
      const data = await resp.json();
      usersTbody.innerHTML = '';
      currentLoadedUsers = data.users || [];
      const isAdmin = (currentUser && currentUser.role === 'Admin');

      if (btnOpenCreateUserModal) {
        btnOpenCreateUserModal.disabled = !isAdmin;
      }

      if (currentLoadedUsers.length === 0) {
        usersTbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No user accounts found.</td></tr>';
        if (selectAllUsers) selectAllUsers.checked = false;
        if (btnDeleteSelectedUsers) btnDeleteSelectedUsers.disabled = true;
        return;
      }

      currentLoadedUsers.forEach(u => {
        const tr = document.createElement('tr');
        const isLocked = (u.status === 'Locked');
        const isChecked = selectedUserIds.has(u.id);
        if (isChecked) tr.classList.add('selected-row');

        tr.innerHTML = `
          <td>
            <input type="checkbox" class="user-select-chk" data-id="${u.id}" ${isChecked ? 'checked' : ''} ${!isAdmin ? 'disabled' : ''} style="margin-right: 8px; vertical-align: middle;">
            <strong>${escapeHtml(u.email)}</strong>
          </td>
          <td>${u.created_at ? new Date(u.created_at).toLocaleString() : '-'}</td>
          <td>
            <select class="input-text" style="padding:2px 8px; font-size:0.8rem;" ${!isAdmin ? 'disabled' : ''} onchange="updateUserRole(${u.id}, this.value)">
              <option value="Admin" ${u.role === 'Admin' ? 'selected' : ''}>Admin</option>
              <option value="Editor" ${u.role === 'Editor' ? 'selected' : ''}>Editor</option>
              <option value="User" ${u.role === 'User' ? 'selected' : ''}>User</option>
            </select>
          </td>
          <td>
            <span class="badge ${isLocked ? 'badge-locked' : 'badge-active'}">${u.status || 'Active'}</span>
            <button class="btn-secondary" style="padding:2px 8px; font-size:0.75rem; margin-left:4px;" ${!isAdmin ? 'disabled' : ''} onclick="toggleUserStatus(${u.id}, '${isLocked ? 'Active' : 'Locked'}')">
              ${isLocked ? 'Unlock' : 'Lock'}
            </button>
          </td>
          <td>
            <button class="btn-secondary" style="padding:2px 8px; font-size:0.75rem;" ${!isAdmin ? 'disabled' : ''} onclick="resetUserPassword(${u.id})">Reset Pass</button>
          </td>
        `;
        usersTbody.appendChild(tr);
      });

      // Bind row checkboxes
      usersTbody.querySelectorAll('.user-select-chk').forEach(chk => {
        chk.addEventListener('change', () => {
          const uid = parseInt(chk.getAttribute('data-id'));
          const tr = chk.closest('tr');
          if (chk.checked) {
            selectedUserIds.add(uid);
            if (tr) tr.classList.add('selected-row');
          } else {
            selectedUserIds.delete(uid);
            if (tr) tr.classList.remove('selected-row');
          }
          updateBulkDeleteUsersBtnState();
        });
      });

      updateBulkDeleteUsersBtnState();
    } catch (e) {
      console.error('Failed to load users:', e);
    }
  }

  function updateBulkDeleteUsersBtnState() {
    const isAdmin = (currentUser && currentUser.role === 'Admin');
    if (btnDeleteSelectedUsers) {
      btnDeleteSelectedUsers.disabled = (selectedUserIds.size === 0 || !isAdmin);
    }
    if (selectAllUsers) {
      selectAllUsers.checked = (currentLoadedUsers.length > 0 && selectedUserIds.size === currentLoadedUsers.length);
      selectAllUsers.disabled = !isAdmin;
    }
  }

  if (selectAllUsers) {
    selectAllUsers.addEventListener('change', () => {
      const isAdmin = (currentUser && currentUser.role === 'Admin');
      if (!isAdmin) return;
      const isChecked = selectAllUsers.checked;
      selectedUserIds.clear();
      if (isChecked) {
        currentLoadedUsers.forEach(u => selectedUserIds.add(u.id));
      }
      usersTbody.querySelectorAll('.user-select-chk').forEach(chk => {
        chk.checked = isChecked;
        const tr = chk.closest('tr');
        if (tr) {
          if (isChecked) tr.classList.add('selected-row');
          else tr.classList.remove('selected-row');
        }
      });
      updateBulkDeleteUsersBtnState();
    });
  }

  if (btnDeleteSelectedUsers) {
    btnDeleteSelectedUsers.onclick = async () => {
      const isAdmin = (currentUser && currentUser.role === 'Admin');
      if (!isAdmin) {
        alert('Only users with Admin access can delete user accounts.');
        return;
      }
      if (selectedUserIds.size === 0) return;
      if (!confirm(`Are you sure you want to delete ${selectedUserIds.size} selected user(s)?`)) return;

      try {
        const resp = await fetch('/api/users/bulk_delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_ids: Array.from(selectedUserIds) })
        });
        const res = await resp.json();
        if (resp.ok) {
          selectedUserIds.clear();
          if (selectAllUsers) selectAllUsers.checked = false;
          loadUsers();
          loadUserActivity();
        } else {
          alert(res.error || 'Failed to delete users');
        }
      } catch (e) {
        alert('Error deleting users: ' + e);
      }
    };
  }

  window.toggleUserStatus = async (uid, newStatus) => {
    const isAdmin = (currentUser && currentUser.role === 'Admin');
    if (!isAdmin) {
      alert('Only users with Admin access can modify user accounts.');
      return;
    }
    const resp = await fetch(`/api/users/${uid}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.error || 'Failed to update user status');
    }
    loadUsers();
    loadUserActivity();
  };

  window.updateUserRole = async (uid, newRole) => {
    const isAdmin = (currentUser && currentUser.role === 'Admin');
    if (!isAdmin) {
      alert('Only users with Admin access can modify user accounts.');
      return;
    }
    const resp = await fetch(`/api/users/${uid}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.error || 'Failed to update user role');
    }
    loadUsers();
  };

  window.resetUserPassword = async (uid) => {
    const isAdmin = (currentUser && currentUser.role === 'Admin');
    if (!isAdmin) {
      alert('Only users with Admin access can modify user accounts.');
      return;
    }
    const p = prompt('Enter new password for this user:', 'admin123');
    if (!p) return;
    const resp = await fetch(`/api/users/${uid}/reset_password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: p })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.error || 'Failed to reset password');
    } else {
      alert('Password updated.');
    }
    loadUserActivity();
  };

  // Create New User Popup Window
  if (btnOpenCreateUserModal) {
    btnOpenCreateUserModal.onclick = () => {
      const isAdmin = (currentUser && currentUser.role === 'Admin');
      if (!isAdmin) {
        alert('Only users with Admin access can create user accounts.');
        return;
      }
      createUserNameInput.value = '';
      createUserPasswordInput.value = '';
      if (createUserAlertMsg) {
        createUserAlertMsg.textContent = '';
        createUserAlertMsg.classList.add('hidden');
      }
      createUserModal.classList.remove('hidden');
      createUserNameInput.focus();
    };
  }

  if (btnCloseCreateUserModalX) {
    btnCloseCreateUserModalX.onclick = () => createUserModal.classList.add('hidden');
  }

  if (btnCancelCreateUser) {
    btnCancelCreateUser.onclick = () => createUserModal.classList.add('hidden');
  }

  if (btnConfirmCreateUser) {
    btnConfirmCreateUser.onclick = async () => {
      const u = createUserNameInput.value.trim();
      const p = createUserPasswordInput.value;

      if (!u || !p) {
        if (createUserAlertMsg) {
          createUserAlertMsg.textContent = 'Please enter both username and password.';
          createUserAlertMsg.classList.remove('hidden');
        } else {
          alert('Please enter both username and password.');
        }
        return;
      }

      try {
        const resp = await fetch('/api/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: u,
            password: p,
            role: 'User',
            status: 'Active'
          })
        });
        const res = await resp.json();
        if (resp.ok && res.status === 'success') {
          createUserModal.classList.add('hidden');
          createUserNameInput.value = '';
          createUserPasswordInput.value = '';
          loadUsers();
          loadUserActivity();
        } else {
          if (createUserAlertMsg) {
            createUserAlertMsg.textContent = res.error || 'Failed to create user.';
            createUserAlertMsg.classList.remove('hidden');
          } else {
            alert(res.error || 'Failed to create user.');
          }
        }
      } catch (e) {
        if (createUserAlertMsg) {
          createUserAlertMsg.textContent = 'Error creating user: ' + e;
          createUserAlertMsg.classList.remove('hidden');
        } else {
          alert('Error creating user: ' + e);
        }
      }
    };
  }

  // User Activity Logs Table
  const userActivityTbody = document.getElementById('userActivityTbody');
  async function loadUserActivity() {
    try {
      const resp = await fetch('/api/users/activity_logs');
      const data = await resp.json();
      userActivityTbody.innerHTML = '';
      (data.activity_logs || []).forEach(l => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${l.created_at ? new Date(l.created_at).toLocaleString() : '-'}</td>
          <td>${escapeHtml(l.user_email)}</td>
          <td><span class="badge badge-editor">${escapeHtml(l.request_type)}</span></td>
          <td><span class="badge ${l.status === 'Success' ? 'badge-user' : 'badge-admin'}">${escapeHtml(l.status)}</span></td>
        `;
        userActivityTbody.appendChild(tr);
      });
    } catch (e) {}
  }

  // ---------------------------------------------------------------------------
  // JWT List, Token Management & JWT Activities
  // ---------------------------------------------------------------------------
  const jwtListTbody = document.getElementById('jwtListTbody');
  const selectAllJwt = document.getElementById('selectAllJwt');
  const btnDeleteSelectedJwt = document.getElementById('btnDeleteSelectedJwt');
  const deleteJwtModal = document.getElementById('deleteJwtModal');
  const btnCloseDeleteJwtModalX = document.getElementById('btnCloseDeleteJwtModalX');
  const btnCancelDeleteJwt = document.getElementById('btnCancelDeleteJwt');
  const btnConfirmDeleteJwt = document.getElementById('btnConfirmDeleteJwt');
  const deleteJwtConfirmMsg = document.getElementById('deleteJwtConfirmMsg');
  const selectedApiKeyNameText = document.getElementById('selectedApiKeyNameText');
  const apiKeyActivitiesTbody = document.getElementById('apiKeyActivitiesTbody');
  const btnRefreshSessionJwt = document.getElementById('btnRefreshSessionJwt');
  const btnRefreshJwtActivities = document.getElementById('btnRefreshJwtActivities');

  let currentJwtTokensCache = [];
  let selectedJwtToken = null; // { id, user_email, token_prefix }

  function updateDeleteJwtButtonState() {
    if (!btnDeleteSelectedJwt) return;
    const checked = jwtListTbody ? jwtListTbody.querySelectorAll('.jwt-select-chk:checked') : [];
    btnDeleteSelectedJwt.disabled = checked.length === 0;
  }

  async function loadJwtTokens() {
    if (!jwtListTbody) return;
    try {
      const resp = await fetch('/api/jwt/tokens');
      const data = await resp.json();
      currentJwtTokensCache = data.tokens || [];
      jwtListTbody.innerHTML = '';

      if (currentJwtTokensCache.length === 0) {
        jwtListTbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No active JWT tokens found.</td></tr>';
        if (selectAllJwt) selectAllJwt.checked = false;
        updateDeleteJwtButtonState();
        return;
      }

      currentJwtTokensCache.forEach(t => {
        const tr = document.createElement('tr');
        const isSelected = selectedJwtToken && selectedJwtToken.id === t.id;
        tr.className = 'jwt-token-row' + (isSelected ? ' selected-row' : '');
        tr.setAttribute('data-id', t.id);
        tr.setAttribute('data-user', t.user_email);
        tr.setAttribute('data-prefix', t.token_prefix);

        const fullToken = t.full_token || '';
        const tokenSuffix = t.token_suffix || (fullToken && fullToken.length >= 10 ? '...' + fullToken.slice(-10) : (fullToken ? '...' + fullToken : (t.token_prefix ? '...' + t.token_prefix.slice(-8) : '...')));
        tr.setAttribute('data-suffix', tokenSuffix);
        tr.style.cursor = 'pointer';

        const rawCreated = t.created_at || '';
        const rawExpiry = t.expires_at || '';
        const statusBadgeClass = t.status === 'active' ? 'badge-user' : 'badge-admin';

        tr.innerHTML = `
          <td style="text-align: center;" class="chk-cell">
            <input type="checkbox" class="jwt-select-chk" data-id="${t.id}">
          </td>
          <td><strong>${escapeHtml(t.user_email)}</strong></td>
          <td><code style="color: #93c5fd; font-family: var(--font-mono); font-size: 0.78rem;">${escapeHtml(tokenSuffix)}</code></td>
          <td>${formatToLocalTime(rawCreated)}</td>
          <td>${formatToLocalTime(rawExpiry)}</td>
          <td><span class="badge ${statusBadgeClass}">${escapeHtml(t.status)}</span></td>
        `;

        // Checkbox click stops row selection event
        const chk = tr.querySelector('.jwt-select-chk');
        if (chk) {
          chk.addEventListener('click', (ev) => {
            ev.stopPropagation();
            updateDeleteJwtButtonState();
          });
        }

        // Row click -> toggle filter on JWT Activities
        tr.addEventListener('click', (ev) => {
          if (ev.target && ev.target.tagName === 'INPUT') return;
          if (selectedJwtToken && selectedJwtToken.id === t.id) {
            // Deselect
            selectedJwtToken = null;
            jwtListTbody.querySelectorAll('.jwt-token-row').forEach(r => r.classList.remove('selected-row'));
            if (selectedApiKeyNameText) selectedApiKeyNameText.textContent = 'All Tokens';
            loadJwtActivities();
          } else {
            // Select this token
            selectedJwtToken = t;
            jwtListTbody.querySelectorAll('.jwt-token-row').forEach(r => r.classList.remove('selected-row'));
            tr.classList.add('selected-row');
            if (selectedApiKeyNameText) {
              selectedApiKeyNameText.textContent = `Token: ${tokenSuffix} (${t.user_email})`;
            }
            loadJwtActivities(t.user_email, t.token_prefix);
          }
        });

        jwtListTbody.appendChild(tr);
      });

      if (selectAllJwt) selectAllJwt.checked = false;
      updateDeleteJwtButtonState();

    } catch (e) {
      console.warn('Error loading JWT tokens:', e);
      jwtListTbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error loading JWT tokens.</td></tr>';
    }
  }

  if (selectAllJwt) {
    selectAllJwt.addEventListener('change', () => {
      const chks = jwtListTbody ? jwtListTbody.querySelectorAll('.jwt-select-chk') : [];
      chks.forEach(chk => { chk.checked = selectAllJwt.checked; });
      updateDeleteJwtButtonState();
    });
  }

  // Delete Selected JWT Modal Handlers
  if (btnDeleteSelectedJwt) {
    btnDeleteSelectedJwt.addEventListener('click', () => {
      const checked = jwtListTbody ? jwtListTbody.querySelectorAll('.jwt-select-chk:checked') : [];
      const ids = Array.from(checked).map(c => parseInt(c.getAttribute('data-id'))).filter(Boolean);
      if (ids.length === 0) return;

      if (deleteJwtConfirmMsg) {
        deleteJwtConfirmMsg.textContent = `Are you sure you want to delete the ${ids.length} selected JWT token(s)?`;
      }
      if (deleteJwtModal) deleteJwtModal.classList.remove('hidden');
    });
  }

  if (btnCloseDeleteJwtModalX) {
    btnCloseDeleteJwtModalX.addEventListener('click', () => {
      if (deleteJwtModal) deleteJwtModal.classList.add('hidden');
    });
  }

  if (btnCancelDeleteJwt) {
    btnCancelDeleteJwt.addEventListener('click', () => {
      if (deleteJwtModal) deleteJwtModal.classList.add('hidden');
    });
  }

  if (btnConfirmDeleteJwt) {
    btnConfirmDeleteJwt.addEventListener('click', async () => {
      const checked = jwtListTbody ? jwtListTbody.querySelectorAll('.jwt-select-chk:checked') : [];
      const ids = Array.from(checked).map(c => parseInt(c.getAttribute('data-id'))).filter(Boolean);
      if (ids.length === 0) return;

      try {
        btnConfirmDeleteJwt.disabled = true;
        btnConfirmDeleteJwt.textContent = 'Deleting...';
        const resp = await fetch('/api/jwt/tokens/bulk_delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token_ids: ids })
        });
        if (resp.ok) {
          if (deleteJwtModal) deleteJwtModal.classList.add('hidden');
          if (selectedJwtToken && ids.includes(selectedJwtToken.id)) {
            selectedJwtToken = null;
            if (selectedApiKeyNameText) selectedApiKeyNameText.textContent = 'All Tokens';
          }
          await loadJwtTokens();
          await loadJwtActivities();
        } else {
          alert('Failed to delete JWT tokens.');
        }
      } catch (e) {
        alert('Error deleting JWT tokens: ' + e.message);
      } finally {
        btnConfirmDeleteJwt.disabled = false;
        btnConfirmDeleteJwt.textContent = 'Confirm Delete';
      }
    });
  }

  async function refreshActiveSessionJwt() {
    try {
      const resp = await fetch('/api/auth/me');
      if (resp.ok) {
        const data = await resp.json();
        if (data.authenticated && data.user) {
          currentUser = data.user;
          currentJwt = data.jwt_token || currentJwt;
          sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
          sessionStorage.setItem('jwtToken', currentJwt);
          updateJwtDisplay(currentUser, currentJwt);
          applyRolePermissions(currentUser);
        }
      }
    } catch (e) {
      console.warn('Error refreshing session JWT:', e);
    }
  }

  if (btnRefreshSessionJwt) {
    btnRefreshSessionJwt.addEventListener('click', async () => {
      await refreshActiveSessionJwt();
      await loadJwtTokens();
      await loadJwtActivities();
    });
  }

  if (btnRefreshJwtActivities) {
    btnRefreshJwtActivities.addEventListener('click', () => {
      loadJwtActivities();
    });
  }

  async function loadJwtActivities(filterUser, filterPrefix) {
    if (!apiKeyActivitiesTbody) return;
    apiKeyActivitiesTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Loading JWT activities...</td></tr>';
    try {
      const targetUser = filterUser !== undefined ? filterUser : (selectedJwtToken ? selectedJwtToken.user_email : null);
      const targetPrefix = filterPrefix !== undefined ? filterPrefix : (selectedJwtToken ? selectedJwtToken.token_prefix : null);

      const params = new URLSearchParams();
      if (targetUser) params.set('user_email', targetUser);
      if (targetPrefix) params.set('token_prefix', targetPrefix);

      const url = params.toString() ? `/api/jwt/activities?${params.toString()}` : '/api/jwt/activities';
      const resp = await fetch(url);
      const data = await resp.json();
      const activities = data.activities || [];
      apiKeyActivitiesTbody.innerHTML = '';
      if (activities.length === 0) {
        apiKeyActivitiesTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No initial user request records found.</td></tr>';
        return;
      }
      activities.forEach(act => {
        const tr = document.createElement('tr');
        const isSuccess = (act.status || '').toLowerCase().includes('success');
        const isDenied = (act.status || '').toLowerCase().includes('denied') || (act.status || '').toLowerCase().includes('expired') || (act.status || '').toLowerCase().includes('failure') || (act.status || '').toLowerCase().includes('error');
        const badgeClass = isSuccess ? 'badge-user' : (isDenied ? 'badge-admin' : 'badge-editor');

        const rawTime = act.created_at || '';
        const localTime = formatToLocalTime(rawTime);

        tr.innerHTML = `
          <td>${escapeHtml(localTime)}</td>
          <td><strong>${escapeHtml(act.user_email || 'User')}</strong></td>
          <td><span style="color:#38bdf8;">${escapeHtml(act.domain || '-')}</span></td>
          <td><code>${escapeHtml(act.recipient || 'agents')}</code></td>
          <td><span class="badge badge-editor">${escapeHtml(act.request_type || act.action || 'User Request')}</span></td>
          <td><span class="badge ${badgeClass}">${escapeHtml(act.status || 'success')}</span></td>
          <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(act.details || '-')}">${escapeHtml(act.details || '-')}</td>
        `;
        apiKeyActivitiesTbody.appendChild(tr);
      });
    } catch (e) {
      apiKeyActivitiesTbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error loading JWT activities.</td></tr>';
    }
  }

  // Enhanced Context Evidence loader hook in chat and audit flow
  async function loadContextEvidence(convId) {
    if (!convId) return;
    try {
      const resp = await fetch(`/api/evidence/${encodeURIComponent(convId)}`);
      if (!resp.ok) return;
      const data = await resp.json();
      renderEvidence(data.retrieved_evidence || data);
    } catch (e) {
      console.warn("Failed to load context evidence:", e);
    }
  }

  // ---------------------------------------------------------------------------
  // Page 3: Agents Router Interface & Management
  // ---------------------------------------------------------------------------
  const agentsTbody = document.getElementById('agentsTbody');
  const statTotalAgents = document.getElementById('statTotalAgents');
  const statActiveAgents = document.getElementById('statActiveAgents');
  const statOfflineAgents = document.getElementById('statOfflineAgents');
  const statRoutingThreshold = document.getElementById('statRoutingThreshold');
  const routerThresholdInput = document.getElementById('routerThresholdInput');
  const btnSetThreshold = document.getElementById('btnSetThreshold');
  const thresholdStatusMsg = document.getElementById('thresholdStatusMsg');
  const btnRefreshAgents = document.getElementById('btnRefreshAgents');
  const btnOpenAddAgentModal = document.getElementById('btnOpenAddAgentModal');
  const addAgentModal = document.getElementById('addAgentModal');
  const btnCloseAddAgentModalX = document.getElementById('btnCloseAddAgentModalX');
  const btnCancelAddAgent = document.getElementById('btnCancelAddAgent');
  const btnSubmitAddAgent = document.getElementById('btnSubmitAddAgent');
  const addAgentAlertMsg = document.getElementById('addAgentAlertMsg');
  const btnTestRoute = document.getElementById('btnTestRoute');
  const testRouteInput = document.getElementById('testRouteInput');
  const testRouteResults = document.getElementById('testRouteResults');

  async function updateRoutingThreshold() {
    if (!routerThresholdInput) return;
    const val = parseFloat(routerThresholdInput.value);
    if (isNaN(val) || val < 0.0 || val > 1.0) {
      alert('Routing threshold must be a number between 0.0 and 1.0 (e.g. 0.50)');
      return;
    }
    try {
      const resp = await fetch('/api/router/threshold', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: val })
      });
      const res = await resp.json();
      if (resp.ok) {
        if (statRoutingThreshold) statRoutingThreshold.textContent = `${Math.round(res.threshold * 100)}%`;
        if (thresholdStatusMsg) {
          thresholdStatusMsg.style.display = 'inline';
          thresholdStatusMsg.textContent = 'Saved!';
          setTimeout(() => { thresholdStatusMsg.style.display = 'none'; }, 2500);
        }
        await loadAgentsData();
      } else {
        alert(`Failed to set threshold: ${res.message || 'Error'}`);
      }
    } catch (e) {
      alert(`Error updating threshold: ${e.message}`);
    }
  }

  if (btnSetThreshold) {
    btnSetThreshold.addEventListener('click', updateRoutingThreshold);
  }
  if (routerThresholdInput) {
    routerThresholdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        updateRoutingThreshold();
      }
    });
  }

  async function loadAgentsData() {
    if (!agentsTbody) return;
    try {
      const resp = await fetch('/api/router/agents');
      if (!resp.ok) {
        agentsTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Agents Router service initializing...</td></tr>';
        return;
      }
      const data = await resp.json();
      const agents = data.agents || [];

      // Update threshold display and input
      if (typeof data.threshold === 'number') {
        const pct = Math.round(data.threshold * 100);
        if (statRoutingThreshold) statRoutingThreshold.textContent = `${pct}%`;
        if (routerThresholdInput && document.activeElement !== routerThresholdInput) {
          routerThresholdInput.value = data.threshold.toFixed(2);
        }
      }

      // Update statistics
      let activeCount = 0;
      let offlineCount = 0;
      agents.forEach(a => {
        if (a.status === 'up') activeCount++;
        else offlineCount++;
      });

      if (statTotalAgents) statTotalAgents.textContent = agents.length;
      if (statActiveAgents) statActiveAgents.textContent = activeCount;
      if (statOfflineAgents) statOfflineAgents.textContent = offlineCount;

      agentsTbody.innerHTML = '';
      if (agents.length === 0) {
        agentsTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No agents registered in router.</td></tr>';
        return;
      }

      agents.forEach(agent => {
        const tr = document.createElement('tr');
        const isUp = (agent.status === 'up');
        const isDefault = agent.is_default;

        const statusBadge = isUp 
          ? `<span class="badge badge-active" style="display:inline-flex; align-items:center; gap:5px; font-weight:700;"><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#10b981;"></span> UP (Active)</span>`
          : `<span class="badge badge-locked" style="display:inline-flex; align-items:center; gap:5px; font-weight:700;"><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#ef4444;"></span> DOWN (Offline)</span>`;

        const typeBadge = isDefault
          ? `<span class="badge" style="background:#065f46; color:#a7f3d0; border:1px solid #10b981;">🛡️ Default Fallback</span>`
          : `<span class="badge" style="background:#581c87; color:#e9d5ff; border:1px solid #a855f7;">⚡ Specialized</span>`;

        // Format sample prompts preview
        let sampleTags = '';
        if (agent.sample_prompts && agent.sample_prompts.length > 0) {
          const previewPrompts = agent.sample_prompts.slice(0, 3);
          sampleTags = '<div style="margin-top:4px; display:flex; flex-wrap:wrap; gap:4px;">' + 
            previewPrompts.map(p => `<span style="font-size:0.73rem; background:#1e293b; color:#94a3b8; padding:2px 6px; border-radius:4px; border:1px solid #334155;" title="${escapeHtml(p)}">${escapeHtml(p.length > 45 ? p.substring(0, 42) + '...' : p)}</span>`).join('') +
            (agent.sample_prompts.length > 3 ? `<span style="font-size:0.73rem; color:#64748b;">+${agent.sample_prompts.length - 3} more</span>` : '') +
            '</div>';
        }

        tr.innerHTML = `
          <td>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:1.2rem;">${isDefault ? '🤖' : '🛠️'}</span>
              <div>
                <strong style="color:#f8fafc; font-size:0.9rem;">${escapeHtml(agent.name)}</strong>
                <div style="font-family:var(--font-mono); font-size:0.75rem; color:#64748b;">ID: ${escapeHtml(agent.id)}</div>
              </div>
            </div>
          </td>
          <td>${statusBadge}</td>
          <td>${typeBadge}</td>
          <td><code style="background:#0f172a; padding:4px 8px; border-radius:4px; font-size:0.78rem; border:1px solid #334155; color:#38bdf8;">${escapeHtml(agent.url)}</code></td>
          <td style="max-width:320px;">
            <div style="font-size:0.83rem; color:#cbd5e1; line-height:1.3;">${escapeHtml(agent.description)}</div>
            ${sampleTags}
          </td>
          <td style="text-align:center;">
            <span class="badge" style="background:#1e293b; color:#38bdf8; font-weight:600;">${agent.queries_handled || 0}</span>
          </td>
          <td style="text-align:right;">
            <div style="display:inline-flex; gap:6px; align-items:center;">
              <button class="btn-secondary btn-agent-status" data-id="${escapeHtml(agent.id)}" data-status="${escapeHtml(agent.status)}" style="padding:4px 8px; font-size:0.78rem;" title="Toggle operational status">
                ${isUp ? 'Turn DOWN' : 'Turn UP'}
              </button>
              <button class="btn-secondary btn-agent-health" data-id="${escapeHtml(agent.id)}" style="padding:4px 8px; font-size:0.78rem;" title="Ping container health">
                🏥 Ping
              </button>
              ${!isDefault ? `
                <button class="btn-danger btn-agent-delete" data-id="${escapeHtml(agent.id)}" style="padding:4px 8px; font-size:0.78rem;" title="Unregister agent">
                  🗑️
                </button>
              ` : ''}
            </div>
          </td>
        `;

        // Wire actions
        const btnStatus = tr.querySelector('.btn-agent-status');
        if (btnStatus) {
          btnStatus.onclick = () => toggleAgentStatus(agent.id, agent.status);
        }
        const btnHealth = tr.querySelector('.btn-agent-health');
        if (btnHealth) {
          btnHealth.onclick = () => checkAgentHealth(agent.id);
        }
        const btnDelete = tr.querySelector('.btn-agent-delete');
        if (btnDelete) {
          btnDelete.onclick = () => deleteAgent(agent.id, agent.name);
        }

        agentsTbody.appendChild(tr);
      });
    } catch (e) {
      console.error('Error loading agents data:', e);
      if (agentsTbody) agentsTbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error connecting to agents router.</td></tr>';
    }
  }

  async function toggleAgentStatus(agentId, currentStatus) {
    const nextStatus = (currentStatus === 'up') ? 'down' : 'up';
    try {
      const resp = await fetch(`/api/router/agents/${encodeURIComponent(agentId)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus })
      });
      const res = await resp.json();
      if (resp.ok) {
        loadAgentsData();
      } else {
        alert(`Failed to update status: ${res.message || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`Error toggling agent status: ${e.message}`);
    }
  }

  async function checkAgentHealth(agentId) {
    try {
      const resp = await fetch(`/api/router/agents/${encodeURIComponent(agentId)}/health`, { method: 'POST' });
      const data = await resp.json();
      if (data.status === 'healthy') {
        alert(`✅ Agent '${agentId}' is healthy and responding (HTTP ${data.code || 200}).`);
      } else {
        alert(`⚠️ Agent '${agentId}' health check reported: ${data.status} ${data.error ? '(' + data.error + ')' : ''}`);
      }
      loadAgentsData();
    } catch (e) {
      alert(`Health ping failed for agent '${agentId}': ${e.message}`);
    }
  }

  async function deleteAgent(agentId, agentName) {
    if (!confirm(`Are you sure you want to unregister agent '${agentName}' (${agentId}) from the router?`)) return;
    try {
      const resp = await fetch(`/api/router/agents/${encodeURIComponent(agentId)}`, { method: 'DELETE' });
      const res = await resp.json();
      if (resp.ok) {
        loadAgentsData();
      } else {
        alert(`Failed to remove agent: ${res.message}`);
      }
    } catch (e) {
      alert(`Error unregistering agent: ${e.message}`);
    }
  }

  // Modal Handlers for Add Agent
  if (btnOpenAddAgentModal) {
    btnOpenAddAgentModal.onclick = () => {
      if (addAgentAlertMsg) addAgentAlertMsg.classList.add('hidden');
      const inputId = document.getElementById('inputNewAgentId');
      const inputName = document.getElementById('inputNewAgentName');
      const inputUrl = document.getElementById('inputNewAgentUrl');
      const inputDesc = document.getElementById('inputNewAgentDesc');
      const inputPrompts = document.getElementById('inputNewAgentPrompts');
      if (inputId) inputId.value = '';
      if (inputName) inputName.value = '';
      if (inputUrl) inputUrl.value = '';
      if (inputDesc) inputDesc.value = '';
      if (inputPrompts) inputPrompts.value = '';
      if (addAgentModal) addAgentModal.classList.remove('hidden');
    };
  }

  function closeAddAgentModal() {
    if (addAgentModal) addAgentModal.classList.add('hidden');
  }

  if (btnCloseAddAgentModalX) btnCloseAddAgentModalX.onclick = closeAddAgentModal;
  if (btnCancelAddAgent) btnCancelAddAgent.onclick = closeAddAgentModal;

  if (btnSubmitAddAgent) {
    btnSubmitAddAgent.onclick = async () => {
      const inputId = document.getElementById('inputNewAgentId');
      const inputName = document.getElementById('inputNewAgentName');
      const inputUrl = document.getElementById('inputNewAgentUrl');
      const inputDesc = document.getElementById('inputNewAgentDesc');
      const inputPrompts = document.getElementById('inputNewAgentPrompts');
      const selectStatus = document.getElementById('selectNewAgentStatus');

      const id = inputId ? inputId.value.trim() : '';
      const name = inputName ? inputName.value.trim() : '';
      const url = inputUrl ? inputUrl.value.trim() : '';
      const description = inputDesc ? inputDesc.value.trim() : '';
      const promptsRaw = inputPrompts ? inputPrompts.value.trim() : '';
      const status = selectStatus ? selectStatus.value : 'up';

      if (!id || !name || !url) {
        if (addAgentAlertMsg) {
          addAgentAlertMsg.textContent = 'Please provide Agent ID, Display Name, and Container URL.';
          addAgentAlertMsg.classList.remove('hidden');
        }
        return;
      }

      const sample_prompts = promptsRaw ? promptsRaw.split('\n').map(p => p.trim()).filter(Boolean) : [];

      try {
        const resp = await fetch('/api/router/agents/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            id: id,
            name: name,
            url: url,
            description: description,
            sample_prompts: sample_prompts,
            status: status,
            is_default: false
          })
        });
        const res = await resp.json();
        if (resp.ok) {
          closeAddAgentModal();
          loadAgentsData();
        } else {
          if (addAgentAlertMsg) {
            addAgentAlertMsg.textContent = res.message || 'Registration failed.';
            addAgentAlertMsg.classList.remove('hidden');
          }
        }
      } catch (e) {
        if (addAgentAlertMsg) {
          addAgentAlertMsg.textContent = `Network error: ${e.message}`;
          addAgentAlertMsg.classList.remove('hidden');
        }
      }
    };
  }

  if (btnRefreshAgents) {
    btnRefreshAgents.onclick = () => loadAgentsData();
  }

  // Test Semantic Route Execution
  async function testSemanticRoute() {
    if (!testRouteInput || !testRouteResults) return;
    const query = testRouteInput.value.trim();
    if (!query) {
      alert('Please enter a query to test semantic routing.');
      return;
    }

    testRouteResults.style.display = 'block';
    testRouteResults.innerHTML = '<div style="color:#94a3b8; font-size:0.9rem;">Computing semantic vector embeddings and matching agents...</div>';

    try {
      const resp = await fetch('/api/router/test_route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query })
      });
      const data = await resp.json();
      if (!resp.ok) {
        testRouteResults.innerHTML = `<div style="color:#ef4444;">Routing test failed: ${escapeHtml(data.message || 'Error')}</div>`;
        return;
      }

      const isFallback = data.is_default_fallback;
      const topAgent = data.selected_agent;
      const scorePct = data.similarity_percent || '0%';
      const ranked = data.ranked_scores || [];

      let outcomeBadge = isFallback
        ? `<span class="badge" style="background:#065f46; color:#a7f3d0; font-size:0.85rem; padding:4px 8px;">🛡️ Default Fallback (< 50% match or specialist offline)</span>`
        : `<span class="badge" style="background:#0284c7; color:#f0f9ff; font-size:0.85rem; padding:4px 8px;">✅ Matched Specialized Agent (> 50% Threshold)</span>`;

      let rankedRows = ranked.map((r, idx) => {
        const isWinner = (topAgent && r.agent_id === topAgent.id);
        const barWidth = Math.max(0, Math.min(100, Math.round(r.score * 100)));
        return `
          <tr style="${isWinner ? 'background:rgba(56, 189, 248, 0.12);' : ''}">
            <td style="font-weight:${isWinner ? '700' : '400'}; color:${isWinner ? '#38bdf8' : '#e2e8f0'};">
              ${isWinner ? '👉 ' : ''}${escapeHtml(r.agent_name)} 
              <span style="font-size:0.75rem; color:#64748b;">(${escapeHtml(r.agent_id)})</span>
            </td>
            <td>
              <span class="badge ${r.status === 'up' ? 'badge-active' : 'badge-locked'}" style="font-size:0.75rem;">
                ${escapeHtml(r.status.toUpperCase())}
              </span>
            </td>
            <td>
              <div style="display:flex; align-items:center; gap:8px;">
                <div style="flex:1; background:#1e293b; height:8px; border-radius:4px; overflow:hidden;">
                  <div style="width:${barWidth}%; background:${barWidth >= 50 ? '#10b981' : '#f59e0b'}; height:100%;"></div>
                </div>
                <span style="font-family:var(--font-mono); font-weight:600; font-size:0.85rem; color:${barWidth >= 50 ? '#34d399' : '#fbbf24'}; width:50px; text-align:right;">
                  ${r.similarity_percent}
                </span>
              </div>
            </td>
            <td>${r.is_default ? '<span style="color:#10b981; font-size:0.8rem;">Yes (Default)</span>' : '<span style="color:#a78bfa; font-size:0.8rem;">Specialized</span>'}</td>
          </tr>
        `;
      }).join('');

      testRouteResults.innerHTML = `
        <div style="margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <div>
            <span style="font-size:0.85rem; color:#94a3b8;">Routing Decision:</span>
            <strong style="color:#ffffff; font-size:1.05rem; margin-left:6px;">${topAgent ? escapeHtml(topAgent.name) : 'None'}</strong>
            <span style="color:#38bdf8; font-family:var(--font-mono); font-size:0.85rem; margin-left:8px;">Score: ${scorePct}</span>
          </div>
          <div>${outcomeBadge}</div>
        </div>
        <p style="font-size:0.84rem; color:#cbd5e1; margin-bottom:14px; background:#1e293b; padding:8px 12px; border-radius:6px; border-left:3px solid #38bdf8;">
          💡 <strong>Explanation:</strong> ${escapeHtml(data.explanation || '')} <span style="color:#64748b; font-size:0.75rem;">(Routing Latency: ${data.routing_latency_ms || 0}ms)</span>
        </p>
        <div style="font-size:0.82rem; font-weight:600; color:#94a3b8; margin-bottom:6px;">Agent Similarity Breakdown:</div>
        <table class="data-table" style="font-size:0.82rem;">
          <thead>
            <tr>
              <th>Agent</th>
              <th style="width:100px;">Status</th>
              <th style="width:200px;">Similarity Match</th>
              <th style="width:120px;">Role</th>
            </tr>
          </thead>
          <tbody>${rankedRows}</tbody>
        </table>
      `;
    } catch (e) {
      testRouteResults.innerHTML = `<div style="color:#ef4444;">Error testing semantic route: ${escapeHtml(e.message)}</div>`;
    }
  }

  if (btnTestRoute) {
    btnTestRoute.onclick = testSemanticRoute;
  }
  if (testRouteInput) {
    testRouteInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') testSemanticRoute();
    });
  }

  // Initial Data Load
  loadModelsAndSkills();
  loadContainers();
  loadAgentsData();

  // Auto-refresh active view every 15 seconds so data updates in real-time
  setInterval(() => {
    if (currentActiveTab === 'page-telemetry') {
      loadTelemetryData();
    } else if (currentActiveTab === 'page-audit') {
      loadAuditLogs();
    } else if (currentActiveTab === 'page-agents') {
      loadAgentsData();
    }
  }, 15000);
});

