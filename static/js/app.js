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
  // Tab Navigation
  // ---------------------------------------------------------------------------
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-target');
      if (!targetId || targetId === currentActiveTab) return;

      navTabs.forEach(t => t.classList.remove('active'));
      pageViews.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPage = document.getElementById(targetId);
      if (targetPage) targetPage.classList.add('active');

      currentActiveTab = targetId;

      // Lazy load view data
      if (targetId === 'page-ingest') {
        loadIngestionData();
      } else if (targetId === 'page-telemetry') {
        loadTelemetryData();
      } else if (targetId === 'page-audit') {
        loadAuditLogs();
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
    btnConfirmShutdown.disabled = (shutdownConfirmInput.value.trim() !== 'Shutdown the service');
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
        body: JSON.stringify({ confirmation: 'Shutdown the service' }),
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

        availableModelsData.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `${m.id} (Max tokens: ${m.output_token_limit})`;
          if (m.id === mData.default_model) {
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

    // 2. Append Pending Agent Bubble
    const pendingAgentBubble = appendPendingAgentBubble();
    btnSendMessage.disabled = true;

    try {
      const payload = {
        message: text,
        agent: agentChoice.value,
        model: chatModel.value,
        temperature: parseFloat(chatTemperature.value) || 0.7,
        max_tokens: parseInt(chatMaxTokens.value) || 4096,
        max_turns: parseInt(chatMaxTurns.value) || 3,
        rag_chunks: parseInt(chatRagChunks.value) || 5,
        skill_mode: chatSkills.value,
        skill_threshold: parseFloat(chatSkillThreshold.value) || 0.2,
        doc_threshold: parseFloat(docThresholdInput.value) || 0.3,
        custom_endpoint: customEndpoint.value.trim(),
      };

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Server error processing message.');

      // Update pending bubble with full response and detail box
      updateAgentBubble(pendingAgentBubble, data);

      // Render retrieved context evidence in Right Card
      renderEvidence(data.retrieved_evidence || {});

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

  function renderEvidence(evidence) {
    const skills = evidence.skills || [];
    const docs = evidence.documents || [];

    if (skills.length === 0 && docs.length === 0) {
      evidenceContainer.innerHTML = `
        <div class="empty-placeholder">
          <span class="empty-icon">📂</span>
          <p>No vector store context retrieved for this conversation.</p>
        </div>
      `;
      return;
    }

    let html = '';

    // Render Skills evidence
    if (skills.length > 0) {
      html += `
        <div class="evidence-doc-group">
          <div class="evidence-doc-header">
            <div class="evidence-doc-title"><span>⚡</span> Skills Vector Store Matches</div>
            <span class="similarity-badge">${skills.length} matched</span>
          </div>
          <div class="evidence-doc-body">
            ${skills.map(s => `
              <div class="evidence-chunk-item">
                <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                  <strong style="color:#fde047;">${escapeHtml(s.name)}</strong>
                  <span style="color:var(--text-muted);font-size:0.75rem;">Score: ${s.similarity}</span>
                </div>
                <div style="color:var(--text-secondary);font-size:0.75rem;">${escapeHtml(s.description || '')}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // Render Documents evidence grouped by document
    if (docs.length > 0) {
      docs.forEach(doc => {
        const chunks = doc.chunks || [];
        html += `
          <div class="evidence-doc-group">
            <div class="evidence-doc-header">
              <div class="evidence-doc-title"><span>📄</span> ${escapeHtml(doc.doc_name)}</div>
              <span class="similarity-badge">Top Match: ${doc.highest_similarity}</span>
            </div>
            <div class="evidence-doc-body">
              ${chunks.map(ch => `
                <div class="evidence-chunk-item">
                  <div style="display:flex;justify-content:space-between;margin-bottom:3px;font-size:0.72rem;color:var(--text-muted);">
                    <span>Chunk #${ch.index || 0}</span>
                    <span>Similarity: ${ch.similarity}</span>
                  </div>
                  <div>${escapeHtml(ch.text)}</div>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      });
    }

    evidenceContainer.innerHTML = html;
  }

  // ---------------------------------------------------------------------------
  // Page 2: Ingestion Logic
  // ---------------------------------------------------------------------------
  async function loadIngestionData() {
    try {
      // 1. Stats
      const sRes = await fetch('/api/vectordb/stats');
      if (sRes.ok) {
        const sData = await sRes.json();
        statChunksCount.textContent = sData.total_chunks || 0;
        statDocsCount.textContent = sData.total_documents || 0;
        statDbSize.textContent = sData.db_size_mb || '0.0';
        activeEmbedderModel = sData.active_model || 'bge-m3';
      }

      // 2. Ingested Docs
      const dRes = await fetch('/api/vectordb/documents');
      if (dRes.ok) {
        const dData = await dRes.json();
        const docs = dData.documents || [];
        if (docs.length === 0) {
          ingestedDocsTbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No documents ingested.</td></tr>`;
        } else {
          ingestedDocsTbody.innerHTML = docs.map(d => `
            <tr>
              <td><strong>${escapeHtml(d.doc_name)}</strong></td>
              <td>${d.chunk_count}</td>
              <td>${d.total_chars.toLocaleString()}</td>
              <td>
                <button class="btn-table-delete" data-doc="${escapeHtml(d.doc_name)}">Delete</button>
              </td>
            </tr>
          `).join('');

          // Bind delete buttons
          ingestedDocsTbody.querySelectorAll('.btn-table-delete').forEach(btn => {
            btn.addEventListener('click', async () => {
              const docName = btn.getAttribute('data-doc');
              if (confirm(`Delete document '${docName}' from vector store?`)) {
                await fetch(`/api/vectordb/document?doc_name=${encodeURIComponent(docName)}`, { method: 'DELETE' });
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
  document.querySelectorAll('.btn-sample-url').forEach(btn => {
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
      });

      if (telRangeSelect.value === 'Custom' && telStartDate.value && telEndDate.value) {
        params.append('start_date', telStartDate.value);
        params.append('end_date', telEndDate.value);
      }

      const res = await fetch(`/api/telemetry?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch telemetry data');
      const data = await res.json();

      // 1. Update Used Models Dropdown
      const usedModels = data.used_models || [];
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
      const s = data.summary || {};
      telTotalPrompts.textContent = (s.total_prompts || 0).toLocaleString();
      telTotalResponses.textContent = (s.total_responses || 0).toLocaleString();
      telTotalErrors.textContent = (s.total_errors || 0).toLocaleString();
      telTotalInTokens.textContent = (s.total_input_tokens || 0).toLocaleString();
      telTotalOutTokens.textContent = (s.total_output_tokens || 0).toLocaleString();

      // 3. Performance stats
      const p = data.performance || {};
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
    const labels = chartsData.labels || [];
    const prompts = chartsData.prompts || [];
    const responses = chartsData.responses || [];
    const errors = chartsData.errors || [];
    const inTokens = chartsData.input_tokens || [];
    const outTokens = chartsData.output_tokens || [];

    // Destroy existing Chart instances
    if (chartThroughputInstance) chartThroughputInstance.destroy();
    if (chartTokensInstance) chartTokensInstance.destroy();

    const chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } },
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
              label: 'Prompts',
              data: prompts,
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              tension: 0.3,
              fill: true,
            },
            {
              label: 'Responses',
              data: responses,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              tension: 0.3,
              fill: true,
            },
            {
              label: 'Errors',
              data: errors,
              borderColor: '#ef4444',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              tension: 0.3,
              fill: true,
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
    } else {
      customDateBoxes.classList.add('hidden');
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
      const res = await fetch('/api/logs');
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
        conversationsTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No conversations recorded yet.</td></tr>`;
        eventsTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No conversation events to display.</td></tr>`;
        selectedConvBadge.textContent = 'None Selected';
        return;
      }

      conversationsTbody.innerHTML = currentConversationsCache.map(c => `
        <tr class="conv-row ${c.conversation_id === selectedConversationId ? 'selected-row' : ''}" data-cid="${escapeHtml(c.conversation_id)}">
          <td><span style="font-family:var(--font-mono);font-size:0.75rem;">${escapeHtml(c.timestamp)}</span></td>
          <td><code style="color:#a5b4fc;">${escapeHtml(c.conversation_id)}</code></td>
          <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(c.user_query)}</td>
          <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(c.agent_response)}</td>
          <td><span class="badge">${escapeHtml(c.agent_type)}</span></td>
          <td><strong>${c.event_count}</strong></td>
        </tr>
      `).join('');

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
    selectedConvBadge.textContent = cid;

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
      const res = await fetch(`/api/logs/${encodeURIComponent(cid)}`);
      if (!res.ok) throw new Error('Failed to load events');
      const data = await res.json();
      currentEventsCache = data.events || [];

      if (currentEventsCache.length === 0) {
        eventsTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No events recorded for this conversation.</td></tr>`;
        return;
      }

      eventsTbody.innerHTML = currentEventsCache.map((evt, idx) => `
        <tr class="event-row" data-idx="${idx}">
          <td><span style="font-family:var(--font-mono);font-size:0.75rem;">${escapeHtml(evt.local_time)}</span></td>
          <td><span class="step-bubble ${evt.event_type.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(evt.event_type)}</span></td>
          <td><strong>${escapeHtml(evt.invoker)}</strong></td>
          <td>${escapeHtml(evt.target)}</td>
          <td>${escapeHtml(evt.short_description)}</td>
        </tr>
      `).join('');

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

    // Extract Prompt / Input
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
    } else if (payload.text_sample !== undefined && payload.text_sample !== null) {
      prompt = payload.text_sample;
    } else if (payload.input !== undefined && payload.input !== null) {
      prompt = payload.input;
    }

    // Extract Response / Output
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
    } else if (payload.output !== undefined && payload.output !== null) {
      response = payload.output;
    } else if (payload.raw_response !== undefined && payload.raw_response !== null) {
      response = payload.raw_response;
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
    eventModalMeta.innerHTML = `
      <div><span style="color:var(--text-muted);">Event ID:</span> <code>${escapeHtml(evt.id || '')}</code></div>
      <div><span style="color:var(--text-muted);">Time (Local):</span> <strong>${escapeHtml(evt.local_time || '')}</strong></div>
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

  // Initial Data Load
  loadModelsAndSkills();
});
