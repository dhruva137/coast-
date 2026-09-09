# Phase 0 addendum — BLOCKING FIXES from the honesty audit

An independent read-only audit of the recent Cursor commits was run on 9 Sep
2026. **Headline: no fabricated data was found.** The Train button launches a
real subprocess and plots only parsed stdout; every displayed metric traces to a
committed measured file; no `Math.random`, no simulated progress, no
sleep-and-emit; no secrets or hardcoded IPs.

But it found **six precision and labelling defects**. None is a lie. Every one of
them is something a technical judge could pull on, and the cost of being caught
mid-pitch is far higher than the cost of fixing them now.

**These fix tasks are part of Phase 0 and block every later phase.**

---

## FIX-1 — `2.02×` is attached to the wrong row  ← most important

**The defect.** `web/coast_console.py:735` renders
`f"{coast_drift:.0f}%  ({improvement_x:.2f}x vs free)"` on a row whose metric
label is `"median drift %"`. Same at `web/vite-train-api.ts:250`.

But the two ratios are different quantities:

| Quantity | Free DR | COAST | Ratio |
|---|---:|---:|---:|
| Median position error | 252.66 m | 125.20 m | **2.018×** ← this is our 2.02× |
| Median drift % | 27.58% | 16.77% | **1.645×** |

Rendering "17% (2.02× vs free)" invites the reading *"drift improved 2.02×"*,
which is **false**. `lab/stress/results/mapfilter/summary.md` states both
correctly and separately — it is the console's juxtaposition that breaks it.

**The fix.** Move `2.02×` onto a median-**error** row. The drift row shows
`27.58% → 16.77%` with no multiplier, or with `1.65×` if a multiplier is wanted.
The two numbers must never share a cell again.

**Propagate the precise wording everywhere** — deck, brief, app, console:

> **2.02× lower median position error** (252.66 m → 125.20 m) across 43 real
> GNSS outages. Median drift falls 27.6% → 16.8%.

Anywhere the deck currently says "2.02× map-in-loop vs naive DR" without naming
*which* quantity, add "median position error". This is a one-word fix that makes
the claim bulletproof.

## FIX-2 — Silent hardcoded fallback shows green numbers with no data

**The defect.** `web/coast_console.py:697-712` seeds `free_drift=27.6`,
`coast_drift=16.8`, `improvement_x=2.02`, `free_pass=8`, `pf_pass=17`,
`n_outages=43` **before** the `try` block. On `OSError`/`KeyError` it sets
`report_err` but keeps the literals. The `report_error` field is then never
rendered — the page JS (`coast_console.py:452-471`) and `TrainPanel.tsx:212-226`
read only `data.ledger` and `data.honesty`. Mirrored at
`web/vite-train-api.ts:206-235`.

Net effect: **delete the results file and the UI still shows identical green
numbers, still citing `lab/stress/results/mapfilter/summary.md` as the source.**

All six literals were verified to match `report.json` exactly, so nothing is
invented today. But the failure mode is a number presented with a provenance it
does not have — which is precisely the thing our whole posture rejects.

**The fix.** Delete the pre-seeded literals. On read failure, render an explicit
error state in the ledger panel: *"Could not read
`lab/stress/results/mapfilter/report.json` — no measured numbers to show."*
Showing nothing is correct. Showing a remembered number is not.

## FIX-3 — Docstring overclaims provenance

**The defect.** `lab/demo.py:13-14` states the headline numbers "*are read from
the committed decision-layer sources — never invented*". True for `2.02×`
(`_load_headline_numbers()`, `demo.py:59-69`). **Not** true for
`free_dr_short_arm_pct: 17` and `free_dr_tunnel_arm_pct: 10`, hardcoded at
`demo.py:71-72`. Same literals at `coast_console.py:753,761` and
`vite-train-api.ts:266`; `oracle_pass=84, oracle_n=186` at
`coast_console.py:718-719`.

All four match their measured files. Hardcoded-but-correct.

**The fix.** Either read them from
`lab/stress/results/isro_benchmark/summary.md` and
`heading_ablation/summary.md` like `2.02×` is read, or amend the docstring to say
exactly which values are read and which are pinned constants verified against
which file. Preferred: read them, so drift is impossible.

## FIX-4 — APK preview renders unlabelled plausible numbers inside the phone frame

**The defect.** `web/src/app/ApkPreview.tsx:23` hardcodes `"28"`/`"31"` km/h and
`"86"` m since fix; `PhoneMap.tsx:32-37` draws a fixed 3-point Bangalore line.
The disclaimer ("Sensors are faked here", `:44`) sits in the **side panel**, not
in the frame.

**A cropped screenshot of that frame reads as a live app.** If it ever reaches a
slide or a social post, we have published fabricated telemetry.

**The fix.** Put a permanent, unremovable **"MOCK — not live data"** badge
*inside* the phone frame, in the same visual layer as the numbers, so no crop can
separate them. Same rule as the replay demo's "REPLAY — real dataset, real
estimator" label.

## FIX-5 — Approximate-location grant does not clear the banner *(real bug)*

