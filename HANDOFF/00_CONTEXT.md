# COAST — project context

**Read this first.** Written for any AI assistant or teammate joining cold. It
states what is true, not what we hope. Then read the task file for your area:
`01_APK_TASKS.md`, `02_CONSOLE_AND_DEPLOY.md`, `03_MODEL.md`.

---

## 1. What this is

**Smart India Hackathon 2026, problem statement 26168**, ISRO / Dept. of Space:
*"AI-ML based Intelligent Dead Reckoning system for seamless navigation."*

When a vehicle enters a tunnel, underpass, car park or urban canyon, GNSS dies
and every navigation app freezes. **COAST** keeps position moving using only the
phone's accelerometer, gyroscope and magnetometer — no OBD-II, no extra hardware
— and constrains the estimate to an offline OpenStreetMap road graph so error
cannot grow without bound.

**The core thesis, and the thing the whole pitch rests on:** the instinct is to
buy a better sensor. We tested it and it is wrong — given a *perfect, simulated,
zero-error* gyroscope, free dead reckoning **still fails 55%** of 60-second
segments. The bottleneck was never sensor quality; it was the absence of a
structural constraint.

So instead of estimating a free position `(x, y)` and snapping to a road
afterwards, the filter's state **is** `(road edge, offset along edge)`. Off-road
is not representable. The control that proves the *in-loop* part matters:
post-hoc snapping scores **0.98× — worse than doing nothing**.

---

## 2. Repository map

| Path | What it is |
|---|---|
| `android/` | COAST Navigator — the Android app, the PS deliverable |
| `web/` | COAST Command — laptop console (Python stdlib HTTP + static JS) |
| `lab/` | Training and benchmark harness. Every published number comes from here |
| `core/` | Shared C++ estimator core → Android JNI, WASM, headless edge daemon |
| `relay/` | Store-and-forward pairing relay (internet-based, not LAN) |
| `site/` | Static landing page intended for Cloudflare Pages |
| `tools/` | `verify_claims.py`, `build_deck.py`, `make_deck_figures.py`, `package_apk.py` |
| `win_tuning/CLAIMS.json` | The 20-claim registry. **Generated — never hand-edit** |
| `docs/MODEL_CARD.md` | COAST-VNet-1 model card, honest numbers |
| `final_demo_pitch/` | The SIH IDEA deck and its assets |
| `tests/` | pytest suite |

**Key web files:** `coast_console.py` (routes), `console_ui.py` (the page),
`pairing.py` (fleet + QR), `engine_compute.py` (live estimator arithmetic),
`security.py`, `auth.py`. Static JS: `app.js`, `engine_calc.js`,
`trace_replay.js`, `world_map.js`, `model_viz.js`.

**Key Android files:** `ui/DriveScreen.kt`, `ui/PairingScreen.kt`,
`ui/MapLibreDriveMap.kt`, `ui/MapBackend.kt`, `nav/SimpleIns.kt`,
`nav/GraphPfEngine.kt` (JNI-shaped hole), `sensor/DeviceProbe.kt`,
`record/RecordService.kt`, `pair/`.

---

## 3. The frozen numbers

All 20 live in `win_tuning/CLAIMS.json`, each re-derived from a measured file by
`python tools/verify_claims.py`, which **fails the build** if any surface states
a number no file produced.

| Claim | Value |
|---|---|
| Map-in-loop vs free DR | **2.02× lower median position error** (252.66 → 125.20 m), 43 outages, CAN truth |
| The negative result | **A perfect gyro still fails 55%** of 60-s segments |
| The control | Post-hoc snapping **0.98× — worse than nothing** |
| Median drift | free 27.58% → COAST **16.77%** (ISRO bar <10% — **not met**) |
| Free-DR pass arms | 17% short / 10% tunnel |
| Heading channel | gyro 16.87% → onset-calibrated compass **7.22%** (655 windows) |
| Edge engine | **19,682 Hz worst config = 98×** the 200 Hz requirement |
| GNSS+INS fusion | **1.07× — a wash** (classical LC-EKF, not AI-based) |
| Our own bug | a unit error inflating every drift figure **3.6×**, found and fixed by us |

### Hard rules
- **Never state a number not in the registry.** Never claim we beat the 10% bar.
- **Never fake a green.** No simulated progress, no interpolated curves, no
  `except: return <plausible value>`. Failures show the real error.
- **Never resurrect the confidence radius** — its spread correlates **−0.23**
  with real error, so it is deliberately hidden.
- **Do not touch** `android/app/src/main/assets/demo/iovnbd_demo.csv` or
  `assets/maps/demo_neighbourhood.mbtiles`.
