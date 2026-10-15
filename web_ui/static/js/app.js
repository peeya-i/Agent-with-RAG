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
  const eventFilterSelect = document.getElementById('eventFilterSelect');
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
      } else if (targetId === 'page-semantic-lab') {
        if (typeof loadSemanticLabData === 'function') loadSemanticLabData();
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
  if (btnShutdown) {
    btnShutdown.addEventListener('click', () => {
      shutdownConfirmInput.value = '';
      btnConfirmShutdown.disabled = true;
      shutdownModal.classList.remove('hidden');
      shutdownConfirmInput.focus();
    });
  }

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

  // ---------------------------------------------------------------------------
  // Per-User Preferences Management (Chat parameters & Routing Threshold)
  // ---------------------------------------------------------------------------
  function getActiveUserEmail() {
    if (currentUser && currentUser.email) return currentUser.email;
    const stored = sessionStorage.getItem('currentUser');
    if (stored) {
      try {
        const u = JSON.parse(stored);
        if (u && u.email) return u.email;
      } catch (e) {}
    }
    return null;
  }

  function getCurrentPreferences() {
    const prefs = {};
    if (chatMaxTokens) prefs.max_tokens = parseInt(chatMaxTokens.value) || 2048;
    if (chatTemperature) prefs.temperature = parseFloat(chatTemperature.value) || 0.7;
    if (agentChoice) prefs.agent = agentChoice.value;
    if (chatMaxTurns) prefs.max_turns = parseInt(chatMaxTurns.value) || 5;
    if (chatRagChunks) prefs.max_chunks = parseInt(chatRagChunks.value) || 5;
    if (docThresholdInput) prefs.doc_threshold = parseFloat(docThresholdInput.value) || 0.3;
    if (chatSkills) prefs.skill_selector = chatSkills.value;
    if (chatSkillThreshold) prefs.skill_threshold = parseFloat(chatSkillThreshold.value) || 0.2;
    const rInput = document.getElementById('routerThresholdInput');
    if (rInput) prefs.router_threshold = parseFloat(rInput.value) || 0.50;
    return prefs;
  }

  async function applyUserPreferences(prefs) {
    if (!prefs || typeof prefs !== 'object') return;
    if (prefs.max_tokens !== undefined && chatMaxTokens) {
      chatMaxTokens.value = prefs.max_tokens;
    }
    if (prefs.temperature !== undefined && chatTemperature) {
      chatTemperature.value = prefs.temperature;
    }
    if (prefs.agent && agentChoice) {
      if (prefs.agent === 'Google ADK LlmAgent' || prefs.agent === 'Google ADK Agent') {
        agentChoice.value = 'Google ADK Agent';
      } else if (prefs.agent === 'Custom Agent') {
        agentChoice.value = 'Custom Agent';
      } else {
        agentChoice.value = prefs.agent;
      }
    }
    if (prefs.max_turns !== undefined && chatMaxTurns) {
      chatMaxTurns.value = prefs.max_turns;
    }
    if (prefs.max_chunks !== undefined && chatRagChunks) {
      chatRagChunks.value = String(prefs.max_chunks);
    } else if (prefs.rag_chunks !== undefined && chatRagChunks) {
      chatRagChunks.value = String(prefs.rag_chunks);
    }
    if (prefs.doc_threshold !== undefined && docThresholdInput) {
      docThresholdInput.value = parseFloat(prefs.doc_threshold).toFixed(2);
    }
    if (prefs.skill_selector && chatSkills) {
      chatSkills.value = prefs.skill_selector;
      if (chatSkills.value === 'Vector Store Selects' || chatSkills.value === 'Vector Store') {
        skillThresholdBox?.classList.remove('hidden');
      } else {
        skillThresholdBox?.classList.add('hidden');
      }
    } else if (prefs.skill_mode && chatSkills) {
      chatSkills.value = prefs.skill_mode;
      if (chatSkills.value === 'Vector Store Selects' || chatSkills.value === 'Vector Store') {
        skillThresholdBox?.classList.remove('hidden');
      } else {
        skillThresholdBox?.classList.add('hidden');
      }
    }
    if (prefs.skill_threshold !== undefined && chatSkillThreshold) {
      chatSkillThreshold.value = parseFloat(prefs.skill_threshold).toFixed(2);
    }
    const rThreshVal = prefs.router_threshold !== undefined ? prefs.router_threshold : prefs.min_routing_threshold;
    if (rThreshVal !== undefined) {
      const val = parseFloat(rThreshVal);
      if (!isNaN(val)) {
        const rInput = document.getElementById('routerThresholdInput');
        if (rInput) rInput.value = val.toFixed(2);
        const rStat = document.getElementById('statRoutingThreshold');
        if (rStat) rStat.textContent = `${Math.round(val * 100)}%`;
        try {
          await fetch('/api/router/threshold', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ threshold: val })
          });
        } catch (e) {
          console.warn('Failed syncing router threshold preference:', e);
        }
      }
    }
  }

  let prefSaveTimeout = null;
  function saveUserPreferences(partial = {}) {
    const email = getActiveUserEmail();
    if (!email) return;
    clearTimeout(prefSaveTimeout);
    prefSaveTimeout = setTimeout(async () => {
      const current = getCurrentPreferences();
      const merged = { ...current, ...partial };
      try {
        localStorage.setItem(`user_prefs_${email}`, JSON.stringify(merged));
      } catch (e) {}
      try {
        await fetch('/api/user/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(merged)
        });
      } catch (err) {
        console.warn('Failed saving user preferences to server:', err);
      }
    }, 400);
  }

  async function loadUserPreferencesForUser(email, preloadedPrefs = null) {
    if (!email) return;
    let prefs = preloadedPrefs;
    if (!prefs || Object.keys(prefs).length === 0) {
      try {
        const resp = await fetch('/api/user/preferences');
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.preferences && Object.keys(data.preferences).length > 0) {
            prefs = data.preferences;
          }
        }
      } catch (e) {}
    }
    if (!prefs || Object.keys(prefs).length === 0) {
      try {
        const cached = localStorage.getItem(`user_prefs_${email}`);
        if (cached) prefs = JSON.parse(cached);
      } catch (e) {}
    }
    if (prefs && Object.keys(prefs).length > 0) {
      try {
        localStorage.setItem(`user_prefs_${email}`, JSON.stringify(prefs));
      } catch (e) {}
      await applyUserPreferences(prefs);
    }
  }

  // Auto-save listeners on Chat Page controls
  [chatMaxTokens, chatTemperature, agentChoice, chatMaxTurns, chatRagChunks, docThresholdInput, chatSkills, chatSkillThreshold].forEach(el => {
    if (el) {
      el.addEventListener('change', () => saveUserPreferences());
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
  // Conversational session history and router metadata state
  let chatSessionHistory = [];
  let lastRouterMetadata = null;
  let activeChatConversationId = 'conv_' + Date.now();
  window.activeChatConversationId = activeChatConversationId;
  window.currentActiveConversationId = activeChatConversationId;

  // Helper to start fresh chat session
  function startNewChatSession() {
    chatSessionHistory = [];
    lastRouterMetadata = null;
    activeChatConversationId = 'conv_' + Date.now();
    window.activeChatConversationId = activeChatConversationId;
    window.currentActiveConversationId = activeChatConversationId;
    if (chatMessages) {
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
          if (chatInput) chatInput.value = btn.getAttribute('data-prompt');
          sendMessage();
        });
      });
    }
    if (typeof renderEvidence === 'function') {
      renderEvidence({}, null);
    }
    if (chatInput) {
      chatInput.value = '';
    }
  }
  window.startNewChatSession = startNewChatSession;

  function clearTestSemanticPrompts() {
    const testInput = document.getElementById('testRouteInput');
    const testResults = document.getElementById('testRouteResults');
    if (testInput) testInput.value = '';
    if (testResults) {
      testResults.innerHTML = '';
      testResults.style.display = 'none';
    }
  }
  window.clearTestSemanticPrompts = clearTestSemanticPrompts;

  // New Session button to clear context and start new chat
  const btnNewChatSession = document.getElementById('btnNewChatSession');
  if (btnNewChatSession) {
    btnNewChatSession.addEventListener('click', () => {
      startNewChatSession();
      if (chatInput) chatInput.focus();
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
      if (!activeChatConversationId) {
        activeChatConversationId = 'conv_' + Date.now();
        window.activeChatConversationId = activeChatConversationId;
        window.currentActiveConversationId = activeChatConversationId;
      }
      const activeConvId = activeChatConversationId;

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

      const data = await res.json().catch(() => ({}));

      // Detect error status code or error response
      if (!res.ok || data.status === 'error' || (data.error && !data.response)) {
        let isJwtExpired = false;

        // 1. Check client-side token expiration from sessionStorage
        if (jwtToken) {
          try {
            const parts = jwtToken.split('.');
            if (parts.length === 3) {
              const payloadObj = JSON.parse(atob(parts[1]));
              if (payloadObj.exp && (Date.now() / 1000) > payloadObj.exp) {
                isJwtExpired = true;
              }
            }
          } catch (e) {}
        }

        // 2. Check server error flags / payload
        const errText = (data.error || data.reason || data.message || '').toString();
        if (data.is_jwt_expired || errText.toLowerCase().includes('expired') || (res.status === 403 && (errText.toLowerCase().includes('jwt') || errText.toLowerCase().includes('token') || errText.toLowerCase().includes('authorization')))) {
          isJwtExpired = true;
        }

        let errMsg = data.error || data.reason || data.message || `Request failed with status ${res.status}`;
        if (isJwtExpired) {
          errMsg = 'Your authentication JWT has expired. Please log out and log back in to renew your session.';
        }

        const err = new Error(errMsg);
        err.isJwtExpired = isJwtExpired;
        err.statusCode = res.status;
        throw err;
      }

      // Track assistant response in session history
      if (data.response) {
        chatSessionHistory.push({ role: 'model', content: data.response });
      }

      // Update pending bubble with full response and detail box
      updateAgentBubble(pendingAgentBubble, data);

      if (data.conversation_id) {
        activeChatConversationId = data.conversation_id;
        window.activeChatConversationId = data.conversation_id;
        window.currentActiveConversationId = data.conversation_id;
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
      const bubble = pendingAgentBubble.querySelector('.message-bubble');
      bubble.style.borderColor = 'rgba(239, 68, 68, 0.7)';
      bubble.style.backgroundColor = 'rgba(239, 68, 68, 0.08)';
      bubble.style.color = '#fecaca';

      if (err.isJwtExpired) {
        bubble.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px; color:#ef4444; font-weight:600; font-size:0.95rem;">
              <span style="font-size:1.2rem;">⚠️</span> Authentication Error (HTTP 403)
            </div>
            <div style="font-size:0.9rem; line-height:1.4;">
              <strong>JWT Token Expired:</strong> Your authentication token has expired.
            </div>
            <div style="font-size:0.85rem; color:#fca5a5;">
              Please log in again to renew your session and continue chatting with agents.
            </div>
            <div style="margin-top:4px;">
              <button type="button" class="btn btn-sm btn-primary" onclick="window.location.reload();" style="padding:5px 14px; font-size:0.82rem; background:linear-gradient(135deg,#ef4444,#dc2626); border:none; cursor:pointer; border-radius:4px; color:#fff; font-weight:500;">
                🔄 Refresh &amp; Re-login
              </button>
            </div>
          </div>
        `;
      } else {
        bubble.innerHTML = `
          <div style="display:flex; align-items:flex-start; gap:8px;">
            <span style="font-size:1.1rem; color:#ef4444;">⚠️</span>
            <div>
              <div style="color:#ef4444; font-weight:600; font-size:0.9rem;">Request Failed:</div>
              <div style="margin-top:3px; font-size:0.88rem; line-height:1.4;">${escapeHtml(err.message)}</div>
            </div>
          </div>
        `;
      }
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
          const isGlobalAdmin = (currentUser && currentUser.role === 'Admin' && (!currentUser.domain || currentUser.domain === 'Global'));
          const userDomain = (currentUser && currentUser.domain) ? currentUser.domain.trim().toLowerCase() : '';
          const userRole = currentUser ? (currentUser.role || 'User') : 'User';
          const isOrgAdminOrEditor = (currentUser && (currentUser.role === 'Admin' || currentUser.role === 'Editor') && !!currentUser.domain);

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

            const isEntryGlobal = (!domain || domain === 'Global (All)' || domain === 'All Tenants (Admin)' || domain.toLowerCase() === 'global');
            let canDeleteThis = false;
            let deleteTitle = '';

            if (isGlobalAdmin) {
              canDeleteThis = true;
              deleteTitle = `Delete ${type} '${escapeHtml(name)}'`;
            } else if (isEntryGlobal) {
              canDeleteThis = false;
              deleteTitle = 'Only Global Admin can delete entries from Global Vector DB';
            } else {
              if (isOrgAdminOrEditor && userDomain === (domain || '').trim().toLowerCase()) {
                canDeleteThis = true;
                deleteTitle = `Delete organization ${type} '${escapeHtml(name)}'`;
              } else {
                canDeleteThis = false;
                deleteTitle = 'Only Admin and Editor roles for this organization can delete this entry';
              }
            }

            return `
            <tr>
              <td>${typeBadge}</td>
              <td><strong>${escapeHtml(name)}</strong></td>
              <td>${domainBadge}</td>
              <td>${chunks}</td>
              <td>${chars.toLocaleString()}</td>
              <td>
                <button class="btn-table-delete" data-doc="${escapeHtml(name)}" data-type="${escapeHtml(type.toLowerCase())}"
                  ${!canDeleteThis ? 'disabled' : ''}
                  title="${escapeHtml(deleteTitle)}"
                  style="${!canDeleteThis ? 'opacity:0.35; cursor:not-allowed;' : ''}">Delete</button>
              </td>
            </tr>
          `;
          }).join('');

          // Bind delete buttons
          ingestedDocsTbody.querySelectorAll('.btn-table-delete').forEach(btn => {
            btn.addEventListener('click', async () => {
              if (btn.disabled) return;
              const docName = btn.getAttribute('data-doc');
              const docType = btn.getAttribute('data-type') || 'document';
              if (confirm(`Delete ${docType} '${docName}' from vector store?`)) {
                try {
                  const delRes = await fetch(`/api/vectordb/document?doc_name=${encodeURIComponent(docName)}&type=${encodeURIComponent(docType)}`, { method: 'DELETE' });
                  if (!delRes.ok) {
                    const errJson = await delRes.json().catch(() => ({}));
                    alert(errJson.error || `Failed to delete ${docType} '${docName}'`);
                  }
                } catch (e) {
                  alert('Error deleting document: ' + e.message);
                }
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
    ingestSpinner.innerHTML = '<span class="spinner-icon">⏳</span> Ingesting content... 0%';
    storageStatusBanner.innerHTML = `
      <div class="ingest-progress-container">
        <div class="ingest-progress-header">
          <span class="status-indicator-busy">⏳ Ingestion in progress: 0%</span>
          <span class="ingest-pct-badge" style="color: #38bdf8;">0%</span>
        </div>
        <div class="ingest-progress-bar">
          <div class="ingest-progress-fill" style="width: 0%;"></div>
        </div>
      </div>
    `;

    // Poll ingestion progress every 500ms
    let progressTimer = setInterval(async () => {
      try {
        const pRes = await fetch('/api/vectordb/ingest_progress');
        if (pRes.ok) {
          const pData = await pRes.json();
          const p = pData.progress || {};
          if (p.active) {
            const pct = Math.min(100, Math.max(0, p.percent || 0));
            const msg = p.message || `Ingesting documents: ${pct}%`;
            ingestSpinner.innerHTML = `<span class="spinner-icon">⏳</span> Ingesting... ${pct}%`;
            storageStatusBanner.innerHTML = `
              <div class="ingest-progress-container">
                <div class="ingest-progress-header">
                  <span class="status-indicator-busy">⏳ ${escapeHtml(msg)}</span>
                  <span class="ingest-pct-badge" style="color: #38bdf8;">${pct}%</span>
                </div>
                <div class="ingest-progress-bar">
                  <div class="ingest-progress-fill" style="width: ${pct}%;"></div>
                </div>
              </div>
            `;
          }
        }
      } catch (e) {
        // ignore polling error
      }
    }, 500);

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

      clearInterval(progressTimer);
      storageStatusBanner.innerHTML = `
        <div class="ingest-progress-container">
          <div class="ingest-progress-header">
            <span class="status-indicator-idle" style="color: #4ade80;">✅ Ingestion complete: 100%</span>
            <span class="ingest-pct-badge" style="color: #4ade80;">100%</span>
          </div>
          <div class="ingest-progress-bar">
            <div class="ingest-progress-fill" style="width: 100%; background: #4ade80;"></div>
          </div>
        </div>
      `;

      alert(data.message || 'Ingestion complete!');
      ingestSourceInput.value = '';
      loadIngestionData();
      setTimeout(() => {
        storageStatusBanner.innerHTML = '<span class="status-indicator-idle">Idle (Ready)</span>';
      }, 2500);
    } catch (err) {
      clearInterval(progressTimer);
      alert(`Ingestion error: ${err.message}`);
      storageStatusBanner.innerHTML = '<span class="status-indicator-idle">Idle (Ready)</span>';
    } finally {
      clearInterval(progressTimer);
      btnPopulateDb.disabled = false;
      ingestSpinner.classList.add('hidden');
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

  // Refresh Embedders button
  const btnRefreshEmbedders = document.getElementById('btnRefreshEmbedders');
  if (btnRefreshEmbedders) {
    btnRefreshEmbedders.addEventListener('click', async () => {
      btnRefreshEmbedders.style.transform = 'rotate(360deg)';
      btnRefreshEmbedders.style.transition = 'transform 0.5s ease';
      try {
        await loadIngestionData();
      } finally {
        setTimeout(() => {
          btnRefreshEmbedders.style.transform = '';
          btnRefreshEmbedders.style.transition = '';
        }, 500);
      }
    });
  }

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
        conversationsTbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No conversations recorded yet.</td></tr>`;
        eventsTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No conversation events to display.</td></tr>`;
        selectedConvBadge.textContent = 'None Selected';
        return;
      }

      conversationsTbody.innerHTML = currentConversationsCache.map(c => {
        const rawTs = c.local_timestamp || c.timestamp || c.last_seen || c.first_seen || '';
        const localTs = formatToLocalTime(rawTs);
        const evCount = c.event_count !== undefined ? c.event_count : (c.events_count || 0);
        const userName = c.user || c.username || 'anonymous';
        const modelBadge = c.model ? `<span class="badge" style="background:#1e1b4b; color:#c084fc; font-size:0.75rem; font-weight:600;">${escapeHtml(c.model)}</span>` : `<span style="color:var(--text-muted);font-size:0.75rem;">-</span>`;
        return `
        <tr class="conv-row ${c.conversation_id === selectedConversationId ? 'selected-row' : ''}" data-cid="${escapeHtml(c.conversation_id)}">
          <td><span style="font-family:var(--font-mono);font-size:0.75rem;">${escapeHtml(localTs)}</span></td>
          <td><code style="color:#a5b4fc;">${escapeHtml(c.conversation_id)}</code></td>
          <td><span class="badge" style="background:#4338ca;color:#e0e7ff;font-size:0.75rem;">${escapeHtml(userName)}</span></td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(c.user_query || '')}</td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(c.agent_response || '')}</td>
          <td><span class="badge" style="background:#0f172a; border:1px solid #3b82f6; color:#93c5fd;">${escapeHtml(c.agent_type || 'Custom Agent')}</span></td>
          <td>${modelBadge}</td>
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

      // Auto-select first (newest) conversation if none selected, or keep selected if exists
      const targetCid = selectedConversationId && currentConversationsCache.some(c => c.conversation_id === selectedConversationId)
        ? selectedConversationId
        : (currentConversationsCache.length > 0 ? currentConversationsCache[0].conversation_id : null);

      if (targetCid) {
        selectConversation(targetCid);
      }

    } catch (e) {
      console.error('Failed to load audit logs:', e);
    }
  }

  function renderEventsTable() {
    if (!currentEventsCache || currentEventsCache.length === 0) {
      eventsTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No events recorded for this conversation.</td></tr>`;
      return;
    }

    const filterVal = eventFilterSelect ? eventFilterSelect.value : 'all';
    const filtered = currentEventsCache.filter(evt => {
      if (filterVal === 'all') return true;
      const type = (evt.event_type || evt.type || '').toLowerCase();
      const invoker = (evt.invoker || '').toLowerCase();
      const target = (evt.target || evt.recipient || '').toLowerCase();
      if (filterVal === 'agents_router') {
        return invoker.includes('router') || target.includes('router') || type.includes('router');
      }
      if (filterVal === 'llm') {
        return invoker.includes('llm') || target.includes('llm') || type.includes('llm');
      }
      if (filterVal === 'tools') {
        return invoker.includes('tool') || target.includes('tool') || type.includes('tool');
      }
      if (filterVal === 'rag') {
        return invoker.includes('rag') || target.includes('rag') || invoker.includes('vector') || target.includes('vector') || type.includes('vector') || type.includes('embedding');
      }
      return true;
    });

    if (filtered.length === 0) {
      eventsTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No events matching component filter '${escapeHtml(filterVal)}'.</td></tr>`;
      return;
    }

    eventsTbody.innerHTML = filtered.map((evt) => {
      const origIdx = currentEventsCache.indexOf(evt);
      const rawTime = evt.local_time || evt.raw_timestamp || evt.timestamp || '';
      const localTime = formatToLocalTime(rawTime);
      const eventType = evt.event_type || evt.type || 'generic';
      const invoker = evt.invoker || 'unknown';
      const target = evt.target || evt.recipient || 'unknown';
      const model = evt.model || '-';
      const desc = evt.short_description || '';
      const isRouter = invoker.includes('router') || target.includes('router') || eventType.includes('router');
      const rowStyle = isRouter ? 'background:rgba(219, 39, 119, 0.12); font-weight:600;' : '';
      return `
        <tr class="event-row ${isRouter ? 'router-event-highlight' : ''}" data-idx="${origIdx}" style="${rowStyle}">
          <td><span style="font-family:var(--font-mono);font-size:0.75rem;">${escapeHtml(localTime)}</span></td>
          <td><span class="step-bubble ${eventType.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(eventType)}</span></td>
          <td><strong>${escapeHtml(invoker)}</strong></td>
          <td>${escapeHtml(target)}</td>
          <td><span class="badge" style="background:#1e1b4b; color:#c084fc; font-size:0.75rem; font-weight:600;">${escapeHtml(model)}</span></td>
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
  }

  if (eventFilterSelect) {
    eventFilterSelect.onchange = renderEventsTable;
  }

  async function selectConversation(cid) {
    selectedConversationId = cid;
    // Isolated audit logs selection - does NOT change activeChatConversationId
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

      renderEventsTable();

    } catch (e) {
      eventsTbody.innerHTML = `<tr><td colspan="6" class="text-danger">Error loading events: ${e.message}</td></tr>`;
    }
  }

  function extractPromptAndResponse(evt) {
    const payload = evt.payload || {};
    let prompt = null;
    let response = null;

    // Check payload.request_payload / payload.response_payload and payload.request / payload.response
    if (payload.request_payload !== undefined && payload.request_payload !== null) {
      prompt = payload.request_payload;
    } else if (payload.request !== undefined && payload.request !== null) {
      if (typeof payload.request === 'object' && Object.keys(payload.request).length > 0) {
        prompt = payload.request;
      } else if (typeof payload.request === 'string' && payload.request.trim() !== '') {
        prompt = payload.request;
      }
    }
    if (payload.response_payload !== undefined && payload.response_payload !== null) {
      response = payload.response_payload;
    } else if (payload.response !== undefined && payload.response !== null) {
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
      <div><span style="color:var(--text-muted);">Target:</span> <strong>${escapeHtml(evt.target || evt.recipient || '')}</strong></div>
      <div><span style="color:var(--text-muted);">Model Used:</span> <strong style="color:#c084fc;">${escapeHtml(evt.model || 'N/A')}</strong></div>
      <div><span style="color:var(--text-muted);">Status:</span> <strong>${escapeHtml(evt.status || 'success')}</strong></div>
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
        btnResetDb.disabled = !isGlobalAdmin;
        btnResetDb.style.opacity = !isGlobalAdmin ? '0.5' : '';
        btnResetDb.style.cursor = !isGlobalAdmin ? 'not-allowed' : '';
        btnResetDb.title = !isGlobalAdmin ? 'Only Global Admin can reset the Vector DB' : '';
      }
    }
  }

  if (currentUser) {
    applyRolePermissions(currentUser);
    updateJwtDisplay(currentUser, currentJwt);
    loadUserPreferencesForUser(currentUser.email);
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
        // Clear all prompts in chat and start new session, and clear Test Semantic Prompts in Agent page
        startNewChatSession();
        clearTestSemanticPrompts();
        logPageView('Chat & Knowledge Mgnt');
        loadIngestionData();
        await loadUserPreferencesForUser(currentUser.email, data.preferences);
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
            <button class="btn-secondary" style="padding:2px 8px; font-size:0.75rem; margin-left:4px; color:#ef4444; border-color:rgba(239,68,68,0.4);" ${!isAdmin ? 'disabled' : ''} onclick="deleteSingleUser(${u.id}, '${escapeHtml(u.email)}')">Delete</button>
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

  window.deleteSingleUser = async (uid, email) => {
    const isAdmin = (currentUser && currentUser.role === 'Admin');
    if (!isAdmin) {
      alert('Only users with Admin access can delete user accounts.');
      return;
    }
    if (!confirm(`Are you sure you want to permanently delete user account '${email}'?`)) {
      return;
    }
    try {
      const resp = await fetch(`/api/users/${uid}`, { method: 'DELETE' });
      const data = await resp.json().catch(() => ({}));
      if (resp.ok && (data.status === 'success' || !data.error)) {
        alert(data.message || `Deleted user ${email}`);
        selectedUserIds.delete(uid);
        loadUsers();
        loadUserActivity();
      } else {
        alert(data.error || 'Failed to delete user.');
      }
    } catch (e) {
      alert('Error deleting user: ' + e.message);
    }
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
  async function loadContextEvidence(convId, routerMeta) {
    if (!convId) return;
    try {
      const resp = await fetch(`/api/evidence/${encodeURIComponent(convId)}`);
      if (!resp.ok) return;
      const data = await resp.json();
      renderEvidence(data.retrieved_evidence || data, routerMeta || data.router_metadata || lastRouterMetadata);
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
  const agentSelectorSelect = document.getElementById('agentSelectorSelect');
  const thresholdControlBox = document.getElementById('thresholdControlBox');
  const statRoutingThresholdSub = document.getElementById('statRoutingThresholdSub');
  const btnRefreshAgents = document.getElementById('btnRefreshAgents');
  const btnOpenAddAgentModal = document.getElementById('btnOpenAddAgentModal');
  const addAgentModal = document.getElementById('addAgentModal');
  const addAgentModalTitle = document.getElementById('addAgentModalTitle');
  const modalAgentTypeNotice = document.getElementById('modalAgentTypeNotice');
  const btnCloseAddAgentModalX = document.getElementById('btnCloseAddAgentModalX');
  const btnCancelAddAgent = document.getElementById('btnCancelAddAgent');
  const btnSubmitAddAgent = document.getElementById('btnSubmitAddAgent');
  const addAgentAlertMsg = document.getElementById('addAgentAlertMsg');
  const btnTestRoute = document.getElementById('btnTestRoute');
  const testRouteInput = document.getElementById('testRouteInput');
  const testRouteResults = document.getElementById('testRouteResults');

  let currentModalMode = 'add'; // 'add', 'edit', 'view'
  let currentModalAgentId = null;

  function updateAgentSelectorUIState(isLlm, thresholdVal) {
    if (isLlm) {
      if (routerThresholdInput) {
        routerThresholdInput.disabled = true;
        routerThresholdInput.style.opacity = '0.5';
        routerThresholdInput.style.cursor = 'not-allowed';
      }
      if (btnSetThreshold) {
        btnSetThreshold.disabled = true;
        btnSetThreshold.style.opacity = '0.5';
        btnSetThreshold.style.cursor = 'not-allowed';
      }
      if (thresholdControlBox) {
        thresholdControlBox.style.opacity = '0.5';
        thresholdControlBox.style.pointerEvents = 'none';
      }
      if (statRoutingThreshold) statRoutingThreshold.textContent = 'N/A (LLM)';
      if (statRoutingThresholdSub) statRoutingThresholdSub.textContent = 'Main LLM Reasoning Mode';
    } else {
      if (routerThresholdInput) {
        routerThresholdInput.disabled = false;
        routerThresholdInput.style.opacity = '1';
        routerThresholdInput.style.cursor = 'text';
      }
      if (btnSetThreshold) {
        btnSetThreshold.disabled = false;
        btnSetThreshold.style.opacity = '1';
        btnSetThreshold.style.cursor = 'pointer';
      }
      if (thresholdControlBox) {
        thresholdControlBox.style.opacity = '1';
        thresholdControlBox.style.pointerEvents = 'auto';
      }
      if (typeof thresholdVal === 'number' && statRoutingThreshold) {
        statRoutingThreshold.textContent = `${Math.round(thresholdVal * 100)}%`;
      }
      if (statRoutingThresholdSub) statRoutingThresholdSub.textContent = 'Min for specialized match';
    }
  }

  if (agentSelectorSelect) {
    agentSelectorSelect.addEventListener('change', async () => {
      const val = agentSelectorSelect.value;
      const isLlm = (val === 'main_llm' || val === 'llm');
      const thresh = parseFloat(routerThresholdInput ? routerThresholdInput.value : 0.55);
      updateAgentSelectorUIState(isLlm, thresh);

      try {
        const resp = await fetch('/api/router/selector', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            selector_type: isLlm ? 'llm' : 'embedding',
            model: isLlm ? 'main_llm' : val
          })
        });
        const res = await resp.json();
        if (thresholdStatusMsg) {
          thresholdStatusMsg.style.display = 'inline';
          thresholdStatusMsg.textContent = isLlm ? 'Main LLM Active!' : 'Model Saved!';
          setTimeout(() => { thresholdStatusMsg.style.display = 'none'; }, 2500);
        }
      } catch (e) {
        console.warn('Error saving agent selector:', e);
      }
    });
  }

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
        saveUserPreferences({ router_threshold: val });
      } else {
        alert(`Failed to set threshold: ${res.message || 'Error'}`);
      }
    } catch (e) {
      alert(`Error setting routing threshold: ${e.message}`);
    }
  }

  if (btnSetThreshold) {
    btnSetThreshold.addEventListener('click', updateRoutingThreshold);
  }
  if (routerThresholdInput) {
    routerThresholdInput.addEventListener('change', () => {
      const val = parseFloat(routerThresholdInput.value);
      if (!isNaN(val) && val >= 0.0 && val <= 1.0) {
        saveUserPreferences({ router_threshold: val });
      }
    });
    routerThresholdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        updateRoutingThreshold();
      }
    });
  }

  function getAgentType(agent) {
    let t = agent.agent_type;
    if (!t && agent.metadata && agent.metadata.registration_type) {
      t = agent.metadata.registration_type;
    }
    if (!t) {
      t = agent.is_default ? "Hard Coded" : "API Registered";
    }
    const tLower = t.toLowerCase();
    if (tLower.includes("manual")) return "Manually Added";
    if (tLower.includes("hard")) return "Hard Coded";
    if (tLower.includes("api")) return "API Registered";
    return agent.is_default ? "Hard Coded" : "API Registered";
  }

  async function loadAgentsData() {
    if (!agentsTbody) return;
    try {
      const [resp, selResp, modelsResp] = await Promise.all([
        fetch('/api/router/agents'),
        fetch('/api/router/selector').catch(() => null),
        fetch('/api/vectordb/models').catch(() => null)
      ]);

      if (!resp.ok) {
        agentsTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Agents Router service initializing...</td></tr>';
        return;
      }
      const data = await resp.json();
      const agents = data.agents || [];
      const selData = (selResp && selResp.ok) ? await selResp.json() : null;
      const modelsData = (modelsResp && modelsResp.ok) ? await modelsResp.json() : null;

      // Populate Agent Selector Dropdown
      if (agentSelectorSelect && modelsData && modelsData.models) {
        const activeSelModel = (selData && selData.active_model) ? selData.active_model : 'bge-large:latest';
        const isLlmActive = (selData && (selData.selector_type === 'llm' || selData.active_model === 'main_llm'));

        agentSelectorSelect.innerHTML = '';
        
        // Option 1: Main LLM select
        const optLlm = document.createElement('option');
        optLlm.value = 'main_llm';
        optLlm.textContent = 'Main LLM select';
        agentSelectorSelect.appendChild(optLlm);

        // Option 2+: Available Embedding Models
        modelsData.models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = `${m.name} (Embedding)`;
          agentSelectorSelect.appendChild(opt);
        });

        if (isLlmActive) {
          agentSelectorSelect.value = 'main_llm';
        } else {
          // Match active embedding model
          const matched = modelsData.models.find(m => m.name === activeSelModel || m.name.split(':')[0] === activeSelModel.split(':')[0]);
          if (matched) {
            agentSelectorSelect.value = matched.name;
          } else {
            agentSelectorSelect.value = activeSelModel;
          }
        }

        updateAgentSelectorUIState(isLlmActive, data.threshold);
      }

      // Update threshold display and input
      if (typeof data.threshold === 'number') {
        const pct = Math.round(data.threshold * 100);
        const isLlm = (agentSelectorSelect && agentSelectorSelect.value === 'main_llm');
        if (!isLlm && statRoutingThreshold) statRoutingThreshold.textContent = `${pct}%`;
        if (routerThresholdInput && document.activeElement !== routerThresholdInput) {
          routerThresholdInput.value = data.threshold.toFixed(2);
        }
      }

      // Update statistics based on actual status
      let activeCount = 0;
      let offlineCount = 0;
      agents.forEach(a => {
        const isUp = (a.status === 'up' && (a.health_status === 'healthy' || !a.health_status));
        if (isUp) activeCount++;
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
        tr.style.cursor = 'pointer';
        tr.title = 'Click to view or edit agent details';
        const isUp = (agent.status === 'up' && (agent.health_status === 'healthy' || !agent.health_status));
        const isDefault = agent.is_default;
        const agentType = getAgentType(agent);

        let statusBadge = '';
        if (isUp) {
          statusBadge = `
            <div style="display:inline-flex; flex-direction:column; gap:2px;">
              <span class="badge badge-active" style="display:inline-flex; align-items:center; gap:5px; font-weight:700;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#10b981;"></span> UP
              </span>
              <span style="font-size:0.7rem; color:#10b981; font-weight:500;">🟢 Healthy</span>
            </div>`;
        } else {
          const rawErr = agent.health_status || 'Offline';
          const shortErr = rawErr.startsWith('unreachable') ? 'Unreachable' : (rawErr.startsWith('unhealthy') ? 'Unhealthy' : 'Offline');
          statusBadge = `
            <div style="display:inline-flex; flex-direction:column; gap:2px;">
              <span class="badge badge-locked" style="display:inline-flex; align-items:center; gap:5px; font-weight:700;" title="${escapeHtml(rawErr)}">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#ef4444;"></span> DOWN
              </span>
              <span style="font-size:0.7rem; color:#ef4444; font-weight:500;" title="${escapeHtml(rawErr)}">🔴 ${escapeHtml(shortErr)}</span>
            </div>`;
        }

        const roleBadge = isDefault
          ? `<span class="badge" style="background:#065f46; color:#a7f3d0; border:1px solid #10b981;">🛡️ Default Fallback</span>`
          : `<span class="badge" style="background:#581c87; color:#e9d5ff; border:1px solid #a855f7;">⚡ Specialized</span>`;

        let typeBadgeStyle = '';
        let typeIcon = '';
        if (agentType === "Hard Coded") {
          typeBadgeStyle = 'background:#1e293b; color:#cbd5e1; border:1px solid #475569;';
          typeIcon = '💻 ';
        } else if (agentType === "API Registered") {
          typeBadgeStyle = 'background:#0c4a6e; color:#7dd3fc; border:1px solid #0284c7;';
          typeIcon = '🔌 ';
        } else {
          typeBadgeStyle = 'background:#451a03; color:#fdba74; border:1px solid #ea580c;';
          typeIcon = '✍️ ';
        }
        const typeBadge = `<span class="badge" style="${typeBadgeStyle} font-size:0.75rem; display:inline-block; margin-top:4px;">${typeIcon}${agentType}</span>`;

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
          <td>
            <div>${roleBadge}</div>
            <div>${typeBadge}</div>
          </td>
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

        // Row click opens the modal with agent info
        tr.addEventListener('click', (e) => {
          if (e.target.closest('button')) return;
          openAgentDetailsModal(agent, agentType);
        });

        // Wire actions
        const btnStatus = tr.querySelector('.btn-agent-status');
        if (btnStatus) {
          btnStatus.onclick = (e) => {
            e.stopPropagation();
            toggleAgentStatus(agent.id, agent.status);
          };
        }
        const btnHealth = tr.querySelector('.btn-agent-health');
        if (btnHealth) {
          btnHealth.onclick = (e) => {
            e.stopPropagation();
            checkAgentHealth(agent.id);
          };
        }
        const btnDelete = tr.querySelector('.btn-agent-delete');
        if (btnDelete) {
          btnDelete.onclick = (e) => {
            e.stopPropagation();
            deleteAgent(agent.id, agent.name);
          };
        }

        agentsTbody.appendChild(tr);
      });
    } catch (e) {
      console.error('Error loading agents data:', e);
      if (agentsTbody) agentsTbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Error connecting to agents router.</td></tr>';
    }
  }

  function openAgentDetailsModal(agent, agentType) {
    if (addAgentAlertMsg) addAgentAlertMsg.classList.add('hidden');
    const inputId = document.getElementById('inputNewAgentId');
    const inputName = document.getElementById('inputNewAgentName');
    const inputUrl = document.getElementById('inputNewAgentUrl');
    const inputDesc = document.getElementById('inputNewAgentDesc');
    const inputPrompts = document.getElementById('inputNewAgentPrompts');
    const selectStatus = document.getElementById('selectNewAgentStatus');

    currentModalAgentId = agent.id;

    if (inputId) {
      inputId.value = agent.id || '';
      inputId.disabled = true;
    }
    if (inputName) {
      inputName.value = agent.name || '';
      inputName.disabled = (agentType !== 'Manually Added');
    }
    if (inputUrl) {
      inputUrl.value = agent.url || '';
      inputUrl.disabled = (agentType !== 'Manually Added');
    }
    if (inputDesc) {
      inputDesc.value = agent.description || '';
      inputDesc.disabled = (agentType !== 'Manually Added');
    }
    if (inputPrompts) {
      inputPrompts.value = (agent.sample_prompts || []).join('\n');
      inputPrompts.disabled = (agentType !== 'Manually Added');
    }
    if (selectStatus) {
      selectStatus.value = agent.status || 'up';
      selectStatus.disabled = (agentType !== 'Manually Added');
    }

    if (agentType === 'Manually Added') {
      currentModalMode = 'edit';
      if (addAgentModalTitle) addAgentModalTitle.innerHTML = `<span class="modal-icon">✏️</span> Edit Agent: ${escapeHtml(agent.name)}`;
      if (modalAgentTypeNotice) {
        modalAgentTypeNotice.className = '';
        modalAgentTypeNotice.style.background = 'rgba(234, 88, 12, 0.15)';
        modalAgentTypeNotice.style.border = '1px solid rgba(234, 88, 12, 0.4)';
        modalAgentTypeNotice.style.color = '#fdba74';
        modalAgentTypeNotice.innerHTML = `<strong>✍️ Manually Added:</strong> You can modify the configuration and URL of this agent.`;
      }
      if (btnCancelAddAgent) btnCancelAddAgent.textContent = 'Cancel';
      if (btnSubmitAddAgent) {
        btnSubmitAddAgent.style.display = 'inline-block';
        btnSubmitAddAgent.textContent = 'Save Changes';
      }
    } else {
      currentModalMode = 'view';
      if (addAgentModalTitle) addAgentModalTitle.innerHTML = `<span class="modal-icon">🤖</span> Agent Details: ${escapeHtml(agent.name)}`;
      if (modalAgentTypeNotice) {
        modalAgentTypeNotice.className = '';
        if (agentType === 'Hard Coded') {
          modalAgentTypeNotice.style.background = 'rgba(100, 116, 139, 0.15)';
          modalAgentTypeNotice.style.border = '1px solid rgba(100, 116, 139, 0.4)';
          modalAgentTypeNotice.style.color = '#94a3b8';
          modalAgentTypeNotice.innerHTML = `<strong>💻 Hard Coded:</strong> Defined in system code. Configuration is read-only.`;
        } else {
          modalAgentTypeNotice.style.background = 'rgba(2, 132, 199, 0.15)';
          modalAgentTypeNotice.style.border = '1px solid rgba(2, 132, 199, 0.4)';
          modalAgentTypeNotice.style.color = '#7dd3fc';
          modalAgentTypeNotice.innerHTML = `<strong>🔌 API Registered:</strong> Registered dynamically via container API. Configuration is read-only.`;
        }
      }
      if (btnCancelAddAgent) btnCancelAddAgent.textContent = 'Close';
      if (btnSubmitAddAgent) {
        btnSubmitAddAgent.style.display = 'none';
      }
    }

    if (addAgentModal) {
      addAgentModal.classList.remove('hidden');
      addAgentModal.style.display = 'flex';
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
  function openAddAgentModal() {
    currentModalMode = 'add';
    currentModalAgentId = null;
    const alertMsg = document.getElementById('addAgentAlertMsg') || addAgentAlertMsg;
    const typeNotice = document.getElementById('modalAgentTypeNotice') || modalAgentTypeNotice;
    const title = document.getElementById('addAgentModalTitle') || addAgentModalTitle;
    const modal = document.getElementById('addAgentModal') || addAgentModal;
    const cancelBtn = document.getElementById('btnCancelAddAgent') || btnCancelAddAgent;
    const submitBtn = document.getElementById('btnSubmitAddAgent') || btnSubmitAddAgent;

    if (alertMsg) {
      alertMsg.textContent = '';
      alertMsg.classList.add('hidden');
    }
    if (typeNotice) {
      typeNotice.className = 'hidden';
      typeNotice.style.display = 'none';
    }
    if (title) {
      title.innerHTML = `<span class="modal-icon">🤖</span> Add New Agent`;
    }

    const inputId = document.getElementById('inputNewAgentId');
    const inputName = document.getElementById('inputNewAgentName');
    const inputUrl = document.getElementById('inputNewAgentUrl');
    const inputDesc = document.getElementById('inputNewAgentDesc');
    const inputPrompts = document.getElementById('inputNewAgentPrompts');
    const selectStatus = document.getElementById('selectNewAgentStatus');

    if (inputId) { inputId.value = ''; inputId.disabled = false; }
    if (inputName) { inputName.value = ''; inputName.disabled = false; }
    if (inputUrl) { inputUrl.value = ''; inputUrl.disabled = false; }
    if (inputDesc) { inputDesc.value = ''; inputDesc.disabled = false; }
    if (inputPrompts) { inputPrompts.value = ''; inputPrompts.disabled = false; }
    if (selectStatus) { selectStatus.value = 'up'; selectStatus.disabled = false; }

    if (cancelBtn) {
      cancelBtn.textContent = 'Cancel';
      cancelBtn.style.display = 'inline-block';
    }
    if (submitBtn) {
      submitBtn.style.display = 'inline-block';
      submitBtn.textContent = 'Add';
    }

    if (modal) {
      modal.classList.remove('hidden');
      modal.style.display = 'flex';
    }
  }

  function closeAddAgentModal() {
    const modal = document.getElementById('addAgentModal') || addAgentModal;
    if (modal) {
      modal.classList.add('hidden');
      modal.style.display = 'none';
    }
    const form = document.getElementById('formAddAgent');
    if (form) {
      try { form.reset(); } catch(e) {}
    }
    currentModalMode = 'add';
    currentModalAgentId = null;
  }

  async function submitAddAgentModal() {
    const inputId = document.getElementById('inputNewAgentId');
    const inputName = document.getElementById('inputNewAgentName');
    const inputUrl = document.getElementById('inputNewAgentUrl');
    const inputDesc = document.getElementById('inputNewAgentDesc');
    const inputPrompts = document.getElementById('inputNewAgentPrompts');
    const alertMsg = document.getElementById('addAgentAlertMsg') || addAgentAlertMsg;

    const id = inputId ? inputId.value.trim() : '';
    const name = inputName ? inputName.value.trim() : '';
    const url = inputUrl ? inputUrl.value.trim() : '';
    const description = inputDesc ? inputDesc.value.trim() : '';
    const promptsRaw = inputPrompts ? inputPrompts.value.trim() : '';

    const sample_prompts = promptsRaw ? promptsRaw.split('\n').map(p => p.trim()).filter(Boolean) : [];

    if (currentModalMode === 'add') {
      if (!id || !name || !url) {
        if (alertMsg) {
          alertMsg.textContent = 'Please provide Agent ID, Display Name, and URI.';
          alertMsg.classList.remove('hidden');
        }
        return;
      }

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
            status: 'up',
            is_default: false,
            registration_type: 'Manually Added',
            metadata: { registration_type: 'Manually Added' }
          })
        });
        const res = await resp.json();
        if (resp.ok) {
          // Close popup window and return to Agents page
          closeAddAgentModal();
          // Send health check to determine live status and display status
          try {
            await fetch(`/api/router/agents/${encodeURIComponent(id)}/health`, { method: 'POST' });
          } catch (hErr) {
            console.warn('Initial health check ping error:', hErr);
          }
          await loadAgentsData();
        } else {
          if (alertMsg) {
            alertMsg.textContent = res.message || 'Registration failed.';
            alertMsg.classList.remove('hidden');
          }
        }
      } catch (e) {
        if (alertMsg) {
          alertMsg.textContent = `Network error: ${e.message}`;
          alertMsg.classList.remove('hidden');
        }
      }
    } else if (currentModalMode === 'edit') {
      if (!name || !url) {
        if (alertMsg) {
          alertMsg.textContent = 'Please provide Display Name and URI.';
          alertMsg.classList.remove('hidden');
        }
        return;
      }

      try {
        const resp = await fetch(`/api/router/agents/${encodeURIComponent(currentModalAgentId)}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: name,
            url: url,
            description: description,
            sample_prompts: sample_prompts,
            status: status
          })
        });
        const res = await resp.json();
        if (resp.ok) {
          closeAddAgentModal();
          try {
            await fetch(`/api/router/agents/${encodeURIComponent(currentModalAgentId)}/health`, { method: 'POST' });
          } catch (hErr) {
            console.warn('Health check error after update:', hErr);
          }
          await loadAgentsData();
        } else {
          if (alertMsg) {
            alertMsg.textContent = res.message || 'Update failed.';
            alertMsg.classList.remove('hidden');
          }
        }
      } catch (e) {
        if (alertMsg) {
          alertMsg.textContent = `Network error: ${e.message}`;
          alertMsg.classList.remove('hidden');
        }
      }
    }
  }

  // Expose globally for inline HTML event triggers
  window.updateRoutingThreshold = updateRoutingThreshold;
  window.loadAgentsData = loadAgentsData;
  window.openAddAgentModal = openAddAgentModal;
  window.closeAddAgentModal = closeAddAgentModal;
  window.submitAddAgentModal = submitAddAgentModal;
  window.testSemanticRoute = testSemanticRoute;

  if (btnOpenAddAgentModal) btnOpenAddAgentModal.onclick = openAddAgentModal;
  if (btnCloseAddAgentModalX) btnCloseAddAgentModalX.onclick = closeAddAgentModal;
  if (btnCancelAddAgent) btnCancelAddAgent.onclick = closeAddAgentModal;
  if (btnSubmitAddAgent) btnSubmitAddAgent.onclick = submitAddAgentModal;

  if (addAgentModal) {
    addAgentModal.addEventListener('click', (e) => {
      if (e.target === addAgentModal) {
        closeAddAgentModal();
      }
    });
  }

  if (btnRefreshAgents) {
    btnRefreshAgents.onclick = async () => {
      try {
        await fetch('/api/router/agents/health_check_all', { method: 'POST' }).catch(() => {});
      } catch (e) {}
      loadAgentsData();
    };
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

  // ---------------------------------------------------------------------------
  // SEMANTIC LAB CONTROLLER (Prompts, Embeddings, Agents & Skills Lab)
  // ---------------------------------------------------------------------------
  let semLabCachedAgents = [];
  let semLabCachedSkills = [];
  let semLabCachedModels = [];
  let semLabCurrentInputMode = 'single'; // 'single' | 'batch'

  const semLabSinglePromptBox = document.getElementById('semLabSinglePromptBox');
  const semLabBatchPromptBox = document.getElementById('semLabBatchPromptBox');
  const btnSemLabModeSingle = document.getElementById('btnSemLabModeSingle');
  const btnSemLabModeBatch = document.getElementById('btnSemLabModeBatch');
  const semLabSingleInput = document.getElementById('semLabSingleInput');
  const semLabBatchInput = document.getElementById('semLabBatchInput');

  const btnSemLabTabAgentDraft = document.getElementById('btnSemLabTabAgentDraft');
  const btnSemLabTabSkillDraft = document.getElementById('btnSemLabTabSkillDraft');
  const semLabAgentDraftBox = document.getElementById('semLabAgentDraftBox');
  const semLabSkillDraftBox = document.getElementById('semLabSkillDraftBox');

  const semLabAgentThreshold = document.getElementById('semLabAgentThreshold');
  const semLabAgentThresholdVal = document.getElementById('semLabAgentThresholdVal');
  const semLabSkillThreshold = document.getElementById('semLabSkillThreshold');
  const semLabSkillThresholdVal = document.getElementById('semLabSkillThresholdVal');

  const semLabPipelineMode = document.getElementById('semLabPipelineMode');
  const semLabEmbedderSelect = document.getElementById('semLabEmbedderSelect');
  const semLabDraftTemplateSelect = document.getElementById('semLabDraftTemplateSelect');
  const semLabDraftAgentName = document.getElementById('semLabDraftAgentName');
  const semLabDraftAgentDesc = document.getElementById('semLabDraftAgentDesc');
  const semLabDraftAgentSamples = document.getElementById('semLabDraftAgentSamples');
  const semLabEnableDraftAgent = document.getElementById('semLabEnableDraftAgent');

  const semLabSkillSelect = document.getElementById('semLabSkillSelect');
  const semLabSkillRawContent = document.getElementById('semLabSkillRawContent');
  const semLabSkillChunkCount = document.getElementById('semLabSkillChunkCount');

  // Sliders
  if (semLabAgentThreshold && semLabAgentThresholdVal) {
    semLabAgentThreshold.addEventListener('input', () => {
      semLabAgentThresholdVal.textContent = parseFloat(semLabAgentThreshold.value).toFixed(2);
    });
  }
  if (semLabSkillThreshold && semLabSkillThresholdVal) {
    semLabSkillThreshold.addEventListener('input', () => {
      semLabSkillThresholdVal.textContent = parseFloat(semLabSkillThreshold.value).toFixed(2);
    });
  }

  // Mode Switchers
  if (btnSemLabModeSingle && btnSemLabModeBatch) {
    btnSemLabModeSingle.addEventListener('click', () => {
      semLabCurrentInputMode = 'single';
      btnSemLabModeSingle.classList.add('active');
      btnSemLabModeBatch.classList.remove('active');
      if (semLabSinglePromptBox) semLabSinglePromptBox.style.display = 'block';
      if (semLabBatchPromptBox) semLabBatchPromptBox.style.display = 'none';
      const batchCard = document.getElementById('semLabBatchResultsCard');
      if (batchCard) batchCard.style.display = 'none';
    });

    btnSemLabModeBatch.addEventListener('click', () => {
      semLabCurrentInputMode = 'batch';
      btnSemLabModeBatch.classList.add('active');
      btnSemLabModeSingle.classList.remove('active');
      if (semLabSinglePromptBox) semLabSinglePromptBox.style.display = 'none';
      if (semLabBatchPromptBox) semLabBatchPromptBox.style.display = 'block';
    });
  }

  // Sandbox Tab Switchers
  if (btnSemLabTabAgentDraft && btnSemLabTabSkillDraft) {
    btnSemLabTabAgentDraft.addEventListener('click', () => {
      btnSemLabTabAgentDraft.classList.add('active');
      btnSemLabTabSkillDraft.classList.remove('active');
      if (semLabAgentDraftBox) semLabAgentDraftBox.style.display = 'block';
      if (semLabSkillDraftBox) semLabSkillDraftBox.style.display = 'none';
    });

    btnSemLabTabSkillDraft.addEventListener('click', () => {
      btnSemLabTabSkillDraft.classList.add('active');
      btnSemLabTabAgentDraft.classList.remove('active');
      if (semLabAgentDraftBox) semLabAgentDraftBox.style.display = 'none';
      if (semLabSkillDraftBox) semLabSkillDraftBox.style.display = 'block';
    });
  }

  // Preset Chips
  document.querySelectorAll('.sem-preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = btn.getAttribute('data-prompt');
      if (p) {
        if (semLabCurrentInputMode !== 'single' && btnSemLabModeSingle) {
          btnSemLabModeSingle.click();
        }
        if (semLabSingleInput) semLabSingleInput.value = p;
        runSemanticLabEvaluation();
      }
    });
  });

  // Single Input Enter key
  if (semLabSingleInput) {
    semLabSingleInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') runSemanticLabEvaluation();
    });
  }

  // Embedder Select change: Auto re-evaluate if prompt exists
  if (semLabEmbedderSelect) {
    semLabEmbedderSelect.addEventListener('change', () => {
      if (semLabSingleInput && semLabSingleInput.value.trim() && semLabCurrentInputMode === 'single') {
        runSemanticLabEvaluation();
      }
    });
  }

  // Template select populate
  if (semLabDraftTemplateSelect) {
    semLabDraftTemplateSelect.addEventListener('change', () => {
      const aId = semLabDraftTemplateSelect.value;
      const target = semLabCachedAgents.find(a => a.id === aId);
      if (target) {
        if (semLabDraftAgentName) semLabDraftAgentName.value = target.name + ' (Draft Variant)';
        if (semLabDraftAgentDesc) semLabDraftAgentDesc.value = target.description || '';
        if (semLabDraftAgentSamples) semLabDraftAgentSamples.value = (target.sample_prompts || []).join('\n');
        if (semLabEnableDraftAgent) semLabEnableDraftAgent.checked = true;
      }
    });
  }

  // Skill select populate
  if (semLabSkillSelect) {
    semLabSkillSelect.addEventListener('change', () => {
      const sName = semLabSkillSelect.value;
      const sObj = semLabCachedSkills.find(s => s.name === sName);
      if (sObj) {
        if (semLabSkillRawContent) semLabSkillRawContent.value = sObj.raw_content || '';
        if (semLabSkillChunkCount) {
          const charLen = (sObj.raw_content || '').length;
          const chunksEst = Math.max(1, Math.ceil(charLen / 1000));
          semLabSkillChunkCount.textContent = `${charLen} chars (~${chunksEst} chunks)`;
        }
      } else {
        if (semLabSkillRawContent) semLabSkillRawContent.value = '';
        if (semLabSkillChunkCount) semLabSkillChunkCount.textContent = '0 Chunks';
      }
    });
  }

  if (semLabSkillRawContent) {
    semLabSkillRawContent.addEventListener('input', () => {
      if (semLabSkillChunkCount) {
        const charLen = semLabSkillRawContent.value.length;
        const chunksEst = Math.max(1, Math.ceil(charLen / 1000));
        semLabSkillChunkCount.textContent = `${charLen} chars (~${chunksEst} chunks, edited)`;
      }
    });
  }

  // Load Semantic Lab Context Data
  async function loadSemanticLabData() {
    try {
      const res = await fetch('/api/semantic_lab/context');
      if (!res.ok) return;
      const data = await res.json();

      semLabCachedAgents = data.agents || [];
      semLabCachedSkills = data.skills || [];
      semLabCachedModels = data.models || [];

      // 1. Update embedder dropdown
      if (semLabEmbedderSelect) {
        semLabEmbedderSelect.innerHTML = `<option value="default">Active Embedder (${escapeHtml(data.active_model || 'Auto')})</option>`;
        semLabCachedModels.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = `${m.name} (${m.status})`;
          semLabEmbedderSelect.appendChild(opt);
        });
      }

      // 2. Update draft template select
      if (semLabDraftTemplateSelect) {
        semLabDraftTemplateSelect.innerHTML = '<option value="">-- Choose template or create new --</option>';
        semLabCachedAgents.forEach(a => {
          const opt = document.createElement('option');
          opt.value = a.id;
          opt.textContent = `${a.name} [${a.status.toUpperCase()}]`;
          semLabDraftTemplateSelect.appendChild(opt);
        });
      }

      // 3. Update skill select
      if (semLabSkillSelect) {
        semLabSkillSelect.innerHTML = '<option value="">-- Select a Skill to Inspect --</option>';
        semLabCachedSkills.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.name;
          opt.textContent = `${s.name} (${(s.triggers || []).length} triggers)`;
          semLabSkillSelect.appendChild(opt);
        });
        if (semLabCachedSkills.length > 0) {
          semLabSkillSelect.value = semLabCachedSkills[0].name;
          semLabSkillSelect.dispatchEvent(new Event('change'));
        }
      }

      // 4. Default thresholds
      if (semLabAgentThreshold && !semLabAgentThreshold.hasAttribute('data-touched')) {
        semLabAgentThreshold.value = data.agent_threshold || 0.50;
        if (semLabAgentThresholdVal) semLabAgentThresholdVal.textContent = parseFloat(semLabAgentThreshold.value).toFixed(2);
      }
    } catch (e) {
      console.warn('Error loading semantic lab context:', e);
    }
  }

  // Run Semantic Lab Evaluation
  async function runSemanticLabEvaluation() {
    const btnRun = document.getElementById('btnRunSemLab');
    const oldBtnText = btnRun ? btnRun.innerHTML : '';
    if (btnRun) {
      btnRun.disabled = true;
      btnRun.innerHTML = '<span class="icon">⏳</span> Evaluating...';
    }

    const mode = (semLabPipelineMode ? semLabPipelineMode.value : 'full');
    const agentThresh = parseFloat(semLabAgentThreshold ? semLabAgentThreshold.value : 0.50);
    const skillThresh = parseFloat(semLabSkillThreshold ? semLabSkillThreshold.value : 0.20);
    const embedderModel = (semLabEmbedderSelect && semLabEmbedderSelect.value) ? semLabEmbedderSelect.value : 'default';

    // Build draft agent if enabled
    let draftAgents = null;
    if (semLabEnableDraftAgent && semLabEnableDraftAgent.checked) {
      const dName = (semLabDraftAgentName ? semLabDraftAgentName.value : '').trim() || 'Draft Specialist Agent';
      const dDesc = (semLabDraftAgentDesc ? semLabDraftAgentDesc.value : '').trim();
      const dSamplesRaw = (semLabDraftAgentSamples ? semLabDraftAgentSamples.value : '').trim();
      const dSamples = dSamplesRaw ? dSamplesRaw.split('\n').map(s => s.trim()).filter(s => s.length > 0) : [];
      
      draftAgents = [
        ...semLabCachedAgents.map(a => ({
          id: a.id,
          name: a.name,
          description: a.description,
          url: a.url,
          sample_prompts: a.sample_prompts,
          status: a.status,
          is_default: a.is_default
        })),
        {
          id: 'draft-sandbox-agent',
          name: dName,
          description: dDesc,
          url: 'http://draft_agent:8000',
          sample_prompts: dSamples,
          status: 'up',
          is_default: false,
          metadata: { registration_type: 'Draft Sandbox' }
        }
      ];
    }

    const tStart = performance.now();

    try {
      if (semLabCurrentInputMode === 'single') {
        const query = (semLabSingleInput ? semLabSingleInput.value : '').trim();
        if (!query) {
          alert('Please enter a test prompt.');
          return;
        }

        // Parallel execution for single prompt
        const semLabConvId = 'conv_semantic_lab_' + Date.now();
        const promises = [];
        if (mode === 'full' || mode === 'agents') {
          promises.push(
            fetch('/api/router/test_route', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                query: query,
                threshold: agentThresh,
                embedder_model: embedderModel,
                draft_agents: draftAgents,
                invoker: 'Semantic Lab',
                conversation_id: semLabConvId
              })
            }).then(r => r.json()).catch(err => ({ status: 'error', message: err.message }))
          );
        } else {
          promises.push(Promise.resolve(null));
        }

        if (mode === 'full' || mode === 'skills') {
          let draftSkill = null;
          const skillContent = (semLabSkillRawContent ? semLabSkillRawContent.value : '').trim();
          const selectedSkill = (semLabSkillSelect ? semLabSkillSelect.value : '');
          if (skillContent && selectedSkill) {
            const cachedOrig = (semLabCachedSkills || []).find(s => s.name === selectedSkill);
            if (!cachedOrig || cachedOrig.raw_content !== skillContent) {
              draftSkill = {
                name: selectedSkill,
                content: skillContent
              };
            }
          }

          promises.push(
            fetch('/api/semantic_lab/test_skills', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                query: query,
                threshold: skillThresh,
                embedder_model: embedderModel,
                limit: 5,
                draft_skill: draftSkill,
                invoker: 'Semantic Lab',
                conversation_id: semLabConvId
              })
            }).then(r => r.json()).catch(err => ({ status: 'error', message: err.message }))
          );
        } else {
          promises.push(Promise.resolve(null));
        }

        const [agentRes, skillRes] = await Promise.all(promises);
        const elapsed = Math.round(performance.now() - tStart);

        renderSemanticLabSingleResults(query, agentRes, skillRes, elapsed, agentThresh, skillThresh, mode);
      } else {
        // Batch Mode
        const batchRaw = (semLabBatchInput ? semLabBatchInput.value : '').trim();
        const prompts = batchRaw.split('\n').map(p => p.trim()).filter(p => p.length > 0);
        if (prompts.length === 0) {
          alert('Please enter at least one test prompt in the batch suite.');
          return;
        }

        const batchConvId = 'conv_semantic_lab_batch_' + Date.now();
        const res = await fetch('/api/semantic_lab/batch_eval', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompts: prompts,
            agent_threshold: agentThresh,
            skill_threshold: skillThresh,
            embedder_model: embedderModel,
            mode: mode,
            draft_agents: draftAgents,
            invoker: 'Semantic Lab',
            conversation_id: batchConvId
          })
        });
        const data = await res.json();
        const elapsed = Math.round(performance.now() - tStart);

        renderSemanticLabBatchResults(data, elapsed);
      }
    } catch (e) {
      alert('Error running semantic lab evaluation: ' + e.message);
    } finally {
      if (btnRun) {
        btnRun.disabled = false;
        btnRun.innerHTML = oldBtnText;
      }
    }
  }

  // Render Single Results
  function renderSemanticLabSingleResults(query, agentRes, skillRes, latencyMs, agentThresh, skillThresh, mode = 'full') {
    // 1. Metric tiles
    const latEl = document.getElementById('semLabMetricLatency');
    const agentEl = document.getElementById('semLabMetricAgent');
    const skillEl = document.getElementById('semLabMetricSkill');
    const statusEl = document.getElementById('semLabMetricStatus');

    if (latEl) latEl.textContent = `${latencyMs} ms`;

    // 2. Agent Card Rendering
    const winnerNameEl = document.getElementById('semLabWinnerName');
    const winnerReasonEl = document.getElementById('semLabWinnerReason');
    const rankedListEl = document.getElementById('semLabRankedAgentsList');
    const agentBadgeEl = document.getElementById('semLabAgentBadge');
    const agentExplainEl = document.getElementById('semLabAgentExplainBox');

    if (agentRes && agentRes.status === 'success') {
      const selected = agentRes.selected_agent;
      const isFallback = agentRes.is_default_fallback;
      const topScore = agentRes.similarity_score;
      const topScorePct = agentRes.similarity_percent || `${Math.round(topScore * 100)}%`;
      const topSpec = agentRes.top_specialized_agent;
      const topSpecScore = agentRes.top_specialized_score !== undefined ? agentRes.top_specialized_score : (topSpec ? topSpec.score : 0);

      if (agentEl) {
        agentEl.textContent = selected ? `${selected.name}${isFallback ? ' (Fallback)' : ` (${topScorePct})`}` : 'None';
      }
      if (statusEl) {
        statusEl.textContent = isFallback ? '🛡️ Fallback Default' : '🎯 Specialized Routed';
        statusEl.style.color = isFallback ? '#fbbf24' : '#34d399';
      }

      if (agentBadgeEl) {
        agentBadgeEl.textContent = isFallback ? 'Default Fallback' : 'Specialized Match';
        agentBadgeEl.className = 'status-badge ' + (isFallback ? 'offline' : 'active');
      }

      const winnerLabelEl = document.getElementById('semLabWinnerLabel');
      if (winnerLabelEl) {
        winnerLabelEl.textContent = isFallback
          ? 'Routed Destination (Default Fallback):'
          : 'Winning Candidate Agent (Specialized Match):';
      }

      if (winnerNameEl) {
        if (isFallback) {
          winnerNameEl.innerHTML = `
            <div style="display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;">
              <span style="color: #fbbf24;">🛡️ ${selected ? escapeHtml(selected.name) : 'Default Fallback Agent'}</span>
              <span style="font-size: 0.85rem; color: #fbbf24; font-weight: 700;">(${topScorePct})</span>
              <span style="font-size: 0.72rem; background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); padding: 2px 7px; border-radius: 4px;">FALLBACK ROUTED</span>
            </div>
          `;
        } else {
          winnerNameEl.innerHTML = `
            <div style="display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;">
              <span style="color: #34d399;">🎯 ${selected ? escapeHtml(selected.name) : 'Specialized Agent'}</span>
              <span style="font-size: 0.85rem; color: #34d399; font-weight: 700;">(${topScorePct})</span>
              <span style="font-size: 0.72rem; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); padding: 2px 7px; border-radius: 4px;">SPECIALIZED ROUTED</span>
            </div>
          `;
        }
      }

      if (winnerReasonEl) {
        let reasonHtml = `<div style="margin-top: 4px; line-height: 1.4;">${escapeHtml(agentRes.explanation || '')}</div>`;
        if (isFallback && topSpec) {
          const specPct = Math.round(topSpecScore * 100);
          reasonHtml += `<div style="margin-top: 6px; font-size: 0.78rem; color: #94a3b8;">Highest specialized candidate: <strong style="color: #f1f5f9;">${escapeHtml(topSpec.name || topSpec.agent_name)}</strong> scored <strong style="color: #fbbf24;">${specPct}% (${topSpecScore.toFixed(4)})</strong> — below the required ${Math.round(agentThresh * 100)}% minimum threshold.</div>`;
        }
        if (agentRes.model_used) {
          reasonHtml += `<div style="font-size: 0.72rem; color: #64748b; margin-top: 4px;">Model Used: <code style="color: #38bdf8;">${escapeHtml(agentRes.model_used)}</code></div>`;
        }
        winnerReasonEl.innerHTML = reasonHtml;
      }

      // Ranked progress bars (sorted descending)
      if (rankedListEl) {
        const ranked = (agentRes.ranked_scores || []).slice().sort((a, b) => (b.score || 0) - (a.score || 0));
        if (ranked.length === 0) {
          rankedListEl.innerHTML = `<div class="text-muted" style="text-align: center; padding: 20px;">No candidate agents registered.</div>`;
        } else {
          rankedListEl.innerHTML = ranked.map(r => {
            const score = r.score || 0;
            const pct = Math.min(100, Math.round(score * 100));
            const isWinner = selected && selected.id === r.agent_id;
            const exceeds = score > agentThresh;
            let barColor = exceeds ? '#10b981' : '#64748b';
            if (r.is_default) barColor = '#3b82f6';
            if (r.status === 'down') barColor = '#ef4444';

            return `
              <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid ${isWinner ? '#38bdf8' : '#334155'}; border-radius: 6px; padding: 8px 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 700; font-size: 0.82rem; color: ${isWinner ? '#38bdf8' : '#f1f5f9'};">
                    ${isWinner ? '👑 ' : ''}${escapeHtml(r.agent_name)}
                    ${r.is_default ? '<span style="font-size: 0.68rem; color: #94a3b8; font-weight: normal; margin-left: 4px;">(Default Fallback)</span>' : ''}
                    ${r.agent_id === 'draft-sandbox-agent' ? '<span style="font-size: 0.68rem; background: #7c3aed; color: #fff; padding: 1px 5px; border-radius: 3px; margin-left: 4px;">DRAFT VARIANT</span>' : ''}
                  </div>
                  <div style="font-weight: 700; font-size: 0.82rem; color: ${barColor};">
                    ${pct}% <span style="font-size: 0.72rem; color: #94a3b8;">(${score.toFixed(4)})</span>
                  </div>
                </div>
                <div style="height: 6px; width: 100%; background: #1e293b; border-radius: 3px; overflow: hidden;">
                  <div style="height: 100%; width: ${pct}%; background: ${barColor}; transition: width 0.4s ease;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: #94a3b8; margin-top: 4px;">
                  <span>Status: <strong style="color: ${r.status === 'up' ? '#34d399' : '#f87171'}">${(r.status || 'up').toUpperCase()}</strong></span>
                  <span>${exceeds ? '✅ Exceeds ' + Math.round(agentThresh * 100) + '% min' : '⚠️ Below ' + Math.round(agentThresh * 100) + '% min'}</span>
                </div>
              </div>
            `;
          }).join('');
        }
      }

      // Explainability details
      if (agentExplainEl) {
        const ranked = agentRes.ranked_scores || [];
        agentExplainEl.innerHTML = `
          <div style="margin-bottom: 8px;">
            <strong style="color: #cbd5e1;">Query Vectorized:</strong>
            <pre style="background: #0f172a; padding: 6px 10px; border-radius: 4px; color: #38bdf8; margin: 4px 0;">"${escapeHtml(query)}"</pre>
          </div>
          <div style="margin-top: 6px;">
            <strong style="color: #cbd5e1;">Agent Text Representations Sent to Vectorizer:</strong>
            ${ranked.map(r => `
              <div style="margin-top: 6px; padding: 6px; background: #0f172a; border-left: 3px solid #38bdf8; border-radius: 2px;">
                <div style="font-weight: 700; color: #f1f5f9; font-size: 0.75rem;">${escapeHtml(r.agent_name)} (${r.agent_id}):</div>
                <pre style="font-size: 0.7rem; color: #94a3b8; white-space: pre-wrap; margin: 4px 0;">${escapeHtml(r.embedding_text || 'No representation cached')}</pre>
              </div>
            `).join('')}
          </div>
        `;
      }
    } else if (agentRes && agentRes.status === 'error') {
      if (agentEl) agentEl.textContent = 'Error';
      if (statusEl) {
        statusEl.textContent = '❌ Evaluation Error';
        statusEl.style.color = '#ef4444';
      }
      if (agentBadgeEl) {
        agentBadgeEl.textContent = 'Error';
        agentBadgeEl.className = 'status-badge offline';
      }
      if (winnerNameEl) winnerNameEl.innerHTML = '<span style="color: #ef4444;">Evaluation Error</span>';
      if (winnerReasonEl) winnerReasonEl.textContent = agentRes.message || 'Error communicating with agents router';
      if (rankedListEl) rankedListEl.innerHTML = `<div style="color: #f87171; padding: 12px; font-size: 0.8rem;">${escapeHtml(agentRes.message || 'Error communicating with agents router')}</div>`;
    } else if (mode === 'skills') {
      if (agentBadgeEl) {
        agentBadgeEl.textContent = 'Skipped (Skills Mode)';
        agentBadgeEl.className = 'status-badge offline';
      }
      if (winnerNameEl) winnerNameEl.textContent = 'Skipped in Skills Mode';
      if (winnerReasonEl) winnerReasonEl.textContent = 'Pipeline mode is currently set to "Skills Search Only".';
      if (rankedListEl) rankedListEl.innerHTML = '<div class="text-muted" style="text-align: center; padding: 14px; font-size: 0.8rem;">Agent routing evaluation skipped.</div>';
    }

    // 3. Skills Card Rendering
    const matchedSkillsListEl = document.getElementById('semLabMatchedSkillsList');
    const skillBadgeEl = document.getElementById('semLabSkillBadge');
    const activatedSkillsTextEl = document.getElementById('semLabActivatedSkillsText');
    const skillExplainEl = document.getElementById('semLabSkillExplainBox');

    if (skillRes && skillRes.status === 'success') {
      const rawMatches = skillRes.matches || [];
      // Deduplicate skills by unique name, keeping highest scoring match
      const seenSkills = new Set();
      const matches = [];
      for (const m of rawMatches) {
        const k = (m.name || m.skill_name || '').trim().toLowerCase();
        if (k && !seenSkills.has(k)) {
          seenSkills.add(k);
          matches.push(m);
        }
      }

      const activatedSkills = matches.slice(0, 2); // Top 2 unique skills pass to prompt

      if (skillEl) {
        skillEl.textContent = activatedSkills.length > 0 ? activatedSkills.map(s => s.name).join(', ') : 'None';
      }

      if (activatedSkillsTextEl) {
        activatedSkillsTextEl.textContent = activatedSkills.length > 0
          ? activatedSkills.map(s => `${s.name} (${Math.round((s.similarity_score || 0) * 100)}%)`).join(', ')
          : 'None (Scores below ' + Math.round(skillThresh * 100) + '% threshold)';
      }

      if (skillBadgeEl) {
        skillBadgeEl.textContent = `${matches.length} Skill Match(es)`;
        skillBadgeEl.className = 'status-badge ' + (matches.length > 0 ? 'active' : 'offline');
      }

      if (matchedSkillsListEl) {
        if (matches.length === 0) {
          matchedSkillsListEl.innerHTML = `<div class="text-muted" style="font-size: 0.8rem; text-align: center; padding: 20px;">No skills met the ${Math.round(skillThresh * 100)}% minimum similarity threshold for this query.</div>`;
        } else {
          matchedSkillsListEl.innerHTML = matches.map((s, idx) => {
            const score = s.similarity_score || 0;
            const pct = Math.min(100, Math.round(score * 100));
            const isActivated = idx < 2;

            return `
              <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid ${isActivated ? '#10b981' : '#334155'}; border-radius: 6px; padding: 8px 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <div style="font-weight: 700; font-size: 0.82rem; color: ${isActivated ? '#34d399' : '#f1f5f9'};">
                    ${isActivated ? '⚡ ' : ''}${escapeHtml(s.name)}
                    ${isActivated ? '<span style="font-size: 0.68rem; background: #065f46; color: #a7f3d0; padding: 1px 6px; border-radius: 3px; margin-left: 6px;">INJECTED IN LLM</span>' : ''}
                  </div>
                  <div style="font-weight: 700; font-size: 0.82rem; color: #34d399;">
                    ${pct}% <span style="font-size: 0.72rem; color: #94a3b8;">(${score.toFixed(4)})</span>
                  </div>
                </div>
                <div style="height: 6px; width: 100%; background: #1e293b; border-radius: 3px; overflow: hidden;">
                  <div style="height: 100%; width: ${pct}%; background: #10b981; transition: width 0.4s ease;"></div>
                </div>
                <div style="font-size: 0.72rem; color: #cbd5e1; margin-top: 6px; font-style: italic; background: #0f172a; padding: 4px 8px; border-radius: 4px;">
                  "${escapeHtml((s.chunk_text || s.text || '').substring(0, 150))}..."
                </div>
              </div>
            `;
          }).join('');
        }
      }

      if (skillExplainEl) {
        skillExplainEl.innerHTML = `
          <div style="margin-bottom: 6px;">
            <strong style="color: #cbd5e1;">Query Vectorized:</strong>
            <pre style="background: #0f172a; padding: 6px 10px; border-radius: 4px; color: #34d399; margin: 4px 0;">"${escapeHtml(query)}"</pre>
          </div>
          ${matches.map(s => `
            <div style="margin-top: 6px; padding: 6px; background: #0f172a; border-left: 3px solid #10b981; border-radius: 2px;">
              <div style="font-weight: 700; color: #34d399; font-size: 0.75rem;">Matched Skill: ${escapeHtml(s.name)} (Cosine Distance: ${(1.0 - (s.similarity_score || 0)).toFixed(4)}):</div>
              <pre style="font-size: 0.7rem; color: #94a3b8; white-space: pre-wrap; margin: 4px 0;">${escapeHtml(s.chunk_text || s.text || '')}</pre>
            </div>
          `).join('')}
        `;
      }
    } else if (skillRes && skillRes.status === 'error') {
      if (skillEl) skillEl.textContent = 'Error';
      if (skillBadgeEl) {
        skillBadgeEl.textContent = 'Error';
        skillBadgeEl.className = 'status-badge offline';
      }
      if (activatedSkillsTextEl) activatedSkillsTextEl.innerHTML = '<span style="color: #ef4444;">Query Error</span>';
      if (matchedSkillsListEl) matchedSkillsListEl.innerHTML = `<div style="color: #f87171; padding: 12px; font-size: 0.8rem;">${escapeHtml(skillRes.message || 'Error querying skills')}</div>`;
    } else if (mode === 'agents') {
      if (skillBadgeEl) {
        skillBadgeEl.textContent = 'Skipped (Agents Mode)';
        skillBadgeEl.className = 'status-badge offline';
      }
      if (activatedSkillsTextEl) activatedSkillsTextEl.textContent = 'Skipped in Agents Mode';
      if (matchedSkillsListEl) matchedSkillsListEl.innerHTML = '<div class="text-muted" style="text-align: center; padding: 14px; font-size: 0.8rem;">Skill vector query skipped.</div>';
    }
  }

  // Render Batch Results
  function renderSemanticLabBatchResults(data, elapsedMs) {
    const batchCard = document.getElementById('semLabBatchResultsCard');
    const tbody = document.getElementById('semLabBatchTbody');
    const latEl = document.getElementById('semLabMetricLatency');
    const statusEl = document.getElementById('semLabMetricStatus');

    if (latEl) latEl.textContent = `${data.total_latency_ms || elapsedMs} ms`;
    if (statusEl) {
      statusEl.textContent = `Batch (${(data.results || []).length} Prompts)`;
      statusEl.style.color = '#38bdf8';
    }

    if (batchCard) batchCard.style.display = 'block';

    if (tbody) {
      const results = data.results || [];
      tbody.innerHTML = results.map(r => {
        const isFallback = r.is_fallback;
        const agentScorePct = Math.round((r.agent_score || 0) * 100);
        const skillScorePct = Math.round((r.skill_score || 0) * 100);

        return `
          <tr>
            <td><strong style="color: #f1f5f9;">${escapeHtml(r.prompt)}</strong></td>
            <td>
              <span style="color: ${isFallback ? '#fbbf24' : '#38bdf8'}; font-weight: 600;">
                ${escapeHtml(r.selected_agent)}
              </span>
            </td>
            <td style="text-align: center; font-weight: 700; color: ${agentScorePct > 50 ? '#34d399' : '#94a3b8'};">
              ${agentScorePct}%
            </td>
            <td>
              <span style="color: #a78bfa; font-weight: 600;">
                ${escapeHtml(r.top_skill)}
              </span>
            </td>
            <td style="text-align: center; font-weight: 700; color: ${skillScorePct > 20 ? '#34d399' : '#94a3b8'};">
              ${skillScorePct}%
            </td>
            <td style="text-align: center;">
              <span class="status-badge ${isFallback ? 'offline' : 'active'}" style="font-size: 0.72rem;">
                ${isFallback ? 'Fallback' : 'Specialized'}
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  window.loadSemanticLabData = loadSemanticLabData;
  window.runSemanticLabEvaluation = runSemanticLabEvaluation;

  // Initial Data Load
  loadModelsAndSkills();
  loadContainers();
  loadAgentsData();
  loadSemanticLabData();
  // Immediate health check ping on startup
  fetch('/api/router/agents/health_check_all', { method: 'POST' }).then(() => loadAgentsData()).catch(() => {});

  // Auto-refresh active view every 15 seconds so data updates in real-time
  setInterval(() => {
    if (currentActiveTab === 'page-telemetry') {
      loadTelemetryData();
    } else if (currentActiveTab === 'page-audit') {
      loadAuditLogs();
    }
  }, 15000);

  // Periodically probe actual status of all registered agents every 30 seconds
  setInterval(async () => {
    try {
      await fetch('/api/router/agents/health_check_all', { method: 'POST' }).catch(() => {});
      await loadAgentsData();
    } catch (e) {
      console.warn('30s agent health check error:', e);
    }
  }, 30000);
});

