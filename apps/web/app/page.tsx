"use client";

import { useEffect, useState } from "react";
import { ControlRail, DiagnosticsPanel, LineChart, Mobile2DFallback, SurfacePlot } from "../components";

type SurfaceResponse = {
  underlying: string;
  snapshot: string;
  moneyness: number[];
  maturities: number[];
  iv: number[][];
  diagnostics: Record<string, unknown>;
  provenance?: Record<string, unknown>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Static demo payloads bundled with the app so the deployed site still
// renders the surface when no live API is configured.
async function fetchSurface(underlying: string): Promise<SurfaceResponse> {
  try {
    const r = await fetch(`${API_BASE}/v1/surfaces/${underlying}`);
    if (!r.ok) throw new Error(`API ${r.status}`);
    return (await r.json()) as SurfaceResponse;
  } catch (e) {
    const r = await fetch(`/demo-surface-${underlying}.json`);
    if (!r.ok) throw e;
    const data = (await r.json()) as SurfaceResponse;
    return { ...data, provenance: { ...(data.provenance ?? {}), bundled: true } };
  }
}

export default function Home() {
  const [underlying, setUnderlying] = useState("BTC");
  const [surface, setSurface] = useState<SurfaceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSurface(null);
    setError(null);
    fetchSurface(underlying).then(setSurface).catch((e) => setError(String(e)));
  }, [underlying]);

  const mid = surface ? Math.floor(surface.maturities.length / 2) : 0;
  const atmIdx = surface
    ? surface.moneyness.reduce((best, k, i) => (Math.abs(k) < Math.abs(surface.moneyness[best]) ? i : best), 0)
    : 0;
  const termStructure = surface?.iv.map((row) => row[atmIdx]) ?? [];

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">Volterra</h1>
        <p className="text-sm text-slate-400">
          {surface?.provenance?.bundled
            ? "source: synthetic-demo (bundled — no live API)"
            : surface?.provenance?.source
              ? `source: ${String(surface.provenance.source)}`
              : "Neural Volatility Surface Lab"}
        </p>
      </header>

      <div className="grid gap-6 sm:grid-cols-[240px_1fr]">
        <ControlRail onChange={setUnderlying} />
        <div className="space-y-6">
          {error && <p className="rounded border border-red-500/50 p-3 text-sm text-red-300">API error: {error}</p>}
          {!surface && !error && <p className="text-sm text-slate-400">Loading surface…</p>}
          {surface && (
            <>
              <div className="hidden sm:block">
                <SurfacePlot x={surface.moneyness} y={surface.maturities} z={surface.iv} title={`${underlying} IV surface`} />
              </div>
              <Mobile2DFallback x={surface.moneyness} y={surface.maturities} z={surface.iv} />
              <div className="grid gap-6 sm:grid-cols-2">
                <LineChart
                  x={surface.moneyness}
                  y={surface.iv[mid] ?? []}
                  title={`Skew @ T=${(surface.maturities[mid] * 365).toFixed(0)}d`}
                  xTitle="Log-forward moneyness"
                  yTitle="IV"
                />
                <LineChart
                  x={surface.maturities}
                  y={termStructure}
                  title="ATM term structure"
                  xTitle="Maturity (y)"
                  yTitle="IV"
                />
              </div>
              <DiagnosticsPanel diagnostics={surface.diagnostics} />
            </>
          )}
        </div>
      </div>
    </main>
  );
}
