import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.lease import LeaseAuthority, LocalLeaseEvaluator
from trustfork.reconciler import TrustForkReconciler, ReconciliationStatus
from trustfork.vector_clock import VectorClock
from trustfork.copilot import AuditCopilot

def run_simulation():
    print("=" * 70)
    print("  TRUSTFORK: BOUNDED AUTHORIZATION LEASE RECONCILIATION")
    print("  Zero-Clawback & Zero-Compensation Post-Partition Architecture")
    print("=" * 70)

    # 1. Initialize Central Authority (Domain A) & Genesis Policy V1
    authority_key = SigningKey.generate()
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW"}])
    dag.add_policy(p1)
    print(f"\n[+] [GENESIS] Central Authority active. Policy V1 published:")
    print(f"    Hash: {p1.hash[:16]}... | Max Loan Limit: $20,000")

    # 2. Issue Pre-Authorized Signed Bounded Lease to Domain B before partition
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
    print(f"\n[*] [PRE-AUTHORIZATION] Authority issued signed bounded lease to Domain B:")
    print(f"    Lease ID: {lease.lease_id} | Scope: {lease.action}/{lease.resource}")
    print(f"    Validity: Epochs 0 -> {lease.valid_until_epoch} | Bounded Usage Limit: ${lease.usage_limit:,.2f}")
    print(f"    Ed25519 Signature: {lease.authority_signature[:24]}... (RFC 8785 canonical)")

    # 3. Network Partition Occurs!
    print(f"\n[!] [EVENT] Network partition severed Domain B from Central Authority!")
    
    # 4. Central Authority updates policy to V2 ($10k) while disconnected
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW"}], parent_hash=p1.hash)
    dag.add_policy(p2)
    print(f"[*] [CENTRAL] Authority policy updated to V2 during partition:")
    print(f"    Hash: {p2.hash[:16]}... | New Limit: $10,000 (Applies to NEW leases only)")

    # 5. Offline Operations at Domain B using Local Lease Evaluator
    branch_key = SigningKey.generate()
    evaluator = LocalLeaseEvaluator("domain_B", authority_key.verify_key)
    evaluator.set_lease(lease)
    vc_branch = VectorClock()

    print(f"\n[*] [OFFLINE EVALUATION] Domain B processing local requests under lease:")

    # Operation 1: Within Lease Bounds ($12,000 at Epoch 3)
    vc_branch.increment("domain_B")
    allowed_1, reason_1, details_1 = evaluator.evaluate({"action": "loan", "amount": 12000}, current_epoch=3)
    print(f"    -> Req 1 ($12,000 @ Epoch 3): {reason_1} (Remaining: ${details_1['remaining_limit']:,.2f})")
    assert allowed_1 is True

    payload_1 = {
        "receipt_id": "RCPT-LEASE-001",
        "domain_id": "domain_B",
        "policy_hash": p1.hash,
        "execution_epoch": 3,
        "request": {"action": "loan", "amount": 12000},
        "lease": lease.to_payload(),
        "lease_signature": lease.authority_signature,
        "vector_clock": vc_branch.to_dict()
    }
    receipt_1 = ReceiptSigner.create_receipt(payload_1, branch_key)

    # Operation 2: Exceeding Remaining Lease Limit ($8,000 requested, only $3,000 remaining)
    allowed_2, reason_2, details_2 = evaluator.evaluate({"action": "loan", "amount": 8000}, current_epoch=4)
    print(f"    -> Req 2 ($8,000 @ Epoch 4): FAIL-CLOSED DENY -> {reason_2} (Req: $8k, Rem: ${details_2['remaining']:,.2f})")
    assert allowed_2 is False

    # Operation 3: Outside Validity Epoch (Epoch 11 > Lease Valid Until 10)
    allowed_3, reason_3, details_3 = evaluator.evaluate({"action": "loan", "amount": 2000}, current_epoch=11)
    print(f"    -> Req 3 ($2,000 @ Epoch 11): FAIL-CLOSED DENY -> {reason_3} (Expired)")
    assert allowed_3 is False

    # 6. Reconnection & Deterministic Reconciliation
    print(f"\n[+] [EVENT] Network healed! Reconciler performing 5-step deterministic verification...")
    reconciler = TrustForkReconciler(dag, p2.hash, authority_verify_key=authority_key.verify_key)
    reconciler.clock.increment("authority")
    
    result = reconciler.reconcile(receipt_1, branch_key.verify_key)
    print(f"[OK] Deterministic Reconciliation Status: {result.status.value}")
    print(f"     Reason: {result.reason}")
    print(f"     Details: Amount=${result.details['amount']:,.2f} | Execution Epoch={result.details['execution_epoch']}")
    assert result.status == ReconciliationStatus.SURVIVES

    # 7. Audit Copilot Explanation
    copilot = AuditCopilot(dag)
    audit = copilot.explain_receipt("RCPT-LEASE-001", payload_1, p2.hash, reconciler.clock.to_dict())
    print("\n" + audit["explanation"])

    # 8. Convergence Confirmation
    print("=" * 70)
    print("  FINAL CONVERGENCE: Both domains now active under Policy V2.")
    print("  Zero clawbacks. Zero rollbacks. Zero compensation sagas executed.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_simulation()
