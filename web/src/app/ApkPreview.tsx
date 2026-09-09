import { useState } from "react";
import { CoastMark } from "../components/CoastMark";
import { PhoneMap } from "../components/PhoneMap";

type Tab = "DRIVE" | "SESSIONS" | "SETTINGS" | "ABOUT";
type NavMode = "idle" | "gps" | "coast";

const VEHICLES = ["SCOOTER", "MOTORCYCLE", "WALK", "CAR"] as const;

export function ApkPreview({ onBack }: { onBack: () => void }) {
  const [tab, setTab] = useState<Tab>("DRIVE");
  const [live, setLive] = useState(false);
  const [blackout, setBlackout] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [vehicle, setVehicle] = useState<(typeof VEHICLES)[number]>("SCOOTER");
  const [darkMap, setDarkMap] = useState(true);
  const [showGhost, setShowGhost] = useState(false);

  const mode: NavMode = !live ? "idle" : blackout ? "coast" : "gps";
  const pill =
    mode === "idle" ? "READY" : mode === "gps" ? "GPS  ·  14 sats" : "COAST — AI speed + road lock";
  const pillClass = mode === "idle" ? "mute" : mode === "gps" ? "gnss" : "amber";
  const speed = live ? (blackout ? "28" : "31") : "--";
  const since = live ? (blackout ? "86" : "0") : "--";
  const modeLabel = mode === "idle" ? "—" : mode === "gps" ? "GPS" : "COAST";

  return (
    <div className="apk-desk">
      <aside className="apk-notes">
        <button className="pill btn-like" type="button" onClick={onBack}>
          Product
        </button>
        <h1>COAST APK on this laptop</h1>
        <p>
          Phone-frame preview of the Android app. Click around, then tell me what to change — I
          will update this UI live without you installing on a phone.
        </p>
        <ol>
          <li>DRIVE is the judge surface (map + START).</li>
          <li>START / STOP and the eye FAB simulate GPS vs COAST.</li>
          <li>Bottom tabs match the APK: Drive, Sessions, Settings, About.</li>
        </ol>
        <p className="fine">
          Sensors are faked here. The sideload APK on Desktop is the real phone build.
        </p>
      </aside>

      <div className="apk-phone" aria-label="COAST Android preview">
        <div className="apk-status">
          <span>9:41</span>
          <span className="apk-notch" />
          <span>5G  ▮▮▮  88%</span> {/* claims:ignore mock chrome */}
        </div>

        <div className="apk-body">
          {tab === "DRIVE" && (
            <div className="apk-drive">
              <PhoneMap blackout={blackout} />
              <div className="apk-top">
                <button className="apk-help" type="button" onClick={() => setTab("ABOUT")}>
                  HELP
                </button>
                <div className={`apk-pill ${pillClass}`}>{pill}</div>
                <span className="apk-help-spacer" />
              </div>
              {live && (
                <div className="apk-motion">
                  {blackout ? "MOVING  ·  28 km/h" : "MOVING  ·  31 km/h"} {/* claims:ignore mock UI */}
                </div>
              )}
              <div className="apk-fabs">
                <button type="button" title="Recenter" aria-label="Recenter">
                  ⌖
                </button>
                <button type="button" title="Layers" aria-label="Layers" className="on">
                  ⧉
                </button>
                <button
                  type="button"
                  title="Simulate GNSS blackout"
                  aria-label="Simulate GNSS blackout"
                  className={blackout ? "warn" : ""}
                  onClick={() => live && setBlackout((b) => !b)}
                >
                  {blackout ? "⊘" : "◉"}
                </button>
              </div>
              <div className={`apk-sheet ${sheetOpen ? "open" : ""}`}>
                <button
                  className="apk-handle"
                  type="button"
                  aria-label="Expand sheet"
                  onClick={() => setSheetOpen((s) => !s)}
                />
                <div className="apk-mock-badge" aria-hidden={false}>
                  MOCK — not live data
                </div>
                <div className="apk-metrics">
                  <div>
                    <span>SPEED</span>
                    <b>
                      {speed} <i>km/h</i>
                    </b>
                  </div>
                  <div>
                    <span>MODE</span>
                    <b className={pillClass}>{modeLabel}</b>
                  </div>
                  <div>
                    <span>SINCE FIX</span>
                    <b>
                      {since} <i>m</i>
                    </b>
                  </div>
                </div>
                <button
                  className={`apk-go ${live ? "stop" : ""}`}
                  type="button"
                  onClick={() => {
                    if (live) {
                      setLive(false);
                      setBlackout(false);
                    } else {
                      setLive(true);
                    }
                  }}
                >
                  {live ? "STOP" : "START"}
                </button>
                {sheetOpen && (
                  <div className="apk-diag">
                    <p>LOOP · not marked yet</p>
                    <p>IMU 412 Hz · model FALLBACK until START on a real phone</p> {/* claims:ignore mock UI */}
                    <p>You can start without location. Relative mode uses motion sensors.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === "SESSIONS" && (
            <div className="apk-page">
              <h2>Sessions</h2>
              <p className="mute">No ride logs on this laptop preview. Field zips live on the phone.</p>
              <div className="apk-empty">FILES will list CHECK / RENAME / ZIP / DELETE after a RECORD ride.</div>
            </div>
          )}

          {tab === "SETTINGS" && (
            <div className="apk-page apk-scroll">
              <h2>Settings</h2>
              <p className="mute">Signed in as guest</p>
              <button className="apk-card-btn" type="button">
                ACCOUNT
              </button>
              <h3>VEHICLE</h3>
              <div className="apk-chips">
                {VEHICLES.map((v) => (
                  <button
                    key={v}
                    type="button"
                    className={vehicle === v ? "on" : ""}
                    onClick={() => setVehicle(v)}
                  >
                    {v}
                  </button>
                ))}
              </div>
              <h3>MAP</h3>
              <label className="apk-toggle">
                <span>Dark map</span>
                <input type="checkbox" checked={darkMap} onChange={() => setDarkMap((d) => !d)} />
              </label>
              <label className="apk-toggle">
                <span>Show ghost car</span>
                <input type="checkbox" checked={showGhost} onChange={() => setShowGhost((d) => !d)} />
              </label>
            </div>
          )}

          {tab === "ABOUT" && (
            <div className="apk-page apk-scroll">
              <div className="apk-about-brand">
                <CoastMark size={36} />
                <h2>COAST</h2>
              </div>
              <p className="apk-kicker">INTELLIGENT DEAD RECKONING · SIH 26168</p>
              <p className="mute">v0.4.0 · on-device only. No network, no account, no analytics.</p>
              <h3>WE CLAIM</h3>
              <ul>
                <li>First smartphone DR that handles leaning two-wheelers.</li>
                <li>Fixed-point coordinated-turn solver with cos(Δφ) insensitivity.</li>
                <li>Branch-decision accuracy as the user metric.</li>
              </ul>
              <h3>WE DO NOT CLAIM</h3>
              <ul>
                <li>Discovery of roll/yaw kinematics.</li>
                <li>Invention of map-matching for tunnels.</li>
              </ul>
            </div>
          )}
        </div>

        <nav className="apk-tabbar" aria-label="App tabs">
          {(["DRIVE", "SESSIONS", "SETTINGS", "ABOUT"] as Tab[]).map((t) => (
            <button key={t} type="button" className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              <span className="apk-tab-ic" aria-hidden>
                {t === "DRIVE" ? "➤" : t === "SESSIONS" ? "▤" : t === "SETTINGS" ? "⚙" : "?"}
              </span>
              {t}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
