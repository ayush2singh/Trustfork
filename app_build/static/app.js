// TrustFork Frontend Controller
let state = {};

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    state = await res.json();
    render();
  } catch (err) {
    console.error("API connection failed:", err);
  }
}

function renderTopology() {
  const top = document.getElementById('topology-container');
  const isPart = state.partition_active;
  top.innerHTML = `
    <div class="node-box">
      <div class="node-icon icon-auth">🏛️</div>
      <div class="node-meta">
        <h4>Central Authority</h4>
        <div class="node-clock">VC: ${JSON.stringify(state.auth_clock || {})}</div>
      </div>
    </div>
    <div class="fiber-link ${isPart ? 'partitioned' : 'connected'}"></div>
    <div class="node-box">
      <div class="node-icon icon-branch">🏢</div>
      <div class="node-meta">
        <h4>Edge Branch B</h4>
        <div class="node-clock">VC: ${JSON.stringify(state.branch_clock || {})}</div>
      </div>
    </div>
  `;
  const toggleBtn = document.getElementById('btn-toggle-partition');
  toggleBtn.textContent = isPart ? '🔗 Reconnect Fiber Link' : '⚡ Sever Network Link';
  toggleBtn.className = isPart ? 'btn btn-primary' : 'btn btn-warning';
}

function render() {
  renderTopology();
  renderAuthority();
  renderBranch();
  renderMerkleDAG();
  renderReconciliation();
}

function renderAuthority() {
  const card = document.getElementById('card-authority');
  const activeHash = (state.auth_policy_hash || '').substring(0, 16);
  card.innerHTML = `
    <div class="card-header">
      <div class="card-title">🏛️ Authority Controls</div>
      <span class="badge badge-indigo">Tip: ${activeHash}...</span>
    </div>
    <p class="subtitle">Governance node responsible for updating authoritative risk thresholds.</p>
    <button id="btn-update-policy" class="btn btn-ghost" onclick="updatePolicy()">Update Policy: Limit $10,000</button>
  `;
}

function renderBranch() {
  const card = document.getElementById('card-branch');
  const lastRcpt = state.branch_receipts && state.branch_receipts.length ? state.branch_receipts[state.branch_receipts.length - 1] : null;
  card.innerHTML = `
    <div class="card-header">
      <div class="card-title">🏢 Branch B (Edge Node)</div>
      <span class="badge badge-emerald">Cached: V1.0</span>
    </div>
    <div class="input-row">
      <div class="slider-wrap">
        <div class="slider-label"><span>Loan Request Amount</span><strong id="loan-val">$20,000</strong></div>
        <input type="range" id="loan-amount" min="5000" max="30000" step="1000" value="20000" oninput="document.getElementById('loan-val').textContent = '$' + Number(this.value).toLocaleString()">
      </div>
      <button class="btn btn-primary" onclick="requestLoan()">Authorize & Sign</button>
    </div>
    ${lastRcpt ? `
      <div class="code-box">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <strong>Last Signed Receipt (RFC 8785 Ed25519):</strong>
          <button class="btn btn-ghost" style="font-size:0.75rem;padding:3px 8px" onclick="runCopilot('${lastRcpt.payload.receipt_id}')">🤖 Copilot Audit</button>
        </div>
        Payload: ${JSON.stringify(lastRcpt.payload)}<br>
        Signature: <span style="color:var(--cyan)">${lastRcpt.signature.substring(0, 32)}...</span>
      </div>
    ` : '<p class="subtitle" style="font-style:italic">No receipts issued yet. Click Authorize to issue a loan.</p>'}
  `;
}


