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


DEFAULT_MODEL = "claude-opus-4-6"

# Maps model name prefixes to their API type
_MODEL_PREFIX_TO_API_TYPE = {
    "claude-": "claude",
}

# API types that don't require an API key (local servers)
_LOCAL_API_TYPES = {"openai"}  # local by default, key optional


class PersonaNotFoundError(Exception):
    """Raised when a persona cannot be found in any tier."""


@dataclass
class Persona:
    name: str
    ai_api_type: str   # "claude" | "openai"
    ai_model: str
    ai_base_url: str   # "" for Claude (uses SDK default), URL for openai
    system_prompt: str    # contents of system-prompt.md
    greeting_prompt: str  # contents of greeting-prompt.md
    goodbye_prompt: str   # contents of goodbye-prompt.md


def resolve_ai_config(ai_section: dict) -> tuple[str, str, str]:
    """Resolve AI configuration from an [ai] section dict.

    Auto-detection rules:
    - If base_url is set but api_type is not → assume "openai"
    - If model starts with "claude-" and no api_type → assume "claude"
    - Default: api_type="claude", model=DEFAULT_MODEL, base_url=""

    Returns:
        (api_type, model, base_url)
    """
    api_type = ai_section.get("api_type", "")
    model = ai_section.get("model", "")
    base_url = ai_section.get("base_url", "")

    # Legacy support: "backend" key from old persona.toml format
    if not api_type:
        api_type = ai_section.get("backend", "")

    # Auto-detect api_type from base_url
    if not api_type and base_url:
        api_type = "openai"

    # Auto-detect api_type from model name prefix
    if not api_type and model:
        for prefix, detected_type in _MODEL_PREFIX_TO_API_TYPE.items():
            if model.startswith(prefix):
                api_type = detected_type
                break

    # Defaults
    if not api_type:
        api_type = "claude"
    if not model:
        model = DEFAULT_MODEL if api_type == "claude" else "default"
    # DEFAULT_MODEL belongs to the claude api_type; reset for other types
    elif model == DEFAULT_MODEL and api_type != "claude":
        model = "default"

    return api_type, model, base_url


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
    ai_section = merged_config.get("ai", {})

    api_type, model, base_url = resolve_ai_config(ai_section)

    return Persona(
        name=persona_section.get("name", name),
        ai_api_type=api_type,
        ai_model=model,
        ai_base_url=base_url,
        system_prompt=system_prompt,
        greeting_prompt=greeting_prompt,
        goodbye_prompt=goodbye_prompt,
    )
