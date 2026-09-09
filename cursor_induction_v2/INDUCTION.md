# COAST — Cursor Induction v2 (one prompt, ~1–2 h of work)

Paste this whole file into Cursor and let it run to completion on the `demo`
branch. It is ordered: **fix what makes the app feel broken FIRST**, then the UI,
then the live localhost system, then dataset stress-testing and research. One
feature per commit; end every commit message with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Claude reviews when done.

Reference docs in this folder: `RESEARCH_2025.md` (papers + our measured sources),
and repo `final_demo_pitch/FIELD_DATASETS.md` (datasets).

## PRIME DIRECTIVE
The manager opened the app and it felt broken: the red puck flies off while the
phone sits still, "Grant Location" says not-granted after granting, and the
navigation feels like a crappy product. **Your #1 job is that a person who picks
up the phone and moves feels it WORKING and TRUSTS it.** Correctness and feel
beat features. Do Block 1 before anything else.

## GROUND TRUTH — DO NOT TOUCH
- `android/app/src/main/assets/demo/iovnbd_demo.csv` (real IO-VNBD strip) and
  `android/app/src/main/assets/maps/demo_neighbourhood.mbtiles` (Coventry basemap).
- The estimator's numeric output on `LiveSensorSource` must not change except where
  Block 1 explicitly fixes a bug. Run the unit suite before/after.

## HONESTY (non-negotiable)
- Never fake a green. Live training must show REAL epochs/metrics; "better than
  baseline" must cite measured rows (`RESEARCH_2025.md` §C). Algorithm-contribution
  claims must be real ablations, not invented. No confidence radius (−0.23). If
  something can't be done honestly in time, ship the honest version + a note.

## FILE OWNERSHIP
UI: `ui/**`, `ui/theme/**`, `data/Prefs.kt`, `res/**`. Engine: `sensor/**`,
`nav/**`, `record/**`, `IdrBus.kt`. Web/localhost: `web/**`. Lab: `lab/**`.

---

# BLOCK 1 — MAKE IT FEEL LIKE IT WORKS (do first)

**1A. Ghost puck explodes on a still phone — ROOT CAUSE FOUND.**
`nav/NaiveGhostEstimator.kt` integrates the RAW accelerometer (`frame.ax, frame.ay`)
and only *assumes* gravity is on body-z. Any hand tilt leaks ~9.8 m/s² into the
horizontal axes → velocity explodes in ~1 s. Our lab "free-DR" baseline removes
gravity, so the ghost is currently more naive than the baseline we quote — and it
looks broken.
- Fix: remove gravity before integrating. Maintain a low-pass gravity estimate per
  axis (e.g. `g = 0.98*g + 0.02*a`, or consume `TYPE_LINEAR_ACCELERATION` if
  `LiveSensorSource` exposes it) and integrate `a − g`. Result: a still phone → the
  red puck drifts SLOWLY (bias/noise), it does not teleport.
- Also gate it: the ghost only renders in the **blackout/replay demo** and the
  **ZUPT tabletop** screen — NOT on a plain live Start. On a normal live drive the
  user should see one confident COAST puck, not a scary red one.
- Add a unit test: still-phone frames (gravity on z, small tilt) → ghost speed after
  10 s is bounded (e.g. < 8 m/s), not thousands.

**1B. "Grant Location" says not granted after granting — ROOT CAUSE FOUND.**
`ui/Permissions.kt::rememberPermissionGate()` checks `requiredPermissions()` =
location **+ POST_NOTIFICATIONS**. On Android 13+, granting location but not
notifications makes the gate report "not granted". Also the displayed
`LocationStatus` (from `IdrBus.location`) is not refreshed on grant.
- Fix: the location banner/button must check ONLY `locationPermissions()`.
  Keep notifications a separate ask at Start. After a grant result, immediately
  re-publish the real location status (call the service's `refreshLocationGate` /
  re-run the gate and `bus.publishLocation(...)`), so the UI flips to granted
  without needing a Start.
- Verify on a real Android 13+ device: grant location → banner clears immediately.

**1C. Prove live motion actually drives the estimate.**
Add a small, honest "motion" indicator on Drive: shows STILL vs MOVING from the live
IMU (speed threshold), and the current speed. Confirm the LIVE path (not just replay)
moves the COAST puck when you actually walk. The injection tests already prove the
pipeline; make sure `LiveSensorSource` → `SimpleIns` → puck is wired identically and
visibly responds within ~1 s of real movement.

**1D. Start-flow sanity.** Pressing Start with no motion must look calm: COAST puck
holds (ZUPT), HUD says WAITING/STILL, no wild movement. No NaN, no crash on rotate /
background / permission-deny.

---

# BLOCK 2 — UI OVERHAUL (proven design language)

The current UI reads like a lab tool. Rebuild the layout to feel like a real
navigation/ride app, using an established pattern — model it on **Google Maps /
Uber driver**: map-first, minimal chrome, one primary action.
- Map fills the screen (already fillMaxSize). Overlays only.
- Use a **Material 3 `BottomSheetScaffold`** with a drag handle: collapsed peek shows
  speed + mode + primary Start/Stop; expanded shows the diagnostics drawer.
