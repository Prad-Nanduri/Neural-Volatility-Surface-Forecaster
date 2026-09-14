import json
from pathlib import Path

import numpy as np
import pytest

from quant.diagnostics import arbitrage_diagnostics
from quant.surface import (
    RawQuote,
    assemble_surface,
    log_forward_moneyness,
)

FIXTURE = Path(__file__).parent / "fixtures" / "btc_chain_demo.json"


def load_quotes():
    data = json.loads(FIXTURE.read_text())
    quotes = [
        RawQuote(
            strike=q["strike"],
            expiry_years=q["expiry_years"],
            option_type=q["option_type"],
            bid=q["bid"],
            ask=q["ask"],
            spot=data["spot"],
            rate=data["rate"],
            dividend_yield=data["dividend_yield"],
        )
        for q in data["quotes"]
    ]
    return data, quotes


def test_log_forward_moneyness():
    assert log_forward_moneyness(100.0, 100.0) == pytest.approx(0.0)
    assert log_forward_moneyness(np.e, 1.0) == pytest.approx(1.0)


def test_fixture_is_deterministic():
    data = json.loads(FIXTURE.read_text())
    assert data["underlying"] == "BTC"
    expiries = {q["expiry_years"] for q in data["quotes"]}
    assert len(expiries) == 5


def test_assemble_surface_shapes():
    _, quotes = load_quotes()
    result = assemble_surface(quotes)
    assert result.moneyness.shape == (41,)
    assert result.maturities.shape == (12,)
    assert result.total_variance.shape == (12, 41)
    assert result.implied_vol.shape == (12, 41)
    assert result.call_prices.shape == (12, 41)
    assert np.all(result.total_variance >= 0.0)
    assert result.n_accepted > 0
    assert result.n_accepted <= result.n_quotes


def test_assemble_surface_diagnostics():
    _, quotes = load_quotes()
    result = assemble_surface(quotes)
    for key in (
        "butterfly_violation_rate",
        "calendar_violation_rate",
        "worst_butterfly",
        "worst_calendar",
    ):
        assert key in result.diagnostics
    # A smooth synthetic surface should be essentially arbitrage-free.
    assert result.diagnostics["butterfly_violation_rate"] < 0.05
    assert result.diagnostics["calendar_violation_rate"] < 0.05


def test_bad_quotes_are_rejected():
    _, quotes = load_quotes()
    bad = [
        RawQuote(100, 0.1, "call", bid=0.0, ask=1.0, spot=100.0),  # zero bid
        RawQuote(100, 0.1, "call", bid=5.0, ask=4.0, spot=100.0),  # crossed
        RawQuote(100, 0.1, "call", bid=None, ask=None, spot=100.0),
        RawQuote(100, -1.0, "call", bid=1.0, ask=2.0, spot=100.0),
    ]
    result = assemble_surface(quotes + bad)
    assert len(result.rejected) >= 4


def test_empty_quotes_raise():
    with pytest.raises(ValueError):
        assemble_surface([])


def test_arbitrage_diagnostics_detects_violations():
    # Butterfly violation: prices concave in strike (peaked middle strike).
    call_prices = np.array([[1.0, 10.0, 1.0]])
    total_var = np.array([[0.1, 0.1, 0.1], [0.2, 0.2, 0.2]])
    diag = arbitrage_diagnostics(call_prices, total_var)
    assert diag["butterfly_violation_rate"] > 0.0
    assert diag["worst_butterfly"] < 0.0

    # Calendar violation: total variance decreasing in maturity.
    total_var_bad = np.array([[0.3, 0.3, 0.3], [0.1, 0.1, 0.1]])
    diag = arbitrage_diagnostics(call_prices, total_var_bad)
    assert diag["calendar_violation_rate"] == 1.0
    assert diag["worst_calendar"] < 0.0
