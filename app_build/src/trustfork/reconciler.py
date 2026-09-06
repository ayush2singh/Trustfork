from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
from nacl.signing import VerifyKey
from trustfork.vector_clock import VectorClock, CausalRelation
from trustfork.merkle_crdt import MerklePolicyDAG
from trustfork.receipt import ReceiptSigner
from trustfork.lease import AuthorizationLease
from trustfork.saga_orchestrator import SagaOrchestrator, CompensationRecord

class ReconciliationStatus(str, Enum):
    SURVIVES = "SURVIVES"
    COMMITTED = "COMMITTED"
    REJECTED_OUTSIDE_LEASE = "REJECTED_OUTSIDE_LEASE"
    REJECTED_SIGNATURE = "REJECTED_SIGNATURE"
    REJECTED_INDEFENSIBLE = "REJECTED_INDEFENSIBLE"
    COMPENSATION_DISPATCHED = "COMPENSATION_DISPATCHED"

@dataclass
class ReconciliationResult:
    status: ReconciliationStatus
    receipt_id: str
    compensation: Optional[CompensationRecord] = None
    reason: str = ""
    details: Optional[Dict[str, Any]] = None

class TrustForkReconciler:
    def __init__(
        self,
        dag: MerklePolicyDAG,
        auth_policy_hash: str,
        saga_orchestrator: Optional[SagaOrchestrator] = None,
        authority_verify_key: Optional[VerifyKey] = None
    ):
        self.dag = dag
        self.auth_policy_hash = auth_policy_hash
        self.saga = saga_orchestrator
        self.authority_verify_key = authority_verify_key
        self.clock = VectorClock()
        self.lease_usage: Dict[str, int] = {}

    def reconcile(self, receipt: Dict[str, Any], verify_key: VerifyKey) -> ReconciliationResult:
        payload = receipt.get("payload", {})
        rid = payload.get("receipt_id", "")
        
        # 1. Verify receipt signature from domain
        if not ReceiptSigner.verify_receipt(receipt, verify_key):
            return ReconciliationResult(ReconciliationStatus.REJECTED_SIGNATURE, rid, reason="Receipt signature invalid")
            
        policy_hash = payload.get("policy_hash", "")
        req = payload.get("request", {})
        rcpt_clock = VectorClock(payload.get("vector_clock", {}))
        relation = VectorClock.compare(rcpt_clock.to_dict(), self.clock.to_dict())
        self.clock.merge(rcpt_clock)

        # Check if executed under a bounded authorization lease
        lease_data = payload.get("lease")
        if lease_data:
            lease = AuthorizationLease(
                lease_id=lease_data.get("lease_id", ""),
                domain_id=lease_data.get("domain_id", ""),
                principal=lease_data.get("principal", "*"),
                action=lease_data.get("action", ""),
                resource=lease_data.get("resource", "account_credit"),
                policy_hash=lease_data.get("policy_hash", ""),
                valid_until_epoch=lease_data.get("valid_until_epoch", 0),
                usage_limit=lease_data.get("usage_limit", 0),
                authority_signature=payload.get("lease_signature") or lease_data.get("authority_signature", "")
            )
            
            # Step 1: Lease signature is valid
            if not self.authority_verify_key or not lease.verify_signature(self.authority_verify_key):
                return ReconciliationResult(
                    ReconciliationStatus.REJECTED_SIGNATURE,
                    rid,
                    reason="Authorization lease signature invalid or missing authority key"
                )
                
            # Step 2: Policy hash matches issued policy evidence in DAG
            lease_policy_node = self.dag.get_policy(lease.policy_hash)
            if not lease_policy_node:
                return ReconciliationResult(
                    ReconciliationStatus.REJECTED_INDEFENSIBLE,
                    rid,
                    reason="Lease policy hash indefensible (not anchored in Merkle DAG)"
                )
                
            # Step 3: Lease was valid at time of execution (epoch check)
            exec_epoch = payload.get("execution_epoch", 0)
            if exec_epoch > lease.valid_until_epoch:
                return ReconciliationResult(
                    ReconciliationStatus.REJECTED_OUTSIDE_LEASE,
                    rid,
                    reason=f"Executed at epoch {exec_epoch} after lease expiry (valid_until={lease.valid_until_epoch})"
                )
                
            # Step 4: Request was within lease scope
            req_action = req.get("action", "")
            req_resource = req.get("resource", "account_credit")
            if req_action != lease.action or req_resource != lease.resource:
                return ReconciliationResult(
                    ReconciliationStatus.REJECTED_OUTSIDE_LEASE,
                    rid,
                    reason=f"Request scope mismatch (expected {lease.action}/{lease.resource}, got {req_action}/{req_resource})"
                )
                
            # Step 5: Usage limits were not exceeded
            amount = req.get("amount", 0)
            current_cum = self.lease_usage.get(lease.lease_id, 0)
            if current_cum + amount > lease.usage_limit:
                return ReconciliationResult(
                    ReconciliationStatus.REJECTED_OUTSIDE_LEASE,
                    rid,
                    reason=f"Lease usage limit exceeded: requested {amount}, previous usage {current_cum}, max {lease.usage_limit}"
                )
            self.lease_usage[lease.lease_id] = current_cum + amount
            
            # All 5 deterministic conditions satisfied -> SURVIVES!
            return ReconciliationResult(
                ReconciliationStatus.SURVIVES,
                rid,
                reason="Pre-authorized bounded lease verified; valid permanently with zero clawback",
                details={
                    "lease_id": lease.lease_id,
                    "policy_hash": lease.policy_hash,
                    "amount": amount,
                    "execution_epoch": exec_epoch,
                    "cumulative_used": self.lease_usage[lease.lease_id]
                }
            )

        # Direct connected / non-leased evaluations
        node = self.dag.get_policy(policy_hash)
        if not node or node.evaluate(req) != "ALLOW":
            return ReconciliationResult(ReconciliationStatus.REJECTED_INDEFENSIBLE, rid, reason="Policy indefensible")
            
        if policy_hash != self.auth_policy_hash or relation == CausalRelation.CONCURRENT:
            if self.saga:
                auth_node = self.dag.get_policy(self.auth_policy_hash)
                comp_action = auth_node.get_compensation_mapping(req.get("action", "")) if auth_node else "clawback"
                excess = req.get("amount", 0) - (auth_node.rules[0].get("max_amount", 0) if auth_node and auth_node.rules else 0)
                record = self.saga.initiate(rid, comp_action or "clawback", {"excess": excess, "request": req})
                return ReconciliationResult(ReconciliationStatus.COMPENSATION_DISPATCHED, rid, compensation=record, reason="Divergence reconciled")
            return ReconciliationResult(ReconciliationStatus.REJECTED_OUTSIDE_LEASE, rid, reason="Unbounded divergence without lease or saga")
            
        return ReconciliationResult(ReconciliationStatus.COMMITTED, rid, reason="Aligned with authority")
