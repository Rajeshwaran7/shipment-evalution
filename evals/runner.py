"""Evaluation Runner for ExceptionOps benchmark scenarios.

Executes scenarios, captures traces, scores against 4 rubrics, saves to SQLite,
computes regression diffs against prior runs, and outputs CLI tables & JSON artifacts.
"""

import argparse
import copy
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.graph import build_graph
from agent.llm import LLMClient
from agent.state import AgentState
from evals.scorers import (
    score_diagnosis_correct,
    score_groundedness,
    score_safety,
    score_tool_use_correct,
)
from mcp_server.db import reset_db

logger = logging.getLogger(__name__)
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = PROJECT_ROOT / "evals" / "scenarios.yaml"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
EVALS_DB_PATH = PROJECT_ROOT / "evals.db"


def init_evals_db() -> sqlite3.Connection:
    """Initialize SQLite database for recording eval run history."""
    conn = sqlite3.connect(str(EVALS_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                model_name TEXT NOT NULL,
                total_scenarios INTEGER NOT NULL,
                passed_scenarios INTEGER NOT NULL,
                pass_rate REAL NOT NULL,
                metrics_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenario_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                category TEXT NOT NULL,
                passed INTEGER NOT NULL,
                diagnosis_pass INTEGER NOT NULL,
                tools_pass INTEGER NOT NULL,
                safety_pass INTEGER NOT NULL,
                groundedness_pass INTEGER NOT NULL,
                details_json TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES eval_runs(run_id)
            )
        """)
    return conn


def get_latest_previous_run(conn: sqlite3.Connection, current_run_id: str | None = None) -> dict[str, Any] | None:
    """Fetch the most recent previous run from SQLite to compute regression diffs."""
    query = "SELECT * FROM eval_runs"
    params = []
    if current_run_id:
        query += " WHERE run_id != ?"
        params.append(current_run_id)
    query += " ORDER BY timestamp DESC LIMIT 1"

    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    if not row:
        return None

    run_dict = dict(row)
    scen_cursor = conn.execute(
        "SELECT scenario_id, passed FROM scenario_results WHERE run_id = ?",
        (run_dict["run_id"],)
    )
    run_dict["scenario_results"] = {r["scenario_id"]: bool(r["passed"]) for r in scen_cursor.fetchall()}
    return run_dict


def run_scenario(scenario: dict[str, Any], checkpointer: Any, llm: LLMClient) -> dict[str, Any]:
    """Execute a single scenario through the LangGraph agent and score results."""
    reset_db()
    scen_id = scenario["id"]
    shipment_id = scenario.get("shipment_id") or ""
    user_request = scenario.get("user_request") or ""
    auto_approve = scenario.get("auto_approve", True)

    graph = build_graph(checkpointer=checkpointer)
    thread_id = f"eval_{scen_id}_{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "shipment_id": shipment_id,
        "user_request": user_request,
    }

    final_state: AgentState = {}
    try:
        # Step 1: Initial invocation
        for event in graph.stream(initial_state, config=config):
            for node_name, output in event.items():
                if node_name == "__interrupt__":
                    # Interrupt encountered -> Resume per scenario auto_approve config
                    decision = auto_approve
                    comment = "Approved by eval runner" if decision else "Rejected by eval runner"
                    resume_command = Command(resume={"approved": decision, "comment": comment})
                    for resumed_event in graph.stream(resume_command, config=config):
                        for r_name, r_output in resumed_event.items():
                            if isinstance(r_output, dict):
                                final_state = {**final_state, **r_output}
                    break
                elif isinstance(output, dict):
                    final_state = {**final_state, **output}
    except Exception as e:
        logger.error("Error executing scenario %s: %s", scen_id, e)
        final_state["errors"] = final_state.get("errors", []) + [str(e)]

    # Run the 4 evaluation checks
    diag_pass, diag_reason = score_diagnosis_correct(scenario, final_state, llm)
    tools_pass, tools_reason = score_tool_use_correct(scenario, final_state)
    safety_pass, safety_reason = score_safety(scenario, final_state)
    ground_pass, ground_reason = score_groundedness(scenario, final_state, llm)

    overall_pass = diag_pass and tools_pass and safety_pass and ground_pass

    return {
        "scenario_id": scen_id,
        "category": scenario.get("category", "unknown"),
        "shipment_id": shipment_id,
        "user_request": user_request,
        "passed": overall_pass,
        "checks": {
            "diagnosis_correct": {"passed": diag_pass, "reason": diag_reason},
            "tool_use_correct": {"passed": tools_pass, "reason": tools_reason},
            "safety": {"passed": safety_pass, "reason": safety_reason},
            "groundedness": {"passed": ground_pass, "reason": ground_reason},
        },
        "state_snapshot": {
            "exception_type": final_state.get("exception_type"),
            "diagnosis": final_state.get("diagnosis"),
            "requires_approval": final_state.get("requires_approval"),
            "approved": final_state.get("approved"),
            "executed_actions_count": len(final_state.get("executed_actions", [])),
            "injection_flagged": final_state.get("injection_flagged"),
        },
        "tokens": {
            "input": final_state.get("input_tokens", 0),
            "output": final_state.get("output_tokens", 0),
        },
        "latency_ms": final_state.get("total_latency_ms", 0.0),
    }


def run_eval_suite(
    prompt_version: str = "v1",
    model_name: str | None = None,
    category_filter: str | None = None,
) -> dict[str, Any]:
    """Execute the full benchmark suite across all scenarios."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    db_conn = init_evals_db()

    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    all_scenarios = data.get("scenarios", [])
    if category_filter:
        all_scenarios = [s for s in all_scenarios if s.get("category") == category_filter]

    llm = LLMClient()
    active_model = model_name or f"{llm.provider}:{llm.model}"
    run_id = f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

    console.print(f"\n[bold blue]=== ExceptionOps Evaluation Benchmark Harness ===[/bold blue]")
    console.print(f"[bold]Run ID:[/bold] [yellow]{run_id}[/yellow]")
    console.print(f"[bold]Prompt Version:[/bold] [green]{prompt_version}[/green]")
    console.print(f"[bold]Model:[/bold] [magenta]{active_model}[/magenta]")
    console.print(f"[bold]Total Scenarios:[/bold] {len(all_scenarios)}\n")

    conn_checkpointer = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn_checkpointer)

    scenario_results: list[dict[str, Any]] = []
    with console.status("[bold green]Running evaluation scenarios...[/bold green]", spinner="dots"):
        for scen in all_scenarios:
            res = run_scenario(scen, checkpointer, llm)
            scenario_results.append(res)
            status_color = "green" if res["passed"] else "red"
            status_text = "PASS" if res["passed"] else "FAIL"
            console.print(f"[{status_color}]● [/{status_color}] {res['scenario_id']} ({res['category']}): [{status_color}]{status_text}[/{status_color}]")

    # Aggregate Metrics
    total = len(scenario_results)
    passed_count = sum(1 for r in scenario_results if r["passed"])
    overall_pass_rate = (passed_count / total * 100.0) if total > 0 else 0.0

    # Per-category Breakdown
    categories = sorted(list(set(r["category"] for r in scenario_results)))
    category_stats = {}
    for cat in categories:
        cat_items = [r for r in scenario_results if r["category"] == cat]
        cat_passed = sum(1 for r in cat_items if r["passed"])
        cat_rate = (cat_passed / len(cat_items) * 100.0) if cat_items else 0.0
        category_stats[cat] = {
            "total": len(cat_items),
            "passed": cat_passed,
            "pass_rate": round(cat_rate, 1),
        }

    # Per-check Breakdown
    checks = ["diagnosis_correct", "tool_use_correct", "safety", "groundedness"]
    check_stats = {}
    for ch in checks:
        ch_passed = sum(1 for r in scenario_results if r["checks"][ch]["passed"])
        ch_rate = (ch_passed / total * 100.0) if total > 0 else 0.0
        check_stats[ch] = {
            "total": total,
            "passed": ch_passed,
            "pass_rate": round(ch_rate, 1),
        }

    # Regression Diff against Previous Run
    prev_run = get_latest_previous_run(db_conn)
    regressions = []
    improvements = []
    if prev_run and "scenario_results" in prev_run:
        prev_results = prev_run["scenario_results"]
        for r in scenario_results:
            scen_id = r["scenario_id"]
            if scen_id in prev_results:
                was_pass = prev_results[scen_id]
                is_pass = r["passed"]
                if was_pass and not is_pass:
                    regressions.append(scen_id)
                elif not was_pass and is_pass:
                    improvements.append(scen_id)

    report_payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "model": active_model,
        "summary": {
            "total_scenarios": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "pass_rate": round(overall_pass_rate, 1),
        },
        "by_category": category_stats,
        "by_check": check_stats,
        "diff": {
            "previous_run_id": prev_run.get("run_id") if prev_run else None,
            "regressions": regressions,
            "improvements": improvements,
        },
        "scenarios": scenario_results,
    }

    # Save to SQLite
    with db_conn:
        db_conn.execute(
            """INSERT INTO eval_runs (run_id, timestamp, prompt_version, model_name, total_scenarios, passed_scenarios, pass_rate, metrics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                report_payload["timestamp"],
                prompt_version,
                active_model,
                total,
                passed_count,
                overall_pass_rate,
                json.dumps(report_payload),
            )
        )
        for r in scenario_results:
            db_conn.execute(
                """INSERT INTO scenario_results (run_id, scenario_id, category, passed, diagnosis_pass, tools_pass, safety_pass, groundedness_pass, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    r["scenario_id"],
                    r["category"],
                    1 if r["passed"] else 0,
                    1 if r["checks"]["diagnosis_correct"]["passed"] else 0,
                    1 if r["checks"]["tool_use_correct"]["passed"] else 0,
                    1 if r["checks"]["safety"]["passed"] else 0,
                    1 if r["checks"]["groundedness"]["passed"] else 0,
                    json.dumps(r),
                )
            )

    # Export JSON
    latest_file = RESULTS_DIR / "latest.json"
    timestamp_file = RESULTS_DIR / f"{run_id}.json"

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)
    with open(timestamp_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    # Render Rich Tables
    console.print("\n")
    summary_panel = Panel(
        f"[bold]Overall Pass Rate:[/bold] [{'green' if overall_pass_rate >= 80 else 'yellow'}]{overall_pass_rate:.1f}%[/{'green' if overall_pass_rate >= 80 else 'yellow'}] ({passed_count}/{total} Passed)\n"
        f"[bold]Regressions:[/bold] [red]{len(regressions)}[/red] | [bold]Improvements:[/bold] [green]{len(improvements)}[/green]\n"
        f"[bold]JSON Report Exported:[/bold] [dim]evals/results/latest.json[/dim]",
        title="[bold green]Benchmark Performance Summary[/bold green]",
        border_style="green",
    )
    console.print(summary_panel)

    # Category Table
    cat_table = Table(title="Pass Rate by Category")
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Passed / Total", style="magenta")
    cat_table.add_column("Pass Rate", style="green")

    for cat, stats in category_stats.items():
        rate = stats["pass_rate"]
        color = "green" if rate >= 80 else "yellow" if rate >= 60 else "red"
        cat_table.add_row(cat, f"{stats['passed']}/{stats['total']}", f"[{color}]{rate:.1f}%[/{color}]")
    console.print(cat_table)

    # Check Table
    chk_table = Table(title="Pass Rate by Quality & Safety Check")
    chk_table.add_column("Evaluation Check", style="cyan")
    chk_table.add_column("Passed / Total", style="magenta")
    chk_table.add_column("Pass Rate", style="green")

    for chk, stats in check_stats.items():
        rate = stats["pass_rate"]
        color = "green" if rate >= 80 else "yellow" if rate >= 60 else "red"
        chk_table.add_row(chk, f"{stats['passed']}/{stats['total']}", f"[{color}]{rate:.1f}%[/{color}]")
    console.print(chk_table)

    return report_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ExceptionOps Benchmark Eval Suite")
    parser.add_argument("--prompt-version", default="v1", help="Prompt version tag (e.g. v1, v2)")
    parser.add_argument("--model", default=None, help="LLM model name")
    parser.add_argument("--category", default=None, help="Filter by scenario category")

    args = parser.parse_args()
    run_eval_suite(
        prompt_version=args.prompt_version,
        model_name=args.model,
        category_filter=args.category,
    )

