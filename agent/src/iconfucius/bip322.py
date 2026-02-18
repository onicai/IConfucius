"""
BIP322 Helper for iconfucius — Pure Python

Drop-in replacement for bip322_helper.mjs.
Reads JSON from stdin, writes JSON to stdout.

Actions:
  sighash  — Compute BIP341 tapscript sighash for BIP322 message signing
  witness  — Encode a 64-byte Schnorr signature as BIP322 base64 witness
  address  — Derive Bitcoin P2TR address from x-only public key

Dependencies:
  pip install bitcoin-utils

The bitcoin-utils package (https://pypi.org/project/bitcoin-utils/) is a
well-maintained Python library for Bitcoin that fully supports Taproot (P2TR),
BIP341 sighash computation, Schnorr signatures, and bech32m encoding. It uses
the coincurve C extension (libsecp256k1 bindings) for fast elliptic curve
operations and includes Bitcoin Core's reference implementations for schnorr
and bech32m.

Reference: odin-docs/demo/getting-started/sample-wallet.ts
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import sys

from bitcoinutils.setup import setup
from bitcoinutils.keys import PublicKey
from bitcoinutils.transactions import Transaction, TxInput, TxOutput
from bitcoinutils.script import Script

# ── Initialise bitcoin-utils for mainnet ─────────────────────────────────────
setup("mainnet")

# BIP341 SIGHASH_DEFAULT = 0x00
SIGHASH_DEFAULT = 0x00


# ── Low-level helpers ────────────────────────────────────────────────────────

def sha256(data: bytes) -> bytes:
    """Single SHA-256 hash."""
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    """Double SHA-256 (Bitcoin standard tx hash)."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def encode_varint(n: int) -> bytes:
    """Encode an integer as a Bitcoin compact-size varint."""
    if n < 253:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


def encode_var_string(b: bytes) -> bytes:
    """Varint-prefixed byte string."""
    return encode_varint(len(b)) + b


# ── BIP0322 tagged message hash ─────────────────────────────────────────────

def bip0322_hash(message: str) -> str:
    """
    Compute the BIP0322 tagged hash of *message*.

    Returns the 32-byte digest as a hex string.
    """
    tag = b"BIP0322-signed-message"
    tag_hash = sha256(tag)
    msg_bytes = message.encode("utf-8")
    return sha256(tag_hash + tag_hash + msg_bytes).hex()


# ── Manual toSpend serialisation ─────────────────────────────────────────────
#
# bitcoin-utils treats txid=0…0 as a coinbase and mangles the scriptSig,
# so we serialise this virtual transaction by hand.  It is never broadcast;
# only its txid matters.

def _serialise_to_spend(message: str, script_pubkey_bytes: bytes) -> bytes:
    """
    Serialise the BIP322 *toSpend* virtual transaction (non-segwit format).

    Structure (version 0, locktime 0):
      version  : 00000000
      vin_cnt  : 01
        txid   : 00…00 (32 bytes)
        vout   : ffffffff
        scriptSig: OP_0 PUSH32 <bip0322_hash(message)>
        sequence : 00000000
      vout_cnt : 01
        amount : 0000000000000000
        scriptPubKey: <p2tr witness program>
      locktime : 00000000
    """
    # ── version ──
    version = b"\x00\x00\x00\x00"

    # ── inputs ──
    vin_count = encode_varint(1)
    txid = b"\x00" * 32                                 # null txid
    vout = struct.pack("<I", 0xFFFFFFFF)
    msg_hash = bytes.fromhex(bip0322_hash(message))     # 32-byte hash
    script_sig = b"\x00\x20" + msg_hash                 # OP_0 PUSH32 <hash>
    script_sig_enc = encode_var_string(script_sig)
    sequence = b"\x00\x00\x00\x00"
    vin = txid + vout + script_sig_enc + sequence

    # ── outputs ──
    vout_count = encode_varint(1)
    amount = struct.pack("<q", 0)
    spk_enc = encode_var_string(script_pubkey_bytes)
    tx_out = amount + spk_enc

    # ── locktime ──
    locktime = b"\x00\x00\x00\x00"

    return version + vin_count + vin + vout_count + tx_out + locktime


def _to_spend_txid(message: str, script_pubkey_bytes: bytes) -> str:
    """Return the txid of the toSpend virtual transaction (hex, internal order)."""
    raw = _serialise_to_spend(message, script_pubkey_bytes)
    # txid = double-SHA256, displayed in reversed byte order
    return double_sha256(raw)[::-1].hex()


# ── Build BIP322 transactions ───────────────────────────────────────────────

