from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import execute_tool

from .actions_utility import _send_result


class ActionTokenLookup(Action):
    def name(self) -> Text:
        return "action_token_lookup"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        query = tracker.get_slot("query")
        if not query:
            dispatcher.utter_message(text="Please provide a token name or ID.")
            return []
        _send_result(
            dispatcher,
            execute_tool("token_lookup", {"query": query}),
        )
        return [SlotSet("query", None)]


class ActionTokenPrice(Action):
    def name(self) -> Text:
        return "action_token_price"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        query = tracker.get_slot("query")
        if not query:
            dispatcher.utter_message(text="Please provide a token name or ID.")
            return []
        _send_result(
            dispatcher,
            execute_tool("token_price", {"query": query}),
        )
        return [SlotSet("query", None)]


class ActionTokenDiscover(Action):
    def name(self) -> Text:
        return "action_token_discover"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        sort_order = tracker.get_slot("sort_order")
        if sort_order:
            args["sort"] = sort_order
        limit = tracker.get_slot("discover_limit")
        if limit is not None:
            args["limit"] = int(limit)

        _send_result(dispatcher, execute_tool("token_discover", args))
        return [
            SlotSet("sort_order", None),
            SlotSet("discover_limit", None),
        ]


class ActionAccountLookup(Action):
    def name(self) -> Text:
        return "action_account_lookup"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        address = tracker.get_slot("address")
        if not address:
            dispatcher.utter_message(text="Please provide an address to look up.")
            return []
        _send_result(
            dispatcher,
            execute_tool("account_lookup", {"address": address}),
        )
        return [SlotSet("address", None)]
