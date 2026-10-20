"""Risk level constants and tool risk mapping for ExceptionOps.

Hard rule 1: Risk is enforced in code, not by the prompt. Every MCP tool has a
risk annotation (low/high). Any high-risk tool call MUST pause the graph for
human approval.
"""

from typing import Final, Literal

RiskLevel = Literal["low", "high"]

RISK_LOW: Final[RiskLevel] = "low"
RISK_HIGH: Final[RiskLevel] = "high"

TOOL_RISK: Final[dict[str, RiskLevel]] = {
    "track_shipment": RISK_LOW,
    "get_customs_status": RISK_LOW,
    "check_weather_risk": RISK_LOW,
    "find_alternate_route": RISK_LOW,
    "notify_customer": RISK_LOW,
    "update_address": RISK_HIGH,
    "reroute_shipment": RISK_HIGH,
}


def is_high_risk(tool_name: str) -> bool:
    """Return True if the specified tool has a HIGH risk annotation."""
    return TOOL_RISK.get(tool_name, RISK_HIGH) == RISK_HIGH

