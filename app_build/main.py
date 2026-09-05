import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from nacl.signing import SigningKey
from trustfork.merkle_crdt import MerklePolicyDAG, PolicyNode
from trustfork.receipt import ReceiptSigner
from trustfork.saga_orchestrator import SagaOrchestrator
from trustfork.saga_store import SagaStore
from trustfork.reconciler import TrustForkReconciler
from trustfork.vector_clock import VectorClock

def run_simulation():
    print("=" * 60 + "\n[+] TRUSTFORK DISTRIBUTED AUTHORIZATION SIMULATION\n" + "=" * 60)
    
    # 1. Initialize Central Authority & Policy V1 ($20k)
    dag = MerklePolicyDAG()
    p1 = PolicyNode("loan_policy", "1.0", [{"action": "loan", "max_amount": 20000, "effect": "ALLOW", "compensation": "clawback"}])
    dag.add_policy(p1)
    print(f"[*] Authority active. Policy V1 published: {p1.hash[:16]}... (Max: $20,000)")

    # 2. Partition strikes! Central cluster updates to Policy V2 ($10k)
    print("\n[!] [EVENT] Network partition severed Branch_B from Central Authority!")
    p2 = PolicyNode("loan_policy", "2.0", [{"action": "loan", "max_amount": 10000, "effect": "ALLOW", "compensation": "clawback"}], parent_hash=p1.hash)
    dag.add_policy(p2)
    print(f"[*] Authority updated to V2: {p2.hash[:16]}... (Max: $10,000)")

    # 3. Branch_B approves $20,000 loan under cached V1
    branch_key = SigningKey.generate()
    vc_branch = VectorClock()
    vc_branch.increment("branch_B")
    payload = {"receipt_id": "RCPT-9021", "policy_hash": p1.hash, "request": {"action": "loan", "amount": 20000}, "vector_clock": vc_branch.to_dict()}
    receipt = ReceiptSigner.create_receipt(payload, branch_key)
    print(f"\n[*] Branch_B evaluated request under V1: ALLOW $20,000")
    print(f"    Signed Receipt: {receipt['signature'][:24]}... (RFC 8785 canonical)")

    # 4. Partition heals & Reconciler evaluates receipt
    print("\n[+] [EVENT] Network healed! Reconciler processing receipt...")
    store = SagaStore(db_path=":memory:")
    saga = SagaOrchestrator(store=store)
    reconciler = TrustForkReconciler(dag, p2.hash, saga)
    reconciler.clock.increment("authority")
    res = reconciler.reconcile(receipt, branch_key.verify_key)
    
    print(f"[OK] Reconciler Status: {res.status.value}")
    print(f"     Action: Dispatched Saga '{res.compensation.action}' for excess ${res.compensation.details['excess']}")

    # 5. Saga executes persistent compensation
    saga.execute(res.compensation.idempotency_key, lambda r: {"clawback": "success", "recovered": r.details['excess']})
    print(f"[OK] Saga Compensation Executed: State -> {saga.store.get(res.compensation.idempotency_key).state.value}\n" + "=" * 60)

if __name__ == "__main__":
    run_simulation()
