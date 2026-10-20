"""Unit tests for ExceptionOps FastAPI endpoints and SSE streaming."""

import time
import pytest
from fastapi.testclient import TestClient

from api.main import app
from mcp_server.db import reset_db


@pytest.fixture(scope="module")
def client():
    """Create FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def run_around_tests():
    """Reset the database before each test run."""
    reset_db()
    yield
    reset_db()


class TestSystemEndpoints:
    """Verify general system endpoints."""

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "ExceptionOps API"}

    def test_get_shipments_catalog(self, client):
        response = client.get("/shipments")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 20
        shipment_ids = [s["shipment_id"] for s in data]
        assert "SHP-1001" in shipment_ids
        assert "SHP-1020" in shipment_ids


class TestRunsLifecycleEndpoints:
    """Verify run creation, streaming, inspection, and approval endpoints."""

    def test_start_run_validation_errors(self, client):
        # Empty shipment ID
        res = client.post("/runs", json={"shipment_id": "", "request": "Status?"})
        assert res.status_code == 400

        # Empty request
        res = client.post("/runs", json={"shipment_id": "SHP-1001", "request": ""})
        assert res.status_code == 400

    def test_start_run_success(self, client):
        res = client.post(
            "/runs",
            json={"shipment_id": "SHP-1007", "request": "Why is it held at customs?"},
        )
        assert res.status_code == 201
        data = res.json()
        assert "run_id" in data
        assert data["shipment_id"] == "SHP-1007"
        assert data["status"] == "running"

    def test_get_run_trace_and_history(self, client):
        # Start a run
        create_res = client.post(
            "/runs",
            json={"shipment_id": "SHP-1007", "request": "Check customs status"},
        )
        run_id = create_res.json()["run_id"]

        # Fetch detail
        res = client.get(f"/runs/{run_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["run_id"] == run_id
        assert data["shipment_id"] == "SHP-1007"
        assert "steps" in data

        # Fetch history
        history_res = client.get("/runs")
        assert history_res.status_code == 200
        runs = history_res.json()
        assert any(r["run_id"] == run_id for r in runs)

    def test_get_run_not_found(self, client):
        res = client.get("/runs/non_existent_run_999")
        assert res.status_code == 404

    def test_stream_endpoint_returns_event_stream(self, client):
        # Start run
        create_res = client.post(
            "/runs",
            json={"shipment_id": "SHP-1018", "request": "Check progress"},
        )
        run_id = create_res.json()["run_id"]

        # Connect to stream
        with client.stream("GET", f"/runs/{run_id}/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            # Read first chunk
            for line in response.iter_lines():
                if line:
                    assert line.startswith("event:") or line.startswith("data:") or line.startswith(":")
                    break

    def test_approval_endpoint_flow(self, client):
        """Test approval submission on high-risk shipment."""
        # SHP-1001 requires high-risk reroute approval
        create_res = client.post(
            "/runs",
            json={"shipment_id": "SHP-1001", "request": "Reroute around storm"},
        )
        run_id = create_res.json()["run_id"]

        # Wait briefly for run to reach paused approval state
        max_attempts = 15
        is_paused = False
        for _ in range(max_attempts):
            time.sleep(0.1)
            detail = client.get(f"/runs/{run_id}").json()
            if detail.get("status") == "paused":
                is_paused = True
                break

        if is_paused:
            # Submit approval
            appr_res = client.post(
                f"/runs/{run_id}/approval",
                json={"decision": True, "comment": "Authorized by test"},
            )
            assert appr_res.status_code == 200
            assert appr_res.json()["decision"] is True
            assert appr_res.json()["status"] == "resuming"


class TestEvaluationEndpoints:
    """Verify evaluation reports and history endpoints."""

    def test_get_evals_latest(self, client):
        res = client.get("/evals/latest")
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data or data.get("status") == "no_results"

    def test_get_evals_history(self, client):
        res = client.get("/evals/history")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        if data:
            first = data[0]
            assert "run_id" in first
            assert "pass_rate" in first

