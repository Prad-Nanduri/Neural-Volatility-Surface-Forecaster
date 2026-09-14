# Deploying Volterra

## Frontend (apps/web) — Vercel

Deployed via the Vercel CLI:

```bash
cd apps/web
vercel link --yes --project volterra-web
vercel env add NEXT_PUBLIC_API_BASE production   # value: https://<your-api-host>
vercel deploy --prod
```

`NEXT_PUBLIC_API_BASE` is baked into the build — after the API URL is known or
changes, update the env var (`vercel env rm` / `vercel env add`) and redeploy
with `vercel deploy --prod`.

## API (services/api) — Railway or Render

The service ships `services/api/Dockerfile` (build context = repo root). It
bundles `src/quant`, the demo fixture, and exposes port 8000 with a health
check at `/v1/health`.

### Railway (railway.toml is committed)

```bash
npm i -g @railway/cli
railway login
railway init            # create project "volterra-api"
railway up              # builds services/api/Dockerfile with repo-root context
railway domain          # prints the public URL
```

Or in the dashboard: New Project → Deploy from GitHub repo → Railway detects
`railway.toml` and the Dockerfile automatically. Set variable `PORT` is not
needed (uvicorn binds 8000); Railway routes to the exposed port. The health
check path is already configured to `/v1/health`.

### Render (render.yaml is committed)

Dashboard → New → Blueprint → point at this repo. Render reads `render.yaml`
and creates a Docker web service named `volterra-api` with health check
`/v1/health`. Or: New → Web Service → repo → Runtime "Docker" →
Dockerfile path `services/api/Dockerfile`, Docker context `.`.

After the API is live, update the frontend env var and redeploy:

```bash
cd apps/web
vercel env rm NEXT_PUBLIC_API_BASE production -y
printf 'https://<your-api-host>' | vercel env add NEXT_PUBLIC_API_BASE production
vercel deploy --prod
```

Verify: `curl https://<your-api-host>/v1/health` returns
`{"status":"ok", ...}` and `https://volterra-web.vercel.app` renders the demo
3-D surface.

## Worker (services/worker)

Demo mode by default (`DEMO_MODE=true`); not required for the deployed demo.
Deploy it later as a second service once a live provider is configured.
