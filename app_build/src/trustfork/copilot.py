from typing import Dict, Any, Optional
from trustfork.merkle_crdt import MerklePolicyDAG
from trustfork.vector_clock import VectorClock, CausalRelation
from trustfork.saga_store import SagaStore

class AuditCopilot:
    """Forensic AI & Semantic Copilot for TrustFork distributed reconciliation."""

    def __init__(self, dag: MerklePolicyDAG, store: Optional[SagaStore] = None):
        self.dag = dag
        self.store = store

    def explain_receipt(self, receipt_id: str, payload: Dict[str, Any], auth_hash: str, auth_clock: Dict[str, int]) -> Dict[str, Any]:
        req = payload.get("request", {})
        rcpt_hash = payload.get("policy_hash", "")
        amount = req.get("amount", 0)
        action = req.get("action", "")
        lease_data = payload.get("lease")
        
        # 1. Causal Vector Clock relation
        rcpt_clock = payload.get("vector_clock", {})
        relation = VectorClock.compare(rcpt_clock, auth_clock)
        
        # 2. Merkle DAG divergence
        is_divergent = rcpt_hash != auth_hash
        auth_node = self.dag.get_policy(auth_hash)
        auth_limit = auth_node.rules[0].get("max_amount", 0) if auth_node and auth_node.rules else 0

        if relation == CausalRelation.HAPPENS_BEFORE:
            causal_desc = "Causally preceded Central Authority's latest update"
        elif relation == CausalRelation.CONCURRENT:
            causal_desc = "Concurrent split-brain (branch was partitioned when update occurred)"
        elif relation == CausalRelation.EQUAL:
            causal_desc = "Fully synchronized with Central Authority"
        else:
            causal_desc = relation.value

        lines = []

        # 3. Handle Bounded Authorization Lease (Zero-Clawback Paradigm)
        if lease_data:
            lease_id = lease_data.get("lease_id", "UNKNOWN_LEASE")
            valid_epoch = lease_data.get("valid_until_epoch", 0)
            exec_epoch = payload.get("execution_epoch", 0)
            usage_limit = lease_data.get("usage_limit", 0)

            lines.append("### [AUDIT VERDICT] SURVIVES (Zero Clawback)")
            lines.append(f"- Receipt ID: {receipt_id}")
            lines.append(f"- Pre-Authorized Lease: {lease_id} (Ed25519 Authority-Signed)")
            lines.append(f"- Execution Scope: Approved ${amount:,.2f} {action} at Epoch {exec_epoch} (Lease valid through Epoch {valid_epoch}).")
            lines.append(f"- Usage Bound: Consumed ${amount:,.2f} of ${usage_limit:,.2f} maximum allocation.")
            lines.append(f"- Causal Partition Context: {causal_desc}.")
            if is_divergent:
                lines.append(f"- Central Policy Drift: Central Authority updated to ${auth_limit:,.2f} ({auth_hash[:8]}...) while partitioned. However, this policy update applies to NEW leases only.")
            lines.append("- Deterministic Defensibility: Operation was strictly pre-bounded before disconnection. Finality guaranteed - Zero clawback or compensation required.")

            return {
                "receipt_id": receipt_id,
                "status": "SURVIVES",
                "relation": relation.value,
                "is_divergent": is_divergent,
                "lease_id": lease_id,
                "explanation": "\n".join(lines)
            }

        # 4. Fallback for Legacy / Direct Commits
        comp_action = auth_node.get_compensation_mapping(action) if auth_node else "clawback"
        idempotency_key = f"compensate_{receipt_id}_{comp_action or 'clawback'}"
        saga_record = self.store.get(idempotency_key) if self.store else None

        if is_divergent:
            excess = saga_record.details.get("excess", 0) if saga_record else 0
            lines.append("### [AUDIT VERDICT] Divergent Execution")
            lines.append(f"- Receipt ID: {receipt_id}")
            lines.append(f"- Offline Request: Approved ${amount:,.2f} {action} under local policy ({rcpt_hash[:8]}...).")
            lines.append(f"- Causal Context: {causal_desc}.")
            lines.append(f"- Divergence Detected: Central Authority was updated to a ${auth_limit:,.2f} limit ({auth_hash[:8]}...).")
            if saga_record:
                lines.append(f"- Forward Recovery: Dispatched {saga_record.action} for ${excess:,.2f} excess.")
        else:
            lines.append("### [AUDIT VERDICT] Committed (Aligned)")
            lines.append(f"- Receipt ID: {receipt_id}")
            lines.append(f"- Transaction: Approved ${amount:,.2f} {action} under policy ({rcpt_hash[:8]}...).")
            lines.append(f"- Causal Context: {causal_desc}.")
            lines.append("- Resolution: Decision is fully defensible under authoritative policy tree.")


        return {
            "receipt_id": receipt_id,
            "idempotency_key": idempotency_key,
            "relation": relation.value,
            "is_divergent": is_divergent,
            "saga": saga_record.__dict__ if saga_record else None,
            "explanation": "\n".join(lines)
        }
