from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
from nacl.signing import VerifyKey
from trustfork.vector_clock import VectorClock, CausalRelation
from trustfork.merkle_crdt import MerklePolicyDAG
from trustfork.receipt import ReceiptSigner
from trustfork.saga_orchestrator import SagaOrchestrator, CompensationRecord

class ReconciliationStatus(str, Enum):
    COMMITTED = "COMMITTED"
    COMPENSATION_DISPATCHED = "COMPENSATION_DISPATCHED"
    REJECTED_SIGNATURE = "REJECTED_SIGNATURE"
    REJECTED_INDEFENSIBLE = "REJECTED_INDEFENSIBLE"

@dataclass
class ReconciliationResult:
    status: ReconciliationStatus
    receipt_id: str
    compensation: Optional[CompensationRecord] = None
    reason: str = ""

class TrustForkReconciler:
    def __init__(self, dag: MerklePolicyDAG, auth_policy_hash: str, saga_orchestrator: SagaOrchestrator):
        self.dag = dag
        self.auth_policy_hash = auth_policy_hash
        self.saga = saga_orchestrator
        self.clock = VectorClock()

    def reconcile(self, receipt: Dict[str, Any], verify_key: VerifyKey) -> ReconciliationResult:
        payload = receipt.get("payload", {})
        rid = payload.get("receipt_id", "")
        if not ReceiptSigner.verify_receipt(receipt, verify_key):
            return ReconciliationResult(ReconciliationStatus.REJECTED_SIGNATURE, rid, reason="Signature invalid")
        policy_hash = payload.get("policy_hash", "")
        req = payload.get("request", {})
        node = self.dag.get_policy(policy_hash)
        if not node or node.evaluate(req) != "ALLOW":
            return ReconciliationResult(ReconciliationStatus.REJECTED_INDEFENSIBLE, rid, reason="Policy indefensible")
        rcpt_clock = VectorClock(payload.get("vector_clock", {}))
        relation = VectorClock.compare(rcpt_clock.to_dict(), self.clock.to_dict())
        self.clock.merge(rcpt_clock)
        if policy_hash != self.auth_policy_hash or relation == CausalRelation.CONCURRENT:
            auth_node = self.dag.get_policy(self.auth_policy_hash)
            comp_action = auth_node.get_compensation_mapping(req.get("action", "")) if auth_node else "clawback"
            excess = req.get("amount", 0) - (auth_node.rules[0].get("max_amount", 0) if auth_node and auth_node.rules else 0)
            record = self.saga.initiate(rid, comp_action or "clawback", {"excess": excess, "request": req})
            return ReconciliationResult(ReconciliationStatus.COMPENSATION_DISPATCHED, rid, compensation=record, reason="Divergence reconciled")
        return ReconciliationResult(ReconciliationStatus.COMMITTED, rid, reason="Aligned with authority")
