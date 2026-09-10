import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import type { TrainEpoch } from "../lib/trainApi";

export type LossChartHandle = {
  toPng: () => string | null;
};

type LossChartProps = {
  epochs: TrainEpoch[];
  holdBaselineRmse?: number | null;
  height?: number;
};

function objectiveOf(e: TrainEpoch): string {
  return (e.objective || e.mode || "").toUpperCase();
}

function heldRmseOf(e: TrainEpoch): number | undefined {
  const v = e.held_rmse ?? e.rmse;
  return v != null && Number.isFinite(v) ? v : undefined;
}

function paintPanel(
  ctx: CanvasRenderingContext2D,
  box: { x: number; y: number; w: number; h: number },
  title: string,
  yLabel: string,
  series: { vals: (number | undefined)[]; color: string; label: string; connect?: boolean }[],
  flatRefs: { value: number; color: string; label: string }[],
  markers: { index: number; label: string }[],
  nEpochs: number,
): void {
  const { x: left, y: top, w, h } = box;
  if (w < 8 || h < 8) return;

  const pad = { l: 44, r: 10, t: 18, b: 16 };
  const pw = w - pad.l - pad.r;
  const ph = h - pad.t - pad.b;
  if (pw < 8 || ph < 8) return;

  const finite: number[] = [];
  for (const s of series) {
    for (const v of s.vals) if (v != null && Number.isFinite(v)) finite.push(v);
  }
  for (const r of flatRefs) if (Number.isFinite(r.value)) finite.push(r.value);
  const maxY = Math.max(0.05, ...(finite.length ? finite : [1]));
  const n = Math.max(1, nEpochs);
  const xOf = (i: number) => left + pad.l + (n <= 1 ? pw / 2 : (i / (n - 1)) * pw);
  const yOf = (v: number) => top + pad.t + (1 - v / maxY) * ph;

  ctx.strokeStyle = "rgba(220,228,236,0.10)";
  ctx.fillStyle = "#8492a0";
  ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
  ctx.lineWidth = 1;
  for (let g = 0; g <= 3; g++) {
    const yy = top + pad.t + (g / 3) * ph;
    ctx.beginPath();
    ctx.moveTo(left + pad.l, yy);
    ctx.lineTo(left + pad.l + pw, yy);
    ctx.stroke();
    ctx.fillText(((1 - g / 3) * maxY).toFixed(2), left + 2, yy + 3);
  }

  ctx.fillStyle = "#e6edf3";
  ctx.font = "11px 'IBM Plex Sans', sans-serif";
  ctx.fillText(title, left + pad.l, top + 12);
  ctx.fillStyle = "#8492a0";
  ctx.font = "9px 'IBM Plex Mono', ui-monospace, monospace";
  ctx.fillText(yLabel, left + 2, top + pad.t - 2);

  for (const r of flatRefs) {
    if (!Number.isFinite(r.value)) continue;
    const yy = yOf(r.value);
    ctx.beginPath();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = r.color;
    ctx.lineWidth = 1.2;
    ctx.moveTo(left + pad.l, yy);
    ctx.lineTo(left + pad.l + pw, yy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = r.color;
    ctx.font = "9px 'IBM Plex Mono', ui-monospace, monospace";
    ctx.fillText(`${r.label} ${r.value.toFixed(2)}`, left + pad.l + 4, yy - 3);
  }

  for (const m of markers) {
    if (m.index < 0 || m.index >= n) continue;
    const xx = xOf(m.index);
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = "rgba(255,179,0,0.85)";
    ctx.lineWidth = 1.2;
    ctx.moveTo(xx, top + pad.t);
    ctx.lineTo(xx, top + pad.t + ph);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ffb300";
    ctx.font = "9px 'IBM Plex Sans', sans-serif";
    ctx.fillText(m.label, xx + 3, top + pad.t + 10);
  }

  for (const s of series) {
    const pts = s.vals
      .map((v, i) => (v != null && Number.isFinite(v) ? { i, v } : null))
      .filter((p): p is { i: number; v: number } => p != null);
    if (!pts.length) continue;
    ctx.strokeStyle = s.color;
    ctx.fillStyle = s.color;
    ctx.lineWidth = 1.6;
    ctx.lineJoin = "round";
    if (s.connect !== false) {
      ctx.beginPath();
      pts.forEach((p, k) => {
        const xx = xOf(p.i);
        const yy = yOf(p.v);
        if (k === 0) ctx.moveTo(xx, yy);
        else ctx.lineTo(xx, yy);
      });
      ctx.stroke();
    }
    pts.forEach((p) => {
      ctx.beginPath();
      ctx.arc(xOf(p.i), yOf(p.v), 2.4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  let legendX = left + pad.l;
  const legendY = top + h - 4;
  ctx.font = "9px 'IBM Plex Mono', ui-monospace, monospace";
  for (const s of series) {
    if (!s.vals.some((v) => v != null && Number.isFinite(v))) continue;
    ctx.fillStyle = s.color;
    ctx.fillText(s.label, legendX, legendY);
    legendX += ctx.measureText(s.label).width + 12;
  }
}

function paint(canvas: HTMLCanvasElement, epochs: TrainEpoch[], holdBaseline: number | null | undefined, cssH: number): void {
  const parent = canvas.parentElement;
  const cssW = Math.max(1, parent?.clientWidth ?? canvas.clientWidth ?? 1);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(cssW * dpr));
  canvas.height = Math.max(1, Math.floor(cssH * dpr));
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  if (!epochs.length) {
    ctx.fillStyle = "#5c6b7a";
    ctx.font = "12px 'IBM Plex Sans', sans-serif";
    ctx.fillText("Waiting for epoch 1… (no invented curve)", 16, cssH / 2);
    return;
  }

  const n = epochs.length;
  const held = epochs.map(heldRmseOf);
  const baseline =
    holdBaseline != null && Number.isFinite(holdBaseline)
      ? holdBaseline
      : epochs.map((e) => e.hold_baseline_rmse).find((v) => v != null && Number.isFinite(v));

  const switchIdx = epochs.findIndex((e, i) => {
    if (i === 0) return false;
    const prev = objectiveOf(epochs[i - 1]!);
    const cur = objectiveOf(e);
    return prev === "MSE" && cur === "NLL";
  });
  const markers = switchIdx >= 0 ? [{ index: switchIdx, label: "MSE → NLL" }] : [];

  const mseRaw = epochs.map((e) => (objectiveOf(e) === "MSE" ? e.loss : undefined));
  const nllRaw = epochs.map((e) => (objectiveOf(e) === "NLL" ? e.loss : undefined));
  const mse0 = mseRaw.find((v) => v != null && Number.isFinite(v));
  const nll0 = nllRaw.find((v) => v != null && Number.isFinite(v));
  // Per-phase normalisation so MSE and NLL never share raw units on one axis.
  const mseLoss = mseRaw.map((v) =>
    v != null && mse0 != null && mse0 > 0 ? v / mse0 : undefined,
  );
  const nllLoss = nllRaw.map((v) =>
    v != null && nll0 != null && Math.abs(nll0) > 1e-12 ? v / nll0 : undefined,
  );
  const clErr = epochs.map((e) =>
    e.cl_end_err_m != null && Number.isFinite(e.cl_end_err_m) ? e.cl_end_err_m : undefined,
  );
  const hasCl = clErr.some((v) => v != null);

  const gap = 8;
  const bands = hasCl ? 3 : 2;
  const bandH = (cssH - gap * (bands - 1)) / bands;

  paintPanel(
    ctx,
    { x: 0, y: 0, w: cssW, h: bandH },
    "Held-out RMSE (headline) — is the task improving?",
    "m/s",
    [{ vals: held, color: "#00d4aa", label: "held RMSE" }],
    baseline != null
      ? [{ value: baseline, color: "#8A929B", label: "hold-last-speed" }]
      : [],
    markers,
    n,
  );

  let y = bandH + gap;
  if (hasCl) {
    paintPanel(
      ctx,
      { x: 0, y, w: cssW, h: bandH },
      "Closed-loop endpoint error (path vs CAN truth)",
      "m",
      [{ vals: clErr, color: "#4FC3F7", label: "cl_end_err_m" }],
      [],
      markers,
      n,
    );
    y += bandH + gap;
  }

  paintPanel(
    ctx,
    { x: 0, y, w: cssW, h: bandH },
    "Train loss (secondary) — each phase ÷ its own start (not raw MSE+NLL)",
    "rel",
    [
      { vals: mseLoss, color: "#ff6b2d", label: "MSE / start", connect: true },
      { vals: nllLoss, color: "#c77dff", label: "NLL / start", connect: true },
    ],
    [],
    markers,
    n,
  );
}

export const LossChart = forwardRef<LossChartHandle, LossChartProps>(function LossChart(
  { epochs, holdBaselineRmse = null, height = 280 },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useImperativeHandle(ref, () => ({
    toPng: () => canvasRef.current?.toDataURL("image/png") ?? null,
  }));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const draw = () => paint(canvas, epochs, holdBaselineRmse, height);
    draw();
    const parent = canvas.parentElement;
    if (!parent || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(draw);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [epochs, holdBaselineRmse, height]);

  return (
    <canvas
      ref={canvasRef}
      height={height}
      aria-label="Held-out RMSE headline and phase-separated train loss"
      style={{ display: "block", width: "100%", height, background: "transparent" }}
    />
  );
});
