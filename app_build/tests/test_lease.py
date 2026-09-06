import pytest
from nacl.signing import SigningKey
from trustfork.lease import AuthorizationLease, LeaseAuthority, LocalLeaseEvaluator

def test_lease_issuance_and_signature_verification():
    authority_key = SigningKey.generate()
    issuer = LeaseAuthority(authority_key)
    
    lease = issuer.issue_lease(
        domain_id="domain_B",
        action="loan",
        resource="account_credit",
        policy_hash="abc123hash",
        valid_until_epoch=10,
        usage_limit=15000
    )
    
    assert lease.lease_id.startswith("LEASE-DOMAIN_B-")
    assert lease.usage_limit == 15000
    assert lease.used_amount == 0
    assert lease.remaining_limit() == 15000
    assert lease.verify_signature(authority_key.verify_key) is True

def test_tampered_lease_fails_verification():
    authority_key = SigningKey.generate()
    issuer = LeaseAuthority(authority_key)
    
    lease = issuer.issue_lease(
        domain_id="domain_B",
        action="loan",
        resource="account_credit",
        policy_hash="abc123hash",
        valid_until_epoch=10,
        usage_limit=15000
    )
    
    # Tamper with usage limit
    lease.usage_limit = 50000
    assert lease.verify_signature(authority_key.verify_key) is False

def test_local_evaluator_allow_and_deny_bounds():
    authority_key = SigningKey.generate()
    issuer = LeaseAuthority(authority_key)
    
    lease = issuer.issue_lease(
        domain_id="branch_B",
        action="loan",
        resource="account_credit",
        policy_hash="policy_v1_hash",
        valid_until_epoch=10,
        usage_limit=15000
    )
    
    evaluator = LocalLeaseEvaluator("branch_B", authority_key.verify_key)
    evaluator.set_lease(lease)
    
    # 1. Successful evaluation within limit and epoch
    allowed, reason, details = evaluator.evaluate({"action": "loan", "amount": 10000}, current_epoch=5)
    assert allowed is True
    assert reason == "ALLOWED_BY_LEASE"
    assert details["remaining_limit"] == 5000
    
    # 2. Rejection when exceeding remaining limit
    allowed, reason, details = evaluator.evaluate({"action": "loan", "amount": 6000}, current_epoch=5)
    assert allowed is False
    assert reason == "EXCEEDS_LEASE_USAGE_LIMIT"
    assert details["remaining"] == 5000
    
    # 3. Rejection when epoch is expired
    allowed, reason, details = evaluator.evaluate({"action": "loan", "amount": 2000}, current_epoch=11)
    assert allowed is False
    assert reason == "LEASE_EXPIRED"
