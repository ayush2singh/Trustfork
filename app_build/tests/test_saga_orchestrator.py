import pytest
from trustfork.saga_orchestrator import SagaOrchestrator, SagaState

def test_saga_initiate_and_execute():
    orchestrator = SagaOrchestrator()
    record = orchestrator.initiate("rcpt_100", "clawback", {"amount": 20000})
    assert record.state == SagaState.INITIATED
    assert record.idempotency_key == "compensate_rcpt_100_clawback"

    call_count = 0
    def mock_handler(rec):
        nonlocal call_count
        call_count += 1
        return {"status": "debited", "amount": rec.details["amount"]}

    executed = orchestrator.execute(record.idempotency_key, mock_handler)
    assert executed.state == SagaState.COMPLETED
    assert executed.execution_result["status"] == "debited"
    assert call_count == 1

    # Retry execution with the same idempotency key
    retry_executed = orchestrator.execute(record.idempotency_key, mock_handler)
    assert retry_executed.state == SagaState.COMPLETED
    assert call_count == 1  # Handler was NOT called again!

def test_saga_failure_transition():
    orchestrator = SagaOrchestrator()
    record = orchestrator.initiate("rcpt_101", "freeze")
    
    def failing_handler(rec):
        raise ConnectionResetError("Gateway timeout")

    with pytest.raises(ConnectionResetError):
        orchestrator.execute(record.idempotency_key, failing_handler)

    assert orchestrator.records[record.idempotency_key].state == SagaState.FAILED
