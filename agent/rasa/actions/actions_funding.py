from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import execute_tool

from .actions_utility import _send_result


def _parse_bot_target(bot_target: str | None) -> dict[str, Any]:
    """Convert bot_target slot into executor args."""
    if not bot_target:
        return {}
    if bot_target.strip().lower() == "all":
        return {"all_bots": True}
    if "," in bot_target:
        return {"bot_names": [b.strip() for b in bot_target.split(",")]}
    return {"bot_name": bot_target.strip()}


def _parse_amount(raw: str | None) -> dict[str, Any]:
    """Parse a unified amount string into executor args.

    Accepts: '10000' (sats), '$5' or '$5.50' (USD), 'all'.
    """
    if not raw:
        return {}
    raw = raw.strip()
    if raw.lower() == "all":
        return {"amount": "all"}
    if raw.startswith("$"):
        try:
            return {"amount_usd": float(raw[1:])}
        except ValueError:
            return {"amount": raw}
    try:
        return {"amount": int(float(raw))}
    except ValueError:
        return {"amount": raw}


class ActionFund(Action):
    def name(self) -> Text:
        return "action_fund"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        args.update(_parse_amount(tracker.get_slot("fund_amount")))
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(dispatcher, execute_tool("fund", args))
        return [
            SlotSet("fund_amount", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_fund", None),
        ]


class ActionWithdraw(Action):
    def name(self) -> Text:
        return "action_withdraw"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        args.update(_parse_amount(tracker.get_slot("withdraw_amount")))
        args.update(_parse_bot_target(tracker.get_slot("bot_target")))

        _send_result(dispatcher, execute_tool("withdraw", args))
        return [
            SlotSet("withdraw_amount", None),
            SlotSet("bot_target", None),
            SlotSet("confirm_withdraw", None),
        ]
