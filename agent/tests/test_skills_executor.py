"""Tests for iconfucius.skills.executor — Tool dispatch and execution."""

import os
from unittest.mock import MagicMock, patch

from iconfucius.skills.executor import (
    execute_tool,
    _enable_verify_certificates,
    _resolve_bot_names,
    _tokens_to_subunits,
    _usd_to_sats,
    _usd_to_tokens,
)


class TestResolveBotNames:
    def test_single_bot_name(self):
        assert _resolve_bot_names({"bot_name": "bot-1"}) == ["bot-1"]

    def test_bot_names_list(self):
        result = _resolve_bot_names({"bot_names": ["bot-12", "bot-14"]})
        assert result == ["bot-12", "bot-14"]

    def test_all_bots(self, odin_project):
        result = _resolve_bot_names({"all_bots": True})
        assert len(result) == 3  # default odin_project fixture has 3 bots

    def test_empty_returns_empty(self):
        assert _resolve_bot_names({}) == []

    def test_bot_names_takes_priority_over_bot_name(self):
        result = _resolve_bot_names({
            "bot_names": ["bot-2", "bot-3"],
            "bot_name": "bot-1",
        })
        assert result == ["bot-2", "bot-3"]

    def test_all_bots_takes_priority(self, odin_project):
        result = _resolve_bot_names({
            "all_bots": True,
            "bot_name": "bot-1",
            "bot_names": ["bot-2"],
        })
        assert len(result) == 3  # all configured bots, not the explicit ones


