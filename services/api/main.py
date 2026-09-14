"""Volterra API skeleton.

Real endpoints (/v1/quotes, /v1/surfaces, /v1/iv, /v1/calibrations,
/v1/scenarios, /v1/metrics) land in a later session — see README roadmap.
"""

from fastapi import FastAPI

app = FastAPI(title="Volterra API", version="0.1.0")


@app.get("/v1/health")
def health():
    return {"status": "ok", "model_version": "none"}
