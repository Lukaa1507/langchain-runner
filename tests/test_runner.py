"""Tests for the Runner class."""


from langchain_runner import Runner
from langchain_runner.models import RunStatus, TriggerType
from langchain_runner.triggers import Trigger


# Test fixtures
async def mock_agent(input: dict) -> dict:
    """Mock agent for testing."""
    messages = input.get("messages", [])
    content = messages[-1]["content"] if messages else "empty"
    return {"messages": [{"role": "assistant", "content": f"Response: {content}"}]}


def sync_mock_agent(input: dict) -> dict:
    """Sync mock agent for testing."""
    return {"response": "sync response"}


class TestRunner:
    """Tests for Runner class."""

    def test_create_runner_with_async_callable(self):
        """Test creating a runner with an async callable."""
        runner = Runner(mock_agent, name="test")
        assert runner.name == "test"
        assert runner.adapter is not None

    def test_create_runner_with_sync_callable(self):
        """Test creating a runner with a sync callable."""
        runner = Runner(sync_mock_agent)
        assert runner.adapter is not None

    def test_trigger_decorator(self):
        """Test the @trigger decorator."""
        runner = Runner(mock_agent)

        @runner.trigger("/ask")
        async def ask(question: str):
            return question

        triggers = runner.get_triggers()
        assert len(triggers) == 1
        assert triggers[0].name == "ask"
        assert triggers[0].trigger_type == TriggerType.HTTP

    def test_webhook_decorator(self):
        """Test the @webhook decorator."""
        runner = Runner(mock_agent)

        @runner.webhook("/github")
        async def on_github(payload: dict):
            return f"event: {payload.get('action')}"

        triggers = runner.get_triggers()
        assert len(triggers) == 1
        assert triggers[0].name == "github"
        assert triggers[0].trigger_type == TriggerType.WEBHOOK

    def test_cron_decorator(self):
        """Test the @cron decorator."""
        runner = Runner(mock_agent)

        @runner.cron("0 9 * * *")
        async def daily():
            return "daily task"

        triggers = runner.get_triggers()
        cron_triggers = runner.get_cron_triggers()

        assert len(triggers) == 1
        assert len(cron_triggers) == 1
        assert cron_triggers[0].schedule == "0 9 * * *"
        assert cron_triggers[0].trigger_type == TriggerType.CRON

    def test_multiple_triggers(self):
        """Test registering multiple triggers."""
        runner = Runner(mock_agent)

        @runner.trigger("/ask")
        async def ask(q: str):
            return q

        @runner.webhook("/stripe")
        async def stripe(payload: dict):
            return str(payload)

        @runner.cron("* * * * *")
        async def minute():
            return "tick"

        assert len(runner.get_triggers()) == 3
        assert len(runner.get_cron_triggers()) == 1


class TestRunStore:
    """Tests for run storage."""

    def test_create_and_get_run(self):
        """Test creating and retrieving a run."""
        runner = Runner(mock_agent)
        run = runner.store.create_run(
            trigger_type=TriggerType.HTTP,
            trigger_name="test",
            input="hello",
        )

        assert run.run_id is not None
        assert run.status == RunStatus.PENDING
        assert run.input == "hello"

        retrieved = runner.store.get_run(run.run_id)
        assert retrieved is not None
        assert retrieved.run_id == run.run_id

    def test_list_runs(self):
        """Test listing runs."""
        runner = Runner(mock_agent)

        for i in range(5):
            runner.store.create_run(
                trigger_type=TriggerType.HTTP,
                trigger_name=f"test_{i}",
                input=f"input_{i}",
            )

        runs = runner.store.list_runs()
        assert len(runs) == 5
        # Most recent first
        assert runs[0].trigger_name == "test_4"

    def test_update_run(self):
        """Test updating a run."""
        runner = Runner(mock_agent)
        run = runner.store.create_run(
            trigger_type=TriggerType.HTTP,
            trigger_name="test",
            input="hello",
        )

        runner.store.update_run(
            run.run_id,
            status=RunStatus.COMPLETED,
            result={"output": "world"},
            final_message="world",
        )

        updated = runner.store.get_run(run.run_id)
        assert updated is not None
        assert updated.status == RunStatus.COMPLETED
        assert updated.result == {"output": "world"}
        assert updated.final_message == "world"

    def test_max_runs_eviction(self):
        """Test that old runs are evicted when max is reached."""
        runner = Runner(mock_agent, max_runs=3)

        for i in range(5):
            runner.store.create_run(
                trigger_type=TriggerType.HTTP,
                trigger_name=f"test_{i}",
                input=f"input_{i}",
            )

        runs = runner.store.list_runs()
        assert len(runs) == 3
        # Only the last 3 should remain
        names = [r.trigger_name for r in runs]
        assert "test_0" not in names
        assert "test_1" not in names
        assert "test_4" in names
