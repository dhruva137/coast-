import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import type { TrainEpoch } from "../lib/trainApi";

export type LossChartHandle = {
  toPng: () => string | null;
};

type LossChartProps = {
  epochs: TrainEpoch[];
  height?: number;
};

function paint(canvas: HTMLCanvasElement, epochs: TrainEpoch[], cssH: number): void {
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

  const pad = { l: 44, r: 12, t: 22, b: 28 };
  const w = cssW - pad.l - pad.r;
  const h = cssH - pad.t - pad.b;
  if (w < 8 || h < 8) return;

  const loss = epochs.map((e) => e.loss).filter((v) => Number.isFinite(v));
  const rmse = epochs.map((e) => e.rmse).filter((v): v is number => v != null && Number.isFinite(v));
  const maxY = Math.max(0.05, ...(loss.length ? loss : [1]), ...(rmse.length ? rmse : [0]));
  const n = Math.max(1, epochs.length);
  const xOf = (i: number) => pad.l + (n <= 1 ? w / 2 : (i / (n - 1)) * w);
  const yOf = (v: number) => pad.t + (1 - v / maxY) * h;

  ctx.strokeStyle = "rgba(220,228,236,0.12)";
  ctx.fillStyle = "#8492a0";
  ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
  ctx.lineWidth = 1;
  for (let g = 0; g <= 4; g++) {
    const y = pad.t + (g / 4) * h;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(pad.l + w, y);
    ctx.stroke();
    const label = ((1 - g / 4) * maxY).toFixed(2);
    ctx.fillText(label, 4, y + 3);
  }

  ctx.fillStyle = "#e6edf3";
  ctx.font = "11px 'IBM Plex Sans', sans-serif";
  ctx.fillText("Train loss / hold RMSE vs epoch (live stdout)", pad.l, 14);
  ctx.fillStyle = "#8492a0";
  ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
  ctx.fillText("epoch", pad.l + w / 2 - 16, cssH - 8);

  const drawSeries = (vals: (number | undefined)[], color: string) => {
    const pts = vals
      .map((v, i) => (v != null && Number.isFinite(v) ? { i, v } : null))
      .filter((p): p is { i: number; v: number } => p != null);
    if (!pts.length) return;
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.lineJoin = "round";
    pts.forEach((p, k) => {
      const x = xOf(p.i);
      const y = yOf(p.v);
      if (k === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = color;
    pts.forEach((p) => {
      ctx.beginPath();
      ctx.arc(xOf(p.i), yOf(p.v), 2.4, 0, Math.PI * 2);
      ctx.fill();
    });
  };

  drawSeries(epochs.map((e) => e.loss), "#ff6b2d");
  drawSeries(epochs.map((e) => e.rmse), "#00d4aa");

  ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
  ctx.fillStyle = "#ff6b2d";
  ctx.fillText("loss", pad.l, cssH - 8);
  ctx.fillStyle = "#00d4aa";
  ctx.fillText("hold RMSE m/s", pad.l + 44, cssH - 8);

  if (!epochs.length) {
    ctx.fillStyle = "#5c6b7a";
    ctx.fillText("Waiting for epoch 1…", pad.l + 8, pad.t + h / 2);
  }
}

export const LossChart = forwardRef<LossChartHandle, LossChartProps>(function LossChart(
  { epochs, height = 176 },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useImperativeHandle(ref, () => ({
    toPng: () => canvasRef.current?.toDataURL("image/png") ?? null,
  }));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const draw = () => paint(canvas, epochs, height);
    draw();
    const parent = canvas.parentElement;
    if (!parent || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(draw);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [epochs, height]);

  return (
    <canvas
      ref={canvasRef}
      height={height}
      aria-label="Live training loss and hold RMSE"
      style={{ display: "block", width: "100%", height, background: "transparent" }}
    />
  );
});
