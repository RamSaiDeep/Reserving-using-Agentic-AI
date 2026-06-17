// ================================================================
// app.js — Main Application Controller (Fixed with Manual Controls)
// ================================================================

// ── Global State ─────────────────────────────────────────────────
const State = {
  step: 0,              // 0=Upload 1=Summary 2=Triangle 3=Model 4=Execute
  triangle: null,
  summary: null,
  recommendation: null,
  selectedMethod: null,
  customLDFs: null,
  ldfBase: 'volumeWeighted', // volumeWeighted, straightAvg, weighted3yr, weighted5yr
  methodParams: {},
  fittedModel: null,
  gemini: null,
  chatHistory: [],
  apiKey: '',
};

const STEPS = ['Upload', 'Data Summary', 'Loss Triangle', 'Select Model', 'IBNR Results'];

// ── Boot ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupDropzone();
  setupChat();
  setupAPIKey();
  renderStepBar();
  setRightPanel('upload');
  addAgentMessage('system', 'Welcome to the Actuarial Reserving Platform. Upload a CSV file to begin.');
});

// ── API Key ───────────────────────────────────────────────────────
function setupAPIKey() {
  const btn   = document.getElementById('api-key-btn');
  const modal = document.getElementById('api-key-modal');
  const input = document.getElementById('api-key-input');
  const save  = document.getElementById('api-key-save');
  const cancel = document.getElementById('api-key-cancel');
  const ind   = document.getElementById('api-key-indicator');

  const stored = localStorage.getItem('gemini_api_key');
  if (stored) {
    State.apiKey = stored;
    State.gemini = new GeminiClient(stored);
    ind.classList.add('connected');
    ind.title = 'Gemini API connected';
  }

  btn.addEventListener('click', () => {
    input.value = State.apiKey;
    modal.classList.add('open');
  });

  save.addEventListener('click', () => {
    const key = input.value.trim();
    if (!key) { showToast('Please enter a valid API key.', 'error'); return; }
    State.apiKey = key;
    State.gemini = new GeminiClient(key);
    localStorage.setItem('gemini_api_key', key);
    ind.classList.add('connected');
    ind.title = 'Gemini API connected';
    modal.classList.remove('open');
    showToast('API key saved. Gemini is ready.', 'success');
  });

  cancel.addEventListener('click', () => modal.classList.remove('open'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); });
}

// ── Step Management ───────────────────────────────────────────────
function renderStepBar() {
  const bar = document.getElementById('step-bar');
  bar.innerHTML = STEPS.map((label, i) => `
    <div class="step-item ${i < State.step ? 'done' : i === State.step ? 'active' : 'pending'}">
      <div class="step-dot">${i < State.step ? '✓' : i + 1}</div>
      <div class="step-label">${label}</div>
    </div>
    ${i < STEPS.length - 1 ? '<div class="step-line ' + (i < State.step ? 'done' : '') + '"></div>' : ''}
  `).join('');
}

function advanceStep(n) {
  State.step = n;
  renderStepBar();
}

// ── Right Panel Renderer ──────────────────────────────────────────
function setRightPanel(view, data = {}) {
  const panel = document.getElementById('right-panel');
  panel.innerHTML = '';

  switch (view) {
    case 'upload':       panel.innerHTML = renderUploadView(); setupDropzone(); break;
    case 'summary':      panel.innerHTML = renderSummaryView(data); break;
    case 'triangle':     panel.innerHTML = renderTriangleView(data); setupLDFEditing(); break;
    case 'model-select': panel.innerHTML = renderModelSelectView(data); break;
    case 'params':       panel.innerHTML = renderParamsView(data); break;
    case 'results':      panel.innerHTML = renderResultsView(data); break;
  }
}

