"""State definition for ExceptionOps LangGraph Agent."""

from typing import Any, Literal, TypedDict

ExceptionCategory = Literal["delay", "customs", "address", "lost", "unknown"]


class ActionProposal(TypedDict):
    """Structured proposal for an action/tool call."""
    tool: str
    args: dict[str, Any]
    risk: Literal["low", "high"]
    estimated_cost_usd: float
    rationale: str


class StepRecord(TypedDict):
    """Record of an individual node or tool execution step."""
    node: str
    timestamp: str
    summary: str
    details: dict[str, Any]
    tokens: dict[str, int]
    latency_ms: float


class AgentState(TypedDict, total=False):
    """LangGraph Agent State for shipment exception resolution."""
    shipment_id: str
    user_request: str
    exception_type: ExceptionCategory
    diagnosis: str
    evidence: list[str]
    proposed_actions: list[dict[str, Any]]
    approved: bool | None
    executed_actions: list[dict[str, Any]]
    final_summary: str
    errors: list[str]

    # Telemetry and Human-in-the-Loop tracking
    requires_approval: bool
    approval_reason: str
    rejection_comment: str
    alternative_plan: list[dict[str, Any]]
    injection_flagged: bool
    injection_patterns: list[str]
    security_warnings: list[str]
    step_history: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    total_latency_ms: float
    estimated_cost_usd: float

