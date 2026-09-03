import { fmtDeg } from "../lib/format.ts";

const VISUAL_CAP = 60;
const TICKS = [-45, -30, -15, 0, 15, 30, 45] as const;

export type LeanGaugeProps = {
  /** Lean estimate φ, radians. Positive = right (body-x roll). */
  phiRad: number;
};

function radToDeg(rad: number): number {
  if (!Number.isFinite(rad)) return 0;
  return (rad * 180) / Math.PI;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function leanRot(deg: number): number {
  return clamp(deg, -VISUAL_CAP, VISUAL_CAP);
}

export function LeanGauge({ phiRad }: LeanGaugeProps) {
  const deg = radToDeg(phiRad);
  const rot = leanRot(deg);
  const cx = 100;
  const cy = 118;
  const r = 78;

  const polar = (angleDeg: number, radius: number) => {
    const a = ((-90 + angleDeg) * Math.PI) / 180;
    return { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
  };

  const tip = polar(0, r - 8);

  return (
    <div
      className="lean-gauge"
      role="meter"
      aria-label="Lean phi"
      aria-valuemin={-45}
      aria-valuemax={45}
      aria-valuenow={Math.round(deg)}
    >
      <div className="lean-gauge-h">LEAN φ</div>
      <svg viewBox="0 0 200 148" width="100%" height="132" aria-hidden="true" className="lean-gauge-svg">
        <path
          d={`M ${polar(-VISUAL_CAP, r).x} ${polar(-VISUAL_CAP, r).y} A ${r} ${r} 0 0 0 ${polar(VISUAL_CAP, r).x} ${polar(VISUAL_CAP, r).y}`}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={1.25}
        />
        {TICKS.map((t) => {
          const outer = polar(t, r);
          const major = t === 0 || Math.abs(t) === 45;
          const inner = polar(t, r - (major ? 11 : 7));
          const label = polar(t, r - 22);
          return (
            <g key={t}>
              <line
                x1={inner.x}
                y1={inner.y}
                x2={outer.x}
                y2={outer.y}
                stroke={major ? "var(--text)" : "var(--mute)"}
                strokeWidth={major ? 1.4 : 1}
              />
              {major ? (
                <text
                  x={label.x}
                  y={label.y}
                  fill="var(--mute)"
                  fontFamily="var(--font-mono)"
                  fontSize={8}
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {t > 0 ? `+${t}` : `${t}`}
                </text>
              ) : null}
            </g>
          );
        })}
        <g
          style={{
            transformOrigin: `${cx}px ${cy}px`,
            transform: `rotate(${rot}deg)`,
            transition: "transform 0.12s linear",
          }}
        >
          <line
            x1={cx}
            y1={cy}
            x2={tip.x}
            y2={tip.y}
            stroke="var(--saffron)"
            strokeWidth={1.75}
            strokeLinecap="round"
          />
          <circle cx={tip.x} cy={tip.y} r={2.2} fill="var(--saffron)" />
          <g transform={`translate(${cx} ${cy})`}>
            <ellipse cx="0" cy="4" rx="9" ry="5.5" fill="none" stroke="var(--text)" strokeWidth={1.15} />
            <path
              d="M 0 -28 L 5 -10 L 16 -6 L 17 2 L 6 6 L 4 12 L -4 12 L -6 6 L -17 2 L -16 -6 L -5 -10 Z"
              fill="none"
              stroke="var(--text)"
              strokeWidth={1.1}
            />
            <line x1="-18" y1="-4" x2="18" y2="-4" stroke="var(--text)" strokeWidth={1.1} />
            <circle cx="0" cy="-16" r="3.2" fill="none" stroke="var(--text)" strokeWidth={1.05} />
          </g>
        </g>
        <circle cx={cx} cy={cy} r={2.4} fill="var(--saffron)" />
      </svg>
      <div className="lean-gauge-val metric-tick-host">{fmtDeg(deg, 1)}</div>
    </div>
  );
}
