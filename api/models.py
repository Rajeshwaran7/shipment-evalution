"""Pydantic data models for ExceptionOps API requests and responses."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    """Payload to initiate an agent resolution run."""
    shipment_id: str = Field(..., description="Shipment ID (e.g. SHP-1001)")
    request: str = Field(..., description="User request or inquiry regarding shipment exception")


class CreateRunResponse(BaseModel):
    """Response returned immediately after initiating a run."""
    run_id: str
    shipment_id: str
    status: Literal["running", "paused", "completed", "failed"]
    started_at: str


class ApprovalRequest(BaseModel):
    """Payload submitted to approve or reject a paused run."""
    decision: bool = Field(..., description="True to approve execution, False to reject")
    comment: str = Field(default="", description="Optional operator comment or reason")


class ApprovalResponse(BaseModel):
    """Response returned upon submitting an approval decision."""
    run_id: str
    status: str
    decision: bool
    resumed_at: str


class RunStepModel(BaseModel):
    """Representation of an individual agent execution step."""
    id: int | None = None
    node: str
    step_index: int
    summary: str
    details: dict[str, Any]
    tokens_in: int
    tokens_out: int
    latency_ms: float
    created_at: str


class RunSummaryModel(BaseModel):
    """Summary of a past or active agent run."""
    run_id: str
    shipment_id: str
    user_request: str
    status: str
    started_at: str
    completed_at: str | None = None
    duration_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    final_summary: str | None = None


class RunDetailModel(BaseModel):
    """Complete trace details of a run including steps and state."""
    run_id: str
    shipment_id: str
    user_request: str
    status: str
    started_at: str
    completed_at: str | None = None
    duration_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    final_summary: str | None = None
    error: str | None = None
    steps: list[dict[str, Any]] = []
    approval_details: dict[str, Any] | None = None

