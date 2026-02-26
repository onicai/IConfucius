"""
Tests for iconfucius.bip322 — Pure Python BIP322/BIP341 implementation.

Run with: pytest tests/test_bip322_helper.py -v
"""

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

from iconfucius.bip322 import (
    bip0322_hash,
    compute_sighash,
    derive_address,
    encode_varint,
    encode_var_string,
    encode_witness,
    inject_signature_and_extract_witness,
)


# ── Test vectors ─────────────────────────────────────────────────────────────
# These are derived from known working outputs of the Node.js implementation.

# Example x-only public key (32 bytes hex)
TEST_PUBKEY = "cc8a4bc64d897bddc5fbc2f670f7a8ba0b386779106cf1223c6fc5d7cd6fc115"

# Expected P2TR address for TEST_PUBKEY (mainnet)
# Derived by running: derive_address(TEST_PUBKEY)
TEST_ADDRESS = "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"

# Example SIWB challenge message
TEST_MESSAGE = """odin.fun wants you to sign in with your Bitcoin account:
bc1pe5fyzr5dgdn895a4spr27f4cnmhatu368lne80r56ng86u9g5pcshytpst

URI: https://odin.fun
Version: 1
Nonce: abc123
Issued At: 2026-02-06T12:00:00.000Z"""

# Example 64-byte Schnorr signature (dummy for encoding tests)
TEST_SIGNATURE = "a" * 128  # 64 bytes as hex


# ── Unit tests: low-level helpers ────────────────────────────────────────────

class TestVarintEncoding:
    """Test Bitcoin varint encoding."""

    def test_single_byte(self):
        """Verify single byte."""
        assert encode_varint(0) == b"\x00"
        assert encode_varint(1) == b"\x01"
        assert encode_varint(252) == b"\xfc"

    def test_two_byte(self):
        """Verify two byte."""
        assert encode_varint(253) == b"\xfd\xfd\x00"
        assert encode_varint(0xFF) == b"\xfd\xff\x00"
        assert encode_varint(0xFFFF) == b"\xfd\xff\xff"

    def test_four_byte(self):
        """Verify four byte."""
        assert encode_varint(0x10000) == b"\xfe\x00\x00\x01\x00"


class TestVarStringEncoding:
    """Test varint-prefixed byte string encoding."""

    def test_empty(self):
        """Verify empty."""
        assert encode_var_string(b"") == b"\x00"

    def test_short(self):
        """Verify short."""
        assert encode_var_string(b"abc") == b"\x03abc"

    def test_64_bytes(self):
        """Verify 64 bytes."""
        sig = bytes.fromhex(TEST_SIGNATURE)
        result = encode_var_string(sig)
        assert result[0] == 64  # length prefix
        assert result[1:] == sig


# ── Unit tests: BIP322 tagged hash ───────────────────────────────────────────

class TestBip0322Hash:
    """Test BIP0322 tagged message hash."""

    def test_empty_message(self):
        # BIP322 test vector: empty message
        """Verify empty message."""
        result = bip0322_hash("")
        # The hash should be 64 hex chars (32 bytes)
        assert len(result) == 64
        # Known hash for empty message
        assert result == "c90c269c4f8fcbe6880f72a721ddfbf1914268a794cbb21cfafee13770ae19f1"

    def test_hello_world(self):
        # BIP322 test vector: "Hello World"
        """Verify hello world."""
        result = bip0322_hash("Hello World")
        assert len(result) == 64
        assert result == "f0eb03b1a75ac6d9847f55c624a99169b5dccba2a31f5b23bea77ba270de0a7a"

    def test_deterministic(self):
        # Same message should always produce same hash
        """Verify deterministic."""
        msg = "test message"
        assert bip0322_hash(msg) == bip0322_hash(msg)


# ── Unit tests: P2TR address derivation ──────────────────────────────────────

class TestDeriveAddress:
    """Test P2TR address derivation from x-only public key."""

    def test_valid_pubkey(self):
        """Verify valid pubkey."""
        address = derive_address(TEST_PUBKEY)
        assert address.startswith("bc1p")
        assert len(address) == 62  # bech32m P2TR address length
        assert address == TEST_ADDRESS

    def test_invalid_pubkey_length(self):
        """Verify invalid pubkey length."""
        with pytest.raises(Exception):
            derive_address("abcd")  # Too short

    def test_invalid_hex(self):
        """Verify invalid hex."""
        with pytest.raises(Exception):
            derive_address("zz" * 32)  # Invalid hex


# ── Unit tests: witness encoding ─────────────────────────────────────────────

