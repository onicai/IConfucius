"""Tests for iconfucius.persona — Persona engine (load, merge, list)."""

import pytest

import iconfucius.config as cfg
from iconfucius.persona import (
    DEFAULT_MODEL,
    Persona,
    PersonaNotFoundError,
    get_builtin_personas_dir,
    list_personas,
    load_persona,
    resolve_ai_config,
    _deep_merge,
)


# ---------------------------------------------------------------------------
# Built-in discovery
# ---------------------------------------------------------------------------

class TestBuiltinPersonas:
    def test_builtin_dir_exists(self):
        d = get_builtin_personas_dir()
        assert d.is_dir()
        assert (d / "iconfucius" / "persona.toml").exists()
        assert (d / "iconfucius" / "system-prompt.md").exists()
        assert (d / "iconfucius" / "greeting-prompt.md").exists()
        assert (d / "iconfucius" / "goodbye-prompt.md").exists()

    def test_list_personas_includes_iconfucius(self):
        names = list_personas()
        assert "iconfucius" in names

    def test_load_builtin_iconfucius(self):
        p = load_persona("iconfucius")
        assert isinstance(p, Persona)
        assert p.name == "IConfucius"
        assert p.ai_api_type == "claude"
        assert len(p.system_prompt) > 0

    def test_builtin_greeting_prompt_has_placeholders(self):
        p = load_persona("iconfucius")
        assert "{icon}" in p.greeting_prompt
        assert "{topic}" in p.greeting_prompt

    def test_builtin_goodbye_prompt_loaded(self):
        p = load_persona("iconfucius")
        assert len(p.goodbye_prompt) > 0


# ---------------------------------------------------------------------------
# Persona not found
# ---------------------------------------------------------------------------

class TestPersonaNotFound:
    def test_raises_for_unknown_name(self):
        with pytest.raises(PersonaNotFoundError, match="nonexistent"):
            load_persona("nonexistent")


# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_flat_override(self):
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_override(self):
        base = {"ai": {"backend": "claude", "model": "old"}}
        override = {"ai": {"model": "new"}}
        result = _deep_merge(base, override)
        assert result == {"ai": {"backend": "claude", "model": "new"}}

    def test_add_new_key(self):
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# Three-tier override
# ---------------------------------------------------------------------------