class TestExecuteToolDispatch:
    def test_unknown_tool_returns_error(self):
        result = execute_tool("nonexistent_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["error"]



class TestSetupStatusExecutor:
    def test_setup_status_returns_all_fields(self):
        result = execute_tool("setup_status", {})
        assert result["status"] == "ok"
        assert "config_exists" in result
        assert "wallet_exists" in result
        assert "env_exists" in result
        assert "has_api_key" in result
        assert "ready" in result

    def test_setup_status_ready_requires_all(self):
        """ready should be False when any component is missing."""
        # In the test environment, wallet likely doesn't exist
        result = execute_tool("setup_status", {})
        assert result["status"] == "ok"
        # ready should be a bool
        assert isinstance(result["ready"], bool)


class TestInitExecutor:
    def test_init_creates_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        # Clear config cache
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None

        result = execute_tool("init", {})
        assert result["status"] == "ok"
        assert (tmp_path / "iconfucius.toml").exists()

    def test_init_existing_config_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text("[settings]\n")

        result = execute_tool("init", {})
        assert result["status"] == "error"
        assert "already exists" in result["error"]

    def test_init_with_num_bots(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None

        result = execute_tool("init", {"num_bots": 2})
        assert result["status"] == "ok"
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" in content
        assert "[bots.bot-3]" not in content

    def test_init_without_num_bots_defaults_to_three(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None

        result = execute_tool("init", {})
        assert result["status"] == "ok"
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-3]" in content
        assert "[bots.bot-4]" not in content


class TestBotListExecutor:
    """Tests for bot_list agent skill."""

    def test_lists_bots(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        execute_tool("init", {"num_bots": 5})
        cfg._cached_config = None
        cfg._cached_config_path = None

        result = execute_tool("bot_list", {})
        assert result["status"] == "ok"
        assert result["bot_count"] == 5
        assert result["bot_names"] == ["bot-1", "bot-2", "bot-3", "bot-4", "bot-5"]
        assert "5 bot(s)" in result["display"]

    def test_no_config_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None

        result = execute_tool("bot_list", {})
        assert result["status"] == "error"


class TestSetBotCountExecutor:
    """Tests for set_bot_count agent skill."""

    def _setup_project(self, tmp_path, monkeypatch, num_bots=3):
        """Helper: init a project with N bots in tmp_path."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        result = execute_tool("init", {"num_bots": num_bots})
        assert result["status"] == "ok"
        cfg._cached_config = None
        cfg._cached_config_path = None
        return tmp_path

    def test_no_config_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        result = execute_tool("set_bot_count", {"num_bots": 5})
        assert result["status"] == "error"
        assert "No iconfucius.toml" in result["error"]

    def test_same_count_is_noop(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch, num_bots=3)
        result = execute_tool("set_bot_count", {"num_bots": 3})
        assert result["status"] == "ok"
        assert result["bot_count"] == 3
        assert "Already" in result["message"]

    def test_increase_adds_bots(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch, num_bots=3)
        result = execute_tool("set_bot_count", {"num_bots": 7})
        assert result["status"] == "ok"
        assert result["bot_count"] == 7
        assert len(result["bots_added"]) == 4
        content = (tmp_path / "iconfucius.toml").read_text()
        for i in range(1, 8):
            assert f"[bots.bot-{i}]" in content
        assert "[bots.bot-8]" not in content

    def test_increase_large(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch, num_bots=3)
        result = execute_tool("set_bot_count", {"num_bots": 100})
        assert result["status"] == "ok"
        assert result["bot_count"] == 100
        assert len(result["bots_added"]) == 97

    def test_decrease_no_sessions_removes_immediately(self, tmp_path, monkeypatch):
        """Bots without cached sessions are removed without balance check."""
        self._setup_project(tmp_path, monkeypatch, num_bots=5)
        result = execute_tool("set_bot_count", {"num_bots": 2})
        assert result["status"] == "ok"
        assert result["bot_count"] == 2
        assert set(result["bots_removed"]) == {"bot-3", "bot-4", "bot-5"}
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" in content
        assert "[bots.bot-3]" not in content

    def test_decrease_with_holdings_returns_blocked(self, tmp_path, monkeypatch):
        """Bots with cached sessions and holdings block removal."""
        self._setup_project(tmp_path, monkeypatch, num_bots=3)
        # Create a fake cached session for bot-3
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir(exist_ok=True)
        (cache_dir / "session_bot-3.json").write_text("{}")

        from iconfucius.cli.balance import BotBalances

        fake_data = BotBalances(
            bot_name="bot-3", bot_principal="abc-123",
            odin_sats=5000, token_holdings=[{"ticker": "TEST", "balance": 100}],
        )
        with patch("iconfucius.cli.balance.collect_balances", return_value=fake_data):
            result = execute_tool("set_bot_count", {"num_bots": 2})
        assert result["status"] == "blocked"
        assert result["reason"] == "bots_have_holdings"
        assert len(result["holdings"]) == 1
        assert result["holdings"][0]["bot_name"] == "bot-3"
        # Config should NOT have been modified
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-3]" in content

    def test_decrease_force_skips_check(self, tmp_path, monkeypatch):
        """force=True removes bots without checking holdings."""
        self._setup_project(tmp_path, monkeypatch, num_bots=5)
        # Create fake sessions (would trigger balance check without force)
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir(exist_ok=True)
        (cache_dir / "session_bot-4.json").write_text("{}")
        (cache_dir / "session_bot-5.json").write_text("{}")

        result = execute_tool("set_bot_count", {"num_bots": 3, "force": True})
        assert result["status"] == "ok"
        assert result["bot_count"] == 3
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-3]" in content
        assert "[bots.bot-4]" not in content

    def test_num_bots_required(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch, num_bots=3)
        result = execute_tool("set_bot_count", {})
        assert result["status"] == "error"
        assert "required" in result["error"].lower()

    def test_num_bots_clamped(self, tmp_path, monkeypatch):
        """num_bots is clamped to 1-1000 range."""
        self._setup_project(tmp_path, monkeypatch, num_bots=3)
        result = execute_tool("set_bot_count", {"num_bots": 0})
        # 0 clamped to 1, so decrease from 3 to 1
        assert result["status"] == "ok"
        assert result["bot_count"] == 1


class TestWalletCreateExecutor:
    def test_wallet_create_creates_pem(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))

        result = execute_tool("wallet_create", {})
        assert result["status"] == "ok"
        pem_path = tmp_path / ".wallet" / "identity-private.pem"
        assert pem_path.exists()

    def test_wallet_create_existing_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        wallet_dir = tmp_path / ".wallet"
        wallet_dir.mkdir()
        (wallet_dir / "identity-private.pem").write_text("existing")

        result = execute_tool("wallet_create", {})
        assert result["status"] == "error"
        assert "already exists" in result["error"]


class TestTokenLookupExecutor:
    def test_token_lookup_known_token(self):
        """token_lookup should find IConfucius by name."""
        with patch("iconfucius.tokens._search_api", return_value=[]):
            result = execute_tool("token_lookup", {"query": "IConfucius"})
        assert result["status"] == "ok"
        assert result["known_match"] is not None
        assert result["known_match"]["id"] == "29m8"

    def test_token_lookup_missing_query_returns_error(self):
        result = execute_tool("token_lookup", {})
        assert result["status"] == "error"
        assert "required" in result["error"].lower()


class TestSecurityStatusExecutor:
    """Tests for security_status agent skill."""

    def _setup_project(self, tmp_path, monkeypatch, settings=""):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        content = '[settings]\n' + settings + '\n[bots.bot-1]\ndescription = "Bot 1"\n'
        (tmp_path / "iconfucius.toml").write_text(content)

    def test_blst_not_installed(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch)
        with patch.dict("sys.modules", {"blst": None}):
            result = execute_tool("security_status", {})
        assert result["status"] == "ok"
        assert result["blst_installed"] is False
        assert result["verify_certificates"] is False
        assert "not installed" in result["display"]

    def test_blst_installed_not_enabled(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch)
        with patch.dict("sys.modules", {"blst": object()}):
            result = execute_tool("security_status", {})
        assert result["status"] == "ok"
        assert result["blst_installed"] is True
        assert result["verify_certificates"] is False
        assert "disabled" in result["display"]
        assert "enable" in result["display"].lower()

    def test_blst_installed_and_enabled(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch,
                            settings="verify_certificates = true")
        with patch.dict("sys.modules", {"blst": object()}):
            result = execute_tool("security_status", {})
        assert result["status"] == "ok"
        assert result["blst_installed"] is True
        assert result["verify_certificates"] is True
        assert "enabled" in result["display"]

    def test_cache_sessions_disabled(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch,
                            settings="cache_sessions = false")
        with patch.dict("sys.modules", {"blst": None}):
            result = execute_tool("security_status", {})
        assert result["cache_sessions"] is False
        assert "disabled" in result["display"].lower()

    def test_recommendations_when_blst_missing(self, tmp_path, monkeypatch):
        self._setup_project(tmp_path, monkeypatch)
        with patch.dict("sys.modules", {"blst": None}):
            result = execute_tool("security_status", {})
        assert "Recommendations:" in result["display"]
        assert "install_blst" in result["display"].lower()

    def test_recommendation_when_blst_present_but_not_enabled(
        self, tmp_path, monkeypatch
    ):
        self._setup_project(tmp_path, monkeypatch)
        with patch.dict("sys.modules", {"blst": object()}):
            result = execute_tool("security_status", {})
        assert "Recommendations:" in result["display"]
        assert "verify_certificates" in result["display"]

    def test_no_recommendations_when_fully_configured(
        self, tmp_path, monkeypatch
    ):
        self._setup_project(tmp_path, monkeypatch,
                            settings="verify_certificates = true")
        with patch.dict("sys.modules", {"blst": object()}):
            result = execute_tool("security_status", {})
        assert "Recommendations:" not in result["display"]


class TestEnableVerifyCertificates:
    """Tests for _enable_verify_certificates helper."""

    def test_no_config_returns_not_enabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        result = _enable_verify_certificates()
        assert result["enabled_now"] is False

    def test_enables_when_not_present(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        result = _enable_verify_certificates()
        assert result["enabled_now"] is True
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "verify_certificates = true" in content

    def test_enables_when_false(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\nverify_certificates = false\n'
            '[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        result = _enable_verify_certificates()
        assert result["enabled_now"] is True
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "verify_certificates = true" in content
        assert "verify_certificates = false" not in content

    def test_noop_when_already_true(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\nverify_certificates = true\n'
            '[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        result = _enable_verify_certificates()
        assert result["enabled_now"] is False

    def test_adds_settings_section_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        (tmp_path / "iconfucius.toml").write_text(
            '[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        result = _enable_verify_certificates()
        assert result["enabled_now"] is True
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "verify_certificates = true" in content


class TestInstallBlstExecutor:
    """Tests for install_blst agent skill."""

    def test_already_installed_enables_config(self, tmp_path, monkeypatch):
        """When blst is already importable, enables verify_certificates."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\n[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        with patch.dict("sys.modules", {"blst": object()}):
            result = execute_tool("install_blst", {})
        assert result["status"] == "ok"
        assert "already installed" in result["display"]
        assert "Enabled" in result["display"]
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "verify_certificates = true" in content

    def test_already_installed_already_enabled(self, tmp_path, monkeypatch):
        """When blst installed and verify_certificates already true."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        (tmp_path / "iconfucius.toml").write_text(
            '[settings]\nverify_certificates = true\n'
            '[bots.bot-1]\ndescription = "Bot 1"\n'
        )
        with patch.dict("sys.modules", {"blst": object()}):
            result = execute_tool("install_blst", {})
        assert result["status"] == "ok"
        assert "already installed" in result["display"]
        assert "already enabled" in result["display"]

    def test_missing_prerequisites(self, tmp_path, monkeypatch):
        """Reports missing tools when blst not installed."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None
        with patch.dict("sys.modules", {"blst": None}):
            with patch("shutil.which", return_value=None):
                result = execute_tool("install_blst", {})
        assert result["status"] == "error"
        assert "Missing prerequisites" in result["error"]

    def test_missing_swig_only(self, tmp_path, monkeypatch):
        """Reports only swig missing when git and cc present."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        import iconfucius.config as cfg
        cfg._cached_config = None
        cfg._cached_config_path = None

        def fake_which(cmd):
            if cmd in ("git", "cc"):
                return f"/usr/bin/{cmd}"
            return None

        with patch.dict("sys.modules", {"blst": None}):
            with patch("shutil.which", side_effect=fake_which):
                result = execute_tool("install_blst", {})
        assert result["status"] == "error"
        assert "swig" in result["error"]
        assert "git" not in result["error"].split("Missing")[1]


class TestTradeRecording:
    """Tests that buy/sell tool calls record trades to memory."""

    def _fake_handler(self, result):
        """Return a handler function that returns the given result."""
        return lambda args: result

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "ticker": "ICONFUCIUS"})
    @patch("iconfucius.memory.append_trade")
    def test_buy_records_trade(self, mock_append, _mock_fetch, _mock_usd,
                               tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        from iconfucius.skills.executor import _HANDLERS
        original = _HANDLERS["trade_buy"]
        _HANDLERS["trade_buy"] = self._fake_handler(
            {"status": "ok", "display": "Bought!"})
        try:
            result = execute_tool("trade_buy",
                                  {"token_id": "29m8", "amount": 1000,
                                   "bot_name": "bot-1"},
                                  persona_name="iconfucius")
        finally:
            _HANDLERS["trade_buy"] = original
        assert result["status"] == "ok"
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][1]
        assert entry["action"] == "BUY"
        assert entry["token_id"] == "29m8"
        assert entry["ticker"] == "ICONFUCIUS"
        assert "bot-1" in entry["bots"]
        assert entry["amount_sats"] == 1000
        assert entry["price_sats"] == 1500
        assert "est_tokens" in entry

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "ticker": "ICONFUCIUS"})
    @patch("iconfucius.memory.append_trade")
    def test_sell_records_trade(self, mock_append, _mock_fetch, _mock_usd,
                                tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        from iconfucius.skills.executor import _HANDLERS
        original = _HANDLERS["trade_sell"]
        _HANDLERS["trade_sell"] = self._fake_handler(
            {"status": "ok", "display": "Sold!"})
        try:
            result = execute_tool("trade_sell",
                                  {"token_id": "29m8", "amount": 5000000,
                                   "bot_name": "bot-1"},
                                  persona_name="iconfucius")
        finally:
            _HANDLERS["trade_sell"] = original
        assert result["status"] == "ok"
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][1]
        assert entry["action"] == "SELL"
        assert entry["token_id"] == "29m8"
        assert entry["ticker"] == "ICONFUCIUS"
        assert entry["price_sats"] == 1500
        assert "est_sats_received" in entry

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "ticker": "ICONFUCIUS"})
    @patch("iconfucius.memory.append_trade")
    def test_sell_all_records_trade(self, mock_append, _mock_fetch, _mock_usd,
                                    tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        from iconfucius.skills.executor import _HANDLERS
        original = _HANDLERS["trade_sell"]
        _HANDLERS["trade_sell"] = self._fake_handler(
            {"status": "ok", "display": "Sold!"})
        try:
            result = execute_tool("trade_sell",
                                  {"token_id": "29m8", "amount": "all",
                                   "all_bots": True},
                                  persona_name="iconfucius")
        finally:
            _HANDLERS["trade_sell"] = original
        assert result["status"] == "ok"
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][1]
        assert entry["action"] == "SELL"
        assert entry["tokens_sold"] == "all"
        assert entry["token_id"] == "29m8"
        # sell-all should NOT have est_sats_received
        assert "est_sats_received" not in entry

    @patch("iconfucius.memory.append_trade")
    def test_failed_trade_not_recorded(self, mock_append):
        from iconfucius.skills.executor import _HANDLERS
        original = _HANDLERS["trade_buy"]
        _HANDLERS["trade_buy"] = self._fake_handler(
            {"status": "error", "error": "No wallet"})
        try:
            result = execute_tool("trade_buy",
                                  {"token_id": "29m8", "amount": 1000,
                                   "bot_name": "bot-1"},
                                  persona_name="iconfucius")
        finally:
            _HANDLERS["trade_buy"] = original
        assert result["status"] == "error"
        mock_append.assert_not_called()

    @patch("iconfucius.memory.append_trade")
    def test_no_persona_no_recording(self, mock_append):
        from iconfucius.skills.executor import _HANDLERS
        original = _HANDLERS["trade_buy"]
        _HANDLERS["trade_buy"] = self._fake_handler(
            {"status": "ok", "display": "Bought!"})
        try:
            result = execute_tool("trade_buy",
                                  {"token_id": "29m8", "amount": 1000,
                                   "bot_name": "bot-1"})
        finally:
            _HANDLERS["trade_buy"] = original
        assert result["status"] == "ok"
        mock_append.assert_not_called()

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "ticker": "ICONFUCIUS"})
    @patch("iconfucius.memory.append_trade",
           side_effect=Exception("disk full"))
    def test_recording_failure_is_silent(self, mock_append, _mock_fetch,
                                         _mock_usd):
        """Trade recording errors don't break the trade result."""
        from iconfucius.skills.executor import _HANDLERS
        original = _HANDLERS["trade_buy"]
        _HANDLERS["trade_buy"] = self._fake_handler(
            {"status": "ok", "display": "Bought!"})
        try:
            result = execute_tool("trade_buy",
                                  {"token_id": "29m8", "amount": 1000,
                                   "bot_name": "bot-1"},
                                  persona_name="iconfucius")
        finally:
            _HANDLERS["trade_buy"] = original
        assert result["status"] == "ok"


class TestMemoryToolHandlers:
    """Tests for memory_read_strategy, memory_read_learnings, memory_update."""

    def test_read_strategy_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = execute_tool("memory_read_strategy", {},
                              persona_name="test-persona")
        assert result["status"] == "ok"
        assert "No strategy" in result["display"]

    def test_read_strategy_with_content(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        from iconfucius.memory import write_strategy
        write_strategy("test-persona", "# My Strategy\nBuy low sell high")
        result = execute_tool("memory_read_strategy", {},
                              persona_name="test-persona")
        assert result["status"] == "ok"
        assert "Buy low sell high" in result["display"]

    def test_read_learnings_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = execute_tool("memory_read_learnings", {},
                              persona_name="test-persona")
        assert result["status"] == "ok"
        assert "No learnings" in result["display"]

    def test_read_learnings_with_content(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        from iconfucius.memory import write_learnings
        write_learnings("test-persona", "# Learnings\nVolume spikes matter")
        result = execute_tool("memory_read_learnings", {},
                              persona_name="test-persona")
        assert result["status"] == "ok"
        assert "Volume spikes matter" in result["display"]

    def test_update_strategy(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = execute_tool("memory_update",
                              {"file": "strategy", "content": "New strategy"},
                              persona_name="test-persona")
        assert result["status"] == "ok"
        assert "updated" in result["display"].lower()
        from iconfucius.memory import read_strategy
        assert read_strategy("test-persona") == "New strategy"

    def test_update_learnings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = execute_tool("memory_update",
                              {"file": "learnings", "content": "New learnings"},
                              persona_name="test-persona")
        assert result["status"] == "ok"
        from iconfucius.memory import read_learnings
        assert read_learnings("test-persona") == "New learnings"

    def test_update_invalid_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = execute_tool("memory_update",
                              {"file": "trades", "content": "Nope"},
                              persona_name="test-persona")
        assert result["status"] == "error"
        assert "Unknown file" in result["error"]

    def test_update_missing_params(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = execute_tool("memory_update", {},
                              persona_name="test-persona")
        assert result["status"] == "error"
        assert "required" in result["error"].lower()

    def test_no_persona_returns_error(self):
        result = execute_tool("memory_read_strategy", {})
        assert result["status"] == "error"
        assert "persona" in result["error"].lower()


class TestWalletBalanceResult:
    """wallet_balance returns structured JSON for the AI to summarize."""

    def test_returns_structured_data(self):
        fake_data = {
            "wallet_ckbtc_sats": 1000,
            "bots": [
                {"name": "bot-1", "principal": "bot1-principal-abc",
                 "odin_sats": 500, "has_odin_account": True,
                 "tokens": [
                    {"ticker": "CONF", "id": "29m8", "balance": 0.000001,
                     "div": 8, "value_sats": 200},
                ]},
            ],
            "totals": {
                "odin_sats": 500,
                "token_value_sats": 200,
                "portfolio_sats": 1700,
            },
            "_display": "table output",
        }
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=fake_data):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1"]):
                    result = execute_tool("wallet_balance", {})
        assert result["status"] == "ok"
        assert result["wallet_ckbtc_sats"] == 1000
        assert result["total_odin_sats"] == 500
        assert result["total_token_value_sats"] == 200
        assert result["portfolio_sats"] == 1700
        # Per-bot data included so AI doesn't need individual balance calls
        assert "bots" in result
        assert len(result["bots"]) == 1
        assert result["bots"][0]["name"] == "bot-1"
        assert result["bots"][0]["principal"] == "bot1-principal-abc"
        assert result["bots"][0]["odin_sats"] == 500
        assert result["bots"][0]["has_odin_account"] is True
        assert result["bots"][0]["tokens"][0]["ticker"] == "CONF"
        # No terminal output — AI summarizes from structured data
        assert "_terminal_output" not in result
        # Constraints surfaced for AI decision-making
        assert result["constraints"]["min_deposit_sats"] == 5000
        assert result["constraints"]["min_trade_sats"] == 500

    def test_includes_constraints(self):
        """constraints dict uses config constants so the AI respects minimums."""
        fake_data = {
            "wallet_ckbtc_sats": 0,
            "totals": {"odin_sats": 0, "token_value_sats": 0, "portfolio_sats": 0},
            "_display": "",
        }
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=fake_data):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1"]):
                    result = execute_tool("wallet_balance", {})
        assert result["status"] == "ok"
        assert result["constraints"] == {
            "min_deposit_sats": 5000,
            "min_trade_sats": 500,
        }

    def test_none_data_returns_error(self):
        with patch("iconfucius.cli.balance.run_all_balances",
                    return_value=None):
            with patch("iconfucius.config.require_wallet", return_value=True):
                with patch("iconfucius.config.get_bot_names",
                            return_value=["bot-1"]):
                    result = execute_tool("wallet_balance", {})
        assert result["status"] == "error"


class TestTokenDiscoverExecutor:
    """Tests for the token_discover agent skill."""

    _FAKE_TOKENS = [
        {
            "id": "abc1",
            "name": "AlphaToken",
            "ticker": "ALPHA",
            "price_sats": 2.0,
            "marketcap_sats": 50000000,
            "volume_24h_sats": 10000000,
            "holder_count": 150,
            "bonded": True,
            "twitter_verified": True,
            "safety": "bonded (graduated to AMM) · Twitter verified · 150 holders · not in known tokens registry",
        },
        {
            "id": "xyz2",
            "name": "BetaToken",
            "ticker": "BETA",
            "price_sats": 0.5,
            "marketcap_sats": 5000000,
            "volume_24h_sats": 1000000,
            "holder_count": 30,
            "bonded": True,
            "twitter_verified": False,
            "safety": "bonded (graduated to AMM) · Twitter NOT verified · 30 holders · not in known tokens registry",
        },
    ]

    def test_returns_tokens(self):
        with patch("iconfucius.tokens.discover_tokens",
                    return_value=self._FAKE_TOKENS):
            with patch("iconfucius.config.get_btc_to_usd_rate",
                        return_value=100000.0):
                result = execute_tool("token_discover",
                                      {"sort": "volume", "limit": 10})
        assert result["status"] == "ok"
        assert result["count"] == 2
        ids = [t["id"] for t in result["tokens"]]
        assert "abc1" in ids
        assert "xyz2" in ids

    def test_default_sort_is_volume(self):
        with patch("iconfucius.tokens.discover_tokens",
                    return_value=self._FAKE_TOKENS):
            with patch("iconfucius.config.get_btc_to_usd_rate",
                        return_value=100000.0):
                result = execute_tool("token_discover", {})
        assert result["status"] == "ok"
        assert result["sort"] == "volume"
        assert "trending" in result["display"].lower()

    def test_newest_sort(self):
        with patch("iconfucius.tokens.discover_tokens",
                    return_value=self._FAKE_TOKENS):
            with patch("iconfucius.config.get_btc_to_usd_rate",
                        return_value=100000.0):
                result = execute_tool("token_discover", {"sort": "newest"})
        assert result["status"] == "ok"
        assert result["sort"] == "newest"
        assert "newest" in result["display"].lower()

    def test_token_fields_present(self):
        with patch("iconfucius.tokens.discover_tokens",
                    return_value=self._FAKE_TOKENS[:1]):
            with patch("iconfucius.config.get_btc_to_usd_rate",
                        return_value=100000.0):
                result = execute_tool("token_discover", {"limit": 1})
        assert result["status"] == "ok"
        token = result["tokens"][0]
        assert "id" in token
        assert "name" in token
        assert "ticker" in token
        assert "price_sats" in token
        assert "marketcap_sats" in token
        assert "volume_24h_sats" in token
        assert "holder_count" in token
        assert "bonded" in token
        assert "safety" in token

    def test_empty_results(self):
        with patch("iconfucius.tokens.discover_tokens", return_value=[]):
            with patch("iconfucius.config.get_btc_to_usd_rate",
                        return_value=100000.0):
                result = execute_tool("token_discover", {})
        assert result["status"] == "ok"
        assert result["tokens"] == []
        assert result["count"] == 0
        assert "No tokens found" in result["display"]

    def test_display_includes_token_info(self):
        with patch("iconfucius.tokens.discover_tokens",
                    return_value=self._FAKE_TOKENS):
            with patch("iconfucius.config.get_btc_to_usd_rate",
                        return_value=100000.0):
                result = execute_tool("token_discover", {})
        assert "AlphaToken" in result["display"]
        assert "ALPHA" in result["display"]
        assert "abc1" in result["display"]


class TestTokenPriceExecutor:
    """Tests for the token_price agent skill."""

    _FAKE_API = {
        "id": "29m8",
        "name": "IConfucius",
        "ticker": "ICONFUCIUS",
        "price": 1500,
        "price_5m": 1500,
        "price_1h": 1400,
        "price_6h": 2000,
        "price_1d": 1000,
        "marketcap": 31500000000,
        "volume_24": 20000000000,
        "holder_count": 253,
        "btc_liquidity": 11000000000,
        "divisibility": 8,
        "bonded": True,
    }

    def test_returns_price_data(self):
        with patch("iconfucius.tokens._search_api", return_value=[]):
            with patch("iconfucius.tokens.fetch_token_data",
                        return_value=self._FAKE_API):
                with patch("iconfucius.config.get_btc_to_usd_rate",
                            return_value=100000.0):
                    result = execute_tool("token_price",
                                          {"query": "IConfucius"})
        assert result["status"] == "ok"
        assert result["token_id"] == "29m8"
        assert result["price_sats"] == 1.5  # 1500 msat / 1000
        assert result["ticker"] == "ICONFUCIUS"
        assert "IConfucius" in result["display"]

    def test_price_change_percentages(self):
        with patch("iconfucius.tokens._search_api", return_value=[]):
            with patch("iconfucius.tokens.fetch_token_data",
                        return_value=self._FAKE_API):
                with patch("iconfucius.config.get_btc_to_usd_rate",
                            return_value=100000.0):
                    result = execute_tool("token_price", {"query": "29m8"})
        # 1500 vs 1400 = +7.1%
        assert result["change_1h"] == "+7.1%"
        # 1500 vs 2000 = -25.0%
        assert result["change_6h"] == "-25.0%"
        # 1500 vs 1000 = +50.0%
        assert result["change_24h"] == "+50.0%"

    def test_missing_query_returns_error(self):
        result = execute_tool("token_price", {})
        assert result["status"] == "error"
        assert "required" in result["error"].lower()

    def test_unknown_token_returns_error(self):
        with patch("iconfucius.tokens._search_api", return_value=[]):
            result = execute_tool("token_price",
                                  {"query": "nonexistent_xyz_999"})
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_api_failure_returns_error(self):
        with patch("iconfucius.tokens._search_api", return_value=[]):
            with patch("iconfucius.tokens.fetch_token_data",
                        return_value=None):
                result = execute_tool("token_price",
                                      {"query": "IConfucius"})
        assert result["status"] == "error"
        assert "Could not fetch" in result["error"]

    def test_usd_rate_failure_graceful(self):
        with patch("iconfucius.tokens._search_api", return_value=[]):
            with patch("iconfucius.tokens.fetch_token_data",
                        return_value=self._FAKE_API):
                with patch("iconfucius.config.get_btc_to_usd_rate",
                            side_effect=Exception("offline")):
                    result = execute_tool("token_price",
                                          {"query": "IConfucius"})
        assert result["status"] == "ok"
        assert result["price_sats"] == 1.5  # 1500 msat / 1000
        assert result["price_usd"] is None
        assert "sats" in result["display"]


class TestTokensToSubunits:
    """Tests for human-readable tokens → raw sub-units conversion."""

    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"divisibility": 8})
    def test_basic_conversion(self, _mock):
        # 1000 tokens with div=8 → 100_000_000_000
        result = _tokens_to_subunits(1000.0, "29m8")
        assert result == 100_000_000_000

    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"divisibility": 0})
    def test_divisibility_zero(self, _mock):
        # div=0 → tokens are indivisible, 1:1
        result = _tokens_to_subunits(500.0, "abc")
        assert result == 500

    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"divisibility": 2})
    def test_divisibility_two(self, _mock):
        result = _tokens_to_subunits(10.5, "xyz")
        assert result == 1050

    @patch("iconfucius.tokens.fetch_token_data", return_value=None)
    def test_missing_data_defaults_to_8(self, _mock):
        result = _tokens_to_subunits(1.0, "unknown")
        assert result == 100_000_000

    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"divisibility": 8})
    def test_fractional_tokens(self, _mock):
        # 0.5 tokens with div=8 → 50_000_000
        result = _tokens_to_subunits(0.5, "29m8")
        assert result == 50_000_000


