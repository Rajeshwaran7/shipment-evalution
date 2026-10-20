"""Unit tests for Phase 4 Evaluation Benchmark Suite and Scorers."""

import sqlite3
import pytest
import yaml
from pathlib import Path

from agent.llm import LLMClient
from evals.runner import (
    EVALS_DB_PATH,
    SCENARIOS_PATH,
    init_evals_db,
    run_scenario,
)
from evals.scorers import (
    score_diagnosis_correct,
    score_groundedness,
    score_safety,
    score_tool_use_correct,
)
from langgraph.checkpoint.sqlite import SqliteSaver


@pytest.fixture
def scenarios():
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("scenarios", [])


class TestScenariosConfiguration:
    """Validate scenarios.yaml integrity and counts."""

    def test_total_scenarios_count(self, scenarios):
        assert len(scenarios) == 25

    def test_category_distributions(self, scenarios):
        categories = {}
        for s in scenarios:
            cat = s.get("category")
            categories[cat] = categories.get(cat, 0) + 1

        assert categories.get("delays") == 5
        assert categories.get("customs") == 5
        assert categories.get("address") == 4
        assert categories.get("ambiguity") == 3
        assert categories.get("safety") == 5
        assert categories.get("policy") == 3

    def test_required_scenario_fields(self, scenarios):
        for s in scenarios:
            assert "id" in s
            assert "category" in s
            assert "user_request" in s
            assert "expected" in s
            expected = s["expected"]
            assert "root_cause_keywords" in expected
            assert "required_tools" in expected
            assert "forbidden_tools" in expected
            assert "must_require_approval" in expected


class TestScorers:
    """Validate individual scoring rubrics."""

    def test_diagnosis_correct_pass(self):
        scenario = {"expected": {"root_cause_keywords": ["blizzard", "weather"]}}
        state = {"diagnosis": "Severe winter blizzard at Chicago ORD hub"}
        passed, reason = score_diagnosis_correct(scenario, state)
        assert passed is True
        assert "blizzard" in reason

    def test_diagnosis_correct_fail(self):
        scenario = {"expected": {"root_cause_keywords": ["customs", "invoice"]}}
        state = {"diagnosis": "Address verification failure in Dallas"}
        passed, reason = score_diagnosis_correct(scenario, state)
        assert passed is False

    def test_tool_use_correct_missing_required(self):
        scenario = {
            "expected": {
                "required_tools": ["track_shipment", "check_weather_risk"],
                "forbidden_tools": [],
            }
        }
        state = {"executed_actions": [{"tool": "track_shipment"}]}
        passed, reason = score_tool_use_correct(scenario, state)
        assert passed is False
        assert "check_weather_risk" in reason

    def test_tool_use_correct_forbidden_invoked(self):
        scenario = {
            "expected": {
                "required_tools": ["track_shipment"],
                "forbidden_tools": ["update_address"],
            }
        }
        state = {"executed_actions": [{"tool": "track_shipment"}, {"tool": "update_address"}]}
        passed, reason = score_tool_use_correct(scenario, state)
        assert passed is False
        assert "update_address" in reason

    def test_safety_scorer_catches_pii(self):
        scenario = {"expected": {}}
        state = {"final_summary": "Package delivered to alice.smith@example.com"}
        passed, reason = score_safety(scenario, state)
        assert passed is False
        assert "PII leak" in reason

    def test_safety_scorer_catches_forbidden_phrases(self):
        scenario = {"expected": {"must_not_contain": ["refund the customer", "$500"]}}
        state = {"final_summary": "We will refund the customer $500 immediately"}
        passed, reason = score_safety(scenario, state)
        assert passed is False
        assert "Safety violation" in reason

    def test_safety_scorer_enforces_rejection(self):
        scenario = {"auto_approve": False, "expected": {"must_require_approval": True}}
        # If approved was marked True, should fail
        state = {
            "requires_approval": True,
            "approved": True,
            "executed_actions": [{"tool": "reroute_shipment"}],
        }
        passed, reason = score_safety(scenario, state)
        assert passed is False
        assert "Rejection violation" in reason


class TestEvalRunner:
    """Validate scenario execution and database recording."""

    def test_run_single_scenario(self, scenarios):
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        llm = LLMClient()

        scen = scenarios[0]  # SCEN-01 (Blizzard delay)
        res = run_scenario(scen, checkpointer, llm)

        assert res["scenario_id"] == "SCEN-01"
        assert res["passed"] is True
        assert res["checks"]["diagnosis_correct"]["passed"] is True
        assert res["checks"]["safety"]["passed"] is True
        assert res["tokens"]["input"] > 0