// ── Upload View ───────────────────────────────────────────────────
function renderUploadView() {
  return `
    <div class="view-header">
      <h2>Upload Loss Data</h2>
      <p class="view-sub">Supports CSV in wide format (AY × dev ages) or long format (one row per AY/dev)</p>
    </div>

    <div class="dropzone" id="dropzone">
      <div class="dz-icon">↑</div>
      <div class="dz-title">Drop CSV file here</div>
      <div class="dz-sub">or click to browse</div>
      <input type="file" id="file-input" accept=".csv,.txt" style="display:none">
    </div>

    <div class="format-guide">
      <div class="format-card">
        <div class="format-title">Wide Format</div>
        <div class="format-desc">Triangle already formed. Columns are development periods.</div>
        <pre class="format-example">accident_year, 12, 24, 36, 48
2020, 1200000, 2100000, 2700000, 2950000
2021, 1350000, 2400000, 3050000</pre>
      </div>
      <div class="format-card">
        <div class="format-title">Long Format</div>
        <div class="format-desc">One row per AY/dev combination. Supports more columns.</div>
        <pre class="format-example">accident_year, dev_age, paid, premium
2020, 12, 1200000, 5000000
2020, 24, 2100000, 5000000
2021, 12, 1350000, 5500000</pre>
      </div>
    </div>`;
}