class TestPersonaOverride:
    def test_global_override(self, tmp_path, monkeypatch):
        """Global tier persona.toml overrides built-in fields."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        # Create global override
        global_dir = tmp_path / ".iconfucius-global" / "personas" / "iconfucius"
        global_dir.mkdir(parents=True)
        (global_dir / "persona.toml").write_text(
            '[persona]\nname = "GlobalConfucius"\n'
        )
        monkeypatch.setattr(
            "iconfucius.persona.get_global_personas_dir",
            lambda: tmp_path / ".iconfucius-global" / "personas",
        )

        p = load_persona("iconfucius")
        assert p.name == "GlobalConfucius"
        # Other fields still come from built-in
        assert p.ai_api_type == "claude"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_local_override(self, tmp_path, monkeypatch):
        """Local tier persona.toml overrides built-in and global."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        # Create local override
        local_dir = tmp_path / "personas" / "iconfucius"
        local_dir.mkdir(parents=True)
        (local_dir / "persona.toml").write_text(
            '[ai]\nmodel = "claude-haiku-4-5-20251001"\n'
        )

        p = load_persona("iconfucius")
        assert p.ai_model == "claude-haiku-4-5-20251001"
        # Other fields still come from built-in
        assert p.name == "IConfucius"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_system_prompt_override(self, tmp_path, monkeypatch):
        """Highest-precedence system-prompt.md wins entirely."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        local_dir = tmp_path / "personas" / "iconfucius"
        local_dir.mkdir(parents=True)
        (local_dir / "system-prompt.md").write_text("Custom prompt override.")

        p = load_persona("iconfucius")
        assert p.system_prompt == "Custom prompt override."

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_greeting_prompt_override(self, tmp_path, monkeypatch):
        """Local greeting-prompt.md overrides built-in."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        local_dir = tmp_path / "personas" / "iconfucius"
        local_dir.mkdir(parents=True)
        (local_dir / "greeting-prompt.md").write_text("Custom greeting {icon} {topic}")

        p = load_persona("iconfucius")
        assert p.greeting_prompt == "Custom greeting {icon} {topic}"

        cfg._cached_config = None
        cfg._cached_config_path = None

    def test_goodbye_prompt_override(self, tmp_path, monkeypatch):
        """Local goodbye-prompt.md overrides built-in."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        local_dir = tmp_path / "personas" / "iconfucius"
        local_dir.mkdir(parents=True)
        (local_dir / "goodbye-prompt.md").write_text("Custom farewell")

        p = load_persona("iconfucius")
        assert p.goodbye_prompt == "Custom farewell"

        cfg._cached_config = None
        cfg._cached_config_path = None


# ---------------------------------------------------------------------------
# AI config override from iconfucius.toml
# ---------------------------------------------------------------------------

class TestResolveAiConfig:
    """Tests for resolve_ai_config() with all resolution table rows."""

    def test_empty_config(self):
        api_type, model, base_url = resolve_ai_config({})
        assert api_type == "claude"
        assert model == DEFAULT_MODEL
        assert base_url == ""

    def test_model_only_claude(self):
        api_type, model, base_url = resolve_ai_config({"model": "claude-sonnet-4-6"})
        assert api_type == "claude"
        assert model == "claude-sonnet-4-6"
        assert base_url == ""

    def test_openai_with_base_url(self):
        api_type, model, base_url = resolve_ai_config({
            "api_type": "openai",
            "base_url": "http://localhost:55128",
        })
        assert api_type == "openai"
        assert model == "default"
        assert base_url == "http://localhost:55128"

    def test_openai_with_model_and_url(self):
        api_type, model, base_url = resolve_ai_config({
            "api_type": "openai",
            "model": "meta-llama/Llama-3-70b",
            "base_url": "https://api.together.xyz/v1",
        })
        assert api_type == "openai"
        assert model == "meta-llama/Llama-3-70b"
        assert base_url == "https://api.together.xyz/v1"

    def test_auto_detect_openai_from_base_url(self):
        """base_url set without api_type → auto-detect openai."""
        api_type, model, base_url = resolve_ai_config({
            "base_url": "http://localhost:8080",
        })
        assert api_type == "openai"
        assert model == "default"
        assert base_url == "http://localhost:8080"

    def test_auto_detect_claude_from_model(self):
        """model starts with 'claude-' without api_type → auto-detect claude."""
        api_type, model, base_url = resolve_ai_config({
            "model": "claude-haiku-4-5-20251001",
        })
        assert api_type == "claude"
        assert model == "claude-haiku-4-5-20251001"
        assert base_url == ""

    def test_legacy_backend_key(self):
        """Legacy 'backend' key is still supported."""
        api_type, model, base_url = resolve_ai_config({
            "backend": "claude",
            "model": "claude-sonnet-4-6",
        })
        assert api_type == "claude"
        assert model == "claude-sonnet-4-6"

    def test_openai_resets_inherited_claude_model(self):
        """DEFAULT_MODEL inherited from persona is reset to 'default' for openai."""
        api_type, model, base_url = resolve_ai_config({
            "api_type": "openai",
            "model": DEFAULT_MODEL,
            "base_url": "http://localhost:55128",
        })
        assert api_type == "openai"
        assert model == "default"
        assert base_url == "http://localhost:55128"

    def test_claude_keeps_default_model(self):
        """DEFAULT_MODEL is preserved for claude api_type."""
        api_type, model, base_url = resolve_ai_config({
            "api_type": "claude",
            "model": DEFAULT_MODEL,
        })
        assert api_type == "claude"
        assert model == DEFAULT_MODEL


class TestAIConfigOverride:
    def test_project_ai_overrides_persona(self, tmp_path, monkeypatch):
        """iconfucius.toml [ai] overrides persona's [ai] section."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None

        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n\n[ai]\napi_type = "openai"\nmodel = "llama-3"\n'
            'base_url = "http://localhost:8080"\n\n'
            '[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        cfg._cached_config = None

        p = load_persona("iconfucius")
        assert p.ai_api_type == "openai"
        assert p.ai_model == "llama-3"
        assert p.ai_base_url == "http://localhost:8080"

        cfg._cached_config = None
        cfg._cached_config_path = None
