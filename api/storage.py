"""SQLite persistence layer for API runs, steps, and telemetry logs."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "storage.db"


def get_db_connection() -> sqlite3.Connection:
    """Return a thread-safe connection with dictionary-like row access."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_storage() -> None:
    """Initialize SQLite database schemas for runs and execution steps."""
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                shipment_id TEXT NOT NULL,
                user_request TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms REAL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                final_summary TEXT,
                error TEXT,
                approval_data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                latency_ms REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)


def create_run(run_id: str, shipment_id: str, user_request: str) -> dict[str, Any]:
    """Create a new run entry with status 'running'."""
    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """INSERT INTO runs (run_id, shipment_id, user_request, status, started_at)
               VALUES (?, ?, ?, 'running', ?)""",
            (run_id, shipment_id, user_request, now_iso),
        )
    return {
        "run_id": run_id,
        "shipment_id": shipment_id,
        "user_request": user_request,
        "status": "running",
        "started_at": now_iso,
    }


def add_step(
    run_id: str,
    node: str,
    step_index: int,
    summary: str,
    details: dict[str, Any],
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0.0,
) -> dict[str, Any]:
    """Record an individual agent execution step."""
    conn = get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    details_str = json.dumps(details)
    with conn:
        cursor = conn.execute(
            """INSERT INTO steps (run_id, node, step_index, summary, details_json, tokens_in, tokens_out, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, node, step_index, summary, details_str, tokens_in, tokens_out, latency_ms, now_iso),
        )
        step_id = cursor.lastrowid

    return {
        "id": step_id,
        "run_id": run_id,
        "node": node,
        "step_index": step_index,
        "summary": summary,
        "details": details,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "created_at": now_iso,
    }


def update_run(run_id: str, **kwargs: Any) -> None:
    """Update fields on a run record."""
    if not kwargs:
        return

    conn = get_db_connection()
    set_clauses = []
    values = []

    for key, val in kwargs.items():
        if key == "approval_data" and isinstance(val, dict):
            val = json.dumps(val)
        set_clauses.append(f"{key} = ?")
        values.append(val)

    values.append(run_id)
    query = f"UPDATE runs SET {', '.join(set_clauses)} WHERE run_id = ?"

    with conn:
        conn.execute(query, values)


def get_run(run_id: str) -> dict[str, Any] | None:
    """Retrieve full details of a specific run."""
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    if not row:
        return None

    run_dict = dict(row)
    if run_dict.get("approval_data"):
        try:
            run_dict["approval_data"] = json.loads(run_dict["approval_data"])
        except json.JSONDecodeError:
            pass

    # Fetch associated steps
    step_cursor = conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY step_index ASC", (run_id,)
    )
    steps = []
    for s_row in step_cursor.fetchall():
        s_dict = dict(s_row)
        try:
            s_dict["details"] = json.loads(s_dict["details_json"])
        except json.JSONDecodeError:
            s_dict["details"] = {}
        s_dict.pop("details_json", None)
        steps.append(s_dict)

    run_dict["steps"] = steps
    return run_dict


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    """List recent runs with summary metrics."""
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
    )
    results = []
    for row in cursor.fetchall():
        d = dict(row)
        if d.get("approval_data"):
            try:
                d["approval_data"] = json.loads(d["approval_data"])
            except json.JSONDecodeError:
                pass
        results.append(d)
    return results


# Initialize on module load
init_storage()

