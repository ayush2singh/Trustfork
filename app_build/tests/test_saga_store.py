import pytest
import os
from trustfork.saga_orchestrator import SagaOrchestrator, SagaState
from trustfork.saga_store import SagaStore

def test_saga_persistence_and_crash_recovery(tmp_path):
    db_file = str(tmp_path / "sagas.db")

    # Phase 1: Pre-crash node creates and initiates saga
    store1 = SagaStore(db_path=db_file)
    orch1 = SagaOrchestrator(store=store1)
    rec = orch1.initiate("rcpt_crash_99", "clawback", {"excess": 10000})
    assert rec.state == SagaState.INITIATED

    # Simulate crash right as execution starts
    rec.state = SagaState.EXECUTING
    store1.save(rec)
    store1.conn.close()  # Node dies!

    # Phase 2: Node reboots with fresh memory
    store2 = SagaStore(db_path=db_file)
    orch2 = SagaOrchestrator(store=store2)

    # Recovery scanner finds pending saga
    pending = store2.get_pending()
    assert len(pending) == 1
    assert pending[0].idempotency_key == "compensate_rcpt_crash_99_clawback"
    assert pending[0].state == SagaState.EXECUTING

    # Recovery worker resumes and completes the compensation
    executed = orch2.execute(pending[0].idempotency_key, lambda r: {"status": "recovered"})
    assert executed.state == SagaState.COMPLETED

    # Verify persisted in SQLite
    reloaded = store2.get(pending[0].idempotency_key)
    assert reloaded.state == SagaState.COMPLETED
    assert reloaded.execution_result == {"status": "recovered"}
    assert len(store2.get_pending()) == 0
