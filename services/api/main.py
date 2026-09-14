"""Volterra FastAPI service.

The service is deliberately demo-first: when no database/provider integration
is configured it serves the deterministic demo fixture
(``tests/fixtures/btc_chain_demo.json``) as a stale-data fallback, while
keeping contracts ready for persistent snapshots and a worker-backed provider.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from quant.black_scholes import implied_vol
from quant.surface import build_surface

app = FastAPI(title="Volterra API", version="1.0.0")

# The demo frontend is served from a different origin (Vercel/localhost);
# allow cross-origin GETs so the deployed UI can fetch surfaces.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
router = APIRouter(prefix="/v1")
MODEL_VERSION = os.getenv("MODEL_VERSION", "demo")


class IVRequest(BaseModel):
    price: float = Field(gt=0)
    spot: float = Field(gt=0)
    strike: float = Field(gt=0)
    time_to_expiry: float = Field(gt=0)
    rate: float = 0.0
    dividend_yield: float = 0.0
    option_type: str = "call"

    @field_validator("option_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        if value not in {"call", "put"}:
            raise ValueError("option_type must be call or put")
        return value


class Quote(BaseModel):
    instrument: str = ""
    underlying: str = "BTC"
    expiry: datetime | None = None
    expiry_years: float | None = None
    strike: float = Field(gt=0)
    option_type: str
    bid: float | None = None
    ask: float | None = None
    mark: float | None = None
    underlying_price: float = Field(gt=0)
    interest_rate: float = 0.0
    dividend_yield: float = 0.0


class SurfaceBuildRequest(BaseModel):
    quotes: list[Quote] = Field(min_length=1)
    moneyness: list[float] | None = None
    maturities: list[float] | None = None


class ScenarioRequest(BaseModel):
    underlying: str = "BTC"
    snapshot: str = "latest"
    spot_shock: float = Field(0.0, gt=-0.99)
    vol_shift: float = 0.0
    skew_shift: float = 0.0


def _fixture_path() -> Path:
    override = os.getenv("VOLTERRA_DEMO_FIXTURE")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        candidate = parent / "tests" / "fixtures" / "btc_chain_demo.json"
        if candidate.exists():
            return candidate
        candidate = parent / "demo_fixture.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("demo fixture not found")


@lru_cache(maxsize=1)
def _demo_fixture() -> dict[str, Any]:
    return json.loads(_fixture_path().read_text())


def _fixture_quote_dicts() -> list[dict[str, Any]]:
    data = _demo_fixture()
    return [
        {
            **q,
            "underlying_price": data["spot"],
            "interest_rate": data["rate"],
            "dividend_yield": data.get("dividend_yield", 0.0),
        }
        for q in data["quotes"]
    ]


@lru_cache(maxsize=8)
def _demo_surface(underlying: str) -> dict[str, Any]:
    return build_surface(_fixture_quote_dicts())


def provenance() -> dict[str, Any]:
    return {
        "source": _demo_fixture().get("source", "deterministic_demo"),
        "model_version": MODEL_VERSION,
        "observed_at": _demo_fixture().get("observed_at"),
        "served_at": datetime.now(UTC).isoformat(),
        "stale": True,
    }


def surface_payload(underlying: str) -> dict[str, Any]:
    payload = _demo_surface(underlying)
    return {
        "underlying": underlying.upper(),
        "coordinate_system": payload["coordinate_system"],
        "moneyness": payload["moneyness"],
        "maturities": payload["maturities"],
        "iv": payload["iv"],
        "total_variance": payload["total_variance"],
        "diagnostics": payload["diagnostics"],
        "coverage": payload["coverage"],
        "provenance": provenance(),
    }


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model_version": MODEL_VERSION, "demo_mode": True}


@router.get("/quotes/{underlying}")
def quotes(underlying: str, limit: int = Query(100, ge=1, le=5000)) -> dict[str, Any]:
    data = _demo_fixture()
    return {
        "underlying": underlying.upper(),
        "quotes": data["quotes"][:limit],
        "count": min(len(data["quotes"]), limit),
        "spot": data["spot"],
        "rate": data["rate"],
        "provenance": provenance(),
        "limit": limit,
    }


@router.get("/surfaces/{underlying}")
def get_surface(underlying: str, snapshot: str = "latest") -> dict[str, Any]:
    payload = surface_payload(underlying)
    payload["snapshot"] = snapshot
    return payload


@router.post("/iv")
def calculate_iv(req: IVRequest) -> dict[str, Any]:
    iv, status = implied_vol(
        req.price,
        req.spot,
        req.strike,
        req.time_to_expiry,
        req.rate,
        req.dividend_yield,
        req.option_type == "call",
    )
    return {"iv": iv, "status": status}


@router.post("/surfaces/build")
def build_surface_endpoint(req: SurfaceBuildRequest) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = build_surface(
            [q.model_dump() for q in req.quotes],
            moneyness=req.moneyness,
            maturities=req.maturities,
        )
    except Exception as exc:
        raise HTTPException(422, f"surface construction failed: {exc}") from exc
    result["latency_ms"] = (time.perf_counter() - started) * 1000
    result["provenance"] = {"source": "request_quotes", "model_version": MODEL_VERSION}
    return result


@router.post("/calibrations/heston")
def calibrate_heston(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "parameters": {},
        "rmse": None,
        "latency_ms": None,
        "model_version": MODEL_VERSION,
        "status": "demo_not_calibrated",
    }


@router.post("/scenarios")
def scenario(req: ScenarioRequest) -> dict[str, Any]:
    payload = _demo_surface(req.underlying)
    k = np.asarray(payload["moneyness"])
    T = np.asarray(payload["maturities"])
    w = np.asarray(payload["total_variance"])
    shifted_k = k - np.log1p(req.spot_shock)
    maturity_scale = np.sqrt(np.maximum(T[:, None], 1e-8))
    shifted = np.maximum(
        w + req.vol_shift * maturity_scale + req.skew_shift * shifted_k[None, :],
        1e-8,
    )
    return {
        "underlying": req.underlying.upper(),
        "snapshot": req.snapshot,
        "moneyness": shifted_k.tolist(),
        "maturities": T.tolist(),
        "iv": np.sqrt(shifted / T[:, None]).tolist(),
        "diagnostics": payload["diagnostics"],
        "provenance": provenance(),
    }


@router.get("/metrics")
def metrics() -> dict[str, Any]:
    payload = _demo_surface("BTC")
    coverage = payload["coverage"]
    return {
        "mode": "demo",
        "quote_count": coverage["n_quotes"],
        "accepted_quote_count": coverage["n_accepted"],
        "iv_failure_rate": coverage["n_rejected"] / max(coverage["n_quotes"], 1),
        "butterfly_violation_rate": payload["diagnostics"]["butterfly_violation_rate"],
        "calendar_violation_rate": payload["diagnostics"]["calendar_violation_rate"],
        "model_version": MODEL_VERSION,
    }


app.include_router(router)
