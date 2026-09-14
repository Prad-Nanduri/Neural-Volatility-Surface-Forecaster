import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_surface_fallback_serves_fixture():
    r = client.get("/v1/surfaces/BTC")
    assert r.status_code == 200
    body = r.json()
    assert body["coordinate_system"] == "log_forward_moneyness_total_variance"
    assert len(body["moneyness"]) == 41
    assert len(body["maturities"]) == 12
    assert len(body["iv"]) == 12
    assert body["provenance"]["stale"] is True
    assert body["diagnostics"]["butterfly_violation_rate"] < 0.05


def test_quotes_fallback():
    r = client.get("/v1/quotes/BTC?limit=10")
    assert r.status_code == 200
    assert r.json()["count"] == 10


def test_iv_endpoint_round_trip():
    r = client.post("/v1/iv", json={
        "price": 10.0, "spot": 100.0, "strike": 100.0,
        "time_to_expiry": 0.25, "rate": 0.0, "option_type": "call",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["iv"] == pytest.approx(0.5, abs=0.05)


def test_scenario_endpoint():
    r = client.post("/v1/scenarios", json={"underlying": "BTC", "vol_shift": 0.01})
    assert r.status_code == 200
    body = r.json()
    assert len(body["iv"]) == 12


def test_metrics():
    r = client.get("/v1/metrics")
    assert r.status_code == 200
    assert r.json()["quote_count"] > 0
