"""Tests for iconfucius.config — verbose/log helpers and network selection."""

import pytest

from iconfucius.config import (
    CKSIGNER_CANISTER_IDS,
    VALID_NETWORKS,
    get_cksigner_canister_id,
    get_network,
    is_verbose,
    log,
    set_network,
    set_verbose,
)


class TestVerboseFlag:
    """Test set_verbose / is_verbose state management."""

    def teardown_method(self):
        # Reset to default after each test
        set_verbose(False)

    def test_default_is_not_verbose(self):
        set_verbose(False)  # ensure default
        assert is_verbose() is False

    def test_set_verbose_false(self):
        set_verbose(False)
        assert is_verbose() is False

    def test_set_verbose_true(self):
        set_verbose(False)
        set_verbose(True)
        assert is_verbose() is True

    def test_set_verbose_calls_set_debug(self):
        from unittest.mock import patch
        with patch("iconfucius.logging_config.set_debug") as mock_set_debug:
            set_verbose(True)
            mock_set_debug.assert_called_once_with(True)
        set_verbose(False)  # reset


class TestLog:
    """Test log() writes to file logger (not stdout)."""

    def test_log_writes_to_logger_not_stdout(self, capsys):
        log("hello")
        assert capsys.readouterr().out == ""  # no stdout output

    def test_log_calls_debug(self, caplog):
        import logging
        with caplog.at_level(logging.DEBUG, logger="iconfucius"):
            log("test message")
        assert "test message" in caplog.text


class TestNetworkSelection:
    """Test set_network / get_network / get_cksigner_canister_id."""

    def teardown_method(self):
        set_network("prd")

    def test_default_is_prd(self):
        set_network("prd")
        assert get_network() == "prd"

    def test_set_testing(self):
        set_network("testing")
        assert get_network() == "testing"

    def test_set_development(self):
        set_network("development")
        assert get_network() == "development"

    def test_invalid_network_raises(self):
        with pytest.raises(ValueError, match="Unknown network"):
            set_network("staging")

    def test_prd_canister_id(self):
        set_network("prd")
        assert get_cksigner_canister_id() == "g7qkb-iiaaa-aaaar-qb3za-cai"

    def test_testing_canister_id(self):
        set_network("testing")
        assert get_cksigner_canister_id() == "ho2u6-qaaaa-aaaar-qb34q-cai"

    def test_development_canister_id(self):
        set_network("development")
        assert get_cksigner_canister_id() == "ho2u6-qaaaa-aaaar-qb34q-cai"

    def test_valid_networks_list(self):
        assert set(VALID_NETWORKS) == {"prd", "testing", "development"}

    def test_canister_ids_dict_matches(self):
        for net in VALID_NETWORKS:
            set_network(net)
            assert get_cksigner_canister_id() == CKSIGNER_CANISTER_IDS[net]


class TestSessionPathNetwork:
    """Test that session file paths are network-aware."""

    def teardown_method(self):
        set_network("prd")

    def test_prd_session_path_no_suffix(self):
        from iconfucius.siwb import _session_path
        set_network("prd")
        path = _session_path("bot-1")
        assert path.endswith("session_bot-1.json")

    def test_testing_session_path_has_suffix(self):
        from iconfucius.siwb import _session_path
        set_network("testing")
        path = _session_path("bot-1")
        assert path.endswith("session_bot-1_testing.json")

    def test_development_session_path_has_suffix(self):
        from iconfucius.siwb import _session_path
        set_network("development")
        path = _session_path("bot-1")
        assert path.endswith("session_bot-1_development.json")

    def test_different_networks_different_paths(self):
        from iconfucius.siwb import _session_path
        set_network("prd")
        prd_path = _session_path("bot-1")
        set_network("testing")
        testing_path = _session_path("bot-1")
        assert prd_path != testing_path
