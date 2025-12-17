# langchain-runner

Run your LangChain/LangGraph agents autonomously with webhooks, cron, and HTTP triggers.

[![PyPI version](https://badge.fury.io/py/langchain-runner.svg)](https://badge.fury.io/py/langchain-runner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Installation

```bash
pip install langchain-runner
```

## Quick Start

```python
from langchain_runner import Runner
from langchain.agents import create_agent

# Your LangChain agent (LangChain v1+)
agent = create_agent(
    model="anthropic:claude-sonnet-4-5-20250929",  # or "openai:gpt-4.1"
    tools=[],
    system_prompt="You are a helpful assistant.",
)

# Wrap it with Runner
runner = Runner(agent)

@runner.cron("0 9 * * *")
async def morning_report():
    return "Generate the daily sales report"

@runner.webhook("/stripe")
async def on_payment(payload: dict):
    return f"Process payment: {payload['type']}"

@runner.trigger("/ask")
async def ask(question: str):
    return question

runner.serve()
```

## Features

- **Webhook triggers** - Receive external webhooks (GitHub, Stripe, Slack, etc.)
- **Cron triggers** - Schedule agent runs with cron expressions
- **HTTP triggers** - Simple POST endpoints to invoke your agent
- **Background execution** - Agent runs don't block HTTP responses
- **Run tracking** - Monitor agent run status and results
- **Zero config** - Works out of the box with sensible defaults

## Endpoints

Once your runner is serving, you get these endpoints automatically:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/triggers` | GET | List registered triggers |
| `/trigger/{name}` | POST | Invoke a registered trigger |
| `/webhook/{name}` | POST | Receive webhook payload |
| `/runs` | GET | List recent runs |
| `/runs/{id}` | GET | Get run status and result |

## Triggers

### HTTP Trigger

Simple endpoint to invoke your agent with a custom message:

```python
@runner.trigger("/ask")
async def ask(question: str):
    return question
```

```bash
curl -X POST http://localhost:8000/trigger/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the weather today?"}'
```

Response:
```json
{"run_id": "abc123", "status": "pending", "message": "Run started"}
```

### Webhook Trigger

Receive webhooks from external services (GitHub, Stripe, Clerk, etc.) and transform them into agent inputs:

```python
@runner.webhook("/clerk")
async def on_clerk_user(payload: dict):
    event_type = payload.get("type")
    user = payload.get("data", {})
    return f"Handle Clerk event '{event_type}' for user: {user.get('email_addresses', [{}])[0].get('email_address')}"
```

**Your webhook URL will be:**
```
https://<your-domain>/webhook/<name>
```

For the example above: `https://your-server.com/webhook/clerk`

#### Setting Up Webhooks

**1. For local development, expose your server with ngrok:**

```bash
# Start your runner
python my_agent.py  # Starts server on port 8000

# In another terminal, expose it
ngrok http 8000
# Output: https://abc123.ngrok.io -> http://localhost:8000
```

Your webhook URL is now: `https://abc123.ngrok.io/webhook/clerk`

**2. Configure the external service (example: Clerk):**

1. Go to your Clerk Dashboard → Webhooks
2. Click "Add Endpoint"
3. Enter your webhook URL: `https://abc123.ngrok.io/webhook/clerk`
4. Select events to subscribe to: `user.created`, `user.updated`, etc.
5. Save the endpoint

**3. For production**, deploy your runner to a cloud provider and use that URL:

```
https://my-agent.railway.app/webhook/clerk
```

### Cron Trigger

Schedule agent runs with cron expressions:

```python
@runner.cron("0 9 * * *")  # Every day at 9am
async def daily_summary():
    return "Generate daily standup summary"

@runner.cron("0 9 * * 1-5")  # Weekdays at 9am
async def weekday_task():
    return "Process weekday reports"

@runner.cron("*/15 * * * *")  # Every 15 minutes
async def check_alerts():
    return "Check for new alerts"
```

## Creating Your Agent

### LangChain Agents (Recommended)

The recommended way to create agents is using LangChain v1+'s `create_agent` function:

```python
from langchain.agents import create_agent

# Using model string (simple)
agent = create_agent(
    model="anthropic:claude-sonnet-4-5-20250929",  # or "openai:gpt-4.1"
    tools=[my_tool],
    system_prompt="You are a helpful assistant.",
)
runner = Runner(agent)
```

You can also use a model instance for more control:

```python
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0,
    max_tokens=4096,
)
agent = create_agent(
    model=model,
    tools=[my_tool],
    system_prompt="You are a helpful assistant.",
)
runner = Runner(agent)
```

### Custom Agents (Advanced)

For advanced use cases, you can pass any callable that accepts and returns the LangGraph message format:

```python
# Async callable
async def my_agent(input: dict) -> dict:
    messages = input["messages"]
    # Your custom logic...
    return {"messages": [..., {"role": "assistant", "content": "response"}]}

runner = Runner(my_agent)

# Sync callable (runs in thread pool automatically)
def my_sync_agent(input: dict) -> dict:
    return {"messages": [{"role": "assistant", "content": "Hello!"}]}

runner = Runner(my_sync_agent)
```

## Configuration

```python
runner = Runner(
    agent,
    name="my-agent",  # Optional name (shown in /health)
    max_runs=1000,    # Max runs to keep in memory
)

runner.serve(
    host="0.0.0.0",
    port=8000,
)
```

Environment variables:
- `LANGCHAIN_RUNNER_HOST` - Host to bind to (default: `0.0.0.0`)
- `LANGCHAIN_RUNNER_PORT` - Port to bind to (default: `8000`)

## CLI

```bash
# Run your agent file
langchain-runner serve my_agent.py

# Or use Python module
python -m langchain_runner serve my_agent.py

# With custom host/port
langchain-runner serve my_agent.py --host 127.0.0.1 --port 3000
```

## Run Tracking

Every agent invocation returns a `run_id` immediately. Use it to track progress:

```python
import requests

# Invoke trigger
response = requests.post(
    "http://localhost:8000/trigger/ask",
    json={"question": "Hello"}
)
run_id = response.json()["run_id"]

# Check status
status = requests.get(f"http://localhost:8000/runs/{run_id}")
print(status.json())
```

Response:
```json
{
  "run_id": "abc123",
  "status": "completed",
  "trigger_type": "http",
  "trigger_name": "ask",
  "input": "Hello",
  "result": {"messages": [...]},
  "final_message": "Here's the answer...",
  "created_at": "2025-01-01T00:00:00Z",
  "completed_at": "2025-01-01T00:00:05Z"
}
```

## Using MCP Tools

The recommended way to add tools to your agent is via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). MCP provides a standard way to connect AI agents to external tools and data sources.

First, install the MCP adapter:

```bash
pip install langchain-runner[mcp]
```

Then connect to MCP servers and use their tools:

```python
import asyncio
from langchain_runner import Runner
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async def create_mcp_agent():
    # Connect to MCP servers
    client = MultiServerMCPClient({
        "tools": {
            "transport": "streamable_http",
            "url": "https://your-mcp-server.com/mcp",
        },
        # You can connect to multiple servers
        "local_tools": {
            "transport": "stdio",
            "command": "python",
            "args": ["./my_mcp_server.py"],
        },
    })
    
    # Get tools from all connected servers
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools from MCP servers")
    
    # Create agent with MCP tools
    agent = create_agent(
        model="anthropic:claude-sonnet-4-5-20250929",
        tools=tools,
        system_prompt="You are a helpful assistant with access to external tools.",
    )
    
    return agent

# Create agent at startup
agent = asyncio.get_event_loop().run_until_complete(create_mcp_agent())
runner = Runner(agent, name="mcp-agent")

@runner.webhook("/process")
async def on_process(payload: dict):
    return f"Process this request: {payload}"

if __name__ == "__main__":
    runner.serve()
```

## Example: Full Setup

```python
import asyncio
from langchain_runner import Runner
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async def setup_agent():
    # Connect to your MCP server with tools (Notion, Slack, etc.)
    client = MultiServerMCPClient({
        "tools": {
            "transport": "streamable_http",
            "url": "https://your-mcp-server.com/mcp",
        }
    })
    tools = await client.get_tools()
    
    return create_agent(
        model="anthropic:claude-sonnet-4-5-20250929",
        tools=tools,
        system_prompt="You are a helpful assistant.",
    )

agent = asyncio.get_event_loop().run_until_complete(setup_agent())
runner = Runner(agent, name="my-assistant")

# HTTP trigger
@runner.trigger("/chat")
async def chat(message: str):
    return message

# Webhook triggers
@runner.webhook("/slack")
async def on_slack(payload: dict):
    event = payload.get("event", {})
    return f"Respond to: {event.get('text', '')}"

@runner.webhook("/github")
async def on_github(payload: dict):
    pr = payload.get("pull_request", {})
    return f"Review PR: {pr.get('title', 'Unknown')}"

# Cron triggers
@runner.cron("0 9 * * 1-5")  # Weekdays at 9am
async def daily_standup():
    return "Generate daily standup summary"

@runner.cron("0 18 * * 5")  # Friday at 6pm
async def weekly_report():
    return "Generate weekly report"

if __name__ == "__main__":
    runner.serve()
```

## Philosophy

langchain-runner follows the same philosophy as [fastapi-mcp](https://github.com/tadata-org/fastapi-mcp):

- **Minimal configuration** - Works out of the box
- **Decorator-based API** - Feels natural to Python developers
- **"Just works"** - Focus on your agent, not the infrastructure

## License

MIT
