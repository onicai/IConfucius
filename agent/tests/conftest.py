"""Shared fixtures for iconfucius tests."""

import os

import pytest

import iconfucius.config as cfg


@pytest.fixture
def odin_project(tmp_path, monkeypatch):
    """Set up a minimal iconfucius project with config + wallet in a temp directory."""
    monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))

    config_content = """\
[settings]

[bots.bot-1]
description = "Bot 1"

[bots.bot-2]
description = "Bot 2"

[bots.bot-3]
description = "Bot 3"
"""
    (tmp_path / "iconfucius.toml").write_text(config_content)

    wallet_dir = tmp_path / ".wallet"
    wallet_dir.mkdir()
    pem = wallet_dir / "identity-private.pem"
    pem.write_text(
        "-----BEGIN PRIVATE KEY-----\n"
        "MC4CAQAwBQYDK2VwBCIEIJ3tspvKM2eCVt34SmVvcNu9bTmtPEf8GUVot2J77spK\n"
        "-----END PRIVATE KEY-----\n"
    )

    # Clear config cache
    cfg._cached_config = None
    cfg._cached_config_path = None

    yield tmp_path

    cfg._cached_config = None
    cfg._cached_config_path = None


@pytest.fixture
def odin_project_no_wallet(tmp_path, monkeypatch):
    """Set up an iconfucius project without a wallet."""
    monkeypatch.setenv("ICONFUCIUS_ROOT", str(tmp_path))

    config_content = """\
[settings]

[bots.bot-1]
description = "Bot 1"
"""
    (tmp_path / "iconfucius.toml").write_text(config_content)

    cfg._cached_config = None
    cfg._cached_config_path = None

    yield tmp_path

    cfg._cached_config = None
    cfg._cached_config_path = None


@pytest.fixture
def mock_siwb_auth():
    """Create a mock SIWB auth result dict."""
    from unittest.mock import MagicMock

    delegate_identity = MagicMock()
    delegate_identity.der_pubkey = b"\x30" * 44
    return {
        "delegate_identity": delegate_identity,
        "bot_principal_text": "aaaaa-aa",
        "jwt_token": "fake-jwt-token",
        "btc_deposit_address": "bc1qtest123",
    }


@pytest.fixture
def mock_wallet_identity():
    """Create a mock wallet Identity object."""
    from unittest.mock import MagicMock

    identity = MagicMock()
    identity.sender.return_value = MagicMock(
        __str__=lambda self: "controller-principal-abc"
    )
    identity.to_pem.return_value = b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"
    return identity
