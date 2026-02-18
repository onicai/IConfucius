"""Token registry — load, look up, and cache known tokens.

Tokens are resolved from three tiers (lowest → highest precedence):
1. Built-in:  <package>/tokens.toml   (shipped with pip install)
2. Global:    ~/.iconfucius/tokens.toml (user additions)
3. Local:     ./tokens.toml            (project directory)

If a token is not found in any tier, the Odin.fun search API is queried
and bonded results are cached locally (~/.iconfucius/.token-cache.json).
"""

import json
import time
from pathlib import Path

import tomllib

from iconfucius.config import _project_root

# Cache expires after 24 hours
_CACHE_TTL_SECONDS = 86400

# Maximum tokens to include in prompt (keep system prompt reasonable)
_MAX_PROMPT_TOKENS = 50


def _builtin_toml() -> Path:
    """Return path to built-in tokens.toml (inside installed package)."""
    return Path(__file__).parent / "tokens.toml"


def _global_toml() -> Path:
    """Return ~/.iconfucius/tokens.toml."""
    return Path.home() / ".iconfucius" / "tokens.toml"


def _local_toml() -> Path:
    """Return ./tokens.toml relative to project root."""
    return Path(_project_root()) / "tokens.toml"


def _cache_path() -> Path:
    """Return ~/.iconfucius/.token-cache.json."""
    return Path.home() / ".iconfucius" / ".token-cache.json"


def _load_toml(path: Path) -> dict[str, dict]:
    """Load tokens from a TOML file. Returns empty dict on error."""
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("tokens", {})
    except Exception:
        return {}


def load_known_tokens() -> dict[str, dict]:
    """Load and merge tokens from all 3 tiers.

    Returns dict keyed by token ID: {"29m8": {"name": "IConfucius", "ticker": "ICONFUCIUS"}}
    Higher tiers override lower tiers.
    """
    merged: dict[str, dict] = {}
    for path in [_builtin_toml(), _global_toml(), _local_toml()]:
        merged.update(_load_toml(path))
    return merged


def lookup_known_token(query: str) -> dict | None:
    """Find a token by ID, name, or ticker (case-insensitive).

    When multiple tokens match by name or ticker, the one with the highest
    marketcap wins (bonded + highest marketcap is the hardest to fake).

    Checks all 3 TOML tiers. Does NOT call the API.
    Returns {"id": "29m8", "name": "IConfucius", "ticker": "ICONFUCIUS", ...} or None.
    """
    tokens = load_known_tokens()
    q = query.lower()

    # Check by ID first (IDs are unique — no disambiguation needed)
    if q in tokens:
        entry = tokens[q]
        return {"id": q, **entry}

    # Search by name or ticker — collect all matches
    matches = []
    for token_id, entry in tokens.items():
        if entry.get("name", "").lower() == q or entry.get("ticker", "").lower() == q:
            matches.append({"id": token_id, **entry})

    if not matches:
        return None

    # Prefer highest marketcap (hardest to fake), then earliest creation date
    # (original token was created first, copycats come later).
    # Negate marketcap so both sort ascending: lowest neg-marketcap = highest marketcap,
    # earliest ISO date string = first alphabetically.
    matches.sort(
        key=lambda m: (-m.get("marketcap", 0), m.get("created_time", "9999")),
    )
    return matches[0]


