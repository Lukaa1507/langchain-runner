"""Basic example of using langchain-runner.

This example demonstrates how to use langchain-runner with a simple
async callable agent. In a real scenario, you would replace this with
your LangGraph agent.

Run with:
    langchain-runner serve examples/basic_agent.py
    # or
    python -m langchain_runner serve examples/basic_agent.py

Then test with:
    curl http://localhost:8000/health
    curl -X POST http://localhost:8000/trigger/ask \\
        -H "Content-Type: application/json" -d '{"question": "Hello!"}'
    curl http://localhost:8000/runs
"""

from langchain_runner import Runner


async def echo_agent(input: dict) -> dict:
    """A simple agent that echoes input - replace with your real agent.

    This follows the LangGraph message format:
    - Input: {"messages": [{"role": "user", "content": "..."}]}
    - Output: {"messages": [..., {"role": "assistant", "content": "..."}]}
    """
    messages = input.get("messages", [])
    user_message = messages[-1].get("content", "") if messages else str(input)
    return {"messages": [*messages, {"role": "assistant", "content": f"Echo: {user_message}"}]}


# Create the runner with your agent
runner = Runner(echo_agent, name="echo-agent")


# ============================================================================
# HTTP Triggers - Simple POST endpoints
# ============================================================================


@runner.trigger("/ask")
async def ask(question: str):
    """Ask the agent a question.

    Example:
        curl -X POST http://localhost:8000/trigger/ask \
            -H "Content-Type: application/json" \
            -d '{"question": "What is the meaning of life?"}'
    """
    return question


@runner.trigger("/analyze")
async def analyze(text: str, style: str = "concise"):
    """Analyze text with a specified style.

    Example:
        curl -X POST http://localhost:8000/trigger/analyze \
            -H "Content-Type: application/json" \
            -d '{"text": "Some text to analyze", "style": "detailed"}'
    """
    return f"Analyze this text in a {style} style: {text}"


# ============================================================================
# Webhook Triggers - Receive payloads from external services
# ============================================================================


@runner.webhook("/github")
async def on_github(payload: dict):
    """Handle GitHub webhook events.

    Configure GitHub to send webhooks to: http://your-server:8000/webhook/github

    Example payload for PR opened:
        {"action": "opened", "pull_request": {"title": "Fix bug", "body": "..."}}
    """
    action = payload.get("action", "unknown")
    pr = payload.get("pull_request", {})
    if pr:
        return f"GitHub: Review PR '{pr.get('title', 'Unknown')}' - {action}"

    repo = payload.get("repository", {}).get("full_name", "unknown")
    return f"GitHub event: {action} on {repo}"


@runner.webhook("/stripe")
async def on_stripe(payload: dict):
    """Handle Stripe webhook events.

    Configure Stripe to send webhooks to: http://your-server:8000/webhook/stripe

    Example payload:
        {"type": "payment_intent.succeeded", "data": {"object": {"amount": 2000}}}
    """
    event_type = payload.get("type", "unknown")
    data = payload.get("data", {}).get("object", {})

    if "payment" in event_type:
        amount = data.get("amount", 0) / 100  # Stripe amounts are in cents
        return f"Process Stripe payment: ${amount:.2f} - {event_type}"

    return f"Handle Stripe event: {event_type}"


# ============================================================================
# Cron Triggers - Scheduled runs
# ============================================================================


@runner.cron("* * * * *")  # Every minute (for demo purposes)
async def heartbeat():
    """Run every minute - useful for monitoring.

    In production, you'd use less frequent schedules like:
    - "0 * * * *" - Every hour
    - "0 9 * * *" - Daily at 9am
    - "0 9 * * 1" - Every Monday at 9am
    """
    return "Perform periodic health check and monitoring"


@runner.cron("0 9 * * *")  # Daily at 9am
async def daily_summary():
    """Generate daily summary at 9am."""
    return "Generate daily standup summary from yesterday's activities"


if __name__ == "__main__":
    # Start the server when run directly
    print("Starting langchain-runner example...")
    print("Try these commands:")
    print("  curl http://localhost:8000/health")
    print("  curl -X POST http://localhost:8000/trigger/ask \\")
    print('       -H "Content-Type: application/json" -d \'{"question": "Hello!"}\'')
    print("  curl http://localhost:8000/runs")
    runner.serve()
