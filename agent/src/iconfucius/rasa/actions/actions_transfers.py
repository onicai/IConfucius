from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import async_execute_tool

from .actions_funding import _parse_amount, _parse_bot_target
from .actions_utility import _send_result


class ActionTokenTransfer(Action):
    def name(self) -> Text:
        return "action_token_transfer"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {
            "token_id": tracker.get_slot("token_id"),
            "amount": tracker.get_slot("transfer_amount") or "0",
            "to_address": tracker.get_slot("transfer_to_address"),
        }
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(dispatcher, await async_execute_tool("token_transfer", args))
        return [
            SlotSet("token_query", None),
            SlotSet("token_id", None),
            SlotSet("transfer_amount", None),
            SlotSet("transfer_to_address", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_transfer", None),
        ]


class ActionWalletSend(Action):
    def name(self) -> Text:
        return "action_wallet_send"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {
            "address": tracker.get_slot("send_address"),
        }
        args.update(_parse_amount(tracker.get_slot("send_amount")))

        _send_result(dispatcher, await async_execute_tool("wallet_send", args))
        return [
            SlotSet("send_amount", None),
            SlotSet("send_address", None),
            SlotSet("confirm_send", None),
        ]
