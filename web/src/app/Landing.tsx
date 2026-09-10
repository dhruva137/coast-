import { CoastWordmark } from "../components/CoastMark";

type LandingProps = {
  onOpenConsole: () => void;
  onRunDemo: () => void;
  onNavigate: (view: "landing" | "console" | "evidence" | "operations" | "apk") => void;
};

export function Landing({ onOpenConsole, onRunDemo, onNavigate }: LandingProps) {
  return (
    <div className="landing">
      <div className="announcement-banner" style={{
        background: "linear-gradient(90deg, #0070f3, #ff3366)",
        color: "white",
        textAlign: "center",
        padding: "8px 16px",
        fontSize: "13px",
        fontWeight: 600,
        letterSpacing: "0.02em",
        position: "relative",
        zIndex: 41
      }}>
        NEW: AVNet-tiny IDR Backbone released! 10Hz on-device inference for leaning two-wheelers.
      </div>
      <nav className="landing-nav" aria-label="Product">
        <div className="brand-mark" aria-hidden="true">
          <CoastWordmark size={22} />
        </div>
        <div className="nav-links">
          <a href="#pricing">SDK</a>
          <a href="#docs">Claims</a>
          <a href="#console-jump" onClick={(e) => { e.preventDefault(); onOpenConsole(); }}>
            Console
          </a>
          <a href="#/apk" onClick={(e) => { e.preventDefault(); onNavigate("apk"); }}>
            APK
          </a>
          <a href="#/evidence" onClick={(e) => { e.preventDefault(); onNavigate("evidence"); }}>
            Evidence
          </a>
          <a href="#/operations" onClick={(e) => { e.preventDefault(); onNavigate("operations"); }}>
            Operations
          </a>
        </div>
        <button className="nav-cta" type="button" onClick={onOpenConsole}>
          Open console
        </button>
      </nav>

      <header className="hero">
        <div className="hero-plane" aria-hidden="true" />
        <div className="hero-track" aria-hidden="true">
          <svg viewBox="0 0 640 520" preserveAspectRatio="xMidYMid meet">
            <text className="label" x="72" y="48">GNSS DENIED · INS</text>
            <path
              className="path-base"
              d="M80 120 C 160 140, 200 220, 240 280 S 320 400, 400 420 S 520 380, 560 300"
            />
            <path
              className="path-ours"
              d="M80 110 C 150 100, 190 180, 250 240 S 340 340, 420 360 S 500 320, 548 250"
            />
            <circle className="dot-live" cx="548" cy="250" r="5" />
            <text className="label" x="420" y="210">COAST lean-aware</text>
            <text className="label" x="300" y="455">car-style baseline</text>
          </svg>
        </div>

        <div className="hero-copy">
          <p className="hero-kicker">Intelligent Dead Reckoning</p>
          <h1 className="hero-brand">
            COAST<span className="dot">.</span>
          </h1>
          <h2 className="hero-headline">Keep the fleet moving when GNSS dies.</h2>
          <p className="hero-lede">
            Smartphone SDK for ride-hailing, delivery, and ambulance — lean-aware dead reckoning
            for two-wheelers underground, in underpasses, and dense urban canyons.
          </p>
          <div className="hero-ctas">
            <button className="btn-primary" type="button" onClick={onOpenConsole}>
              Open console
            </button>
            <button className="btn-ghost" type="button" onClick={onRunDemo}>
              Run live demo
            </button>
            <button className="btn-ghost" type="button" onClick={() => onNavigate("evidence")}>
              Inspect evidence
            </button>
          </div>
          <div className="hero-status">
            <span>
              <b>Target</b> · ISRO &lt;10% · &lt;100 m/km
            </span>
            <span>
              <b>Class</b> · 10 Hz on-device
            </span>
            <span>
              <b>Hardware</b> · phone only
            </span>
          </div>
        </div>
      </header>

      <section className="section pricing" id="pricing">
        <div className="section-head">
          <p className="section-eyebrow">SDK license</p>
          <h2 className="section-title">Ship COAST into your navigation stack.</h2>
          <p className="section-lede">
            Placeholder commercial tiers for buyers evaluating a phone-side DR module. No
            published customer logos — pricing is indicative until pilots close.
          </p>
        </div>
        <div className="tier-grid">
          <article className="tier">
            <h3 className="tier-name">Pilot</h3>
            <p className="tier-price">Contact · 30–90 day eval</p>
            <p className="tier-blurb">
              Single city / campus integration. Replay harness + judge console. Engineering
              office hours during outage scenarios.
            </p>
            <ul>
              <li>TypeScript / C++ core access</li>
              <li>Campus graph + simulator</li>
              <li>Act scripts for internal demos</li>
              <li>No production SLA</li>
            </ul>
            <button className="tier-cta" type="button" onClick={onOpenConsole}>
              Start with console
            </button>
          </article>
          <article className="tier featured">
            <h3 className="tier-name">Fleet</h3>
            <p className="tier-price">Per MAU · volume bands</p>
            <p className="tier-blurb">
              Ride-hailing and delivery fleets. On-device 10 Hz class estimate, branch-decision
              hooks, and lean-aware two-wheeler path.
            </p>
            <ul>
              <li>Production SDK embedding</li>
              <li>Graph particle filter API</li>
              <li>Error-budget diagnostics</li>
              <li>Priority support window</li>
            </ul>
            <button className="tier-cta" type="button" onClick={onRunDemo}>
              Run fleet demo
            </button>
          </article>
          <article className="tier">
            <h3 className="tier-name">Enterprise</h3>
            <p className="tier-price">Custom · ISRO / OEM / ambulance</p>
            <p className="tier-blurb">
              Source escrow, on-prem builds, and joint validation against your GNSS-denied
              corridors. Contractual claims only after measured logs.
            </p>
            <ul>
              <li>C++17 port + golden vectors</li>
              <li>Custom road-graph ingest</li>
              <li>Joint validation protocol</li>
              <li>Security review path</li>
            </ul>
            <button className="tier-cta" type="button" onClick={onOpenConsole}>
              Review claims first
            </button>
          </article>
        </div>
        <p className="pricing-note">
          Honest status: research prototype framed for SIH 26168 / ISRO smart vehicles. Fleet
          and Enterprise terms are placeholders — do not treat as a live storefront.
        </p>
      </section>

      <section className="section docs" id="docs">
        <div className="section-head">
          <p className="section-eyebrow">Docs strip</p>
          <h2 className="section-title">What we claim — and what we do not.</h2>
          <p className="section-lede">
            Jury and buyer brief. Defensible lines only. Simulation until campus two-wheeler
            logs exist.
          </p>
        </div>
        <div className="docs-grid">
          <div className="docs-col">
            <h3>Defensible claims</h3>
            <ul>
              <li>First smartphone DR path that treats leaning two-wheelers as first-class</li>
              <li>Fixed-point coordinated-turn solver with cos(Δφ) insensitivity</li>
              <li>Error budget: heading hurts far more than speed (F8, simulated)</li>
              <li>Branch-decision accuracy as the user-facing metric</li>
            </ul>
          </div>
          <div className="docs-col">
            <h3>Limitations</h3>
            <ul>
              <li className="warn">Findings F1–F12 are simulation until real two-wheeler logs</li>
              <li>Hard braking mid-turn remains a failure mode (~0.4 g → high drift)</li>
              <li>Tight forks (±8°) degrade branch posterior confidence</li>
              <li>Do not claim discovery of roll/yaw kinematics or classic map-matching</li>
            </ul>
          </div>
          <div className="docs-col">
            <h3>ISRO bars</h3>
            <div className="isro-bars">
              <div className="isro-bar">
                <span className="lbl">Drift</span>
                <div className="track">
                  <div className="fill" style={{ width: "100%" }} /> {/* claims:ignore layout */}
                </div>
                <span className="val">&lt; 10%</span>
              </div>
              <div className="isro-bar">
                <span className="lbl">Error</span>
                <div className="track">
                  <div className="fill" style={{ width: "92%", animationDelay: "0.12s" }} /> {/* claims:ignore layout */}
                </div>
                <span className="val">&lt; 100 m / km</span>
              </div>
              <div className="isro-bar">
                <span className="lbl">Rate</span>
                <div className="track">
                  <div className="fill" style={{ width: "85%", animationDelay: "0.24s" }} /> {/* claims:ignore layout */}
                </div>
                <span className="val">10 Hz class</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="landing-foot">
        <div className="brand-mark">
          <CoastWordmark size={22} />
        </div>
        <span>SIH 26168 · framed for ISRO / fleet buyers · phone-side dead reckoning</span>
        <div className="footer-actions">
          <button className="btn-ghost" type="button" onClick={() => onNavigate("evidence")}>Evidence room</button>
          <button className="btn-ghost" type="button" onClick={() => onNavigate("operations")}>Operations</button>
          <button className="btn-ghost" type="button" onClick={onOpenConsole}>Open console</button>
        </div>
      </footer>
    </div>
  );
}
