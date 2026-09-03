import { useEffect, useRef } from "react";

const ZERO = "rgba(232,237,242,0.16)";

export type SparklineProps = {
  data: number[];
  color: string;
  height: number;
};

function finiteData(data: number[]): number[] {
  return data.filter((v) => Number.isFinite(v));
}

function paint(
  canvas: HTMLCanvasElement,
  data: number[],
  color: string,
  cssH: number,
): void {
  const parent = canvas.parentElement;
  const cssW = Math.max(1, parent?.clientWidth ?? canvas.clientWidth ?? 1);
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  canvas.width = Math.max(1, Math.floor(cssW * dpr));
  canvas.height = Math.max(1, Math.floor(cssH * dpr));
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const pad = 2;
  const w = cssW - pad * 2;
  const h = cssH - pad * 2;
  const series = finiteData(data);

  if (h <= 0 || w <= 0) return;

  const min = series.length ? Math.min(0, ...series) : -1;
  const max = series.length ? Math.max(0, ...series) : 1;
  const span = max - min || 1;
  const yOf = (v: number) => pad + (1 - (v - min) / span) * h;

  ctx.beginPath();
  ctx.strokeStyle = ZERO;
  ctx.lineWidth = 1;
  const y0 = yOf(0);
  ctx.moveTo(pad, y0);
  ctx.lineTo(pad + w, y0);
  ctx.stroke();

  if (series.length === 0) return;

  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.25;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  if (series.length === 1) {
    const x = pad + w / 2;
    const y = yOf(series[0]!);
    ctx.arc(x, y, 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    return;
  }
  const step = w / (series.length - 1);
  series.forEach((v, i) => {
    const x = pad + i * step;
    const y = yOf(v);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

export function Sparkline({ data, color, height }: SparklineProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const h = Number.isFinite(height) && height > 0 ? height : 48;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const draw = () => paint(canvas, data, color, h);
    draw();
    const parent = canvas.parentElement;
    if (!parent || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(draw);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [data, color, h]);

  return (
    <canvas
      ref={ref}
      height={h}
      aria-hidden="true"
      style={{
        display: "block",
        width: "100%",
        height: h,
        background: "transparent",
      }}
    />
  );
}
