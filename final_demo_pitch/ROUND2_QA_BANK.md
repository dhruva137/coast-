# Round 2 — Q&A Bank (tiered A / B)

**Source:** `win_tuning/F9_PRESENTATION.md` §C  
**Numbers:** `win_tuning/CLAIMS.json` + Phase 0 FIX-1 wording only.

Fill the same six names as `ROUND2_SCRIPT.md` / `ROUND2_TEAMWORK_PLAYBOOK.md`.

| Role | Placeholder | Real name |
|---|---|---|
| Team lead / pitch | `[NAME_LEAD]` | ________________ |
| Estimator / core | `[NAME_ESTIMATOR]` | ________________ |
| Android / product | `[NAME_ANDROID]` | ________________ |
| ML / speed model | `[NAME_ML]` | ________________ |
| Evaluation / data | `[NAME_EVAL]` | ________________ |
| Maps / systems | `[NAME_MAPS]` | ________________ |

---

## Hard rules (every member)

1. **Answer level matching.** Type A = non-specialist wording. Type B = specialist depth. Read the questioner, then pick a column. If they look lost mid-answer, drop to A immediately.
2. **No guessing.** If you don't know: *"I don't know — I'd measure it by X."* Scores higher than a confident wrong answer.
3. **Number discipline.** Say only the five memorised numbers (see playbook § Five-number drill). Anything else numeric → *"I'd have to check the exact figure — `[NAME_EVAL]` owns the benchmark."* Never estimate a number out loud.
4. **2.02× is median position error only** (252.66 m → 125.20 m). Drift is separate: 27.6% → 16.8%. Never merge those facts or put 2.02× on a drift row.
5. **Answer only what was asked.** Over-answering signals anxiety.
6. **Hand off to the domain owner.** *"That's `[NAME_X]`'s area."* Never answer inside someone else's domain. One voice at a time.
7. **Lead speaks least in Q&A.** Route; do not absorb.

---

## Domain routing (who takes the first word)

| Topic | Owner |
|---|---|
| What is this / why it matters / close | `[NAME_LEAD]` |
| Map-in-loop, particle filter, Kalman, 55%, 0.98×, along-track limit | `[NAME_ESTIMATOR]` |
| App screens, blackout demo, on-device behaviour | `[NAME_ANDROID]` |
| AVNet, ONNX, Train button, speed-model wash | `[NAME_ML]` |
| Any number provenance, linter, benchmark, unit-bug story | `[NAME_EVAL]` |
| OSM, offline, privacy, "did the map leak?" | `[NAME_MAPS]` |

---

## Tiered answers

### "Isn't this just map matching?"

| Type A | Type B |
|---|---|
| "Map matching cleans up a GPS trail after the fact. We use the map *while* estimating, so the position can never leave the road in the first place." | "Post-hoc snapping scores **0.98×** — it hurts, because you snap a drifted estimate confidently onto the wrong road. Our state space *is* the graph: (edge, offset along edge). Lateral divergence isn't suppressed, it's unrepresentable. Same map, opposite architecture — **0.98×** vs **2.02× lower median position error**." |

**Owner:** `[NAME_ESTIMATOR]`

---

### "How accurate is it?"

| Type A | Type B |
|---|---|
| "About twice as good as the standard approach on real drives — and more importantly, it stays on the right road." | "**2.02× lower median position error**: **252.66 m → 125.20 m** across **43** outages, CAN ground truth. Median drift **27.6% → 16.8%** (separate quantity — not the 2.02×). We don't yet clear the sub-10% tunnel bar end-to-end." |

**Owner:** `[NAME_ESTIMATOR]` (numbers confirmed by `[NAME_EVAL]` if challenged)

---

### "How long can it go without GPS?"

| Type A | Type B |
|---|---|
| "Short to medium outages — a tunnel, an underpass, a car park. Not a whole city." | "We're UDR-class — no wheel ticks — so we degrade faster than automotive ADR past about a minute. The map bounds lateral error indefinitely; along-track error still accumulates." |

**Owner:** `[NAME_ESTIMATOR]`

---

### "Does Google already do this?"

| Type A | Type B |
|---|---|
| "Their tunnel fix needs Bluetooth beacons physically installed in the tunnel. It's off by default and no Indian city is on the list. Ours needs nothing installed." | Same, plus: "It's a hardware-deployment answer, not an algorithmic one. It doesn't help outside instrumented tunnels." |

**Owner:** `[NAME_LEAD]` or `[NAME_MAPS]` (hand off if it turns into map/privacy)

---

### "Have real users used it?"

| Type A | Type B |
|---|---|
| "Not yet — you're the first person outside the team to hold it. That's why there's no login and no setup." | Same, plus: field drives are the top roadmap item. Honest: science is on recorded real-world data (IO-VNBD + CAN truth); the app has not yet run a live road drive with us. |

**Owner:** `[NAME_ANDROID]` / `[NAME_LEAD]`

