# Round 2 — Timed 3-Act Script (≤5:00)

**Source:** `win_tuning/F9_PRESENTATION.md` · **Teamwork:** `win_tuning/F10_TEAMWORK.md`  
**Hard cap:** 5:00. Target: ~4:00. If over, cut from Act 2 — never Act 1.  
**Numbers:** only `win_tuning/CLAIMS.json` / Phase 0 wording. **2.02× = median position error only** (not drift %).

Fill names once; use the same six everywhere (script, Q&A bank, teamwork playbook).

| Role | Placeholder | Real name (fill today) |
|---|---|---|
| Team lead / pitch | `[NAME_LEAD]` | ________________ |
| Estimator / core | `[NAME_ESTIMATOR]` | ________________ |
| Android / product | `[NAME_ANDROID]` | ________________ |
| ML / speed model | `[NAME_ML]` | ________________ |
| Evaluation / data | `[NAME_EVAL]` | ________________ |
| Maps / systems | `[NAME_MAPS]` | ________________ |

---

## Staging (before the clock)

- Line up in a shallow arc, not a single file. Speaker steps half a pace forward; others face them.
- Phone: charged, demo pre-warmed, airplane mode ready (or Simulate GNSS Blackout).
- Laptop: `python tools/verify_claims.py --demo-failure` one keystroke away; figures on disk.
- Backup video: phone **and** laptop **and** USB. Rehearse the cut until **<5 s**.

---

## ACT 1 — The handoff · 0:00–1:00 (60 s)

*This is the demo. Everything else is support.*

### Handoff 1 — Lead → Android

**`[NAME_LEAD]`** (open, ~10 s):

> "You've all had your map freeze in a tunnel. Watch what ours does."  
> *`[NAME_ANDROID]`, hand the judge the phone.*

**`[NAME_LEAD]` goes quiet.** Do not narrate over the demo.

**`[NAME_ANDROID]`** (drives + narrates, ~50 s):

1. Physically hand the phone to the judge. Let them hold it.
2. Turn on **airplane mode** in front of them — or tap **Simulate GNSS Blackout**.
3. The dot keeps moving on the road.
4. Say:

> "No GPS. No internet. That position is coming from the phone's motion sensors and the road map — nothing else."

Optional if walking is allowed and time allows (~10 s max): walk out and back to a floor tile; show closure. Skip if it risks the clock.

**Guaranteed speaking:** `[NAME_ANDROID]` must finish Act 1 narration alone if Lead is cut short.

### Act 1 failure transition (rehearse)

| If | Who | Line (under 5 s) | Then |
|---|---|---|---|
| App crashes / freezes | `[NAME_ANDROID]` | "That's the live path being stubborn — here's the recorded run." | Backup video → continue as if planned |
| Phone dies / won't unlock | `[NAME_LEAD]` | "We'll use the recorded run." | Backup video; phone stays charged from 8:45 next time |
| Demo lag / wrong screen | `[NAME_ANDROID]` | Same cut line | Do **not** debug on stage |

---

## ACT 2 — The insight · 1:00–2:30 (90 s)

*Scores F1. Volunteer the limitation — highest-value fifteen seconds.*

### Handoff 2 — Lead → Estimator

**`[NAME_LEAD]`** (~5 s):

> "The reason this works isn't obvious — `[NAME_ESTIMATOR]` found it."

**`[NAME_ESTIMATOR]`** (~75–85 s), claim first:

> "The obvious way to do this is to make the sensor better. We tested that. We gave our algorithm a **perfect** gyroscope — simulated, zero error, physically impossible — and it **still failed 55%** of the time.
>
> So the sensor was never the problem. We changed the geometry instead. Most systems estimate a free position and then snap it to the nearest road afterwards. We measured that: it scores **0.98× — it actually makes things worse.** What we do is put the road map *inside* the filter. The estimate lives on the road graph; there is no way to represent being off the road. Result: **2.02× lower median position error** across 43 real GNSS outages, with vehicle CAN data as ground truth — **252.66 m → 125.20 m**. Median drift falls separately: **27.6% → 16.8%**.
>
> And here's what we *don't* claim. This fixes sideways error. It does not fix how far along the road you are — right street, wrong distance. That's a known open problem, and it's exactly why the rail industry still installs physical beacons to reset odometry. It's our next milestone."

**Cut list if over time (Act 2 only):** drop the rail/beacon sentence last; never drop the 55%, the 0.98×, the 2.02× median-error line, or the along-track limitation.

