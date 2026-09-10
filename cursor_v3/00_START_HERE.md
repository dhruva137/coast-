# COAST v3 — Cursor build programme

**Paste this file into Cursor first. Read `01_THE_ENGINE.md` before writing any
code — you cannot build this well without understanding what it does.**

Branch: `demo`. One feature per commit. End every commit message with:
`Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`

---

## What you are building

COAST is a smartphone navigation system that keeps working when GPS dies
(tunnels, underpasses, urban canyons, jamming). It is an entry for Smart India
Hackathon 2026, problem statement 26168, from ISRO / Dept. of Space.

There are three surfaces:

| Surface | What it is | State |
|---|---|---|
| **COAST Navigator** | The Android app. The actual product. | Built, needs polish + new features |
| **COAST Command** | A laptop web console: fleet tracking, live model training, engine telemetry, evidence | Built as a skeleton — **this programme rebuilds most of it** |
| **The lab** | Python training/benchmark harness | Strong; needs a real experiment framework |

**The console is what judges watch on a projector.** Right now it is a
functional skeleton that looks like a developer tool. It needs to look like a
product an operations team uses.

---

## The nine phases

Sequential. Do not start a phase until the previous one's acceptance list is
green. Inside a phase, the numbered work items are independent — **launch them
as parallel subagents.**

| # | Phase | File | Roughly |
|---|---|---|---|
| 1 | Shell, identity, login, design system | `PHASE_1_SHELL.md` | The console stops looking like a demo |
| 2 | Fleet: real maps, sessions, device registry | `PHASE_2_FLEET.md` | Tracks on real roads, not a bare grid |
| 3 | Engine visualisation | `PHASE_3_ENGINE_VIZ.md` | The estimator, *alive*, on screen |
| 4 | Training lab + model design framework | `PHASE_4_TRAINING.md` | Real architecture search, real ablations |
| 5 | Android app upgrades | `PHASE_5_APK.md` | Pairing, splash, Vehicle Check, smooth marker |
| 6 | Security hardening | `PHASE_6_SECURITY.md` | It survives a hostile look |
| 7 | F1–F10 criteria sweep | `PHASE_7_CRITERIA.md` | Every scoring criterion has an artifact |
| 8 | Demo readiness | `PHASE_8_DEMO.md` | The 10-minute run, rehearsed, with fallbacks |
| 9 | Final audit | `PHASE_9_AUDIT.md` | Adversarial pass, then stop |

---

## Non-negotiable rules

These are not style preferences. Breaking one of them can lose the competition.

### 1. Never fabricate a number
Not on a slide, not in the app, not in the console, not in a `summary.md`, not
in a comment. If a value is not the output of a real computation on real data,
it does not get written down as a result.

`python tools/verify_claims.py` re-derives all 20 registered claims from their
measured source files and fails on any claim-shaped number in a pitch surface
that no file produced. **It must exit 0 at the end of every phase.**

### 2. Never fake a green
No simulated progress, no interpolated loss curves, no `Math.random()` standing
in for a metric, no `except: return <plausible value>`. If a computation fails,
the UI says it failed and shows the real error.

This has already been enforced once: the metrics ledger used to fall back to
hardcoded numbers when its results file was missing, so deleting the file still
showed green figures. That was fixed. Do not reintroduce the pattern anywhere.

### 3. Placeholder data must be unmistakable
The fleet currently shows "Judge-1 / Judge-2". If those appear with no phone
actually paired, a judge reads the whole console as fake — and they are right to.
**Any non-live data must carry a permanent on-screen badge in the same visual
layer as the data**, so no screenshot can crop it off. Prefer designed empty
states over seeded fake data. See `PHASE_2_FLEET.md` §Empty states.

### 4. Do not touch the demo ground truth
`android/app/src/main/assets/demo/iovnbd_demo.csv` and
`android/app/src/main/assets/maps/demo_neighbourhood.mbtiles`.

### 5. The headline numbers are frozen
2.02× lower median position error · perfect gyro still fails 55% · post-hoc
snapping 0.98× · free-DR 17%/10% arms · edge worst case 19,682 Hz (98×) ·
100 ms handover · 3.6× unit bug · heading: gyro 16.87% → compass 7.22%.
If your work changes any of these, **stop and report** — do not silently update.

### 6. Offline is a hard requirement
The venue wifi may be dead. Every surface must cold-start and run with no
network: no CDN, no web fonts, no remote tiles at demo time. Anything hosted is
a bonus surface, never the critical path.

### 7. Ship the honest partial
If something cannot be finished honestly in the time available, ship the honest
version plus a written limitation. A documented gap scores far better than a
fabricated completion — and this team has already won credibility by publishing
its own negative results.

---

## How to run a phase

1. Read the phase file end to end.
2. Read `01_THE_ENGINE.md` if you have not.
3. Launch the phase's work items as **parallel subagents**, one per item. They
   own disjoint files — the ownership table is in each phase file.
4. When all return: run the gate.
5. Report the phase table (below), then start the next phase.

### The gate — after every phase, all four must pass

```bash
python tools/verify_claims.py          # exit 0
python web/test_console_routes.py      # all routes OK
cd android && ./gradlew testStandardDebugUnitTest
cd android && ./gradlew assembleStandardRelease
```

### Report format

| item | status | files | notes |
|---|---|---|---|
| 1.1 | done / done-with-limitation / not-done | paths | measured result paths, or why not |

---

## File ownership (keeps parallel subagents from colliding)

| Domain | Paths |
|---|---|
| Console UI | `web/console_ui.py`, `web/static/**` |
| Console backend | `web/coast_console.py`, `web/pairing.py`, `web/auth.py` |
| Console tests | `web/test_*.py` |
| Android UI | `android/app/src/main/java/in/sih26168/idr/ui/**`, `res/**` |
| Android engine | `.../sensor/**`, `.../nav/**`, `.../record/**` |
| C++ core | `core/cpp/**` |
| Lab / models | `lab/models/**` |
| Lab / benchmarks | `lab/stress/**`, `lab/eval/**` |
| Tooling | `tools/**` |
| **Strategy docs** | `cursor_v3/**`, `win_tuning/**`, `design_v3/**` — **read-only. Never edit.** |

---

## Where things already are

Read these before asking what exists:

- `design_v3/00_DESIGN_THESIS.md` — why the console and the app are opposite
  design problems, and the layered-communication doctrine. **Binding.**
- `design_v3/01_PS_COMPLIANCE_AUDIT.md` — every problem-statement requirement vs
  what is actually built. Your scorecard.
- `win_tuning/F1_*.md` … `F10_*.md` — what each judging criterion rewards.
- `win_tuning/CLAIMS.json` — the 20 registered claims, generated, do not hand-edit.
- `lab/stress/results/*/summary.md` — every measured result, including the
  negative ones.
- `core/cpp/apps/README.md` — the C++ engine's own benchmark record.
