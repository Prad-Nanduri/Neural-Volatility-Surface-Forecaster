"""Regenerate tests/fixtures/btc_chain_demo.json deterministically.

Builds a synthetic-but-realistic BTC option chain: a parametric smile
(total variance w(k, T) = a + b*(rho*(k-m) + sqrt((k-m)^2 + s^2)), SVI-style
raw parameterization) priced through Black-Scholes with a fixed bid/ask
spread convention. No live Deribit data required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from quant.black_scholes import bs_price  # noqa: E402

SPOT = 65_000.0
RATE = 0.03
OBSERVED_AT = "2026-09-14T00:00:00Z"

# Expiries in days and per-expiry SVI-style params (a, b, rho, m, s).
EXPIRIES = {
    7: (0.0012, 0.020, -0.35, 0.05, 0.15),
    30: (0.0040, 0.030, -0.30, 0.04, 0.20),
    60: (0.0090, 0.035, -0.28, 0.03, 0.25),
    90: (0.0140, 0.040, -0.25, 0.02, 0.30),
    180: (0.0300, 0.045, -0.22, 0.02, 0.35),
}

# 15 relative strikes per expiry, ~0.75x to ~1.35x spot.
REL_STRIKES = [0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 1.00,
               1.025, 1.05, 1.10, 1.15, 1.20, 1.25, 1.35]


def svi_total_variance(k, a, b, rho, m, s):
    import math

    return a + b * (rho * (k - m) + math.sqrt((k - m) ** 2 + s * s))


def main() -> None:
    import math

    quotes = []
    for days, (a, b, rho, m, s) in EXPIRIES.items():
        T = days / 365.0
        F = SPOT * math.exp(RATE * T)
        for rel in REL_STRIKES:
            K = round(rel * F, -1)  # round to nearest 10 like Deribit strikes
            k = math.log(K / F)
            w = svi_total_variance(k, a, b, rho, m, s)
            iv = math.sqrt(w / T)
            for option_type in ("call", "put"):
                mid = bs_price(SPOT, K, T, RATE, 0.0, iv, option_type == "call")
                if mid <= 0:
                    continue
                # spread ~0.6% of mid + small absolute floor
                half = max(0.003 * mid, 0.5)
                quotes.append(
                    {
                        "instrument": f"BTC-{days}D-{int(K)}-{option_type[0].upper()}",
                        "expiry_years": T,
                        "strike": K,
                        "option_type": option_type,
                        "bid": round(max(mid - half, 0.0), 8),
                        "ask": round(mid + half, 8),
                        "mark": round(mid, 8),
                        "implied_vol": round(iv, 6),
                    }
                )

    fixture = {
        "underlying": "BTC",
        "source": "synthetic-demo",
        "observed_at": OBSERVED_AT,
        "spot": SPOT,
        "rate": RATE,
        "dividend_yield": 0.0,
        "quotes": quotes,
    }
    out = Path(__file__).with_name("btc_chain_demo.json")
    out.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"wrote {len(quotes)} quotes -> {out}")


if __name__ == "__main__":
    main()
