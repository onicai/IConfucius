from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import execute_tool

from .actions_funding import _parse_amount, _parse_bot_target
from .actions_utility import _send_result


class ActionResolveToken(Action):
    def name(self) -> Text:
        return "action_resolve_token"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        query = tracker.get_slot("token_query")
        if not query:
            dispatcher.utter_message(text="Please provide a token name or ID.")
            return []

        result = execute_tool("token_lookup", {"query": query})
        if result.get("status") == "ok":
            match = result.get("known_match")
            if match:
                token_id = match["id"]
                name = match.get("name", token_id)
                dispatcher.utter_message(
                    text=f"Resolved '{query}' to {name} ({token_id})"
                )
                return [SlotSet("token_id", token_id)]

            # Multiple results — show them and clear token_query for re-collection
            display = result.get("display", "")
            if display:
                dispatcher.utter_message(text=display)
            dispatcher.utter_message(
                text="Please specify which token by ID."
            )
            return [
                SlotSet("token_id", None),
                SlotSet("token_query", None),
            ]

        dispatcher.utter_message(
            text=result.get("error", f"Token not found: {query}")
        )
        return [
            SlotSet("token_id", None),
            SlotSet("token_query", None),
        ]


class ActionTradeBuy(Action):
    def name(self) -> Text:
        return "action_trade_buy"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {"token_id": tracker.get_slot("token_id")}
        args.update(_parse_amount(tracker.get_slot("trade_amount")))
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(dispatcher, execute_tool("trade_buy", args))
        return [
            SlotSet("token_query", None),
            SlotSet("token_id", None),
            SlotSet("trade_amount", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_trade", None),
        ]


class ActionTradeSell(Action):
    def name(self) -> Text:
        return "action_trade_sell"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {"token_id": tracker.get_slot("token_id")}
        args.update(_parse_amount(tracker.get_slot("trade_amount")))
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(dispatcher, execute_tool("trade_sell", args))
        return [
            SlotSet("token_query", None),
            SlotSet("token_id", None),
            SlotSet("trade_amount", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_trade", None),
        ]
