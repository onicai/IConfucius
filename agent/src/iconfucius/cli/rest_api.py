"""Sprint 1: Explore the Odin.Fun public REST API.

This script queries public (unauthenticated) endpoints to understand
data structures, token IDs, price formats, and satoshi conversions.

Note: The API is behind Cloudflare bot protection.  We use curl_cffi
with Chrome TLS-fingerprint impersonation to pass the challenge.

IMPORTANT: Token names and tickers are NOT unique on odin.fun.
Always use the token ID as the primary identifier.
"""

import json

from curl_cffi import requests

BASE_URL = "https://api.odin.fun/v1"

# Test tokens - bonded (graduated to AMM).
# Keyed by token ID (the only unique identifier).
TEST_TOKENS_BONDED = [
    "29m8",  # IConfucius
    "28k1",  # Crypto Burger (CRYPTOBURG)
    "2jjj",  # ODINDOG
]


def pp(label: str, data: object) -> None:
    """Pretty-print a JSON-serialisable object with a label."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, default=str))


def get(path: str, params: dict | None = None) -> dict:
    """GET request to the Odin API; return parsed JSON."""
    url = f"{BASE_URL}{path}"
    print(f"\n>>> GET {url}  params={params}")
    resp = requests.get(
        url,
        params=params,
        impersonate="chrome",
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def list_tokens() -> None:
    data = get("/tokens", {"limit": 5})
    pp("List tokens (first 5)", data)


def get_bonded_token_details() -> None:
    for tid in TEST_TOKENS_BONDED:
        data = get(f"/token/{tid}")
        pp(f"Token details [bonded]: {tid}", data)


def get_newest_tokens(count: int = 3) -> list[str]:
    """Fetch the most recently created tokens (typically unbonded).

    Returns a list of token IDs.
    """
    data = get("/tokens", {"limit": count, "sort": "created_time:desc"})
    token_ids = [t["id"] for t in data["data"]]
    pp(f"Newest tokens ({count} most recent)", data)
    return token_ids


def get_unbonded_token_details(token_ids: list[str]) -> None:
    for tid in token_ids:
        data = get(f"/token/{tid}")
        pp(f"Token details [unbonded]: {tid}", data)


def list_trades() -> None:
    data = get("/trades", {"limit": 5})
    pp("Recent trades (first 5)", data)


def search_tokens() -> None:
    data = get("/search", {"q": "ICONFUCIUS"})
    pp("Search: ICONFUCIUS", data)


def main() -> None:
    print("Odin.Fun REST API Explorer")
    print(f"Base URL: {BASE_URL}")

    list_tokens()
    get_bonded_token_details()
    newest = get_newest_tokens(3)
    get_unbonded_token_details(newest)
    list_trades()
    search_tokens()

    print("\nDone.")


if __name__ == "__main__":
    main()
