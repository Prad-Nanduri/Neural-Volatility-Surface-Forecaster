# Volterra — Neural Volatility Surface Lab

This system turns noisy option quotes into a diagnosable, arbitrage-aware
surface and (in later phases) uses a learned pricing surrogate to accelerate
interpretable stochastic-volatility calibration.

## Repository layout

```text
apps/web/                 # Next.js frontend (placeholder)
services/api/             # FastAPI service (skeleton + migrations)
services/worker/          # ingestion and scheduled snapshots (placeholder)
src/quant/                # shared numerical code
  black_scholes.py        # BS pricing + Brent implied-vol inversion
  surface.py              # quote -> total-variance surface assembly
  diagnostics.py          # butterfly/calendar arbitrage diagnostics
ml/                       # surrogate dataset / training / evaluation (stubs)
tests/                    # pytest suite + deterministic BTC demo fixture
docker-compose.yml        # postgres + redis + api
pyproject.toml            # packaging, ruff, pytest config
package.json              # npm workspaces root (apps/web)
.github/workflows/ci.yml  # lint + tests + smoke test
```

## Surface coordinate convention

All surface work happens in **log-forward moneyness** and **total variance**,
not raw strike and raw implied volatility:

- `k = log(K / F)` where `F = S * exp((r - q) * T)` is the forward price.
- `w(k, T) = sigma_iv(k, T)^2 * T`.

Working in `(k, w)` behaves better across maturities than fitting IV against
strike, and makes the calendar no-arbitrage condition a simple monotonicity
check: `w` should be non-decreasing in `T` at fixed `k`. Butterfly arbitrage
is checked on repriced calls (convexity in strike). See
`src/quant/surface.py` and `src/quant/diagnostics.py`.

## Local development

```bash
pip install -e .[dev]
ruff check .
pytest -q
python ml/evaluate.py --smoke-test   # builds a surface from the demo fixture
docker compose up postgres redis     # local state services
```

The deterministic demo chain (`tests/fixtures/btc_chain_demo.json`,
regenerate via `tests/fixtures/generate_demo_fixture.py`) lets downstream
work proceed without Deribit access.

## Next steps (not yet implemented)

- FastAPI endpoints (`/v1/quotes`, `/v1/surfaces`, `/v1/iv`,
  `/v1/calibrations/heston`, `/v1/scenarios`, `/v1/metrics`).
- Deribit ingestion worker + Redis caching + PostgreSQL persistence.
- Next.js dashboard with Plotly surface/skew/term-structure views.
- Heston surrogate dataset generation, training, and calibration benchmark.
- Deployment (Vercel frontend + Railway/Render services).
