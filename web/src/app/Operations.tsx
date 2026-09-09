import { EnterpriseNav } from "./EvidenceRoom";

const devices = [
  { id: "DEMO-RIDER-014", health: "Nominal", ood: "0.08", confidence: "92%", outage: "—", consent: "Granted · expires 18:00" }, // claims:ignore seeded demo
  { id: "DEMO-RIDER-027", health: "Degraded", ood: "0.61", confidence: "44%", outage: "Active · 01:42", consent: "Granted · shift only" }, // claims:ignore seeded demo
  { id: "DEMO-RIDER-031", health: "Offline", ood: "—", confidence: "—", outage: "Closed · 12:18", consent: "Revoked · 17:06" },
];

export function Operations({ navigate }: { navigate: (view: "landing" | "console" | "evidence" | "operations") => void }) {
  return (
    <main className="enterprise-page operations-page">
      <EnterpriseNav active="operations" navigate={navigate} />
      <header className="enterprise-head operations-head">
        <div>
          <p className="section-eyebrow">Consent-based fleet assurance</p>
          <h1>Operations</h1>
          <p>Health, uncertainty, and outage response—without covert person tracking.</p>
        </div>
        <div className="demo-fleet-banner">
          <b>SEEDED DEMO FLEET</b>
          <span>No customer, rider, or live location data</span>
        </div>
      </header>

      <section className="ops-command">
        <div className="ops-map" aria-label="Abstract demo fleet operations map">
          <div className="map-grid" />
          <svg viewBox="0 0 760 410" preserveAspectRatio="none" aria-hidden="true">
            <path className="ops-road" d="M0 320 C140 280 190 350 325 270 S530 150 760 190" />
            <path className="ops-road secondary" d="M160 0 C190 100 270 130 325 270 S390 390 470 410" />
            <path className="outage-corridor" d="M406 220 C450 182 500 157 562 151" />
            <circle className="fleet-dot nominal" cx="254" cy="307" r="7" />
            <circle className="fleet-dot degraded" cx="506" cy="164" r="8" />
            <circle className="fleet-dot offline" cx="324" cy="268" r="7" />
          </svg>
          <div className="ops-map-label north">DEMO ZONE · NON-GEOGRAPHIC</div>
          <div className="incident-callout">
            <span>GNSS OUTAGE · DEMO-RIDER-027</span>
            <b>01:42 active · confidence 44%</b> {/* claims:ignore seeded demo */}
            <small>Fallback degraded · dispatch notified</small>
          </div>
          <div className="map-consent">Locations rendered only while shift consent is valid.</div>
        </div>

        <aside className="ops-summary">
          <div className="ops-clock"><span>OPERATIONAL POSTURE</span><b>DEGRADED</b><small>1 active outage · demo data</small></div>
          <div className="ops-metric"><span>Consent-valid devices</span><b>2 / 3</b></div>
          <div className="ops-metric"><span>OOD alerts</span><b className="status-warn">1</b></div>
          <div className="ops-metric"><span>Median confidence</span><b>68%</b></div> {/* claims:ignore seeded demo */}
          <div className="ops-metric"><span>Audit events today</span><b>18</b></div>
          <div className="privacy-posture">
            <strong>Privacy posture</strong>
            <p>No hidden tracking. Collection is purpose-bound, time-limited, visible to the operator, and revocable.</p>
          </div>
        </aside>
      </section>

      <section className="fleet-section">
        <div className="section-line"><div><span className="section-eyebrow">Device assurance</span><h2>Demo fleet state</h2></div><span className="data-age">SNAPSHOT · NOT LIVE</span></div>
        <div className="fleet-table">
          <div className="fleet-row fleet-header"><span>Device</span><span>Health</span><span>OOD score</span><span>Confidence</span><span>GNSS incident</span><span>Consent scope</span></div>
          {devices.map((device) => <div className="fleet-row" key={device.id}>
            <span className="mono">{device.id}</span>
            <span><i className={`health-dot ${device.health.toLowerCase()}`} />{device.health}</span>
            <span className="mono">{device.ood}</span>
            <span className="mono">{device.confidence}</span>
            <span>{device.outage}</span>
            <span className={device.consent.startsWith("Revoked") ? "status-warn" : "status-ok"}>{device.consent}</span>
          </div>)}
        </div>
      </section>

      <section className="audit-section">
        <div className="audit-trail">
          <div className="section-line"><div><span className="section-eyebrow">Immutable activity trail</span><h2>Consent &amp; access audit</h2></div><span className="hash-link">CHAIN VERIFIED · DEMO</span></div>
          <div className="audit-events">
            <div><time>17:06:21</time><i className="revoke" /><p><b>Consent revoked</b><span>DEMO-RIDER-031 · location stream stopped within 1 s</span></p><code>evt…7af2</code></div>
            <div><time>16:58:03</time><i /><p><b>Incident accessed</b><span>Role: safety_operator · purpose: outage triage</span></p><code>evt…29cd</code></div>
            <div><time>16:57:48</time><i className="alert" /><p><b>OOD threshold crossed</b><span>DEMO-RIDER-027 · policy escalated confidence state</span></p><code>evt…10be</code></div>
            <div><time>16:30:00</time><i /><p><b>Shift consent granted</b><span>DEMO-RIDER-014 · purpose: navigation resilience</span></p><code>evt…e418</code></div>
          </div>
        </div>
        <aside className="access-policy">
          <span className="section-eyebrow">Enforced access policy</span>
          <h2>Tracking requires a reason.</h2>
          <ol>
            <li><b>Consent</b><span>Operator sees collection state and can revoke.</span></li>
            <li><b>Purpose</b><span>Outage response, safety, or device diagnostics only.</span></li>
            <li><b>Least privilege</b><span>Location access is role- and incident-scoped.</span></li>
            <li><b>Retention</b><span>Raw traces expire; aggregate evidence remains.</span></li>
          </ol>
          <p className="ethics-reject">Explicitly prohibited: hidden person tracking, off-shift monitoring, and customer data repurposing.</p>
        </aside>
      </section>
    </main>
  );
}