class TestUsdConversion:
    """Tests for USD-to-sats and USD-to-tokens conversion."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    def test_usd_to_sats(self, _mock):
        # $1 at $100k/BTC = 1000 sats
        assert _usd_to_sats(1.0) == 1000

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    def test_usd_to_sats_twenty_dollars(self, _mock):
        # $20 at $100k/BTC = 20,000 sats
        assert _usd_to_sats(20.0) == 20000

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8})
    def test_usd_to_tokens(self, _mock_fetch, _mock_usd):
        # $5 at $100k/BTC = 5000 sats
        # raw_tokens = 5000 * 1_000_000 * 10^8 / 1500
        tokens = _usd_to_tokens(5.0, "29m8")
        assert tokens > 0
        # Verify: value_sats = (tokens * 1500) / 10^8 / 10^6 ≈ 5000
        value_sats = (tokens * 1500) / (10 ** 8) / 1_000_000
        assert abs(value_sats - 5000) < 1  # within 1 sat

    @patch("iconfucius.tokens.fetch_token_data", return_value=None)
    def test_usd_to_tokens_no_price_raises(self, _mock):
        from pytest import raises
        with raises(ValueError, match="Could not fetch price"):
            _usd_to_tokens(5.0, "nonexistent")


class TestTradeUsdAmount:
    """Tests for amount_usd parameter in trade_buy and trade_sell."""

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    def test_buy_with_amount_usd(self, _mock_usd, tmp_path, monkeypatch):
        """trade_buy with amount_usd converts to sats."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        fake_results = [("bot-1", {"status": "ok", "action": "buy"})]
        with patch("iconfucius.config.require_wallet", return_value=True):
            with patch("iconfucius.cli.concurrent.run_per_bot",
                        return_value=fake_results):
                result = execute_tool("trade_buy", {
                    "token_id": "29m8",
                    "amount_usd": 20.0,
                    "bot_name": "bot-1",
                })
        assert result["status"] == "ok"
        assert result["succeeded"] == 1

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8})
    def test_sell_with_amount_usd(self, _mock_fetch, _mock_usd,
                                   tmp_path, monkeypatch):
        """trade_sell with amount_usd converts to raw tokens."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        fake_results = [("bot-1", {"status": "ok", "action": "sell"})]
        with patch("iconfucius.config.require_wallet", return_value=True):
            with patch("iconfucius.cli.concurrent.run_per_bot",
                        return_value=fake_results):
                result = execute_tool("trade_sell", {
                    "token_id": "29m8",
                    "amount_usd": 5.0,
                    "bot_name": "bot-1",
                })
        assert result["status"] == "ok"
        assert result["succeeded"] == 1

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    def test_buy_usd_does_not_mutate_args(self, _mock_usd, tmp_path, monkeypatch):
        """trade_buy with amount_usd must not write back into args dict."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        fake_results = [("bot-1", {"status": "ok", "action": "buy"})]
        args = {"token_id": "29m8", "amount_usd": 20.0, "bot_name": "bot-1"}
        with patch("iconfucius.config.require_wallet", return_value=True):
            with patch("iconfucius.cli.concurrent.run_per_bot",
                        return_value=fake_results):
                execute_tool("trade_buy", args)
        assert "amount" not in args

    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100000.0)
    @patch("iconfucius.tokens.fetch_token_data",
           return_value={"price": 1500, "divisibility": 8})
    def test_sell_usd_does_not_mutate_args(self, _mock_fetch, _mock_usd,
                                            tmp_path, monkeypatch):
        """trade_sell with amount_usd must not write raw subunits into args."""
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        fake_results = [("bot-1", {"status": "ok", "action": "sell"})]
        args = {"token_id": "29m8", "amount_usd": 5.0, "bot_name": "bot-1"}
        with patch("iconfucius.config.require_wallet", return_value=True):
            with patch("iconfucius.cli.concurrent.run_per_bot",
                        return_value=fake_results):
                execute_tool("trade_sell", args)
        assert "amount" not in args

    def test_buy_no_amount_returns_error(self):
        """trade_buy without amount or amount_usd returns error."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_buy", {
                "token_id": "29m8",
                "bot_name": "bot-1",
            })
        assert result["status"] == "error"

    def test_sell_no_amount_returns_error(self):
        """trade_sell without amount or amount_usd returns error."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_sell", {
                "token_id": "29m8",
                "bot_name": "bot-1",
            })
        assert result["status"] == "error"

    @patch("iconfucius.config.get_btc_to_usd_rate",
           side_effect=Exception("offline"))
    def test_buy_usd_conversion_failure(self, _mock):
        """trade_buy returns error when USD conversion fails."""
        with patch("iconfucius.config.require_wallet", return_value=True):
            result = execute_tool("trade_buy", {
                "token_id": "29m8",
                "amount_usd": 20.0,
                "bot_name": "bot-1",
            })
        assert result["status"] == "error"
        assert "USD conversion failed" in result["error"]


