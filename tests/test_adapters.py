"""Tests for agent adapters."""

import pytest

from langchain_runner.adapters import AgentAdapter, create_adapter


class TestAgentAdapter:
    """Tests for AgentAdapter."""

    def test_create_adapter_async_callable(self):
        """Test creating adapter for async callable."""

        async def agent(input: dict) -> dict:
            return {"result": "ok"}

        adapter = create_adapter(agent)
        assert isinstance(adapter, AgentAdapter)

    def test_create_adapter_sync_callable(self):
        """Test creating adapter for sync callable."""

        def agent(input: dict) -> dict:
            return {"result": "ok"}

        adapter = create_adapter(agent)
        assert isinstance(adapter, AgentAdapter)

    def test_create_adapter_langgraph_like(self):
        """Test creating adapter for LangGraph-like object."""

        class FakeCompiledGraph:
            def invoke(self, input: dict, config=None) -> dict:
                return {"messages": [{"role": "assistant", "content": "hi"}]}

            async def ainvoke(self, input: dict, config=None) -> dict:
                return {"messages": [{"role": "assistant", "content": "hi"}]}

        adapter = create_adapter(FakeCompiledGraph())
        assert isinstance(adapter, AgentAdapter)

    @pytest.mark.asyncio
    async def test_invoke_async_callable(self):
        """Test invoking an async callable."""

        async def agent(input: dict) -> dict:
            return {"response": input["messages"][0]["content"]}

        adapter = create_adapter(agent)
        result = await adapter.invoke("hello")
        assert result == {"response": "hello"}

    @pytest.mark.asyncio
    async def test_invoke_sync_callable(self):
        """Test invoking a sync callable."""

        def agent(input: dict) -> dict:
            return {"response": "sync"}

        adapter = create_adapter(agent)
        result = await adapter.invoke("hello")
        assert result == {"response": "sync"}

    @pytest.mark.asyncio
    async def test_invoke_langgraph_like(self):
        """Test invoking a LangGraph-like agent."""

        class FakeGraph:
            async def ainvoke(self, input: dict, config=None) -> dict:
                return {"messages": [{"role": "assistant", "content": "response"}]}

            def invoke(self, input: dict, config=None) -> dict:
                return {"messages": [{"role": "assistant", "content": "response"}]}

        adapter = create_adapter(FakeGraph())
        result = await adapter.invoke("test")
        assert result["messages"][0]["content"] == "response"

    def test_extract_final_message_string(self):
        """Test extracting message from string result."""
        adapter = create_adapter(lambda x: x)
        assert adapter.extract_final_message("hello") == "hello"

    def test_extract_final_message_dict(self):
        """Test extracting message from dict result."""
        adapter = create_adapter(lambda x: x)
        assert adapter.extract_final_message({"content": "hello"}) == "hello"
        assert adapter.extract_final_message({"response": "world"}) == "world"

    def test_extract_final_message_messages(self):
        """Test extracting message from messages format."""
        adapter = create_adapter(lambda x: x)
        result = {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        }
        assert adapter.extract_final_message(result) == "hello"

    def test_prepare_input_string(self):
        """Test preparing string input."""
        adapter = create_adapter(lambda x: x)
        prepared = adapter._prepare_input("hello")
        assert prepared == {"messages": [{"role": "user", "content": "hello"}]}

    def test_prepare_input_dict_passthrough(self):
        """Test preparing dict input passes through."""
        adapter = create_adapter(lambda x: x)
        input_dict = {"messages": [{"role": "user", "content": "hi"}]}
        prepared = adapter._prepare_input(input_dict)
        assert prepared == input_dict
