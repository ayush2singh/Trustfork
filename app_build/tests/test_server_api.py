import pytest
from fastapi.testclient import TestClient
from trustfork.server import app

client = TestClient(app)

def test_api_simulation_bounded_lease_lifecycle():
    # 1. Check initial state - has pre-authorized lease
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.json()
    assert data["partition_active"] is False
    assert data["active_lease"] is not None
    assert data["active_lease"]["usage_limit"] == 15000
    assert data["active_lease"]["remaining_limit"] == 15000

    # 2. Toggle partition
    toggle = client.post("/api/partition/toggle")
    assert toggle.status_code == 200
    assert toggle.json()["partition_active"] is True

    # 3. Update authority policy while partitioned
    update = client.post("/api/authority/update-policy?max_amount=10000")
    assert update.status_code == 200
    assert update.json()["status"] == "policy_updated"

    # 4. Request valid loan within lease bounds ($12,000 <= $15,000)
    loan = client.post("/api/branch/request-loan?amount=12000")
    assert loan.status_code == 200
    assert loan.json()["status"] == "approved"
    assert loan.json()["remaining_limit"] == 3000

    # 5. Request loan exceeding remaining limit ($5,000 > $3,000 remaining) -> FAIL CLOSED
    bad_loan = client.post("/api/branch/request-loan?amount=5000")
    assert bad_loan.status_code == 200
    assert bad_loan.json()["status"] == "denied"
    assert bad_loan.json()["reason"] == "EXCEEDS_LEASE_USAGE_LIMIT"

    # 6. Cannot reconcile while partitioned
    bad_reconcile = client.post("/api/reconcile")
    assert bad_reconcile.status_code == 400

    # 7. Heal partition and reconcile
    client.post("/api/partition/toggle")
    good_reconcile = client.post("/api/reconcile")
    assert good_reconcile.status_code == 200
    rec_data = good_reconcile.json()
    assert len(rec_data["results"]) == 1
    # STRICT REQUIREMENT: Verified as SURVIVES with zero compensation!
    assert rec_data["results"][0]["status"] == "SURVIVES"
    assert rec_data["results"][0]["compensation"] is None
    assert rec_data["results"][0]["details"]["amount"] == 12000

    # 8. Test Copilot explanation
    rcpt_id = rec_data["results"][0]["receipt_id"]
    copilot_res = client.post("/api/copilot/explain", json={"receipt_id": rcpt_id})
    assert copilot_res.status_code == 200
    c_data = copilot_res.json()
    assert c_data["status"] == "SURVIVES"
    assert "SURVIVES (Zero Clawback)" in c_data["explanation"]
    assert "Zero clawback or compensation required" in c_data["explanation"]
