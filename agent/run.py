"""CLI Entrypoint for running ExceptionOps Agent on shipments with human approval gating."""

import argparse
import json
import sys
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from langgraph.types import Command
from agent.graph import build_graph, get_default_checkpointer
from agent.state import AgentState

console = Console()


def run_agent_cli(
    shipment_id: str,
    user_request: str,
    auto_approve: bool = True,
    reject: bool = False,
    rejection_comment: str = "Rejected by operations team",
) -> AgentState:
    """Run the ExceptionOps LangGraph agent on a single shipment with checkpointer and interrupt support."""
    console.print(f"\n[bold blue]=== ExceptionOps Agent Execution ===[/bold blue]")
    console.print(f"[bold]Shipment ID:[/bold] [yellow]{shipment_id}[/yellow]")
    console.print(f"[bold]User Request:[/bold] [cyan]{user_request}[/cyan]\n")

    checkpointer = get_default_checkpointer()
    graph = build_graph(checkpointer=checkpointer)

    thread_id = f"cli_{shipment_id}_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "shipment_id": shipment_id,
        "user_request": user_request,
    }

    final_state: AgentState = {}
    stream_active = True

    # Initial Stream Run
    with console.status("[bold green]Executing agent workflow...[/bold green]", spinner="dots"):
        for event in graph.stream(initial_state, config=config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
                    # Interrupt encountered
                    interrupt_val = node_output[0].value if node_output else {}
                    console.print("\n[bold yellow]⏸ GRAPH PAUSED: Human Approval Required![/bold yellow]")
                    proposals = interrupt_val.get("proposed_actions", [])
                    reasons = interrupt_val.get("approval_reason", "")
                    cost = interrupt_val.get("estimated_cost_usd", 0.0)

                    panel_content = (
                        f"[bold]Trigger Reason:[/bold] {reasons}\n"
                        f"[bold]Total Estimated Cost:[/bold] ${cost:.2f}\n"
                        f"[bold]Proposed Actions:[/bold]\n"
                        + "\n".join(f"- {p.get('tool')}: {p.get('rationale')} (Cost: ${p.get('estimated_cost_usd', 0.0):.2f})" for p in proposals)
                    )
                    console.print(Panel(panel_content, title="[bold red]Human Approval Gate[/bold red]", border_style="yellow"))

                    # Determine Decision
                    decision = not reject
                    comment = rejection_comment if reject else "Approved via CLI"
                    console.print(f"[bold cyan]Action Decision:[/bold cyan] [{'green]APPROVE' if decision else 'red]REJECT'}[/]")

                    # Resume Stream
                    for resumed_event in graph.stream(Command(resume={"approved": decision, "comment": comment}), config=config):
                        for r_node, r_output in resumed_event.items():
                            if isinstance(r_output, dict):
                                summary = ""
                                history = r_output.get("step_history", [])
                                if history:
                                    summary = history[-1].get("summary", "")
                                console.print(f"[cyan]▶ Step [{r_node.upper()}]:[/cyan] {summary}")
                                final_state = {**final_state, **r_output}
                    stream_active = False
                    break

                if isinstance(node_output, dict):
                    summary = ""
                    history = node_output.get("step_history", [])
                    if history:
                        summary = history[-1].get("summary", "")

                    color = "cyan"
                    if node_name == "risk_check":
                        color = "magenta"
                    elif node_name == "approval":
                        color = "yellow"
                    elif node_name == "execute":
                        color = "red"
                    elif node_name == "summarize":
                        color = "green"

                    console.print(f"[{color}]▶ Step [{node_name.upper()}]:[/{color}] {summary}")
                    final_state = {**final_state, **node_output}

    # Summary Panel
    console.print(Panel(
        final_state.get("final_summary", "No summary generated."),
        title="[bold green]Final Executive Summary[/bold green]",
        border_style="green",
    ))

    # Telemetry Table
    table = Table(title="Execution Telemetry & Governance")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Classified Category", str(final_state.get("exception_type", "unknown")))
    table.add_row("Requires Approval", str(final_state.get("requires_approval", False)))
    table.add_row("Approved", str(final_state.get("approved", None)))
    table.add_row("Actions Executed", str(len(final_state.get("executed_actions", []))))
    table.add_row("Injection Flagged", str(final_state.get("injection_flagged", False)))
    table.add_row("Input Tokens", str(final_state.get("input_tokens", 0)))
    table.add_row("Output Tokens", str(final_state.get("output_tokens", 0)))
    table.add_row("Total Latency (ms)", f"{final_state.get('total_latency_ms', 0.0):.2f}")
    table.add_row("Estimated Cost ($)", f"${final_state.get('estimated_cost_usd', 0.0):.2f}")

    console.print(table)
    return final_state


def main():
    parser = argparse.ArgumentParser(description="Run ExceptionOps Agent on a shipment")
    parser.add_argument("--shipment", required=True, help="Shipment ID (e.g. SHP-1001)")
    parser.add_argument("request", nargs="?", default="Why is my shipment delayed?", help="User request or question")
    parser.add_argument("--reject", action="store_true", help="Reject proposed high-risk actions during approval gate")
    parser.add_argument("--comment", default="Action rejected by user CLI", help="Rejection comment")

    args = parser.parse_args()
    run_agent_cli(
        shipment_id=args.shipment,
        user_request=args.request,
        reject=args.reject,
        rejection_comment=args.comment,
    )


if __name__ == "__main__":
    main()
