from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import execute_tool

from .actions_utility import _send_result

DEFAULT_PERSONA = "iconfucius"


def _persona(tracker: Tracker) -> str:
    return tracker.get_slot("persona_key") or DEFAULT_PERSONA


class ActionMemoryReadStrategy(Action):
    def name(self) -> Text:
        return "action_memory_read_strategy"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(
            dispatcher,
            execute_tool(
                "memory_read_strategy", {}, persona_name=_persona(tracker)
            ),
        )
        return []


class ActionMemoryReadLearnings(Action):
    def name(self) -> Text:
        return "action_memory_read_learnings"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(
            dispatcher,
            execute_tool(
                "memory_read_learnings", {}, persona_name=_persona(tracker)
            ),
        )
        return []


class ActionMemoryReadTrades(Action):
    def name(self) -> Text:
        return "action_memory_read_trades"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        last_n = tracker.get_slot("last_n")
        if last_n is not None:
            args["last_n"] = int(last_n)

        _send_result(
            dispatcher,
            execute_tool(
                "memory_read_trades", args, persona_name=_persona(tracker)
            ),
        )
        return [SlotSet("last_n", None)]


class ActionMemoryReadBalances(Action):
    def name(self) -> Text:
        return "action_memory_read_balances"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        last_n = tracker.get_slot("last_n")
        if last_n is not None:
            args["last_n"] = int(last_n)

        _send_result(
            dispatcher,
            execute_tool(
                "memory_read_balances", args, persona_name=_persona(tracker)
            ),
        )
        return [SlotSet("last_n", None)]


class ActionMemoryUpdate(Action):
    def name(self) -> Text:
        return "action_memory_update"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args = {
            "file": tracker.get_slot("memory_file"),
            "content": tracker.get_slot("memory_content"),
        }
        _send_result(
            dispatcher,
            execute_tool("memory_update", args, persona_name=_persona(tracker)),
        )
        return [
            SlotSet("memory_file", None),
            SlotSet("memory_content", None),
            SlotSet("confirm_memory_update", None),
        ]


class ActionMemoryArchive(Action):
    def name(self) -> Text:
        return "action_memory_archive"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        args: dict[str, Any] = {}
        keep_days = tracker.get_slot("keep_days")
        if keep_days is not None:
            args["keep_days"] = int(keep_days)

        _send_result(
            dispatcher,
            execute_tool(
                "memory_archive_balances",
                args,
                persona_name=_persona(tracker),
            ),
        )
        return [
            SlotSet("keep_days", None),
            SlotSet("confirm_memory_archive", None),
        ]