- Top: a single status pill (GPS ↔ IDR) — the existing one, restyled, centered.
- Floating buttons (M3 `FloatingActionButton`): recenter, layers/basemap, blackout
  toggle (demo). Large tap targets, content descriptions.
- Settings / Sessions / Auth: card-based M3 lists, consistent spacing, one accent.
- Restrained palette (one accent `#00E0A4`; blue only for the GNSS track). No random
  colors, no cramped buttons. Consistent typography scale.
- Keep it a real, editable Compose implementation — do not screenshot a template.
  You may look at Material 3 Compose samples and the Now-in-Android repo for
  structure. Acceptance: a screenshot reads as a polished nav app at a glance.

---

# BLOCK 3 — LOCALHOST LIVE SYSTEM (backend + frontend + phone + live training)

One local web app the manager runs on the laptop to (a) watch the phone live and
(b) watch the model train live. Start with one command, e.g. `python -m web.coast_console`.

**3A. Backend** (FastAPI or Flask + a WebSocket/SSE channel; stdlib-only fallback OK):
- `POST /ingest` — the phone (tracker flavor) posts live position (already sending).
- `GET /feed` — latest phone frames.
- `POST /train` — launches the real training (`lab/models/run_speed_bakeoff.py` /
  `lab/demo`) as a subprocess and **streams every epoch's metrics live** (loss, RMSE,
  val, LR, elapsed) over the socket. No fake numbers — pipe the real stdout/metrics.
- `GET /metrics` — the committed baseline vs COAST numbers (from `RESEARCH_2025.md`
  §C source files) so the page can show "baseline 28% → COAST 17% → ISRO 10%".

**3B. Frontend** (dark, matches the app; plain JS + Chart.js from the CDN is fine):
- **Live map panel**: the phone's dot + trail (GNSS blue / IDR teal), same palette.
  "Streaming from phone over LAN" indicator.
- **Live training panel**: press **Train** in the browser (no terminal needed) →
  watch epochs tick and a **loss/RMSE curve animate down** in real time.
- **Improvement story panel** ("why are we better"): a small honest **algorithm
  ledger** — a table of ablations showing what each component contributes to the
  measured result (free DR 28% → + map-in-loop 17% (2.02×); perfect-gyro-still-fails
  55% as the reason). Pull from the measured summary.md files; label each row with its
  source. Do NOT invent contributions.
- On finish, show the three figures (`figures/`) inline.

**3C. Honesty guard**: the browser Train is the SAME code as the terminal train; the
live curve is the real loss; the "better than baseline" panel cites files. If the
live quick-run can't reproduce the full 2.02×, label it "fast re-run" and cite the
full run — same rule as `lab.demo`.

---

# BLOCK 4 — BIGGER / REAL DATASET STRESS TEST

The demo data is one UK drive. Add a harness to stress the estimator on a larger,
independent dataset and report metrics.
- Build `lab/stress/run_dataset_stress.py <dataset_dir> --adapter <name>` that runs
  free-DR vs map-in-loop (or at least drift + CDF + pass-rate) and writes
  `lab/stress/results/dataset_stress/<name>/summary.md` + a CDF figure.
- Add `lab/eval/adapters/` with a column-mapping adapter pattern (like the IO-VNBD
  demo-strip mapping) so any dataset's columns → our session schema.
- **Data logistics (tell the manager in the report):** the pipeline is LOCAL, so the
  best path is: manager downloads one dataset locally, drops it under `data/field/`,
  and this harness scores it. Kaggle notebooks would fork the pipeline — avoid.
  Recommended first pick: the Kaggle **motorcycle-rider smartphone sensors** set
  (two-wheeler, our differentiator) or **IEEE DataPort Smartphone IMU+GPS**
  (multi-mode, GPS truth). See `final_demo_pitch/FIELD_DATASETS.md`.
- Write the adapter + a tiny synthetic fixture so the harness runs green now; when the
  manager provides the real download, it scores for real.

---

# BLOCK 5 — RESEARCH ENHANCEMENTS (measured, from RESEARCH_2025.md)

Do the top item fully; stub the rest with honest notes.
- **Mount-invariant speed model (EqNIO-style)**: add gravity-axis canonicalization to
  the AVNet input and MEASURE per-window + closed-loop vs current
  (`lab/models/results/...summary.md`). Report the real delta (could be a wash — say so).
- Leave `RESEARCH_2025.md` §D items 2–4 as documented backlog with the paper links.
- Update the deck's References slide content bundle (`final_demo_pitch/ppt_assets`) to
  cite the shared-bike GNSS-blocked paper + EqNIO + neural-augmented-KF.

---

# ACCEPTANCE + REPORT
When done, report a table: each block/item = done / done-with-limitation / not-done,
with file pointers and measured summary.md paths. Confirm: unit suite green;
still-phone ghost is bounded; location grant flips the banner immediately on a real
device; `python -m web.coast_console` serves the live phone map + live training curve;
dataset harness runs; no faked numbers; demo assets untouched. Then stop — Claude reviews.
