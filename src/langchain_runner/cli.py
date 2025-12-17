"""CLI for langchain-runner."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

from langchain_runner import __version__


def load_runner_from_file(filepath: str):
    """Load a Runner instance from a Python file.

    The file should either:
    1. Have a `runner` variable that is a Runner instance
    2. Have an `app` variable that is a Runner instance
    3. Have a function called `create_runner()` that returns a Runner instance
    """
    from langchain_runner import Runner

    path = Path(filepath).resolve()
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    # Add the file's directory to sys.path for imports
    sys.path.insert(0, str(path.parent))

    # Load the module
    spec = importlib.util.spec_from_file_location("_runner_module", path)
    if not spec or not spec.loader:
        print(f"Error: Could not load module from {filepath}")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Look for runner instance
    for attr_name in ["runner", "app"]:
        if hasattr(module, attr_name):
            obj = getattr(module, attr_name)
            if isinstance(obj, Runner):
                return obj

    # Look for factory function
    if hasattr(module, "create_runner"):
        runner = module.create_runner()
        if isinstance(runner, Runner):
            return runner

    print(
        f"Error: Could not find a Runner instance in {filepath}. "
        "Expected a 'runner' or 'app' variable, or a 'create_runner()' function."
    )
    sys.exit(1)


def cmd_serve(args: argparse.Namespace) -> None:
    """Run the serve command."""
    runner = load_runner_from_file(args.file)

    host = args.host or os.environ.get("LANGCHAIN_RUNNER_HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("LANGCHAIN_RUNNER_PORT", "8000"))

    print(f"Starting langchain-runner v{__version__}")
    print(f"Serving on http://{host}:{port}")
    print(f"Loaded {len(runner.get_triggers())} trigger(s)")

    for trigger in runner.get_triggers():
        print(f"  - {trigger.trigger_type.value}: {trigger.path}")

    runner.serve(host=host, port=port, log_level="info")


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="langchain-runner",
        description="Run LangChain/LangGraph agents with webhooks, cron, and HTTP triggers",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the runner server")
    serve_parser.add_argument(
        "file",
        help="Python file containing the Runner instance",
    )
    serve_parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: 8000)",
    )

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