class TestAggregateTradeResults:
    """Tests for _aggregate_trade_results helper."""

    def test_all_succeeded(self):
        from iconfucius.skills.executor import _aggregate_trade_results
        results = [
            ("bot-1", {"status": "ok", "action": "buy", "amount": 3000}),
            ("bot-2", {"status": "ok", "action": "buy", "amount": 2500}),
        ]
        r = _aggregate_trade_results(results, "buy", "29m8")
        assert r["status"] == "ok"
        assert r["succeeded"] == 2
        assert r["failed"] == 0
        assert r["skipped"] == 0
        assert "Bought 29m8 from 2 bot(s)" in r["display"]
        assert r["details"] == [
            {"bot": "bot-1", "amount": 3000},
            {"bot": "bot-2", "amount": 2500},
        ]
        assert r["notes"] == []

    def test_mixed_results(self):
        from iconfucius.skills.executor import _aggregate_trade_results
        results = [
            ("bot-1", {"status": "ok", "action": "sell"}),
            ("bot-2", {"status": "skipped", "reason": "No tokens"}),
            ("bot-3", Exception("connection timeout")),
        ]
        r = _aggregate_trade_results(results, "sell", "29m8")
        assert r["status"] == "partial"
        assert r["succeeded"] == 1
        assert r["failed"] == 1
        assert r["skipped"] == 1

    def test_notes_from_capped_buy(self):
        from iconfucius.skills.executor import _aggregate_trade_results
        results = [
            ("bot-1", {"status": "ok", "action": "buy", "amount": 7371,
                       "note": "Requested 7,380 sats but bot-1 only had 7,371 sats on Odin.Fun. Buy amount was auto-capped."}),
        ]
        r = _aggregate_trade_results(results, "buy", "2r74")
        assert r["succeeded"] == 1
        assert r["details"] == [{"bot": "bot-1", "amount": 7371}]
        assert len(r["notes"]) == 1
        assert "auto-capped" in r["notes"][0]

    def test_all_skipped(self):
        from iconfucius.skills.executor import _aggregate_trade_results
        results = [
            ("bot-1", {"status": "skipped", "reason": "No tokens"}),
        ]
        r = _aggregate_trade_results(results, "sell", "29m8")
        assert r["status"] == "ok"
        assert r["succeeded"] == 0
        assert r["skipped"] == 1


