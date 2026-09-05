import sqlite3
import json
from typing import Optional, List
from trustfork.saga_orchestrator import CompensationRecord, SagaState

class SagaStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS sagas (
                    idempotency_key TEXT PRIMARY KEY,
                    saga_id TEXT, receipt_id TEXT, action TEXT,
                    state TEXT, details TEXT, execution_result TEXT
                )
            """)

    def save(self, record: CompensationRecord) -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO sagas (idempotency_key, saga_id, receipt_id, action, state, details, execution_result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    state = excluded.state,
                    execution_result = excluded.execution_result
            """, (
                record.idempotency_key, record.saga_id, record.receipt_id, record.action,
                record.state.value, json.dumps(record.details),
                json.dumps(record.execution_result) if record.execution_result is not None else None
            ))

    def get(self, key: str) -> Optional[CompensationRecord]:
        cur = self.conn.execute("SELECT * FROM sagas WHERE idempotency_key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return None
        return CompensationRecord(
            saga_id=row["saga_id"], receipt_id=row["receipt_id"], action=row["action"],
            idempotency_key=row["idempotency_key"], state=SagaState(row["state"]),
            details=json.loads(row["details"]) if row["details"] else {},
            execution_result=json.loads(row["execution_result"]) if row["execution_result"] else None
        )

    def get_pending(self) -> List[CompensationRecord]:
        cur = self.conn.execute("SELECT idempotency_key FROM sagas WHERE state IN (?, ?)",
                                (SagaState.INITIATED.value, SagaState.EXECUTING.value))
        return [self.get(row["idempotency_key"]) for row in cur.fetchall()]

    def get_all(self) -> List[CompensationRecord]:
        cur = self.conn.execute("SELECT idempotency_key FROM sagas")
        return [self.get(row["idempotency_key"]) for row in cur.fetchall()]

