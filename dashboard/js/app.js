// ================================================================
// app.js — Agentic Frontend Client
// ================================================================

const API_BASE = 'http://localhost:8000/api';

const State = {
  step: 0,
  sessionId: null,
  triangle: null,
  summary: null,
  recommendation: null,
  selectedMethod: null,
  customLDFs: null,
  ldfBase: 'volumeWeighted',
  methodParams: {},
  chatHistory: [],
  apiKey: '',
  baseUrl: '',
  modelName: '',
};

const STEPS = ['Ingestion Pipeline', 'Data Summary', 'Loss Triangle', 'Select Model', 'IBNR Results'];

document.addEventListener('DOMContentLoaded', () => {
  setupDropzone();
  setupChat();
  setupAPIKey();
  renderStepBar();
  setRightPanel('upload');
  addAgentMessage('system', 'Multi-Agent architecture active. Please start the Python server, then configure your parameters and upload a CSV file.');
});

// ── API Key ───────────────────────────────────────────────────────
function setupAPIKey() {
  const btn = document.getElementById('api-key-btn');
  const modal = document.getElementById('api-key-modal');
  const inputUrl = document.getElementById('api-baseurl-input');
  const inputModel = document.getElementById('api-model-input');
  const inputKey = document.getElementById('api-key-input');
  const save = document.getElementById('api-key-save');
  const cancel = document.getElementById('api-key-cancel');
  const ind = document.getElementById('api-key-indicator');

  State.baseUrl = localStorage.getItem('ai_base_url') || '';
  State.modelName = localStorage.getItem('ai_model_name') || '';
  State.apiKey = localStorage.getItem('ai_api_key') || '';

  if (State.apiKey) {
    ind.classList.add('connected');
    ind.title = 'AI API connected';
  }

  btn.addEventListener('click', () => { 
    inputUrl.value = State.baseUrl;
    inputModel.value = State.modelName;
    inputKey.value = State.apiKey;
    modal.classList.add('open'); 
  });
  
  save.addEventListener('click', () => {
    const key = inputKey.value.trim();
    if (!key) { showToast('Please enter a valid API key.', 'error'); return; }
    
    State.baseUrl = inputUrl.value.trim();
    State.modelName = inputModel.value.trim();
    State.apiKey = key;
    
    localStorage.setItem('ai_base_url', State.baseUrl);
    localStorage.setItem('ai_model_name', State.modelName);
    localStorage.setItem('ai_api_key', key);
    
    ind.classList.add('connected');
    modal.classList.remove('open');
    showToast('AI Settings saved.', 'success');
  });
  
  cancel.addEventListener('click', () => modal.classList.remove('open'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); });
}



// ── UI Helpers ────────────────────────────────────────────────────
function renderStepBar() {
  document.getElementById('step-bar').innerHTML = STEPS.map((label, i) => `
    <div class="step-item ${i < State.step ? 'done' : i === State.step ? 'active' : 'pending'}">
      <div class="step-dot">${i < State.step ? '✓' : i + 1}</div>
      <div class="step-label">${label}</div>
    </div>
    ${i < STEPS.length - 1 ? '<div class="step-line ' + (i < State.step ? 'done' : '') + '"></div>' : ''}
  `).join('');
}

function advanceStep(n) { State.step = n; renderStepBar(); }

let _msgId = 0;
function addAgentMessage(type, html, state = '') {
  const id = `msg-${++_msgId}`;
  const log = document.getElementById('agent-log');
  const icon = { system: '⬡', agent: '◆', action: '→', error: '✕', warn: '⚠' }[type] || '●';
  log.insertAdjacentHTML('beforeend', `<div class="agent-msg type-${type} ${state ? 'state-'+state : ''}" id="${id}"><span class="msg-icon">${icon}</span><span class="msg-body">${html}</span></div>`);
  log.scrollTop = log.scrollHeight;
  return id;
}