class TestCheckUpdate:
    """Tests for the check_update tool handler."""

    def test_returns_no_update_when_cache_empty(self):
        from iconfucius.skills.executor import _update_cache
        _update_cache.clear()
        result = execute_tool("check_update", {})
        assert result["status"] == "ok"
        assert result["update_available"] is False
        assert result["latest_version"] is None
        assert result["upgrade_command"] == "/upgrade"

    def test_returns_update_when_cache_populated(self):
        from iconfucius.skills.executor import _update_cache
        _update_cache.clear()
        _update_cache["latest_version"] = "99.0.0"
        _update_cache["release_notes"] = "- New feature"
        try:
            result = execute_tool("check_update", {})
            assert result["status"] == "ok"
            assert result["update_available"] is True
            assert result["latest_version"] == "99.0.0"
            assert result["release_notes"] == "- New feature"
            assert result["upgrade_command"] == "/upgrade"
        finally:
            _update_cache.clear()

    def test_includes_running_version(self):
        from iconfucius import __version__
        from iconfucius.skills.executor import _update_cache
        _update_cache.clear()
        result = execute_tool("check_update", {})
        assert result["running_version"] == __version__


class TestAccountLookupExecutor:
    def test_missing_address_returns_error(self):
        result = execute_tool("account_lookup", {})
        assert result["status"] == "error"
        assert "Address is required" in result["error"]

    @patch("iconfucius.accounts.lookup_odin_account", return_value=None)
    def test_unknown_address_returns_not_found(self, mock_lookup):
        result = execute_tool("account_lookup", {"address": "zzzzz-zzzzz"})
        assert result["status"] == "ok"
        assert result["found"] is False
        assert "No Odin.fun account found" in result["display"]

    @patch("iconfucius.accounts.lookup_odin_account")
    def test_found_account_returns_details(self, mock_lookup):
        mock_lookup.return_value = {
            "principal": "abc-def-ghi",
            "username": "trader42",
            "btc_wallet_address": "bc1qfake",
            "btc_deposit_address": "bc1qdeposit",
            "bio": "I trade stuff",
            "avatar": None,
            "admin": False,
            "verified": True,
            "follower_count": 100,
            "following_count": 50,
            "created_at": "2024-01-01",
        }
        result = execute_tool("account_lookup", {"address": "abc-def-ghi"})
        assert result["status"] == "ok"
        assert result["found"] is True
        assert result["principal"] == "abc-def-ghi"
        assert result["username"] == "trader42"
        assert "trader42" in result["display"]
        assert "bc1qfake" in result["display"]
        assert "bc1qdeposit" in result["display"]
        assert "100" in result["display"]

    @patch("iconfucius.accounts.lookup_odin_account")
    def test_resolves_btc_address(self, mock_lookup):
        mock_lookup.return_value = {
            "principal": "resolved-principal",
            "username": None,
            "btc_wallet_address": "bc1qfake",
            "btc_deposit_address": None,
            "bio": None,
            "avatar": None,
            "admin": False,
            "verified": False,
            "follower_count": 0,
            "following_count": 0,
            "created_at": None,
        }
        result = execute_tool("account_lookup", {"address": "bc1qfake"})
        assert result["status"] == "ok"
        assert result["found"] is True
        assert result["principal"] == "resolved-principal"


