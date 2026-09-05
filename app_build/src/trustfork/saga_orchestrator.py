from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Dict, Optional, List

class SagaState(str, Enum):
    INITIATED = "COMPENSATION_INITIATED"
    EXECUTING = "COMPENSATION_EXECUTING"
    COMPLETED = "COMPENSATION_COMPLETE"
    FAILED = "COMPENSATION_FAILED"

@dataclass
class CompensationRecord:
    saga_id: str
    receipt_id: str
    action: str
    idempotency_key: str
    state: SagaState = SagaState.INITIATED
    details: Dict[str, Any] = field(default_factory=dict)
    execution_result: Optional[Any] = None

class SagaOrchestrator:
    def __init__(self, store: Optional[Any] = None):
        self.store = store
        self.records: Dict[str, CompensationRecord] = {}

    def initiate(self, receipt_id: str, action: str, details: Optional[Dict[str, Any]] = None) -> CompensationRecord:
        idempotency_key = f"compensate_{receipt_id}_{action}"
        if self.store:
            existing = self.store.get(idempotency_key)
            if existing: return existing
        elif idempotency_key in self.records:
            return self.records[idempotency_key]
        record = CompensationRecord(f"saga_{receipt_id}", receipt_id, action, idempotency_key, SagaState.INITIATED, details or {})
        if self.store: self.store.save(record)
        self.records[idempotency_key] = record
        return record

    def execute(self, idempotency_key: str, handler: Callable[[CompensationRecord], Any]) -> CompensationRecord:
        record = self.store.get(idempotency_key) if self.store else self.records[idempotency_key]
        if record.state == SagaState.COMPLETED:
            return record
        record.state = SagaState.EXECUTING
        if self.store: self.store.save(record)
        try:
            record.execution_result = handler(record)
            record.state = SagaState.COMPLETED
        except Exception as e:
            record.state = SagaState.FAILED
            record.execution_result = str(e)
            if self.store: self.store.save(record)
            raise e
        if self.store: self.store.save(record)
        return record
