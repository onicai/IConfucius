"""
iconfucius.siwb — SIWB Login via onicai Chain Fusion Canister

Authenticates a bot on odin.fun using the onicai Chain Fusion canister for
threshold Schnorr signing (chain fusion).

Flow:
  1. Get x-only pubkey + P2TR address from onicai ckSigner canister
  2. Call SIWB canister siwb_prepare_login(address)
  3. Sign BIP322 message via onicai ckSigner canister signBip322()
  4. Generate Ed25519 session key
  5. Call SIWB canister siwb_login()
  6. Call SIWB canister siwb_get_delegation()
  7. Exchange delegation for JWT via REST API

Session caching:
  After login, saves JWT + metadata to secret/session_{bot_name}.json.
  Use load_session(bot_name) to get a cached session if still valid.

Usage:
  from iconfucius.siwb import siwb_login, load_session
  session = load_session("bot-1")  # returns cached session or None
  if not session:
      session = siwb_login("bot-1")
"""

import base64
import hashlib
import json
import os
import stat
import threading
import time

from curl_cffi import requests as cffi_requests
from icp_agent import Agent, Client
from icp_canister import Canister
from icp_identity import DelegateIdentity, Identity
from icp_principal import Principal

from iconfucius.candid import CKBTC_LEDGER_CANDID, ODIN_SIWB_CANDID, ONICAI_CKSIGNER_CANDID
from iconfucius.config import (
    CKBTC_LEDGER_CANISTER_ID,
    IC_HOST,
    ODIN_API_URL,
    ODIN_SIWB_CANISTER_ID,
    _project_root,
    fmt_sats,
    get_btc_to_usd_rate,
    get_cache_sessions,
    get_cksigner_canister_id,
    get_network,
    get_pem_file,
    get_verify_certificates,
    log,
    set_verbose,
)
from iconfucius.transfers import CKBTC_FEE, unwrap_canister_result


# ---------------------------------------------------------------------------
# icp-py-core result unwrapping
# ---------------------------------------------------------------------------

def unwrap(result):
    """Unwrap icp-py-core Canister call result.

    icp-py-core returns a list of typed dicts, e.g.:
      [{'type': 'variant', 'value': {'Ok': {...}}}]

    This extracts the inner value dict, e.g. {'Ok': {...}}.
    """
    if isinstance(result, list) and len(result) > 0:
        item = result[0]
        if isinstance(item, dict) and "value" in item:
            return item["value"]
    return result


# ---------------------------------------------------------------------------
# Helper: bytes-to-hex
# ---------------------------------------------------------------------------

def to_hex(v):
    """Convert bytes to hex string, passthrough if already str."""
    if isinstance(v, bytes):
        return v.hex()
    return v


# ---------------------------------------------------------------------------
# Public key retrieval (query-first with update fallback)
# ---------------------------------------------------------------------------

def bot_has_public_key(bot_name: str) -> bool:
    """Fast check whether a bot has a public key cached in the canister.

    Uses an anonymous query call — no authentication, no fees, no side effects.
    Returns False if the bot has never been used (key not yet generated).
    """
    from icp_agent import Agent, Client
    from icp_canister import Canister
    from icp_identity import Identity

    client = Client(url=IC_HOST)
    anon_agent = Agent(Identity(anonymous=True), client)
    cksigner = Canister(
        agent=anon_agent,
        canister_id=get_cksigner_canister_id(),
        candid_str=ONICAI_CKSIGNER_CANDID,
    )
    try:
        result = unwrap(cksigner.getPublicKeyQuery(
            {"botName": bot_name},
            verify_certificate=get_verify_certificates(),
        ))
        return "Ok" in result
    except Exception:
        return False


# Lock to serialize all icrc2_approve + paid-canister-call pairs across threads.
# ICRC-2 approve sets a total allowance (not additive), so concurrent
# threads would overwrite each other's approvals. This lock ensures
# each thread's approve+spend completes before the next begins.
# Used by: _get_public_key (update), sign_with_fee.
_fee_payment_lock = threading.Lock()


