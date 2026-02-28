"""Pure unit-conversion helpers for Odin.fun / ckBTC math.

No API calls, no side effects — just arithmetic.

Odin.fun unit conventions
-------------------------
The canister uses **milli-subunits** everywhere.  For any asset:

    ``1 display-unit = 10^(divisibility + decimals) milli-subunits``

BTC has divisibility=8, decimals=3  → ``10^11`` milli-subunits per BTC
Tokens typically have the same  → ``10^11`` milli-subunits per display-token

- ``price`` from ``/v1/token/{id}``: **msat per display-token**
- ``marketcap``, ``volume_24``: **msat**
- ``balance`` from ``/v1/user/{principal}/balances``: **milli-subunits**
  (with an extra ``decimals`` factor; use :func:`adjust_api_decimals`)
- Canister ``getBalance("btc")``: **millisatoshis** (= BTC milli-subunits)
- Canister ``getBalance(token_id)``: **milli-subunits** (divide by 10^11 for display)
- Canister ``token_trade``: amounts in **milli-subunits**
- ICRC-1 ckBTC ``icrc1_balance_of``: **satoshis**
"""

MSAT_PER_SAT: int = 1_000
SATS_PER_BTC: int = 100_000_000

# ---------------------------------------------------------------------------
# BTC unit helpers
# ---------------------------------------------------------------------------

def msat_to_sats(msat: int) -> int:
    """Convert millisatoshis to satoshis (integer division)."""
    return msat // MSAT_PER_SAT


def sats_to_msat(sats: int) -> int:
    """Convert satoshis to millisatoshis."""
    return sats * MSAT_PER_SAT


def usd_to_sats(amount_usd: float, btc_usd_rate: float) -> int:
    """Convert a USD amount to satoshis given BTC/USD rate."""
    if btc_usd_rate <= 0:
        raise ValueError("btc_usd_rate must be > 0")
    return round((amount_usd / btc_usd_rate) * SATS_PER_BTC)


def sats_to_usd(sats: int, btc_usd_rate: float) -> float:
    """Convert satoshis to USD given BTC/USD rate."""
    return (sats / SATS_PER_BTC) * btc_usd_rate


# ---------------------------------------------------------------------------
# Token sub-unit helpers
# ---------------------------------------------------------------------------

def subunits_to_display(raw: int, divisibility: int = 8) -> float:
    """Convert raw sub-units to human-readable display tokens.

    Example: 100_000_000 raw with div=8 → 1.0 display-token.
    """
    return raw / (10 ** divisibility)


def display_to_subunits(display: float, divisibility: int = 8) -> int:
    """Convert human-readable display tokens to raw sub-units.

    Example: 1.0 display-token with div=8 → 100_000_000 raw.
    """
    return int(display * (10 ** divisibility))


def millisubunits_to_display(msu: int, divisibility: int = 8,
                              decimals: int = 3) -> float:
    """Convert milli-subunits (canister units) to display tokens.

    ``1 display-token = 10^(divisibility + decimals) milli-subunits``

    Example: 10_000_000_000_000 with div=8, dec=3 → 100.0 display-tokens.
    """
    return msu / (10 ** (divisibility + decimals))


def display_to_millisubunits(display: float, divisibility: int = 8,
                              decimals: int = 3) -> int:
    """Convert display tokens to milli-subunits (canister units).

    ``display * 10^(divisibility + decimals)``

    Example: 100.0 with div=8, dec=3 → 10_000_000_000_000 milli-subunits.
    """
    return int(display * (10 ** (divisibility + decimals)))


def adjust_api_decimals(balance: int, decimals: int = 0) -> float:
    """Strip the extra ``decimals`` factor from a milli-subunit balance.

    The ``/v1/user/{principal}/balances`` endpoint may embed extra decimal
    digits in the ``balance`` field.  The ``decimals`` response field tells
    how many extra powers-of-10 to divide out.

    Returns the adjusted value (still in milli-subunit scale) ready for
    further conversion with :func:`subunits_to_display` or
    :func:`_fmt_token_amount`.

    Example: balance=132_482_122_800_932, decimals=3
      → 132_482_122_800.932
    """
    if decimals > 0:
        return balance / (10 ** decimals)
    return balance


# ---------------------------------------------------------------------------
# Token value helpers (price = msat per display-token)
# ---------------------------------------------------------------------------

def token_value_sats(raw_subunits: int, price_msat: int,
                     divisibility: int = 8) -> float:
    """Value in sats of *raw_subunits* at *price_msat* per display-token.

    Formula: raw * price / 10^div / 1000
    """
    return raw_subunits * price_msat / (10 ** divisibility) / MSAT_PER_SAT


def millisubunit_value_sats(balance: int, price_msat: int,
                            divisibility: int = 8) -> float:
    """Value in sats for a balance reported in **milli-subunits**.

    Both canister ``getBalance`` and the REST API ``/v1/user/.../balances``
    return balances in milli-subunits.  Equivalent to
    ``token_value_sats(balance, price, div) / 1000``.
    """
    return token_value_sats(balance, price_msat, divisibility) / MSAT_PER_SAT


# ---------------------------------------------------------------------------
# Trade estimate helpers
# ---------------------------------------------------------------------------

def display_tokens_from_sats(sats: int, price_msat: int) -> float:
    """Estimate display-tokens received for a given sats spend.

    Formula: sats * 1000 / price
    """
    if not price_msat:
        return 0.0
    return sats * MSAT_PER_SAT / price_msat


def sats_from_display_tokens(tokens: float, price_msat: int) -> int:
    """Estimate sats received for selling *tokens* display-tokens.

    Formula: round(tokens * price / 1000)
    """
    return round(tokens * price_msat / MSAT_PER_SAT)


def millisubunits_from_sats(sats: int, price_msat: int,
                            divisibility: int = 8,
                            decimals: int = 3) -> int:
    """Estimate milli-subunits received for a given sats spend.

    Formula: int(sats * 1000 * 10^(div+dec) / price)
    """
    if not price_msat:
        return 0
    return int(sats * MSAT_PER_SAT * (10 ** (divisibility + decimals))
               / price_msat)
