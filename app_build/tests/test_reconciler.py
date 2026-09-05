import pytest
from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.saga_orchestrator import SagaOrchestrator
from trustfork.reconciler import TrustForkReconciler, ReconciliationStatus
from trustfork.vector_clock import VectorClock

def test_reconciliation_pipeline():
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW", "compensation": "clawback"}])
    dag.add_policy(p1)
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW", "compensation": "clawback"}], parent_hash=p1.hash)
    dag.add_policy(p2)
    
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    saga = SagaOrchestrator()
    reconciler = TrustForkReconciler(dag, p2.hash, saga)

    # 1. Honest divergence during partition (evaluated under p1=20000, while auth is p2=10000)
    vc_branch = VectorClock()
    vc_branch.increment("branch_1")
    payload1 = {
        "receipt_id": "r1",
        "policy_hash": p1.hash,
        "request": {"action": "loan", "amount": 20000},
        "vector_clock": vc_branch.to_dict()
    }
    rcpt = ReceiptSigner.create_receipt(payload1, signing_key)
    
    result = reconciler.reconcile(rcpt, verify_key)
    assert result.status == ReconciliationStatus.COMPENSATION_DISPATCHED
    assert result.compensation is not None
    assert result.compensation.details["excess"] == 10000

    # 2. Tampered signature
    tampered_rcpt = dict(rcpt)
    tampered_rcpt["payload"] = dict(rcpt["payload"])
    tampered_rcpt["payload"]["request"] = {"action": "loan", "amount": 99999}
    bad_sig_res = reconciler.reconcile(tampered_rcpt, verify_key)
    assert bad_sig_res.status == ReconciliationStatus.REJECTED_SIGNATURE

    # 3. Indefensible decision (fabricated policy hash)
    fake_payload = {
        "receipt_id": "r3",
        "policy_hash": "fake_hash_999",
        "request": {"action": "loan", "amount": 50000},
        "vector_clock": vc_branch.to_dict()
    }
    fake_rcpt = ReceiptSigner.create_receipt(fake_payload, signing_key)
    fake_res = reconciler.reconcile(fake_rcpt, verify_key)
    assert fake_res.status == ReconciliationStatus.REJECTED_INDEFENSIBLE
