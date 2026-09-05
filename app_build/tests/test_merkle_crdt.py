from src.trustfork.merkle_crdt import PolicyNode, MerklePolicyDAG

def test_policy_hashing_and_lineage():
    rules_v1 = [{"action": "Loan.Disburse", "max_amount": 25000, "effect": "ALLOW", "compensation": "Loan.Freeze_And_Recall"}]
    p1 = PolicyNode("pol_loan", "v1", rules_v1)
    
    rules_v2 = [{"action": "Loan.Disburse", "max_amount": 15000, "effect": "ALLOW", "compensation": "Loan.Freeze_And_Recall"}]
    p2 = PolicyNode("pol_loan", "v2", rules_v2, parent_hash=p1.hash)
    
    dag = MerklePolicyDAG()
    dag.add_policy(p1)
    dag.add_policy(p2)
    
    assert dag.get_policy(p1.hash) == p1
    assert dag.get_policy(p2.hash) == p2
    assert p2.parent_hash == p1.hash
    assert dag.tip_hash == p2.hash

def test_policy_evaluation():
    rules = [{"action": "Loan.Disburse", "max_amount": 25000, "effect": "ALLOW", "compensation": "Loan.Freeze_And_Recall"}]
    policy = PolicyNode("pol_loan", "v1", rules)
    
    # Within limit
    assert policy.evaluate({"action": "Loan.Disburse", "amount": 20000}) == "ALLOW"
    # Over limit
    assert policy.evaluate({"action": "Loan.Disburse", "amount": 30000}) == "DENY"
    # Unmatched action
    assert policy.evaluate({"action": "Wire.Transfer", "amount": 100}) == "DENY"