# ---------------------------------------------------------------------------
# Tool definition content — ensures AI sees critical constraints
# ---------------------------------------------------------------------------


class TestWalletSendDefinition:
    """Verify wallet_send tool definition contains the BTC minimum and dual-mode info."""

    def _get_wallet_send_def(self):
        from iconfucius.skills.definitions import TOOLS
        for t in TOOLS:
            if t["name"] == "wallet_send":
                return t
        raise AssertionError("wallet_send not found in TOOL_DEFINITIONS")

    def test_description_mentions_btc_minimum(self):
        """AI must see the 50,000 sats minimum for BTC sends."""
        desc = self._get_wallet_send_def()["description"]
        assert "50,000" in desc

    def test_description_mentions_ic_principal(self):
        """AI must know it can send ckBTC to an IC principal."""
        desc = self._get_wallet_send_def()["description"]
        assert "principal" in desc.lower()

    def test_description_mentions_btc_address(self):
        """AI must know BTC address mode converts via ckBTC minter."""
        desc = self._get_wallet_send_def()["description"]
        assert "bc1" in desc
        assert "minter" in desc.lower()

    def test_description_forbids_below_minimum(self):
        """AI must see NEVER call with less than 50,000 sats."""
        desc = self._get_wallet_send_def()["description"]
        assert "NEVER" in desc
        assert "50,000" in desc

    def test_only_address_required(self):
        """amount is optional (amount_usd is an alternative), only address required."""
        schema = self._get_wallet_send_def()["input_schema"]
        assert schema["required"] == ["address"]

    def test_amount_field_mentions_btc_minimum(self):
        """amount field reminds AI of the 50,000 minimum for BTC addresses."""
        props = self._get_wallet_send_def()["input_schema"]["properties"]
        assert "50000" in props["amount"]["description"]

    def test_amount_usd_field_mentions_btc_minimum(self):
        """amount_usd field reminds AI of the 50,000 minimum for BTC addresses."""
        props = self._get_wallet_send_def()["input_schema"]["properties"]
        assert "50000" in props["amount_usd"]["description"]

    def test_address_field_describes_both_modes(self):
        """Address field describes both IC principal and BTC address."""
        props = self._get_wallet_send_def()["input_schema"]["properties"]
        addr_desc = props["address"]["description"]
        assert "principal" in addr_desc.lower()
        assert "bc1" in addr_desc

    def test_description_mentions_wallet_monitor(self):
        """AI should know to use wallet_monitor after a BTC send."""
        desc = self._get_wallet_send_def()["description"]
        assert "wallet_monitor" in desc


