// ==========================================================================
// TrustFork Interactive Engine Controller
// ==========================================================================

let state = {};
let currentStepIndex = 0;
let events = [];
let isAutoPlaying = false;
let lastCopilotText = "";

const SCENARIO_STEPS = [
  {
    title: "1. Cluster Sync",
    desc: "Both nodes synchronized under Genesis Policy V1 ($20k limit).",
    actionHint: "Click '⚡ Sever Fiber Link' to simulate a split-brain network partition.",
    buttonLabel: "Sever Fiber Link ⚡",
    action: () => togglePartition()
  },
  {
    title: "2. Sever Link",
    desc: "Fiber is severed. Branch B is operating in offline-isolated mode.",
    actionHint: "Update Authority Policy to $10,000 while Branch is disconnected.",
    buttonLabel: "Update Authority Policy ($10k) 🏛️",
    action: () => updatePolicy(10000)
  },
  {
    title: "3. HQ Policy V2",
    desc: "Authority tightened risk limit to $10k. Branch B remains unaware.",
    actionHint: "Issue an offline loan of $20,000 at Edge Branch B under cached V1.",
    buttonLabel: "Authorize $20,000 Loan 🏢",
    action: () => requestLoan(20000)
  },
  {
    title: "4. Offline Sign",
    desc: "Branch B authorized $20,000 and generated an RFC 8785 Ed25519 receipt.",
    actionHint: "Reconnect the fiber optic link to allow reconciliation.",
    buttonLabel: "Reconnect Fiber Link 🔗",
    action: () => togglePartition()
  },
  {
    title: "5. Reconnect",
    desc: "Link restored. Divergent receipts are pending reconciliation.",
    actionHint: "Trigger the Reconciler to detect CRDT divergence and dispatch Saga recovery.",
    buttonLabel: "Trigger Reconciliation ⚖️",
    action: () => reconcile()
  },
  {
    title: "6. Saga & Copilot",
    desc: "Automated clawback saga executed. Inspect executive forensic verdict.",
    actionHint: "Simulation complete! Reset engine or explore different loan amounts.",
    buttonLabel: "Reset Simulation ↺",
    action: () => resetEngine()
  }
];

// --------------------------------------------------------------------------
// Initialization & Polling
// --------------------------------------------------------------------------
async function fetchState() {
  try {
    const res = await fetch('/api/state');
    if (!res.ok) throw new Error('Failed to fetch state');
    state = await res.json();
    render();
  } catch (err) {
    console.error("API connection failed:", err);
  }
}

// --------------------------------------------------------------------------
// Core Render Loop
// --------------------------------------------------------------------------
function render() {
  renderNavbar();
  renderStepper();
  renderTopology();
  renderMerkleDAG();
  renderReconciliation();
}

// --------------------------------------------------------------------------
// 1. Navigation & Cluster Telemetry
// --------------------------------------------------------------------------
function renderNavbar() {
  const isPart = state.partition_active;
  const statusBadge = document.getElementById('cluster-status-badge');
  const statusText = document.getElementById('cluster-status-text');
  const toggleBtn = document.getElementById('btn-toggle-partition');

  if (isPart) {
    statusBadge.className = 'cluster-pill severed';
    statusText.textContent = 'FIBER SEVERED (SPLIT-BRAIN)';
    toggleBtn.textContent = '🔗 Reconnect Fiber Link';
    toggleBtn.className = 'btn btn-primary';
  } else {
    statusBadge.className = 'cluster-pill';
    statusText.textContent = 'CLUSTER HEALTHY (ONLINE)';
    toggleBtn.textContent = '⚡ Sever Fiber Link';
    toggleBtn.className = 'btn btn-warning';
  }
}

