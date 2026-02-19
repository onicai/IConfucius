"""Tests for iconfucius.logging_config — security properties."""

import logging
import os
import stat

import pytest


class TestLogFilePermissions:
    """Log file and directory must be owner-only."""

    def test_log_dir_is_0700(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger
        get_logger()

        log_dir = tmp_path / ".logs"
        mode = stat.S_IMODE(log_dir.stat().st_mode)
        assert mode == 0o700, f"Expected 0700, got {oct(mode)}"

    def test_log_file_is_0600(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger
        logger = get_logger()
        logger.info("test")  # force flush
        for h in logger.handlers:
            h.flush()

        log_file = tmp_path / ".logs" / "iconfucius.log"
        mode = stat.S_IMODE(log_file.stat().st_mode)
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"


class TestJwtScrubbing:
    """JWT tokens must NEVER appear in log output."""

    _FAKE_JWT = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )

    def test_jwt_scrubbed_from_log_message(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger, set_debug
        logger = get_logger()
        set_debug(True)  # enable DEBUG so message is written

        logger.debug(f"Token: {self._FAKE_JWT}")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "eyJ" not in log_content
        assert "[JWT-REDACTED]" in log_content

    def test_jwt_scrubbed_at_info_level(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger
        logger = get_logger()

        logger.info(f"Token: {self._FAKE_JWT}")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "eyJ" not in log_content
        assert "[JWT-REDACTED]" in log_content

    def test_non_jwt_message_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger
        logger = get_logger()

        logger.info("Wallet principal: abc-123-def")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "abc-123-def" in log_content


class TestLogLevelGating:
    """Debug messages must only appear when --verbose is active."""

    def test_default_level_is_info(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger
        logger = get_logger()

        logger.debug("secret debug detail")
        logger.info("operational info")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "secret debug detail" not in log_content
        assert "operational info" in log_content

    def test_set_debug_enables_debug(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger, set_debug
        logger = get_logger()
        set_debug(True)

        logger.debug("now visible")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "now visible" in log_content

    def test_set_debug_false_restores_info(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        _reset_logger()
        from iconfucius.logging_config import get_logger, set_debug
        logger = get_logger()
        set_debug(True)
        set_debug(False)

        logger.debug("should be hidden again")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "should be hidden again" not in log_content

    def test_env_var_enables_debug(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        monkeypatch.setenv("ICONFUCIUS_VERBOSE", "1")
        _reset_logger()
        from iconfucius.logging_config import get_logger
        logger = get_logger()

        logger.debug("env debug visible")
        for h in logger.handlers:
            h.flush()

        log_content = (tmp_path / ".logs" / "iconfucius.log").read_text()
        assert "env debug visible" in log_content


def _reset_logger():
    """Remove all handlers from the iconfucius logger so get_logger() re-initializes."""
    logger = logging.getLogger("iconfucius")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
