"""Surface assembly on a fixed (log-forward moneyness, maturity) grid.

Pipeline (spec section 5):
  1. Convert every valid quote to IV and then to total variance w = iv^2 * T.
  2. Transform strike to log-forward moneyness k = log(K / F).
  3. Deduplicate nearby points, preferring tighter bid/ask spreads.
  4. Fit on a fixed grid: 41 moneyness points x 12 maturities.
  5. Interpolate per maturity, then smooth across maturity.
  6. Reprice the IV grid to produce price-space diagnostics.
  7. Report coverage, rejected quotes, max residual, and arbitrage violations.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from quant.black_scholes import bs_price, implied_vol
from quant.diagnostics import arbitrage_diagnostics

# Fixed grids (spec section 5, step 4).
DEFAULT_MONEYNESS_GRID = np.linspace(-1.0, 1.0, 41)
DEFAULT_MATURITY_GRID = np.array(
    [7, 14, 21, 30, 45, 60, 90, 120, 150, 180, 270, 365], dtype=float
) / 365.0

MIN_PRICE_TICK = 1e-6
DEDUP_K_TOLERANCE = 1e-3
MATURITY_SMOOTH_WINDOW = 3


@dataclass(frozen=True)
class RawQuote:
    strike: float
    expiry_years: float
    option_type: str  # "call" or "put"
    bid: float | None
    ask: float | None
    spot: float
    rate: float = 0.0
    dividend_yield: float = 0.0


@dataclass
class SurfaceResult:
    moneyness: np.ndarray  # shape (41,)
    maturities: np.ndarray  # shape (12,)
    total_variance: np.ndarray  # shape (12, 41)
    implied_vol: np.ndarray  # shape (12, 41)
    call_prices: np.ndarray  # shape (12, 41), repriced for diagnostics
    forwards: np.ndarray  # shape (12,)
    diagnostics: dict = field(default_factory=dict)
    n_quotes: int = 0
    n_accepted: int = 0
    rejected: list = field(default_factory=list)
    max_residual: float = 0.0


def mid_price(quote: RawQuote) -> float | None:
    """Prefer the mid when both sides are positive; reject crossed markets."""
    bid, ask = quote.bid, quote.ask
    if bid is None or ask is None:
        return None
    if not (math.isfinite(bid) and math.isfinite(ask)):
        return None
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return 0.5 * (bid + ask)


def log_forward_moneyness(strike, forward):
    return np.log(np.asarray(strike, dtype=float) / forward)


def forward_price(spot, rate, dividend_yield, T):
    return spot * math.exp((rate - dividend_yield) * T)


def _quotes_to_points(
    quotes: Sequence[RawQuote],
) -> tuple[list[tuple[float, float, float, float]], list[dict]]:
    """Steps 1-2: quote -> (T, k, w, spread); collect rejected quotes."""
    points: list[tuple[float, float, float, float]] = []
    rejected: list[dict] = []
    for q in quotes:
        mid = mid_price(q)
        if mid is None or mid < MIN_PRICE_TICK:
            rejected.append({"strike": q.strike, "reason": "bad_quotes"})
            continue
        if q.option_type not in ("call", "put") or q.expiry_years <= 0:
            rejected.append({"strike": q.strike, "reason": "invalid_input"})
            continue
        iv, status = implied_vol(
            mid, q.spot, q.strike, q.expiry_years,
            q.rate, q.dividend_yield, q.option_type == "call",
        )
        if iv is None:
            rejected.append({"strike": q.strike, "reason": status})
            continue
        F = forward_price(q.spot, q.rate, q.dividend_yield, q.expiry_years)
        k = float(log_forward_moneyness(q.strike, F))
        w = iv * iv * q.expiry_years
        if q.ask is not None and q.bid is not None:
            spread = q.ask - q.bid
        else:
            spread = math.inf
        points.append((q.expiry_years, k, w, spread))
    return points, rejected


def _deduplicate(points):
    """Step 3: within a (maturity, ~k) bucket keep the tightest-spread point."""
    best: dict[tuple[int, int], tuple[float, float, float, float]] = {}
    for T, k, w, spread in points:
        key = (round(T, 6), round(k / DEDUP_K_TOLERANCE))
        if key not in best or spread < best[key][3]:
            best[key] = (T, k, w, spread)
    return list(best.values())


def _smooth_across_maturities(w: np.ndarray) -> np.ndarray:
    """Step 5b: light moving-average smoothing along the maturity axis."""
    n = MATURITY_SMOOTH_WINDOW // 2
    out = w.copy()
    for j in range(w.shape[0]):
        lo, hi = max(0, j - n), min(w.shape[0], j + n + 1)
        window = w[lo:hi]
        out[j] = np.nanmean(window, axis=0)
    return out


def assemble_surface(
    quotes: Sequence[RawQuote],
    moneyness_grid: np.ndarray = DEFAULT_MONEYNESS_GRID,
    maturity_grid: np.ndarray = DEFAULT_MATURITY_GRID,
) -> SurfaceResult:
    """Steps 1-7: quotes -> gridded total-variance surface with diagnostics."""
    k_grid = np.asarray(moneyness_grid, dtype=float)
    T_grid = np.asarray(maturity_grid, dtype=float)

    points, rejected = _quotes_to_points(quotes)
    points = _deduplicate(points)

    W = np.full((len(T_grid), len(k_grid)), np.nan)
    spot = quotes[0].spot if quotes else np.nan
    rate = quotes[0].rate if quotes else 0.0
    div = quotes[0].dividend_yield if quotes else 0.0
    forwards = np.array([forward_price(spot, rate, div, T) for T in T_grid])

    # Steps 4-5a: per observed maturity, interpolate w across k; assign each
    # observed maturity's slice to the nearest grid maturity.
    by_maturity: dict[float, list[tuple[float, float, float, float]]] = {}
    for p in points:
        by_maturity.setdefault(round(p[0], 6), []).append(p)

    for T_obs, pts in by_maturity.items():
        ks = np.array([p[1] for p in pts])
        ws = np.array([p[2] for p in pts])
        order = np.argsort(ks)
        ks, ws = ks[order], ws[order]
        j = int(np.argmin(np.abs(T_grid - T_obs)))
        W[j] = np.interp(k_grid, ks, ws)

    # Fill grid maturities with no observations by nearest observed slice.
    observed_rows = [j for j in range(len(T_grid)) if not np.all(np.isnan(W[j]))]
    if not observed_rows:
        raise ValueError("no valid quotes: cannot assemble a surface")
    for j in range(len(T_grid)):
        if np.all(np.isnan(W[j])):
            nearest = min(observed_rows, key=lambda r: abs(r - j))
            W[j] = W[nearest]

    W = _smooth_across_maturities(np.maximum(W, 0.0))

    # Step 6: back out IV and reprice calls for diagnostics. The butterfly
    # check uses raw second differences, so reprice on strikes evenly spaced
    # in K (equal k-spacing is not equal K-spacing).
    iv_grid = np.sqrt(np.maximum(W, 0.0) / T_grid[:, None])
    call_prices = np.empty_like(W)
    for j, T in enumerate(T_grid):
        F = forwards[j]
        K_lo, K_hi = F * math.exp(k_grid[0]), F * math.exp(k_grid[-1])
        K_diag = np.linspace(K_lo, K_hi, len(k_grid))
        w_diag = np.interp(np.log(K_diag / F), k_grid, W[j])
        iv_diag = np.sqrt(np.maximum(w_diag, 0.0) / T)
        call_prices[j] = [
            bs_price(spot, K, T, rate, div, iv, True)
            for K, iv in zip(K_diag, iv_diag, strict=True)
        ]

    # Step 7: coverage, repricing residual vs observed mids, arbitrage.
    max_residual = 0.0
    for T, k, w, _spread in points:
        j = int(np.argmin(np.abs(T_grid - T)))
        w_hat = float(np.interp(k, k_grid, W[j]))
        max_residual = max(max_residual, abs(w_hat - w))

    diagnostics = arbitrage_diagnostics(call_prices, W)

    return SurfaceResult(
        moneyness=k_grid,
        maturities=T_grid,
        total_variance=W,
        implied_vol=iv_grid,
        call_prices=call_prices,
        forwards=forwards,
        diagnostics=diagnostics,
        n_quotes=len(quotes),
        n_accepted=len(points),
        rejected=rejected,
        max_residual=max_residual,
    )