**The defect.** `android/.../ui/Permissions.kt:49-51` uses
`needed.all { … GRANTED }` over both `ACCESS_FINE_LOCATION` and
`ACCESS_COARSE_LOCATION`. If the user taps **"Approximate"** on the system
dialog, only COARSE is granted and the banner never clears — the same class of
bug as the original notifications defect, one layer down.

**The fix.** The banner should clear when **either** FINE or COARSE is granted
(`any` rather than `all`), and separately surface that precision is reduced if
only COARSE is present. Verify on a real Android 13+ device by choosing
"Approximate".

## FIX-6 — "Dataset stress harness" oversells a plumbing smoke test

**Not a dishonesty finding — the code is exemplary here.** The audit specifically
checked whether the synthetic fixture was rigged to make map-in-loop win, and
found the opposite: `generate.py:25-26` places the track *outside* the OSM bbox
deliberately, commented *"honest: map-in-loop needs independent OSM coverage; do
not invent it."* The harness correctly refuses to score map-in-loop
(`run_dataset_stress.py:196-203`) and the summary states it did not run rather
than inventing an improvement. The fixture is labelled SYNTHETIC in five places
and the result is a **FAIL** (0/1 pass, 20.92% drift).

**The residual issue is only the name.** It is one session of constant-speed,
constant-yaw-rate motion with an injected 0.015 rad/s bias — a plumbing smoke
test, not a stress test. Calling it a "dataset stress harness" in a pitch
oversells it.

**The fix.** Rename in all pitch-facing text to **"dataset adapter harness
(synthetic plumbing fixture)"**. It becomes a real stress test only when a
downloaded field dataset is scored through it. Until then it is evidence of good
engineering process, not evidence of performance — and it is genuinely worth
showing as the former.

**Related:** `web/_smoke_coast.py:26-27` asserts `"2.02" in row["display"]`,
which passes on the FIX-2 fallback and therefore cannot detect a missing results
file. After FIX-2, change it to assert the error state appears when the results
file is absent.

---

## Also worth doing (non-blocking)

- **Squash the duplicate commits.** `085aac8` and `ad8a023` carry identical
  messages; `ad8a023` is a 751-line rework. A judge browsing the log sees a
  duplicate.
- **The Block 5 commit message cherry-picks.** It cites "closed-loop −20 m
  median; mount-swap probe more stable" from a result whose own summary calls it
  a near-wash on 3 of 23 folds. The summary is honest; the commit message should
  match it. Amend the language in any pitch reference.
- **`vite.config.ts` binds `host: "::"`** — a LAN-exposed dev server with a
  `POST /api/train` that spawns Python. Fine on a demo laptop; know it before
  running it on venue wifi, and prefer `localhost` binding unless the phone
  actually needs to reach it.

---

## What the audit confirms we should be proud of

Put these in the pitch — they are unusually strong, and they are *earned*:

- **Live training is exactly what it claims.** Real `Popen(["-m","lab.demo"])`,
  real stdout parsing, real epochs, and `lab/demo.py:159-190` computes a genuine
  held-out RMSE per epoch — the second curve on the chart is measured, not fitted.
  On subprocess failure both backends emit an error and plot nothing.
- **Honesty is enforced in code, not just in documents.** `try_map_in_loop`
  returns three distinct refusal paths, each carrying an explicit `"honesty"`
  string. **Showing a judge code that refuses to score rather than guess is a
  stronger trust signal than any result.**
- **Our own falsification tests are committed and displayed when they fail.**
  `mapfilter/summary.md` records "helped 28 | hurt 15", a 26% correct-edge rate,
  and the −0.23 spread-error correlation with the note that a near-zero value
  makes the uncertainty "decorative and must not be shown to a user" — which is
  why the confidence radius is gated off.
- **The map graph carries a provenance guarantee.** `report.json` records
  `built_from_drive_data: false` — "no IO-VNBD trajectory, GNSS fix or CSV column
  was read while building this graph." That is a pre-emptive answer to
  "did you leak the test set into your map?", which is the sharpest question a
  machine-learning judge can ask.
- **Android is genuinely privacy-clean.** No analytics, no default network,
  `trackerOptIn=false`, no logging, no secrets, no hardcoded IPs.
- **The working tree is a rebrand, not a numbers change.** `figures/demo_run.json`
  headlines are byte-identical (2.018070842498746; 8→17 of 43; 27.58/16.77;
  17/10). Only `wall_seconds` 42.6→32.8 changed.

---

## Acceptance for this addendum

- [ ] FIX-1 — `2.02×` appears only on a median-**error** row; drift row carries
      no multiplier; wording updated in deck, brief, app, console
- [ ] FIX-2 — no pre-seeded literals; missing results file produces a visible
      error state, not numbers
- [ ] FIX-3 — 17% / 10% / 84 / 186 read from source, or docstring corrected
- [ ] FIX-4 — "MOCK — not live data" badge inside the phone frame
- [ ] FIX-5 — banner clears on Approximate-only grant; verified on device
- [ ] FIX-6 — renamed to "dataset adapter harness (synthetic plumbing fixture)"
      in all pitch-facing text; smoke test updated
- [ ] `python tools/verify_claims.py` green after all of the above
