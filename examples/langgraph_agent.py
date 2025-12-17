"""Example using langchain-runner with a LangChain agent.

This example shows how to use langchain-runner with a LangChain v1 agent.
You'll need to install langchain and set up your LLM credentials.

Install dependencies:
    pip install langchain-runner[mcp] langchain langchain-anthropic

Set environment variable:
    export ANTHROPIC_API_KEY=your-key-here

Run:
    langchain-runner serve examples/langgraph_agent.py
"""

from langchain_runner import Runner

# ============================================================================
# OPTION 1: Using LangChain v1 create_agent with MCP Tools (RECOMMENDED)
# ============================================================================
#
# import asyncio
# from langchain.agents import create_agent
# from langchain_mcp_adapters.client import MultiServerMCPClient
#
# async def create_mcp_agent():
#     # Connect to MCP server(s) that provide your tools
#     client = MultiServerMCPClient({
#         "tools": {
#             "transport": "streamable_http",
#             "url": "https://your-mcp-server.com/mcp",
#         }
#     })
#     tools = await client.get_tools()
#
#     # Create the agent with model string
#     # Supported formats: "anthropic:claude-sonnet-4-5-20250929", "openai:gpt-4.1", etc.
#     return create_agent(
#         model="anthropic:claude-sonnet-4-5-20250929",
#         tools=tools,
#         system_prompt="You are a helpful assistant with access to external tools.",
#     )
#
# agent = asyncio.get_event_loop().run_until_complete(create_mcp_agent())

# ============================================================================
# OPTION 2: Using explicit model instance (more control)
# ============================================================================
#
# from langchain.agents import create_agent
# from langchain_anthropic import ChatAnthropic
#
# model = ChatAnthropic(
#     model="claude-sonnet-4-5-20250929",
#     temperature=0,
#     max_tokens=4096,
# )
#
# agent = create_agent(
#     model=model,
#     tools=tools,  # From MCP or custom tools
#     system_prompt="You are a helpful assistant.",
# )

# ============================================================================
# OPTION 3: With middleware (LangChain v1 feature)
# ============================================================================
#
# from langchain.agents import create_agent
# from langchain.agents.middleware import (
#     PIIMiddleware,
#     SummarizationMiddleware,
# )
#
# agent = create_agent(
#     model="anthropic:claude-sonnet-4-5-20250929",
#     tools=tools,  # From MCP
#     system_prompt="You are a helpful assistant.",
#     middleware=[
#         PIIMiddleware("email", strategy="redact", apply_to_input=True),
#         SummarizationMiddleware(model="anthropic:claude-sonnet-4-5-20250929", trigger={"tokens": 500}),
#     ],
# )

# ============================================================================
# For this example, we use a mock agent (no API keys needed)
# Replace with the real agent above when deploying
# ============================================================================


async def mock_agent(input: dict) -> dict:
    """Mock agent for demonstration - replace with real LangChain agent."""
    messages = input.get("messages", [])
    user_msg = messages[-1]["content"] if messages else "No message"

    return {
        "messages": [
            *messages,
            {"role": "assistant", "content": f"Agent processed: {user_msg}"},
        ]
    }


# Create the runner
runner = Runner(mock_agent, name="my-langchain-agent")


@runner.trigger("/chat")
async def chat(message: str):
    """Chat with the agent."""
    return message


@runner.trigger("/search")
async def search_query(query: str):
    """Search for something."""
    return f"Search the web for: {query}"


@runner.webhook("/slack")
async def on_slack(payload: dict):
    """Handle Slack events.

    Slack sends events like:
    {
        "event": {
            "type": "message",
            "text": "Hello bot",
            "user": "U123456"
        }
    }
    """
    event = payload.get("event", {})
    text = event.get("text", "")
    user = event.get("user", "unknown")
    return f"Respond to Slack message from {user}: {text}"


@runner.webhook("/github")
async def on_github(payload: dict):
    """Handle GitHub webhook events.

    GitHub sends events like:
    {
        "action": "opened",
        "pull_request": {"title": "...", "body": "..."}
    }
    """
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    if pr:
        return f"Review this pull request: {pr.get('title', 'Unknown PR')}"
    return f"Handle GitHub event: {action}"


@runner.cron("0 9 * * 1-5")  # Weekdays at 9am
async def standup_reminder():
    """Send standup reminder on weekdays."""
    return "Generate the daily standup summary for the team."


@runner.cron("0 18 * * 5")  # Friday at 6pm
async def weekly_summary():
    """Generate weekly summary on Fridays."""
    return "Generate a summary of this week's accomplishments and next week's priorities."


if __name__ == "__main__":
    runner.serve()
