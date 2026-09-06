import pytest
from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.lease import LeaseAuthority, LocalLeaseEvaluator
from trustfork.saga_orchestrator import SagaOrchestrator
from trustfork.reconciler import TrustForkReconciler, ReconciliationStatus
from trustfork.vector_clock import VectorClock

def test_deterministic_lease_reconciliation_survives():
    # 1. Authority sets up DAG and Policy V1 ($20k)
    authority_key = SigningKey.generate()
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW"}])
    dag.add_policy(p1)
    
    # 2. Authority issues bounded lease to domain_B before partition
    issuer = LeaseAuthority(authority_key)
    lease = issuer.issue_lease(
        domain_id="domain_B",
        action="loan",
        resource="account_credit",
        policy_hash=p1.hash,
        valid_until_epoch=10,
        usage_limit=15000
    )
    
    # 3. Partition occurs! Authority updates to Policy V2 ($10k)
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW"}], parent_hash=p1.hash)
    dag.add_policy(p2)
    
    # 4. Domain B executes loan of $12,000 within lease bounds
    branch_key = SigningKey.generate()
    evaluator = LocalLeaseEvaluator("domain_B", authority_key.verify_key)
    evaluator.set_lease(lease)
    
    allowed, reason, details = evaluator.evaluate({"action": "loan", "amount": 12000}, current_epoch=3)
    assert allowed is True
    
    vc_branch = VectorClock()
    vc_branch.increment("domain_B")
    payload = {
        "receipt_id": "RCPT-SURVIVE-1",
        "domain_id": "domain_B",
        "policy_hash": p1.hash,
        "execution_epoch": 3,
        "request": {"action": "loan", "amount": 12000},
        "lease": lease.to_payload(),
        "lease_signature": lease.authority_signature,
        "vector_clock": vc_branch.to_dict()
    }
    rcpt = ReceiptSigner.create_receipt(payload, branch_key)
    
    # 5. Reconciler verifies upon reconnection
    reconciler = TrustForkReconciler(dag, p2.hash, authority_verify_key=authority_key.verify_key)
    result = reconciler.reconcile(rcpt, branch_key.verify_key)
    
    # STRICT REQUIREMENT: Must SURVIVE with zero compensation!
    assert result.status == ReconciliationStatus.SURVIVES
    assert result.compensation is None
    assert result.details["amount"] == 12000
    assert result.details["cumulative_used"] == 12000

def test_lease_reconciliation_rejects_expired_and_exceeded_bounds():
    authority_key = SigningKey.generate()
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW"}])
    dag.add_policy(p1)
    
    issuer = LeaseAuthority(authority_key)
    lease = issuer.issue_lease(
        domain_id="domain_B",
        action="loan",
        resource="account_credit",
        policy_hash=p1.hash,
        valid_until_epoch=5,
        usage_limit=10000
    )
    
    branch_key = SigningKey.generate()
    reconciler = TrustForkReconciler(dag, p1.hash, authority_verify_key=authority_key.verify_key)
    
    # Attempt 1: Executed past validity epoch
    payload_expired = {
        "receipt_id": "RCPT-EXP-1",
        "execution_epoch": 6, # > valid_until_epoch 5
        "request": {"action": "loan", "amount": 5000},
        "lease": lease.to_payload(),
        "lease_signature": lease.authority_signature,
        "vector_clock": {}
    }
    rcpt_expired = ReceiptSigner.create_receipt(payload_expired, branch_key)
    res_exp = reconciler.reconcile(rcpt_expired, branch_key.verify_key)
    assert res_exp.status == ReconciliationStatus.REJECTED_OUTSIDE_LEASE

    # Attempt 2: Exceeding usage limit
    payload_exceed = {
        "receipt_id": "RCPT-EXCEED-1",
        "execution_epoch": 2,
        "request": {"action": "loan", "amount": 15000}, # > usage_limit 10000
        "lease": lease.to_payload(),
        "lease_signature": lease.authority_signature,
        "vector_clock": {}
    }
    rcpt_exceed = ReceiptSigner.create_receipt(payload_exceed, branch_key)
    res_exceed = reconciler.reconcile(rcpt_exceed, branch_key.verify_key)
    assert res_exceed.status == ReconciliationStatus.REJECTED_OUTSIDE_LEASE

def test_legacy_compensation_backward_compatibility():
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW", "compensation": "clawback"}])
    dag.add_policy(p1)
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW", "compensation": "clawback"}], parent_hash=p1.hash)
    dag.add_policy(p2)
    
    signing_key = SigningKey.generate()
    saga = SagaOrchestrator()
    reconciler = TrustForkReconciler(dag, p2.hash, saga_orchestrator=saga)

    vc_branch = VectorClock()
    vc_branch.increment("branch_1")
    payload = {
        "receipt_id": "r_legacy",
        "policy_hash": p1.hash,
        "request": {"action": "loan", "amount": 20000},
        "vector_clock": vc_branch.to_dict()
    }
    rcpt = ReceiptSigner.create_receipt(payload, signing_key)
    result = reconciler.reconcile(rcpt, signing_key.verify_key)
    assert result.status == ReconciliationStatus.COMPENSATION_DISPATCHED
