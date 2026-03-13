"""Advisory agent with tool-call status reporting via output_channel."""
from __future__ import annotations

from typing import Any, Dict, Optional

from rasa.agents.protocol.mcp.mcp_open_agent import MCPOpenAgent
from rasa.agents.schemas import AgentInput, AgentOutput, AgentToolResult
from rasa.core.channels.channel import OutputChannel

TOOL_LABELS = {
    "wallet_balance": "Checking wallet balance...",
    "token_price": "Checking token price...",
    "memory_read_strategy": "Reading trading strategy...",
    "memory_read_learnings": "Reading trading learnings...",
    "memory_read_trades": "Reading trade history...",
    "memory_read_balances": "Reading balance history...",
    "token_lookup": "Looking up token...",
    "token_discover": "Discovering tokens...",
    "bot_list": "Listing bots...",
    "public_balance": "Checking public balance...",
    "account_lookup": "Looking up account...",
    "setup_and_operational_status": "Checking status...",
    "check_update": "Checking for updates...",
    "wallet_monitor": "Checking wallet monitor...",
    "how_to_fund_wallet": "Getting funding instructions...",
    "security_status": "Checking security status...",
}


class AdvisoryAgent(MCPOpenAgent):
    """Advisory agent with tool-call status reporting via output_channel.

    Overrides ``_execute_tool_call`` to send a ``tool_status`` custom event
    through the output channel before each tool execution, so the CLI can
    update the spinner with a user-friendly label.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._output_channel: Optional[OutputChannel] = None
        self._recipient_id: Optional[str] = None

    async def send_message(
        self,
        agent_input: AgentInput,
        output_channel: Optional[OutputChannel] = None,
    ) -> AgentOutput:
        self._output_channel = output_channel
        self._recipient_id = agent_input.recipient_id
        try:
            return await super().send_message(agent_input, output_channel)
        finally:
            self._output_channel = None
            self._recipient_id = None

    async def _execute_tool_call(
        self, tool_name: str, arguments: Dict[str, Any],
    ) -> AgentToolResult:
        if self._output_channel and self._recipient_id:
            label = TOOL_LABELS.get(tool_name, f"Running {tool_name}...")
            await self._output_channel.send_custom_json(
                self._recipient_id,
                {"type": "tool_status", "tool": tool_name, "text": label},
            )
        return await super()._execute_tool_call(tool_name, arguments)
