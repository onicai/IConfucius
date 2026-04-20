from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import async_execute_tool

from .actions_funding import _fmt_trade_amount, _parse_amount, _parse_bot_target
from .actions_utility import _send_result

DEFAULT_PERSONA = "iconfucius"


def _persona(tracker: Tracker) -> str:
    return tracker.get_slot("persona_key") or DEFAULT_PERSONA


class ActionResolveToken(Action):
    def name(self) -> Text:
        return "action_resolve_token"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        query = tracker.get_slot("token_query")
        if not query:
            dispatcher.utter_message(text="Please provide a token name or ID.")
            return []

        result = await async_execute_tool("token_lookup", {"query": query})
        if result.get("status") == "ok":
            match = result.get("known_match")
            if match:
                token_id = match["id"]
                token_name = match.get("name") or match.get("ticker") or token_id
                return [
                    SlotSet("token_id", token_id),
                    SlotSet("token_name", token_name),
                ]

            # Multiple results — show them and clear token_query for re-collection
            display = result.get("display", "")
            if display:
                dispatcher.utter_message(text=display)
            dispatcher.utter_message(
                text="Please specify which token by ID."
            )
            return [
                SlotSet("token_id", None),
                SlotSet("token_name", None),
                SlotSet("token_query", None),
            ]

        dispatcher.utter_message(
            text=result.get("error", f"Token not found: {query}")
        )
        return [
            SlotSet("token_id", None),
            SlotSet("token_name", None),
            SlotSet("token_query", None),
        ]


class ActionFormatTradeBuyConfirm(Action):
    def name(self) -> Text:
        return "action_format_trade_buy_confirm"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        raw = tracker.get_slot("trade_amount")
        return [SlotSet("trade_display", _fmt_trade_amount(raw))]


class ActionFormatTradeSellConfirm(Action):
    def name(self) -> Text:
        return "action_format_trade_sell_confirm"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        raw = (tracker.get_slot("trade_amount") or "").strip()
        if not raw:
            display = "?"
        elif raw.lower() == "all" or raw.startswith("$"):
            display = raw
        else:
            display = f"{raw} tokens"
        return [SlotSet("trade_display", display)]


class ActionTradeBuy(Action):
    def name(self) -> Text:
        return "action_trade_buy"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {"token_id": tracker.get_slot("token_id")}
        args.update(_parse_amount(tracker.get_slot("trade_amount")))
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(
            dispatcher,
            await async_execute_tool("trade_buy", args, persona_name=_persona(tracker)),
        )
        return [
            SlotSet("token_query", None),
            SlotSet("token_id", None),
            SlotSet("token_name", None),
            SlotSet("trade_amount", None),
            SlotSet("trade_display", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_trade", None),
        ]


class ActionTradeSell(Action):
    def name(self) -> Text:
        return "action_trade_sell"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {"token_id": tracker.get_slot("token_id")}
        args.update(_parse_amount(tracker.get_slot("trade_amount")))
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(
            dispatcher,
            await async_execute_tool("trade_sell", args, persona_name=_persona(tracker)),
        )
        return [
            SlotSet("token_query", None),
            SlotSet("token_id", None),
            SlotSet("token_name", None),
            SlotSet("trade_amount", None),
            SlotSet("trade_display", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_trade", None),
        ]
