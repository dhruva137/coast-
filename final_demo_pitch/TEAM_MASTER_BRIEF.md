# COAST — Team Master Brief (read this first)

**One document that tells the whole team what we're building, where we stand, and
how to present it.** SIH 2026, Problem Statement **26168**, ISRO / Dept. of Space —
"AI-ML based Intelligent Dead Reckoning system for seamless navigation."

**Precursor:** Friday 11 Sep 2026. Round 1 = PPT (criteria F1–F8). Round 2 =
live pitch + Q&A + teamwork (F9–F10), all 6 members present. Dress: white shirt,
black pants.

---

## 1. What we're building, in one paragraph

When your phone enters a tunnel, underpass, metro, multi-level car park, or a
GNSS-jammed area, consumer GPS dies and the map freezes. **COAST keeps the dot
moving** using only the phone's own accelerometer and gyroscope — no internet, no
extra hardware — and snaps the estimate onto an OpenStreetMap road graph so the
error cannot grow without bound. Most vehicles on Indian roads (trucks, older
cars, 200M+ two-wheelers) have no built-in inertial navigation; the phone is the
nav system. It's the same inertial-navigation discipline ISRO flies on launch
vehicles, on a ₹15,000 phone.

**Say the name like this:** COAST — "when GPS dies, you coast on sensors."

---

## 2. The numbers — MEMORISE THESE (all measured, all defensible)

Every number has a source file a judge can open. **Never say a number not on this
list.**

| Claim | Number | Source file |
|---|---|---|
| Our headline: map-in-loop vs naive DR | **2.02× lower median position error** (252.66 m → 125.20 m; 43 real GNSS outages, car CAN truth). Median drift 27.6% → 16.8% | `lab/stress/results/mapfilter/summary.md` |
| The negative result we volunteer | **A perfect gyro still fails 55%** of 60-s segments | `lab/stress/results/heading_ablation/summary.md` |
| Naive DR baseline (what we beat) | **17%** short-arm / **10%** tunnel-arm pass; **28%** median drift vs our **17%** | `lab/stress/results/isro_benchmark/summary.md` |
| Edge engine throughput | **19,682 Hz** worst measured case (180-particle PF, 100% GNSS-denied) → **98×** the 200 Hz requirement | `core/cpp/apps/README.md` |
| GNSS→DR handover | **100 ms** | `lab/stress/results/` |
| The bug we caught in our OWN pipeline | a unit error inflating every drift **3.6×** | `docs/AUDIT_AND_PLAN.md` |
| Offline OSM road graph | **3,271 km / 35,631 edges**, no key, no billing | `maps/` |

**Do NOT claim:** that we already clear the hardest tunnel bar end-to-end; ZUPT
drift reduction; first-ever phone INS; beating a named paper; any live road drive
we didn't run; a confidence radius (our uncertainty signal is broken, −0.23).

**The one-line honest pitch:** *"Naive dead-reckoning fails even with a perfect
gyro — so a better sensor isn't the answer. We put the road map inside the filter
loop and got 2× better on real data. We don't yet clear the hardest bar
end-to-end; that's our stated next work."* Volunteering the gap is what makes
judges believe the rest.

---

## 3. The PPT (Round 1 decider) — content per slide

Official SIH IDEA format, **6 slides**, diagram-led. File:
`final_demo_pitch/ppt_assets/COAST_SIH2026_IDEA.pptx`. Diagrams in
`ppt_assets/diagrams/`. Fill Team ID / Team Name; verify Theme on the portal.

1. **Title** — PS 26168 · title · ISRO / Dept. of Space · Theme (Space Technology,
   verify) · Category Software · Team ID/Name. Tagline: *when GPS dies, you coast
   on sensors.*
2. **The Idea** — problem (GPS dies, map freezes) → idea (phone-only IDR, no
   hardware) → **innovation: map INSIDE the filter loop** → the 55% negative
   result. Diagram: `concept.png` (naive sprays off-road vs COAST hugs it).
3. **Technical Approach** — stack (Kotlin/Compose · MapLibre+OSM · ONNX · C++
   core) + methods (AI speed · gyro evidence · ZUPT · map-in-loop particle filter ·
   HMM map-matching). Diagram: `architecture.png` (sensors → filter → position;
   shared C++ core → 10 Hz phone + 200 Hz edge).
4. **Feasibility & Viability** — feasible today (any phone, offline, edge 98× the
   need); risk (heading drift; hardest bar not cleared) → strategy (map-in-loop
   done → alignment → calibrated uncertainty → field logs). Diagram: `results.png`
   (2.02× · 55% · 17/10% · 120k Hz + the 3.6× bug story).
5. **Impact & Benefits** — who (200M+ two-wheelers, trucks, older cars; logistics,
   ambulances, metro) · social/economic/environmental · strategic (jamming =
   sovereignty; NavIC; ISRO).
6. **Research & References** — IO-VNBD · Newson-Krumm 2009 · TLIO/RoNIN/TinyOdom/
   AI-IMU-DR · **EqNIO, shared-bike GNSS-blocked, neural-augmented KF (2025)** ·
   our measured result files. (See `cursor_induction_v2/RESEARCH_2025.md`.)

---

## 4. The live demo (Round 2) — the 3-act script

