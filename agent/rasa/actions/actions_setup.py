from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import async_execute_tool

from .actions_utility import _send_result


class ActionInit(Action):
    def name(self) -> Text:
        return "action_init"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        num_bots = tracker.get_slot("setup_num_bots")
        if num_bots is not None:
            args["num_bots"] = int(num_bots)
        if tracker.get_slot("setup_force"):
            args["force"] = True

        _send_result(dispatcher, await async_execute_tool("init", args))
        return [
            SlotSet("setup_num_bots", None),
            SlotSet("setup_force", None),
            SlotSet("confirm_setup", None),
        ]


class ActionWalletCreate(Action):
    def name(self) -> Text:
        return "action_wallet_create"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        if tracker.get_slot("setup_force"):
            args["force"] = True

        _send_result(dispatcher, await async_execute_tool("wallet_create", args))
        return [
            SlotSet("setup_force", None),
            SlotSet("confirm_setup", None),
        ]


class ActionSetBotCount(Action):
    def name(self) -> Text:
        return "action_set_bot_count"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        num_bots = tracker.get_slot("setup_num_bots")
        if num_bots is not None:
            args["num_bots"] = int(num_bots)
        if tracker.get_slot("setup_force"):
            args["force"] = True

        _send_result(dispatcher, await async_execute_tool("set_bot_count", args))
        return [
            SlotSet("setup_num_bots", None),
            SlotSet("setup_force", None),
            SlotSet("confirm_setup", None),
        ]
