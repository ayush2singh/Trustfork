from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os
from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.saga_orchestrator import SagaOrchestrator
from trustfork.saga_store import SagaStore
from trustfork.reconciler import TrustForkReconciler
from trustfork.vector_clock import VectorClock
from trustfork.copilot import AuditCopilot

app = FastAPI(title="TrustFork Authorization Engine")

class SimulationEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.partition_active: bool = False
        self.dag = MerklePolicyDAG()
        self.p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW", "compensation": "clawback"}])
        self.dag.add_policy(self.p1)
        self.auth_policy_hash = self.p1.hash
        self.store = SagaStore(db_path=":memory:")
        self.saga = SagaOrchestrator(store=self.store)
        self.reconciler = TrustForkReconciler(self.dag, self.auth_policy_hash, self.saga)
        self.branch_key = SigningKey.generate()
        self.branch_clock = VectorClock()
        self.branch_receipts: List[Dict[str, Any]] = []
        self.reconciliation_history: List[Dict[str, Any]] = []
        self.all_receipts_by_id: Dict[str, Any] = {}
        self.copilot = AuditCopilot(self.dag, self.store)

engine = SimulationEngine()


@app.get("/api/state")
def get_state():
    return {
        "partition_active": engine.partition_active,
        "auth_policy_hash": engine.auth_policy_hash,
        "branch_policy_hash": engine.p1.hash,
        "branch_pubkey_hex": engine.branch_key.verify_key.encode().hex(),
        "auth_clock": engine.reconciler.clock.to_dict(),
        "branch_clock": engine.branch_clock.to_dict(),
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
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": max_amount, "effect": "ALLOW", "compensation": "clawback"}], parent_hash=engine.auth_policy_hash)
    engine.dag.add_policy(p2)
    engine.auth_policy_hash = p2.hash
    engine.reconciler.auth_policy_hash = p2.hash
    engine.reconciler.clock.increment("authority")
    return {"status": "policy_updated", "hash": p2.hash, "max_amount": max_amount}

@app.post("/api/branch/request-loan")
def request_loan(amount: int = 20000):
    engine.branch_clock.increment("branch_B")
    payload = {"receipt_id": f"RCPT-{len(engine.all_receipts_by_id)+101}", "policy_hash": engine.p1.hash, "request": {"action": "loan", "amount": amount}, "vector_clock": engine.branch_clock.to_dict()}
    rcpt = ReceiptSigner.create_receipt(payload, engine.branch_key)
    engine.branch_receipts.append(rcpt)
    engine.all_receipts_by_id[payload["receipt_id"]] = payload
    return {"status": "approved", "receipt": rcpt}

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
            engine.saga.execute(res.compensation.idempotency_key, lambda r: {"clawback": "success", "recovered": r.details["excess"]})
        results.append({"receipt_id": res.receipt_id, "status": res.status.value, "reason": res.reason, "compensation": res.compensation.__dict__ if res.compensation else None})
    engine.reconciliation_history.extend(results)
    engine.branch_receipts.clear()
    return {"results": results, "clock": engine.reconciler.clock.to_dict()}

@app.post("/api/reset")
def reset_sim():
    engine.reset()
    return {"status": "reset"}

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