class TestEncodeWitness:
    """Test BIP322 witness encoding."""

    def test_valid_signature(self):
        """Verify valid signature."""
        witness = encode_witness(TEST_SIGNATURE)
        # Should be base64 encoded
        decoded = base64.b64decode(witness)
        # Structure: varint(1) + varstring(64-byte sig)
        assert decoded[0] == 1  # witness count
        assert decoded[1] == 64  # signature length
        assert decoded[2:] == bytes.fromhex(TEST_SIGNATURE)

    def test_invalid_signature_length(self):
        """Verify invalid signature length."""
        with pytest.raises(ValueError, match="Expected 64-byte"):
            encode_witness("aa" * 32)  # Only 32 bytes


class TestInjectSignatureAndExtractWitness:
    """Test full witness extraction with message context."""

    def test_produces_same_as_simple_encode(self):
        # For P2TR key-path spend, the full and simple methods should match
        """Verify produces same as simple encode."""
        result1 = inject_signature_and_extract_witness(
            TEST_MESSAGE, TEST_PUBKEY, TEST_SIGNATURE
        )
        result2 = {"witness": encode_witness(TEST_SIGNATURE)}
        assert result1["witness"] == result2["witness"]


# ── Unit tests: sighash computation ──────────────────────────────────────────

class TestComputeSighash:
    """Test BIP341 sighash computation for BIP322 signing."""

    def test_returns_sighash_and_address(self):
        """Verify returns sighash and address."""
        result = compute_sighash(TEST_MESSAGE, TEST_PUBKEY)
        assert "sighash" in result
        assert "address" in result
        assert len(result["sighash"]) == 64  # 32 bytes hex
        assert result["address"] == TEST_ADDRESS

    def test_deterministic(self):
        # Same inputs should produce same sighash
        """Verify deterministic."""
        result1 = compute_sighash(TEST_MESSAGE, TEST_PUBKEY)
        result2 = compute_sighash(TEST_MESSAGE, TEST_PUBKEY)
        assert result1["sighash"] == result2["sighash"]

    def test_different_message_different_sighash(self):
        """Verify different message different sighash."""
        result1 = compute_sighash("message 1", TEST_PUBKEY)
        result2 = compute_sighash("message 2", TEST_PUBKEY)
        assert result1["sighash"] != result2["sighash"]


# ── Integration test: CLI interface ──────────────────────────────────────────

class TestCLIInterface:
    """Test the JSON stdin/stdout CLI interface."""

    @pytest.fixture
    def script_path(self):
        """Return the path to the BIP322 CLI script."""
        return Path(__file__).parent.parent / "src" / "iconfucius" / "bip322.py"

    def _call_cli(self, script_path: Path, request: dict) -> dict:
        """Call the CLI and return parsed JSON response."""
        result = subprocess.run(
            [sys.executable, str(script_path)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return json.loads(result.stdout.strip())

    def test_address_action(self, script_path):
        """Verify address action."""
        response = self._call_cli(script_path, {
            "action": "address",
            "pubkey": TEST_PUBKEY,
        })
        assert response["address"] == TEST_ADDRESS

    def test_sighash_action(self, script_path):
        """Verify sighash action."""
        response = self._call_cli(script_path, {
            "action": "sighash",
            "message": TEST_MESSAGE,
            "pubkey": TEST_PUBKEY,
        })
        assert "sighash" in response
        assert "address" in response
        assert len(response["sighash"]) == 64

    def test_witness_action_simple(self, script_path):
        """Verify witness action simple."""
        response = self._call_cli(script_path, {
            "action": "witness",
            "signature": TEST_SIGNATURE,
        })
        assert "witness" in response
        # Verify it's valid base64
        base64.b64decode(response["witness"])

    def test_witness_action_full(self, script_path):
        """Verify witness action full."""
        response = self._call_cli(script_path, {
            "action": "witness",
            "message": TEST_MESSAGE,
            "pubkey": TEST_PUBKEY,
            "signature": TEST_SIGNATURE,
        })
        assert "witness" in response

    def test_unknown_action(self, script_path):
        """Verify unknown action."""
        response = self._call_cli(script_path, {
            "action": "unknown",
        })
        assert "error" in response

    def test_missing_required_field(self, script_path):
        """Verify missing required field."""
        response = self._call_cli(script_path, {
            "action": "address",
            # missing pubkey
        })
        assert "error" in response


# Note: Cross-validation tests with Node.js were removed after migration to pure Python.
# The Node.js implementation (bip322_helper.mjs) has been deleted.
# All outputs were verified to match before removal.
