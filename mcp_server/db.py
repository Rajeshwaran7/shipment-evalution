"""In-memory database store and audit log for ExceptionOps MCP Server."""

import copy
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).parent / "data" / "shipments.json"

_INITIAL_SHIPMENTS: dict[str, dict[str, Any]] = {}
_SHIPMENTS: dict[str, dict[str, Any]] = {}
_AUDIT_LOG: list[dict[str, Any]] = []

EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def mask_pii(text: str) -> str:
    """Mask email addresses and phone numbers in text."""
    if not text:
        return text
    masked = EMAIL_REGEX.sub("[EMAIL_MASKED]", text)
    masked = PHONE_REGEX.sub("[PHONE_MASKED]", masked)
    return masked


def load_initial_data() -> None:
    """Load shipments from JSON file into memory."""
    global _INITIAL_SHIPMENTS, _SHIPMENTS, _AUDIT_LOG
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Shipments data file not found at {DATA_FILE}")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    _INITIAL_SHIPMENTS = {item["shipment_id"]: item for item in data}
    _SHIPMENTS = copy.deepcopy(_INITIAL_SHIPMENTS)
    _AUDIT_LOG = []


def reset_db() -> None:
    """Reset working copy of shipments to initial state and clear audit log."""
    global _SHIPMENTS, _AUDIT_LOG
    if not _INITIAL_SHIPMENTS:
        load_initial_data()
    _SHIPMENTS = copy.deepcopy(_INITIAL_SHIPMENTS)
    _AUDIT_LOG = []


def get_shipment(shipment_id: str) -> dict[str, Any] | None:
    """Retrieve a shipment by ID from in-memory store."""
    if not _SHIPMENTS:
        load_initial_data()
    return _SHIPMENTS.get(shipment_id)


def list_all_shipments() -> list[dict[str, Any]]:
    """List all shipments from in-memory store."""
    if not _SHIPMENTS:
        load_initial_data()
    return list(_SHIPMENTS.values())


def log_audit(action: str, shipment_id: str, details: dict[str, Any]) -> dict[str, Any]:
    """Append a mutation to the audit log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "shipment_id": shipment_id,
        "details": details,
    }
    _AUDIT_LOG.append(entry)
    return entry


def get_audit_log(shipment_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve audit log entries, optionally filtered by shipment_id."""
    if shipment_id:
        return [entry for entry in _AUDIT_LOG if entry["shipment_id"] == shipment_id]
    return list(_AUDIT_LOG)


# Automatically load on import
load_initial_data()

