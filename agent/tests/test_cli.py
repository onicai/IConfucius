"""Tests for iconfucius.cli — CLI routing, help, init, config commands."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest
from typer.testing import CliRunner

from iconfucius.cli import app, state, _resolve_bot_names
from iconfucius.cli.balance import BotBalances
from iconfucius.config import get_network, set_network

runner = CliRunner()

# Patch at source modules since wallet.py uses local imports
ID = "icp_identity.Identity"
AG = "icp_agent.Agent"
CL = "icp_agent.Client"
TR = "iconfucius.transfers"


# ---------------------------------------------------------------------------
# Help output
# ---------------------------------------------------------------------------

class TestHelpOutput:
    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool", return_value={
        "status": "ok", "config_exists": True, "wallet_exists": True,
        "env_exists": True, "has_api_key": True, "ready": True,
    })
    def test_no_args_starts_chat(self, mock_exec, mock_run_chat):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        mock_run_chat.assert_called_once()

    def test_help_flag(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Setup:" in result.output
        assert "How to use your bots:" in result.output

    def test_version_flag(self):
        import tomllib
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            version = tomllib.load(f)["project"]["version"]
        from iconfucius import __version__
        assert version == __version__, (
            f"pyproject.toml ({version}) != __init__.py ({__version__})"
        )
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "iconfucius" in result.output
        assert version in result.output

    def test_version_short_flag(self):
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "iconfucius" in result.output

    def test_help_lists_all_commands(self):
        result = runner.invoke(app, ["--help"])
        assert "init" in result.output
        assert "config" in result.output
        assert "balance" in result.output
        assert "fund" in result.output
        assert "withdraw" in result.output
        assert "trade" in result.output
        assert "wallet" in result.output
        assert "chat" in result.output
        assert "persona" in result.output

    def test_no_deposit_command(self):
        result = runner.invoke(app, ["--help"])
        # deposit command should be removed
        lines = result.output.split("\n")
        command_lines = [l for l in lines if l.strip().startswith("deposit")]
        assert len(command_lines) == 0


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Resolve bot names
# ---------------------------------------------------------------------------

class TestResolveBotNames:
    def test_global_bot(self, odin_project):
        state.bot_name = "bot-2"
        state.all_bots = False
        result = _resolve_bot_names()
        assert result == ["bot-2"]
        state.bot_name = None

    def test_per_command_bot(self, odin_project):
        state.bot_name = None
        state.all_bots = False
        result = _resolve_bot_names(bot="bot-3")
        assert result == ["bot-3"]

    def test_global_all_bots(self, odin_project):
        state.bot_name = None
        state.all_bots = True
        result = _resolve_bot_names()
        assert set(result) == {"bot-1", "bot-2", "bot-3"}
        state.all_bots = False

    def test_per_command_all_bots(self, odin_project):
        state.bot_name = None
        state.all_bots = False
        result = _resolve_bot_names(all_bots=True)
        assert set(result) == {"bot-1", "bot-2", "bot-3"}

    def test_no_flag_exits(self, odin_project):
        from click.exceptions import Exit
        state.bot_name = None
        state.all_bots = False
        with pytest.raises(Exit):
            _resolve_bot_names()


# ---------------------------------------------------------------------------
# Upgrade wizard (odin-bots → iconfucius migration)
# ---------------------------------------------------------------------------

class TestUpgradeWizard:
    def test_upgrade_renames_config(self, tmp_path, monkeypatch):
        """Accepting the upgrade renames odin-bots.toml → iconfucius.toml."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "odin-bots.toml").write_text("[bots.bot-1]\n")
        result = runner.invoke(app, ["config"], input="y\n")
        assert result.exit_code == 0
        assert not (tmp_path / "odin-bots.toml").exists()
        assert (tmp_path / "iconfucius.toml").exists()
        assert "Renamed odin-bots.toml" in result.output

    def test_upgrade_renames_global_dir(self, tmp_path, monkeypatch):
        """Upgrade renames ~/.odin-bots/ → ~/.iconfucius/ when it exists."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "odin-bots.toml").write_text("[bots.bot-1]\n")
        old_global = tmp_path / ".odin-bots"
        old_global.mkdir()
        (old_global / "tokens.toml").write_text("")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(app, ["config"], input="y\n")
        assert result.exit_code == 0
        assert not old_global.exists()
        assert (tmp_path / ".iconfucius").exists()
        assert (tmp_path / ".iconfucius" / "tokens.toml").exists()

    def test_upgrade_updates_gitignore_comment(self, tmp_path, monkeypatch):
        """Upgrade updates the .gitignore comment from odin-bots to iconfucius."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "odin-bots.toml").write_text("[bots.bot-1]\n")
        (tmp_path / ".gitignore").write_text("# odin-bots project\n.env\n")
        result = runner.invoke(app, ["config"], input="y\n")
        assert result.exit_code == 0
        content = (tmp_path / ".gitignore").read_text()
        assert "# iconfucius project" in content
        assert "# odin-bots project" not in content

    def test_upgrade_declined(self, tmp_path, monkeypatch):
        """Declining the upgrade leaves odin-bots.toml untouched."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "odin-bots.toml").write_text("[bots.bot-1]\n")
        result = runner.invoke(app, ["config"], input="n\n")
        assert result.exit_code == 0
        assert (tmp_path / "odin-bots.toml").exists()
        assert not (tmp_path / "iconfucius.toml").exists()

    def test_no_upgrade_when_new_config_exists(self, tmp_path, monkeypatch):
        """No upgrade prompt when iconfucius.toml already exists."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "odin-bots.toml").write_text("[bots.bot-1]\n")
        (tmp_path / "iconfucius.toml").write_text("[bots.bot-1]\n")
        result = runner.invoke(app, ["config"])
        assert "odin-bots" not in result.output.lower() or "upgrade" not in result.output.lower()

    def test_no_upgrade_when_no_old_config(self, tmp_path, monkeypatch):
        """No upgrade prompt when odin-bots.toml doesn't exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text("[bots.bot-1]\n")
        result = runner.invoke(app, ["config"])
        assert "odin-bots.toml" not in result.output


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------

class TestInitCommand:
    def test_creates_config_and_gitignore(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "iconfucius.toml").exists()
        assert (tmp_path / ".gitignore").exists()
        assert "Created iconfucius.toml" in result.output

    def test_refuses_overwrite_without_force(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text("existing")
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_force_overwrites(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        (tmp_path / "iconfucius.toml").write_text("old")
        result = runner.invoke(app, ["init", "--force"])
        assert result.exit_code == 0
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-1]" in content

    def test_creates_three_default_bots(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" in content
        assert "[bots.bot-3]" in content

    def test_bots_flag_one(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = runner.invoke(app, ["init", "--bots", "1"])
        assert result.exit_code == 0
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" not in content
        assert "bot-1" in result.output

    def test_bots_flag_five(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = runner.invoke(app, ["init", "--bots", "5"])
        assert result.exit_code == 0
        content = (tmp_path / "iconfucius.toml").read_text()
        for i in range(1, 6):
            assert f"[bots.bot-{i}]" in content
        assert "[bots.bot-6]" not in content
        assert "bot-5" in result.output

    def test_bots_short_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))
        result = runner.invoke(app, ["init", "-n", "2"])
        assert result.exit_code == 0
        content = (tmp_path / "iconfucius.toml").read_text()
        assert "[bots.bot-1]" in content
        assert "[bots.bot-2]" in content
        assert "[bots.bot-3]" not in content


# ---------------------------------------------------------------------------
# Config command
# ---------------------------------------------------------------------------

class TestConfigCommand:
    def teardown_method(self):
        set_network("prd")

    def test_shows_config(self, odin_project):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "bot-1" in result.output
        assert "bot-2" in result.output

    def test_prd_hides_network(self, odin_project):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "Network:" not in result.output

    def test_prd_shows_prd_canister_id(self, odin_project):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "g7qkb-iiaaa-aaaar-qb3za-cai" in result.output

    def test_testing_shows_network(self, odin_project):
        result = runner.invoke(app, ["--network", "testing", "config"])
        assert result.exit_code == 0
        assert "Network:" in result.output
        assert "testing" in result.output

    def test_testing_shows_testing_canister_id(self, odin_project):
        result = runner.invoke(app, ["--network", "testing", "config"])
        assert result.exit_code == 0
        assert "ho2u6-qaaaa-aaaar-qb34q-cai" in result.output

    def test_development_shows_network(self, odin_project):
        result = runner.invoke(app, ["--network", "development", "config"])
        assert result.exit_code == 0
        assert "Network:" in result.output
        assert "development" in result.output


# ---------------------------------------------------------------------------
# Command routing (mock run_* functions)
# ---------------------------------------------------------------------------

class TestFundRouting:
    @patch("iconfucius.cli.fund.run_fund")
    def test_fund_requires_bot_flag(self, mock_run_fund, odin_project):
        result = runner.invoke(app, ["fund", "5000"])
        assert result.exit_code == 1
        assert "--bot" in result.output
        assert "--all-bots" in result.output
        mock_run_fund.assert_not_called()

    @patch("iconfucius.cli.fund.run_fund")
    def test_fund_bot_before_command(self, mock_run_fund, odin_project):
        result = runner.invoke(app, ["--bot", "bot-2", "fund", "3000"])
        args = mock_run_fund.call_args
        assert args.kwargs["bot_names"] == ["bot-2"]
        assert args.kwargs["amount"] == 3000

    @patch("iconfucius.cli.fund.run_fund")
    def test_fund_bot_after_command(self, mock_run_fund, odin_project):
        result = runner.invoke(app, ["fund", "3000", "--bot", "bot-2"])
        args = mock_run_fund.call_args
        assert args.kwargs["bot_names"] == ["bot-2"]

    @patch("iconfucius.cli.fund.run_fund")
    def test_fund_all_bots_before_command(self, mock_run_fund, odin_project):
        result = runner.invoke(app, ["--all-bots", "fund", "1000"])
        args = mock_run_fund.call_args
        assert set(args.kwargs["bot_names"]) == {"bot-1", "bot-2", "bot-3"}

    @patch("iconfucius.cli.fund.run_fund")
    def test_fund_all_bots_after_command(self, mock_run_fund, odin_project):
        result = runner.invoke(app, ["fund", "1000", "--all-bots"])
        args = mock_run_fund.call_args
        assert set(args.kwargs["bot_names"]) == {"bot-1", "bot-2", "bot-3"}


class TestWithdrawRouting:
    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_withdraw_requires_bot_flag(self, mock_run_withdraw, odin_project):
        result = runner.invoke(app, ["withdraw", "1000"])
        assert result.exit_code == 1
        assert "--bot" in result.output
        mock_run_withdraw.assert_not_called()

    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_withdraw_bot_before_command(self, mock_run_withdraw, odin_project):
        result = runner.invoke(app, ["--bot", "bot-1", "withdraw", "1000"])
        mock_run_withdraw.assert_called_once()
        args = mock_run_withdraw.call_args
        assert args.kwargs["amount"] == "1000"
        assert args.kwargs["bot_name"] == "bot-1"

    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_withdraw_bot_after_command(self, mock_run_withdraw, odin_project):
        result = runner.invoke(app, ["withdraw", "1000", "--bot", "bot-1"])
        mock_run_withdraw.assert_called_once()
        args = mock_run_withdraw.call_args
        assert args.kwargs["bot_name"] == "bot-1"

    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_withdraw_all_bots_before_command(self, mock_run_withdraw, odin_project):
        result = runner.invoke(app, ["--all-bots", "withdraw", "all"])
        assert mock_run_withdraw.call_count == 3

    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_withdraw_all_bots_after_command(self, mock_run_withdraw, odin_project):
        result = runner.invoke(app, ["withdraw", "all", "--all-bots"])
        assert mock_run_withdraw.call_count == 3


class TestTradeRouting:
    @patch("iconfucius.cli.trade.run_trade")
    def test_trade_requires_bot_flag(self, mock_run_trade, odin_project):
        result = runner.invoke(app, ["trade", "buy", "29m8", "1000"])
        assert result.exit_code == 1
        assert "--bot" in result.output
        mock_run_trade.assert_not_called()

    @patch("iconfucius.cli.trade.run_trade")
    def test_trade_bot_before_command(self, mock_run_trade, odin_project):
        result = runner.invoke(app, ["--bot", "bot-1", "trade", "buy", "29m8", "1000"])
        mock_run_trade.assert_called_once()
        args = mock_run_trade.call_args
        assert args.kwargs["action"] == "buy"
        assert args.kwargs["token_id"] == "29m8"
        assert args.kwargs["amount"] == "1000"

    @patch("iconfucius.cli.trade.run_trade")
    def test_trade_bot_after_command(self, mock_run_trade, odin_project):
        result = runner.invoke(app, ["trade", "buy", "29m8", "1000", "--bot", "bot-1"])
        mock_run_trade.assert_called_once()
        args = mock_run_trade.call_args
        assert args.kwargs["bot_name"] == "bot-1"

    @patch("iconfucius.cli.trade.run_trade")
    def test_trade_sell(self, mock_run_trade, odin_project):
        result = runner.invoke(app, ["--bot", "bot-1", "trade", "sell", "29m8", "500"])
        args = mock_run_trade.call_args
        assert args.kwargs["action"] == "sell"


# ---------------------------------------------------------------------------
# Sweep command
# ---------------------------------------------------------------------------

class TestSweepRouting:
    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_sweep_requires_bot_flag(self, mock_collect, mock_trade, mock_withdraw,
                                      odin_project):
        result = runner.invoke(app, ["sweep"])
        assert result.exit_code == 1
        assert "--bot" in result.output
        mock_collect.assert_not_called()

    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_sweep_single_bot(self, mock_collect, mock_trade, mock_withdraw,
                               odin_project):
        mock_collect.return_value = BotBalances(
            bot_name="bot-1", bot_principal="principal-1", odin_sats=5000,
            token_holdings=[
                {"ticker": "TEST", "token_id": "29m8", "balance": 1000, "value_sats": 5.0},
                {"ticker": "DOG", "token_id": "2jjj", "balance": 2000, "value_sats": 3.0},
            ],
        )
        result = runner.invoke(app, ["--bot", "bot-1", "sweep"])
        # Should sell both tokens then withdraw
        assert mock_trade.call_count == 2
        assert mock_trade.call_args_list[0] == call(
            bot_name="bot-1", action="sell", token_id="29m8", amount="all",
            verbose=True,
        )
        assert mock_trade.call_args_list[1] == call(
            bot_name="bot-1", action="sell", token_id="2jjj", amount="all",
            verbose=True,
        )
        mock_withdraw.assert_called_once_with(
            bot_name="bot-1", amount="all", verbose=True,
        )

    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_sweep_all_bots(self, mock_collect, mock_trade, mock_withdraw,
                             odin_project):
        mock_collect.side_effect = [
            BotBalances(bot_name="bot-1", bot_principal="p1", odin_sats=5000,
                        token_holdings=[{"ticker": "T", "token_id": "29m8",
                                         "balance": 100, "value_sats": 1.0}]),
            BotBalances(bot_name="bot-2", bot_principal="p2", odin_sats=3000,
                        token_holdings=[]),
            BotBalances(bot_name="bot-3", bot_principal="p3", odin_sats=0,
                        token_holdings=[]),
        ]
        result = runner.invoke(app, ["--all-bots", "sweep"])
        # bot-1 has 1 token, bot-2 and bot-3 have none
        assert mock_trade.call_count == 1
        assert mock_trade.call_args == call(
            bot_name="bot-1", action="sell", token_id="29m8", amount="all",
            verbose=True,
        )
        # All 3 bots should attempt withdraw
        assert mock_withdraw.call_count == 3

    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_sweep_no_holdings(self, mock_collect, mock_trade, mock_withdraw,
                                odin_project):
        mock_collect.return_value = BotBalances(
            bot_name="bot-1", bot_principal="p1", odin_sats=1000,
            token_holdings=[],
        )
        result = runner.invoke(app, ["sweep", "--bot", "bot-1"])
        mock_trade.assert_not_called()
        mock_withdraw.assert_called_once()

    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_sweep_skips_zero_balance_tokens(self, mock_collect, mock_trade,
                                              mock_withdraw, odin_project):
        mock_collect.return_value = BotBalances(
            bot_name="bot-1", bot_principal="p1", odin_sats=1000,
            token_holdings=[
                {"ticker": "T1", "token_id": "aaa", "balance": 500, "value_sats": 1.0},
                {"ticker": "T2", "token_id": "bbb", "balance": 0, "value_sats": 0.0},
            ],
        )
        result = runner.invoke(app, ["sweep", "--bot", "bot-1"])
        # Only T1 sold (T2 has zero balance)
        assert mock_trade.call_count == 1
        assert mock_trade.call_args[1]["token_id"] == "aaa"


# ---------------------------------------------------------------------------
# Network option
# ---------------------------------------------------------------------------

class TestNetworkOption:
    def teardown_method(self):
        set_network("prd")

    def test_default_network_is_prd(self, odin_project):
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert get_network() == "prd"

    def test_network_before_command(self, odin_project):
        result = runner.invoke(app, ["--network", "testing", "config"])
        assert result.exit_code == 0
        assert get_network() == "testing"

    def test_network_after_command(self, odin_project):
        result = runner.invoke(app, ["config", "--network", "testing"])
        assert result.exit_code == 0
        assert "testing" in result.output

    @patch("iconfucius.cli.fund.run_fund")
    def test_network_with_fund(self, mock_run_fund, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-1", "fund", "5000",
        ])
        assert get_network() == "testing"
        mock_run_fund.assert_called_once()

    def test_invalid_network(self, odin_project):
        result = runner.invoke(app, ["--network", "staging", "config"])
        # set_network raises ValueError, Typer catches it
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Option placement flexibility (--network, --bot, --all-bots anywhere)
# ---------------------------------------------------------------------------

class TestOptionPlacement:
    """Verify --network, --bot, and --all-bots work before and after commands."""

    def teardown_method(self):
        set_network("prd")

    # --network placement with config

    def test_network_before_config(self, odin_project):
        result = runner.invoke(app, ["--network", "testing", "config"])
        assert result.exit_code == 0
        assert "ho2u6-qaaaa-aaaar-qb34q-cai" in result.output

    def test_network_after_config(self, odin_project):
        result = runner.invoke(app, ["config", "--network", "testing"])
        assert result.exit_code == 0
        assert "ho2u6-qaaaa-aaaar-qb34q-cai" in result.output

    # --network placement with wallet balance

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_network_before_wallet_balance(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "wallet", "balance", "--bot", "bot-1",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_network_after_wallet_balance(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "wallet", "balance", "--bot", "bot-1", "--network", "testing",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    # --network placement with wallet info

    @patch(f"{TR}.unwrap_canister_result", return_value=0)
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.get_pending_btc", return_value=0)
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=25000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_network_before_wallet_info(self, MockIdentity, MockClient,
                                         MockAgent, mock_create, mock_get_bal,
                                         mock_minter, mock_pending,
                                         mock_btc_addr, mock_withdrawal_acct,
                                         mock_unwrap, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, [
            "--network", "testing", "wallet", "info",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    @patch(f"{TR}.unwrap_canister_result", return_value=0)
    @patch(f"{TR}.get_withdrawal_account",
           return_value={"owner": "minter", "subaccount": []})
    @patch(f"{TR}.get_btc_address", return_value="bc1qtest123")
    @patch(f"{TR}.get_pending_btc", return_value=0)
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(f"{TR}.get_balance", return_value=25000)
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_network_after_wallet_info(self, MockIdentity, MockClient,
                                        MockAgent, mock_create, mock_get_bal,
                                        mock_minter, mock_pending,
                                        mock_btc_addr, mock_withdrawal_acct,
                                        mock_unwrap, odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, [
            "wallet", "info", "--network", "testing",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    # --network placement with wallet receive

    @patch("iconfucius.cli.balance.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{TR}.get_balance", return_value=10000)
    @patch(f"{TR}.get_btc_address", return_value="bc1qtestaddr123")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_network_before_wallet_receive(self, MockIdentity, MockClient,
                                            MockAgent, mock_minter,
                                            mock_ckbtc, mock_btc_addr,
                                            mock_get_bal, mock_rate,
                                            odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, [
            "--network", "testing", "wallet", "receive",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    @patch("iconfucius.cli.balance.get_btc_to_usd_rate", return_value=100_000.0)
    @patch(f"{TR}.get_balance", return_value=10000)
    @patch(f"{TR}.get_btc_address", return_value="bc1qtestaddr123")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(f"{TR}.create_ckbtc_minter")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_network_after_wallet_receive(self, MockIdentity, MockClient,
                                           MockAgent, mock_minter,
                                           mock_ckbtc, mock_btc_addr,
                                           mock_get_bal, mock_rate,
                                           odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "test-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()

        result = runner.invoke(app, [
            "wallet", "receive", "--network", "testing",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    # --network placement with wallet send

    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.transfer", return_value={"Ok": 42})
    @patch(f"{TR}.get_balance")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_network_before_wallet_send(self, MockIdentity, MockClient,
                                         MockAgent, mock_create, mock_get_bal,
                                         mock_transfer, mock_unwrap,
                                         odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()
        mock_get_bal.side_effect = [5000, 3990]

        result = runner.invoke(app, [
            "--network", "testing", "wallet", "send", "1000", "dest-principal",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    @patch(f"{TR}.unwrap_canister_result", side_effect=lambda x: x)
    @patch(f"{TR}.transfer", return_value={"Ok": 42})
    @patch(f"{TR}.get_balance")
    @patch(f"{TR}.create_icrc1_canister")
    @patch(AG)
    @patch(CL)
    @patch(ID)
    def test_network_after_wallet_send(self, MockIdentity, MockClient,
                                        MockAgent, mock_create, mock_get_bal,
                                        mock_transfer, mock_unwrap,
                                        odin_project):
        mock_id = MagicMock()
        mock_id.sender.return_value = MagicMock(
            __str__=lambda s: "ctrl-principal"
        )
        MockIdentity.from_pem.return_value = mock_id
        MockIdentity.return_value = MagicMock()
        mock_get_bal.side_effect = [5000, 3990]

        result = runner.invoke(app, [
            "wallet", "send", "1000", "dest-principal", "--network", "testing",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    # --network placement with instructions

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_network_before_instructions(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-1", "instructions",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_network_after_instructions(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "instructions", "--bot", "bot-1", "--network", "testing",
        ])
        assert result.exit_code == 0
        assert get_network() == "testing"

    # --network placement with fund

    @patch("iconfucius.cli.fund.run_fund")
    def test_network_before_fund(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-1", "fund", "5000",
        ])
        assert result.exit_code == 0

    @patch("iconfucius.cli.fund.run_fund")
    def test_network_after_fund(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--bot", "bot-1", "fund", "5000", "--network", "testing",
        ])
        assert result.exit_code == 0

    # --network placement with withdraw

    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_network_before_withdraw(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-1", "withdraw", "1000",
        ])
        assert result.exit_code == 0

    @patch("iconfucius.cli.withdraw.run_withdraw")
    def test_network_after_withdraw(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--bot", "bot-1", "withdraw", "1000", "--network", "testing",
        ])
        assert result.exit_code == 0

    # --network placement with trade

    @patch("iconfucius.cli.trade.run_trade")
    def test_network_before_trade(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-1", "trade", "buy", "29m8", "1000",
        ])
        assert result.exit_code == 0

    @patch("iconfucius.cli.trade.run_trade")
    def test_network_after_trade(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--bot", "bot-1", "trade", "buy", "29m8", "1000", "--network", "testing",
        ])
        assert result.exit_code == 0

    # --network placement with sweep

    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_network_before_sweep(self, mock_collect, mock_trade, mock_withdraw,
                                   odin_project):
        mock_collect.return_value = BotBalances(
            bot_name="bot-1", bot_principal="p1", odin_sats=0, token_holdings=[],
        )
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-1", "sweep",
        ])
        assert result.exit_code == 0

    @patch("iconfucius.cli.withdraw.run_withdraw")
    @patch("iconfucius.cli.trade.run_trade")
    @patch("iconfucius.cli.balance.collect_balances")
    def test_network_after_sweep(self, mock_collect, mock_trade, mock_withdraw,
                                  odin_project):
        mock_collect.return_value = BotBalances(
            bot_name="bot-1", bot_principal="p1", odin_sats=0, token_holdings=[],
        )
        result = runner.invoke(app, [
            "--bot", "bot-1", "sweep", "--network", "testing",
        ])
        assert result.exit_code == 0

    # --bot placement with --network

    @patch("iconfucius.cli.fund.run_fund")
    def test_bot_before_network_before_command(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--bot", "bot-2", "--network", "testing", "fund", "5000",
        ])
        args = mock_run.call_args
        assert args.kwargs["bot_names"] == ["bot-2"]

    @patch("iconfucius.cli.fund.run_fund")
    def test_network_before_bot_before_command(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--bot", "bot-2", "fund", "5000",
        ])
        args = mock_run.call_args
        assert args.kwargs["bot_names"] == ["bot-2"]

    @patch("iconfucius.cli.fund.run_fund")
    def test_bot_after_command_network_after_command(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "fund", "5000", "--bot", "bot-2", "--network", "testing",
        ])
        assert result.exit_code == 0
        args = mock_run.call_args
        assert args.kwargs["bot_names"] == ["bot-2"]

    # --all-bots placement with --network

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_all_bots_before_network_wallet_balance(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--all-bots", "wallet", "balance", "--network", "testing",
        ])
        assert result.exit_code == 0
        args = mock_run.call_args
        assert set(args.kwargs["bot_names"]) == {"bot-1", "bot-2", "bot-3"}

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_network_before_all_bots_before_wallet_balance(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "--network", "testing", "--all-bots", "wallet", "balance",
        ])
        assert result.exit_code == 0
        args = mock_run.call_args
        assert set(args.kwargs["bot_names"]) == {"bot-1", "bot-2", "bot-3"}

    @patch("iconfucius.cli.balance.run_all_balances")
    def test_wallet_balance_all_bots_network_at_command(self, mock_run, odin_project):
        result = runner.invoke(app, [
            "wallet", "balance", "--all-bots", "--network", "testing",
        ])
        assert result.exit_code == 0
        args = mock_run.call_args
        assert set(args.kwargs["bot_names"]) == {"bot-1", "bot-2", "bot-3"}


# ---------------------------------------------------------------------------
# Onboarding wizard (_start_chat)
# ---------------------------------------------------------------------------

class TestStartChatWizard:
    """Tests for the interactive setup wizard in _start_chat().

    Wizard order: init → API key → wallet create → show address → chat.
    """

    def _ready_status(self):
        return {
            "status": "ok", "config_exists": True, "wallet_exists": True,
            "env_exists": True, "has_api_key": True, "ready": True,
        }

    def _no_config_status(self):
        return {
            "status": "ok", "config_exists": False, "wallet_exists": False,
            "env_exists": False, "has_api_key": False, "ready": False,
        }

    def _after_init_status(self):
        """After init: config exists, but no API key and no wallet yet."""
        return {
            "status": "ok", "config_exists": True, "wallet_exists": False,
            "env_exists": True, "has_api_key": False, "ready": False,
        }

    def _no_wallet_status(self):
        return {
            "status": "ok", "config_exists": True, "wallet_exists": False,
            "env_exists": True, "has_api_key": True, "ready": False,
        }

    def _no_api_key_status(self):
        return {
            "status": "ok", "config_exists": True, "wallet_exists": True,
            "env_exists": True, "has_api_key": False, "ready": False,
        }

    def _how_to_fund_wallet_result(self):
        return {
            "status": "ok",
            "display": "Wallet balance: 0 sats\n\nOption 1: ...\nOption 2: ...",
            "wallet_principal": "abc-principal",
            "btc_deposit_address": "bc1qtest123",
            "ckbtc_balance_sats": 0,
        }

    # --- Config init prompts ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["n"])
    def test_decline_init_exits(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_config_status()
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "iconfucius init" in result.output
        mock_chat.assert_not_called()

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_ctrl_c_during_init_prompt(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_config_status()
        result = runner.invoke(app, [])
        mock_chat.assert_not_called()

    # --- Bot count prompt ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y", "5"])
    def test_custom_bot_count(self, mock_input, mock_exec, mock_chat):
        """User enters 5 for bot count."""
        calls = []

        def track_exec(name, args):
            calls.append((name, args))
            if name == "setup_status" and not _calls_with(calls, "init"):
                return self._no_config_status()
            if name == "init":
                return {"status": "ok", "display": "Created iconfucius.toml"}
            return self._ready_status()

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        init_calls = [(n, a) for n, a in calls if n == "init"]
        assert len(init_calls) == 1
        assert init_calls[0][1] == {"num_bots": 5}

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y", ""])
    def test_empty_bot_count_defaults_to_three(self, mock_input, mock_exec, mock_chat):
        """Pressing Enter at bot count prompt uses default of 3."""
        calls = []

        def track_exec(name, args):
            calls.append((name, args))
            if name == "setup_status" and not _calls_with(calls, "init"):
                return self._no_config_status()
            if name == "init":
                return {"status": "ok", "display": "Created iconfucius.toml"}
            return self._ready_status()

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        init_calls = [(n, a) for n, a in calls if n == "init"]
        assert init_calls[0][1] == {"num_bots": 3}

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y", "abc"])
    def test_invalid_bot_count_uses_default(self, mock_input, mock_exec, mock_chat):
        calls = []

        def track_exec(name, args):
            calls.append((name, args))
            if name == "setup_status" and not _calls_with(calls, "init"):
                return self._no_config_status()
            if name == "init":
                return {"status": "ok", "display": "Created iconfucius.toml"}
            return self._ready_status()

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        assert "Invalid number" in result.output
        init_calls = [(n, a) for n, a in calls if n == "init"]
        assert init_calls[0][1] == {"num_bots": 3}

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y", KeyboardInterrupt])
    def test_ctrl_c_during_bot_count(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_config_status()
        result = runner.invoke(app, [])
        mock_chat.assert_not_called()

    # --- Init output ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y", "3"])
    def test_init_shows_clean_message(self, mock_input, mock_exec, mock_chat):
        """Wizard prints its own message, not the raw CLI output."""
        calls = []

        def track_exec(name, args):
            calls.append((name, args))
            if name == "setup_status" and not _calls_with(calls, "init"):
                return self._no_config_status()
            if name == "init":
                return {"status": "ok", "display": "lots of CLI output"}
            return self._ready_status()

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        assert "Created project with 3 bot(s): bot-1, bot-2, bot-3" in result.output
        # Raw CLI output should NOT appear
        assert "lots of CLI output" not in result.output

    # --- API key prompt (asked BEFORE wallet) ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["sk-ant-test-key-123"])
    def test_api_key_prompt_saves_to_env(self, mock_input, mock_exec, mock_chat,
                                         tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_exec.return_value = self._no_api_key_status()

        env_path = tmp_path / ".env"
        env_path.write_text("ANTHROPIC_API_KEY=your-api-key-here\n")

        result = runner.invoke(app, [])
        content = env_path.read_text()
        assert "sk-ant-test-key-123" in content
        assert "your-api-key-here" not in content
        assert "Saved API key" in result.output

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["sk-ant-my-key"])
    def test_api_key_creates_env_if_missing(self, mock_input, mock_exec, mock_chat,
                                             tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_exec.return_value = self._no_api_key_status()

        env_path = tmp_path / ".env"
        assert not env_path.exists()

        result = runner.invoke(app, [])
        assert env_path.exists()
        assert env_path.read_text() == "ANTHROPIC_API_KEY=sk-ant-my-key\n"

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["sk-ant-new-key"])
    def test_api_key_replaces_existing_value(self, mock_input, mock_exec, mock_chat,
                                              tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_exec.return_value = self._no_api_key_status()

        env_path = tmp_path / ".env"
        env_path.write_text("OTHER_VAR=hello\nANTHROPIC_API_KEY=old-key\n")

        result = runner.invoke(app, [])
        content = env_path.read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-new-key" in content
        assert "OTHER_VAR=hello" in content
        assert "old-key" not in content

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["sk-ant-appended"])
    def test_api_key_appends_to_env_without_key(self, mock_input, mock_exec, mock_chat,
                                                 tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_exec.return_value = self._no_api_key_status()

        env_path = tmp_path / ".env"
        env_path.write_text("OTHER_VAR=hello\n")

        result = runner.invoke(app, [])
        content = env_path.read_text()
        assert "OTHER_VAR=hello" in content
        assert "ANTHROPIC_API_KEY=sk-ant-appended" in content

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=[""])
    def test_empty_api_key_exits(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_api_key_status()
        result = runner.invoke(app, [])
        assert "No key entered" in result.output
        mock_chat.assert_not_called()

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_ctrl_c_during_api_key_prompt(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_api_key_status()
        result = runner.invoke(app, [])
        mock_chat.assert_not_called()

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["sk-ant-key"])
    def test_api_key_sets_environ(self, mock_input, mock_exec, mock_chat,
                                   tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_exec.return_value = self._no_api_key_status()
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = runner.invoke(app, [])
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-key"

    # --- Wallet create prompts (asked AFTER API key) ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["n"])
    def test_decline_wallet_create_exits(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_wallet_status()
        result = runner.invoke(app, [])
        assert "iconfucius wallet create" in result.output
        mock_chat.assert_not_called()

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_ctrl_c_during_wallet_prompt(self, mock_input, mock_exec, mock_chat):
        mock_exec.return_value = self._no_wallet_status()
        result = runner.invoke(app, [])
        mock_chat.assert_not_called()

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y"])
    def test_wallet_create_shows_address(self, mock_input, mock_exec, mock_chat):
        """After wallet creation, wizard shows principal and deposit address."""
        calls = []

        def track_exec(name, args):
            calls.append((name, args))
            if name == "setup_status" and not _calls_with(calls, "wallet_create"):
                return self._no_wallet_status()
            if name == "wallet_create":
                return {"status": "ok", "display": "Wallet created"}
            if name == "how_to_fund_wallet":
                return self._how_to_fund_wallet_result()
            return self._ready_status()

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        assert "Wallet created." in result.output
        assert "Option 1" in result.output or "Option 2" in result.output

    # --- Full wizard flow ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["y", "2", "sk-ant-full-flow", "y"])
    def test_full_wizard_flow(self, mock_input, mock_exec, mock_chat,
                               tmp_path, monkeypatch):
        """Full flow: init → API key → wallet → chat."""
        monkeypatch.chdir(tmp_path)
        step = {"n": 0}  # track wizard progression

        def track_exec(name, args):
            if name == "setup_status":
                if step["n"] == 0:
                    return self._no_config_status()
                if step["n"] == 1:
                    return self._after_init_status()
                return self._ready_status()
            if name == "init":
                step["n"] = 1
                return {"status": "ok", "display": "done"}
            if name == "wallet_create":
                step["n"] = 2
                return {"status": "ok", "display": "done"}
            if name == "how_to_fund_wallet":
                return self._how_to_fund_wallet_result()
            return {"status": "ok"}

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        # Verify wizard reached chat
        mock_chat.assert_called_once()
        # Verify all prompts were consumed
        assert "Created project with 2 bot(s)" in result.output

    # --- Wizard order: API key before wallet ---

    @patch("iconfucius.cli.chat.run_chat")
    @patch("iconfucius.skills.executor.execute_tool")
    @patch("builtins.input", side_effect=["sk-ant-key", "y"])
    def test_api_key_asked_before_wallet(self, mock_input, mock_exec, mock_chat,
                                          tmp_path, monkeypatch):
        """When both API key and wallet are missing, API key is asked first."""
        monkeypatch.chdir(tmp_path)
        calls = []

        def track_exec(name, args):
            calls.append(name)
            if name == "setup_status" and "wallet_create" not in calls:
                # Config exists, but no API key and no wallet
                return {
                    "status": "ok", "config_exists": True, "wallet_exists": False,
                    "env_exists": True, "has_api_key": False, "ready": False,
                }
            if name == "wallet_create":
                return {"status": "ok", "display": "done"}
            if name == "how_to_fund_wallet":
                return self._how_to_fund_wallet_result()
            return self._ready_status()

        mock_exec.side_effect = track_exec
        result = runner.invoke(app, [])
        # API key prompt comes first (consumed "sk-ant-key"),
        # then wallet prompt (consumed "y")
        assert "Saved API key" in result.output
        assert "Wallet created." in result.output


def _calls_with(calls, name):
    """Helper: return calls matching a tool name."""
    return [c for c in calls if c[0] == name]