function updateAgentMessage(id, html) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('state-analyzing');
  el.querySelector('.msg-body').innerHTML = html;
  el.parentElement.scrollTop = el.parentElement.scrollHeight;
}

function showToast(msg, type = 'info') {
  let toast = document.getElementById('toast');
  if (!toast) { toast = document.createElement('div'); toast.id = 'toast'; document.body.appendChild(toast); }
  toast.className = `toast toast-${type} show`;
  toast.textContent = msg;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 3500);
}

function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtShort(n) {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

// ── Views ─────────────────────────────────────────────────────────
function setRightPanel(view, data = {}) {
  const panel = document.getElementById('right-panel');
  panel.innerHTML = '';
  switch (view) {
    case 'upload':       panel.innerHTML = renderUploadView(); setupDropzone(); break;
    case 'summary':      panel.innerHTML = renderSummaryView(data); break;
    case 'triangle':     panel.innerHTML = renderTriangleView(); setupLDFEditing(); break;
    case 'model-select': panel.innerHTML = renderModelSelectView(data); break;
    case 'params':       panel.innerHTML = renderParamsView(data); break;
    case 'results':      panel.innerHTML = renderResultsView(data); break;
  }
}

function renderUploadView() {
  return `
    <div class="view-header"><h2>Upload Loss Data</h2><p class="view-sub">Sequential Agent Pipeline</p></div>
    <div style="margin-bottom: 24px; padding: 16px; background: rgba(255,255,255,0.05); border-radius: 8px;">
      <label style="display:block; margin-bottom:8px; font-weight:500;">Loss Development Factor (LDF) configuration:</label>
      <div style="display:flex; align-items:center; gap: 12px;">
        <span>Calculate </span>
        <input type="number" id="n-years-input" value="5" min="1" max="20" class="param-input" style="width: 80px;">
        <span> year averages.</span>
      </div>
    </div>
    <div class="dropzone" id="dropzone"><div class="dz-icon">↑</div><div class="dz-title">Drop CSV file here</div><input type="file" id="file-input" accept=".csv,.txt" style="display:none"></div>
  `;
}

function setupDropzone() {
  const dz = document.getElementById('dropzone');
  const input = document.getElementById('file-input');
  if (!dz || !input) return;
  dz.addEventListener('click', () => input.click());
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
  dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('drag-over'); processFile(e.dataTransfer.files[0]); });
  input.addEventListener('change', () => processFile(input.files[0]));
}

async function processFile(file) {
  if (!file) return;
  const nYears = document.getElementById('n-years-input').value || 5;
  
  const msgId = addAgentMessage('agent', `🚀 Launching Sequential Multi-Agent Pipeline for <strong>${file.name}</strong>...`, 'analyzing');
  
  const formData = new FormData();
  formData.append('file', file);
  formData.append('n_years', nYears);
  if (State.apiKey) {
    formData.append('api_key', State.apiKey);
    formData.append('base_url', State.baseUrl);
    formData.append('model_name', State.modelName);
  }

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error('Network response was not ok');

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          if (msg.type === "agent") {
            addAgentMessage('action', `<strong>[${msg.agent}]</strong> ${msg.text}`);
            if (msg.agent === "System Error") {
              updateAgentMessage(msgId, 'Pipeline aborted due to error.');
            }
          } else if (msg.type === "complete") {
            State.sessionId = msg.session_id;
            State.summary = msg.summary;
            State.triangle = msg.triangle;
            State.recommendation = msg.recommendation; // Save the recommendation
            State.customLDFs = null;
            
            updateAgentMessage(msgId, 'Pipeline execution completed. See summary in right panel.');
            setTimeout(() => {
              advanceStep(1);
              setRightPanel('summary', State.summary);
            }, 1000);
          } else if (msg.type === "error") {
            updateAgentMessage(msgId, `Failed: ${msg.message}`);
          }
        } catch(err) {
          console.error("Stream parse error:", err);
        }
      }
    }
  } catch (e) {
    showToast('Pipeline Error: ' + e.message, 'error');
    updateAgentMessage(msgId, `Failed to process: ${e.message}`);
  }
}

