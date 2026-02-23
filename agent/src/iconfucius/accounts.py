"""iconfucius.accounts — Odin.fun account resolution and lookup."""

from curl_cffi import requests as cffi_requests

from iconfucius.config import ODIN_API_URL


def _search_odin_account(address: str) -> dict | None:
    """Search Odin.fun for an account by address.

    Accepts IC principals, BTC deposit addresses, or BTC wallet addresses.
    Uses the /v1/users search endpoint (same as the Odin.fun frontend).

    Returns the full user dict if found, None otherwise.
    """
    try:
        resp = cffi_requests.get(
            f"{ODIN_API_URL}/users",
            params={"search": address, "env": "production"},
            impersonate="chrome",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("data", [])
        if not results:
            return None
        return results[0]
    except Exception:
        return None


def resolve_odin_account(address: str) -> str | None:
    """Resolve an address to an Odin.fun account's IC principal.

    Accepts IC principals or BTC wallet addresses. Uses the /v1/users search
    endpoint (same as the Odin.fun frontend) to look up the account.

    Returns the IC principal if found, None otherwise.
    """
    user = _search_odin_account(address)
    if not user:
        return None
    return user.get("principal")


def lookup_odin_account(address: str) -> dict | None:
    """Look up an Odin.fun account and return key account details.

    Accepts IC principals, BTC deposit addresses, or BTC wallet addresses.

    Returns a dict with account details if found, None otherwise.
    """
    user = _search_odin_account(address)
    if not user:
        return None
    return {
        "principal": user.get("principal"),
        "username": user.get("username"),
        "btc_wallet_address": user.get("btc_wallet_address"),
        "btc_deposit_address": user.get("btc_deposit_address"),
        "bio": user.get("bio"),
        "avatar": user.get("avatar"),
        "admin": user.get("admin"),
        "verified": user.get("verified"),
        "follower_count": user.get("follower_count"),
        "following_count": user.get("following_count"),
        "created_at": user.get("created_at"),
    }
