"""Tests for iconfucius.units — pure unit-conversion helpers."""

import pytest

from iconfucius.units import (
    MSAT_PER_SAT,
    SATS_PER_BTC,
    adjust_api_decimals,
    display_to_millisubunits,
    display_to_subunits,
    display_tokens_from_sats,
    millisubunit_value_sats,
    millisubunits_from_sats,
    millisubunits_to_display,
    msat_to_sats,
    sats_from_display_tokens,
    sats_to_msat,
    sats_to_usd,
    subunits_to_display,
    token_value_sats,
    usd_to_sats,
)


class TestConstants:
    def test_msat_per_sat(self):
        assert MSAT_PER_SAT == 1_000

    def test_sats_per_btc(self):
        assert SATS_PER_BTC == 100_000_000


class TestBtcUnits:
    def test_msat_to_sats_basic(self):
        assert msat_to_sats(5_000_000) == 5_000

    def test_msat_to_sats_remainder_truncated(self):
        assert msat_to_sats(5_999) == 5

    def test_msat_to_sats_zero(self):
        assert msat_to_sats(0) == 0

    def test_sats_to_msat_basic(self):
        assert sats_to_msat(5_000) == 5_000_000

    def test_sats_to_msat_zero(self):
        assert sats_to_msat(0) == 0

    def test_roundtrip_sats_msat(self):
        """msat_to_sats(sats_to_msat(x)) == x for exact amounts."""
        for sats in [0, 1, 500, 100_000_000]:
            assert msat_to_sats(sats_to_msat(sats)) == sats

    def test_usd_to_sats(self):
        # $100 at $100k/BTC = 0.001 BTC = 100_000 sats
        assert usd_to_sats(100.0, 100_000.0) == 100_000

    def test_usd_to_sats_small(self):
        # $1 at $100k/BTC = 1000 sats
        assert usd_to_sats(1.0, 100_000.0) == 1_000

    def test_sats_to_usd(self):
        # 100_000 sats at $100k/BTC = $100
        assert sats_to_usd(100_000, 100_000.0) == pytest.approx(100.0)

    def test_roundtrip_usd_sats(self):
        rate = 87_000.0
        usd = 50.0
        sats = usd_to_sats(usd, rate)
        back = sats_to_usd(sats, rate)
        # Allow ±1 sat rounding
        assert abs(back - usd) < 0.01


class TestTokenSubunits:
    def test_subunits_to_display_default(self):
        # 100_000_000 raw at div=8 = 1.0
        assert subunits_to_display(100_000_000) == pytest.approx(1.0)

    def test_subunits_to_display_custom_div(self):
        assert subunits_to_display(1_000, 3) == pytest.approx(1.0)

    def test_subunits_to_display_zero(self):
        assert subunits_to_display(0) == 0.0

    def test_display_to_subunits_default(self):
        assert display_to_subunits(1.0) == 100_000_000

    def test_display_to_subunits_custom_div(self):
        assert display_to_subunits(1.0, 3) == 1_000

    def test_display_to_subunits_zero(self):
        assert display_to_subunits(0.0) == 0

    def test_roundtrip_subunits(self):
        for raw in [0, 1, 100_000_000, 2_771_411_893_677_396]:
            assert display_to_subunits(subunits_to_display(raw)) == raw


class TestMilliSubunits:
    """Tests for milli-subunit conversions (canister native units)."""

    def test_millisubunits_to_display_default(self):
        # 10^11 milli-subunits = 1.0 display token (div=8, dec=3)
        assert millisubunits_to_display(100_000_000_000) == pytest.approx(1.0)

    def test_millisubunits_to_display_100_tokens(self):
        # 100 * 10^11 = 10^13
        assert millisubunits_to_display(10_000_000_000_000) == pytest.approx(100.0)

    def test_display_to_millisubunits_default(self):
        assert display_to_millisubunits(1.0) == 100_000_000_000

    def test_display_to_millisubunits_100(self):
        assert display_to_millisubunits(100.0) == 10_000_000_000_000

    def test_roundtrip_millisubunits(self):
        for msu in [0, 100_000_000_000, 10_000_000_000_000]:
            display = millisubunits_to_display(msu)
            back = display_to_millisubunits(display)
            assert back == msu

    def test_custom_div_dec(self):
        # div=6, dec=2 → factor = 10^8
        assert display_to_millisubunits(1.0, 6, 2) == 100_000_000
        assert millisubunits_to_display(100_000_000, 6, 2) == pytest.approx(1.0)

    def test_millisubunits_from_sats_basic(self):
        # 1000 sats at 1000 msat/token, div=8, dec=3
        # = 1000 * 1000 * 10^11 / 1000 = 10^14
        assert millisubunits_from_sats(1000, 1000) == 100_000_000_000_000

    def test_millisubunits_from_sats_zero_price(self):
        assert millisubunits_from_sats(1000, 0) == 0

    def test_millisubunits_from_sats_realistic(self):
        # 500 sats at price=9415 msat/token, div=8, dec=3
        # = 500 * 1000 * 10^11 / 9415
        expected = int(500 * 1000 * 10**11 / 9415)
        assert millisubunits_from_sats(500, 9415) == expected


