from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os
from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.lease import AuthorizationLease, LeaseAuthority, LocalLeaseEvaluator
from trustfork.saga_orchestrator import SagaOrchestrator
from trustfork.saga_store import SagaStore
from trustfork.reconciler import TrustForkReconciler, ReconciliationStatus
from trustfork.vector_clock import VectorClock
from trustfork.copilot import AuditCopilot

app = FastAPI(title="TrustFork Authorization Engine")

class SimulationEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("SAGA_DB_PATH", ":memory:")
        self.reset()

    def reset(self):
        self.partition_active: bool = False
        self.current_epoch: int = 1
        
        # 1. Authority Genesis Policy V1
        self.dag = MerklePolicyDAG()
        self.p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW"}])
        self.dag.add_policy(self.p1)
        self.auth_policy_hash = self.p1.hash
        
        # 2. Authority Keys & Pre-Authorized Bounded Lease
        self.authority_key = SigningKey.generate()
        self.lease_issuer = LeaseAuthority(self.authority_key)
        self.active_lease = self.lease_issuer.issue_lease(
            domain_id="domain_B",
            action="loan",
            resource="account_credit",
            policy_hash=self.p1.hash,
            valid_until_epoch=10,
            usage_limit=15000,
            lease_id="LEASE-DOMAIN_B-E10"
        )
        
        # 3. Domain B Setup
        self.branch_key = SigningKey.generate()
        self.branch_evaluator = LocalLeaseEvaluator("domain_B", self.authority_key.verify_key)
        self.branch_evaluator.set_lease(self.active_lease)
        self.branch_clock = VectorClock()
        self.branch_receipts: List[Dict[str, Any]] = []
        self.reconciliation_history: List[Dict[str, Any]] = []
        self.all_receipts_by_id: Dict[str, Any] = {}
        
        # 4. Stores & Reconciler
        self.store = SagaStore(db_path=self.db_path)
        self.saga = SagaOrchestrator(store=self.store)
        self.reconciler = TrustForkReconciler(
            dag=self.dag,
            auth_policy_hash=self.auth_policy_hash,
            saga_orchestrator=self.saga,
            authority_verify_key=self.authority_key.verify_key
        )
        self.copilot = AuditCopilot(self.dag, self.store)

engine = SimulationEngine()

@app.get("/api/state")
def get_state():
    return {
        "partition_active": engine.partition_active,
        "current_epoch": engine.current_epoch,
        "auth_policy_hash": engine.auth_policy_hash,
        "branch_policy_hash": engine.p1.hash,
        "branch_pubkey_hex": engine.branch_key.verify_key.encode().hex(),
        "authority_pubkey_hex": engine.authority_key.verify_key.encode().hex(),
        "auth_clock": engine.reconciler.clock.to_dict(),
        "branch_clock": engine.branch_clock.to_dict(),
        "active_lease": {
            "lease_id": engine.active_lease.lease_id,
            "domain_id": engine.active_lease.domain_id,
            "action": engine.active_lease.action,
            "resource": engine.active_lease.resource,
            "policy_hash": engine.active_lease.policy_hash,
            "valid_until_epoch": engine.active_lease.valid_until_epoch,
            "usage_limit": engine.active_lease.usage_limit,
            "used_amount": engine.active_lease.used_amount,
            "remaining_limit": engine.active_lease.remaining_limit(),
            "signature": engine.active_lease.authority_signature
        } if engine.active_lease else None,
        "dag_nodes": [{"hash": n.hash, "version": n.version, "rules": n.rules, "parent": n.parent_hash} for n in engine.dag.nodes.values()],
        "branch_receipts": engine.branch_receipts,
        "sagas": [s.__dict__ for s in engine.store.get_all()],
        "history": engine.reconciliation_history
    }

@app.post("/api/partition/toggle")
def toggle_partition():
    engine.partition_active = not engine.partition_active
    return {"partition_active": engine.partition_active}

