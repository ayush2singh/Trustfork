import pytest
from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.saga_orchestrator import SagaOrchestrator, SagaState
from trustfork.reconciler import TrustForkReconciler, ReconciliationStatus
from trustfork.vector_clock import VectorClock

def test_full_partition_and_reconciliation_lifecycle():
    # 1. Setup Merkle Policy DAG at Authority
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW", "compensation": "clawback"}])
    dag.add_policy(p1)
    
    # 2. Central authority updates policy to V2 ($10,000 max)
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW", "compensation": "clawback"}], parent_hash=p1.hash)
    dag.add_policy(p2)

    # 3. Branch node is partitioned; holds only V1. It approves a $20,000 loan.
    branch_key = SigningKey.generate()
    vc_branch = VectorClock()
    vc_branch.increment("branch_B")
    
    receipt_payload = {
        "receipt_id": "rcpt_partition_001",
        "policy_hash": p1.hash,
        "request": {"action": "loan", "amount": 20000},
        "vector_clock": vc_branch.to_dict()
    }
    signed_receipt = ReceiptSigner.create_receipt(receipt_payload, branch_key)

    # 4. Partition heals: Receipt transmitted to Central Reconciler
    saga = SagaOrchestrator()
    reconciler = TrustForkReconciler(dag, p2.hash, saga)
    reconciler.clock.increment("authority")  # Authority is at {"authority": 1}

    result = reconciler.reconcile(signed_receipt, branch_key.verify_key)

    # 5. Assert 4-stage pipeline outcomes
    assert result.status == ReconciliationStatus.COMPENSATION_DISPATCHED
    assert result.compensation is not None
    assert result.compensation.details["excess"] == 10000
    assert reconciler.clock.to_dict() == {"authority": 1, "branch_B": 1}

    # 6. Saga Orchestrator executes compensation clawback
    clawback_called = False
    def external_bank_clawback(record):
        nonlocal clawback_called
        clawback_called = True
        return {"status": "success", "recovered_amount": record.details["excess"]}

    saga.execute(result.compensation.idempotency_key, external_bank_clawback)
    assert clawback_called is True
    assert saga.records[result.compensation.idempotency_key].state == SagaState.COMPLETED