function renderMerkleDAG() {
  const card = document.getElementById('card-merkle-dag');
  const nodes = state.dag_nodes || [];
  card.innerHTML = `
    <div class="card-header"><div class="card-title">🌳 Merkle-CRDT Policy Tree</div><span class="badge badge-indigo">${nodes.length} Nodes</span></div>
    <div class="dag-list">
      ${nodes.map(n => `
        <div class="dag-item">
          <div style="display:flex;justify-content:space-between"><strong>Version ${n.version}</strong><span class="dag-hash">${n.hash.substring(0, 16)}...</span></div>
          <div style="font-size:0.8rem;color:var(--text-muted)">Rules: Max $${n.rules[0]?.max_amount?.toLocaleString()} | Action: ${n.rules[0]?.action} | Parent: ${n.parent ? n.parent.substring(0, 12) + '...' : 'Genesis'}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderReconciliation() {
  const card = document.getElementById('card-reconciliation');
  const isPart = state.partition_active;
  const history = state.history || [];
  const sagas = state.sagas || [];
  card.innerHTML = `
    <div class="card-header">
      <div class="card-title">⚖️ Reconciliation & Saga Monitor</div>
      <button class="btn btn-primary" onclick="reconcile()" ${isPart ? 'disabled title="Heal partition first"' : ''}>Trigger Reconciliation</button>
    </div>
    ${isPart ? '<div style="color:var(--rose);font-size:0.85rem">⚠️ Cannot reconcile: Network fiber partition is currently severed!</div>' : ''}
    <div class="pipeline-steps">
      <div class="pipeline-step"><div class="step-dot ${history.length ? 'passed' : ''}"></div><span>1. Ed25519 Cryptographic Verification</span></div>
      <div class="pipeline-step"><div class="step-dot ${history.length ? 'passed' : ''}"></div><span>2. Historical Merkle Defensibility Check</span></div>
      <div class="pipeline-step"><div class="step-dot ${history.length ? 'passed' : ''}"></div><span>3. Vector Clock Causal Convergence</span></div>
      <div class="pipeline-step"><div class="step-dot ${history.length ? 'passed' : ''}"></div><span>4. Forward Compensation Dispatch</span></div>
    </div>
    ${sagas.length ? `
      <table class="saga-table">
        <thead><tr><th>Saga ID</th><th>Action</th><th>Excess</th><th>State</th><th>Audit</th></tr></thead>
        <tbody>
          ${sagas.map(s => `<tr><td><code>${s.saga_id}</code></td><td>${s.action}</td><td>$${s.details?.excess || 0}</td><td><span class="badge badge-emerald">${s.state}</span></td><td><button class="btn btn-ghost" style="padding:2px 6px;font-size:0.75rem" onclick="runCopilot('${s.receipt_id}')">🤖 Audit</button></td></tr>`).join('')}
        </tbody>
      </table>
    ` : '<p class="subtitle" style="font-style:italic">No active sagas.</p>'}
  `;
}

async function runCopilot(receiptId) {
  const output = document.getElementById('copilot-output');
  output.innerHTML = '<p class="placeholder-text">🤖 Copilot analyzing Merkle DAG, Vector Clocks, and Saga Store...</p>';
  try {
    const res = await fetch('/api/copilot/explain', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({receipt_id: receiptId})
    });
    if (!res.ok) throw new Error('Could not analyze receipt');
    const data = await res.json();
    output.innerHTML = `
      <div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:8px;padding:12px">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px">
          <strong>Receipt: ${data.receipt_id}</strong>
          <span class="badge ${data.is_divergent ? 'badge-rose' : 'badge-emerald'}">${data.relation}</span>
        </div>
        <div style="font-size:0.85rem;line-height:1.5;white-space:pre-wrap;color:var(--text)">${data.explanation}</div>
      </div>
    `;
  } catch (err) {
    output.innerHTML = `<p style="color:var(--rose)">Failed to run copilot analysis: ${err.message}</p>`;
  }
}

async function togglePartition() { await fetch('/api/partition/toggle', {method:'POST'}); fetchState(); }
async function updatePolicy() { await fetch('/api/authority/update-policy', {method:'POST'}); fetchState(); }
async function requestLoan() { const val = document.getElementById('loan-amount').value; await fetch(`/api/branch/request-loan?amount=${val}`, {method:'POST'}); fetchState(); }
async function reconcile() { await fetch('/api/reconcile', {method:'POST'}); fetchState(); }
async function resetEngine() { await fetch('/api/reset', {method:'POST'}); fetchState(); }

document.getElementById('btn-toggle-partition').addEventListener('click', togglePartition);
document.getElementById('btn-reset').addEventListener('click', resetEngine);

fetchState();


