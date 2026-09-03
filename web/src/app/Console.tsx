import { useEffect, useMemo, useState } from "react";
import { MapView } from "../components/MapView";
import { LeanGauge } from "../components/LeanGauge";
import { ErrorBudget } from "../components/ErrorBudget";
import { BranchBars } from "../components/BranchBars";
import { MetricTicker } from "../components/MetricTicker";
import { ActNarration } from "../components/ActNarration";
import { Sparkline } from "../components/Sparkline";
import { ACT_COPY, buildDemo, type ActId, type DemoBundle } from "../lib/runDemo";

export type ConsoleProps = {
  onBack: () => void;
  onNavigate?: (view: "evidence" | "operations") => void;
  /** When set, auto-run this act once on mount (e.g. live demo CTA). */
  autoAct?: ActId;
};

export function Console({ onBack, onNavigate, autoAct }: ConsoleProps) {
  const [act, setAct] = useState<ActId>(autoAct ?? 1);
  const [demo, setDemo] = useState<DemoBundle | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"live" | "budget" | "claims">("live");

  const cur = demo?.ours[Math.min(idx, (demo?.ours.length ?? 1) - 1)];
  const gnss = cur?.gnss_aided ?? true;

  useEffect(() => {
    if (autoAct == null) return;
    run(autoAct);
  }, []);

  useEffect(() => {
    if (!playing || !demo) return;
    let raf = 0;
    let last = performance.now();
    const tick = (t: number) => {
      if (t - last > 32) {
        last = t;
        setIdx((i) => {
          if (i >= demo.ours.length - 1) {
            setPlaying(false);
            return demo.ours.length - 1;
          }
          return i + 1;
        });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, demo]);

  const leanSeries = useMemo(() => {
    if (!demo) return [] as number[];
    const end = Math.min(idx + 1, demo.ours.length);
    const start = Math.max(0, end - 120);
    return demo.ours.slice(start, end).map((s) => (s.lean * 180) / Math.PI);
  }, [demo, idx]);

  function selectAct(next: ActId) {
    setAct(next);
  }

  function run(next: ActId) {
    setBusy(true);
    setPlaying(false);
    setAct(next);
    setTimeout(() => {
      const bundle = buildDemo(next);
      setDemo(bundle);
      setIdx(0);
      setBusy(false);
      setPlaying(true);
    }, 40);
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="wordmark" type="button" onClick={onBack} title="Back to product">
          IDR<span>.</span>
        </button>
        <div className="meta">
          <div className="sub">Console · SIH 26168 · ISRO frame</div>
          <div className="tagline">Intelligent Dead Reckoning — two-wheeler GNSS outage</div>
        </div>
        <div className="pills">
          <span className={`pill ${demo ? (gnss ? "on" : "off") : ""}`}>
            {!demo ? "STANDBY" : gnss ? "GNSS LOCK" : "GNSS DENIED · INS"}
          </span>
          <span className="pill">{cur ? `${(cur.speed * 3.6).toFixed(0)} km/h` : "— km/h"}</span>
          <span className="pill">10 Hz class</span>
          <button className="pill btn-like" type="button" onClick={onBack}>
            Product
          </button>
          <button className="pill btn-like" type="button" onClick={() => onNavigate?.("evidence")}>
            Evidence
          </button>
          <button className="pill btn-like" type="button" onClick={() => onNavigate?.("operations")}>
            Operations
          </button>
        </div>
      </header>

      <aside className="rail">
        <h2>Acts</h2>
        {([1, 2, 3, 4, 5] as ActId[]).map((n) => (
          <button
            key={n}
            className={`act ${act === n ? "active" : ""}`}
            onClick={() => selectAct(n)}
            type="button"
          >
            <strong>
              Act {n} · {ACT_COPY[n].title}
            </strong>
            <em>{ACT_COPY[n].line}</em>
          </button>
        ))}
        <button
          className={`go ${busy ? "busy" : ""}`}
          disabled={busy}
          onClick={() => run(act)}
          type="button"
        >
          {busy ? "Estimating…" : demo ? "Re-run act" : "Run this act"}
        </button>
        <div style={{ marginTop: 10 }} key={`narr-${act}-${playing}`}>
          <ActNarration act={act} playing={playing} />
        </div>
        <p className="fine">
          Loop closure is the score — walk back to a marked X. No infrastructure. We under-claim
          on purpose until two-wheeler logs exist.
        </p>
      </aside>

      <div className="mapwrap">
        <MapView demo={demo} idx={idx} />
        {!demo && !busy && (
          <div className="map-idle">
            <div className="map-idle-inner">
              <span className="brand-mark">
                IDR<span className="dot">.</span>
              </span>
              <p>Full-bleed map is the product surface. Run an act to stream lean-aware vs car-style traces.</p>
              <div className="hint">SELECT ACT → RUN</div>
            </div>
          </div>
        )}
        {busy && (
          <div className="estimating-veil" role="status">
            <span>Estimating…</span>
          </div>
        )}
        <div className="hud-float">
          <div className={`chip ${!gnss && demo ? "hot" : ""}`}>
            φ {(cur ? (cur.lean * 180) / Math.PI : 0).toFixed(1)}°
          </div>
          <div className={`chip ${playing ? "live" : ""}`}>
            {cur?.mode?.toUpperCase() ?? "IDLE"}
          </div>
          <div className="chip">{cur?.edge_id ?? "no edge"}</div>
        </div>
      </div>

      <aside className="side">
        <div className="tabs">
          <button className={tab === "live" ? "on" : ""} onClick={() => setTab("live")} type="button">
            Live
          </button>
          <button
            className={tab === "budget" ? "on" : ""}
            onClick={() => setTab("budget")}
            type="button"
          >
            F8 budget
          </button>
          <button
            className={tab === "claims" ? "on" : ""}
            onClick={() => setTab("claims")}
            type="button"
          >
            Claims
          </button>
        </div>
        {tab === "live" && (
          <div className="side-stack">
            <LeanGauge phiRad={cur?.lean ?? 0} />
            <MetricTicker
              loop_closure_m={demo?.metricsOurs.loop_closure_m ?? Number.NaN}
              drift_pct={demo?.metricsOurs.drift_pct ?? Number.NaN}
              distance_m={demo?.metricsOurs.distance_m ?? Number.NaN}
              branch_accuracy={demo?.metricsOurs.branch_accuracy ?? Number.NaN}
              mode={cur?.mode ?? "coast"}
            />
            <div>
              <h2>Lean history</h2>
              <Sparkline data={leanSeries} color="#ff6b2d" height={44} />
            </div>
            <BranchBars posteriors={cur?.branch_posteriors ?? {}} />
            <div className="baseline-strip">
              <h2 style={{ marginBottom: 6 }}>Baseline · car-style</h2>
              Same IMU. ψ̇ = ω_z. Drift{" "}
              <strong>{demo ? `${demo.metricsBase.drift_pct.toFixed(2)}%` : "—"}</strong>
              {" · "}
              close <strong>{demo ? `${demo.metricsBase.loop_closure_m.toFixed(1)} m` : "—"}</strong>
            </div>
          </div>
        )}
        {tab === "budget" && <ErrorBudget />}
        {tab === "claims" && (
          <div className="claims-body">
            <p>
              <strong>Say only this.</strong> First smartphone DR that handles leaning
              two-wheelers. Fixed-point coordinated-turn solver with cos(Δφ) insensitivity.
              Branch-decision accuracy as the user metric.
            </p>
            <p className="dont">
              Do not claim: discovering roll/yaw kinematics (Titterton &amp; Weston),
              map-matching (Newson &amp; Krumm 2009), road signatures (arXiv 2303.03942),
              adaptive NHC (MTDNN 2025).
            </p>
            <p>
              Hard braking mid-turn is the real failure mode (0.4 g → 9.6% drift). Simulation
              until campus bicycle logs exist.
            </p>
          </div>
        )}
      </aside>

      <footer className="bottom">
        <div className="legend">
          <span>
            <i className="sw" style={{ background: "#4da3ff" }} /> IDR
          </span>
          <span>
            <i className="sw" style={{ background: "#ff4d6a" }} /> Baseline
          </span>
        </div>
        <div className="scrub">
          <input
            type="range"
            min={0}
            max={Math.max(1, (demo?.ours.length ?? 1) - 1)}
            value={idx}
            aria-label="Replay scrubber"
            onChange={(e) => {
              setPlaying(false);
              setIdx(Number(e.target.value));
            }}
          />
          <div className="mono" style={{ fontSize: 11, color: "var(--mute)" }}>
            {cur ? `${(cur.t_ns / 1e9).toFixed(1)} s` : "idle"} · scrubber · replay-first
          </div>
        </div>
        <div className="legend" style={{ justifyContent: "flex-end", paddingRight: 14, gap: 8 }}>
          <button
            className="pill btn-like"
            type="button"
            onClick={() => setPlaying((p) => !p)}
            disabled={!demo}
          >
            {playing ? "Pause" : "Play"}
          </button>
        </div>
      </footer>
    </div>
  );
}