def _get_public_key(cksigner, bot_name: str, wallet_agent=None,
                    query_only: bool = False) -> tuple[str, str]:
    """Get bot public key, trying query call first then update on cache miss.

    The query call (getPublicKeyQuery) is free. The update call (getPublicKey)
    may require ICRC-2 fee payment when fee tokens are configured.

    Args:
        cksigner: Canister object for the ckSigner canister.
        bot_name: Bot name to fetch the public key for.
        wallet_agent: Agent for the wallet identity (needed for fee payment
            on update).
        query_only: If True, only use the free query call — never fall back
            to the paid update call. Use for read-only operations like
            balance checks where generating a new key is not needed.

    Returns:
        Tuple of (publicKeyHex, address).

    Raises:
        RuntimeError: If the query fails (and query_only=True) or if both
            query and update calls fail.
    """
    # Try query call first (free, fast, works when key is already cached)
    result = unwrap(cksigner.getPublicKeyQuery(
        {"botName": bot_name}, verify_certificate=get_verify_certificates(),
    ))
    if "Err" in result:
        if query_only:
            raise RuntimeError(
                f"No public key cached for bot '{bot_name}'. "
                f"The bot has not been used yet."
            )
        # Cache miss — fall back to update call (may require fee payment).
        # Serialize approve+spend so concurrent threads don't race.
        with _fee_payment_lock:
            log(f"  -> Cache miss, calling getPublicKey (update) to populate cache")
            payment = _approve_fee_if_required(cksigner, wallet_agent)
            result = unwrap(cksigner.getPublicKey(
                {"botName": bot_name, "payment": payment},
                verify_certificate=get_verify_certificates(),
            ))
        if "Err" in result:
            raise RuntimeError(f"getPublicKey failed: {result['Err']}")
    return result["Ok"]["publicKeyHex"], result["Ok"]["address"]


def _approve_fee_if_required(cksigner, wallet_agent) -> list:
    """Check fee tokens and approve ICRC-2 payment if required.

    Returns:
        list: Payment record wrapped in list (opt Some), or empty list (opt None).
    """
    fee_result = unwrap(cksigner.getFeeTokens(verify_certificate=get_verify_certificates()))
    if "Err" in fee_result:
        raise RuntimeError(f"getFeeTokens failed: {fee_result['Err']}")
    fee_tokens = fee_result["Ok"]["feeTokens"]

    if not fee_tokens:
        log(f"  No fees configured (free getPublicKey)")
        return []  # opt None

    ckbtc_fee_token = None
    for ft in fee_tokens:
        if ft["tokenName"] == "ckBTC":
            ckbtc_fee_token = ft
            break

    if ckbtc_fee_token is None:
        raise RuntimeError(
            f"ckSigner requires fee payment but no ckBTC fee token configured. "
            f"Available: {[ft['tokenName'] for ft in fee_tokens]}"
        )

    if wallet_agent is None:
        raise RuntimeError("Fee payment required but no wallet_agent provided")

    fee_amount = ckbtc_fee_token["fee"]
    token_ledger = ckbtc_fee_token["tokenLedger"]

    try:
        _btc_usd = get_btc_to_usd_rate()
    except Exception:
        _btc_usd = None
    log(f"  Fee: {fmt_sats(fee_amount, _btc_usd)} (ckBTC)")

    log(f"  -> ICRC-2 approve: allowing ckSigner to collect {fmt_sats(fee_amount, _btc_usd)}...")
    ckbtc = Canister(
        agent=wallet_agent,
        canister_id=CKBTC_LEDGER_CANISTER_ID,
        candid_str=CKBTC_LEDGER_CANDID,
    )
    cksigner_principal = Principal.from_str(get_cksigner_canister_id())
    approve_amount = fee_amount + CKBTC_FEE  # fee + ledger transfer fee

    approve_result = unwrap_canister_result(ckbtc.icrc2_approve({
        "spender": {"owner": cksigner_principal, "subaccount": []},
        "amount": approve_amount,
        "fee": [],
        "memo": [],
        "from_subaccount": [],
        "created_at_time": [],
        "expected_allowance": [],
        "expires_at": [],
    }, verify_certificate=get_verify_certificates()))

    if isinstance(approve_result, dict) and "Err" in approve_result:
        raise RuntimeError(f"icrc2_approve for fee payment failed: {approve_result['Err']}")
    log(f"  Approve OK (block index: {approve_result.get('Ok', approve_result)})")

    return [{
        "tokenName": "ckBTC",
        "tokenLedger": token_ledger,
        "amount": fee_amount,
    }]


