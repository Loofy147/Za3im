"""Small SQLite execution/artifact ledger for Za3im's initial single-instance slice."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

from .ports import IdempotencyConflict


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class ExecutionStore:
    """SQLite state is authoritative for execution status and idempotency.

    This initial implementation is intended for one service instance using a local
    filesystem. It does not claim distributed locking or exactly-once external effects.
    """

    def __init__(self, db_path: str, artifact_dir: str, recover_interrupted: bool = True) -> None:
        self.db_path = str(db_path)
        self.artifact_dir = Path(artifact_dir).resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        Path(self.db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if recover_interrupted:
            self._recover_interrupted()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed','budget_exceeded','interrupted')),
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS execution_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL REFERENCES executions(execution_id),
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL REFERENCES executions(execution_id),
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_execution ON execution_events(execution_id, event_id);
            """)

    def _event(self, conn: sqlite3.Connection, execution_id: str, event_type: str, payload: dict | None = None) -> int:
        cursor = conn.execute(
            "INSERT INTO execution_events(execution_id,event_type,payload_json,occurred_at) VALUES(?,?,?,?)",
            (execution_id, event_type, canonical_json(payload or {}), utc_now()),
        )
        return int(cursor.lastrowid)

    def record_event(self, execution_id: str, event_type: str, payload: dict | None = None) -> str:
        """Persist a bounded evidence/usage event and return its real event ID."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(execution_id)
            if row["status"] != "running":
                conn.rollback()
                raise ValueError("events cannot be appended after execution is terminal")
            event_id = self._event(conn, execution_id, event_type, payload)
            conn.commit()
            return str(event_id)

    def _recover_interrupted(self) -> None:
        """Fail closed on runs interrupted by a process restart; never auto-replay provider work."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT execution_id FROM executions WHERE status='running'").fetchall()
            for row in rows:
                execution_id = row["execution_id"]
                result = {
                    "schema_version": "za3im.execution.result/0.1",
                    "execution_id": execution_id,
                    "status": "failed",
                    "started_at": None,
                    "finished_at": utc_now(),
                    "summary": "Execution was interrupted by service restart; automatic replay is blocked to avoid duplicate provider work.",
                    "artifacts": [],
                    "verification": {"status": "unknown", "checks": []},
                    "accounting": {"actual_provider_cost_usd": None, "estimated_provider_cost_usd": None, "customer_credits_charged": None, "accounting_status": "unknown", "usage_reference_ids": []},
                    "engine": {"engine_id": "openai-responses", "engine_version": "unknown", "adapter_version": "0.1.0", "model_provider": "openai", "model_id": None},
                    "errors": [{"code": "INTERRUPTED_EXECUTION", "message": "Service restarted while the execution was running; create a new idempotency key after reviewing provider-side usage.", "retryable": False, "source_component": "execution_store"}],
                    "side_effects": [],
                    "event_reference_ids": [],
                    "known_limitations": ["Provider-side completion may have occurred before the process stopped; reconcile cost before rerunning."]
                }
                conn.execute("UPDATE executions SET status='interrupted', result_json=?, error_json=?, updated_at=? WHERE execution_id=?",
                             (canonical_json(result), canonical_json(result["errors"][0]), utc_now(), execution_id))
                self._event(conn, execution_id, "interrupted_on_startup", {"reason": "stale_running_execution"})
            conn.commit()

    def claim(self, request: dict) -> tuple[dict, bool]:
        body_hash = fingerprint(request)
        tenant_id = request["tenant_id"]
        key = request["idempotency_key"]
        execution_id = request["execution_id"]
        now = utc_now()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM executions WHERE tenant_id=? AND idempotency_key=?",
                (tenant_id, key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != body_hash:
                    conn.rollback()
                    raise IdempotencyConflict("Idempotency key was already used with a different request body")
                conn.commit()
                return self._row_to_dict(existing), False
            collision = conn.execute("SELECT * FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
            if collision:
                conn.rollback()
                raise IdempotencyConflict("execution_id already belongs to another request")
            conn.execute(
                "INSERT INTO executions(execution_id,tenant_id,idempotency_key,request_hash,request_json,status,created_at,updated_at) VALUES(?,?,?,?,?,'running',?,?)",
                (execution_id, tenant_id, key, body_hash, canonical_json(request), now, now),
            )
            self._event(conn, execution_id, "execution_claimed", {"request_hash": body_hash})
            conn.commit()
        return self.get_execution(execution_id), True

    def finish(self, execution_id: str, status: str, result: dict, error: dict | None = None, artifact_rows: list[dict] | None = None) -> dict:
        if status not in {"succeeded", "failed", "budget_exceeded", "interrupted"}:
            raise ValueError(f"unsupported terminal status: {status}")
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(execution_id)
            if row["status"] != "running":
                conn.rollback()
                raise ValueError("terminal execution records are immutable")
            conn.execute("UPDATE executions SET status=?, result_json=?, error_json=?, updated_at=? WHERE execution_id=?",
                         (status, canonical_json(result), canonical_json(error) if error else None, utc_now(), execution_id))
            for artifact in artifact_rows or []:
                conn.execute(
                    "INSERT INTO artifacts(artifact_id,execution_id,tenant_id,role,media_type,sha256,size_bytes,path,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (artifact["artifact_id"], execution_id, artifact["tenant_id"], artifact["role"], artifact["media_type"], artifact["sha256"], artifact["size_bytes"], artifact["path"], utc_now()),
                )
            self._event(conn, execution_id, "execution_finished", {"status": status, "artifact_count": len(artifact_rows or [])})
            conn.commit()
        return self.get_execution(execution_id)

    def get_execution(self, execution_id: str) -> dict | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_artifact(self, artifact_id: str) -> dict | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        return dict(row) if row else None

    def list_events(self, execution_id: str) -> list[dict]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM execution_events WHERE execution_id=? ORDER BY event_id", (execution_id,)).fetchall()
        return [{"event_id": r["event_id"], "execution_id": r["execution_id"], "event_type": r["event_type"], "payload": json.loads(r["payload_json"]), "occurred_at": r["occurred_at"]} for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "execution_id": row["execution_id"],
            "tenant_id": row["tenant_id"],
            "idempotency_key": row["idempotency_key"],
            "request_hash": row["request_hash"],
            "request": json.loads(row["request_json"]),
            "status": row["status"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
