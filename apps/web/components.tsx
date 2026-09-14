"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js";
import { useState } from "react";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type SurfaceProps = { x: number[]; y: number[]; z: number[][]; title?: string };

export function SurfacePlot({ x, y, z, title = "Implied volatility" }: SurfaceProps) {
  const data: Data[] = [{ type: "surface", x, y, z, colorscale: "Viridis",
    hovertemplate: "k=%{x:.3f}<br>T=%{y:.3f}<br>IV=%{z:.2%}<extra></extra>",
    colorbar: { title: { text: "IV" } } }];
  const layout: Partial<Layout> = { title, autosize: true, margin: { l: 0, r: 0, t: 42, b: 0 },
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    scene: { xaxis: { title: "Log-forward moneyness" }, yaxis: { title: "Maturity" },
      zaxis: { title: "Implied volatility" }, aspectmode: "auto" } };
  return <div className="h-[360px] w-full sm:h-[560px]"><Plot data={data} layout={layout}
    useResizeHandler className="h-full w-full" config={{ responsive: true, displaylogo: false }} /></div>;
}

export function LineChart({ x, y, title, xTitle, yTitle }: { x: number[]; y: number[]; title: string; xTitle: string; yTitle: string }) {
  return <Plot data={[{ type: "scatter", mode: "lines+markers", x, y, line: { color: "#38bdf8" } }]}
    layout={{ title, margin: { l: 48, r: 12, t: 42, b: 42 }, xaxis: { title: xTitle }, yaxis: { title: yTitle }, autosize: true }} useResizeHandler className="h-64 w-full" config={{ responsive: true }} />;
}

export function ControlRail({ onChange }: { onChange?: (value: string) => void }) {
  const [underlying, setUnderlying] = useState("BTC");
  return <aside className="space-y-4 rounded-xl border p-4">
    <label className="block text-sm">Underlying<select className="mt-1 w-full rounded border p-2" value={underlying} onChange={e => { setUnderlying(e.target.value); onChange?.(e.target.value); }}><option>BTC</option><option>ETH</option></select></label>
    <label className="block text-sm">Snapshot<select className="mt-1 w-full rounded border p-2"><option>Latest</option><option>Demo</option></select></label>
    <label className="block text-sm">View<select className="mt-1 w-full rounded border p-2"><option>IV surface</option><option>Total variance</option></select></label>
  </aside>;
}

export function DiagnosticsPanel({ diagnostics }: { diagnostics: Record<string, unknown> }) {
  return <section className="rounded-xl border p-4"><h2 className="mb-3 text-lg font-semibold">Diagnostics</h2><dl className="grid grid-cols-2 gap-3 text-sm">{Object.entries(diagnostics).map(([key, value]) => <div key={key}><dt className="text-slate-500">{key}</dt><dd>{String(value)}</dd></div>)}</dl></section>;
}

export function Mobile2DFallback({ x, z }: SurfaceProps) {
  const row = z[Math.floor(z.length / 2)] ?? [];
  return <div className="block sm:hidden"><LineChart x={x} y={row} title="2D skew (mobile view)" xTitle="Log-moneyness" yTitle="IV" /></div>;
}
