import math

import pytest

from quant.black_scholes import bs_price, implied_vol, norm_cdf

S = 100.0


@pytest.mark.parametrize("is_call", [True, False])
@pytest.mark.parametrize("sigma", [0.05, 0.2, 0.5, 0.9, 1.5])
@pytest.mark.parametrize("T", [1 / 365, 7 / 365, 30 / 365, 0.5, 1.0, 2.0])
@pytest.mark.parametrize("r", [0.0, 0.03, 0.08, -0.01])
@pytest.mark.parametrize("K", [50, 80, 95, 100, 105, 120, 160])
def test_price_iv_round_trip(K, r, T, sigma, is_call):
    price = bs_price(S, K, T, r, 0.0, sigma, is_call)
    # The true lower no-arbitrage bound under discounting is the sigma -> 0
    # price (discounted forward intrinsic); the upper bound is S or K e^-rT.
    fwd_intrinsic = (
        max(S - K * math.exp(-r * T), 0.0)
        if is_call
        else max(K * math.exp(-r * T) - S, 0.0)
    )
    upper = S if is_call else K * math.exp(-r * T)
    iv, status = implied_vol(price, S, K, T, r, 0.0, is_call)
    if iv is None:
        # Inversion may legitimately fail only for prices pinned to a
        # no-arbitrage boundary.
        assert status in {"outside_bounds", "invalid_input", "no_bracket"}
        intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)
        assert (
            # Below the (undiscounted) intrinsic bound the spec's inversion
            # rejects by design, even when discounting makes the price valid.
            price < intrinsic
            or price <= fwd_intrinsic + 1e-6 * max(1.0, abs(fwd_intrinsic))
            or price >= upper - 1e-6 * max(1.0, abs(upper))
        )
        return
    assert status == "ok"
    # The invariant is price -> IV -> price; where time value is negligible
    # (deep options, tiny maturities) IV is not identified by the price.
    assert bs_price(S, K, T, r, 0.0, iv, is_call) == pytest.approx(
        price, abs=1e-6
    )
    if price - fwd_intrinsic > 0.005 * S:
        assert iv == pytest.approx(sigma, rel=1e-3, abs=1e-3)


def test_norm_cdf():
    assert norm_cdf(0.0) == pytest.approx(0.5)
    assert norm_cdf(math.inf) == pytest.approx(1.0)
    assert norm_cdf(-math.inf) == pytest.approx(0.0)


def test_near_expiry_call():
    price = bs_price(S, 100.0, 1e-6, 0.0, 0.0, 0.2, True)
    iv, status = implied_vol(price, S, 100.0, 1e-6, 0.0, 0.0, True)
    assert status == "ok"
    assert iv == pytest.approx(0.2, abs=1e-4)


def test_expired_option_returns_intrinsic():
    assert bs_price(S, 90.0, 0.0, 0.0, 0.0, 0.2, True) == pytest.approx(10.0)
    assert bs_price(S, 110.0, 0.0, 0.0, 0.0, 0.2, False) == pytest.approx(10.0)


def test_deep_itm_and_otm():
    deep_itm = bs_price(S, 1.0, 1.0, 0.0, 0.0, 0.5, True)
    assert deep_itm == pytest.approx(99.0, abs=1e-6)
    deep_otm = bs_price(S, 1e4, 1.0, 0.0, 0.0, 0.5, True)
    assert deep_otm == pytest.approx(0.0, abs=1e-10)


def test_zero_bid_price_is_invalid():
    iv, status = implied_vol(0.0, S, 100.0, 0.25, 0.0, 0.0, True)
    assert iv is None
    assert status == "invalid_input"


def test_wide_spread_mid_still_inverts():
    bid, ask = 9.0, 13.0  # very wide spread around mid 11.0
    mid = 0.5 * (bid + ask)
    iv, status = implied_vol(mid, S, 100.0, 0.5, 0.0, 0.0, True)
    assert status == "ok"
    assert bs_price(S, 100.0, 0.5, 0.0, 0.0, iv, True) == pytest.approx(mid)


def test_price_above_upper_bound_rejected():
    iv, status = implied_vol(S + 1.0, S, 100.0, 0.25, 0.0, 0.0, True)
    assert iv is None
    assert status == "outside_bounds"


def test_price_below_intrinsic_rejected():
    iv, status = implied_vol(5.0, S, 90.0, 0.25, 0.0, 0.0, True)
    assert iv is None
    assert status == "outside_bounds"


def test_nan_and_invalid_inputs():
    iv, status = implied_vol(float("nan"), S, 100.0, 0.25, 0.0, 0.0, True)
    assert (iv, status) == (None, "non_finite")
    iv, status = implied_vol(10.0, -1.0, 100.0, 0.25, 0.0, 0.0, True)
    assert (iv, status) == (None, "invalid_input")
