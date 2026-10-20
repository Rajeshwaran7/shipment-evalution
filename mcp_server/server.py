"""ExceptionOps FastMCP Server.

Exposes logistics tools with low and high risk annotations for:
- Tracking shipments
- Checking customs status
- Analyzing weather risks
- Proposing alternate routes
- Notifying customers (with PII masking)
- Updating delivery addresses (HIGH risk)
- Rerouting shipments (HIGH risk with hub allowlist)
"""

import json
from datetime import datetime, timezone
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP

from mcp_server.db import (
    get_audit_log,
    get_shipment,
    list_all_shipments,
    log_audit,
    mask_pii,
    reset_db,
)
from mcp_server.risk import RISK_HIGH, RISK_LOW, TOOL_RISK

# Enforce allowed logistics hubs
ALLOWED_HUBS = {
    "ORD", "JFK", "LAX", "DFW", "ATL", "MEM",
    "CVG", "MIA", "SEA", "DEN", "BOS", "ANC", "PHX", "OAK"
}

# Hub weather database for simulation
WEATHER_DATABASE = {
    "ORD": {"condition": "Severe Winter Blizzard", "risk": "severe", "impact": "Ground operations halted, runway closed"},
    "JFK": {"condition": "Severe Thunderstorms and Wind Shear", "risk": "severe", "impact": "FAA ground stop in effect"},
    "SFO": {"condition": "Dense Fog Zero Visibility", "risk": "moderate", "impact": "Flow control restrictions, 25% arrival capacity"},
    "DEN": {"condition": "Heavy Snow Flurries", "risk": "moderate", "impact": "De-icing delays 45-60 minutes"},
    "MIA": {"condition": "Tropical Squall", "risk": "moderate", "impact": "Intermittent ramp holds"},
    "DFW": {"condition": "Clear", "risk": "low", "impact": "Normal flight operations"},
    "ATL": {"condition": "Clear", "risk": "low", "impact": "Normal operations"},
    "MEM": {"condition": "Scattered Clouds", "risk": "low", "impact": "Normal operations"},
    "CVG": {"condition": "Light Rain", "risk": "low", "impact": "Normal rail/air ramp operations"},
    "LAX": {"condition": "Sunny", "risk": "low", "impact": "Normal gate operations"},
    "SEA": {"condition": "Overcast", "risk": "low", "impact": "Normal operations"},
    "BOS": {"condition": "Fair", "risk": "low", "impact": "Normal operations"},
    "ANC": {"condition": "Cold/Clear", "risk": "low", "impact": "Normal cargo operations"},
}

mcp = FastMCP("ExceptionOps-Logistics-Server")


@mcp.tool(description="Retrieve full tracking details, history, and status for a shipment. [Risk: low]")
def track_shipment(shipment_id: str) -> dict[str, Any]:
    """Track a shipment by ID."""
    if not shipment_id or not shipment_id.strip():
        return {"status": "error", "error": "shipment_id cannot be empty"}

    shipment = get_shipment(shipment_id.strip())
    if not shipment:
        return {
            "status": "error",
            "error": f"Shipment '{shipment_id}' not found in system",
            "shipment_id": shipment_id,
        }

    return {
        "status": "success",
        "shipment_id": shipment["shipment_id"],
        "origin": shipment["origin"],
        "destination": shipment["destination"],
        "shipment_status": shipment["status"],
        "eta": shipment["eta"],
        "last_event": shipment["last_event"],
        "events": shipment["events"],
        "notes": shipment["notes"],
        "address_verified": shipment["address_verified"],
    }


@mcp.tool(description="Check customs clearance status, hold reasons, and missing documentation. [Risk: low]")
def get_customs_status(shipment_id: str) -> dict[str, Any]:
    """Retrieve customs clearance details for international or cross-border parcels."""
    if not shipment_id or not shipment_id.strip():
        return {"status": "error", "error": "shipment_id cannot be empty"}

    shipment = get_shipment(shipment_id.strip())
    if not shipment:
        return {
            "status": "error",
            "error": f"Shipment '{shipment_id}' not found in system",
            "shipment_id": shipment_id,
        }

    customs = shipment.get("customs", {})
    return {
        "status": "success",
        "shipment_id": shipment["shipment_id"],
        "customs_status": customs.get("status", "unknown"),
        "hold_reason": customs.get("hold_reason"),
        "missing_documents": customs.get("missing_documents", []),
    }


