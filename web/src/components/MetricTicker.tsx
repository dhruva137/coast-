import { useEffect, useRef, useState } from "react";
import { fmtM, fmtPct } from "../lib/format.ts";

export type NavMode = "gnss" | "ins" | "graph" | "coast" | string;

export type MetricTickerProps = {
  loop_closure_m: number;
  drift_pct: number;
  distance_m: number;
  /** Fraction in [0, 1], same as core `IMetrics.branch_accuracy`. */
  branch_accuracy: number;
  mode: NavMode;
};

function Cell({ label, value, tickKey }: { label: string; value: string; tickKey: string }) {
  const [flash, setFlash] = useState(false);
  const prev = useRef(value);

  useEffect(() => {
    if (prev.current === value) return;
    prev.current = value;
    setFlash(true);
    const t = window.setTimeout(() => setFlash(false), 450);
    return () => window.clearTimeout(t);
  }, [value, tickKey]);

  return (
    <div className="metric-cell">
      <div className="metric-cell-l">{label}</div>
      <div className={`metric-cell-v ${flash ? "metric-tick" : ""}`}>{value}</div>
    </div>
  );
}

function modeColor(mode: string): string {
  const m = mode.toLowerCase();
  if (m === "gnss") return "var(--teal)";
  if (m === "graph") return "var(--saffron)";
  return "var(--text)";
}

export function MetricTicker({
  loop_closure_m,
  drift_pct,
  distance_m,
  branch_accuracy,
  mode,
}: MetricTickerProps) {
  const accPct = Number.isFinite(branch_accuracy) ? branch_accuracy * 100 : Number.NaN;
  const modeLabel = typeof mode === "string" && mode.length > 0 ? mode.toUpperCase() : "—";
  const [modeFlash, setModeFlash] = useState(false);
  const prevMode = useRef(modeLabel);

  useEffect(() => {
    if (prevMode.current === modeLabel) return;
    prevMode.current = modeLabel;
    setModeFlash(true);
    const t = window.setTimeout(() => setModeFlash(false), 450);
    return () => window.clearTimeout(t);
  }, [modeLabel]);

  return (
    <div className="metric-ticker">
      <Cell label="LOOP CLOSURE" value={fmtM(loop_closure_m, 1)} tickKey="loop" />
      <Cell label="DRIFT" value={fmtPct(drift_pct, 2)} tickKey="drift" />
      <Cell label="DISTANCE" value={fmtM(distance_m, 0)} tickKey="dist" />
      <Cell label="BRANCH ACC" value={fmtPct(accPct, 0)} tickKey="branch" />
      <div className="metric-cell metric-cell-wide">
        <div className="metric-cell-l">MODE</div>
        <div
          className={`metric-cell-v ${modeFlash ? "metric-tick" : ""}`}
          style={{ color: modeColor(modeLabel), letterSpacing: "0.12em" }}
        >
          {modeLabel}
        </div>
      </div>
    </div>
  );
}