// --------------------------------------------------------------------------
// 2. Guided Scenario Stepper
// --------------------------------------------------------------------------
function calculateCurrentStep() {
  if (state.sagas && state.sagas.length > 0) return 5;
  if (state.branch_receipts && state.branch_receipts.length > 0 && !state.partition_active) return 4;
  if (state.branch_receipts && state.branch_receipts.length > 0 && state.partition_active) return 3;
  if (state.dag_nodes && state.dag_nodes.length > 1 && state.partition_active) return 2;
  if (state.partition_active) return 1;
  return 0;
}

function renderStepper() {
  currentStepIndex = calculateCurrentStep();
  const track = document.getElementById('stepper-steps-container');
  track.innerHTML = SCENARIO_STEPS.map((step, idx) => {
    const isCompleted = idx < currentStepIndex;
    const isActive = idx === currentStepIndex;
    let cls = 'stepper-step';
    if (isActive) cls += ' active';
    if (isCompleted) cls += ' completed';

    return `
      <div class="${cls}" onclick="setStep(${idx})">
        <div class="step-num-badge">${isCompleted ? '✓ DONE' : 'STEP 0' + (idx + 1)}</div>
        <div class="step-label">${step.title}</div>
      </div>
    `;
  }).join('');

  const current = SCENARIO_STEPS[currentStepIndex];
  document.getElementById('stepper-tip-text').innerHTML = `<strong>${current.desc}</strong> ${current.actionHint}`;
  const actionBtn = document.getElementById('btn-next-step');
  actionBtn.textContent = current.buttonLabel;
}

function executeCurrentStepAction() {
  const current = SCENARIO_STEPS[currentStepIndex];
  if (current && typeof current.action === 'function') {
    current.action();
  }
}

function setStep(idx) {
  currentStepIndex = idx;
  renderStepper();
}

function advanceStep(delta) {
  currentStepIndex = Math.max(0, Math.min(SCENARIO_STEPS.length - 1, currentStepIndex + delta));
  renderStepper();
}

