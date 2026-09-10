# COAST — path prediction when GNSS dies

Smart India Hackathon 2026 · ISRO problem statement 26168.

COAST is an Android app and a fleet console that keeps a vehicle's position
moving through tunnels, urban canyons, and jam zones — on-device, no cloud fix
required. It ships with **COAST-VNet-1**, a 96,086-parameter, 392 KB neural
inertial-odometry model trained on IO-VNBD with CAN-bus speed truth.

- **APK**: field-side dead-reckoning navigator with a live sensor demo, session
  history, and console pairing over LAN.
- **Console** (`web/`): fleet map, model page, training telemetry, evidence
  registry, session replay. Runs on a laptop at the venue.
- **Landing page** (`site/`): the public model release page. Ships as static
  HTML — deploys to Vercel or Cloudflare Pages in one click.

---

## Quick tour

### Landing page

Open [`site/index.html`](site/index.html) in any browser. That's the public
model release page — hero, spec grid, closed-loop benchmark table against the
naive baselines and the ISRO PS 26168 bar, and downloads.

To deploy it, see [`site/DEPLOY.md`](site/DEPLOY.md) for step-by-step Vercel
and Cloudflare Pages instructions, including how to point
`coast.paper2anything.com` at either host.

### Console (laptop)

```bash
python -m web.coast_console
# → http://127.0.0.1:8787
```

Front door → **Open the console** for the fleet + model + training tabs, or
**See docs** to open the landing page in a new tab. Live pairing (QR + code)
and training runs live on this process.

### APK (Android)

Build locally (Gradle daemon can't run in every sandbox, so no CI wrap):

```bash
cd android
./gradlew assembleStandardDebug
```

Output: `android/app/build/outputs/apk/standard/debug/app-standard-debug.apk`.

Optional packager that keeps `.onnx` STORE-aligned and produces a versioned
name:

```bash
python tools/package_apk.py --flavor standard --build-type debug
# → android/dist/COAST-standard-debug.apk
```

The APK ships four tabs:

- **DRIVE** — full-bleed MapLibre map on the public OpenStreetMap tile server.
  Bottom sheet holds speed, mode, and the pair-with-console button.
- **SENSE** — live sensor demo: spirit level, compass needle (rotation-vector
  based, calibration verified in [`SensorMathTest`](android/app/src/test/java/in/sih26168/idr/nav/SensorMathTest.kt)),
  pitch / roll / shake / spin, and a shake recorder that draws a live graph
  and saves each session to Signal History.
- **CONNECT** — paste the console pairing link, or type a 6-digit code. Camera
  QR scanning is a tertiary option.
- **SETTINGS** — account, help, signal history, vehicle profile, map appearance.

### Running the console-route tests

```bash
python web/test_console_routes.py
python tools/verify_claims.py
```

Both must exit `OK`. `verify_claims.py` proves every number the console
displays traces back to a committed measurement file.

---

## What the model actually does

**COAST-VNet-1** is a frequency-decoupled CNN-GRU. A phone on a dashboard sees
two superimposed signals: **vehicle motion** in the low band and **road and
engine vibration** in the high band. Rather than filter one away, the network
splits the band and treats them as different information, fusing them into a
single forward-speed estimate for dead reckoning.

| | |
|---|---|
| Architecture | frequency-decoupled CNN-GRU |
| Parameters | 96,086 |
| ONNX size | 392 KB |
| Input | `(20, 6)` · 2.0 s window at 10 Hz · `ax ay az gx gy gz` (SI, phone frame) |
| Output | forward speed (m/s) + log-σ² head |
| Runtime | ONNX Runtime Mobile · CPU on device |

### Measured, held-out closed-loop performance

Leave-file-out over 23 IO-VNBD drives, 12 epochs per fold, CAN-truth labels:

| Method | Median distance error | Median drift | Folds won |
|---|---:|---:|---:|
| **COAST-VNet-1 · ours** | **150.3 m** | **18.0%** | **9 / 23** |
| Frozen onset speed (naive) | 163.2 m | 21.1% | — |
| Free-DR integrate (naive) | 303.6 m | 36.4% | — |

System-level (map-in-loop over 43 outages): **2.02× lower** median position
error than naive DR. Edge engine throughput: worst case **19,682 Hz**, 98× the
200 Hz problem-statement requirement.

Full protocol, per-fold table, and every ablation are in
[`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).

---

## Repository layout

| Path | What lives here |
|---|---|
| `android/` | Kotlin APK (Jetpack Compose + MapLibre + ONNX Runtime Mobile) |
| `web/` | Python console — HTTP + SSE, fleet map, model page, training telemetry, evidence |
| `site/` | Static landing page (Vercel / Cloudflare Pages ready) |
| `core/ts/` `core/cpp/` | Estimator: InEKF, graph particle filter, C++ port, golden vectors |
| `lab/` | Python experiments, training runs, evaluation harness |
| `maps/` | Offline OSM extraction and tile packs |
| `docs/` | Model card, architecture notes, the project bible |
| `tools/` | `verify_claims.py`, `package_apk.py`, and utilities |

---

## Claim verification

Every claim-shaped number in the console and the landing page traces back to a
committed measurement file:

```bash
python tools/verify_claims.py
```

Numbers that would not survive that check never make it onto the page.

---

## Licence

Prototype for Smart India Hackathon 2026. Dataset IO-VNBD remains under its
upstream licence.