def format_known_tokens_for_prompt() -> str:
    """Format top tokens as a markdown table for system prompt injection.

    Returns a compact table with the most well-known tokens (sorted by name).
    """
    tokens = load_known_tokens()
    if not tokens:
        return ""

    # Sort by name, take top N
    items = sorted(tokens.items(), key=lambda x: x[1].get("name", "").lower())
    items = items[:_MAX_PROMPT_TOKENS]

    lines = [
        "| ID     | Name                           | Ticker       |",
        "|--------|--------------------------------|--------------|",
    ]
    for token_id, entry in items:
        name = entry.get("name", "")[:30]
        ticker = entry.get("ticker", "")[:12]
        lines.append(f"| {token_id:<6s} | {name:<30s} | {ticker:<12s} |")

    lines.append(f"\n({len(tokens)} total known tokens — use token_lookup for the full list)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API fallback with local cache
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    """Load the token cache from disk."""
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    """Write the token cache to disk."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def _is_fresh(entry: dict) -> bool:
    """Check if a cache entry is still fresh (within TTL)."""
    cached_at = entry.get("cached_at", 0)
    return (time.time() - cached_at) < _CACHE_TTL_SECONDS


def search_token(query: str) -> dict:
    """Search for a token, checking TOML tiers, cache, then API.

    Returns:
        {
            "known_match": {...} | None,   # match from TOML tiers
            "search_results": [...],       # API search results with safety notes
        }
    """
    # 1. Check TOML tiers
    known = lookup_known_token(query)

    # 2. Search API for additional results
    search_results = _search_api(query)

    # 3. Annotate results with safety notes
    known_ids = set(load_known_tokens().keys())
    annotated = []
    for r in search_results:
        r["safety"] = _safety_note(r, r["id"] in known_ids)
        annotated.append(r)

    # 4. Cache any bonded results we found
    _cache_bonded_results(annotated)

    return {
        "known_match": known,
        "search_results": annotated,
    }


def lookup_token_with_fallback(query: str) -> dict | None:
    """Look up a single token with API fallback for unknown tokens.

    Checks: TOML tiers → local cache → API search (bonded only).
    Caches bonded API results locally.

    Returns token dict or None.
    """
    # 1. Check TOML tiers
    known = lookup_known_token(query)
    if known:
        return known

    # 2. Check local cache
    cache = _load_cache()
    q = query.lower()
    for token_id, entry in cache.items():
        if not _is_fresh(entry):
            continue
        if (token_id == q
                or entry.get("name", "").lower() == q
                or entry.get("ticker", "").lower() == q):
            return {"id": token_id, **{k: v for k, v in entry.items() if k != "cached_at"}}

    # 3. Search API, return first bonded result
    results = _search_api(query)
    bonded = [r for r in results if r.get("bonded") is True]

    if bonded:
        best = bonded[0]
        _cache_bonded_results(bonded)
        return {
            "id": best["id"],
            "name": best.get("name", ""),
            "ticker": best.get("ticker", ""),
        }

    return None


def _search_api(query: str) -> list[dict]:
    """Search the Odin.fun API. Returns flattened token results.

    The /search endpoint returns results with data nested in 'entity'.
    This function flattens the structure so callers get standard token dicts.
    """
    try:
        from curl_cffi import requests as cffi_requests

        resp = cffi_requests.get(
            "https://api.odin.fun/v1/search",
            params={"q": query},
            impersonate="chrome",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("data", []):
            if item.get("type") != "token":
                continue
            entity = item.get("entity", {})
            if entity:
                results.append(entity)
            else:
                results.append(item)
        return results
    except Exception:
        return []


def _safety_note(token: dict, is_known: bool) -> str:
    """Compute a safety note for a token search result."""
    parts = []

    if is_known and token.get("bonded"):
        return "VERIFIED — bonded token in iconfucius registry"

    if token.get("bonded"):
        parts.append("bonded (graduated to AMM)")
    else:
        parts.append("WARNING: NOT bonded")

    if token.get("twitter_verified"):
        parts.append("Twitter verified")
    else:
        parts.append("Twitter NOT verified")

    holder_count = token.get("holder_count", 0)
    if holder_count < 10:
        parts.append(f"only {holder_count} holders")
    else:
        parts.append(f"{holder_count:,} holders")

    if not is_known:
        parts.append("not in known tokens registry")

    return " · ".join(parts)


def _cache_bonded_results(results: list[dict]) -> None:
    """Cache bonded search results to the local cache file."""
    bonded = [r for r in results if r.get("bonded") is True]
    if not bonded:
        return

    cache = _load_cache()
    now = time.time()

    for r in bonded:
        cache[r["id"]] = {
            "name": r.get("name", ""),
            "ticker": r.get("ticker", ""),
            "bonded": True,
            "cached_at": now,
        }

    _save_cache(cache)
