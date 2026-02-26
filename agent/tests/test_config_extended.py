"""Extended tests for iconfucius.config — file loading, project root, wallet checks."""

import os
from unittest.mock import patch

import pytest

from iconfucius.config import (
    CONFIG_FILENAME,
    PEM_FILE,
    _project_root,
    add_bots_to_config,
    create_default_config,
    find_config,
    get_bot_description,
    get_bot_names,
    get_pem_file,
    get_cache_sessions,
    get_verify_certificates,
    load_config,
    remove_bots_from_config,
    require_wallet,
    validate_bot_name,
)
import iconfucius.config as cfg


class TestProjectRoot:
    def test_uses_iconfucius_root_env(self, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", "/custom/root")
        assert _project_root() == "/custom/root"

    def test_uses_pwd_env_as_fallback(self, monkeypatch):
        monkeypatch.delenv("ICONFUCIUS_ROOT", raising=False)
        monkeypatch.setenv("PWD", "/pwd/path")
        assert _project_root() == "/pwd/path"

    def test_falls_back_to_cwd(self, monkeypatch):
        monkeypatch.delenv("ICONFUCIUS_ROOT", raising=False)
        monkeypatch.delenv("PWD", raising=False)
        assert _project_root() == os.getcwd()


class TestFindConfig:
    def test_found(self, odin_project):
        result = find_config()
        assert result is not None
        assert result.name == CONFIG_FILENAME

    def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        assert find_config() is None


class TestLoadConfig:
    def test_loads_from_file(self, odin_project):
        config = load_config(reload=True)
        assert "bot-1" in config["bots"]
        assert "bot-2" in config["bots"]

    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        config = load_config(reload=True)
        assert "bot-1" in config["bots"]

    def test_caching(self, odin_project):
        config1 = load_config(reload=True)
        config2 = load_config()
        assert config1 is config2

    def test_reload_clears_cache(self, odin_project):
        load_config(reload=True)
        cfg._cached_config["settings"]["test_key"] = "changed"
        config = load_config(reload=True)
        assert "test_key" not in config["settings"]


class TestGetPemFile:
    def test_returns_absolute_path(self, odin_project):
        pem = get_pem_file()
        assert pem.endswith(PEM_FILE)
        assert os.path.isabs(pem)


class TestRequireWallet:
    def test_returns_true_when_exists(self, odin_project, capsys):
        assert require_wallet() is True

    def test_returns_false_and_prints_when_missing(self, odin_project_no_wallet, capsys):
        assert require_wallet() is False
        output = capsys.readouterr().out
        assert "No iconfucius wallet found" in output
        assert "iconfucius wallet create" in output


class TestGetBotNames:
    def test_returns_all_bots(self, odin_project):
        names = get_bot_names()
        assert "bot-1" in names
        assert "bot-2" in names
        assert "bot-3" in names
        assert len(names) == 3


class TestGetBotDescription:
    def test_existing_bot(self, odin_project):
        assert get_bot_description("bot-1") == "Bot 1"

    def test_nonexistent_bot(self, odin_project):
        assert get_bot_description("nonexistent") == ""


class TestValidateBotName:
    def test_valid_name(self, odin_project):
        assert validate_bot_name("bot-1") is True

    def test_invalid_name(self, odin_project):
        assert validate_bot_name("nonexistent") is False


class TestCreateDefaultConfig:
    def test_generates_toml(self):
        content = create_default_config()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" in content
        assert "[bots.bot-3]" in content

    def test_includes_verify_certificates(self):
        content = create_default_config()
        assert "verify_certificates = false" in content

    def test_default_is_three_bots(self):
        content = create_default_config()
        assert "[bots.bot-3]" in content
        assert "[bots.bot-4]" not in content

    def test_one_bot(self):
        content = create_default_config(num_bots=1)
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" not in content

    def test_five_bots(self):
        content = create_default_config(num_bots=5)
        for i in range(1, 6):
            assert f"[bots.bot-{i}]" in content
            assert f'description = "Bot {i}"' in content
        assert "[bots.bot-6]" not in content

    def test_ten_bots(self):
        content = create_default_config(num_bots=10)
        for i in range(1, 11):
            assert f"[bots.bot-{i}]" in content
        assert "[bots.bot-11]" not in content

    def test_zero_clamped_to_one(self):
        content = create_default_config(num_bots=0)
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" not in content

    def test_negative_clamped_to_one(self):
        content = create_default_config(num_bots=-5)
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" not in content

    def test_over_thousand_clamped(self):
        content = create_default_config(num_bots=1500)
        assert "[bots.bot-1000]" in content
        assert "[bots.bot-1001]" not in content

    def test_header_always_present(self):
        content = create_default_config(num_bots=1)
        assert "[settings]" in content
        assert "cache_sessions = true" in content
        assert 'default_persona = "iconfucius"' in content
        assert "# [ai]" in content


class TestAddBotsToConfig:
    """Tests for add_bots_to_config()."""

    def test_adds_new_bots(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / CONFIG_FILENAME).write_text(create_default_config(num_bots=3))
        added = add_bots_to_config(3, 6)
        assert added == ["bot-4", "bot-5", "bot-6"]
        content = (tmp_path / CONFIG_FILENAME).read_text()
        for i in range(1, 7):
            assert f"[bots.bot-{i}]" in content
        assert "[bots.bot-7]" not in content

    def test_returns_empty_when_nothing_to_add(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / CONFIG_FILENAME).write_text(create_default_config(num_bots=3))
        added = add_bots_to_config(3, 3)
        assert added == []


class TestRemoveBotsFromConfig:
    """Tests for remove_bots_from_config()."""

    def test_removes_specified_bots(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / CONFIG_FILENAME).write_text(create_default_config(num_bots=5))
        remove_bots_from_config(["bot-4", "bot-5"])
        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-3]" in content
        assert "[bots.bot-4]" not in content
        assert "[bots.bot-5]" not in content

    def test_removes_middle_bot(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / CONFIG_FILENAME).write_text(create_default_config(num_bots=5))
        remove_bots_from_config(["bot-3"])
        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert "[bots.bot-2]" in content
        assert "[bots.bot-3]" not in content
        assert "[bots.bot-4]" in content

    def test_removes_all_bots_except_one(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / CONFIG_FILENAME).write_text(create_default_config(num_bots=3))
        remove_bots_from_config(["bot-2", "bot-3"])
        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" not in content
        assert "[settings]" in content


