# 08 — Execution Order + Acceptance

**For Cursor.** Build in this exact order. **Do not start a P1 item until every
P0 item is green.** After each item, run the stated acceptance check; if it
fails, fix before moving on. Commit after each item with a clear message (do NOT
squash). Claude reviews after the P0 block and again after P1.

---

## Ground rules

- Branch: work on `demo` (or a `demo-build` branch off it). One feature per commit.
- **File ownership (to avoid two-agent conflicts if work is parallelized):**
  - UI owner: `ui/**`, `ui/theme/**`, `data/Prefs.kt`, `res/**`.
  - Engine/demo owner: `sensor/**`, `nav/**`, `record/**`, `IdrBus.kt`,
    `IdrApplication.kt`, `test/**`.
  - Lab owner: `lab/**`, `figures/**`, `Makefile`/`demo.py`.
  - Shared read: `IdrBus` state contracts — engine owner *adds* flows, UI owner
    *reads* them. Agree the flow names first (listed in files 04/05).
- **Never fake a GREEN.** If a spec can't be met honestly by Friday, mark it done
  with the honest limitation and tell Claude. See `00_READ_ME_FIRST.md` honesty rules.
- Commit attribution: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Build order

### Block P0 (must all be green before any P1)

| # | Item | Spec | Acceptance check |
|---|---|---|---|
| 1 | Full-screen map (kill 300 dp box) | `04` P0-1 | Map fills screen on device/emulator; HUD floats over it |
| 2 | Uber-black theme + dark basemap | `04` P0-2 | Screenshot reads as dark ride-map; blue only on GNSS track |
| 3 | HUD pill + bottom sheet (GPS↔IDR) | `04` P0-3 | Pill flips GNSS→amber IDR on blackout; no uncertainty radius drawn |
| 4 | `SensorSource` refactor (Live + Replay) | `05` P0-1 | Full test suite identical results on `LiveSensorSource`; replay emits at 10 Hz |
| 5 | Blackout toggle + bundled drive assets | `05` P0-1 | Airplane-mode ON: full blackout demo runs from assets, dot follows road |
| 6 | Offline mbtiles basemap | `04` P0-4 | Airplane-mode ON: basemap present, not blank |
| 7 | Stability hardening (NaN/ONNX/lifecycle/perm) | `05` P0-2 | Rotation, screen-off, denied-permission, ONNX-fail: no crash; tests added |
| 8 | Sensor-injection + loop-closure tests | `05` P0-3 | Left/right yaw moves estimate correct way; still→no drift; all tests green |
| 9 | `lab.demo` one-command training + figures | `06` P0-1,2 | ≤90 s on RTX 5050; writes `figures/{trajectory_overlay,cdf_error,drift_comparison}.png`; reproducible |
| 10 | Reference figures committed as fallback | `06` P0-1 | `figures/_reference/` has identical known-good copies |
| 11 | PPT drafted from `03_PPT_SPEC.md` | `03` | 10 slides, official template, numbers match `01` §D |
| 12 | Pre-recorded backup demo video | `01` §F | 60–90 s screen capture of the blackout demo + live training |

**→ Claude review gate 1:** Claude verifies numbers, honesty (no fake passes, no
confidence radius), test pass, and that the blackout demo is the real code path.

### Block P1 (only after P0 green)

| # | Item | Spec | Acceptance check |
|---|---|---|---|
| 13 | Ghost car (naive red puck) | `05` P1-1 | Real naive integrator diverges off-road on same input; labelled |
| 14 | Settings screen | `04` P1-1 | Vehicle/map/demo/privacy toggles persist via `Prefs` |
| 15 | Sessions/history | `04` P1-2 | Past sessions list + per-session track; last-location card |
| 16 | Login/sign-out stub | `04` P1-3 | Guest default; local-only name; zero network added |
| 17 | Phone-tracker flavor + laptop page | `07` | `tracker` flavor adds INTERNET; `standard` stays network-free; live dot over LAN |
| 18 | ZUPT tabletop mode | `05` P1-2 | Still phone: naive drifts, COAST holds 0.00 m/s, side by side |

**→ Claude review gate 2:** Claude verifies F8 `standard` flavor still has no
INTERNET permission, ghost car is a real integrator, and restyles/ hardens as needed.

### Block P2 (AFTER Friday — for the 30 Sep finals)

19. GNSS+INS tight fusion · 20. Online alignment engine · 21. Field scooter
loop-closure logs · 22. On-phone measured latency · 23. Dynamic-alignment
tabletop (if not honestly ready for P1).

---

## Definition of done for Friday (the minimum that wins)

- [ ] PPT (10 slides) in official template, numbers verbatim from `01` §D.
- [ ] APK (debug, arm64) installs and opens to a full-screen dark map.
- [ ] Blackout demo runs end-to-end with wifi OFF, from bundled assets.
- [ ] `python -m lab.demo` trains + writes 3 figures in ≤90 s, reproducibly.
- [ ] Sensor-injection test proves the pipeline moves on real input.
- [ ] Pre-recorded backup video exists.
- [ ] Q&A bank rehearsed; every member owns a part (F10).
- [ ] No fabricated number anywhere; negative result (55%) is on a slide.

If all of the above are true, we walk in with a Round-1 deck that scores F1–F8
on defensible depth and a Round-2 demo that makes it believable. That is the bar.

---

## What Claude does after Cursor

1. Read the diff of each P0 commit; verify acceptance checks really pass (not
   just claimed).
2. Fix anything physics- or honesty-critical (unit bugs, fake passes, broken
   confidence display, estimator behaviour changes under the `SensorSource`
   refactor).
3. Wire the exact measured numbers into PPT/figures; confirm consistency.
4. Harden edge cases the tests missed.
5. Report what's real vs. still-next, with file pointers — including failures.
