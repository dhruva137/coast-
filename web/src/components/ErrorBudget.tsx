import { fmtM, fmtPct } from "../lib/format.ts";

const SAFFRON = "#ff6b2d";
const TEXT = "#e8edf2";
const MUTE = "#8b98a5";
const LINE = "rgba(255,255,255,0.08)";
const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const SANS = '"IBM Plex Sans", system-ui, sans-serif';

/** F8 — simulation, IO-VNBD-derived noise. Not real two-wheeler data. */
const F8: readonly {
  source: string;
  detail: string;
  metres: number;
  drift: number;
}[] = [
  { source: "AVNet vel", detail: "0.5 m per s", metres: 15.0, drift: 1.13 },
  { source: "AVNet att", detail: "~10°", metres: 52.3, drift: 3.94 },
  { source: "cos(lean)", detail: "34°", metres: 84.9, drift: 6.4 },
  { source: "gyro bias", detail: "0.3°/s · 125 s", metres: 188.5, drift: 14.2 },
];

export function ErrorBudget() {
  return (
    <div
      style={{
        background: "transparent",
        border: `1px solid ${LINE}`,
        padding: "10px 12px 12px",
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
        ERROR BUDGET F8
      </div>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
        }}
      >
        <thead>
          <tr style={{ color: MUTE, fontFamily: SANS, letterSpacing: "0.08em" }}>
            <th style={{ textAlign: "left", fontWeight: 500, padding: "0 0 6px" }}>SOURCE</th>
            <th style={{ textAlign: "right", fontWeight: 500, padding: "0 0 6px" }}>POS</th>
            <th style={{ textAlign: "right", fontWeight: 500, padding: "0 0 6px" }}>DRIFT</th>
          </tr>
        </thead>
        <tbody>
          {F8.map((row, i) => {
            const last = i === F8.length - 1;
            return (
              <tr key={row.source} style={{ color: last ? SAFFRON : TEXT }}>
                <td style={{ padding: "5px 0", borderTop: `1px solid ${LINE}` }}>
                  <div style={{ fontFamily: SANS }}>{row.source}</div>
                  <div style={{ fontFamily: MONO, fontSize: 10, color: last ? SAFFRON : MUTE }}>
                    {row.detail}
                  </div>
                </td>
                <td
                  style={{
                    fontFamily: MONO,
                    textAlign: "right",
                    verticalAlign: "top",
                    padding: "5px 0",
                    borderTop: `1px solid ${LINE}`,
                    whiteSpace: "nowrap",
                  }}
                >
                  {fmtM(row.metres, 1)}
                </td>
                <td
                  style={{
                    fontFamily: MONO,
                    textAlign: "right",
                    verticalAlign: "top",
                    padding: "5px 0",
                    borderTop: `1px solid ${LINE}`,
                    whiteSpace: "nowrap",
                  }}
                >
                  {fmtPct(row.drift, 2)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div
        style={{
          marginTop: 10,
          fontFamily: SANS,
          fontSize: 11,
          lineHeight: 1.4,
          color: MUTE,
        }}
      >
        Heading is <span style={{ color: SAFFRON, fontFamily: MONO }}>far more</span>{" "}
        damaging than speed. Honest: simulation.
      </div>
    </div>
  );
}
