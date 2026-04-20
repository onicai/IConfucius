"""Tests for iconfucius.mcp_server — MCP HTTP server for tool execution."""

import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest

from iconfucius.mcp_server import MCP_DEFAULT_PORT, create_mcp_server, create_asgi_app


def _list_tools_req():
    """Create a proper ListToolsRequest."""
    return ListToolsRequest(method="tools/list")


def _call_tool_req(name, arguments=None):
    """Create a proper CallToolRequest."""
    return CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name=name, arguments=arguments or {}),
    )


def _get_handler(server, request_cls):
    """Look up a registered handler by MCP request class."""
    handler = server.request_handlers.get(request_cls)
    assert handler is not None, f"No handler registered for {request_cls}"
    return handler


class TestMCPDefaultPort:
    """Verify MCP server configuration constants."""

    def test_default_port(self):
        assert MCP_DEFAULT_PORT == 5138


class TestCreateMcpServer:
    """Tests for MCP server factory."""

    def test_returns_server(self):
        server = create_mcp_server()
        assert server is not None
        assert server.name == "iconfucius-tools"

    def test_registers_list_tools_handler(self):
        server = create_mcp_server()
        assert ListToolsRequest in server.request_handlers

    def test_registers_call_tool_handler(self):
        server = create_mcp_server()
        assert CallToolRequest in server.request_handlers

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        """list_tools handler returns all tools from TOOLS."""
        from iconfucius.skills.definitions import TOOLS

        server = create_mcp_server()
        handler = _get_handler(server, ListToolsRequest)

        result = (await handler(_list_tools_req())).root
        assert len(result.tools) == len(TOOLS)

        tool_names = {t.name for t in result.tools}
        expected_names = {t["name"] for t in TOOLS}
        assert tool_names == expected_names

    @pytest.mark.asyncio
    async def test_list_tools_has_descriptions(self):
        """Every tool has a non-empty description."""
        server = create_mcp_server()
        handler = _get_handler(server, ListToolsRequest)
        result = (await handler(_list_tools_req())).root

        for tool in result.tools:
            assert tool.description, f"Tool {tool.name} has no description"

    @pytest.mark.asyncio
    async def test_list_tools_has_input_schema(self):
        """Every tool has an input schema."""
        server = create_mcp_server()
        handler = _get_handler(server, ListToolsRequest)
        result = (await handler(_list_tools_req())).root

        for tool in result.tools:
            assert tool.inputSchema is not None, f"Tool {tool.name} has no inputSchema"

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """call_tool returns JSON result for successful tool execution."""
        fake_result = {"status": "ok", "data": "test_value"}

        with patch("iconfucius.mcp_server.execute_tool", return_value=fake_result):
            server = create_mcp_server()
            handler = _get_handler(server, CallToolRequest)
            result = (await handler(_call_tool_req("wallet_balance"))).root

        assert not result.isError
        assert len(result.content) == 1
        parsed = json.loads(result.content[0].text)
        assert parsed["status"] == "ok"
        assert parsed["data"] == "test_value"

    @pytest.mark.asyncio
    async def test_call_tool_error(self):
        """call_tool sets isError=True for error results."""
        fake_result = {"status": "error", "error": "Something went wrong"}

        with patch("iconfucius.mcp_server.execute_tool", return_value=fake_result):
            server = create_mcp_server()
            handler = _get_handler(server, CallToolRequest)
            result = (await handler(_call_tool_req("wallet_balance"))).root

        assert result.isError is True
        parsed = json.loads(result.content[0].text)
        assert parsed["status"] == "error"

    @pytest.mark.asyncio
    async def test_call_tool_passes_persona(self):
        """call_tool always passes persona_name='iconfucius'."""
        with patch("iconfucius.mcp_server.execute_tool", return_value={"status": "ok"}) as mock_exec:
            server = create_mcp_server()
            handler = _get_handler(server, CallToolRequest)
            _ = await handler(_call_tool_req("token_price", {"query": "ICONFUCIUS"}))

        mock_exec.assert_called_once_with(
            "token_price", {"query": "ICONFUCIUS"}, persona_name="iconfucius",
        )

    @pytest.mark.asyncio
    async def test_call_tool_json_serializes_non_standard_types(self):
        """Results with non-JSON-serializable types use default=str."""
        from datetime import datetime
        fake_result = {"status": "ok", "ts": datetime(2025, 1, 1, 12, 0)}

        with patch("iconfucius.mcp_server.execute_tool", return_value=fake_result):
            server = create_mcp_server()
            handler = _get_handler(server, CallToolRequest)
            result = (await handler(_call_tool_req("wallet_balance"))).root

        parsed = json.loads(result.content[0].text)
        assert "2025" in parsed["ts"]


class TestCreateAsgiApp:
    """Tests for the ASGI app wrapper."""

    def test_returns_starlette_app(self):
        from starlette.applications import Starlette

        server = create_mcp_server()
        app = create_asgi_app(server)
        assert isinstance(app, Starlette)

    def test_app_has_mcp_route(self):
        server = create_mcp_server()
        app = create_asgi_app(server)

        route_paths = [r.path for r in app.routes]
        assert "/mcp" in route_paths