function renderSummaryView(s) {
  return `
    <div class="view-header"><h2>Data Summary</h2></div>
    <div class="summary-grid">
      <div class="summary-card"><div class="sc-label">Accident Years</div><div class="sc-value">${s.accidentYears}</div><div class="sc-detail">${s.oldestAY} – ${s.latestAY}</div></div>
      <div class="summary-card"><div class="sc-label">Dev Periods</div><div class="sc-value">${s.devPeriods}</div><div class="sc-detail">Max: ${s.maxDevAge}m</div></div>
      <div class="summary-card"><div class="sc-label">Total Paid</div><div class="sc-value">${fmt(s.totalPaid)}</div><div class="sc-detail">latest diagonal</div></div>
      <div class="summary-card"><div class="sc-label">Premium Data</div><div class="sc-value">${s.hasPremium ? 'Yes ✓' : 'No'}</div></div>
    </div>
    <div style="margin-top:24px; text-align:right;"><button class="btn-run" onclick="viewTriangle()">Review Loss Triangle →</button></div>`;
}

function viewTriangle() {
  advanceStep(2);
  if (!State.customLDFs) {
    State.customLDFs = State.triangle.ldfs.slice(0, -1).map(s => s[State.ldfBase] ?? 1.0);
  }
  setRightPanel('triangle');
}

function renderTriangleView() {
  const t = State.triangle;
  const triRows = t.accidentYears.map((ay, i) => {
    const cells = t.devAges.map((dev, j) => {
      const v = t.matrix[i][j];
      return `<td class="tri-cell ${v === null ? 'empty' : ''}">${v !== null ? fmtShort(v) : '—'}</td>`;
    }).join('');
    return `<tr><td class="tri-ay">${ay}</td>${cells}</tr>`;
  }).join('');

  const rowHtml = (label, key) => {
    const cells = t.ldfs.slice(0, -1).map(s => `<td class="ldf-cell ${State.ldfBase === key ? 'active-base' : ''}">${s[key] ? s[key].toFixed(3) : '—'}</td>`).join('');
    return `<tr class="ldf-row ${State.ldfBase === key ? 'active-row' : ''}"><td class="tri-ay">${label}</td>${cells}<td></td></tr>`;
  };

  const selRow = State.customLDFs.map((v, j) => `<td class="ldf-cell"><input type="number" class="ldf-input" data-idx="${j}" value="${v.toFixed(4)}" step="0.001"></td>`).join('');
  const devHeaders = t.devAges.map(d => `<th>${d}m</th>`).join('');

  return `
    <div class="view-header">
      <h2>Loss Development Triangle</h2>
      <div class="view-actions">
        <select id="ldf-base-select" onchange="changeLDFBase(this.value)" class="param-input" style="height:32px;">
          <option value="volumeWeighted" ${State.ldfBase === 'volumeWeighted' ? 'selected' : ''}>Vol. Weighted Avg</option>
          <option value="straightAvg" ${State.ldfBase === 'straightAvg' ? 'selected' : ''}>Straight Avg</option>
          <option value="weighted3yr" ${State.ldfBase === 'weighted3yr' ? 'selected' : ''}>3-Year Weighted Avg</option>
          <option value="weighted5yr" ${State.ldfBase === 'weighted5yr' ? 'selected' : ''}>5-Year Weighted Avg</option>
        </select>
      </div>
    </div>
    <div class="table-scroll">
      <table class="tri-table">
        <thead><tr><th>AY ╲ Dev</th>${devHeaders}</tr></thead>
        <tbody>
          ${triRows}
          ${rowHtml('Vol. Wtd', 'volumeWeighted')}
          ${rowHtml('Straight', 'straightAvg')}
          ${rowHtml('3-Year', 'weighted3yr')}
          ${rowHtml('5-Year', 'weighted5yr')}
          <tr class="ldf-row sel-row"><td class="tri-ay">Selected LDF</td>${selRow}<td class="ldf-cell tail">1.000 (tail)</td></tr>
        </tbody>
      </table>
    </div>
    <div style="margin-top:24px; text-align:right;"><button class="btn-run" onclick="proceedToModelSelection()">Select Execution Model →</button></div>`;
}

