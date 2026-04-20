"""Tests for the advisory agent with tool-call status reporting."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iconfucius.rasa.sub_agents.advisory_agent.advisory_agent import (
    TOOL_LABELS,
    AdvisoryAgent,
)


class TestToolLabels:
    """Tests for the TOOL_LABELS dictionary."""

    def test_all_labels_are_strings(self):
        for name, label in TOOL_LABELS.items():
            assert isinstance(name, str)
            assert isinstance(label, str)

    def test_all_labels_end_with_ellipsis(self):
        for name, label in TOOL_LABELS.items():
            assert label.endswith("..."), f"Label for {name} should end with '...'"

    def test_expected_tools_present(self):
        expected = {
            "wallet_balance", "token_price", "memory_read_strategy",
            "memory_read_learnings", "memory_read_trades",
            "memory_read_balances", "token_lookup", "token_discover",
            "bot_list", "public_balance", "account_lookup",
            "setup_and_operational_status", "check_update",
            "wallet_monitor", "how_to_fund_wallet", "security_status",
        }
        assert set(TOOL_LABELS.keys()) == expected

    def test_label_count(self):
        assert len(TOOL_LABELS) == 16


class TestAdvisoryAgent:
    """Tests for AdvisoryAgent tool_status reporting."""

    def _make_agent(self):
        """Create an AdvisoryAgent with mocked parent init."""
        with patch.object(AdvisoryAgent, "__init__", lambda self, *a, **kw: None):
            agent = AdvisoryAgent.__new__(AdvisoryAgent)
            agent._output_channel = None
            agent._recipient_id = None
            return agent

    @pytest.mark.asyncio
    async def test_execute_tool_call_sends_status(self):
        """_execute_tool_call sends tool_status before calling super."""
        agent = self._make_agent()
        output_channel = AsyncMock()
        agent._output_channel = output_channel
        agent._recipient_id = "user-42"

        # Mock the parent's _execute_tool_call
        mock_result = MagicMock()
        with patch(
            "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent._execute_tool_call",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await agent._execute_tool_call("wallet_balance", {})

        # Verify tool_status was sent
        output_channel.send_custom_json.assert_called_once_with(
            "user-42",
            {
                "type": "tool_status",
                "tool": "wallet_balance",
                "text": "Checking wallet balance...",
            },
        )
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_execute_tool_call_unknown_tool_fallback_label(self):
        """Unknown tools get a 'Running <name>...' fallback label."""
        agent = self._make_agent()
        output_channel = AsyncMock()
        agent._output_channel = output_channel
        agent._recipient_id = "user-42"

        mock_result = MagicMock()
        with patch(
            "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent._execute_tool_call",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await agent._execute_tool_call("some_unknown_tool", {"x": 1})

        call_args = output_channel.send_custom_json.call_args[0]
        assert call_args[1]["text"] == "Running some_unknown_tool..."

    @pytest.mark.asyncio
    async def test_execute_tool_call_no_output_channel(self):
        """No status sent when output_channel is None."""
        agent = self._make_agent()
        agent._output_channel = None
        agent._recipient_id = "user-42"

        mock_result = MagicMock()
        with patch(
            "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent._execute_tool_call",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await agent._execute_tool_call("wallet_balance", {})

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_execute_tool_call_no_recipient_id(self):
        """No status sent when recipient_id is None."""
        agent = self._make_agent()
        output_channel = AsyncMock()
        agent._output_channel = output_channel
        agent._recipient_id = None

        mock_result = MagicMock()
        with patch(
            "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent._execute_tool_call",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await agent._execute_tool_call("wallet_balance", {})

        output_channel.send_custom_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_sets_and_clears_channel(self):
        """send_message sets _output_channel/_recipient_id and clears on exit."""
        agent = self._make_agent()
        output_channel = AsyncMock()

        agent_input = MagicMock()
        agent_input.recipient_id = "user-99"

        mock_output = MagicMock()
        with patch(
            "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent.send_message",
            new_callable=AsyncMock,
            return_value=mock_output,
        ) as mock_super:
            # During super().send_message, verify state is set
            async def check_state(ai, oc=None):
                assert agent._output_channel is output_channel
                assert agent._recipient_id == "user-99"
                return mock_output

            mock_super.side_effect = check_state

            result = await agent.send_message(agent_input, output_channel)

        # After send_message, state is cleared
        assert agent._output_channel is None
        assert agent._recipient_id is None
        assert result == mock_output

    @pytest.mark.asyncio
    async def test_send_message_clears_on_exception(self):
        """State is cleaned up even if super().send_message raises."""
        agent = self._make_agent()
        output_channel = AsyncMock()

        agent_input = MagicMock()
        agent_input.recipient_id = "user-99"

        with patch(
            "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent.send_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM error"),
        ):
            with pytest.raises(RuntimeError, match="LLM error"):
                await agent.send_message(agent_input, output_channel)

        assert agent._output_channel is None
        assert agent._recipient_id is None

    @pytest.mark.asyncio
    async def test_each_known_tool_gets_correct_label(self):
        """Each tool in TOOL_LABELS gets its specific label text."""
        agent = self._make_agent()
        output_channel = AsyncMock()
        agent._output_channel = output_channel
        agent._recipient_id = "user-1"

        mock_result = MagicMock()

        for tool_name, expected_label in TOOL_LABELS.items():
            output_channel.reset_mock()
            with patch(
                "rasa.agents.protocol.mcp.mcp_open_agent.MCPOpenAgent._execute_tool_call",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                await agent._execute_tool_call(tool_name, {})

            sent_data = output_channel.send_custom_json.call_args[0][1]
            assert sent_data["text"] == expected_label, (
                f"Tool {tool_name}: expected '{expected_label}', got '{sent_data['text']}'"
            )