---

### "How do I know the numbers are real?"

| Type A | Type B |
|---|---|
| "Watch this." *(run `python tools/verify_claims.py --demo-failure`)* | Plus: "The registry includes our failures — **1.07×** on GNSS+INS fusion, a wash on alignment (**32%** edge accuracy), our speed model losing to a naive hold (**0 of 23** folds). Nobody fabricating results fabricates those." |

**Owner:** `[NAME_EVAL]`

---

### "Did the map leak your test data?"

| Type A | Type B |
|---|---|
| "No — the map is independent public data." | "The graph build report records `built_from_drive_data: false`: no trajectory, GNSS fix, or CSV column from the drives was read while building it." |

**Owner:** `[NAME_MAPS]`

---

### "Why not a Kalman filter?"

| Type A | Type B |
|---|---|
| "At a junction you might be on either road. A Kalman filter has to pick one; ours keeps both until the motion decides." | "Multi-modal belief on a graph. A unimodal Gaussian collapses exactly at the branch point where the ambiguity matters most." |

**Owner:** `[NAME_ESTIMATOR]`

---

### "What about NavIC?"

| Type A | Type B |
|---|---|
| "NavIC is being expanded right now — more satellites are launching. Ours works even while that's happening, and works underground where no satellite reaches." | Respectful, paired with recovery — never a criticism of NavIC. Same framing as `win_tuning/RESEARCH_GLOBAL_CONTEXT.md` §0.1: complementary to satellite growth, not a competitor narrative. |

**Owner:** `[NAME_LEAD]` (route to `[NAME_ESTIMATOR]` if it becomes filter/technical)

---

### "What's your biggest weakness?"

| Type A | Type B |
|---|---|
| "It's never been on a real road drive — only on recorded real-world data. And our confidence estimate doesn't work, so we hide it rather than show a number we don't trust." | Same, plus the along-track error problem (right street, wrong distance). Uncertainty signal: spread–error correlation **−0.23** — near zero, decorative; must not show a confidence radius. |

**Owner:** `[NAME_LEAD]` opens; `[NAME_ESTIMATOR]` / `[NAME_EVAL]` deepen if asked

---

## Extra cold drills (by domain)

### Lead — "What is this and why does it matter?"

| Type A | Type B |
|---|---|
| "When GPS dies in a tunnel, the map freezes. COAST keeps the blue dot moving using only phone sensors and an offline road map — no extra hardware." | Same + market close: **19.6 million** two-wheelers FY2024-25 (SIAM); industry fallback needs vehicle wheel sensors; we need the phone in your pocket. |

### Android — "Walk me through what's on this screen."

| Type A | Type B |
|---|---|
| "Full-screen map, your position, blackout / replay controls. Airplane mode proves nothing leaves the device." | Label honesty: live blackout vs **REPLAY — real dataset, real estimator**. Mock/preview UIs say **MOCK — not live data** in-frame. No confidence radius shown. |

### ML — "What does the neural net actually do, and why is it a wash per-window?"

| Type A | Type B |
|---|---|
| "It estimates speed from motion sensors when GPS is gone. On a fair leave-file-out test it does not beat simply holding the last speed — and we say that out loud." | AVNet-tiny: median RMSE **5.061 m/s** vs hold **1.280 m/s**; **0 of 23** folds beat hold per-window. Closed-loop distance wins are a separate story — do not oversell. Train button runs a real training subprocess, not a fake progress bar. |

### Maps — "Why OSM not Google? Does data leave the phone?"

| Type A | Type B |
|---|---|
| "OSM needs no API key and works offline. With basemap off and airplane mode, nothing leaves the phone." | Offline graph on device; no analytics / no default network / tracker opt-in false. Provenance: `built_from_drive_data: false`. |

### Eval — "How do I know these numbers are real?" *(also the self-audit story)*

| Type A | Type B |
|---|---|
| Linter demo + "every number has a source file." | Self-audit (~20 s): we found a unit bug inflating every drift number by **3.6×**; stopped; fixed; re-ran everything invalidated; now lint deck numbers against source. Disagreement story: post-hoc snap measured at **0.98×** — settled by data, not argument. |

---

## Delivery mechanics (F9)

- Lead with the conclusion, then support. Claim first, evidence second.
- Numbers aloud: three max in the pitch — **2.02× · 55% · 19.6 million**. Repetition beats coverage.
- Silence is fine. Two-second pause before answering reads as considered.
- Do not read slides. Watch the judge's face.
- Hostile judge: *"Good question"* → straight answer → no argument.
- Never contradict a teammate on a number. Only `[NAME_EVAL]` may gently correct a factual number error — once.

---

## Acceptance (Q&A)

- [ ] Printed / shared; every member drilled both columns
- [ ] Hard rules recited once as a team
- [ ] Each member answered five random bank questions cold
- [ ] Handoff phrase rehearsed: *"That's [Name]'s area — [Name]?"*