function setupLDFEditing() {
  document.querySelectorAll('.ldf-input').forEach(input => {
    input.addEventListener('change', () => { State.customLDFs[parseInt(input.dataset.idx)] = parseFloat(input.value); });
  });
}

window.changeLDFBase = function(base) {
  State.ldfBase = base;
  State.customLDFs = State.triangle.ldfs.slice(0, -1).map(s => s[base] ?? 1.0);
  setRightPanel('triangle');
};

function proceedToModelSelection() {
  advanceStep(3);
  // Show all available methods for user to choose
  const ranked = [
    { code: 'BF', label: 'Bornhuetter-Ferguson', desc: 'Uses a priori expected loss ratios.', score: 10, recommended: true, params: [{key: 'aprioriLossRatio', label: 'A Priori Loss Ratio', default: 0.65}] },
    { code: 'CL', label: 'Chain Ladder (Basic)', desc: 'Standard development method.', score: 9, recommended: true, params: [] },
    { code: 'CC', label: 'Cape Cod', desc: 'Uses an overall loss ratio for stability.', score: 8, recommended: false, params: [{key: 'decay', label: 'Decay Factor', default: 1.0}] },
    { code: 'BK', label: 'Benktander', desc: 'Iterative blend of BF and CL.', score: 7, recommended: false, params: [{key: 'aprioriLossRatio', label: 'A Priori Loss Ratio', default: 0.65}, {key: 'iterations', label: 'Iterations (c)', default: 1}] },
    { code: 'MCL', label: 'Mack Chain Ladder', desc: 'Calculates standard errors and variance.', score: 6, recommended: false, params: [] },
    { code: 'CLK', label: 'Clark Stochastic', desc: 'Stochastic curve fitting approximation.', score: 5, recommended: false, params: [{key: 'curveType', label: 'Growth Curve', default: 'loglogistic'}] },
    { code: 'CO', label: 'Case Outstanding', desc: 'Uses only reported case reserves.', score: 4, recommended: false, params: [] }
  ];
  State.ranked = ranked;
  setRightPanel('model-select', { ranked });
}

function renderModelSelectView({ ranked }) {
  const cards = ranked.map(m => `
    <div class="method-card ${m.recommended ? 'recommended' : ''}" onclick="selectMethod('${m.code}')">
      <div class="mc-header"><div class="mc-code">${m.code}</div><div class="mc-label">${m.label}</div></div>
      <div class="mc-desc">${m.desc}</div>
      <div class="mc-score-bar"><div class="mc-score-fill" style="width:${Math.min(m.score * 10, 100)}%"></div></div>
    </div>`).join('');
  
  const recHtml = State.recommendation ? `
    <div style="margin-bottom: 24px; padding: 16px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px;">
      <h3 style="margin-top: 0; color: #60a5fa; font-size: 14px; margin-bottom: 8px;">✨ AI Recommendation</h3>
      <div style="font-size: 13px; line-height: 1.5; color: var(--text-main);">${State.recommendation}</div>
    </div>` : '';

  return `<div class="view-header"><h2>Select Execution Model</h2><p class="view-sub">Select a tool for the Execution Agent</p></div>${recHtml}<div class="method-grid">${cards}</div>`;
}

window.selectMethod = function(code) {
  State.selectedMethod = code;
  const method = State.ranked.find(m => m.code === code);
  const params = method ? method.params : [];
  if (params.length > 0) setRightPanel('params', { code, params });
  else submitParams(code);
};

