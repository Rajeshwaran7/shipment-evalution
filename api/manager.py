"""Background execution manager, event broadcasting, and state synchronization for runs."""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from langgraph.types import Command
from sse_starlette.sse import ServerSentEvent

from agent.graph import build_graph, get_default_checkpointer
from agent.llm import LLMClient
from agent.state import AgentState
from api.cost import calculate_cost
from api.storage import add_step, get_run, update_run

logger = logging.getLogger(__name__)

# Active in-memory queues per run_id for SSE streaming
_RUN_QUEUES: dict[str, list[asyncio.Queue]] = {}
_RUN_TASKS: dict[str, asyncio.Task] = {}


def _broadcast_event(run_id: str, event_type: str, data: dict[str, Any]) -> None:
    """Send an event to all connected SSE clients for a specific run."""
    queues = _RUN_QUEUES.get(run_id, [])
    payload = {"event": event_type, "data": data}
    for q in queues:
        q.put_nowait(payload)


def register_stream_queue(run_id: str) -> asyncio.Queue:
    """Register a new SSE stream subscriber queue."""
    q: asyncio.Queue = asyncio.Queue()
    if run_id not in _RUN_QUEUES:
        _RUN_QUEUES[run_id] = []
    _RUN_QUEUES[run_id].append(q)
    return q


def unregister_stream_queue(run_id: str, q: asyncio.Queue) -> None:
    """Remove an SSE stream subscriber queue on disconnect."""
    if run_id in _RUN_QUEUES and q in _RUN_QUEUES[run_id]:
        _RUN_QUEUES[run_id].remove(q)
        if not _RUN_QUEUES[run_id]:
            _RUN_QUEUES.pop(run_id, None)


async def execute_run_workflow(run_id: str, shipment_id: str, user_request: str) -> None:
    """Run the LangGraph workflow asynchronously in the background."""
    start_time = time.perf_counter()
    checkpointer = get_default_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}

    initial_state: AgentState = {
        "shipment_id": shipment_id,
        "user_request": user_request,
    }

    step_index = 0
    final_state: AgentState = {}
    llm = LLMClient()
    active_model = f"{llm.provider}:{llm.model}"

    try:
        # Run graph in thread executor to keep FastAPI async loop non-blocking
        loop = asyncio.get_event_loop()

        def run_stream():
            return list(graph.stream(initial_state, config=config))

        events = await loop.run_in_executor(None, run_stream)

        for event in events:
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
                    # High-risk approval gate triggered
                    interrupt_val = node_output[0].value if node_output else {}
                    proposals = interrupt_val.get("proposed_actions", [])
                    reasons = interrupt_val.get("approval_reason", "")
                    cost = interrupt_val.get("estimated_cost_usd", 0.0)

                    approval_payload = {
                        "status": "approval_required",
                        "run_id": run_id,
                        "approval_reason": reasons,
                        "proposed_actions": proposals,
                        "estimated_cost_usd": cost,
                    }

                    update_run(
                        run_id,
                        status="paused",
                        approval_data=approval_payload,
                    )
                    _broadcast_event(run_id, "approval_required", approval_payload)
                    return

                if isinstance(node_output, dict):
                    step_index += 1
                    summary = ""
                    history = node_output.get("step_history", [])
                    if history:
                        summary = history[-1].get("summary", "")

                    tokens_in = node_output.get("input_tokens", 0) - final_state.get("input_tokens", 0)
                    tokens_out = node_output.get("output_tokens", 0) - final_state.get("output_tokens", 0)
                    latency = node_output.get("total_latency_ms", 0.0) - final_state.get("total_latency_ms", 0.0)

                    step_record = add_step(
                        run_id=run_id,
                        node=node_name,
                        step_index=step_index,
                        summary=summary,
                        details=node_output,
                        tokens_in=max(0, tokens_in),
                        tokens_out=max(0, tokens_out),
                        latency_ms=max(0.0, latency),
                    )

                    _broadcast_event(run_id, "step", step_record)
                    final_state = {**final_state, **node_output}

        # If completed without interruption
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        in_tok = final_state.get("input_tokens", 0)
        out_tok = final_state.get("output_tokens", 0)
        cost_usd = calculate_cost(active_model, in_tok, out_tok)
        now_iso = datetime.now(timezone.utc).isoformat()

        update_run(
            run_id,
            status="completed",
            completed_at=now_iso,
            duration_ms=round(duration_ms, 2),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd,
            final_summary=final_state.get("final_summary", ""),
        )

        _broadcast_event(run_id, "complete", {
            "status": "completed",
            "run_id": run_id,
            "final_summary": final_state.get("final_summary", ""),
            "duration_ms": round(duration_ms, 2),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost_usd,
        })

    except Exception as e:
        logger.exception("Run %s failed with error: %s", run_id, e)
        update_run(run_id, status="failed", error=str(e))
        _broadcast_event(run_id, "error", {"error": str(e)})


