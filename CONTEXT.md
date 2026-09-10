# COAST — project context

**Read this first in a new session.** Written 10 Sep 2026 from a full survey of
the `demo` branch. It says what is true, not what we hope.

---

## 1. What this is

**COAST** — Smart India Hackathon 2026, problem statement **26168**, ISRO /
Dept. of Space: *"AI-ML based Intelligent Dead Reckoning system for seamless
navigation."*

When a vehicle enters a tunnel, underpass, car park or urban canyon, GNSS dies
and every navigation app freezes. COAST keeps the position moving using only the
phone's accelerometer, gyroscope and magnetometer — no OBD-II, no extra hardware
— and constrains the estimate to an offline OpenStreetMap road graph so error
cannot grow without bound.

**The core insight, and the thing the pitch rests on:** the instinct is to buy a
better sensor. We tested that instinct and it is wrong — given a *perfect,
simulated, zero-error* gyroscope, free dead reckoning **still fails 55%** of
60-second segments. The bottleneck was never sensor quality; it was the absence
of a structural constraint. So instead of estimating a free position `(x, y)` and
snapping to a road afterwards, the filter's state **is** `(road edge, offset
along edge)`. Off-road is not representable.

The control that proves it is the *in-loop* part that matters: post-hoc snapping
scores **0.98× — worse than doing nothing**. Same map, opposite architecture.

---

## 2. The three surfaces

| Surface | What it is | State |
|---|---|---|
| **COAST Navigator** | Android app — the PS deliverable | Builds and installs. Four launch-crash bugs fixed (§5). Never run a real field drive. |
| **COAST Command** | Laptop console: engine arithmetic, live training, fleet, evidence | Running on `http://127.0.0.1:8787/`. All routes green. |
| **The lab** | Python training + benchmark harness | Strong and honest. Every published number has a source file. |
| **`site/`** | Static landing page for Cloudflare Pages | Skeleton exists (`index.html`, `styles.css`, `wrangler.toml`). Not deployed. |

**COAST-VNet-1** is the speed model: 96,086 params, 392 KB ONNX, 20×6 input at
10 Hz, frequency-decoupled CNN-GRU — low band through a GRU (vehicle motion),
high band through a conv stack (road/engine vibration, the noise the PS names).
Card: `docs/MODEL_CARD.md`.

---

## 3. The frozen numbers

All 20 live in `win_tuning/CLAIMS.json`, each re-derived from a measured file by
`python tools/verify_claims.py`, which **fails the build** if a slide states a
number no file produced. Currently **green, 20/20**.

| Claim | Value |
|---|---|
| Map-in-loop vs free DR | **2.02× lower median position error** (252.66 → 125.20 m), 43 real outages, CAN truth |
| The negative result | **A perfect gyro still fails 55%** of 60-s segments |
| The control | Post-hoc road snapping **0.98× — worse than nothing** |
| Median drift | free 27.58% → COAST **16.77%** (ISRO bar is <10% — **we do not meet it**) |
| Free-DR pass arms | 17% short / 10% tunnel |
| Heading channel | gyro 16.87% → onset-calibrated compass **7.22%** (655 windows) |
| Edge engine | **19,682 Hz worst config = 98×** the 200 Hz requirement |
| GNSS+INS fusion | **1.07× — a wash** (classical LC-EKF, not AI-based) |
| Our own bug | a unit error inflating every drift figure **3.6×**, found and fixed by us |

**Rules:** never state a number not in the registry. Never claim we beat the 10%
bar. Never resurrect the confidence radius — its spread correlates **−0.23** with
real error, so it is deliberately gated off.

---

## 4. Honest scorecard against the problem statement

| PS requirement | Status |
|---|---|
| In-vehicle alignment & calibration | 🟡 built; online alignment measured a **wash** (32%→32%); pitch/roll good, yaw-to-vehicle open |
| AI speed & vibration filter | ✅ frequency-decoupled by design — **matches the requirement architecturally**. Loses to hold-last-speed 23/23 per-window; ~8% better closed-loop |
| Map-matching + NHC + kinematics | ✅ **strongest deliverable** — HMM (Newson-Krumm, cited) + NHC + map-in-loop 2.02× |
| **AI-based GNSS+INS fusion** | ❌ **biggest gap** — classical LC-EKF at 1.07×. Dataset has no pseudoranges, so true tight coupling is impossible here |
| Seamless handover, both directions | ✅ **100 ms** measured across 15/15 events |
| Real-time nav interface | 🟡 built; marker smoothing is the weak spot and is graded |
| Magnetometer as an input | 🟡 read and fused in `SimpleIns`; **did not transfer to closed-loop map-in-loop** on a 3-window smoke test |
| DR drift < 10% | ❌ at **16.77%** — say this first, before a judge finds it |
| 10 Hz phone / 200 Hz edge | ✅ exceeded — 98× worst case |
| Works with external IMU (edge) | ✅ shared C++ core → JNI + WASM + headless daemon |
| Position plot from IO-VNBD | ✅ `figures/trajectory_overlay.png` + live engine view |

---

## 5. What the last session changed (UNCOMMITTED — 55 files, +3572/−1239)

**Product shell, deliberately, not the estimator.** The instruction was: treat the
estimator as a replaceable engine, ship the car body so a better engine drops in.

- **Android:** tabs cut to DRIVE + SETTINGS; one-tap Demo Mode; theme preference
  actually wired; km/h honoured; local guest profile (no cloud auth); in-app QR
  pairing (`pair/` package, `coast://pair`, store-and-forward queue); Vehicle
  Check screen; `GraphPfEngine` — a **JNI-shaped hole** for a native map-PF that
  falls back to FREE-DR when the `.so` is absent.
