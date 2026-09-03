import { fmtPct } from "../lib/format.ts";

const SAFFRON = "#ff6b2d";
const OURS = "#4da3ff";
const TEXT = "#e8edf2";
const MUTE = "#8b98a5";
const LINE = "rgba(255,255,255,0.08)";
const TRACK = "rgba(255,255,255,0.06)";
const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const SANS = '"IBM Plex Sans", system-ui, sans-serif';

export type BranchBarsProps = {
  /** Edge-id → posterior mass. Values in [0, 1]. */
  posteriors: Record<string, number>;
};

function mass(n: number): number {
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function labelEdge(id: string): string {
  return id.replace(/_/g, " ");
}

export function BranchBars({ posteriors }: BranchBarsProps) {
  const rows = Object.entries(posteriors)
    .map(([id, w]) => ({ id, w: mass(w) }))
    .sort((a, b) => b.w - a.w || a.id.localeCompare(b.id));
  const winner = rows[0];
  const peak = winner && winner.w > 0 ? winner.w : 1;

  return (
    <div
      style={{
        background: "transparent",
        border: `1px solid ${LINE}`,
        padding: "10px 12px 8px",
        color: TEXT,
      }}
    >
      <div
        style={{
          fontFamily: SANS,
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: MUTE,
          marginBottom: 10,
        }}
      >
        WHICH RAMP
      </div>
      {rows.length === 0 ? (
        <div style={{ fontFamily: MONO, fontSize: 12, color: MUTE }}>NO FORK</div>
      ) : (
        rows.map((row) => {
          const win = winner !== undefined && row.id === winner.id && row.w > 0;
          const width = `${(100 * row.w) / peak}%`;
          return (
            <div key={row.id} style={{ marginBottom: 8 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 8,
                  marginBottom: 3,
                  fontSize: 11,
                }}
              >
                <span
                  style={{
                    fontFamily: SANS,
                    color: win ? SAFFRON : TEXT,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  {labelEdge(row.id)}
                </span>
                <span style={{ fontFamily: MONO, color: win ? SAFFRON : MUTE }}>
                  {fmtPct(row.w * 100, 1)}
                </span>
              </div>
              <div style={{ height: 6, background: TRACK, border: `1px solid ${LINE}` }}>
                <div
                  style={{
                    height: "100%",
                    width,
                    background: win ? SAFFRON : OURS,
                    transition: "width 0.28s cubic-bezier(0.22, 1, 0.36, 1)",
                  }}
                />
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
