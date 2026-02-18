#!/usr/bin/env python3
"""iconfucius agent skill CLI — thin wrapper around iconfucius.skills.executor.

Usage:
    iconfucius-skill.py <command> [--key value ...]
    iconfucius-skill.py help

All output is JSON to stdout. Interactive/status messages go to stderr.
"""

import json
import sys


def _parse_args(argv: list[str]) -> tuple[str, dict]:
    """Parse command and --key value pairs from argv.

    Returns:
        (command, {key: value})
    """
    if not argv:
        return "help", {}

    command = argv[0]
    args = {}
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            key = token.lstrip("-")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                value = argv[i + 1]
                # Parse booleans and integers
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                else:
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                args[key] = value
                i += 2
            else:
                # Flag without value = True
                args[key] = True
                i += 1
        else:
            i += 1

    return command, args


def _print_help() -> dict:
    """Return help information as structured data."""
    from iconfucius.skills.definitions import TOOLS

    tools = []
    for t in TOOLS:
        params = list(t["input_schema"].get("properties", {}).keys())
        tools.append({
            "name": t["name"],
            "description": t["description"],
            "parameters": params,
            "requires_confirmation": t["requires_confirmation"],
        })

    return {
        "status": "ok",
        "message": "iconfucius agent skill",
        "usage": "iconfucius-skill.py <command> [--key value ...]",
        "tools": tools,
    }


def main():
    # Load .env if present
    try:
        from dotenv import load_dotenv
        from pathlib import Path

        load_dotenv(dotenv_path=Path.cwd() / ".env", override=True)
    except ImportError:
        pass

    command, args = _parse_args(sys.argv[1:])

    if command == "help":
        result = _print_help()
    else:
        from iconfucius.skills.executor import execute_tool

        result = execute_tool(command, args)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
