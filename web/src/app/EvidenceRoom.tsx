import { useEffect, useState } from "react";

type EvidenceClass = "REAL CAR" | "INJECTED LEAN";
type ProofSummary = {
  generated_utc: string;
  status: string;
  honesty_note: string;
  provenance: {
    protocol: string;
    data_class: string;
    independent_source_files: number;
    viable_sessions: number;
    completed_placements: number;
    manifest_path: string;
    axis_mapping: { vehicle_gz_yaw: string };
  };
  overall: {
    n: number;
    final_error_m: { p50: number; p95: number };
    coverage_95_endpoint: number;
    failure_rate_over_50m: number;
  };
  counterfactual: {
    status: string;
    data_class: string;
    injected_lean: {
      car_style: { final_error_m: number };
      lean_aware: { final_error_m: number };
    };
  };
  plots: string[];
};

const PROOF_SOURCE = "/evidence/proof_summary.json";

function EvidenceBadge({ kind }: { kind: EvidenceClass }) {
  return <span className={`evidence-badge ${kind.toLowerCase().replace(" ", "-")}`}>{kind}</span>;
}

export function EvidenceRoom({ navigate }: { navigate: (view: "landing" | "console" | "evidence" | "operations") => void }) {
  const [proof, setProof] = useState<ProofSummary | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(PROOF_SOURCE, { cache: "no-store" });
        if (!response.ok) throw new Error(`Proof artifact returned ${response.status}`);
        const next = (await response.json()) as ProofSummary;
        if (!next.status || !next.overall || !next.provenance || !next.counterfactual) {
          throw new Error("Proof artifact schema is incomplete");
        }
        if (active) setProof(next);
      } catch {
        if (active) setLoadFailed(true);
      }
    }
    load();
    return () => { active = false; };
  }, []);

  const isRed = proof?.status.includes("NOT_DEPLOYMENT_READY") ?? false;
  const overall = proof?.overall;
  const counterfactual = proof?.counterfactual.injected_lean;
  const percent = (value: number | undefined) => value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;

  return (
    <main className="enterprise-page">
      <EnterpriseNav active="evidence" navigate={navigate} />
      <header className="enterprise-head">
        <div>
          <p className="section-eyebrow">Independent evaluation surface</p>
          <h1>Evidence Room</h1>
          <p>Trace every claim to its data class, challenge state, and failure envelope.</p>
        </div>
        <div className={`artifact-state ${isRed ? "validation-red" : loadFailed ? "demo" : "verified"}`}>
          <b>{isRed ? "NOT DEPLOYMENT-READY" : loadFailed ? "PROOF ARTIFACT UNAVAILABLE" : "LOADING CANONICAL PROOF"}</b>
          <span>{proof ? "VALIDATION RED · corrected protocol complete" : loadFailed ? `${PROOF_SOURCE} could not be loaded; no fallback metrics shown` : PROOF_SOURCE}</span>
        </div>
      </header>

      <section className="provenance-strip" aria-label="Dataset provenance">
        <div><span>DATASET</span><strong>{proof ? `IO-VNBD · ${proof.provenance.independent_source_files} real-car files` : "Awaiting proof artifact"}</strong></div>
        <div><span>PROTOCOL</span><strong>{proof?.provenance.protocol ?? "—"}</strong></div>
        <div><span>SESSIONS</span><strong className="mono">{proof?.provenance.viable_sessions ?? "—"}</strong></div>
        <div><span>MANIFEST</span><strong className={proof ? "status-ok" : "status-warn"}>{proof?.provenance.manifest_path ?? "NOT LOADED"}</strong></div>
      </section>

      <section className="challenge-band">
        <div className="challenge-title">
          <span>CANONICAL VERDICT</span>
          <strong className={isRed ? "status-bad" : ""}>{proof?.status.replaceAll("_", " ") ?? "AWAITING ARTIFACT"}</strong>
        </div>
        <div className="challenge-timeline">
          <div className="done"><i>01</i><b>Corrected</b><span>vehicle yaw = −GYROSCOPE Pitch</span></div>
          <div className="done"><i>02</i><b>Segmented</b><span>{proof ? `${proof.provenance.viable_sessions} viable sessions` : "session boundaries enforced"}</span></div>
          <div className={isRed ? "validation-failed" : "pending"}><i>03</i><b>Validation</b><span>{isRed ? "RED · deployment blocked" : "awaiting canonical verdict"}</span></div>
        </div>
      </section>

      <section className="evidence-workspace">
        <div className="blackout-viz">
          <div className="viz-heading">
            <div><span>CORRECTED RELIABILITY PROOF</span><b>All placements · no cherry-picked product pass</b></div>
          </div>
          {proof?.plots[0]
            ? <img className="proof-reliability-plot" src={proof.plots[0]} alt="Corrected reliability proof for all 120 real-car placements" />
            : <div className="proof-unavailable">Canonical reliability plot unavailable</div>}
          <div className="viz-legend">
            <span>corrected, segmented real-car replay</span>
            <EvidenceBadge kind="REAL CAR" />
          </div>
        </div>

        <aside className="evidence-readout">
          <p className="readout-kicker">Corrected real-car proof</p>
          <strong className="big-ratio">{overall?.n ?? "—"}</strong>
          <p>placements across {proof?.provenance.independent_source_files ?? "—"} source files and {proof?.provenance.viable_sessions ?? "—"} segmented sessions.</p>
          <div className="readout-stat"><span>Median final error</span><b>{overall ? `${overall.final_error_m.p50.toFixed(1)} m` : "—"}</b></div>
          <div className="readout-stat"><span>P95 final error</span><b>{overall ? `${overall.final_error_m.p95.toFixed(1)} m` : "—"}</b></div>
          <div className="readout-stat"><span>95% endpoint coverage</span><b className="status-bad">{percent(overall?.coverage_95_endpoint)}</b></div>
          <div className="readout-stat"><span>Error &gt; 50 m</span><b className="status-bad">{percent(overall?.failure_rate_over_50m)}</b></div>
          <p className="hard-note">{proof?.honesty_note ?? "No fallback claims are displayed without the canonical proof artifact."}</p>
        </aside>
      </section>

      <section className="analytics-band">
        <div className="analytic">
          <div className="analytic-head"><span>OVERALL MEDIAN</span><b>Real-car final position error</b></div>
          <strong className="canonical-metric">{overall ? `${overall.final_error_m.p50.toFixed(1)} m` : "—"}</strong>
          <p>Across all corrected placements.</p>
        </div>
        <div className="analytic">
          <div className="analytic-head"><span>P95 ERROR</span><b>Real-car failure tail</b></div>
          <strong className="canonical-metric status-bad">{overall ? `${overall.final_error_m.p95.toFixed(1)} m` : "—"}</strong>
          <p>The long failure tail is retained in the verdict.</p>
        </div>
        <div className="analytic">
          <div className="analytic-head"><span>COVERAGE</span><b>Target 95%</b></div>
          <strong className="canonical-metric status-bad">{percent(overall?.coverage_95_endpoint)}</strong>
          <p>Observed endpoint coverage; validation remains red.</p>
        </div>
      </section>

      <section className="results-section">
        <div className="results-top">
          <div><span className="section-eyebrow">Evidence classes</span><h2>Real proof and injected counterfactual</h2></div>
        </div>
        <div className="result-table" role="table">
          <div className="result-row result-header" role="row"><span>Evidence</span><span>Class</span><span>Scope</span><span>Measured result</span><span>Verdict</span></div>
          <div className="result-row" role="row">
            <span><b>Corrected reliability battery</b><small>{proof?.provenance.axis_mapping.vehicle_gz_yaw ?? "canonical axis mapping"}</small></span>
            <span><EvidenceBadge kind="REAL CAR" /></span>
            <span>{overall?.n ?? "—"} placements · {proof?.provenance.independent_source_files ?? "—"} files · {proof?.provenance.viable_sessions ?? "—"} sessions</span>
            <span className="mono">{overall ? `${overall.final_error_m.p50.toFixed(1)} m median` : "—"}<small>{overall ? `${overall.final_error_m.p95.toFixed(1)} m p95 · ${percent(overall.failure_rate_over_50m)} over 50 m` : "artifact not loaded"}</small></span>
            <span className="verdict bad">NOT DEPLOYMENT-READY</span>
          </div>
          <div className="result-row" role="row">
            <span><b>Lean-aware counterfactual</b><small>Clearly injected fixture; not field evidence</small></span>
            <span><EvidenceBadge kind="INJECTED LEAN" /></span>
            <span>{proof?.counterfactual.data_class ?? "synthetic injected fixture"}</span>
            <span className="mono">{counterfactual ? `${counterfactual.car_style.final_error_m.toFixed(2)} m car → ${counterfactual.lean_aware.final_error_m.toFixed(2)} m lean` : "—"}</span>
            <span className="verdict injected">INJECTED ONLY</span>
          </div>
        </div>
      </section>
    </main>
  );
}

export function EnterpriseNav({ active, navigate }: { active: "evidence" | "operations"; navigate: (view: "landing" | "console" | "operations" | "evidence") => void }) {
  return <nav className="enterprise-nav">
    <button className="wordmark" type="button" onClick={() => navigate("landing")}>IDR<span>.</span></button>
    <div className="enterprise-nav-links">
      <button className={active === "evidence" ? "active" : ""} type="button" onClick={() => navigate("evidence")}>Evidence Room</button>
      <button className={active === "operations" ? "active" : ""} type="button" onClick={() => navigate("operations")}>Operations</button>
      <button type="button" onClick={() => navigate("console")}>Product Console</button>
    </div>
    <span className="enterprise-mode">BUYER EVALUATION · READ ONLY</span>
  </nav>;
}
