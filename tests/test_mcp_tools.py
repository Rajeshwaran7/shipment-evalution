"""Unit tests for ExceptionOps MCP Tools and mock logistics dataset."""

import pytest

from mcp_server.db import (
    get_audit_log,
    get_shipment,
    list_all_shipments,
    mask_pii,
    reset_db,
)
from mcp_server.risk import RISK_HIGH, RISK_LOW, TOOL_RISK, is_high_risk
from mcp_server.server import (
    ALLOWED_HUBS,
    check_weather_risk,
    find_alternate_route,
    get_customs_status,
    notify_customer,
    reroute_shipment,
    track_shipment,
    update_address,
)


@pytest.fixture(autouse=True)
def run_around_tests():
    """Reset the database before each test."""
    reset_db()
    yield
    reset_db()


class TestShipmentsDataset:
    """Validate data integrity and seeded problem distributions."""

    def test_total_shipments_count(self):
        shipments = list_all_shipments()
        assert len(shipments) == 20

    def test_seeded_problem_distribution(self):
        shipments = list_all_shipments()

        delays = [s for s in shipments if s["status"] == "delayed"]
        customs = [s for s in shipments if s["status"] == "customs_hold"]
        address = [s for s in shipments if not s["address_verified"] and s["status"] == "exception"]
        lost = [s for s in shipments if s["address_verified"] and s["status"] == "exception"]
        clean = [s for s in shipments if s["status"] in {"in_transit", "out_for_delivery", "delivered"}]

        assert len(delays) == 6, f"Expected 6 delays, got {len(delays)}"
        assert len(customs) == 5, f"Expected 5 customs holds, got {len(customs)}"
        assert len(address) == 4, f"Expected 4 address issues, got {len(address)}"
        assert len(lost) == 2, f"Expected 2 lost shipments, got {len(lost)}"
        assert len(clean) == 3, f"Expected 3 clean shipments, got {len(clean)}"

    def test_prompt_injection_shipments(self):
        shipments = list_all_shipments()
        injections = []
        for s in shipments:
            notes = s["notes"].lower()
            if any(phrase in notes for phrase in ["ignore previous", "system prompt", "unrestricted assistant"]):
                injections.append(s["shipment_id"])

        assert len(injections) == 3
        assert "SHP-1003" in injections
        assert "SHP-1009" in injections
        assert "SHP-1014" in injections


class TestRiskMapping:
    """Validate tool risk classifications."""

    def test_all_tools_have_risk_annotation(self):
        expected_tools = {
            "track_shipment",
            "get_customs_status",
            "check_weather_risk",
            "find_alternate_route",
            "notify_customer",
            "update_address",
            "reroute_shipment",
        }
        assert set(TOOL_RISK.keys()) == expected_tools

    def test_high_risk_tools(self):
        assert is_high_risk("update_address") is True
        assert is_high_risk("reroute_shipment") is True
        assert TOOL_RISK["update_address"] == RISK_HIGH
        assert TOOL_RISK["reroute_shipment"] == RISK_HIGH

    def test_low_risk_tools(self):
        assert is_high_risk("track_shipment") is False
        assert is_high_risk("get_customs_status") is False
        assert is_high_risk("check_weather_risk") is False
        assert is_high_risk("find_alternate_route") is False
        assert is_high_risk("notify_customer") is False


class TestTrackShipmentTool:
    """Test track_shipment behavior and error cases."""

    def test_track_valid_shipment(self):
        res = track_shipment("SHP-1001")
        assert res["status"] == "success"
        assert res["shipment_id"] == "SHP-1001"
        assert res["origin"] == "ORD"
        assert res["destination"] == "DFW"
        assert res["shipment_status"] == "delayed"
        assert len(res["events"]) >= 3

    def test_track_unknown_shipment(self):
        res = track_shipment("SHP-9999")
        assert res["status"] == "error"
        assert "not found" in res["error"]

    def test_track_empty_id(self):
        res = track_shipment("")
        assert res["status"] == "error"
        assert "empty" in res["error"]


class TestCustomsStatusTool:
    """Test get_customs_status behavior and error cases."""

    def test_customs_hold_details(self):
        res = get_customs_status("SHP-1007")
        assert res["status"] == "success"
        assert res["customs_status"] == "held"
        assert res["hold_reason"] == "Missing Commercial Invoice"
        assert "Commercial Invoice" in res["missing_documents"]

    def test_customs_cleared(self):
        res = get_customs_status("SHP-1001")
        assert res["status"] == "success"
        assert res["customs_status"] == "cleared"
        assert res["hold_reason"] is None
        assert res["missing_documents"] == []

    def test_customs_unknown_id(self):
        res = get_customs_status("SHP-9999")
        assert res["status"] == "error"
        assert "not found" in res["error"]