@mcp.tool(description="Assess atmospheric and weather hazards at a logistics hub on a specific date. [Risk: low]")
def check_weather_risk(location: str, date: str) -> dict[str, Any]:
    """Evaluate weather risks and transit disruptions at a given airport or port hub."""
    if not location or not location.strip():
        return {"status": "error", "error": "location cannot be empty"}
    if not date or not date.strip():
        return {"status": "error", "error": "date cannot be empty"}

    loc_upper = location.strip().upper()
    weather_info = WEATHER_DATABASE.get(loc_upper, {
        "condition": "Normal meteorological conditions",
        "risk": "low",
        "impact": "No weather-related operational delays detected",
    })

    return {
        "status": "success",
        "location": loc_upper,
        "date": date.strip(),
        "risk_level": weather_info["risk"],
        "condition": weather_info["condition"],
        "impact": weather_info["impact"],
    }


@mcp.tool(description="Identify alternative transit routes and bypass hubs to circumvent delays. [Risk: low]")
def find_alternate_route(shipment_id: str) -> dict[str, Any]:
    """Compute available detour routes, transit time delta, and added costs."""
    if not shipment_id or not shipment_id.strip():
        return {"status": "error", "error": "shipment_id cannot be empty"}

    shipment = get_shipment(shipment_id.strip())
    if not shipment:
        return {
            "status": "error",
            "error": f"Shipment '{shipment_id}' not found in system",
            "shipment_id": shipment_id,
        }

    origin = shipment["origin"]
    dest = shipment["destination"]

    # Pre-calculated alternative hubs based on origin/destination
    alternatives = []
    if origin == "ORD":
        alternatives.append({
            "via_hub": "CVG",
            "eta_hours_added": 8,
            "estimated_cost_usd": 120.0,
            "feasibility": "high",
            "notes": "Truck relay via Cincinnati avoids grounded Chicago flights"
        })
        alternatives.append({
            "via_hub": "MEM",
            "eta_hours_added": 12,
            "estimated_cost_usd": 240.0,
            "feasibility": "medium",
            "notes": "Air feeder via Memphis air sort hub"
        })
    elif origin == "JFK":
        alternatives.append({
            "via_hub": "ATL",
            "eta_hours_added": 6,
            "estimated_cost_usd": 150.0,
            "feasibility": "high",
            "notes": "Bypass East Coast storm through Southeast corridor"
        })
    elif origin == "LAX":
        alternatives.append({
            "via_hub": "OAK",
            "eta_hours_added": 10,
            "estimated_cost_usd": 180.0,
            "feasibility": "high",
            "notes": "Regional transfer via Northern California hub"
        })
    else:
        alternatives.append({
            "via_hub": "DFW",
            "eta_hours_added": 14,
            "estimated_cost_usd": 210.0,
            "feasibility": "medium",
            "notes": "Central distribution hub bypass"
        })

    return {
        "status": "success",
        "shipment_id": shipment["shipment_id"],
        "current_origin": origin,
        "current_destination": dest,
        "alternate_routes": alternatives,
    }


@mcp.tool(description="Send an operational update to the customer with automatic PII masking. [Risk: low, templated, masks PII]")
def notify_customer(shipment_id: str, channel: str, message: str) -> dict[str, Any]:
    """Dispatch customer notifications across email, sms, or portal while redacting PII."""
    if not shipment_id or not shipment_id.strip():
        return {"status": "error", "error": "shipment_id cannot be empty"}
    if not channel or channel.strip().lower() not in {"email", "sms", "portal"}:
        return {"status": "error", "error": f"Invalid channel '{channel}'. Allowed: email, sms, portal"}
    if not message or not message.strip():
        return {"status": "error", "error": "message cannot be empty"}

    shipment = get_shipment(shipment_id.strip())
    if not shipment:
        return {
            "status": "error",
            "error": f"Shipment '{shipment_id}' not found in system",
            "shipment_id": shipment_id,
        }

    # Mask any PII inside message
    cleaned_message = mask_pii(message.strip())

    # Mask recipient customer details
    raw_customer = shipment.get("customer", {})
    masked_email = mask_pii(raw_customer.get("email", ""))
    masked_phone = mask_pii(raw_customer.get("phone", ""))
    recipient_identifier = masked_email if channel == "email" else masked_phone

    # Mutate in-memory events
    now_iso = datetime.now(timezone.utc).isoformat()
    shipment["events"].append({
        "timestamp": now_iso,
        "location": shipment["destination"],
        "description": f"Customer notification dispatched via {channel.upper()}"
    })

    # Append to audit log
    audit_entry = log_audit(
        action="notify_customer",
        shipment_id=shipment["shipment_id"],
        details={
            "channel": channel,
            "masked_message": cleaned_message,
            "recipient": recipient_identifier,
        }
    )

    return {
        "status": "success",
        "shipment_id": shipment["shipment_id"],
        "channel": channel,
        "masked_message": cleaned_message,
        "recipient": recipient_identifier,
        "timestamp": audit_entry["timestamp"],
    }


