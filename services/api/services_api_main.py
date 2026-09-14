"""Volterra FastAPI service.

The service is deliberately demo-first: it uses deterministic in-memory data when
no database/provider integration is configured, while keeping contracts ready for
persistent snapshots and a worker-backed provider.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.quant.black_scholes import implied_vol
from src.quant.diagnostics import arbitrage_diagnostics
from src.quant.surface import build_surface

app = FastAPI(title="Volterra API", version="1.0.0")
router = APIRouter(prefix="/v1")
MODEL_VERSION = "demo"


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
    instrument: str
    underlying: str
    expiry: datetime
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


DEMO_K = np.linspace(-0.8, 0.8, 41)
DEMO_T = np.array([7, 14, 30, 60, 90, 180, 365], dtype=float) / 365.0
DEMO_IV = np.array([
    0.78 + 0.12 * np.exp(-((DEMO_K + 0.12) / 0.40) ** 2) + 0.04 * np.sqrt(t)
    - 0.10 * DEMO_K for t in DEMO_T
])


def provenance() -> dict[str, Any]:
    return {"source": "deterministic_demo", "model_version": MODEL_VERSION,
            "observed_at": datetime.now(timezone.utc).isoformat(), "stale": True}


def surface_payload() -> dict[str, Any]:
    return {"coordinate_system": "log_forward_moneyness_total_variance",
            "moneyness": DEMO_K.tolist(), "maturities": DEMO_T.tolist(),
            "iv": DEMO_IV.tolist(), "diagnostics": {"mode": "demo"},
            "provenance": provenance()}


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model_version": MODEL_VERSION, "demo_mode": True}


@router.get("/quotes/{underlying}")
def quotes(underlying: str, limit: int = Query(100, ge=1, le=5000)) -> dict[str, Any]:
    return {"underlying": underlying.upper(), "quotes": [], "count": 0,
            "provenance": provenance(), "limit": limit}


@router.get("/surfaces/{underlying}")
def get_surface(underlying: str, snapshot: str = "latest") -> dict[str, Any]:
    payload = surface_payload()
    payload.update({"underlying": underlying.upper(), "snapshot": snapshot})
    return payload


@router.post("/iv")
def calculate_iv(req: IVRequest) -> dict[str, Any]:
    iv, status = implied_vol(req.price, req.spot, req.strike, req.time_to_expiry,
                             req.rate, req.dividend_yield, req.option_type == "call")
    return {"iv": iv, "status": status}


@router.post("/surfaces/build")
def build_surface_endpoint(req: SurfaceBuildRequest) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = build_surface([q.model_dump() for q in req.quotes],
                               moneyness=req.moneyness, maturities=req.maturities)
    except Exception as exc:
        raise HTTPException(422, f"surface construction failed: {exc}") from exc
    result["latency_ms"] = (time.perf_counter() - started) * 1000
    result["provenance"] = {"source": "request_quotes", "model_version": MODEL_VERSION}
    return result


@router.post("/calibrations/heston")
def calibrate_heston(payload: dict[str, Any]) -> dict[str, Any]:
    return {"parameters": {}, "rmse": None, "latency_ms": None,
            "model_version": MODEL_VERSION, "status": "demo_not_calibrated"}


@router.post("/scenarios")
def scenario(req: ScenarioRequest) -> dict[str, Any]:
    shifted_k = (DEMO_K - np.log1p(req.spot_shock)).tolist()
    maturity_scale = np.sqrt(np.maximum(DEMO_T[:, None], 1e-8))
    shifted = np.maximum(DEMO_IV ** 2 + req.vol_shift * maturity_scale
                         + req.skew_shift * np.asarray(shifted_k)[None, :], 1e-8)
    return {"underlying": req.underlying.upper(), "snapshot": req.snapshot,
            "moneyness": shifted_k, "maturities": DEMO_T.tolist(),
            "iv": np.sqrt(shifted).tolist(), "diagnostics": {"mode": "demo"},
            "provenance": provenance()}


@router.get("/metrics")
def metrics() -> dict[str, Any]:
    return {"mode": "demo", "quote_count": 0, "accepted_quote_count": 0,
            "iv_failure_rate": None, "butterfly_violation_rate": None,
            "calendar_violation_rate": None, "model_version": MODEL_VERSION}


app.include_router(router)