# ---------------------------------------------------------------------------
# Session caching
# ---------------------------------------------------------------------------

def _session_dir():
    """Return the .cache/ directory for session files."""
    return os.path.join(_project_root(), ".cache")


def _session_path(bot_name: str) -> str:
    """Return session file path: .cache/session_{bot_name}[_{network}].json."""
    # Sanitize bot name for filesystem
    safe_name = bot_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    network = get_network()
    if network == "prd":
        filename = f"session_{safe_name}.json"
    else:
        filename = f"session_{safe_name}_{network}.json"
    return os.path.join(_session_dir(), filename)


def save_session(session: dict, bot_name: str) -> str:
    """Save session to .cache/session_{bot_name}.json.

    Includes session_identity (as base64 PEM) and delegation_chain
    so delegate_identity can be reconstructed on load.
    Skipped when cache_sessions = false in iconfucius.toml.
    """
    if not get_cache_sessions():
        return ""
    path = _session_path(bot_name)

    # Serialize session_identity to PEM (base64 for JSON)
    session_identity = session.get("session_identity")
    session_pem_b64 = None
    if session_identity:
        pem_bytes = session_identity.to_pem()
        session_pem_b64 = base64.b64encode(pem_bytes).decode("ascii")

    data = {
        "jwt_token": session["jwt_token"],
        "bot_principal_text": session["bot_principal_text"],
        "address": session["address"],
        "bot_name": bot_name,
        "saved_at": time.time(),
        # For delegate_identity reconstruction
        "session_pem_b64": session_pem_b64,
        "delegation_chain": session.get("delegation_chain"),
        # Cached BTC deposit address (from ckBTC minter, deterministic per principal)
        "btc_deposit_address": session.get("btc_deposit_address"),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Atomic-create with 0600 from the start (no race window with world-readable perms)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_session(bot_name: str = None, verbose: bool = True) -> dict | None:
    """Load cached session if JWT is still valid.

    Args:
        bot_name: Bot name to load session for. If None, uses default from config.
        verbose: If True, print status messages.

    Returns:
        Dict with jwt_token, bot_principal_text, address, delegate_identity, etc.
        Or None if no valid session exists.

    Validates the JWT by calling GET /v1/auth.
    Reconstructs delegate_identity from saved session_pem and delegation_chain.
    Returns None immediately when cache_sessions = false in iconfucius.toml.

    Expiration notes:
    - JWT expires after 24 hours (set by Odin.Fun REST API)
    - Delegation expires after 48 hours (set by SIWB canister, cannot be changed)
    - We validate the JWT first, so effective session lifetime is 24 hours
    - When JWT expires, load_session returns None, triggering a fresh SIWB login
    """
    set_verbose(verbose)

    if not get_cache_sessions():
        log("Session caching disabled (cache_sessions = false)")
        return None

    path = _session_path(bot_name)
    if not os.path.exists(path):
        log(f"No cached session for bot={bot_name}")
        return None

    with open(path, "r") as f:
        data = json.load(f)

    jwt_token = data.get("jwt_token")
    if not jwt_token:
        log("Cached session has no JWT")
        return None

    # Validate JWT is still accepted by the API
    try:
        resp = cffi_requests.get(
            f"{ODIN_API_URL}/auth",
            impersonate="chrome",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            log(f"Loaded cached session from {os.path.basename(path)}")
            log(f"  Bot principal: {data['bot_principal_text']}")

            result = {
                "jwt_token": jwt_token,
                "bot_principal_text": data["bot_principal_text"],
                "address": data["address"],
                "bot_name": bot_name,
                "btc_deposit_address": data.get("btc_deposit_address"),
            }

            # Reconstruct delegate_identity if we have the saved components
            session_pem_b64 = data.get("session_pem_b64")
            delegation_chain = data.get("delegation_chain")
            if session_pem_b64 and delegation_chain:
                try:
                    pem_bytes = base64.b64decode(session_pem_b64)
                    session_identity = Identity.from_pem(pem_bytes)
                    delegate_identity = DelegateIdentity(session_identity, delegation_chain)
                    result["delegate_identity"] = delegate_identity
                    result["session_identity"] = session_identity
                    result["delegation_chain"] = delegation_chain
                except Exception as e:
                    log(f"  Warning: session partially restored ({e})")

            return result
        else:
            log(f"Cached JWT expired or invalid (status {resp.status_code})")
    except Exception as e:
        log(f"JWT validation failed: {e}")

    return None


# ---------------------------------------------------------------------------
# Sign with fee payment
# ---------------------------------------------------------------------------

def sign_with_fee(cksigner, wallet_agent, bot_name, message):
    """Sign a message via ckSigner canister, handling ICRC-2 fee payment if required.

    Flow:
      1. Query getFeeTokens() to discover fee requirements
      2. If fees configured, icrc2_approve on ckBTC ledger (spender = ckSigner)
      3. Call sign() with payment record

    Args:
        cksigner: ckSigner Canister object (authenticated with wallet_agent)
        wallet_agent: Agent for the PEM identity (holds ckBTC)
        bot_name: Bot name for derivation path
        message: 32-byte message hash to sign (bytes)

    Returns:
        dict: Unwrapped sign result with "Ok" or "Err" key

    Raises:
        RuntimeError: If fee approval fails or no ckBTC fee token found
    """
    # Serialize approve+sign so concurrent threads don't race on allowance.
    with _fee_payment_lock:
        payment = _approve_fee_if_required(cksigner, wallet_agent)

        log(f"  -> Signing message via threshold Schnorr (BIP340)...")
        sign_result = unwrap(cksigner.sign({
            "botName": bot_name,
            "message": message,
            "payment": payment,
        }, verify_certificate=get_verify_certificates()))

    return sign_result


def signBip322_with_fee(cksigner, wallet_agent, bot_name, message):
    """Sign a BIP322 message via ckSigner canister, handling ICRC-2 fee payment.

    Args:
        cksigner: ckSigner Canister object (authenticated with wallet_agent)
        wallet_agent: Agent for the PEM identity (holds ckBTC)
        bot_name: Bot name for derivation path
        message: BIP322 message string to sign

    Returns:
        dict: Unwrapped signBip322 result with "Ok" or "Err" key
    """
    with _fee_payment_lock:
        payment = _approve_fee_if_required(cksigner, wallet_agent)
        result = unwrap(cksigner.signBip322({
            "botName": bot_name,
            "message": message,
            "payment": payment,
        }, verify_certificate=get_verify_certificates()))
    return result


# ---------------------------------------------------------------------------
# SIWB login flow (reusable)
# ---------------------------------------------------------------------------

def siwb_login(bot_name: str = None, verbose: bool = True) -> dict:
    """Run the full SIWB login flow and return auth context.

    Args:
        bot_name: Bot name to authenticate. If None, uses default from config.
        verbose: If True, print status messages.

    Returns dict with:
        delegate_identity: DelegateIdentity for canister calls
        jwt_token: JWT string for REST API calls
        bot_principal: Principal object (bot's odin.fun identity)
        bot_principal_text: str (textual principal)
        address: str (P2TR bc1p... address)
        delegation_chain: dict (for API calls)
        bot_name: str (the bot name used)
    """
    set_verbose(verbose)

    # Load controller identity from PEM file
    pem_path = get_pem_file()
    if not os.path.exists(pem_path):
        raise FileNotFoundError(
            f"PEM not found at {pem_path}\n"
            "Create it with: iconfucius wallet create"
        )

    with open(pem_path, "r") as f:
        pem_content = f.read()
    wallet_identity = Identity.from_pem(pem_content)
    log(f"Wallet principal: {wallet_identity.sender()}")

    # Create agents
    client = Client(url=IC_HOST)
    wallet_agent = Agent(wallet_identity, client)
    anon_agent = Agent(Identity(anonymous=True), client)

    canister_id = get_cksigner_canister_id()

    # Step 1: Get bot public key (try fast query first, fall back to update)
    log(f"\n--- Step 1: Get bot public key (bot={bot_name}) ---")
    log(f"  -> Fetch the bot's Schnorr public key from the IC canister (derived via BIP340)")
    iconfucius = Canister(
        agent=wallet_agent,
        canister_id=canister_id,
        candid_str=ONICAI_CKSIGNER_CANDID,
    )
    pubkey_hex, address = _get_public_key(iconfucius, bot_name, wallet_agent)
    log(f"X-only pubkey: {pubkey_hex}")

    # Step 2: Sign In With Bitcoin (SIWB) prepare login
    log(f"\n--- Step 2: Sign In With Bitcoin (SIWB) prepare login ---")
    log(f"  -> Request a challenge message from SIWB canister to prove Bitcoin address ownership")
    siwb = Canister(
        agent=anon_agent,
        canister_id=ODIN_SIWB_CANISTER_ID,
        candid_str=ODIN_SIWB_CANDID,
    )
    prepare_result = unwrap(siwb.siwb_prepare_login(address, verify_certificate=get_verify_certificates()))
    if "Err" in prepare_result:
        raise RuntimeError(f"siwb_prepare_login failed: {prepare_result['Err']}")
    message = prepare_result["Ok"]
    log(f"SIWB message:\n{message}")

    # Step 3: Sign BIP322 message (canister computes sighash, signs, encodes witness)
    log(f"\n--- Step 3: Sign BIP322 message via ckSigner canister ---")
    log(f"  -> Canister hashes challenge per BIP322, signs with threshold Schnorr (BIP340), encodes witness")
    bip322_result = signBip322_with_fee(iconfucius, wallet_agent, bot_name, message)
    if "Err" in bip322_result:
        raise RuntimeError(f"signBip322 failed: {bip322_result['Err']}")
    signature_hex = bip322_result["Ok"]["signatureHex"]
    witness_b64 = bip322_result["Ok"]["witnessB64"]
    assert bip322_result["Ok"]["address"] == address, (
        f"Address mismatch: {bip322_result['Ok']['address']} != {address}"
    )
    # Step 4: Generate Ed25519 session key
    log(f"\n--- Step 4: Generate Ed25519 session key ---")
    log(f"  -> Create ephemeral Ed25519 keypair for IC canister calls (SIWB will delegate to this key)")
    session_identity = Identity(type="ed25519")
    der_pubkey = session_identity.der_pubkey
    session_pubkey_der = bytes.fromhex(der_pubkey) if isinstance(der_pubkey, str) else der_pubkey
    log(f"Session pubkey (DER) length: {len(session_pubkey_der)} bytes")

    # Step 5: SIWB login
    log(f"\n--- Step 5: SIWB login ---")
    log(f"  -> Submit BIP322 proof to SIWB canister - links Bitcoin address to session key")
    login_result = unwrap(siwb.siwb_login(
        witness_b64, address, pubkey_hex, session_pubkey_der,
        {"Bip322Simple": None}, verify_certificate=get_verify_certificates(),
    ))
    if "Err" in login_result:
        raise RuntimeError(f"siwb_login failed: {login_result['Err']}")
    expiration = login_result["Ok"]["expiration"]
    user_canister_pubkey = login_result["Ok"]["user_canister_pubkey"]
    # Format expiration as human-readable
    import datetime
    exp_sec = expiration / 1_000_000_000
    exp_dt = datetime.datetime.fromtimestamp(exp_sec)
    now_dt = datetime.datetime.now()
    duration = exp_dt - now_dt
    hours = duration.total_seconds() / 3600
    log(f"Expiration: {expiration} ({exp_dt.strftime('%Y-%m-%d %H:%M:%S')}, {hours:.1f}h from now)")

    # Step 6: Get delegation (with retry)
    log(f"\n--- Step 6: Get delegation ---")
    log(f"  -> Fetch signed delegation from SIWB - authorizes session key to act as bot's principal")
    delegation_result = None
    for attempt in range(5):
        delegation_result = unwrap(siwb.siwb_get_delegation(
            address, session_pubkey_der, expiration,
            verify_certificate=get_verify_certificates(),
        ))
        if "Ok" in delegation_result:
            break
        log(f"Attempt {attempt + 1}: {delegation_result.get('Err', 'unknown error')}, retrying...")
        time.sleep(2)
    if "Err" in delegation_result:
        raise RuntimeError(f"siwb_get_delegation failed: {delegation_result['Err']}")

    signed_delegation = delegation_result["Ok"]

    # Build delegation chain for DelegateIdentity
    delegation_chain = {
        "delegations": [
            {
                "delegation": {
                    "pubkey": to_hex(signed_delegation["delegation"]["pubkey"]),
                    "expiration": signed_delegation["delegation"]["expiration"],
                },
                "signature": to_hex(signed_delegation["signature"]),
            }
        ],
        "publicKey": to_hex(user_canister_pubkey),
    }
    delegate_identity = DelegateIdentity(session_identity, delegation_chain)

    # Compute bot principal from user_canister_pubkey
    ucp = user_canister_pubkey if isinstance(user_canister_pubkey, bytes) else bytes.fromhex(user_canister_pubkey)
    principal_bytes = hashlib.sha224(ucp).digest() + b"\x02"
    bot_principal = Principal(principal_bytes)
    bot_principal_text = bot_principal.to_str()
    log(f"Bot principal: {bot_principal_text}")

    # Step 7: Exchange delegation for JWT
    log(f"\n--- Step 7: Exchange delegation for JWT ---")
    log(f"  -> Send delegation to Odin.Fun REST API - returns JWT for authenticated API calls")
    timestamp = str(int(time.time() * 1000))
    _der_pubkey, sig_bytes = delegate_identity.sign(timestamp.encode())

    # API delegation format (expiration as hex string, matching @dfinity/identity)
    api_delegation = {
        "delegations": [
            {
                "delegation": {
                    "pubkey": to_hex(signed_delegation["delegation"]["pubkey"]),
                    "expiration": format(signed_delegation["delegation"]["expiration"], "x")
                        if isinstance(signed_delegation["delegation"]["expiration"], int)
                        else signed_delegation["delegation"]["expiration"],
                },
                "signature": to_hex(signed_delegation["signature"]),
            }
        ],
        "publicKey": to_hex(user_canister_pubkey),
    }

    payload = {
        "timestamp": timestamp,
        "signature": base64.b64encode(sig_bytes).decode(),
        "delegation": json.dumps(api_delegation),
    }

    resp = cffi_requests.post(
        f"{ODIN_API_URL}/auth",
        json=payload,
        impersonate="chrome",
        headers={"Accept": "application/json"},
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"JWT exchange failed: {resp.status_code} {resp.text[:200]}")

    jwt_token = resp.json().get("token")
    if not jwt_token:
        raise RuntimeError(f"No token in response: {resp.text[:200]}")
    log(f"JWT token: obtained (not logged for security)")

    # Verify JWT
    verify_resp = cffi_requests.get(
        f"{ODIN_API_URL}/auth",
        impersonate="chrome",
        headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/json"},
    )
    log(f"Verify: {verify_resp.status_code} {verify_resp.text[:200]}")

    result = {
        "delegate_identity": delegate_identity,
        "session_identity": session_identity,
        "jwt_token": jwt_token,
        "bot_principal": bot_principal,
        "bot_principal_text": bot_principal_text,
        "address": address,
        "delegation_chain": delegation_chain,
        "api_delegation": api_delegation,
        "bot_name": bot_name,
    }

    # Cache session for reuse
    session_path = save_session(result, bot_name)
    log(f"Session saved to {os.path.basename(session_path)}")

    return result


# ---------------------------------------------------------------------------
# Main (standalone execution)
# ---------------------------------------------------------------------------

def main():
    """Run a standalone SIWB login and print the resulting bot principal."""
    result = siwb_login(verbose=True)
    print(f"\n--- Done ---")
    print(f"Bot principal: {result['bot_principal_text']}")


if __name__ == "__main__":
    main()