async def resume_run_workflow(run_id: str, decision: bool, comment: str = "") -> None:
    """Resume a paused LangGraph workflow with operator approval/rejection."""
    run_entry = get_run(run_id)
    if not run_entry:
        raise ValueError(f"Run '{run_id}' not found.")

    checkpointer = get_default_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}
    llm = LLMClient()
    active_model = f"{llm.provider}:{llm.model}"

    update_run(run_id, status="running")
    _broadcast_event(run_id, "resumed", {
        "status": "running",
        "decision": decision,
        "comment": comment,
    })

    loop = asyncio.get_event_loop()

    def run_resume():
        cmd = Command(resume={"approved": decision, "comment": comment})
        return list(graph.stream(cmd, config=config))

    try:
        events = await loop.run_in_executor(None, run_resume)
        existing_steps = run_entry.get("steps", [])
        step_index = len(existing_steps)
        final_state: dict[str, Any] = {}

        for event in events:
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    step_index += 1
                    summary = ""
                    history = node_output.get("step_history", [])
                    if history:
                        summary = history[-1].get("summary", "")

                    tokens_in = node_output.get("input_tokens", 0) - final_state.get("input_tokens", 0)
                    tokens_out = node_output.get("output_tokens", 0) - final_state.get("output_tokens", 0)
                    latency = node_output.get("total_latency_ms", 0.0) - final_state.get("total_latency_ms", 0.0)

                    step_record = add_step(
                        run_id=run_id,
                        node=node_name,
                        step_index=step_index,
                        summary=summary,
                        details=node_output,
                        tokens_in=max(0, tokens_in),
                        tokens_out=max(0, tokens_out),
                        latency_ms=max(0.0, latency),
                    )

                    _broadcast_event(run_id, "step", step_record)
                    final_state = {**final_state, **node_output}

        now_iso = datetime.now(timezone.utc).isoformat()
        in_tok = run_entry.get("input_tokens", 0) + final_state.get("input_tokens", 0)
        out_tok = run_entry.get("output_tokens", 0) + final_state.get("output_tokens", 0)
        cost_usd = calculate_cost(active_model, in_tok, out_tok)

        update_run(
            run_id,
            status="completed",
            completed_at=now_iso,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd,
            final_summary=final_state.get("final_summary", ""),
        )

        _broadcast_event(run_id, "complete", {
            "status": "completed",
            "run_id": run_id,
            "final_summary": final_state.get("final_summary", ""),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost_usd,
        })

    except Exception as e:
        logger.exception("Error resuming run %s: %s", run_id, e)
        update_run(run_id, status="failed", error=str(e))
        _broadcast_event(run_id, "error", {"error": str(e)})


async def sse_event_generator(run_id: str) -> AsyncGenerator[ServerSentEvent, None]:
    """Yield Server-Sent Events for a run, replaying existing history first."""
    run_entry = get_run(run_id)
    if not run_entry:
        yield ServerSentEvent(event="error", data=json.dumps({"error": f"Run {run_id} not found"}))
        return

    # 1. Replay historical steps
    for step in run_entry.get("steps", []):
        yield ServerSentEvent(event="step", data=json.dumps(step))

    # If run already finished or waiting for approval, emit current state
    status = run_entry.get("status")
    if status == "paused" and run_entry.get("approval_data"):
        yield ServerSentEvent(event="approval_required", data=json.dumps(run_entry["approval_data"]))
        # Keep stream open so client receives 'resumed', subsequent steps, and 'complete'
    elif status == "completed":
        yield ServerSentEvent(
            event="complete",
            data=json.dumps({
                "status": "completed",
                "final_summary": run_entry.get("final_summary"),
                "duration_ms": run_entry.get("duration_ms"),
                "cost_usd": run_entry.get("cost_usd"),
                "input_tokens": run_entry.get("input_tokens"),
                "output_tokens": run_entry.get("output_tokens"),
            }),
        )
        return
    elif status == "failed":
        yield ServerSentEvent(event="error", data=json.dumps({"error": run_entry.get("error", "Execution failed")}))
        return

    # 2. Subscribe to live events
    q = register_stream_queue(run_id)
    try:
        while True:
            try:
                event_item = await asyncio.wait_for(q.get(), timeout=30.0)
                event_type = event_item["event"]
                event_data = event_item["data"]
                yield ServerSentEvent(event=event_type, data=json.dumps(event_data))

                if event_type in {"complete", "error"}:
                    break
            except asyncio.TimeoutError:
                # Keep-alive comment
                yield ServerSentEvent(comment="keepalive")
    finally:
        unregister_stream_queue(run_id, q)

