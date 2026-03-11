from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import async_execute_tool

from .actions_utility import _send_result


class ActionWalletBalance(Action):
    def name(self) -> Text:
        return "action_wallet_balance"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        bot_name = tracker.get_slot("bot_name")
        if bot_name:
            args["bot_name"] = bot_name
        if tracker.get_slot("ckbtc_minter"):
            args["ckbtc_minter"] = True

        _send_result(dispatcher, await async_execute_tool("wallet_balance", args))
        return [
            SlotSet("bot_name", None),
            SlotSet("ckbtc_minter", None),
        ]


class ActionWalletMonitor(Action):
    def name(self) -> Text:
        return "action_wallet_monitor"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(dispatcher, await async_execute_tool("wallet_monitor", {}))
        return []


class ActionPublicBalance(Action):
    def name(self) -> Text:
        return "action_public_balance"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        principal = tracker.get_slot("principal")
        if not principal:
            dispatcher.utter_message(text="Please provide an IC principal.")
            return []
        _send_result(
            dispatcher,
            await async_execute_tool("public_balance", {"principal": principal}),
        )
        return [SlotSet("principal", None)]


class ActionHowToFund(Action):
    def name(self) -> Text:
        return "action_how_to_fund"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(dispatcher, await async_execute_tool("how_to_fund_wallet", {}))
        return []