function renderParamsView({ code, params }) {
  const fields = params.map(p => `<div class="param-field"><label>${p.label}</label><input type="number" id="param-${p.key}" class="param-input" data-key="${p.key}" value="${p.default}" step="any"></div>`).join('');
  return `<div class="view-header"><h2>Parameters</h2></div><div class="params-container">${fields}<button class="btn-run" onclick="submitParams('${code}')">Execute Tool →</button></div>`;
}

window.submitParams = async function(code) {
  const params = {};
  document.querySelectorAll('.param-input').forEach(i => params[i.dataset.key] = parseFloat(i.value));

  advanceStep(4);
  const msgId = addAgentMessage('agent', `⚙️ <strong>Execution Agent</strong> running ${code} on backend…`, 'analyzing');

  try {
    const res = await fetch(`${API_BASE}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: State.sessionId,
        method_code: code,
        params: params,
        custom_ldfs: [...State.customLDFs, 1.0], // add tail
        api_key: State.apiKey,
        base_url: State.baseUrl,
        model_name: State.modelName
      })
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    setRightPanel('results', data);
    
    updateAgentMessage(msgId, 'Execution complete. Report displayed in right panel.');
  } catch (e) {
    updateAgentMessage(msgId, 'Execution failed: ' + e.message);
  }
};

function renderResultsView(data) {
  // Extract all unique keys from results array to form dynamic columns
  let keys = new Set();
  data.results.forEach(r => Object.keys(r).forEach(k => keys.add(k)));
  keys = Array.from(keys);
  
  // Custom ordering: ay, paid, cdfToUlt, pctReported, ultimate, ibnr... then others
  const coreKeys = ['ay', 'paid', 'cdfToUlt', 'pctReported', 'ultimate', 'ibnr'];
  const extraKeys = keys.filter(k => !coreKeys.includes(k));
  const finalKeys = [...coreKeys, ...extraKeys];
  
  const headers = finalKeys.map(k => `<th>${k.charAt(0).toUpperCase() + k.slice(1)}</th>`).join('');
  const rows = data.results.map(r => {
    return '<tr>' + finalKeys.map(k => {
      let val = r[k];
      if (typeof val === 'number') {
        if (k === 'ay' || k === 'pctReported' || k.includes('ELR') || k.includes('cdf')) val = val;
        else val = fmt(val);
      }
      return `<td>${val != null ? val : '—'}</td>`;
    }).join('') + '</tr>';
  }).join('');
  
  return `
    <div class="view-header"><h2>IBNR Results</h2><button class="btn-ghost" onclick="advanceStep(3); proceedToModelSelection();">← Back</button></div>
    <div class="kpi-strip">
      <div class="kpi-block"><div class="kpi-label">Total IBNR</div><div class="kpi-value">${fmt(data.totalIBNR)}</div></div>
      <div class="kpi-block"><div class="kpi-label">Total Ultimate</div><div class="kpi-value">${fmt(data.totalUlt)}</div></div>
    </div>
    <div class="table-scroll" style="margin-bottom: 24px;">
      <table class="results-table">
        <thead><tr>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <h2 style="margin-bottom: 16px;">Execution Report</h2>
    <div id="report-container">
      ${(function() {
        if (!data.narration) return '<div style="color: rgba(255,255,255,0.5);">Detailed process explanation unavailable.</div>';
        try {
          let cleanJson = data.narration.replace(/```json/g, '').replace(/```/g, '').trim();
          const rep = JSON.parse(cleanJson);
          
          let inputsHtml = rep.inputs;
          if (Array.isArray(rep.inputs)) {
            inputsHtml = '<ul style="margin: 0; padding-left: 20px; color: rgba(255,255,255,0.9);">' + rep.inputs.map(i => `<li style="margin-bottom: 4px;">${i}</li>`).join('') + '</ul>';
          } else if (typeof rep.inputs === 'object' && rep.inputs !== null) {
            inputsHtml = '<ul style="margin: 0; padding-left: 20px; color: rgba(255,255,255,0.9);">' + Object.entries(rep.inputs).map(([k,v]) => `<li style="margin-bottom: 4px;"><strong>${k}:</strong> ${v}</li>`).join('') + '</ul>';
          }

          const numHtml = Object.entries(rep.output_numbers || {}).map(([k, v]) => `
            <div style="background: rgba(0,0,0,0.3); padding: 16px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.15); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
              <span style="color: rgba(255,255,255,0.6); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">${k}</span>
              <span style="font-weight: 700; color: #10b981; font-size: 24px;">${fmt(v)}</span>
            </div>
          `).join('');
          
          return `
            <div style="display: flex; flex-direction: column; gap: 8px; max-width: 800px; margin: 0 auto;">
              
              <!-- Step 1: Inputs -->
              <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="color: #60a5fa; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                  <span style="background: #3b82f6; color: white; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 10px;">1</span> REQUIRED INPUTS
                </div>
                <div style="font-size: 14px; line-height: 1.6; color: rgba(255,255,255,0.9);">${inputsHtml}</div>
              </div>
              
              <!-- Arrow Down -->
              <div style="text-align: center; color: rgba(255,255,255,0.2); font-size: 20px;">↓</div>
              
              <!-- Step 2: Process -->
              <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="color: #60a5fa; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                  <span style="background: #3b82f6; color: white; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 10px;">2</span> MATHEMATICAL PROCESS
                </div>
                <div style="font-size: 14px; line-height: 1.6; color: rgba(255,255,255,0.9);">${rep.process}</div>
                <div style="margin-top: 16px; padding-top: 16px; border-top: 1px dashed rgba(255,255,255,0.1); font-size: 13px; color: rgba(255,255,255,0.7); line-height: 1.5;">
                  <strong style="color: #a78bfa; text-transform: uppercase; font-size: 10px; letter-spacing: 1px; display: block; margin-bottom: 4px;">Impact of Exposures</strong> 
                  ${rep.impact}
                </div>
              </div>
              
              <!-- Arrow Down -->
              <div style="text-align: center; color: rgba(16, 185, 129, 0.4); font-size: 20px;">↓</div>
              
              <!-- Step 3: Output -->
              <div style="background: rgba(16, 185, 129, 0.05); padding: 24px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.3); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.05);">
                <div style="color: #10b981; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                  <span style="background: #10b981; color: white; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 10px;">3</span> FINAL OUTPUT & RECOMMENDATION
                </div>
                <div style="font-size: 14px; line-height: 1.6; color: rgba(255,255,255,0.9); margin-bottom: 24px;">${rep.output_text}</div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                  ${numHtml}
                </div>
              </div>
              
            </div>
          `;
        } catch (e) {
          return `<div style="padding: 16px; background: rgba(255,255,255,0.05); border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); font-size: 13px; line-height: 1.6; white-space: pre-wrap;">${data.narration}</div>`;
        }
      })()}
    </div>`;
}

function setupChat() {
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const submit = async () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    if (!State.apiKey) { showToast('API key required for chat.', 'error'); return; }
    if (!State.sessionId) { showToast('Upload data first to query the Parallel Agent.', 'error'); return; }
    
    addAgentMessage('user', escapeHTML(text));
    const typingId = addAgentMessage('agent', '…', 'analyzing');
    
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: State.sessionId,
          message: text,
          history: State.chatHistory,
          api_key: State.apiKey,
          base_url: State.baseUrl,
          model_name: State.modelName
        })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      
      State.chatHistory.push({ role: 'user', text });
      State.chatHistory.push({ role: 'model', text: data.reply });
      updateAgentMessage(typingId, data.reply);
    } catch (e) {
      updateAgentMessage(typingId, 'Error: ' + e.message);
    }
  };
  send.addEventListener('click', submit);
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } });
}

function escapeHTML(str) { return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