class TestWalletSendMonitorHintStripped:
    """Verify wallet_send strips the CLI-specific monitor command."""

    @patch("iconfucius.config.require_wallet", return_value="/tmp/fake.pem")
    def test_cli_monitor_hint_removed(self, mock_wallet):
        # Simulate CLI output that includes the monitor hint
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = (
            "BTC withdrawal initiated! Block index: 123\n"
            "BTC will arrive after the transaction is confirmed.\n"
            "Check progress with: iconfucius wallet balance --monitor\n"
            "Wallet balance: 5,000 sats"
        )

        with patch("typer.testing.CliRunner") as MockRunner:
            MockRunner.return_value.invoke.return_value = mock_result
            result = execute_tool("wallet_send", {
                "amount": "50000", "address": "bc1qfake",
            })

        assert result["status"] == "ok"
        assert "iconfucius wallet balance --monitor" not in result["display"]
        assert "BTC withdrawal initiated" in result["display"]
        assert result["hint"] == "Use wallet_monitor to check withdrawal progress."

    @patch("iconfucius.config.require_wallet", return_value="/tmp/fake.pem")
    def test_ckbtc_send_no_hint(self, mock_wallet):
        """ckBTC sends (no BTC withdrawal) should not get a hint."""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = "Transfer succeeded! Block index: 456"

        with patch("typer.testing.CliRunner") as MockRunner:
            MockRunner.return_value.invoke.return_value = mock_result
            result = execute_tool("wallet_send", {
                "amount": "5000", "address": "rrkah-fqaaa-aaaaa-aaaaq-cai",
            })

        assert result["status"] == "ok"
        assert "hint" not in result