- **No ToS violations** — do not scrape Google/Apple map tiles. The PS names
  OpenStreetMap, so OSM is *compliance*, not compromise.

---

## 4. Honest scorecard against the problem statement

| PS requirement | Status |
|---|---|
| In-vehicle alignment & calibration | 🟡 built; online alignment measured a **wash** (32%→32%); yaw-to-vehicle open |
| AI speed & vibration filter | ✅ frequency-decoupled by design; loses to hold-last-speed per-window, ~8% better closed-loop |
| Map-matching + NHC + kinematics | ✅ **strongest deliverable** — HMM (Newson-Krumm, cited) + NHC + 2.02× |
| **AI-based GNSS+INS fusion** | ❌ **biggest gap** — classical LC-EKF at 1.07×. No pseudoranges in dataset |
| Seamless handover both directions | ✅ **100 ms** across 15/15 events |
| Real-time nav interface | 🟡 built; marker smoothing weak and it is graded |
| Magnetometer as an input | 🟡 fused in `SimpleIns`; end-to-end transfer unproven |
| DR drift < 10% | ❌ at **16.77%** — say this first, before a judge finds it |
| 10 Hz phone / 200 Hz edge | ✅ exceeded — 98× worst case |
| External IMU / edge engine | ✅ shared C++ core → JNI + WASM + daemon |

---

## 5. Traps — things that look true and are not

- **The residual speed model failed under rollout.** Teacher-forced it beats
  persistence 13/23 folds; under closed-loop rollout — the actual deployment
  contract — it wins **0/23** with 213.5 m median 60 s error vs hold's 7.7 m.
  Correctly rejected; the 6-channel ONNX stays. Do not revive it without
  solving exposure bias.
- **Filter traces contradict the benchmark.** All exported traces in
  `lab/stress/results/traces/` show map-in-loop *losing* to free DR (0.26×,
  0.79×, 0.21×) while the verified aggregate is 2.02× better and the summary
  records "helped 28 | hurt 15". The exporter likely does not match the
  benchmark config. **This blocks the best possible demo visual.**
- **Several experiment dirs are smoke runs**, n=2 to n=19, not full protocol.
  Check `n` before quoting anything from `mapfilter_compass`,
  `gnss_ins_fusion_learned`, `gnss_ins_fusion_ai`.
- **2.02× is lab Python, not the phone.** The phone runs `SimpleIns` + ONNX
  speed; the on-device map-PF slot (`GraphPfEngine`) is empty.
- **At 10 Hz, Nyquist is 5 Hz.** The model's "high-frequency" vibration branch
  cannot physically observe 20–100 Hz road/engine vibration. Resampling may
  beat any architecture change.
- **Windows PowerShell has no `&&`.** Use separate lines or `;`.
- **Gradle works on the user's machine** (`BUILD SUCCESSFUL`). It fails only
  inside sandboxes that cannot open a loopback socket. Use
  `./gradlew assembleStandardRelease` — **not** `tools/package_apk.py`, which
  is a sandbox-only fallback and has caused launch crashes.

---

## 6. Verification gate — run after every change

```bash
python tools/verify_claims.py          # 20/20 traced to measured files
python -m pytest tests/ -q
python web/test_console_routes.py
cd android
./gradlew testStandardDebugUnitTest
./gradlew assembleStandardRelease
```

Output APK: `android/app/build/outputs/apk/standard/release/app-standard-release.apk`

---

## 7. Four launch-crash bugs already fixed — verify they survive your edits

1. **Splash NPE** — `SplashScreenView.getIconView()` is `@Nullable` but
   core-splashscreen asserts non-null; throws on some ROMs during the first
   frame. Guarded with `runCatching` in `MainActivity.kt`.
2. **MapLibre native init** — `abiFilters` ships arm64/armv7 only, so on x86
   emulators `libmaplibre.so` is absent → `UnsatisfiedLinkError`. Probed once,
   falls back to Canvas map.
3. **Bundled tiles beat live tiles** — the pack only covers Coventry, so live
   drives elsewhere showed a dark rectangle. Now bounds-checked
   (`insideBundledTilePack`).
4. **`onTimeout` wrong overload** — Android 15 `dataSync` calls the two-arg
   form. Both now overridden in `RecordService.kt`.

---

## 8. The posture that has been working

Volunteer the gap before anyone finds it. We publish our own negative results —
the 0.98×, the 1.07×, the 55%, the rejected residual model, the 3.6× bug we
found in our own pipeline — and that is *why* the wins are believed. A registry
containing only wins is one nobody should trust. Keep it that way.