class TestGetVerifyCertificates:
    def test_defaults_to_false(self, odin_project):
        """No verify_certificates in config -> returns False."""
        load_config(reload=True)
        assert get_verify_certificates() is False

    def test_explicit_false(self, tmp_path, monkeypatch):
        """verify_certificates = false -> returns False."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            "[settings]\nverify_certificates = false\n\n[bots.bot-1]\n"
        )
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)
        assert get_verify_certificates() is False

    def test_true_with_blst(self, tmp_path, monkeypatch):
        """verify_certificates = true + blst importable -> returns True."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            "[settings]\nverify_certificates = true\n\n[bots.bot-1]\n"
        )
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)

        with patch.dict("sys.modules", {"blst": object()}):
            assert get_verify_certificates() is True

    def test_true_without_blst_exits(self, tmp_path, monkeypatch, capsys):
        """verify_certificates = true + no blst -> SystemExit(1)."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            "[settings]\nverify_certificates = true\n\n[bots.bot-1]\n"
        )
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)

        with patch.dict("sys.modules", {"blst": None}):
            with pytest.raises(SystemExit) as exc_info:
                get_verify_certificates()
            assert exc_info.value.code == 1

        output = capsys.readouterr().out
        assert "blst" in output
        assert "README-security.md" in output

    def test_no_config_file(self, tmp_path, monkeypatch):
        """No iconfucius.toml at all -> returns False."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)
        assert get_verify_certificates() is False


class TestGetCacheSessions:
    def test_defaults_to_true(self, odin_project):
        """No cache_sessions in config -> returns True."""
        load_config(reload=True)
        assert get_cache_sessions() is True

    def test_explicit_true(self, tmp_path, monkeypatch):
        """cache_sessions = true -> returns True."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            "[settings]\ncache_sessions = true\n\n[bots.bot-1]\n"
        )
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)
        assert get_cache_sessions() is True

    def test_explicit_false(self, tmp_path, monkeypatch):
        """cache_sessions = false -> returns False."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text(
            "[settings]\ncache_sessions = false\n\n[bots.bot-1]\n"
        )
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)
        assert get_cache_sessions() is False

    def test_no_config_file(self, tmp_path, monkeypatch):
        """No iconfucius.toml at all -> returns True."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        load_config(reload=True)
        assert get_cache_sessions() is True

    def test_included_in_default_config(self):
        """Default config template includes cache_sessions = true."""
        content = create_default_config()
        assert "cache_sessions = true" in content


class TestGetAiTimeout:
    """Tests for get_ai_timeout() validation."""

    def test_default_timeout(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        from iconfucius.config import AI_TIMEOUT_DEFAULT, get_ai_timeout
        assert get_ai_timeout() == AI_TIMEOUT_DEFAULT

    def test_valid_timeout(self, tmp_path, monkeypatch):
        (tmp_path / "iconfucius.toml").write_text("[ai]\ntimeout = 300\n")
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        from iconfucius.config import get_ai_timeout
        assert get_ai_timeout() == 300

    def test_malformed_timeout_falls_back(self, tmp_path, monkeypatch):
        (tmp_path / "iconfucius.toml").write_text('[ai]\ntimeout = "not-a-number"\n')
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        from iconfucius.config import AI_TIMEOUT_DEFAULT, get_ai_timeout
        assert get_ai_timeout() == AI_TIMEOUT_DEFAULT

    def test_negative_timeout_falls_back(self, tmp_path, monkeypatch):
        (tmp_path / "iconfucius.toml").write_text("[ai]\ntimeout = -10\n")
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        from iconfucius.config import AI_TIMEOUT_DEFAULT, get_ai_timeout
        assert get_ai_timeout() == AI_TIMEOUT_DEFAULT

    def test_zero_timeout_falls_back(self, tmp_path, monkeypatch):
        (tmp_path / "iconfucius.toml").write_text("[ai]\ntimeout = 0\n")
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        cfg._cached_config = None
        cfg._cached_config_path = None
        from iconfucius.config import AI_TIMEOUT_DEFAULT, get_ai_timeout
        assert get_ai_timeout() == AI_TIMEOUT_DEFAULT
