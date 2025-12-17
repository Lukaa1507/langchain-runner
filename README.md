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
    model="openai:gpt-4o",  # or "anthropic:claude-sonnet-4"
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

Transform incoming webhook payloads into agent inputs:

```python
@runner.webhook("/github")
async def on_github(payload: dict):
    pr = payload.get("pull_request", {})
    return f"Review this PR: {pr.get('title')}"
```

```bash
# GitHub sends a webhook to http://your-server:8000/webhook/github
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

## Supported Agents

langchain-runner works with:

### 1. LangChain Agents (Recommended - LangChain v1+)

```python
from langchain.agents import create_agent

# Using model string (simple)
agent = create_agent(
    model="openai:gpt-4o",
    tools=[my_tool],
    system_prompt="You are a helpful assistant.",
)
runner = Runner(agent)

# Using model instance (more control)
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_agent(
    model=model,
    tools=[my_tool],
    system_prompt="You are a helpful assistant.",
)
runner = Runner(agent)
```

### 2. Async Callable

```python
async def my_agent(input: dict) -> dict:
    messages = input["messages"]
    # Process messages...
    return {"messages": [..., {"role": "assistant", "content": "response"}]}

runner = Runner(my_agent)
```

### 3. Sync Callable (runs in thread pool)

```python
def my_sync_agent(input: dict) -> dict:
    return {"response": "Hello!"}

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

## Example: Full Setup

```python
from langchain_runner import Runner
from langchain.agents import create_agent

# Define tools
def search(query: str) -> str:
    """Search the web."""
    return f"Results for: {query}"

def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

# Create agent (LangChain v1+)
agent = create_agent(
    model="openai:gpt-4o",
    tools=[search, get_weather],
    system_prompt="You are a helpful assistant.",
)

# Create runner
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
