"""Unit tests for ExceptionOps LangGraph Agent workflow using MockLLM."""

import pytest

from agent.graph import build_graph, node_risk_check
from agent.llm import LLMClient
from agent.mcp_client import mcp_client
from agent.state import AgentState
from mcp_server.db import reset_db


@pytest.fixture(autouse=True)
def run_around_tests():
    """Reset the database before each test run."""
    reset_db()
    yield
    reset_db()


class TestLLMWrapper:
    """Verify provider wrapper, latency, tokens, and offline fallback."""

    def test_mock_llm_classification(self):
        client = LLMClient(provider="mock")
        resp = client.generate(
            system_prompt="You are the Exception Classifier",
            user_prompt="Shipment SHP-1001 has blizzard delay",
        )
        assert resp.provider == "mock"
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0
        assert resp.latency_ms >= 0.0
        assert '"delay"' in resp.content.lower()

    def test_mock_llm_diagnosis(self):
        client = LLMClient(provider="mock")
        resp = client.generate(
            system_prompt="You are the Root Cause Diagnostician",
            user_prompt="Shipment SHP-1007 commercial invoice missing",
        )
        assert "invoice" in resp.content.lower()

    def test_mock_llm_planning(self):
        client = LLMClient(provider="mock")
        resp = client.generate(
            system_prompt="You are the Action Planner",
            user_prompt="Shipment SHP-1012 apartment missing",
        )
        assert "update_address" in resp.content


class TestAgentGraphWorkflow:
    """End-to-end graph tests for different shipment anomaly categories."""

    def test_weather_delay_resolution(self):
        graph = build_graph()
        initial_state: AgentState = {
            "shipment_id": "SHP-1001",
            "user_request": "Why is my package delayed in Chicago?",
            "approved": True,  # Pre-approved for end-to-end execution
        }

        final_state: AgentState = {}
        for event in graph.stream(initial_state):
            for node_name, output in event.items():
                if isinstance(output, dict):
                    final_state = {**final_state, **output}

        assert final_state.get("exception_type") == "delay"
        assert "blizzard" in final_state.get("diagnosis", "").lower() or "chicago" in final_state.get("diagnosis", "").lower()
        assert len(final_state.get("evidence", [])) >= 2
        assert final_state.get("requires_approval") is True
        assert len(final_state.get("executed_actions", [])) >= 1
        assert len(final_state.get("final_summary", "")) > 20

    def test_customs_hold_resolution(self):
        graph = build_graph()
        initial_state: AgentState = {
            "shipment_id": "SHP-1007",
            "user_request": "Why is my international package stopped at customs?",
        }

        final_state: AgentState = {}
        for event in graph.stream(initial_state):
            for node_name, output in event.items():
                if isinstance(output, dict):
                    final_state = {**final_state, **output}

        assert final_state.get("exception_type") == "customs"
        assert "invoice" in final_state.get("diagnosis", "").lower()
        assert len(final_state.get("evidence", [])) >= 2
        # Customs notification is low-risk ($0 cost)
        assert len(final_state.get("executed_actions", [])) >= 1
        assert len(final_state.get("final_summary", "")) > 20

    def test_address_exception_resolution(self):
        graph = build_graph()
        initial_state: AgentState = {
            "shipment_id": "SHP-1012",
            "user_request": "Driver says apartment number missing.",
            "approved": True,  # Pre-approved for end-to-end execution
        }

        final_state: AgentState = {}
        for event in graph.stream(initial_state):
            for node_name, output in event.items():
                if isinstance(output, dict):
                    final_state = {**final_state, **output}

        assert final_state.get("exception_type") == "address"
        assert "apartment" in final_state.get("diagnosis", "").lower()
        assert final_state.get("requires_approval") is True
        # Verify update_address tool was planned and executed
        tools_called = [a["tool"] for a in final_state.get("executed_actions", [])]
        assert "update_address" in tools_called

    def test_rejection_bypasses_execution(self):
        """When approval is rejected (False), execute node must be bypassed."""
        graph = build_graph()
        initial_state: AgentState = {
            "shipment_id": "SHP-1001",
            "user_request": "Why is it delayed?",
            "approved": False,  # Pre-rejected
            "rejection_comment": "Customer does not want reroute at this time.",
        }

        final_state: AgentState = {}
        executed_nodes = []
        for event in graph.stream(initial_state):
            for node_name, output in event.items():
                executed_nodes.append(node_name)
                final_state = {**final_state, **output}

        # Node 'execute' and 'notify' should NOT run if rejected
        assert "execute" not in executed_nodes
        assert len(final_state.get("executed_actions", [])) == 0
        assert "summarize" in executed_nodes

    def test_dynamic_tools_discovery_in_agent(self):
        tools = mcp_client.discover_tools()
        assert len(tools) == 7
        tool_names = [t["name"] for t in tools]
        assert "reroute_shipment" in tool_names
        assert "update_address" in tool_names
        assert "notify_customer" in tool_names