1. **Act 1 — the handoff (the whole pitch, 60 s).** Judge holds the phone. Turn
   location off in front of them (or hit "Simulate GNSS Blackout"). The dot keeps
   moving on the map. If walking is possible: walk out and back to a floor tile and
   show closure error. *This is the demo; everything else is support.*
2. **Act 2 — the blackout replay** — a real IO-VNBD drive (Coventry, UK) streamed
   through the real estimator on the phone, on the real roads, with the basemap
   present in airplane mode. Labelled "REPLAY — real dataset, real estimator."
3. **Act 3 — the laptop proof** — `python -m lab.demo` (or the localhost console)
   trains the model live in ~33 s and regenerates the 3 figures; show the 2.02×.
4. **The ask** — 200M+ two-wheelers, any phone, zero extra hardware.

Keep a **pre-recorded backup video** (rules allow it if the live demo fails).

---

## 5. Where we stand — done / in progress / left

### Done and verified ✅
- **Laptop science** — 2.02× map-in-loop, 55% negative result, edge engine 120k Hz,
  honest washes on GNSS+INS fusion (1.07×), alignment (32%), speed model. All measured.
- **Android app builds** — full-screen dark map, blackout replay on the **real UK
  drive + matching basemap**, ghost car, ZUPT tabletop, settings/sessions/auth-stub,
  tracker flavor, barometer detector, on-phone latency. Unit suite green; all
  flavors + release assemble.
- **Live training** — `python -m lab.demo` runs in ~33 s, real GPU training, writes
  the 3 screening figures. Honest CDF (we're not at 10 m yet — shown truthfully).
- **PPT** — official-format deck + 3 clean diagrams.
- **Privacy (F8)** — no user data leaves the device; basemap-off = zero network.

### In progress (Cursor is executing `cursor_induction_v2/INDUCTION.md`) 🔧
- **2 bugs found by the manager, root-caused, being fixed:** (1) red ghost puck flew
  off on a still phone (integrated gravity — fix: remove gravity); (2) "Grant
  Location" said not-granted after granting (bundled with notifications — fix: split).
- **UI overhaul** to a real Google-Maps/Uber layout (bottom sheet, FABs, one accent).
- **Localhost live console** — one web app showing the phone's live dot AND a
  browser Train button that streams real epochs + an animated loss curve + an honest
  "why we beat the baseline" ledger.
- **Dataset adapter harness (synthetic plumbing fixture)** + adapter pattern.
- **Research enhancement** — mount-invariant speed model (EqNIO-style), measured.

### Left (human / next) ⏳
- Fill PPT Team ID / Team Name; verify Theme.
- Record the 60–90 s backup demo video (storyboard: `final_demo_pitch/DEMO_VIDEO_SCRIPT.md`).
- Download ONE field dataset locally into `data/field/` (see `FIELD_DATASETS.md`) →
  we score it for a real independent number.
- Re-test the fixed APK on a phone; shrink to arm64 for transfer.
- Rehearse Q&A; assign per-member ownership (below).
- (For 30 Sep finals) on-device field drive, GNSS+INS tight fusion, alignment engine.

**Honest overall:** the *science is proven on real data*; the *app is fully built
but has never run a real field drive*, and two feel-bugs are being fixed. Round 1
(PPT) is in strong shape; Round 2 (live demo) rests on the blackout replay + live
training, both working.

---

## 6. Team guide — who owns what (fill names)

Every member must be able to defend their area in Round 2 (F10 is scored on visible
shared ownership).

| Area | Owns | Must be able to answer |
|---|---|---|
| **Estimator / C++ core** | map-in-loop filter, edge engine | why map-in-loop, the 55% result, 120k Hz |
| **Android app / UI** | the phone app, the demo | run the blackout demo, explain the HUD |
| **ML / speed model** | AVNet-tiny, ONNX, training | leave-file-out, why the model is a wash & why that's fine |
| **Maps / OSM** | road graph, offline tiles | why OSM not Google, offline story |
| **Evaluation / benchmark** | the measured numbers | every number in §2 + its source file |
| **Pitch / docs / demo ops** | PPT, video, localhost console | the 3-act script, the honest framing |

---

## 7. The honesty rules (these WIN at an ISRO-adjacent round)

1. Only measured numbers (§2). 2. Volunteer the 55% negative result. 3. Own what's
not done. 4. The blackout demo is real data through the real estimator — say
"replay." 5. No confidence radius. 6. If a judge points at any line of code, we can
defend it — including our failures. A defensible negative result beats a polished
lie, every time.

---

## 8. Where everything lives

| Need | Path |
|---|---|
| This brief | `final_demo_pitch/TEAM_MASTER_BRIEF.md` |
| The deck + diagrams | `final_demo_pitch/ppt_assets/` |
| Slide-by-slide spec + Q&A | `final_demo_pitch/03_PPT_SPEC.md`, `docs/JUDGE_CROSS_EXAM.md` |
| Decision layer / strategy | `final_demo_pitch/01_DECISION_LAYER.md` |
| Current build tasks (Cursor) | `cursor_induction_v2/INDUCTION.md` |
| 2025 research + baseline sources | `cursor_induction_v2/RESEARCH_2025.md` |
| Field datasets | `final_demo_pitch/FIELD_DATASETS.md` |
| Live training + figures | `python -m lab.demo` → `figures/` |
| Video storyboard | `final_demo_pitch/DEMO_VIDEO_SCRIPT.md` |
| Deep project state | `docs/PROJECT_STATE.md` |