def _build_bip322_transactions(
    message: str, pubkey_hex: str
) -> tuple[Transaction, Script, str]:
    """
    Build the BIP322 toSpend and toSign transactions.

    Parameters
    ----------
    message : str
        The SIWB challenge message.
    pubkey_hex : str
        32-byte x-only public key (hex).

    Returns
    -------
    (tx_to_sign, p2tr_script_pubkey, address)
    """
    # Derive Bitcoin P2TR address & scriptPubKey
    pk = PublicKey("02" + pubkey_hex)
    addr = pk.get_taproot_address()
    p2tr_spk = addr.to_script_pub_key()
    p2tr_spk_bytes = p2tr_spk.to_bytes()

    # Compute toSpend txid (manual serialisation)
    to_spend_txid = _to_spend_txid(message, p2tr_spk_bytes)

    # Build toSign using bitcoin-utils Transaction API
    inp = TxInput(
        to_spend_txid,
        0,
        Script([]),
        sequence=b"\x00\x00\x00\x00",
    )
    out = TxOutput(0, Script(["OP_RETURN"]))
    tx_to_sign = Transaction(
        [inp],
        [out],
        version=b"\x00\x00\x00\x00",
        has_segwit=True,
    )

    return tx_to_sign, p2tr_spk, addr.to_string()


# ── Public API ───────────────────────────────────────────────────────────────

def compute_sighash(message: str, pubkey_hex: str) -> dict:
    """
    Compute the BIP341 sighash for a BIP322 P2TR message signing.

    Parameters
    ----------
    message : str
        The SIWB challenge message.
    pubkey_hex : str
        32-byte x-only public key (hex).

    Returns
    -------
    dict with keys ``sighash`` (hex) and ``address`` (bc1p…).
    """
    tx_to_sign, p2tr_spk, address = _build_bip322_transactions(message, pubkey_hex)

    sighash_bytes = tx_to_sign.get_transaction_taproot_digest(
        txin_index=0,
        script_pubkeys=[p2tr_spk],
        amounts=[0],
        sighash=SIGHASH_DEFAULT,
    )

    return {
        "sighash": sighash_bytes.hex(),
        "address": address,
    }


def inject_signature_and_extract_witness(
    message: str, pubkey_hex: str, signature_hex: str
) -> dict:
    """
    Inject a Schnorr signature into the BIP322 toSign transaction and
    return the base64-encoded witness.

    For a BIP322 P2TR key-path spend the witness is simply:
      varint(1) || varint_string(64-byte signature)

    This matches the JS version which finalises the transaction and
    extracts ``finalScriptWitness = [signature]``.

    Parameters
    ----------
    message : str
        The SIWB challenge message (used to reconstruct the tx).
    pubkey_hex : str
        32-byte x-only public key (hex).
    signature_hex : str
        64-byte Schnorr signature (hex).

    Returns
    -------
    dict with key ``witness`` (base64).
    """
    sig_bytes = bytes.fromhex(signature_hex)
    if len(sig_bytes) != 64:
        raise ValueError(f"Expected 64-byte signature, got {len(sig_bytes)}")

    # For P2TR key-path spend with SIGHASH_DEFAULT the witness is just
    # [signature] — exactly one stack item.
    witness_data = encode_varint(1) + encode_var_string(sig_bytes)
    return {"witness": base64.b64encode(witness_data).decode("ascii")}


def encode_witness(signature_hex: str) -> str:
    """
    Encode a 64-byte Schnorr signature as BIP322 base64 witness (simple).

    Parameters
    ----------
    signature_hex : str
        64-byte Schnorr signature (hex).

    Returns
    -------
    base64-encoded witness string.
    """
    sig_bytes = bytes.fromhex(signature_hex)
    if len(sig_bytes) != 64:
        raise ValueError(f"Expected 64-byte signature, got {len(sig_bytes)}")

    witness_data = encode_varint(1) + encode_var_string(sig_bytes)
    return base64.b64encode(witness_data).decode("ascii")


def derive_address(pubkey_hex: str) -> str:
    """
    Derive a Bitcoin P2TR address from a 32-byte x-only public key.

    Parameters
    ----------
    pubkey_hex : str
        32-byte x-only public key (hex).

    Returns
    -------
    Bitcoin P2TR address string (bc1p…).
    """
    pk = PublicKey("02" + pubkey_hex)
    return pk.get_taproot_address().to_string()


# ── CLI: read JSON from stdin, dispatch action, write JSON to stdout ─────────

def main() -> None:
    try:
        req = json.loads(sys.stdin.read())
        action = req.get("action")

        if action == "sighash":
            if not req.get("message") or not req.get("pubkey"):
                raise ValueError('sighash requires "message" and "pubkey"')
            result = compute_sighash(req["message"], req["pubkey"])

        elif action == "witness":
            if not req.get("signature"):
                raise ValueError('witness requires "signature"')
            if req.get("message") and req.get("pubkey"):
                result = inject_signature_and_extract_witness(
                    req["message"], req["pubkey"], req["signature"]
                )
            else:
                result = {"witness": encode_witness(req["signature"])}

        elif action == "address":
            if not req.get("pubkey"):
                raise ValueError('address requires "pubkey"')
            result = {"address": derive_address(req["pubkey"])}

        else:
            raise ValueError(f"Unknown action: {action}")

        sys.stdout.write(json.dumps(result) + "\n")

    except Exception as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