- **Console:** operator cookie gates fleet/pair/demo/train; `/pair`, `/ingest`,
  `/api/health`, `/static/*` stay public; world map JS; UI reloads from disk and
  cache-busts statics (an old process had been serving stale HTML for hours).
- **One demo contract** — `web/static/uk_demo_manifest.json` + `web/demo_contract.py`
  so Fleet, Engine and the APK all use the same clip and the same outage window
  [20, 80] s, with **GNSS → IDR → GNSS** in both directions.
- **New smoke experiments** (small n — see §6): `mapfilter_compass`,
  `gnss_ins_fusion_learned`, `transition_adaptive`.
- **New:** `tests/` (14 pass), `lab/models/results/leaderboard.md`,
  `nll_diagnosis/`, `lab/stress/results/traces/`, `site/`.

### Four launch-crash bugs fixed (verified present)
1. **Splash NPE** — `SplashScreenView.getIconView()` is `@Nullable` but
   core-splashscreen asserts non-null; it throws inside the platform's exit
   callback on the first frame, on ROMs we cannot test. Now `runCatching`, with
   `provider.remove()` as the fallback.
2. **MapLibre native init unguarded** — `abiFilters` ships arm64/armv7 only, so on
   an x86 emulator `libmaplibre.so` is absent → `UnsatisfiedLinkError` on the
   default tab. Now probed once, falls back to the Canvas map.
3. **Bundled tiles always beat live tiles** — the pack only covers Coventry, so
   any live drive elsewhere got a dark rectangle with no streets and no error.
   Now bounds-checked.
4. **`onTimeout` wrong overload** — Android 15's `dataSync` budget calls the
   two-argument form. Both are now overridden.

---

## 6. Traps — things that look true and are not

- **The new experiment results are SMOKE runs, not protocol runs.**
  `mapfilter_compass` is **n=3 windows** and says compass made map-in-loop
  *worse* (606 m vs 328 m). `gnss_ins_fusion_learned` is **n=2**. Neither is
  conclusive; neither may be quoted. `transition_adaptive` (15 drives, 15 events)
  is the one solid new result and it confirms the 100 ms figure.
- **The heading win has not transferred.** Compass cuts the *heading channel* from
  16.87% → 7.22%, but that is heading in isolation. It has **not** been shown to
  improve end-to-end map-in-loop.
- **The NLL head inflates variance.** `nll_diagnosis` confirms the signature —
  loss fell while held-out RMSE rose (5.238 → 5.390). Likely why the confidence
  signal is broken.
- **2.02× is lab Python, not the phone.** The phone runs `SimpleIns` + ONNX speed;
  the map-PF slot on device is empty.
- **The shipped ONNX is a placeholder drop-in**, re-exported at 40 epochs. Same
  tensor contract; not a benchmark win.
- **Windows PowerShell has no `&&`.** Use separate lines or `;`. This has cost a
  build cycle already.
- **Gradle works on the user's machine** (`BUILD SUCCESSFUL in 3m 21s`). It fails
  only inside the assistant's sandbox, which cannot open a loopback socket.
  `tools/package_apk.py` exists as a fallback but is **not** the standard path —
  `./gradlew assembleStandardRelease` is.
- **`android/gradlew` (POSIX) is broken** — `DEFAULT_JVM_OPTS` expands unquoted.
  Use `gradlew.bat` on Windows.

---

## 7. Verification — all currently green

```bash
python tools/verify_claims.py          # 20/20 traced to measured files
python web/test_console_routes.py      # all routes, incl. auth gating
python -m pytest tests/ -q             # 14 passed
cd android
./gradlew testStandardDebugUnitTest
./gradlew assembleStandardRelease
```

---

## 8. Where this should go next

Ordered by value, honestly assessed.

1. **Promote the smoke experiments to full protocol.** `mapfilter_compass` at
   n=3 is the difference between "compass helps end-to-end" and "compass hurts".
   Run all 43 outages. This is the single highest-information action available,
   and it may move the 2.02× headline — if it does, report the new number with
   its full protocol, never overwrite quietly.
2. **Close the AI-fusion gap.** The PS asks for an *AI-based* GNSS+INS fusion and
   ours is classical at 1.07×. A learned trust schedule between AI-speed, gyro,
   compass and map, scored on the same 43 outages. A measured negative here is
   still a real answer to the requirement.
3. **Marker smoothing on the phone.** A 10 Hz fix driving a marker directly
   teleports; the PS grades "smooth, uninterrupted vehicle icon". Interpolate and
   drive at 60 fps. Highest perceived-quality-per-line change in the app.
4. **Device test the APK.** It has never run a real field drive. That is the
   largest single unknown in the project.
5. **Second dataset.** Everything is IO-VNBD. One independent public log would
   turn "validated on the given dataset" into "generalises".
6. **Deploy `site/`** to Cloudflare Pages on a subdomain, with the APK on GitHub
   Releases (2 GB per-file limit; Cloudflare Pages caps files at 25 MiB).

**Deliberately not doing:** chasing the <10% bar by tuning; scraping Google Maps
tiles (violates their No Scraping clause, and the PS names OpenStreetMap anyway —
OSM is compliance, not compromise).

---

## 9. The posture that has been working

Volunteer the gap before anyone finds it. We publish our own negative results —
the 0.98×, the 1.07×, the 55%, the 3.6× bug we found in our own pipeline — and
that is *why* the wins are believable. A registry containing only wins is a
registry nobody should trust. Keep it that way.
