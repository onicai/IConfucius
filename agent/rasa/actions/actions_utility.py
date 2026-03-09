from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.skills.executor import execute_tool


def _send_result(dispatcher: CollectingDispatcher, result: dict) -> None:
    """Send tool result to the user, picking the best display field."""
    if result.get("status") == "ok":
        text = (
            result.get("_display")
            or result.get("display")
            or str(result)
        )
        dispatcher.utter_message(text=text)
    else:
        dispatcher.utter_message(
            text=result.get("error", "An unexpected error occurred.")
        )


class ActionBotList(Action):
    def name(self) -> Text:
        return "action_bot_list"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(dispatcher, execute_tool("bot_list", {}))
        return []


class ActionCheckStatus(Action):
    def name(self) -> Text:
        return "action_check_status"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(
            dispatcher,
            execute_tool("setup_and_operational_status", {}),
        )
        return []


class ActionCheckUpdate(Action):
    def name(self) -> Text:
        return "action_check_update"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(dispatcher, execute_tool("check_update", {}))
        return []


class ActionSecurityStatus(Action):
    def name(self) -> Text:
        return "action_security_status"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(dispatcher, execute_tool("security_status", {}))
        return []


class ActionInstallBlst(Action):
    def name(self) -> Text:
        return "action_install_blst"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        _send_result(dispatcher, execute_tool("install_blst", {}))
        return []
