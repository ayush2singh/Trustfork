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

def test_full_bounded_lease_zero_clawback_lifecycle():
    from trustfork.lease import LeaseAuthority, LocalLeaseEvaluator

    # 1. Authority Genesis Policy V1 ($20,000)
    authority_key = SigningKey.generate()
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW"}])
    dag.add_policy(p1)

    # 2. Issue Bounded Lease to Domain B before partition
    issuer = LeaseAuthority(authority_key)
    lease = issuer.issue_lease(
        domain_id="domain_B",
        action="loan",
        resource="account_credit",
        policy_hash=p1.hash,
        valid_until_epoch=10,
        usage_limit=15000,
        lease_id="LEASE-DOMAIN_B-E10"
    )

    # 3. Partition occurs! Authority updates to Policy V2 ($10,000)
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW"}], parent_hash=p1.hash)
    dag.add_policy(p2)

    # 4. Domain B executes loan of $12,000 within lease bounds ($12,000 <= $15,000)
    branch_key = SigningKey.generate()
    evaluator = LocalLeaseEvaluator("domain_B", authority_key.verify_key)
    evaluator.set_lease(lease)
    
    allowed, reason, details = evaluator.evaluate({"action": "loan", "amount": 12000}, current_epoch=3)
    assert allowed is True
    assert details["remaining_limit"] == 3000

    # 5. Domain B attempts out-of-bounds loan of $5,000 (> $3,000 remaining) -> Fails closed
    bad_allowed, bad_reason, _ = evaluator.evaluate({"action": "loan", "amount": 5000}, current_epoch=4)
    assert bad_allowed is False
    assert bad_reason == "EXCEEDS_LEASE_USAGE_LIMIT"

    # 6. Reconnect & Deterministic Reconciliation
    payload = {
        "receipt_id": "RCPT-BOUNDED-001",
        "domain_id": "domain_B",
        "policy_hash": p1.hash,
        "execution_epoch": 3,
        "request": {"action": "loan", "amount": 12000},
        "lease": lease.to_payload(),
        "lease_signature": lease.authority_signature,
        "vector_clock": {"domain_B": 1}
    }
    rcpt = ReceiptSigner.create_receipt(payload, branch_key)

    reconciler = TrustForkReconciler(dag, p2.hash, authority_verify_key=authority_key.verify_key)
    reconciler.clock.increment("authority")
    res = reconciler.reconcile(rcpt, branch_key.verify_key)

    # STRICT REQUIREMENT: Verified as SURVIVES with ZERO CLAWBACK
    assert res.status == ReconciliationStatus.SURVIVES
    assert res.compensation is None
    assert res.details["amount"] == 12000
    assert res.details["execution_epoch"] == 3

