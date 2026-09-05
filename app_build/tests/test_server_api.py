import pytest
from fastapi.testclient import TestClient
from trustfork.server import app

client = TestClient(app)

def test_api_simulation_lifecycle():
    # 1. Check initial state
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.json()
    assert data["partition_active"] is False
    assert len(data["dag_nodes"]) == 1

    # 2. Toggle partition
    toggle = client.post("/api/partition/toggle")
    assert toggle.status_code == 200
    assert toggle.json()["partition_active"] is True

    # 3. Update authority policy while partitioned
    update = client.post("/api/authority/update-policy?max_amount=10000")
    assert update.status_code == 200
    assert update.json()["status"] == "policy_updated"

    # 4. Request loan at branch ($20,000) under V1
    loan = client.post("/api/branch/request-loan?amount=20000")
    assert loan.status_code == 200
    assert loan.json()["status"] == "approved"

    # 5. Cannot reconcile while partitioned
    bad_reconcile = client.post("/api/reconcile")
    assert bad_reconcile.status_code == 400

    # 6. Heal partition and reconcile
    client.post("/api/partition/toggle")
    good_reconcile = client.post("/api/reconcile")
    assert good_reconcile.status_code == 200
    rec_data = good_reconcile.json()
    assert len(rec_data["results"]) == 1
    assert rec_data["results"][0]["status"] == "COMPENSATION_DISPATCHED"
    assert rec_data["results"][0]["compensation"]["details"]["excess"] == 10000

    # 7. Verify final state has completed saga
    final_state = client.get("/api/state").json()
    assert len(final_state["sagas"]) == 1
    assert final_state["sagas"][0]["state"] == "COMPENSATION_COMPLETE"

    # 8. Test Copilot explanation
    rcpt_id = rec_data["results"][0]["receipt_id"]
    copilot_res = client.post("/api/copilot/explain", json={"receipt_id": rcpt_id})
    assert copilot_res.status_code == 200
    c_data = copilot_res.json()
    assert c_data["is_divergent"] is True
    assert "Receipt Analysis" in c_data["explanation"]
    assert "Dispatched forward-recovery" in c_data["explanation"]

