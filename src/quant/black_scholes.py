from math import erf, exp, log, sqrt

from scipy.optimize import brentq

SQRT2 = sqrt(2.0)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / SQRT2))


def bs_price(S, K, T, r, q, sigma, is_call=True):
    if T <= 0:
        intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)
        return intrinsic
    if sigma <= 0:
        forward_intrinsic = max(S * exp(-q * T) - K * exp(-r * T), 0.0)
        return (
            forward_intrinsic
            if is_call
            else forward_intrinsic + K * exp(-r * T) - S * exp(-q * T)
        )

    d1 = (log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    if is_call:
        return S * exp(-q * T) * norm_cdf(d1) - K * exp(-r * T) * norm_cdf(d2)
    return K * exp(-r * T) * norm_cdf(-d2) - S * exp(-q * T) * norm_cdf(-d1)


def implied_vol(price, S, K, T, r, q, is_call=True):
    if not all(map(lambda x: x == x, [price, S, K, T, r, q])):
        return None, "non_finite"
    if price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None, "invalid_input"

    intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)
    upper = S if is_call else K * exp(-r * T)
    if price < intrinsic - 1e-8 or price > upper + 1e-8:
        return None, "outside_bounds"

    def f(vol):
        return bs_price(S, K, T, r, q, vol, is_call) - price

    try:
        value = brentq(f, 1e-8, 8.0, xtol=1e-9, rtol=1e-9, maxiter=100)
        return value, "ok"
    except ValueError:
        return None, "no_bracket"