@mcp.tool(description="Update destination delivery address. Modifies core delivery destination. [Risk: HIGH]")
def update_address(shipment_id: str, new_address: str, verified_by: str) -> dict[str, Any]:
    """Correct or update customer street address for stalled parcels."""
    if not shipment_id or not shipment_id.strip():
        return {"status": "error", "error": "shipment_id cannot be empty"}
    if not new_address or not new_address.strip():
        return {"status": "error", "error": "new_address cannot be empty"}
    if not verified_by or not verified_by.strip():
        return {"status": "error", "error": "verified_by cannot be empty"}

    shipment = get_shipment(shipment_id.strip())
    if not shipment:
        return {
            "status": "error",
            "error": f"Shipment '{shipment_id}' not found in system",
            "shipment_id": shipment_id,
        }

    # Apply in-memory state update
    old_verified = shipment.get("address_verified", False)
    shipment["address_verified"] = True
    now_iso = datetime.now(timezone.utc).isoformat()
    shipment["events"].append({
        "timestamp": now_iso,
        "location": shipment["destination"],
        "description": f"Address updated to: {new_address.strip()} (Verified by: {verified_by.strip()})"
    })
    shipment["status"] = "in_transit"

    # Audit log
    audit_entry = log_audit(
        action="update_address",
        shipment_id=shipment["shipment_id"],
        details={
            "new_address": new_address.strip(),
            "verified_by": verified_by.strip(),
            "previous_address_verified": old_verified,
        }
    )

    return {
        "status": "success",
        "shipment_id": shipment["shipment_id"],
        "new_address": new_address.strip(),
        "address_verified": True,
        "verified_by": verified_by.strip(),
        "timestamp": audit_entry["timestamp"],
    }


@mcp.tool(description="Reroute a delayed or blocked parcel through a new transit hub. Modifies physical transit routing. [Risk: HIGH]")
def reroute_shipment(shipment_id: str, new_hub: str, reason: str) -> dict[str, Any]:
    """Execute high-risk physical rerouting to an approved alternative hub."""
    if not shipment_id or not shipment_id.strip():
        return {"status": "error", "error": "shipment_id cannot be empty"}
    if not new_hub or not new_hub.strip():
        return {"status": "error", "error": "new_hub cannot be empty"}
    if not reason or not reason.strip():
        return {"status": "error", "error": "reason cannot be empty"}

    hub_clean = new_hub.strip().upper()
    if hub_clean not in ALLOWED_HUBS:
        return {
            "status": "error",
            "error": f"Hub '{new_hub}' is not an authorized transit hub. Allowed hubs: {sorted(list(ALLOWED_HUBS))}",
            "shipment_id": shipment_id,
        }

    shipment = get_shipment(shipment_id.strip())
    if not shipment:
        return {
            "status": "error",
            "error": f"Shipment '{shipment_id}' not found in system",
            "shipment_id": shipment_id,
        }

    # Apply in-memory state update
    old_last_event = shipment.get("last_event")
    now_iso = datetime.now(timezone.utc).isoformat()
    new_event_desc = f"Rerouted via hub {hub_clean}. Reason: {reason.strip()}"
    shipment["last_event"] = new_event_desc
    shipment["status"] = "rerouted"
    shipment["events"].append({
        "timestamp": now_iso,
        "location": hub_clean,
        "description": new_event_desc,
    })

    # Audit log
    audit_entry = log_audit(
        action="reroute_shipment",
        shipment_id=shipment["shipment_id"],
        details={
            "new_hub": hub_clean,
            "reason": reason.strip(),
            "previous_last_event": old_last_event,
        }
    )

    return {
        "status": "success",
        "shipment_id": shipment["shipment_id"],
        "new_hub": hub_clean,
        "reason": reason.strip(),
        "updated_last_event": new_event_desc,
        "timestamp": audit_entry["timestamp"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