// --------------------------------------------------------------------------
// 3. Visual Network Topology
// --------------------------------------------------------------------------
function renderTopology() {
  const container = document.getElementById('topology-container');
  const isPart = state.partition_active;
  const authHash = state.auth_policy_hash || '';
  const branchPolicyHash = state.branch_policy_hash || (state.dag_nodes ? state.dag_nodes[0]?.hash : '');
  const branchPubkey = state.branch_pubkey_hex || 'ed25519:3a89...';
  const lastRcpt = state.branch_receipts && state.branch_receipts.length ? state.branch_receipts[state.branch_receipts.length - 1] : null;

  // Active Policy Rule info
  const authNode = (state.dag_nodes || []).find(n => n.hash === authHash);
  const authLimit = authNode?.rules[0]?.max_amount || 20000;

  container.innerHTML = `
    <!-- Central Authority Node -->
    <div class="node-card">
      <div class="node-card-header">
        <div class="node-avatar avatar-auth">🏛️</div>
        <div class="node-heading">
          <div class="node-title-row">
            <h3>Central Authority</h3>
            <span class="node-id-chip">node-auth-01</span>
          </div>
          <div class="node-subtext">Governance & Merkle Root Anchor</div>
        </div>
      </div>

      <div class="node-meta-grid">
        <div class="meta-tile">
          <span class="meta-label">Vector Clock</span>
          <span class="meta-val">${JSON.stringify(state.auth_clock || {})}</span>
        </div>
        <div class="meta-tile">
          <span class="meta-label">Active Limit</span>
          <span class="meta-val" style="color:var(--indigo-core)">$${authLimit.toLocaleString()}</span>
        </div>
        <div class="meta-tile" style="grid-column: span 2">
          <span class="meta-label">Current Policy Hash</span>
          <span class="meta-val" style="cursor:pointer" onclick="copyToClipboard('${authHash}', 'Authority Policy Hash')">
            ${authHash ? authHash.substring(0, 18) + '...' : 'Genesis'} 📋
          </span>
        </div>
      </div>

      <div class="node-action-zone">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:0.75rem;color:var(--text-secondary);font-weight:600">Publish Policy Update:</span>
          <span class="badge badge-indigo">Version 2.0</span>
        </div>
        <div class="preset-pills">
          <button class="preset-pill" onclick="updatePolicy(10000)">$10k (Stricter)</button>
          <button class="preset-pill" onclick="updatePolicy(15000)">$15k</button>
          <button class="preset-pill" onclick="updatePolicy(25000)">$25k</button>
        </div>
      </div>
    </div>

    <!-- Fiber Optic Link Stage -->
    <div class="fiber-chassis">
      <div class="fiber-badge ${isPart ? 'partitioned' : 'connected'}">
        ${isPart ? '⚡ FIBER SEVERED (SPLIT-BRAIN)' : '● FIBER LINK ACTIVE'}
      </div>

      <div class="fiber-svg-stage">
        <svg width="220" height="60" viewBox="0 0 220 60">
          <defs>
            <linearGradient id="fiber-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#6366f1" />
              <stop offset="50%" stop-color="#06b6d4" />
              <stop offset="100%" stop-color="#10b981" />
            </linearGradient>
          </defs>
          ${isPart ? `
            <line x1="10" y1="30" x2="85" y2="30" class="fiber-line-broken" />
            <line x1="135" y1="30" x2="210" y2="30" class="fiber-line-broken" />
            <text x="110" y="36" text-anchor="middle" class="spark-symbol">⚡</text>
          ` : `
            <line x1="10" y1="30" x2="210" y2="30" class="fiber-line-connected" />
            <circle cx="20" cy="30" r="4" class="packet-circle" />
            <circle cx="200" cy="30" r="3.5" class="packet-reverse" />
          `}
        </svg>
      </div>

      <div style="font-size:0.72rem;color:var(--text-muted);text-align:center">
        ${isPart ? 'Cross-partition consensus halted (CAP Theorem)' : 'Sub-millisecond Heartbeat Sync'}
      </div>
    </div>

    <!-- Edge Branch B Node -->
    <div class="node-card">
      <div class="node-card-header">
        <div class="node-avatar avatar-branch">🏢</div>
        <div class="node-heading">
          <div class="node-title-row">
            <h3>Edge Branch B</h3>
            <span class="node-id-chip">branch-apac-b</span>
          </div>
          <div class="node-subtext">Partition-Tolerant Edge Worker</div>
        </div>
      </div>

      <div class="node-meta-grid">
        <div class="meta-tile">
          <span class="meta-label">Vector Clock</span>
          <span class="meta-val">${JSON.stringify(state.branch_clock || {})}</span>
        </div>
        <div class="meta-tile">
          <span class="meta-label">Cached Policy</span>
          <span class="meta-val" style="color:var(--cyan-core)">V1.0 ($20,000)</span>
        </div>
        <div class="meta-tile" style="grid-column: span 2">
          <span class="meta-label">Ed25519 Public Key</span>
          <span class="meta-val" style="cursor:pointer" onclick="copyToClipboard('${branchPubkey}', 'Branch Public Key')">
            ${branchPubkey.substring(0, 18)}... 📋
          </span>
        </div>
      </div>

      <div class="node-action-zone">
        <div class="slider-group">
          <div class="slider-header">
            <span>Loan Request Amount</span>
            <span class="slider-val-strong" id="loan-display">$20,000</span>
          </div>
          <input type="range" id="loan-slider" min="5000" max="30000" step="1000" value="20000"
                 oninput="document.getElementById('loan-display').textContent = '$' + Number(this.value).toLocaleString()">
          <div class="preset-pills" style="margin-top:0.25rem">
            <button class="preset-pill" onclick="setLoanAmount(10000)">$10k</button>
            <button class="preset-pill" onclick="setLoanAmount(20000)">$20k</button>
            <button class="preset-pill" onclick="setLoanAmount(25000)">$25k</button>
          </div>
        </div>

        <button class="btn btn-cyan" onclick="requestLoanFromSlider()">
          ⚡ Authorize & Sign (RFC 8785)
        </button>

        ${lastRcpt ? `
          <div style="background:rgba(0,0,0,0.3);border:1px solid var(--border-subtle);border-radius:6px;padding:8px 10px;font-family:var(--font-mono);font-size:0.75rem">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
              <strong style="color:var(--cyan-core)">${lastRcpt.payload.receipt_id}</strong>
              <button class="btn btn-ghost btn-sm" style="padding:1px 6px;font-size:0.7rem" onclick="runCopilot('${lastRcpt.payload.receipt_id}')">
                🤖 Copilot Audit
              </button>
            </div>
            <div style="color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
              Sig: ${lastRcpt.signature.substring(0, 24)}...
            </div>
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function setLoanAmount(val) {
  const slider = document.getElementById('loan-slider');
  if (slider) {
    slider.value = val;
    document.getElementById('loan-display').textContent = '$' + Number(val).toLocaleString();
  }
}

function requestLoanFromSlider() {
  const slider = document.getElementById('loan-slider');
  const val = slider ? Number(slider.value) : 20000;
  requestLoan(val);
}

// --------------------------------------------------------------------------
// 4. Merkle-CRDT Policy Tree Explorer
// --------------------------------------------------------------------------
function renderMerkleDAG() {
  const nodesList = document.getElementById('dag-nodes-list');
  const countBadge = document.getElementById('dag-node-count');
  const nodes = state.dag_nodes || [];
  
  countBadge.textContent = `${nodes.length} Nodes in DAG`;

  nodesList.innerHTML = nodes.map((node, idx) => {
    const isAuth = node.hash === state.auth_policy_hash;
    const isBranch = node.hash === (state.branch_policy_hash || state.dag_nodes[0]?.hash);
    
    let borderClass = '';
    if (isAuth && isBranch) borderClass = 'is-authority is-branch';
    else if (isAuth) borderClass = 'is-authority';
    else if (isBranch) borderClass = 'is-branch';

    const rule = node.rules[0] || {};

    return `
      <div class="dag-node-card ${borderClass}">
        <div class="dag-node-top">
          <div class="dag-version-tag">
            <span>Version ${node.version}</span>
            ${isAuth ? '<span class="badge badge-indigo">Authority Head</span>' : ''}
            ${isBranch ? '<span class="badge badge-cyan">Branch Cached</span>' : ''}
          </div>
          <span class="dag-hash-chip" onclick="copyToClipboard('${node.hash}', 'Policy SHA-256 Hash')">
            ${node.hash.substring(0, 16)}... 📋
          </span>
        </div>

        <div class="dag-rules-summary">
          <span>Max Limit: <strong>$${(rule.max_amount || 0).toLocaleString()}</strong></span>
          <span>Action: <strong>${rule.action || 'loan'}</strong></span>
          <span>Compensation: <strong>${rule.compensation || 'clawback'}</strong></span>
        </div>

        <div class="dag-ancestry">
          Parent: ${node.parent ? `<span style="color:var(--text-secondary)">${node.parent.substring(0, 16)}...</span>` : '<span style="color:var(--emerald-core)">Genesis Anchor (Root)</span>'}
        </div>
      </div>
    `;
  }).join('');
}

// --------------------------------------------------------------------------
// 5. Reconciliation & Saga Ledger
// --------------------------------------------------------------------------
function renderReconciliation() {
  const isPart = state.partition_active;
  const reconcileBtn = document.getElementById('btn-trigger-reconcile');
  const sagas = state.sagas || [];
  const tbody = document.getElementById('saga-table-body');

  if (reconcileBtn) {
    reconcileBtn.disabled = isPart;
    reconcileBtn.title = isPart ? "Cannot reconcile while fiber is severed!" : "Reconcile offline receipts with DAG";
  }

  // Update pipeline checkmarks if reconciliation has run
  if (state.history && state.history.length > 0) {
    for (let i = 1; i <= 4; i++) {
      const step = document.getElementById(`pipe-step-${i}`);
      const timeChip = document.getElementById(`pipe-time-${i}`);
      if (step) step.className = 'pipeline-step-item passed';
      if (timeChip) {
        timeChip.textContent = i === 1 ? '0.4ms' : i === 2 ? '0.2ms' : i === 3 ? '0.1ms' : '1.2ms';
      }
    }
  }

  if (!sagas.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center;color:var(--text-muted);padding:1.2rem;font-style:italic">
          No sagas recorded. Dispatches forward recovery automatically upon divergence.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = sagas.map(s => {
    const excess = s.details?.excess || 0;
    return `
      <tr>
        <td><code>${s.saga_id}</code></td>
        <td><strong>${s.action}</strong></td>
        <td><span style="color:var(--rose-core);font-weight:700">-$${excess.toLocaleString()}</span></td>
        <td><code style="font-size:0.75rem">${s.idempotency_key}</code></td>
        <td><span class="badge badge-emerald">${s.state}</span></td>
        <td>
          <button class="btn btn-ghost btn-sm" style="padding:2px 8px;font-size:0.72rem" onclick="runCopilot('${s.receipt_id}')">
            📋 Audit
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// --------------------------------------------------------------------------
// 6. Forensic Audit Copilot Terminal
// --------------------------------------------------------------------------
async function runCopilot(receiptId) {
  const output = document.getElementById('copilot-output');
  output.innerHTML = `
    <div style="text-align:center;color:var(--cyan-core);padding:2rem 1rem">
      <div class="status-beacon" style="margin:0 auto 10px auto;width:12px;height:12px"></div>
      <div style="font-family:var(--font-mono);font-size:0.85rem">
        AuditCopilot inspecting Merkle DAG, Vector Clocks, and SQLite Saga store...
      </div>
    </div>
  `;

  try {
    const res = await fetch('/api/copilot/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ receipt_id: receiptId })
    });

    if (!res.ok) throw new Error('Copilot analysis failed');
    const data = await res.json();
    lastCopilotText = data.explanation;

    // Convert markdown into rich styled HTML
    const formattedHtml = formatMarkdownVerdict(data.explanation);

    output.innerHTML = `
      <div class="copilot-card">
        <div class="copilot-card-top">
          <div>
            <span style="font-family:var(--font-mono);font-size:0.75rem;color:var(--text-muted)">TARGET RECEIPT:</span>
            <strong style="color:var(--text-pure);margin-left:6px">${data.receipt_id}</strong>
          </div>
          <div style="display:flex;gap:0.5rem">
            <span class="badge ${data.is_divergent ? 'badge-rose' : 'badge-emerald'}">
              ${data.relation}
            </span>
            <span class="badge ${data.is_divergent ? 'badge-amber' : 'badge-emerald'}">
              ${data.is_divergent ? 'DIVERGENT (RECONCILED)' : 'ALIGNED'}
            </span>
          </div>
        </div>

        <div class="copilot-markdown-content">
          ${formattedHtml}
        </div>
      </div>
    `;

    addEventLog('COPILOT', `Forensic audit verdict generated for ${receiptId} (${data.relation})`, 'auth');
  } catch (err) {
    output.innerHTML = `
      <div style="color:var(--rose-core);padding:1.5rem;font-family:var(--font-mono);font-size:0.82rem">
        ⚠️ Failed to run forensic copilot audit: ${err.message}
      </div>
    `;
  }
}

function formatMarkdownVerdict(md) {
  if (!md) return '';
  const lines = md.split('\n');
  let html = '';
  let inList = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('### ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<div class="copilot-verdict-h3" style="margin-bottom:0.5rem">${trimmed.substring(4)}</div>`;
    } else if (trimmed.startsWith('• ') || trimmed.startsWith('- ')) {
      if (!inList) { html += '<ul>'; inList = true; }
      let content = trimmed.substring(2);
      // Replace **bold** with <strong>bold</strong>
      content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      // Replace `code` with <code>code</code>
      content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
      html += `<li>${content}</li>`;
    } else if (trimmed.length > 0) {
      if (inList) { html += '</ul>'; inList = false; }
      let content = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
      html += `<p style="margin-bottom:0.4rem">${content}</p>`;
    }
  }
  if (inList) html += '</ul>';
  return html;
}

function copyCopilotReport() {
  if (!lastCopilotText) {
    showToast('No active Copilot report to copy. Run an audit first.');
    return;
  }
  copyToClipboard(lastCopilotText, 'Audit Verdict Markdown');
}

// --------------------------------------------------------------------------
// 7. Event Stream & Activity Logger
// --------------------------------------------------------------------------
function addEventLog(source, message, type = 'info') {
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
  
  const container = document.getElementById('event-stream-container');
  const countBadge = document.getElementById('event-count-badge');

  events.unshift({ time: timeStr, source, message, type });
  if (events.length > 40) events.pop();

  if (countBadge) countBadge.textContent = `${events.length} Events`;

  if (container) {
    container.innerHTML = events.map(e => {
      let badgeClass = 'event-badge-auth';
      if (e.type === 'branch') badgeClass = 'event-badge-branch';
      if (e.type === 'alert') badgeClass = 'event-badge-alert';
      if (e.type === 'success') badgeClass = 'event-badge-success';

      return `
        <div class="event-entry">
          <span class="event-timestamp">[${e.time}]</span>
          <span class="${badgeClass}">[${e.source}]</span>
          <span>${e.message}</span>
        </div>
      `;
    }).join('');
  }
}

// --------------------------------------------------------------------------
// 8. Server API Invocation Handlers
// --------------------------------------------------------------------------
async function togglePartition() {
  try {
    const res = await fetch('/api/partition/toggle', { method: 'POST' });
    const data = await res.json();
    if (data.partition_active) {
      addEventLog('NETWORK', '⚡ Fiber link severed! Split-brain risk active. Branch B in isolated mode.', 'alert');
      showToast('⚠️ Fiber link severed! Partition active.');
    } else {
      addEventLog('NETWORK', '🔗 Fiber link reconnected. Peers can now reconcile divergent receipts.', 'success');
      showToast('🔗 Network healed. Reconnected to Central Authority.');
    }
    await fetchState();
  } catch (err) {
    showToast('Error toggling partition: ' + err.message);
  }
}

async function updatePolicy(maxAmount = 10000) {
  try {
    const res = await fetch(`/api/authority/update-policy?max_amount=${maxAmount}`, { method: 'POST' });
    const data = await res.json();
    addEventLog('AUTHORITY', `🏛️ Policy updated to Version 2.0. Limit: $${maxAmount.toLocaleString()} (Hash: ${data.hash.substring(0, 8)}...)`, 'auth');
    showToast(`🏛️ Policy updated to $${maxAmount.toLocaleString()}`);
    await fetchState();
  } catch (err) {
    showToast('Error updating policy: ' + err.message);
  }
}

async function requestLoan(amount = 20000) {
  try {
    const res = await fetch(`/api/branch/request-loan?amount=${amount}`, { method: 'POST' });
    const data = await res.json();
    const rcpt = data.receipt;
    addEventLog('BRANCH_B', `🏢 Approved and signed loan for $${amount.toLocaleString()}. Receipt: ${rcpt.payload.receipt_id}`, 'branch');
    showToast(`🏢 Approved $${amount.toLocaleString()} loan (Receipt: ${rcpt.payload.receipt_id})`);
    await fetchState();
  } catch (err) {
    showToast('Error requesting loan: ' + err.message);
  }
}

async function reconcile() {
  try {
    // Visual pipeline animation
    for (let i = 1; i <= 4; i++) {
      const step = document.getElementById(`pipe-step-${i}`);
      if (step) step.className = 'pipeline-step-item active';
      await new Promise(r => setTimeout(r, 120));
      if (step) step.className = 'pipeline-step-item passed';
    }

    const res = await fetch('/api/reconcile', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Reconciliation failed');
    }
    const data = await res.json();
    
    if (data.results && data.results.length > 0) {
      for (const r of data.results) {
        addEventLog('RECONCILER', `⚖️ Reconciled ${r.receipt_id}: ${r.status}. Action: ${r.compensation?.action || 'Committed'}`, 'success');
        showToast(`⚖️ Reconciled ${r.receipt_id}: Forward recovery dispatched.`);
        // Auto-run Copilot audit on the first reconciled receipt
        await runCopilot(r.receipt_id);
      }
    } else {
      addEventLog('RECONCILER', '⚖️ Reconciler executed. All receipts aligned.', 'success');
      showToast('⚖️ Reconciled: All receipts aligned.');
    }

    await fetchState();
  } catch (err) {
    showToast('Reconciliation blocked: ' + err.message);
    addEventLog('RECONCILER', `⚠️ ${err.message}`, 'alert');
  }
}

async function resetEngine() {
  try {
    await fetch('/api/reset', { method: 'POST' });
    events = [];
    addEventLog('SYSTEM', 'Cluster engine reset to Genesis State (Policy V1, $20,000 max).', 'auth');
    showToast('↺ Cluster reset to initial state.');
    await fetchState();
    document.getElementById('copilot-output').innerHTML = `
      <div style="text-align:center;color:var(--text-muted);padding:2rem 1rem">
        <div style="font-size:2rem;margin-bottom:0.5rem">🤖</div>
        <div style="font-weight:600;color:var(--text-secondary);margin-bottom:0.25rem">Forensic Audit Ready</div>
        <div style="font-size:0.8rem">Click <strong>"Copilot Audit"</strong> on any signed receipt or saga record to inspect formal causal post-mortem analysis.</div>
      </div>
    `;
  } catch (err) {
    showToast('Error resetting engine: ' + err.message);
  }
}

// --------------------------------------------------------------------------
// 9. Automated Walkthrough Demo (Auto-Play)
// --------------------------------------------------------------------------
async function startAutoPlayDemo() {
  if (isAutoPlaying) return;
  isAutoPlaying = true;
  const btn = document.getElementById('btn-auto-play');
  btn.disabled = true;
  btn.textContent = '⏳ Playing Story...';

  try {
    // 0. Reset
    await resetEngine();
    await new Promise(r => setTimeout(r, 1500));

    // 1. Sever Link
    await togglePartition();
    await new Promise(r => setTimeout(r, 1800));

    // 2. Update HQ Policy to $10,000
    await updatePolicy(10000);
    await new Promise(r => setTimeout(r, 1800));

    // 3. Request $20,000 Loan at Branch B
    await requestLoan(20000);
    await new Promise(r => setTimeout(r, 1800));

    // 4. Reconnect Fiber Link
    await togglePartition();
    await new Promise(r => setTimeout(r, 1800));

    // 5. Reconcile
    await reconcile();

    showToast('✨ Auto-Play Demo Complete! Executive Audit Verdict rendered below.');
  } catch (err) {
    showToast('Auto-play aborted: ' + err.message);
  } finally {
    isAutoPlaying = false;
    btn.disabled = false;
    btn.textContent = '▶️ Auto-Play Story';
  }
}

// --------------------------------------------------------------------------
// 10. Utilities & Toast System
// --------------------------------------------------------------------------
function copyToClipboard(text, label = 'Content') {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(`📋 Copied ${label} to clipboard!`);
    }).catch(() => {
      fallbackCopy(text, label);
    });
  } else {
    fallbackCopy(text, label);
  }
}

function fallbackCopy(text, label) {
  const ta = document.createElement('textarea');
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
  showToast(`📋 Copied ${label} to clipboard!`);
}

function showToast(msg) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }, 3500);
}

// --------------------------------------------------------------------------
// Bootstrapping
// --------------------------------------------------------------------------
document.getElementById('btn-toggle-partition').addEventListener('click', togglePartition);
fetchState();