class TestTokenValue:
    def test_token_value_sats_basic(self):
        # 1 display token (10^8 raw) at price 1000 msat/token
        # = 10^8 * 1000 / 10^8 / 1000 = 1.0 sat
        assert token_value_sats(100_000_000, 1000) == pytest.approx(1.0)

    def test_token_value_sats_realistic(self):
        # A realistic scenario: 27,714,118.94 display tokens (raw=2_771_411_893_677_396)
        # at price 180 msat/token -> value = raw * 180 / 10^8 / 1000
        raw = 2_771_411_893_677_396
        price = 180
        expected = raw * 180 / 1e8 / 1000
        assert token_value_sats(raw, price) == pytest.approx(expected)

    def test_token_value_sats_zero_raw(self):
        assert token_value_sats(0, 1000) == 0.0

    def test_millisubunit_value_sats(self):
        # milli-subunits = raw * 1000, so value should be same as
        # token_value_sats(balance, price, div) / 1000
        balance = 2_771_411_893_677_396_000  # milli-subunits
        price = 180
        expected = token_value_sats(balance, price) / 1000
        assert millisubunit_value_sats(balance, price) == pytest.approx(expected)

    def test_millisubunit_value_sats_100_tokens(self):
        """100 display tokens at 9415 msat/token should be ~941.5 sats."""
        # 100 display tokens = 100 * 10^11 milli-subunits
        msu = 10_000_000_000_000
        price = 9415
        # Expected: 100 tokens * 9415 msat / 1000 = 941.5 sats
        assert millisubunit_value_sats(msu, price) == pytest.approx(941.5)


class TestTradeEstimates:
    def test_display_tokens_from_sats(self):
        # 1000 sats at 1000 msat/token = 1000 * 1000 / 1000 = 1000 tokens
        assert display_tokens_from_sats(1000, 1000) == pytest.approx(1000.0)

    def test_display_tokens_from_sats_high_price(self):
        # 1000 sats at 500_000 msat/token = 1000 * 1000 / 500_000 = 2.0 tokens
        assert display_tokens_from_sats(1000, 500_000) == pytest.approx(2.0)

    def test_display_tokens_from_sats_zero_price(self):
        assert display_tokens_from_sats(1000, 0) == 0.0

    def test_sats_from_display_tokens(self):
        # 1000 tokens at 1000 msat/token = 1000 * 1000 / 1000 = 1000 sats
        assert sats_from_display_tokens(1000.0, 1000) == 1000

    def test_sats_from_display_tokens_high_price(self):
        # 2.0 tokens at 500_000 msat/token = 2 * 500_000 / 1000 = 1000 sats
        assert sats_from_display_tokens(2.0, 500_000) == 1000

    def test_roundtrip_sats_tokens_sats(self):
        """Buy then sell should return ~same sats (minus rounding)."""
        sats = 10_000
        price = 180
        tokens = display_tokens_from_sats(sats, price)
        back = sats_from_display_tokens(tokens, price)
        assert abs(back - sats) <= 1


class TestBugScenarios:
    """Verify the 1_000 vs 1_000_000 bug is fixed."""

    def test_millisubunits_from_sats_not_1000x(self):
        # 500 sats at price=180 msat/token, div=8, dec=3
        # Correct:  500 * 1_000 * 10^11 / 180
        # Old bug:  500 * 1_000_000 * 10^8 / 180 (1000× too much for raw, but wrong unit)
        result = millisubunits_from_sats(500, 180)
        correct = int(500 * 1_000 * 10**11 / 180)
        assert result == correct

    def test_display_tokens_from_sats_not_1000x(self):
        # 500 sats at price=180 msat/token
        # Correct: 500 * 1000 / 180 ≈ 2777.78
        # Old bug: 500 * 1_000_000 / 180 ≈ 2_777_777.78 (1000× too much)
        result = display_tokens_from_sats(500, 180)
        correct = 500 * 1000 / 180
        assert result == pytest.approx(correct)

    def test_sats_from_display_tokens_not_1000x(self):
        # 100 display tokens at price=180 msat/token
        # Correct: 100 * 180 / 1000 = 18 sats
        # Old bug: 100 * 180 / 1_000_000 = 0.018 → rounds to 0
        result = sats_from_display_tokens(100.0, 180)
        correct = round(100.0 * 180 / 1000)
        assert result == correct
        assert result == 18

    def test_sell_check_with_millisubunits(self):
        """The canister sell check bug: sending 10^8 sub-units when 10^11
        milli-subunits were needed, causing 'Min trade amount' errors."""
        # 100 display tokens at 9415 msat/token
        msu = display_to_millisubunits(100.0)  # 10^13
        assert msu == 10_000_000_000_000
        value = millisubunit_value_sats(msu, 9415)
        assert value == pytest.approx(941.5)
        assert value > 500  # above 500 sats minimum


class TestAdjustApiDecimals:
    """Tests for adjust_api_decimals (milli-subunit decimals correction)."""

    def test_decimals_zero_no_change(self):
        """decimals=0 returns balance unchanged."""
        assert adjust_api_decimals(132_482_122_800_932, 0) == 132_482_122_800_932

    def test_decimals_default_no_change(self):
        """Default decimals=0 returns balance unchanged."""
        assert adjust_api_decimals(100_000) == 100_000

    def test_decimals_three(self):
        """Real API example: balance=132482122800932, decimals=3."""
        result = adjust_api_decimals(132_482_122_800_932, 3)
        assert result == pytest.approx(132_482_122_800.932)

    def test_decimals_with_display_conversion(self):
        """Full chain: adjust decimals then convert to display tokens."""
        raw = 132_482_122_800_932
        adjusted = adjust_api_decimals(raw, decimals=3)
        display = subunits_to_display(int(adjusted), divisibility=8)
        assert display == pytest.approx(1324.82, rel=0.01)
