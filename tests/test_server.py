"""Tests for the FastAPI server."""

import pytest
from fastapi.testclient import TestClient

from langchain_runner import Runner
from langchain_runner.server import create_app


async def mock_agent(input: dict) -> dict:
    """Mock agent for testing."""
    messages = input.get("messages", [])
    content = messages[-1]["content"] if messages else "empty"
    return {"messages": [{"role": "assistant", "content": f"Response: {content}"}]}


@pytest.fixture
def runner():
    """Create a test runner with triggers."""
    r = Runner(mock_agent, name="test-agent")

    @r.trigger("/ask")
    async def ask(question: str):
        return question

    @r.webhook("/github")
    async def on_github(payload: dict):
        return f"PR: {payload.get('title', 'unknown')}"

    return r


@pytest.fixture
def client(runner):
    """Create a test client."""
    app = create_app(runner)
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent_name"] == "test-agent"
        assert "version" in data


class TestTriggersEndpoint:
    """Tests for /triggers endpoint."""

    def test_list_triggers(self, client):
        """Test listing all triggers."""
        response = client.get("/triggers")
        assert response.status_code == 200
        triggers = response.json()
        assert len(triggers) == 2

        names = [t["name"] for t in triggers]
        assert "ask" in names
        assert "github" in names


class TestTriggerEndpoint:
    """Tests for /trigger/{name} endpoint."""

    def test_invoke_trigger(self, client, runner):
        """Test invoking an HTTP trigger."""
        response = client.post(
            "/trigger/ask",
            json={"question": "What is AI?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "pending"

    def test_trigger_not_found(self, client):
        """Test 404 for unknown trigger."""
        response = client.post("/trigger/unknown", json={})
        assert response.status_code == 404

    def test_invoke_webhook_as_trigger_fails(self, client):
        """Test that webhook triggers can't be invoked via /trigger."""
        response = client.post("/trigger/github", json={})
        assert response.status_code == 400  # Bad request - not an HTTP trigger


class TestWebhookEndpoint:
    """Tests for /webhook/{name} endpoint."""

    def test_invoke_webhook(self, client):
        """Test invoking a webhook."""
        response = client.post(
            "/webhook/github",
            json={"title": "Fix bug"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "pending"

    def test_webhook_not_found(self, client):
        """Test 404 for unknown webhook."""
        response = client.post("/webhook/unknown", json={})
        assert response.status_code == 404


class TestRunsEndpoint:
    """Tests for /runs endpoints."""

    def test_list_runs_empty(self, client):
        """Test listing runs when empty."""
        response = client.get("/runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_runs_after_trigger(self, client):
        """Test listing runs after invoking a trigger."""
        # Invoke a trigger
        client.post("/trigger/ask", json={"question": "Hello"})

        # List runs
        response = client.get("/runs")
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) == 1
        assert runs[0]["trigger_name"] == "ask"

    def test_get_run_by_id(self, client):
        """Test getting a specific run."""
        # Create a run
        create_response = client.post("/trigger/ask", json={"question": "Hello"})
        run_id = create_response.json()["run_id"]

        # Get the run
        response = client.get(f"/runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["trigger_name"] == "ask"

    def test_get_run_not_found(self, client):
        """Test 404 for unknown run ID."""
        response = client.get("/runs/nonexistent")
        assert response.status_code == 404
