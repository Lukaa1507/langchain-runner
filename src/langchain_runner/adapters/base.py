"""Adapter for invoking agents."""

from __future__ import annotations

import asyncio
from typing import Any


class AgentAdapter:
    """Wraps any agent (LangGraph graph or callable) for invocation."""

    def __init__(self, agent: Any) -> None:
        self.agent = agent
        self._has_ainvoke = hasattr(agent, "ainvoke")
        self._has_invoke = hasattr(agent, "invoke")
        self._is_callable = callable(agent) and not self._has_invoke

    def _prepare_input(self, input: str | dict) -> dict:
        """Wrap string input in messages format."""
        if isinstance(input, str):
            return {"messages": [{"role": "user", "content": input}]}
        return input

    async def invoke(self, input: str | dict) -> Any:
        """Invoke the agent."""
        prepared = self._prepare_input(input)

        if self._has_ainvoke:
            return await self.agent.ainvoke(prepared)
        if self._has_invoke:
            return await asyncio.to_thread(self.agent.invoke, prepared)
        if self._is_callable:
            if asyncio.iscoroutinefunction(self.agent):
                return await self.agent(prepared)
            return await asyncio.to_thread(self.agent, prepared)

        raise TypeError(f"Cannot invoke agent of type {type(self.agent).__name__}")

    def extract_final_message(self, result: Any) -> str | None:
        """Extract the final message from agent result."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            # Check messages format (LangGraph standard)
            if "messages" in result and result["messages"]:
                last = result["messages"][-1]
                if hasattr(last, "content"):
                    return str(last.content)
                if isinstance(last, dict) and "content" in last:
                    return str(last["content"])
            # Try common response keys
            for key in ("content", "response", "output"):
                if key in result:
                    return str(result[key])
        return str(result) if result else None


def create_adapter(agent: Any) -> AgentAdapter:
    """Create an adapter for the given agent."""
    return AgentAdapter(agent)
