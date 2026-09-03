const SAFFRON = "#ff6b2d";
const TEXT = "#e8edf2";
const MUTE = "#8b98a5";
const LINE = "rgba(255,255,255,0.08)";
const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const SANS = '"IBM Plex Sans", system-ui, sans-serif';

export type DemoAct = 1 | 2 | 3 | 4 | 5;

export type ActNarrationProps = {
  act: DemoAct;
  playing: boolean;
};

export type ActBeat = {
  act: DemoAct;
  title: string;
  clock: string;
  line: string;
};

/** Jury script from bible §8. Spoken claims only; no unpublished results. */
export const ACT_SCRIPT: readonly ActBeat[] = [
  {
    act: 1,
    title: "THE HANDOFF",
    clock: "60 s",
    line: "Judge holds the phone. Walk from GNSS lock into the basement. GPS dies. The dot keeps moving. Return to the marked X — loop-closure error over distance travelled is the score.",
  },
  {
    act: 2,
    title: "THE VEHICLE",
    clock: "90 s",
    line: "Same bicycle ride, two traces: car-style AI-IMU baseline vs lean-aware IDR. Baseline diverges at every turn. Textbook cos(φ) — we apply it; we do not claim discovery.",
  },
  {
    act: 3,
    title: "THE BENCHMARK",
    clock: "60 s",
    line: "Replay an underpass with GNSS at both ends: entered here, predicted exit here, GPS says here. Score it live against ISRO — <10% drift, <100 m per km.",
  },
  {
    act: 4,
    title: "THE METRIC",
    clock: "60 s",
    line: "Every team quotes drift %. A driver feels one thing: did we take the right ramp? Report branch-decision accuracy. Tight forks (±8°) are where it degrades.",
  },
  {
    act: 5,
    title: "THE ASK",
    clock: "30 s",
    line: "Two hundred million two-wheelers. Any phone. Zero extra hardware. Ships as an SDK to ride-hailing, delivery fleets, and ambulance services.",
  },
];

function beatFor(act: DemoAct): ActBeat {
  return ACT_SCRIPT[act - 1] ?? ACT_SCRIPT[0]!;
}

export function ActNarration({ act, playing }: ActNarrationProps) {
  const beat = beatFor(act);
  const accent = playing ? SAFFRON : LINE;

  return (
    <div
      style={{
        background: "transparent",
        border: `1px solid ${accent}`,
        boxShadow: playing ? `inset 2px 0 0 ${SAFFRON}` : "none",
        padding: "10px 12px 12px",
        color: TEXT,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 8,
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
          }}
        >
          ACT {beat.act} · {beat.title}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: MONO, fontSize: 11, color: MUTE }}>{beat.clock}</span>
          <span
            style={{
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: "0.14em",
              color: playing ? SAFFRON : MUTE,
            }}
          >
            {playing ? "LIVE" : "HOLD"}
          </span>
        </div>
      </div>
      <p
        style={{
          margin: 0,
          fontFamily: SANS,
          fontSize: 13,
          lineHeight: 1.45,
          color: playing ? TEXT : "#c9d3dc",
        }}
      >
        {beat.line}
      </p>
    </div>
  );
}
