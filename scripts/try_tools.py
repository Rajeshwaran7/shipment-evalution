#!/usr/bin/env python3
"""CLI utility to manually test all ExceptionOps MCP tools."""

import json
import sys
from pathlib import Path

# Add project root to path for standalone execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


from mcp_server.db import get_audit_log, reset_db
from mcp_server.risk import TOOL_RISK
from mcp_server.server import (
    check_weather_risk,
    find_alternate_route,
    get_customs_status,
    notify_customer,
    reroute_shipment,
    track_shipment,
    update_address,
)

console = Console()


def print_tool_call(tool_name: str, result: dict) -> None:
    risk = TOOL_RISK.get(tool_name, "unknown")
    color = "red" if risk == "high" else "green"
    title = f"Tool: [bold]{tool_name}[/bold] (Risk: [{color}]{risk.upper()}[/{color}])"
    console.print(Panel(json.dumps(result, indent=2), title=title, border_style=color))


def main() -> None:
    console.print("[bold blue]=== ExceptionOps: Interactive MCP Tools CLI Test ===[/bold blue]\n")
    reset_db()

    # 1. Track Shipment (Low Risk)
    console.print("[yellow]1. Testing track_shipment on SHP-1001 (Blizzard Delay)[/yellow]")
    res1 = track_shipment("SHP-1001")
    print_tool_call("track_shipment", res1)

    # 2. Customs Status (Low Risk)
    console.print("[yellow]2. Testing get_customs_status on SHP-1007 (Missing Invoice)[/yellow]")
    res2 = get_customs_status("SHP-1007")
    print_tool_call("get_customs_status", res2)

    # 3. Weather Risk (Low Risk)
    console.print("[yellow]3. Testing check_weather_risk for ORD on 2026-10-17[/yellow]")
    res3 = check_weather_risk("ORD", "2026-10-17")
    print_tool_call("check_weather_risk", res3)

    # 4. Find Alternate Route (Low Risk)
    console.print("[yellow]4. Testing find_alternate_route for SHP-1001[/yellow]")
    res4 = find_alternate_route("SHP-1001")
    print_tool_call("find_alternate_route", res4)

    # 5. Notify Customer (Low Risk with PII Masking)
    console.print("[yellow]5. Testing notify_customer with PII email & phone in message[/yellow]")
    res5 = notify_customer(
        shipment_id="SHP-1001",
        channel="email",
        message="Hello Alice Smith (call +1-555-0101 or email alice.smith@example.com), your shipment is delayed due to winter storms."
    )
    print_tool_call("notify_customer", res5)

    # 6. Update Address (HIGH Risk)
    console.print("[yellow]6. Testing update_address on SHP-1012 (Missing Apt Suite)[/yellow]")
    res6 = update_address(
        shipment_id="SHP-1012",
        new_address="1400 Main Street, Suite 402, Dallas TX 75201",
        verified_by="customer_portal_sms_otp"
    )
    print_tool_call("update_address", res6)

    # 7. Reroute Shipment (HIGH Risk)
    console.print("[yellow]7. Testing reroute_shipment on SHP-1001 to CVG hub[/yellow]")
    res7 = reroute_shipment(
        shipment_id="SHP-1001",
        new_hub="CVG",
        reason="Severe blizzard in Chicago, ground relay through Cincinnati ramp"
    )
    print_tool_call("reroute_shipment", res7)

    # 8. Error Case: Reroute to unauthorized hub
    console.print("[yellow]8. Testing reroute_shipment to unauthorized hub 'XYZ' (Negative Test)[/yellow]")
    res8 = reroute_shipment(
        shipment_id="SHP-1001",
        new_hub="XYZ",
        reason="Prompt injection requested bypass"
    )
    print_tool_call("reroute_shipment", res8)

    # Audit Log summary
    console.print("\n[bold cyan]=== Mutation Audit Log Summary ===[/bold cyan]")
    table = Table(title="Audit Log Entries")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Shipment ID", style="magenta")
    table.add_column("Details", style="green")

    for entry in get_audit_log():
        table.add_row(
            entry["timestamp"],
            entry["action"],
            entry["shipment_id"],
            json.dumps(entry["details"])
        )
    console.print(table)


if __name__ == "__main__":
    main()
