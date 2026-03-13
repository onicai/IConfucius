"""MCP HTTP server exposing iconfucius tools.

Uses the MCP low-level Server API (not FastMCP) because our tools have
pre-built input_schema dicts that don't map to Python function signatures.

All tools from ``TOOLS`` are always exposed.  Access control is handled
by Rasa's ``include_tools`` filter on the sub-agent side.
"""

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolResult, TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount

from iconfucius.skills.definitions import TOOLS
from iconfucius.skills.executor import execute_tool

_log = logging.getLogger(__name__)

MCP_DEFAULT_PORT = 5138


# ------------------------------------------------------------------
# Server factory
# ------------------------------------------------------------------

def create_mcp_server() -> Server:
    """Create an MCP ``Server`` with list_tools / call_tool handlers."""
    server = Server("iconfucius-tools")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["input_schema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> CallToolResult:
        result = await asyncio.to_thread(
            execute_tool, name, arguments, persona_name="iconfucius",
        )
        text = json.dumps(result, default=str)
        is_error = result.get("status") == "error"
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            isError=is_error,
        )

    return server


# ------------------------------------------------------------------
# ASGI app
# ------------------------------------------------------------------

def create_asgi_app(server: Server) -> Starlette:
    """Wrap *server* in a Starlette app serving ``/mcp``."""
    session_manager = StreamableHTTPSessionManager(app=server)

    @asynccontextmanager
    async def _lifespan(app: Starlette):
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/mcp", app=session_manager.handle_request)],
        lifespan=_lifespan,
    )
    return app


# ------------------------------------------------------------------
# Convenience launcher
# ------------------------------------------------------------------

async def start_mcp_server(
    port: int = MCP_DEFAULT_PORT,
) -> tuple[asyncio.Task, uvicorn.Server]:
    """Start the MCP HTTP server as an asyncio task.

    Returns ``(task, uv_server)`` so the caller can shut down via
    ``uv_server.should_exit = True``.
    """
    import socket

    # Check port availability before starting uvicorn, so we can give a
    # clear error message instead of a cryptic traceback.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
    except OSError:
        print(f"\nPort {port} is already in use.")
        print("Another iconfucius MCP server is probably running.\n")
        print(f"Try: ICONFUCIUS_MCP_PORT={port + 1} iconfucius chat --rasa")
        sys.exit(1)

    server = create_mcp_server()
    app = create_asgi_app(server)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    uv_server = uvicorn.Server(config)

    task = asyncio.create_task(uv_server.serve())
    return task, uv_server
