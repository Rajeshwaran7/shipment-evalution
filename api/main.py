"""FastAPI application for ExceptionOps backend.

Features:
- Live streaming of agent steps via Server-Sent Events (SSE)
- Human approval / rejection gate endpoint
- Runs history and telemetry observability
- Evaluation reports and historical benchmarks
- Mock shipment catalog for frontend picker
- CORS enabled for Vite development server
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from api.manager import (
    execute_run_workflow,
    resume_run_workflow,
    sse_event_generator,
)
from api.models import (
    ApprovalRequest,
    ApprovalResponse,
    CreateRunRequest,
    CreateRunResponse,
    RunDetailModel,
    RunSummaryModel,
)
from api.storage import create_run, get_run, list_runs
from mcp_server.db import list_all_shipments

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("exception_ops_api")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_LATEST_FILE = PROJECT_ROOT / "evals" / "results" / "latest.json"
EVALS_DB_FILE = PROJECT_ROOT / "evals.db"

app = FastAPI(
    title="ExceptionOps - Logistics Exception Resolution API",
    version="1.0.0",
    description="Agentic logistics resolution system with MCP tools and human-in-the-loop approval gating.",
)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "ExceptionOps API"}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    """OpenAI-compatible models discovery endpoint for local AI tools and extensions."""
    return {
        "object": "list",
        "data": [
            {
                "id": "mock-logistics-v1",
                "object": "model",
                "created": 1700000000,
                "owned_by": "exception-ops",
            }
        ],
    }


@app.get("/shipments")
def get_shipments() -> list[dict[str, Any]]:
    """List all available mock shipments for frontend dropdown picker."""
    return list_all_shipments()


@app.post("/runs", response_model=CreateRunResponse, status_code=status.HTTP_201_CREATED)
def start_run(payload: CreateRunRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Initiate a new exception resolution workflow for a shipment."""
    shipment_id = payload.shipment_id.strip()
    user_request = payload.request.strip()

    if not shipment_id:
        raise HTTPException(status_code=400, detail="shipment_id cannot be empty")
    if not user_request:
        raise HTTPException(status_code=400, detail="request cannot be empty")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    run_record = create_run(run_id=run_id, shipment_id=shipment_id, user_request=user_request)

    # Launch background graph execution
    background_tasks.add_task(execute_run_workflow, run_id, shipment_id, user_request)

    return {
        "run_id": run_id,
        "shipment_id": shipment_id,
        "status": "running",
        "started_at": run_record["started_at"],
    }


@app.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str):
    """Server-Sent Events (SSE) streaming endpoint for live agent step execution."""
    run_entry = get_run(run_id)
    if not run_entry:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return EventSourceResponse(sse_event_generator(run_id))


@app.post("/runs/{run_id}/approval", response_model=ApprovalResponse)
async def submit_approval(
    run_id: str,
    payload: ApprovalRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Submit human approval or rejection to resume a paused agent execution."""
    run_entry = get_run(run_id)
    if not run_entry:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    if run_entry.get("status") != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Run '{run_id}' is not currently paused for approval (status: {run_entry.get('status')})"
        )

    # Resume the workflow in background
    background_tasks.add_task(resume_run_workflow, run_id, payload.decision, payload.comment)

    from datetime import datetime, timezone
    return {
        "run_id": run_id,
        "status": "resuming",
        "decision": payload.decision,
        "resumed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/runs", response_model=list[RunSummaryModel])
def get_runs_history(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve history of agent runs with aggregated telemetry and duration."""
    return list_runs(limit=limit)


@app.get("/runs/{run_id}", response_model=RunDetailModel)
def get_run_trace(run_id: str) -> dict[str, Any]:
    """Retrieve full trace details, execution steps, and final state of a run."""
    run_entry = get_run(run_id)
    if not run_entry:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run_entry


@app.get("/evals/latest")
def get_latest_eval_results() -> dict[str, Any]:
    """Fetch the latest benchmark evaluation report."""
    if not EVALS_LATEST_FILE.exists():
        return {
            "status": "no_results",
            "message": "No evaluations have been run yet. Run: python -m evals.run",
        }

    try:
        with open(EVALS_LATEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading latest evals: {e}")


@app.get("/evals/history")
def get_evals_history(limit: int = 20) -> list[dict[str, Any]]:
    """Retrieve historical eval runs from SQLite."""
    if not EVALS_DB_FILE.exists():
        return []

    try:
        conn = sqlite3.connect(str(EVALS_DB_FILE))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT run_id, timestamp, prompt_version, model_name, total_scenarios, passed_scenarios, pass_rate
               FROM eval_runs ORDER BY timestamp DESC LIMIT ?""",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error("Error querying eval history: %s", e)
        return []

