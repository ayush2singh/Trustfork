from typing import Dict, Any, Optional
from trustfork.merkle_crdt import MerklePolicyDAG
from trustfork.vector_clock import VectorClock, CausalRelation
from trustfork.saga_store import SagaStore

class AuditCopilot:
    """Forensic AI & Semantic Copilot for TrustFork distributed reconciliation."""

    def __init__(self, dag: MerklePolicyDAG, store: SagaStore):
        self.dag = dag
        self.store = store

    def explain_receipt(self, receipt_id: str, payload: Dict[str, Any], auth_hash: str, auth_clock: Dict[str, int]) -> Dict[str, Any]:
        req = payload.get("request", {})
        rcpt_hash = payload.get("policy_hash", "")
        amount = req.get("amount", 0)
        action = req.get("action", "")
        
        # 1. Causal Vector Clock relation
        rcpt_clock = payload.get("vector_clock", {})
        relation = VectorClock.compare(rcpt_clock, auth_clock)
        
        # 2. Merkle DAG divergence
        is_divergent = rcpt_hash != auth_hash
        rcpt_node = self.dag.get_policy(rcpt_hash)
        auth_node = self.dag.get_policy(auth_hash)
        auth_limit = auth_node.rules[0].get("max_amount", 0) if auth_node and auth_node.rules else 0

        # 3. Saga state lookup via idempotency key
        comp_action = auth_node.get_compensation_mapping(action) if auth_node else "clawback"
        idempotency_key = f"compensate_{receipt_id}_{comp_action or 'clawback'}"
        saga_record = self.store.get(idempotency_key)

        
        # 4. Generate forensic explanation
        analysis = []
        analysis.append(f"**Receipt Analysis: `{receipt_id}`**")
        analysis.append(f"- **Requested Action**: `{action}` for `${amount:,.2f}`")
        analysis.append(f"- **Causal Relationship**: `{relation.value}` (Branch operated concurrently without knowing HQ updates).")
        
        if is_divergent:
            analysis.append(f"- **DAG Divergence**: Policy Hash `{rcpt_hash[:12]}...` (Branch V1) diverged from Authority `{auth_hash[:12]}...` (Authority V2 limit: `${auth_limit:,.2f}`).")
            if saga_record:
                analysis.append(f"- **Saga Resolution**: Dispatched forward-recovery `{saga_record.action}` for excess `${saga_record.details.get('excess', 0):,.2f}`. State is `{saga_record.state.value}` via key `{idempotency_key}`.")
        else:
            analysis.append("- **Status**: Aligned with Authority. Transaction fully committed without divergence.")

        return {
            "receipt_id": receipt_id,
            "idempotency_key": idempotency_key,
            "relation": relation.value,
            "is_divergent": is_divergent,
            "saga": saga_record.__dict__ if saga_record else None,
            "explanation": "\n".join(analysis)
        }