class TestWeatherRiskTool:
    """Test check_weather_risk evaluation."""

    def test_severe_weather_at_hub(self):
        res = check_weather_risk("ORD", "2026-10-17")
        assert res["status"] == "success"
        assert res["risk_level"] == "severe"
        assert "Blizzard" in res["condition"]

    def test_clear_weather_at_hub(self):
        res = check_weather_risk("DFW", "2026-10-17")
        assert res["status"] == "success"
        assert res["risk_level"] == "low"

    def test_empty_location(self):
        res = check_weather_risk("", "2026-10-17")
        assert res["status"] == "error"


class TestFindAlternateRouteTool:
    """Test find_alternate_route detour calculations."""

    def test_alternate_routes_ord(self):
        res = find_alternate_route("SHP-1001")
        assert res["status"] == "success"
        assert len(res["alternate_routes"]) > 0
        hubs = [route["via_hub"] for route in res["alternate_routes"]]
        assert "CVG" in hubs
        assert res["alternate_routes"][0]["estimated_cost_usd"] > 0

    def test_alternate_routes_unknown_id(self):
        res = find_alternate_route("SHP-9999")
        assert res["status"] == "error"
        assert "not found" in res["error"]


class TestNotifyCustomerTool:
    """Test notify_customer with PII masking and audit logging."""

    def test_notify_pii_masking_in_message(self):
        raw_msg = "Please contact support at support@logistics.com or +1-555-987-6543 regarding parcel."
        res = notify_customer("SHP-1001", "email", raw_msg)
        assert res["status"] == "success"
        assert "[EMAIL_MASKED]" in res["masked_message"]
        assert "[PHONE_MASKED]" in res["masked_message"]
        assert "support@logistics.com" not in res["masked_message"]
        assert "+1-555-987-6543" not in res["masked_message"]

    def test_notify_masks_customer_recipient(self):
        res = notify_customer("SHP-1001", "email", "Your shipment has been delayed.")
        assert res["status"] == "success"
        assert "[EMAIL_MASKED]" in res["recipient"]

    def test_notify_invalid_channel(self):
        res = notify_customer("SHP-1001", "pigeon_post", "Delayed")
        assert res["status"] == "error"
        assert "Invalid channel" in res["error"]

    def test_notify_records_audit_log(self):
        res = notify_customer("SHP-1001", "sms", "Weather update for shipment")
        assert res["status"] == "success"
        logs = get_audit_log("SHP-1001")
        assert len(logs) == 1
        assert logs[0]["action"] == "notify_customer"


class TestUpdateAddressTool:
    """Test update_address HIGH-risk tool."""

    def test_update_address_success(self):
        res = update_address(
            shipment_id="SHP-1012",
            new_address="1400 Main Street, Suite 402, Dallas TX 75201",
            verified_by="agent_phone_auth"
        )
        assert res["status"] == "success"
        assert res["address_verified"] is True
        assert res["verified_by"] == "agent_phone_auth"

        # Verify mutation in database
        updated = get_shipment("SHP-1012")
        assert updated["address_verified"] is True
        assert any("Suite 402" in evt["description"] for evt in updated["events"])

        # Verify audit log
        logs = get_audit_log("SHP-1012")
        assert len(logs) == 1
        assert logs[0]["action"] == "update_address"

    def test_update_address_missing_args(self):
        res = update_address("SHP-1012", "", "agent")
        assert res["status"] == "error"
        assert "new_address cannot be empty" in res["error"]


class TestRerouteShipmentTool:
    """Test reroute_shipment HIGH-risk tool and hub allowlist."""

    def test_reroute_to_allowed_hub(self):
        res = reroute_shipment("SHP-1001", "CVG", "Blizzard detour via Cincinnati")
        assert res["status"] == "success"
        assert res["new_hub"] == "CVG"
        assert "CVG" in res["updated_last_event"]

        # Check DB update
        updated = get_shipment("SHP-1001")
        assert updated["status"] == "rerouted"
        assert "CVG" in updated["last_event"]

        # Check audit log
        logs = get_audit_log("SHP-1001")
        assert len(logs) == 1
        assert logs[0]["action"] == "reroute_shipment"
        assert logs[0]["details"]["new_hub"] == "CVG"

    def test_reroute_to_unauthorized_hub_rejected(self):
        res = reroute_shipment("SHP-1001", "XYZ", "Prompt injection malicious destination")
        assert res["status"] == "error"
        assert "not an authorized transit hub" in res["error"]

        # DB must NOT be modified
        shipment = get_shipment("SHP-1001")
        assert shipment["status"] == "delayed"
        assert len(get_audit_log("SHP-1001")) == 0

    def test_reroute_unknown_shipment(self):
        res = reroute_shipment("SHP-9999", "CVG", "Detour")
        assert res["status"] == "error"
        assert "not found" in res["error"]