function setupDropzone() {
  const dz    = document.getElementById('dropzone');
  const input = document.getElementById('file-input');
  if (!dz || !input) return;

  dz.addEventListener('click', () => input.click());
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
  dz.addEventListener('drop', e => {
    e.preventDefault();
    dz.classList.remove('drag-over');
    processFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => processFile(input.files[0]));
}

async function processFile(file) {
  if (!file) return;
  if (!file.name.match(/\.(csv|txt)$/i)) {
    showToast('Please upload a .csv or .txt file.', 'error');
    return;
  }

  addAgentMessage('system', `Reading file: <strong>${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)`);

  const text = await file.text();
  try {
    State.triangle = Triangle.fromCSV(text);
    State.summary  = State.triangle.getSummary();
    
    // Print diagnostic logs if parsing was tricky
    if (State.summary.parseLog && State.summary.parseLog.length > 0) {
      console.log('--- CSV Parsing Log ---');
      State.summary.parseLog.forEach(l => console.log(l));
    }

    if (State.gemini) State.gemini.setContext({ summary: State.summary });

    addAgentMessage('system', `✓ Parsed successfully as <strong>${State.summary.format === 'wide' ? 'Wide' : 'Long'}</strong> format.`);
    advanceStep(1);
    runDataSummaryAgent();
  } catch (e) {
    showToast('CSV parse error: ' + e.message, 'error');
    addAgentMessage('error', `Failed to parse CSV: ${e.message}`);
    console.error(e);
  }
}

// ── Agent: Data Summary ────────────────────────────────────────────
function runDataSummaryAgent() {
  setRightPanel('summary', State.summary);
  const msgId = addAgentMessage('agent', '🔍 <strong>Data Summary Agent</strong> is analyzing your dataset…', 'analyzing');

  const fallbackMsg = `Found <strong>${State.summary.accidentYears}</strong> accident years (${State.summary.oldestAY}–${State.summary.latestAY}) across <strong>${State.summary.devPeriods}</strong> development periods. Triangle completeness: <strong>${State.summary.completeness}%</strong>.`;

  if (State.gemini) {
    const stepData = {
      ...State.summary,
      premiums: State.triangle.premiums,
      exposures: State.triangle.exposures,
    };
    State.gemini.narrateStep('data_summary', stepData)
      .then(reply => updateAgentMessage(msgId, reply))
      .catch(e => {
        console.error('Gemini error:', e);
        updateAgentMessage(msgId, fallbackMsg);
      });
  } else {
    updateAgentMessage(msgId, fallbackMsg);
  }
}

// ── Summary View ──────────────────────────────────────────────────
function renderSummaryView(s) {
  const isNew = s.isNewLOB;
  return `
    <div class="view-header">
      <h2>Data Summary</h2>
      <p class="view-sub">What the Data Summary Agent found in your CSV</p>
    </div>
    <div class="summary-grid">
      <div class="summary-card"><div class="sc-label">Accident Years</div><div class="sc-value">${s.accidentYears}</div><div class="sc-detail">${s.oldestAY} – ${s.latestAY}</div></div>
      <div class="summary-card"><div class="sc-label">Dev Periods</div><div class="sc-value">${s.devPeriods}</div><div class="sc-detail">Max: ${s.maxDevAge}m</div></div>
      <div class="summary-card"><div class="sc-label">Completeness</div><div class="sc-value">${s.completeness}%</div><div class="sc-detail">of upper triangle</div></div>
      <div class="summary-card"><div class="sc-label">Total Paid</div><div class="sc-value">${fmt(s.totalPaid)}</div><div class="sc-detail">latest diagonal</div></div>
      <div class="summary-card ${isNew ? 'warn' : 'ok'}">
        <div class="sc-label">New LOB?</div>
        <div class="sc-value">${isNew ? 'Yes ⚠' : 'No ✓'}</div>
        <div class="sc-detail">${isNew ? 'Limited history' : 'Established data'}</div>
      </div>
      <div class="summary-card ${s.hasPremium ? 'ok' : ''}">
        <div class="sc-label">Premium Data</div>
        <div class="sc-value">${s.hasPremium ? 'Yes ✓' : 'No'}</div>
        <div class="sc-detail">${s.hasPremium ? 'BF/CC available' : 'BF/CC limited'}</div>
      </div>
      <div class="summary-card">
        <div class="sc-label">Exposure Data</div>
        <div class="sc-value">${s.hasExposure ? 'Yes ✓' : 'No'}</div>
        <div class="sc-detail">${s.hasExposure ? 'Freq/Sev enabled' : 'Rate analysis limited'}</div>
      </div>
      <div class="summary-card">
        <div class="sc-label">Data Format</div>
        <div class="sc-value">${s.format === 'wide' ? 'Wide' : 'Long'}</div>
        <div class="sc-detail">Auto-detected</div>
      </div>
    </div>
    <div style="margin-top:24px; text-align:right;">
      <button class="btn-run" onclick="runConverterAgent()">Generate Loss Triangle →</button>
    </div>`;
}

// ── Agent: Converter ──────────────────────────────────────────────
function runConverterAgent() {
  advanceStep(2);
  
  // Set default custom LDFs if not set
  if (!State.customLDFs) {
    const stats = State.triangle.computeLDFs();
    State.customLDFs = stats.map(s => s[State.ldfBase] ?? s.volumeWeighted ?? 1.0);
  }

  setRightPanel('triangle', { triangle: State.triangle });
  const msgId = addAgentMessage('agent', '🔺 <strong>Converter Agent</strong> building loss development triangle…', 'analyzing');

  const s = State.summary;
  const fallbackMsg = `Triangle built: <strong>${s.accidentYears} accident years × ${s.devPeriods} development periods</strong>. The latest diagonal is highlighted.`;

  if (State.gemini) {
    State.gemini.narrateStep('converter', {
      accidentYears: s.accidentYears,
      devPeriods: s.devPeriods,
      completeness: s.completeness,
      totalPaid: s.totalPaid,
    }).then(reply => updateAgentMessage(msgId, reply)).catch(() => updateAgentMessage(msgId, fallbackMsg));
  } else {
    updateAgentMessage(msgId, fallbackMsg);
  }
}

// ── Triangle View ─────────────────────────────────────────────────
function renderTriangleView({ triangle }) {
  if (!triangle) return '<p class="loading">Loading…</p>';

  const ays    = triangle.accidentYears;
  const devs   = triangle.devAges;
  const matrix = triangle.matrix;
  const n      = ays.length;
  const ldfStats = triangle.computeLDFs();

  // Color scale
  let maxVal = 0;
  matrix.forEach(row => row.forEach(v => { if (v) maxVal = Math.max(maxVal, v); }));
  const cellColor = val => {
    if (val === null) return '';
    const pct = maxVal > 0 ? val / maxVal : 0;
    return `background: rgba(91,124,250,${(0.08 + pct * 0.3).toFixed(2)})`;
  };

  const triRows = ays.map((ay, i) => {
    const cells = devs.map((dev, j) => {
      const v = matrix[i][j];
      const isLatest = (j === triangle.getCurrentDevIndex()[i]);
      return `<td class="tri-cell ${isLatest ? 'latest' : ''} ${v === null ? 'empty' : ''}"
        style="${cellColor(v)}" title="${ay} @ ${dev}m: ${v !== null ? fmt(v) : '—'}">
        ${v !== null ? fmtShort(v) : '—'}
      </td>`;
    }).join('');
    return `<tr><td class="tri-ay">${ay}</td>${cells}</tr>`;
  }).join('');

  const rowHtml = (label, key, isCov = false) => {
    const cells = ldfStats.slice(0, -1).map(s => {
      let val = s[key];
      if (val == null) return `<td class="ldf-cell">—</td>`;
      if (isCov) {
        return `<td class="ldf-cell ${val > 0.15 ? 'warn-cell' : ''}">${(val * 100).toFixed(1)}%</td>`;
      }
      return `<td class="ldf-cell ${State.ldfBase === key ? 'active-base' : ''}">${val.toFixed(3)}</td>`;
    }).join('');
    return `<tr class="ldf-row ${State.ldfBase === key ? 'active-row' : ''}"><td class="tri-ay">${label}</td>${cells}<td></td></tr>`;
  };

  const vwRow  = rowHtml('Vol. Wtd LDF', 'volumeWeighted');
  const saRow  = rowHtml('Straight Avg', 'straightAvg');
  const w3Row  = rowHtml('3-Year Avg', 'weighted3yr');
  const w5Row  = rowHtml('5-Year Avg', 'weighted5yr');
  const covRow = rowHtml('CoV', 'cov', true);

  const selRow = ldfStats.map((s, j) =>
    s.isTail
      ? `<td class="ldf-cell tail">1.000<br><span style="font-size:10px;color:var(--muted)">tail</span></td>`
      : `<td class="ldf-cell"><input type="number" class="ldf-input" data-idx="${j}"
          value="${State.customLDFs[j]?.toFixed(4) || ''}" step="0.001" min="1"></td>`
  ).join('');

  const devHeaders = devs.map(d => `<th>${d}m</th>`).join('');

  return `
    <div class="view-header">
      <h2>Loss Development Triangle</h2>
      <div class="view-actions">
        <select id="ldf-base-select" onchange="changeLDFBase(this.value)" class="param-input" style="height:32px; padding:0 8px;">
          <option value="volumeWeighted" ${State.ldfBase === 'volumeWeighted' ? 'selected' : ''}>Vol. Weighted Avg</option>
          <option value="straightAvg" ${State.ldfBase === 'straightAvg' ? 'selected' : ''}>Straight Avg</option>
          <option value="weighted3yr" ${State.ldfBase === 'weighted3yr' ? 'selected' : ''}>3-Year Weighted Avg</option>
          <option value="weighted5yr" ${State.ldfBase === 'weighted5yr' ? 'selected' : ''}>5-Year Weighted Avg</option>
        </select>
        <button class="btn-ghost" onclick="resetLDFs()">Reset LDFs</button>
      </div>
    </div>

    <div class="info-banner">
      Outlined cells = latest diagonal. Adjust LDFs below to override the selected average.
    </div>

    <div class="table-scroll">
      <table class="tri-table">
        <thead><tr><th>AY ╲ Dev</th>${devHeaders}</tr></thead>
        <tbody>
          ${triRows}
          ${vwRow}${saRow}${w3Row}${w5Row}${covRow}
          <tr class="ldf-row sel-row"><td class="tri-ay">Selected LDF</td>${selRow}</tr>
        </tbody>
      </table>
    </div>
    
    <div style="margin-top:24px; text-align:right;">
      <button class="btn-run" onclick="runAnalysisAgent()">Run Analysis & Select Model →</button>
    </div>`;
}

function setupLDFEditing() {
  document.querySelectorAll('.ldf-input').forEach(input => {
    input.addEventListener('change', () => {
      const idx = parseInt(input.dataset.idx);
      const val = parseFloat(input.value);
      if (!isNaN(val) && val >= 1.0) {
        State.customLDFs[idx] = val;
      } else {
        input.value = State.customLDFs[idx]?.toFixed(4) || '';
      }
    });
  });
}

function changeLDFBase(base) {
  State.ldfBase = base;
  resetLDFs(false); // don't show toast
}

function resetLDFs(showMsg = true) {
  if (!State.triangle) return;
  const stats = State.triangle.computeLDFs();
  State.customLDFs = stats.map(s => s[State.ldfBase] ?? s.volumeWeighted ?? 1.0);
  setRightPanel('triangle', { triangle: State.triangle });
  if (showMsg) showToast(`LDFs reset to ${State.ldfBase}.`, 'info');
}

// ── Agent: Analysis ────────────────────────────────────────────────
function runAnalysisAgent() {
  advanceStep(3);
  State.recommendation = recommendMethod(State.triangle);
  setRightPanel('model-select', State.recommendation);
  
  const top = State.recommendation.ranked[0];
  const msgId = addAgentMessage('agent', '🤖 <strong>Analysis Agent</strong> evaluating reserving methods…', 'analyzing');

  const fallbackMsg = `Recommendation: <strong>${top.label}</strong>. ${top.reasons[0] || ''}`;

  if (State.gemini) {
    const scores = {};
    State.recommendation.ranked.forEach(r => scores[r.code] = r.score);
    State.gemini.narrateStep('analysis', {
      recommended: top.label,
      scores,
      warnings: State.recommendation.warnings,
      summary: State.summary,
    }).then(reply => updateAgentMessage(msgId, reply)).catch(() => updateAgentMessage(msgId, fallbackMsg));
  } else {
    updateAgentMessage(msgId, fallbackMsg);
  }
}

// ── Model Select View ─────────────────────────────────────────────
function renderModelSelectView({ ranked, warnings }) {
  const warningHTML = warnings.length
    ? `<div class="warning-banner">${warnings.map(w => `⚠ ${w}`).join('<br>')}</div>`
    : '';

  const cards = ranked.map(m => {
    const cls = ['method-card', m.recommended ? 'recommended' : '', m.score <= 1 ? 'disabled' : ''].join(' ').trim();
    const reasonsHTML = m.reasons.length ? `<ul class="method-reasons">${m.reasons.map(r => `<li>${r}</li>`).join('')}</ul>` : '';

    return `
      <div class="${cls}" data-code="${m.code}" onclick="selectMethod('${m.code}')">
        <div class="mc-header">
          <div class="mc-code">${m.code}</div>
          <div class="mc-label">${m.label}</div>
          ${m.recommended ? '<div class="mc-badge">AI RECOMMENDED</div>' : ''}
        </div>
        <div class="mc-desc">${m.description}</div>
        ${reasonsHTML}
        <div class="mc-score-bar"><div class="mc-score-fill" style="width:${Math.min(m.score * 12, 100)}%"></div></div>
        <div class="mc-score-label">Suitability Score: ${m.score}</div>
      </div>`;
  }).join('');

  return `
    <div class="view-header">
      <h2>Select Reserving Method</h2>
      <p class="view-sub">The Analysis Agent evaluated the methods against your data. <strong>Click a card to proceed.</strong></p>
    </div>
    ${warningHTML}
    <div class="method-grid">${cards}</div>`;
}

window.selectMethod = function(code) {
  State.selectedMethod = code;
  const MethodClass = METHODS[code];
  if (!MethodClass) return;

  const reqParams = MethodClass.getRequiredParams();
  if (MethodClass.needsPremium && !State.summary.hasPremium) {
    addAgentMessage('warn', `⚠ <strong>${MethodClass.label}</strong> requires premium data. You must enter it manually.`);
  }

  if (reqParams.length > 0 || (MethodClass.needsPremium && !State.summary.hasPremium)) {
    setRightPanel('params', { code, MethodClass, reqParams });
  } else {
    runExecutionAgent(code, {});
  }
};

// ── Params View ────────────────────────────────────────────────────
function renderParamsView({ code, MethodClass, reqParams }) {
  const needsPrem = MethodClass.needsPremium && !State.summary.hasPremium;

  const paramFields = reqParams.map(p => {
    if (p.type === 'select') {
      const opts = p.options.map(o => `<option value="${o}" ${o === p.default ? 'selected' : ''}>${o}</option>`).join('');
      return `<div class="param-field"><label>${p.label}</label><div class="param-hint">${p.hint}</div><select id="param-${p.key}" class="param-input" data-key="${p.key}">${opts}</select></div>`;
    }
    const unit = p.type === 'percent' ? '%' : '';
    return `<div class="param-field"><label>${p.label} ${unit ? `<span class="unit">${unit}</span>` : ''}</label><div class="param-hint">${p.hint}</div><input type="number" id="param-${p.key}" class="param-input" data-key="${p.key}" value="${p.default}" step="any"></div>`;
  }).join('');

  const premFields = needsPrem ? `<div class="params-title">⚠ Premium by Accident Year (Required)</div><div class="param-hint">Enter earned premium values below.</div><div class="prem-grid">` + State.triangle.accidentYears.map(ay => `<div class="prem-row"><span class="prem-ay">${ay}</span><input type="number" class="prem-input" data-ay="${ay}" placeholder="0" min="0"></div>`).join('') + `</div>` : '';

  return `
    <div class="view-header"><h2>${MethodClass.label} — Parameters</h2><button class="btn-ghost" onclick="setRightPanel('model-select', State.recommendation)">← Back</button></div>
    <div class="params-container">
      ${paramFields ? `<div class="params-section"><div class="params-title">Method Parameters</div>${paramFields}</div>` : ''}
      ${premFields ? `<div class="params-section">${premFields}</div>` : ''}
      <button class="btn-run" onclick="submitParams('${code}')">Run ${MethodClass.label} →</button>
    </div>`;
}

window.submitParams = function(code) {
  const params = {};
  document.querySelectorAll('.param-input').forEach(input => {
    params[input.dataset.key] = input.tagName === 'SELECT' ? input.value : parseFloat(input.value);
  });

  document.querySelectorAll('.prem-input').forEach(input => {
    const ay = parseInt(input.dataset.ay);
    const val = parseFloat(input.value);
    if (!isNaN(val) && val > 0) State.triangle.premiums[ay] = val;
  });

  State.methodParams = params;
  runExecutionAgent(code, params);
};

// ── Agent: Execution ──────────────────────────────────────────────
function runExecutionAgent(code, params) {
  const MethodClass = METHODS[code];
  if (!MethodClass) return;

  try {
    const model = new MethodClass();
    model.fit(State.triangle, params, State.customLDFs);
    State.fittedModel = model;

    const results = model.getResults();
    const totalIBNR = model.getTotalIBNR();
    const totalUlt  = model.getTotalUltimate();
    const totalPaid = State.triangle.getLatestDiagonal().reduce((s, v) => s + (v ?? 0), 0);

    if (State.gemini) {
      State.gemini.setContext({
        selectedMethod: MethodClass.label,
        ibnrResults: { totalIBNR, totalUltimate: totalUlt, totalPaid },
        ldfs: State.customLDFs,
        premiums: State.triangle.premiums,
      });
    }

    advanceStep(4);
    setRightPanel('results', { code, model, results, totalIBNR, totalUlt, totalPaid, params });

    const msgId = addAgentMessage('agent', `⚙️ <strong>Execution Agent</strong> running <strong>${MethodClass.label}</strong>…`, 'analyzing');
    const fallbackMsg = `<strong>${MethodClass.label}</strong> complete. Total IBNR: <strong>${fmt(totalIBNR)}</strong> on ultimate losses of <strong>${fmt(totalUlt)}</strong>.`;

    if (State.gemini) {
      State.gemini.narrateStep('execution', { method: MethodClass.label, results, totalIBNR, totalUlt, totalPaid, params })
        .then(reply => updateAgentMessage(msgId, reply))
        .catch(() => updateAgentMessage(msgId, fallbackMsg));
    } else {
      updateAgentMessage(msgId, fallbackMsg);
    }
  } catch (e) {
    addAgentMessage('error', `Execution failed: ${e.message}`);
    showToast('Model execution error: ' + e.message, 'error');
  }
}

// ── Results View ──────────────────────────────────────────────────
function renderResultsView({ code, model, results, totalIBNR, totalUlt, totalPaid, params }) {
  const MethodClass = METHODS[code];
  const isMack = code === 'MCL';
  const pctPaid = totalUlt > 0 ? (totalPaid / totalUlt * 100).toFixed(1) : '—';
  const pctIBNR = totalUlt > 0 ? (totalIBNR / totalUlt * 100).toFixed(1) : '—';

  const extraHeaders = isMack ? '<th>Std Error</th><th>CV%</th><th>IBNR 75th</th><th>IBNR 95th</th>' : '';
  const extraTotals  = isMack ? '<td>—</td><td>—</td><td>—</td><td>—</td>' : '';

  const rows = results.map(r => {
    const ibnrCls = r.ibnr < 0 ? 'neg-ibnr' : '';
    const extras = isMack ? `<td>${r.stdError != null ? fmt(r.stdError) : '—'}</td><td>${r.cv ?? '—'}%</td><td>${r.ibnr_75 != null ? fmt(r.ibnr_75) : '—'}</td><td>${r.ibnr_95 != null ? fmt(r.ibnr_95) : '—'}</td>` : '';
    return `<tr><td class="col-ay">${r.ay}</td><td>${fmt(r.paid)}</td><td>${fmt(r.ultimate)}</td><td class="${ibnrCls}">${fmt(r.ibnr)}</td><td>${r.pctReported ?? '—'}%</td><td>${r.cdfToUlt ?? '—'}</td>${extras}</tr>`;
  }).join('');

  return `
    <div class="view-header">
      <h2>${MethodClass.label} — IBNR Results</h2>
      <button class="btn-ghost" onclick="setRightPanel('model-select', State.recommendation); advanceStep(3);">← Change Method</button>
    </div>
    <div class="kpi-strip">
      <div class="kpi-block"><div class="kpi-label">Total IBNR</div><div class="kpi-value">${fmt(totalIBNR)}</div><div class="kpi-sub">${pctIBNR}% of ultimate</div></div>
      <div class="kpi-block"><div class="kpi-label">Total Ultimate</div><div class="kpi-value">${fmt(totalUlt)}</div><div class="kpi-sub">Projected losses</div></div>
      <div class="kpi-block"><div class="kpi-label">Total Paid</div><div class="kpi-value">${fmt(totalPaid)}</div><div class="kpi-sub">${pctPaid}% paid to date</div></div>
    </div>
    <div class="results-section">
      <div class="section-title">IBNR by Accident Year</div>
      <div class="table-scroll">
        <table class="results-table">
          <thead><tr><th>AY</th><th>Paid (Latest)</th><th>Ultimate</th><th>IBNR</th><th>% Reported</th><th>CDF to Ult</th>${extraHeaders}</tr></thead>
          <tbody>${rows}</tbody>
          <tfoot><tr class="totals-row"><td>Total</td><td>${fmt(totalPaid)}</td><td>${fmt(totalUlt)}</td><td>${fmt(totalIBNR)}</td><td>—</td><td>—</td>${extraTotals}</tr></tfoot>
        </table>
      </div>
    </div>`;
}

// ── Chat ──────────────────────────────────────────────────────────
function setupChat() {
  const input = document.getElementById('chat-input');
  const send  = document.getElementById('chat-send');
  const submit = async () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    if (!State.gemini) { showToast('Please set your Gemini API key first.', 'error'); return; }
    addChatMessage('user', text);
    State.chatHistory.push({ role: 'user', text });
    const typingId = addChatMessage('ai', '…', 'typing');
    try {
      const reply = await State.gemini.sendMessage(text, State.chatHistory.slice(-10));
      updateChatMessage(typingId, reply);
      State.chatHistory.push({ role: 'model', text: reply });
    } catch (e) {
      updateChatMessage(typingId, `Error: ${e.message}`);
    }
  };
  send.addEventListener('click', submit);
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } });
}

