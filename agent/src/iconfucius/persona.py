"""Persona engine — load, merge, and list trading personas.

Personas are resolved from three tiers (lowest → highest precedence):
1. Built-in:  <package>/personas/<name>/
2. Global:    ~/.iconfucius/personas/<name>/
3. Local:     ./personas/<name>/  (project directory)

For persona.toml: deep-merge keys (higher tier overrides lower).
For system-prompt.md: highest-precedence version wins entirely.
"""

from dataclasses import dataclass
from pathlib import Path

import tomllib

from iconfucius.config import _project_root, get_ai_config


class PersonaNotFoundError(Exception):
    """Raised when a persona cannot be found in any tier."""


@dataclass
class Persona:
    name: str
    description: str
    voice: str
    risk: str          # conservative | moderate | aggressive
    budget_limit: int  # 0 = unlimited
    bot: str           # default bot name
    ai_backend: str    # claude | gemini | ollama | openai
    ai_model: str
    system_prompt: str    # contents of system-prompt.md
    greeting_prompt: str  # contents of greeting-prompt.md
    goodbye_prompt: str   # contents of goodbye-prompt.md


def get_builtin_personas_dir() -> Path:
    """Return path to built-in personas dir (inside installed package)."""
    return Path(__file__).parent / "personas"


def get_global_personas_dir() -> Path:
    """Return ~/.iconfucius/personas/."""
    return Path.home() / ".iconfucius" / "personas"


def get_local_personas_dir() -> Path:
    """Return ./personas/ relative to project root."""
    return Path(_project_root()) / "personas"


def _tier_dirs() -> list[Path]:
    """Return persona directories in precedence order (lowest first)."""
    return [
        get_builtin_personas_dir(),
        get_global_personas_dir(),
        get_local_personas_dir(),
    ]


def list_personas() -> list[str]:
    """List all available persona names across all 3 tiers (deduplicated)."""
    names: set[str] = set()
    for tier_dir in _tier_dirs():
        if tier_dir.is_dir():
            for child in tier_dir.iterdir():
                if child.is_dir() and (child / "persona.toml").exists():
                    names.add(child.name)
    return sorted(names)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge two dicts. Override values win for non-dict keys."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_persona(name: str) -> Persona:
    """Load and merge a persona from all available tiers.

    Args:
        name: Persona directory name (e.g. "iconfucius").

    Returns:
        Merged Persona dataclass.

    Raises:
        PersonaNotFoundError: If persona not found in any tier.
    """
    merged_config: dict = {}
    system_prompt = ""
    greeting_prompt = ""
    goodbye_prompt = ""
    found = False

    for tier_dir in _tier_dirs():
        persona_dir = tier_dir / name
        if not persona_dir.is_dir():
            continue

        # Load persona.toml if present
        toml_path = persona_dir / "persona.toml"
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                tier_config = tomllib.load(f)
            merged_config = _deep_merge(merged_config, tier_config)
            found = True

        # Markdown files: highest tier wins entirely
        prompt_path = persona_dir / "system-prompt.md"
        if prompt_path.exists():
            system_prompt = prompt_path.read_text()
            found = True

        greet_path = persona_dir / "greeting-prompt.md"
        if greet_path.exists():
            greeting_prompt = greet_path.read_text()

        bye_path = persona_dir / "goodbye-prompt.md"
        if bye_path.exists():
            goodbye_prompt = bye_path.read_text()

    if not found:
        raise PersonaNotFoundError(
            f"Persona '{name}' not found. Available: {list_personas()}"
        )

    # Apply iconfucius.toml [ai] override (highest precedence)
    project_ai = get_ai_config()
    if project_ai:
        ai_section = merged_config.get("ai", {})
        ai_section = _deep_merge(ai_section, project_ai)
        merged_config["ai"] = ai_section

    # Extract fields with defaults
    persona_section = merged_config.get("persona", {})
    defaults_section = merged_config.get("defaults", {})
    ai_section = merged_config.get("ai", {})

    return Persona(
        name=persona_section.get("name", name),
        description=persona_section.get("description", ""),
        voice=persona_section.get("voice", ""),
        risk=defaults_section.get("risk", "conservative"),
        budget_limit=defaults_section.get("budget_limit", 0),
        bot=defaults_section.get("bot", "bot-1"),
        ai_backend=ai_section.get("backend", "claude"),
        ai_model=ai_section.get("model", "claude-sonnet-4-5-20250929"),
        system_prompt=system_prompt,
        greeting_prompt=greeting_prompt,
        goodbye_prompt=goodbye_prompt,
    )