@app.post("/api/authority/update-policy")
def update_policy(max_amount: int = 10000):
    p2 = PolicyNode(
        "loan_policy",
        "2.0",
        [{"action": "loan", "max_amount": max_amount, "effect": "ALLOW"}],
        parent_hash=engine.auth_policy_hash
    )
    engine.dag.add_policy(p2)
    engine.auth_policy_hash = p2.hash
    engine.reconciler.auth_policy_hash = p2.hash
    engine.reconciler.clock.increment("authority")
    return {
        "status": "policy_updated",
        "hash": p2.hash,
        "max_amount": max_amount,
        "note": "New policy applies to newly issued leases only; active bounded leases remain valid until epoch expiry."
    }

@app.post("/api/branch/request-loan")
def request_loan(amount: int = 12000, use_lease: bool = True):
    engine.branch_clock.increment("domain_B")
    rid = f"RCPT-{len(engine.all_receipts_by_id) + 101}"
    
    if use_lease and engine.active_lease:
        allowed, reason, details = engine.branch_evaluator.evaluate({"action": "loan", "amount": amount}, engine.current_epoch)
        if not allowed:
            return {
                "status": "denied",
                "reason": reason,
                "details": details,
                "note": "Operation rejected fail-closed during partition: strictly outside lease bounds."
            }
        payload = {
            "receipt_id": rid,
            "domain_id": "domain_B",
            "policy_hash": engine.active_lease.policy_hash,
            "execution_epoch": engine.current_epoch,
            "request": {"action": "loan", "amount": amount},
            "lease": engine.active_lease.to_payload(),
            "lease_signature": engine.active_lease.authority_signature,
            "vector_clock": engine.branch_clock.to_dict()
        }
    else:
        # Legacy fallback
        payload = {
            "receipt_id": rid,
            "policy_hash": engine.p1.hash,
            "request": {"action": "loan", "amount": amount},
            "vector_clock": engine.branch_clock.to_dict()
        }
        
    rcpt = ReceiptSigner.create_receipt(payload, engine.branch_key)
    engine.branch_receipts.append(rcpt)
    engine.all_receipts_by_id[rid] = payload
    return {"status": "approved", "receipt": rcpt, "remaining_limit": engine.active_lease.remaining_limit() if engine.active_lease else 0}

class ExplainRequest(BaseModel):
    receipt_id: str

@app.post("/api/copilot/explain")
def copilot_explain(req: ExplainRequest):
    payload = engine.all_receipts_by_id.get(req.receipt_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return engine.copilot.explain_receipt(
        req.receipt_id,
        payload,
        engine.auth_policy_hash,
        engine.reconciler.clock.to_dict()
    )

@app.post("/api/reconcile")
def reconcile_all():
    if engine.partition_active:
        raise HTTPException(status_code=400, detail="Cannot reconcile while network partition is active!")
    results = []
    for rcpt in engine.branch_receipts:
        res = engine.reconciler.reconcile(rcpt, engine.branch_key.verify_key)
        if res.compensation:
            engine.saga.execute(res.compensation.idempotency_key, lambda r: {"clawback": "success", "recovered": r.details.get("excess", 0)})
        results.append({
            "receipt_id": res.receipt_id,
            "status": res.status.value,
            "reason": res.reason,
            "details": res.details,
            "compensation": res.compensation.__dict__ if res.compensation else None
        })
    engine.reconciliation_history.extend(results)
    engine.branch_receipts.clear()
    return {"results": results, "clock": engine.reconciler.clock.to_dict()}

@app.post("/api/epoch/advance")
def advance_epoch():
    engine.current_epoch += 1
    return {"current_epoch": engine.current_epoch}

@app.post("/api/reset")
def reset_sim():
    engine.reset()
    return {"status": "reset"}

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("trustfork.server:app", host=host, port=port, reload=False)