// ── UI Helpers ────────────────────────────────────────────────────
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

function addChatMessage(role, text, id = null) {
  const msgId = id || `chat-${++_msgId}`;
  const log = document.getElementById('agent-log');
  log.insertAdjacentHTML('beforeend', `<div class="chat-msg role-${role}" id="${msgId}"><div class="chat-bubble ${role}">${role === 'user' ? escapeHTML(text) : markdownToHTML(text)}</div></div>`);
  log.scrollTop = log.scrollHeight;
  return msgId;
}

function updateChatMessage(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.querySelector('.chat-bubble').innerHTML = markdownToHTML(text);
  el.classList.remove('typing');
  el.parentElement.scrollTop = el.parentElement.scrollHeight;
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

function escapeHTML(str) { return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function markdownToHTML(md) {
  if (!md) return '';
  return md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>').replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>').replace(/^- (.+)$/gm, '<li>$1</li>').replace(/(<li>[\s\S]*?<\/li>\n?)+/g, s => `<ul>${s}</ul>`).replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
}
function showToast(msg, type = 'info') {
  let toast = document.getElementById('toast');
  if (!toast) { toast = document.createElement('div'); toast.id = 'toast'; document.body.appendChild(toast); }
  toast.className = `toast toast-${type} show`;
  toast.textContent = msg;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 3500);
}
