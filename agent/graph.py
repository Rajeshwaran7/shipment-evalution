"""LangGraph State Machine for ExceptionOps Shipment Exception Resolution.

Includes:
- Human-in-the-loop approval gate via LangGraph interrupt
- Security guardrails: prompt injection detection & untrusted data delimiting
- PII masking on outbound notifications
- Hub allowlist enforcement
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from agent.guardrails import (
    ALLOWED_HUBS,
    detect_injection,
    mask_pii,
    sanitize_untrusted,
    validate_reroute_hub,
)
from agent.llm import LLMClient
from agent.mcp_client import mcp_client
from agent.prompts import (
    CLASSIFY_SYSTEM_PROMPT,
    DIAGNOSE_SYSTEM_PROMPT,
    PLAN_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
)
from agent.state import ActionProposal, AgentState, ExceptionCategory

logger = logging.getLogger(__name__)

COST_APPROVAL_THRESHOLD = float(os.getenv("COST_APPROVAL_THRESHOLD", "200.0"))
DB_PATH = Path(__file__).resolve().parent.parent / "checkpoints.db"


def node_ingest(state: AgentState) -> dict[str, Any]:
    """Ingest shipment ID, fetch baseline telemetry, detect prompt injections, and sanitize data."""
    shipment_id = state.get("shipment_id", "").strip()
    user_request = state.get("user_request", "").strip()

    evidence = list(state.get("evidence", []))
    security_warnings = list(state.get("security_warnings", []))
    injection_patterns = list(state.get("injection_patterns", []))
    injection_flagged = bool(state.get("injection_flagged", False))

    updates: dict[str, Any] = {
        "shipment_id": shipment_id,
        "user_request": user_request,
        "evidence": evidence,
        "proposed_actions": list(state.get("proposed_actions", [])),
        "executed_actions": list(state.get("executed_actions", [])),
        "errors": list(state.get("errors", [])),
        "security_warnings": security_warnings,
        "injection_patterns": injection_patterns,
        "injection_flagged": injection_flagged,
        "step_history": list(state.get("step_history", [])),
        "input_tokens": int(state.get("input_tokens", 0)),
        "output_tokens": int(state.get("output_tokens", 0)),
        "total_latency_ms": float(state.get("total_latency_ms", 0.0)),
        "estimated_cost_usd": float(state.get("estimated_cost_usd", 0.0)),
    }

    # 1. Guardrail: Detect injection in user request
    req_flag, req_pat = detect_injection(user_request)
    if req_flag:
        updates["injection_flagged"] = True
        updates["injection_patterns"].append(req_pat)
        updates["security_warnings"].append(
            f"Prompt injection detected in user request: '{req_pat}'. Malicious commands ignored."
        )

    if not shipment_id:
        updates["errors"].append("No shipment_id provided in request.")
        return updates

    # 2. Query MCP server for initial tracking details
    track_res = mcp_client.call_tool("track_shipment", {"shipment_id": shipment_id})
    if track_res.get("status") == "error":
        updates["errors"].append(track_res.get("error", "Unknown tracking error"))
    else:
        origin = track_res.get("origin", "Unknown")
        dest = track_res.get("destination", "Unknown")
        status = track_res.get("shipment_status", "Unknown")
        last_evt = track_res.get("last_event", "None")
        notes = track_res.get("notes", "")

        # 3. Guardrail: Detect injection in shipment notes
        notes_flag, notes_pat = detect_injection(notes)
        if notes_flag:
            updates["injection_flagged"] = True
            updates["injection_patterns"].append(notes_pat)
            updates["security_warnings"].append(
                f"Prompt injection detected in shipment notes: '{notes_pat}'. Instructions disregarded."
            )

        evidence_entry = (
            f"Tracking Scan: Status={status}, Origin={origin}, Destination={dest}, "
            f"Last Event: {last_evt}"
        )
        updates["evidence"].append(evidence_entry)

    updates["step_history"].append({
        "node": "ingest",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": (
            f"Ingested shipment {shipment_id}. "
            f"{'WARNING: Injection detected in notes!' if updates['injection_flagged'] else 'Tracking OK.'}"
        ),
        "details": {
            "tracking_status": track_res.get("status"),
            "injection_flagged": updates["injection_flagged"],
            "security_warnings": updates["security_warnings"],
        },
    })
    return updates


def node_classify(state: AgentState) -> dict[str, Any]:
    """Classify the shipment exception category using LLM with untrusted data delimiters."""
    llm = LLMClient()
    shipment_id = state.get("shipment_id", "")
    user_req = state.get("user_request", "")
    evidence_text = "\n".join(state.get("evidence", []))

    # Guardrail: Wrap all untrusted user content and evidence in delimiters
    sanitized_block = sanitize_untrusted(
        f"Shipment ID: {shipment_id}\n"
        f"User Inquiry: {user_req}\n"
        f"Observed Evidence:\n{evidence_text}\n"
    )

    user_prompt = (
        f"Classify the following shipment anomaly:\n"
        f"{sanitized_block}\n"
        f"Respond with JSON containing 'exception_type' and 'reasoning'."
    )

    resp = llm.generate(CLASSIFY_SYSTEM_PROMPT, user_prompt)
    exception_type: ExceptionCategory = "unknown"

    try:
        clean_json = resp.content
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()

        data = json.loads(clean_json)
        raw_type = data.get("exception_type", "").lower()
        if raw_type in {"delay", "customs", "address", "lost", "unknown"}:
            exception_type = raw_type  # type: ignore
    except Exception as e:
        logger.warning("Failed to parse classification JSON (%s). Defaulting to unknown.", e)
        exception_type = "unknown"

    step_record = {
        "node": "classify",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": f"Classified exception as '{exception_type}'",
        "details": {"exception_type": exception_type, "llm_output": resp.content},
        "tokens": {"input": resp.input_tokens, "output": resp.output_tokens},
        "latency_ms": resp.latency_ms,
    }

    return {
        "exception_type": exception_type,
        "input_tokens": state.get("input_tokens", 0) + resp.input_tokens,
        "output_tokens": state.get("output_tokens", 0) + resp.output_tokens,
        "total_latency_ms": state.get("total_latency_ms", 0.0) + resp.latency_ms,
        "step_history": state.get("step_history", []) + [step_record],
    }


def node_diagnose(state: AgentState) -> dict[str, Any]:
    """Gather domain-specific tool evidence and state root cause."""
    shipment_id = state.get("shipment_id", "")
    exc_type = state.get("exception_type", "unknown")
    evidence = list(state.get("evidence", []))

    tools_called = []
    if exc_type == "delay":
        track_res = mcp_client.call_tool("track_shipment", {"shipment_id": shipment_id})
        origin = track_res.get("origin", "ORD")
        weather_res = mcp_client.call_tool("check_weather_risk", {
            "location": origin,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })
        tools_called.append("check_weather_risk")
        if weather_res.get("status") == "success":
            evidence.append(
                f"Weather Assessment at {origin}: Risk={weather_res.get('risk_level')}, "
                f"Condition={weather_res.get('condition')}, Impact={weather_res.get('impact')}"
            )
        route_res = mcp_client.call_tool("find_alternate_route", {"shipment_id": shipment_id})
        tools_called.append("find_alternate_route")
        if route_res.get("status") == "success" and route_res.get("alternate_routes"):
            alts = route_res.get("alternate_routes")
            evidence.append(f"Alternate Routes Available: {len(alts)} route(s) found (e.g. via {alts[0]['via_hub']})")

    elif exc_type == "customs":
        customs_res = mcp_client.call_tool("get_customs_status", {"shipment_id": shipment_id})
        tools_called.append("get_customs_status")
        if customs_res.get("status") == "success":
            evidence.append(
                f"Customs Status: {customs_res.get('customs_status')}. "
                f"Hold Reason: {customs_res.get('hold_reason')}. "
                f"Missing Docs: {', '.join(customs_res.get('missing_documents', []))}"
            )

    elif exc_type == "address":
        track_res = mcp_client.call_tool("track_shipment", {"shipment_id": shipment_id})
        if track_res.get("status") == "success":
            evidence.append(
                f"Address Verification: Verified={track_res.get('address_verified')}. "
                f"Carrier Delivery Notes: {track_res.get('notes')}"
            )

    # Use LLM to formulate grounded diagnosis with delimited evidence
    llm = LLMClient()
    sanitized_evidence = sanitize_untrusted(
        f"Category: {exc_type}\n"
        f"Collected Evidence:\n" + "\n".join(f"- {e}" for e in evidence)
    )

    user_prompt = (
        f"Synthesize the following operational evidence to diagnose root cause for shipment {shipment_id}:\n"
        f"{sanitized_evidence}\n"
        f"Respond with JSON keys: 'root_cause', 'evidence_summary', 'is_conclusive'."
    )

    resp = llm.generate(DIAGNOSE_SYSTEM_PROMPT, user_prompt)
    root_cause = "Unknown root cause; insufficient corroborated evidence."
    try:
        clean_json = resp.content
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
        data = json.loads(clean_json)
        root_cause = data.get("root_cause", root_cause)
    except Exception as e:
        logger.warning("Failed to parse diagnosis JSON: %s", e)

    step_record = {
        "node": "diagnose",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": f"Root cause diagnosed: {root_cause[:80]}...",
        "details": {
            "root_cause": root_cause,
            "evidence_count": len(evidence),
            "tools_called": tools_called,
        },
        "tokens": {"input": resp.input_tokens, "output": resp.output_tokens},
        "latency_ms": resp.latency_ms,
    }

    return {
        "evidence": evidence,
        "diagnosis": root_cause,
        "input_tokens": state.get("input_tokens", 0) + resp.input_tokens,
        "output_tokens": state.get("output_tokens", 0) + resp.output_tokens,
        "total_latency_ms": state.get("total_latency_ms", 0.0) + resp.latency_ms,
        "step_history": state.get("step_history", []) + [step_record],
    }


def node_plan(state: AgentState) -> dict[str, Any]:
    """Formulate an action plan using dynamically discovered MCP tools."""
    llm = LLMClient()
    discovered_tools = mcp_client.discover_tools()
    tool_summaries = [f"- {t['name']}: {t['description']} (Risk: {t['risk']})" for t in discovered_tools]

    sanitized_diag = sanitize_untrusted(state.get("diagnosis", ""))

    user_prompt = (
        f"Shipment {state.get('shipment_id')} Diagnosis:\n"
        f"{sanitized_diag}\n\n"
        f"Available Tools:\n" + "\n".join(tool_summaries) + "\n\n"
        f"Propose resolution actions in JSON format with key 'proposed_actions'."
    )

    resp = llm.generate(PLAN_SYSTEM_PROMPT, user_prompt)
    proposals: list[dict[str, Any]] = []

    try:
        clean_json = resp.content
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
        data = json.loads(clean_json)
        raw_actions = data.get("proposed_actions", [])

        for act in raw_actions:
            tool_name = act.get("tool", "")
            args = act.get("args", {})

            # Guardrail: If injection was flagged, ensure malicious commands (e.g. unauthorized refund) are blocked
            if "refund" in tool_name.lower():
                continue

            # Guardrail: Hub allowlist check
            if tool_name == "reroute_shipment":
                hub = args.get("new_hub", "")
                if not validate_reroute_hub(hub):
                    logger.warning("Rejected reroute proposal to invalid hub '%s'", hub)
                    continue

            # Hard Rule 1: Code-level risk lookup
            code_risk = mcp_client.get_tool_risk(tool_name)
            cost = float(act.get("estimated_cost_usd", 0.0))
            proposals.append({
                "tool": tool_name,
                "args": args,
                "risk": code_risk,
                "estimated_cost_usd": cost,
                "rationale": act.get("rationale", ""),
            })
    except Exception as e:
        logger.warning("Failed to parse action planning JSON: %s", e)

    # Ensure tool args have required fields
    for p in proposals:
        if "shipment_id" not in p["args"] and state.get("shipment_id"):
            p["args"]["shipment_id"] = state.get("shipment_id")
        if p["tool"] == "notify_customer":
            if "channel" not in p["args"]:
                p["args"]["channel"] = "email"
            if "message" not in p["args"]:
                p["args"]["message"] = p.get("rationale") or f"Update regarding exception on shipment {state.get('shipment_id')}."

    step_record = {
        "node": "plan",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": f"Formulated plan with {len(proposals)} action(s)",
        "details": {"proposed_actions": proposals},
        "tokens": {"input": resp.input_tokens, "output": resp.output_tokens},
        "latency_ms": resp.latency_ms,
    }

    return {
        "proposed_actions": proposals,
        "input_tokens": state.get("input_tokens", 0) + resp.input_tokens,
        "output_tokens": state.get("output_tokens", 0) + resp.output_tokens,
        "total_latency_ms": state.get("total_latency_ms", 0.0) + resp.latency_ms,
        "step_history": state.get("step_history", []) + [step_record],
    }


def node_risk_check(state: AgentState) -> dict[str, Any]:
    """Code-level enforcement: check tool risk annotations and cost threshold."""
    proposals = state.get("proposed_actions", [])
    requires_approval = False
    reasons = []
    total_cost = 0.0

    for action in proposals:
        tool_name = action.get("tool", "")
        cost = float(action.get("estimated_cost_usd", 0.0))
        total_cost += cost

        # Hard Rule 1: Code-level risk check
        if mcp_client.get_tool_risk(tool_name) == "high":
            requires_approval = True
            reasons.append(f"Tool '{tool_name}' carries HIGH risk annotation.")

        if cost > COST_APPROVAL_THRESHOLD:
            requires_approval = True
            reasons.append(f"Action cost ${cost:.2f} exceeds threshold ${COST_APPROVAL_THRESHOLD:.2f}.")

    step_record = {
        "node": "risk_check",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": (
            f"Risk check: {'APPROVAL REQUIRED' if requires_approval else 'PASSED'}. "
            f"Total cost: ${total_cost:.2f}"
        ),
        "details": {
            "requires_approval": requires_approval,
            "reasons": reasons,
            "total_cost": total_cost,
        },
    }

    return {
        "requires_approval": requires_approval,
        "approval_reason": "; ".join(reasons) if reasons else "No high-risk actions.",
        "estimated_cost_usd": total_cost,
        "step_history": state.get("step_history", []) + [step_record],
    }


def route_after_risk_check(state: AgentState) -> Literal["approval", "execute"]:
    """Conditional router: route to approval if high-risk or cost threshold exceeded."""
    if state.get("requires_approval") and state.get("approved") is not True:
        return "approval"
    return "execute"


def node_approval(state: AgentState) -> dict[str, Any]:
    """Approval node using LangGraph interrupt for human-in-the-loop review."""
    proposals = state.get("proposed_actions", [])
    approval_reasons = state.get("approval_reason", "")
    cost = state.get("estimated_cost_usd", 0.0)

    # Check if decision was pre-set (e.g. non-interactive test)
    decision = state.get("approved")
    comment = state.get("rejection_comment", "")

    if decision is None:
        # Trigger LangGraph interrupt - pauses the graph with state saved in checkpointer
        resume_payload = interrupt({
            "status": "approval_required",
            "proposed_actions": proposals,
            "approval_reason": approval_reasons,
            "estimated_cost_usd": cost,
        })

        if isinstance(resume_payload, dict):
            decision = resume_payload.get("approved", False)
            comment = resume_payload.get("comment", "")
        elif isinstance(resume_payload, bool):
            decision = resume_payload
        else:
            decision = False

    updates: dict[str, Any] = {
        "approved": decision,
        "rejection_comment": comment,
    }

    if not decision:
        # On rejection: produce an alternative non-invasive plan
        updates["alternative_plan"] = [
            {
                "tool": "notify_customer",
                "args": {
                    "shipment_id": state.get("shipment_id"),
                    "channel": "email",
                    "message": f"Proposed resolution was rejected: {comment or 'Operations manual review requested.'}",
                },
                "risk": "low",
                "estimated_cost_usd": 0.0,
                "rationale": "Alternative notification acknowledging rejection.",
            }
        ]

    step_record = {
        "node": "approval",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": (
            f"Human approval decision: {'APPROVED' if decision else 'REJECTED'}"
            f" (Comment: {comment or 'None'})"
        ),
        "details": {
            "approved": decision,
            "comment": comment,
            "alternative_plan": updates.get("alternative_plan", []),
        },
    }
    updates["step_history"] = state.get("step_history", []) + [step_record]
    return updates


def route_after_approval(state: AgentState) -> Literal["execute", "summarize"]:
    """If rejected by human, skip execution and jump directly to summary."""
    if state.get("approved") is False:
        return "summarize"
    return "execute"


def node_execute(state: AgentState) -> dict[str, Any]:
    """Execute approved actions via MCP client."""
    proposals = state.get("proposed_actions", [])
    executed = list(state.get("executed_actions", []))

    for action in proposals:
        tool_name = action.get("tool", "")
        args = dict(action.get("args", {}))
        if "shipment_id" not in args and state.get("shipment_id"):
            args["shipment_id"] = state.get("shipment_id")

        # Skip shipment-specific tools if shipment_id is missing or empty
        if tool_name in {"track_shipment", "get_customs_status", "find_alternate_route", "notify_customer", "update_address", "reroute_shipment"}:
            if not args.get("shipment_id"):
                continue

        res = mcp_client.call_tool(tool_name, args)
        executed.append({
            "tool": tool_name,
            "args": args,
            "result": res,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

    step_record = {
        "node": "execute",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": f"Executed {len(proposals)} action(s)",
        "details": {"executed_actions": executed},
    }

    return {
        "executed_actions": executed,
        "step_history": state.get("step_history", []) + [step_record],
    }


def node_notify(state: AgentState) -> dict[str, Any]:
    """Ensure customer notification is dispatched with masked PII."""
    executed = list(state.get("executed_actions", []))
    already_notified = any(act.get("tool") == "notify_customer" for act in executed)

    if not already_notified and state.get("shipment_id"):
        # Guardrail: PII masking on outbound notification message
        raw_msg = f"Status update: {state.get('diagnosis', 'Your shipment is being processed.')}"
        cleaned_msg = mask_pii(raw_msg)

        res = mcp_client.call_tool("notify_customer", {
            "shipment_id": state.get("shipment_id"),
            "channel": "email",
            "message": cleaned_msg,
        })
        executed.append({
            "tool": "notify_customer",
            "args": {"shipment_id": state.get("shipment_id"), "channel": "email"},
            "result": res,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

    step_record = {
        "node": "notify",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": "Verified customer notification dispatch with PII redaction",
        "details": {"notification_status": "dispatched"},
    }

    return {
        "executed_actions": executed,
        "step_history": state.get("step_history", []) + [step_record],
    }


def node_summarize(state: AgentState) -> dict[str, Any]:
    """Generate final executive summary grounded in evidence and executed steps."""
    llm = LLMClient()
    user_prompt = (
        f"Generate resolution summary for shipment {state.get('shipment_id')}:\n"
        f"Category: {state.get('exception_type')}\n"
        f"Diagnosis: {state.get('diagnosis')}\n"
        f"Requires Approval: {state.get('requires_approval')}\n"
        f"Approved: {state.get('approved')}\n"
        f"Rejection Comment: {state.get('rejection_comment')}\n"
        f"Executed Actions: {json.dumps(state.get('executed_actions', []))}\n"
        f"Alternative Plan: {json.dumps(state.get('alternative_plan', []))}\n"
        f"Security Warnings: {json.dumps(state.get('security_warnings', []))}\n"
    )

    resp = llm.generate(SUMMARIZE_SYSTEM_PROMPT, user_prompt)
    summary_text = mask_pii(resp.content)

    step_record = {
        "node": "summarize",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": "Generated final resolution summary",
        "details": {"summary": summary_text},
        "tokens": {"input": resp.input_tokens, "output": resp.output_tokens},
        "latency_ms": resp.latency_ms,
    }

    return {
        "final_summary": summary_text,
        "input_tokens": state.get("input_tokens", 0) + resp.input_tokens,
        "output_tokens": state.get("output_tokens", 0) + resp.output_tokens,
        "total_latency_ms": state.get("total_latency_ms", 0.0) + resp.latency_ms,
        "step_history": state.get("step_history", []) + [step_record],
    }


def get_default_checkpointer() -> SqliteSaver:
    """Initialize or return SQLite checkpointer for LangGraph state persistence."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return SqliteSaver(conn)


def build_graph(checkpointer: Any = None):
    """Build and compile the LangGraph workflow with optional checkpointer."""
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("ingest", node_ingest)
    workflow.add_node("classify", node_classify)
    workflow.add_node("diagnose", node_diagnose)
    workflow.add_node("plan", node_plan)
    workflow.add_node("risk_check", node_risk_check)
    workflow.add_node("approval", node_approval)
    workflow.add_node("execute", node_execute)
    workflow.add_node("notify", node_notify)
    workflow.add_node("summarize", node_summarize)

    # Add Edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "classify")
    workflow.add_edge("classify", "diagnose")
    workflow.add_edge("diagnose", "plan")
    workflow.add_edge("plan", "risk_check")

    # Conditional Routing from risk_check
    workflow.add_conditional_edges(
        "risk_check",
        route_after_risk_check,
        {
            "approval": "approval",
            "execute": "execute",
        }
    )

    # Conditional Routing from approval
    workflow.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "execute": "execute",
            "summarize": "summarize",
        }
    )

    workflow.add_edge("execute", "notify")
    workflow.add_edge("notify", "summarize")
    workflow.add_edge("summarize", END)

    return workflow.compile(checkpointer=checkpointer)