class TestHowToFundWalletHandler:
    """Tests for the how_to_fund_wallet executor handler."""

    def test_no_wallet_returns_error(self):
        with patch("iconfucius.config.require_wallet", return_value=False):
            result = execute_tool("how_to_fund_wallet", {})
        assert result["status"] == "error"
        assert "wallet" in result["error"].lower()

    @patch("iconfucius.transfers.get_btc_address", return_value="bc1qfund123")
    @patch("iconfucius.transfers.create_ckbtc_minter")
    @patch("iconfucius.transfers.get_balance", return_value=0)
    @patch("iconfucius.transfers.create_icrc1_canister")
    @patch("icp_agent.Agent")
    @patch("icp_agent.Client")
    @patch("icp_identity.Identity")
    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_returns_structured_data(self, mock_rate, MockId, MockClient,
                                      MockAgent, mock_icrc1, mock_bal,
                                      mock_minter, mock_btc_addr, odin_project):
        mock_identity = MagicMock()
        mock_identity.sender.return_value = MagicMock(
            __str__=lambda s: "fund-principal"
        )
        MockId.from_pem.return_value = mock_identity
        MockId.return_value = MagicMock()

        result = execute_tool("how_to_fund_wallet", {})
        assert result["status"] == "ok"
        assert result["wallet_principal"] == "fund-principal"
        assert result["btc_deposit_address"] == "bc1qfund123"
        assert result["ckbtc_balance_sats"] == 0

    @patch("iconfucius.transfers.get_btc_address", return_value="bc1qfund123")
    @patch("iconfucius.transfers.create_ckbtc_minter")
    @patch("iconfucius.transfers.get_balance", return_value=0)
    @patch("iconfucius.transfers.create_icrc1_canister")
    @patch("icp_agent.Agent")
    @patch("icp_agent.Client")
    @patch("icp_identity.Identity")
    @patch("iconfucius.config.get_btc_to_usd_rate", return_value=100_000.0)
    def test_display_has_both_options(self, mock_rate, MockId, MockClient,
                                      MockAgent, mock_icrc1, mock_bal,
                                      mock_minter, mock_btc_addr, odin_project):
        mock_identity = MagicMock()
        mock_identity.sender.return_value = MagicMock(
            __str__=lambda s: "fund-principal"
        )
        MockId.from_pem.return_value = mock_identity
        MockId.return_value = MagicMock()

        result = execute_tool("how_to_fund_wallet", {})
        display = result["display"]
        assert "Option 1" in display
        assert "Option 2" in display
        assert "bc1qfund123" in display
        assert "fund-principal" in display
        assert "wallet_monitor" in display
        assert "~6 Bitcoin confirmations" in display