### Act 2 failure transition

| If | Who | Then |
|---|---|---|
| Estimator blanks | `[NAME_LEAD]` | One prompt: "The 55% result — then map-in-loop." Do not take the speech. |
| Judge interrupts mid-Act 2 | Speaker | Answer briefly, return to the limitation beat if not yet said. |

---

## ACT 3 — The proof and the ask · 2:30–4:00 (≤90 s)

### Handoff 3 — Estimator → Evaluation

**`[NAME_ESTIMATOR]`** (~5 s):

> "Every number I just gave you is checked automatically — `[NAME_EVAL]`, show them."

**`[NAME_EVAL]`** (~15 s):

1. Run: `python tools/verify_claims.py --demo-failure`
2. Show the build failing on a planted fake number.
3. Say:

> "Every number in our deck is linted against a measured source file. If someone typed a number we hadn't measured, this fails."

### Optional if time (~20 s) — Lead → ML

**`[NAME_LEAD]`:** *"`[NAME_ML]`, Train — if we have twenty seconds."*

**`[NAME_ML]`:** Press Train; real epochs stream; loss curve moves. Label honestly:

> "Fast re-run of the measured training loop — not a simulation."

If Train fails or hangs: **skip immediately** to committed figures on disk. Never wait on a subprocess.

### Maps opening (if Q&A has not started and time remains, ~10 s)

**`[NAME_LEAD]`:** *"`[NAME_MAPS]`, one line on offline."*

**`[NAME_MAPS]`:**

> "Road graph is OpenStreetMap, on-device. No Google key, no billing, and the graph was not built from our drive data."

### The close — `[NAME_LEAD]` (~20–25 s)

> "Nineteen point six million two-wheelers sold in India last year. Almost none of them have any navigation fallback, because the fallback the industry sells needs wheel sensors the vehicle has to provide. We built one that needs nothing but the phone already in your pocket."

Stop. Leave silence for the judge. Do not add a second close.

### Act 3 failure transitions

| If | Who | Line / action |
|---|---|---|
| Laptop won't project | `[NAME_LEAD]` | Pitch from phone / spoken figures. All six know the script without slides. |
| `verify_claims` fails for real | `[NAME_EVAL]` | "We won't show a broken linter — figures are on disk from the measured run." Show committed summary / figures. |
| Live training fails | `[NAME_ML]` | Skip to committed figures. No waiting. |
| Venue wifi dead | Everyone | Already on airplane mode / localhost. Do not troubleshoot network. |

---

## Timing card (print this)

| Beat | Owner | Clock |
|---|---|---|
| Open + hand phone | `[NAME_LEAD]` → `[NAME_ANDROID]` | 0:00 |
| Blackout demo | `[NAME_ANDROID]` | → 1:00 |
| Insight + limitation | `[NAME_LEAD]` → `[NAME_ESTIMATOR]` | → 2:30 |
| Claims linter | `[NAME_ESTIMATOR]` → `[NAME_EVAL]` | ~2:45 |
| Optional Train | `[NAME_ML]` | only if <3:40 |
| Optional offline line | `[NAME_MAPS]` | only if <3:50 |
| Close | `[NAME_LEAD]` | → ≤4:00–5:00 |

**Every member speaks at least once.** If Q&A starts early, Lead creates openings (see playbook).

---

## Failure drill — full table (rehearse explicitly)

| If | Then |
|---|---|
| App crashes | "Let me show you the recorded run" → backup video. **Under 5 seconds.** No debugging. |
| Phone won't connect / dies | Backup video. Phone charged + airplane mode from 8:45. |
| Laptop won't project | Pitch from the phone. Script without slides. |
| Live training fails | Skip to committed figures. Never wait on a subprocess. |
| Judge asks something nobody knows | "I don't know — here's how we'd find out." Never guess. |
| Judge hostile / dismissive | Stay warm, answer, do not argue. Composure is F9. |

**Airplane mode from the start** — privacy proof and insurance.

---

## Acceptance (script)

- [ ] Six names filled; speaking parts match ownership table
- [ ] Timed ≤5:00 in two rehearsals
- [ ] Three handoffs sound natural
- [ ] Crash → backup video <5 s
- [ ] All six can deliver Act 1 alone if needed
- [ ] Numbers match CLAIMS: **2.02× median position error**, 55%, 0.98×, 19.6M; drift never carries 2.02×
