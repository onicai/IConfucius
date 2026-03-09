from typing import Any, Dict, List, Text

import anthropic
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from iconfucius.persona import load_persona


class ActionGreeting(Action):
    def name(self) -> Text:
        return "action_greeting"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        topic = tracker.get_slot("greeting_topic") or "Wisdom"
        icon = tracker.get_slot("greeting_icon") or ""
        persona_key = tracker.get_slot("persona_key") or "iconfucius"

        persona = load_persona(persona_key)
        greeting_prompt = persona.greeting_prompt.format(icon=icon, topic=topic)

        user_msg = (
            f"{greeting_prompt}\n\n"
            f"After a blank line, also add:\n"
            f"{persona.goodbye_prompt}"
        )

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            system=persona.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text.strip()

        # Split: everything before the last line is greeting, last line is goodbye
        lines = text.split("\n")
        goodbye = ""
        greeting_lines = []
        for line in reversed(lines):
            if line.strip() and not goodbye:
                goodbye = line.strip()
            else:
                greeting_lines.insert(0, line)
        greeting = "\n".join(greeting_lines).strip()

        dispatcher.utter_message(text=f"GREETING:{greeting}")
        dispatcher.utter_message(text=f"GOODBYE:{goodbye}")
        return []
