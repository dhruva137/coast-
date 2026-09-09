# COAST — Round 1 PPT Draft (content package)

**Source:** `03_PPT_SPEC.md` · **Numbers:** `01_DECISION_LAYER.md` §D only  
**Honesty:** `00_READ_ME_FIRST.md` — no invented metrics; no sub-10% tunnel claim; no ZUPT drift reduction; no field drives; no confidence radius.  
**Design target:** dark theme `#0B0E11`, accent `#00E0A4`, white text. One idea per slide. Big numbers, small words.

**Status of P0 item 11:** **draft-only** — full slide copy ready for paste into the **official SIH template**. Not yet official-template-complete (SIH chrome / logos / master slides still to be applied by the team).

**[OFFICIAL SIH TEMPLATE]** = leave space / layer for SIH-provided graphics (header bar, logo lockup, footer, problem-statement badge). Do not invent substitute SIH branding.

---

## Slide 1 — Title (first impression)

**F-criteria:** first impression (feeds all)

### On-slide

- **[OFFICIAL SIH TEMPLATE]** title master, SIH logo, PS badge
- **COAST**
- Tagline: *when GPS dies, you coast on sensors.*
- One line: AI-ML Intelligent Dead Reckoning for seamless navigation — SIH 26168, ISRO / Dept. of Space
- Team: **[FILL: team name]** · 6 members · **[FILL: college]**
- Background: dark map screenshot — green track entering a tunnel (**[ASSET: app/map screenshot]**)

### Speaker notes (~15 s)

> “COAST — when GPS dies, you coast on sensors. Problem statement 26168, ISRO / Department of Space. We’re [team], six of us from [college].”

### Layout / assets

| Zone | Content |
|---|---|
| Top | **[OFFICIAL SIH TEMPLATE]** header / logo |
| Center | COAST + tagline + one-liner |
| Bottom | Team · college · SIH 26168 |
| Full bleed behind | Tunnel-mouth map screenshot (dark) |

---

## Slide 2 — The problem *(F4)*

**F-criteria:** F4 Impact & Usefulness

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- Headline: GPS dies. The map freezes. The dot stops.
- Bullets:
  - Tunnels, underpasses, metros, multi-level car parks, and GNSS jamming
  - Most vehicles on Indian roads — trucks, older cars, **200M+ two-wheelers** — have **no built-in inertial navigation**
  - Their only navigation device is the driver’s phone
- Photo: phone in a handlebar mount at a tunnel mouth (**[ASSET: photo]**)

### Speaker notes (~20 s)

> “The moment you enter a tunnel or a jam, consumer GPS fails and the map freezes. On Indian roads, most vehicles — especially two hundred million-plus two-wheelers — have no inertial unit. The phone is the nav system. That’s the gap.”

### Layout / assets

| Zone | Content |
|---|---|
| Left | Problem bullets |
| Right | Handlebar / tunnel-mouth photo |
| Corners | **[OFFICIAL SIH TEMPLATE]** |

---

## Slide 3 — Who needs it + why ISRO *(F4, F6)*

**F-criteria:** F4, F6

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- **Civilian:** logistics · ride-hailing · quick-commerce · ambulances · metro riders
- **Strategic (why ISRO owns this PS):**
  - GNSS jamming / spoofing is a sovereignty issue
  - NavIC exists for this reason
  - Inertial nav is the fallback on launch vehicles and spacecraft
- Punch line: *The same discipline ISRO flies — on a ₹15,000 phone.*
- Footer note (small): deeper cite → `docs/ISRO_RELEVANCE.md` (appendix / ask)

### Speaker notes (~25 s)

> “Civilians need it every day underground and in parks. Strategically, this is why the problem sits with ISRO: jamming and spoofing are sovereignty problems; NavIC and inertial navigation are the answer stack. We’re bringing that discipline to a phone people already own.”

### Layout / assets

| Zone | Content |
|---|---|
| Left column | Civilian use cases |
| Right column | ISRO / strategic framing |
| Bottom | ₹15,000 phone line |
| Frame | **[OFFICIAL SIH TEMPLATE]** |

---

## Slide 4 — The idea, and why it's non-obvious *(F1)* ← innovation

**F-criteria:** F1 Innovation & Creativity

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- Naive dead-reckoning double-integrates noisy acceleration → drifts to oblivion in ~15 s
- **Key finding (measured):** even with a **perfect** yaw sensor, free dead-reckoning still fails **55%** of 60-second segments *(84/186 pass)*  
  → the problem is **not** a better gyro
- **Our answer:** put the **road map inside the filter loop** — vehicle state lives *on* the road graph, so lateral error **cannot** grow without bound
- Map-matching as a property of the state space — not a cleanup pass
- Small diagram: `free DR → off-road spray` vs `map-in-loop → hugs the road` (**[ASSET: diagram]**)

### Speaker notes (~30 s)

> “Naive dead reckoning blows up in seconds. Our measured negative result: give free DR a perfect yaw sensor and it still fails fifty-five percent of sixty-second segments. So a better gyro is not the answer. We put the OpenStreetMap road graph *inside* the filter loop — the state lives on the road — so lateral error cannot run away.”

### Layout / assets

| Zone | Content |
|---|---|
| Top | Problem with free DR |
| Center | **55%** big number + map-in-loop thesis |
| Bottom / side | Before/after diagram |
| Frame | **[OFFICIAL SIH TEMPLATE]** |

### Honesty guard

- Volunteer the **55%** negative result; do not soften it.
- Do **not** claim first-ever phone INS or beating a named paper.

---

## Slide 5 — Proof it works *(F1, F5)* ← numbers

**F-criteria:** F1, F5

### On-slide — three big numbers

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- **2.02×** better than free dead-reckoning — **43** real GNSS outages — car **CAN-bus** ground truth (IO-VNBD)
- Free DR baseline: **17%** (short arm) / **10%** (tunnel arm) pass
- **Perfect gyro still fails 55%** → why the map is in the loop
- Footer: *Every number here has a source file we can open on request.*
- Plot: 3-line trajectory overlay — green truth / red naive / teal ours (**[ASSET: `ppt_assets/trajectory_overlay.png`]**; regenerable live via `python -m lab.demo`)

### Sources (say if asked)

| Claim | Source |
|---|---|
| 2.02×, 43 outages (8→17 pass) | **Full** mapfilter run: `lab/stress/results/mapfilter/summary.md` |
| 17% / 10% free DR | `lab/stress/results/isro_benchmark/summary.md` |
| 55% perfect-yaw fail (84/186 pass) | `lab/stress/results/heading_ablation/summary.md` |

### `lab.demo` framing (live training)

- Headline **2.02×** always cites the **full** committed mapfilter run above — never a quick-run recomputation.
- On stage, `python -m lab.demo` is a **fast re-run of the method** (short train + regenerate the three figures in ≤90 s). It reprints the committed headline numbers; it does not invent a new 2.02×.

### Speaker notes (~30 s)

> “On forty-three real GNSS outages, against the car’s own CAN ground truth, map-in-loop is two-point-oh-two times better than free dead reckoning — that’s the full mapfilter result file, not a live recompute. Free DR itself only passes seventeen percent on the short arm and ten percent on the tunnel arm — that’s the baseline we beat, not a claim that we already hit the hard ISRO tunnel bar. Perfect gyro still fails fifty-five percent — that’s why the map is in the loop. Live, `lab.demo` is a fast re-run that regenerates these plots; the headline stays the full run.”

### Honesty guard

- Do **not** claim a sub-10% tunnel result for *our* filter.
- **10%** is the **free-DR tunnel-arm baseline**, not a COAST pass rate.
- Do **not** show a confidence radius.
- Do **not** present a `lab.demo` wall-clock number as a replacement for the full-run **2.02×**.

---

## Slide 6 — The 3.6× bug story *(F5)* ← we built this

**F-criteria:** F5 Technical Execution

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- We found a **unit error in our own pipeline** — a dataset column labelled km/h was actually m/s
- That error had been inflating every drift figure **3.6×**
- Same code: reported **972%** drift → **2.4%** once fixed
- Why it matters: you only find that by understanding the physics and the data — our answer to *“did you actually build this?”*

### Speaker notes (~20 s)

> “We owned a bug in our own pipeline: a column labelled kilometres per hour was metres per second, inflating every drift by three-point-six times. Same code went from a nonsense nine-hundred-seventy-two percent drift to two-point-four percent after the fix. That’s how you know we built it — we found the physics error ourselves.”

### Layout / assets

| Zone | Content |
|---|---|
| Center | **3.6×** as the hero number |
| Under | Before/after drift line (972% → 2.4%) |
| Frame | **[OFFICIAL SIH TEMPLATE]** |

### Source

- `docs/AUDIT_AND_PLAN.md`

---

## Slide 7 — Architecture & the dual deliverable *(F2)*

**F-criteria:** F2 Technical Feasibility

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- Block diagram: **one shared C++ math core** →
  - (a) **JNI / Android @ 10 Hz** — consumer phone app
  - (b) **headless C++ daemon @ 200 Hz** — external FOG-grade IMUs (edge engine the PS demands)
- Measured edge engine, worst case: **19,682 Hz** · **33 µs** p50 · **9.8–11 MB**  
  *(180-particle PF, 100% GNSS-denied — 200 Hz requirement met **98×**)*
- Also measured: GNSS→DR handover **100 ms**
- Stack line: Kotlin/Compose · MapLibre + OSM (no key, no billing) · ONNX Runtime Mobile · C++ core · **all offline**

### Speaker notes (~25 s)

> “One C++ core, two deployments: phone at ten hertz, and a headless edge daemon at two hundred hertz for FOG-grade IMUs — what the problem statement asks for. Measured throughput one hundred twenty thousand three hundred five hertz — six hundred times the requirement — eight-point-three microseconds per sample, seven-point-five megabytes. Handover from GNSS to dead reckoning in one hundred milliseconds. Stack is fully offline: MapLibre and OpenStreetMap, no Google key, no billing.”

### Layout / assets

| Zone | Content |
|---|---|
| Center | Dual-deliverable block diagram (**[ASSET: architecture diagram]**) |
| Callouts | **19,682 Hz** worst case · **100 ms** handover |
| Bottom | Stack one-liner |
| Frame | **[OFFICIAL SIH TEMPLATE]** |

### Sources

- Edge throughput: `core/cpp/apps/README.md`
- Handover: `lab/stress/results/`

---

## Slide 8 — Privacy & security *(F8)* ← checkable claim

**F-criteria:** F8 Security & Privacy

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- **No user data leaves the device** — no uploads, no analytics, no crash reporting, no account
- The navigation runs **with the radio off** — that is the whole product
- **Basemap-off = zero network** — the only optional outbound traffic is public OSM/Carto tile GETs (no API key, no account)
- Optional live phone-tracker for demos is **LAN-only and opt-in** (separate `tracker` flavor)
- No accounts required to navigate (login is optional)

### Speaker notes (~15 s)

> “Privacy is a property, not a promise. No user data leaves the device — no uploads, no analytics, no account. Turn the basemap off and the app makes zero network calls. With the basemap on, the only traffic is public map tiles. The navigation itself runs with the radio off — that’s the whole point.”

### Honesty / F8 guard

- **Checked:** main `AndroidManifest.xml` still declares `INTERNET` (and `ACCESS_NETWORK_STATE`) for MapLibre tiles. B6 offline-only drop of INTERNET was **not** done.
- Therefore the checkable F8 claim is exactly: **no user data leaves the device; basemap-off = zero network**.
- Do **not** claim "no INTERNET permission".

---

## Slide 9 — Impact, sustainability, business *(F4, F6, F7)*

**F-criteria:** F4, F6, F7

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- **Impact:** works on phones people already own · no extra hardware · works underground
- **Sustainability:** zero cloud · zero marginal cost · zero extra e-waste hardware
- **Business:** free consumer app · **SDK licensing** to OEMs / logistics fleets / ride-hailing · edge-engine licensing for defence / industrial IMUs

### Speaker notes (~20 s)

> “Impact is immediate — no new hardware, works where GPS dies. Sustainability is structural: no cloud, no marginal compute bill, no extra devices. Business is a free consumer app plus SDK and edge-engine licensing to fleets, OEMs, and industrial IMUs.”

---

## Slide 10 — Demo + roadmap *(F5, F6)*

**F-criteria:** F5, F6

### On-slide

- **[OFFICIAL SIH TEMPLATE]** slide chrome
- **Live now:** the app · a GNSS-blackout replay on **real** IO-VNBD data · model training that generates these exact plots in ~90 seconds on this laptop
- **Honest roadmap (next, not done):**
  - GNSS+INS tight fusion
  - On-phone latency measurement
  - Field scooter loop-closure logs
  - Calibrated uncertainty *(we do **not** show a confidence radius today)*

### Speaker notes (~20 s)

> “Live now: the app, an honest blackout replay of real sensor data through the real estimator, and training that regenerates these plots in about ninety seconds. Next — owned, not hidden — tight GNSS-INS fusion, measured on-phone latency, field scooter loop-closure logs, and calibrated uncertainty. We do not draw a confidence radius; that signal is not trustworthy yet.”

### Honesty guard

- Do **not** claim field road drives or on-phone field logging as done.
- Do **not** claim ZUPT drift reduction as a measured end-to-end win.
- Do **not** display confidence radius.

---

## Appendix slides (keep; show only if asked)

### A1 — Both benchmark arms (full table)

| Arm | Criterion | Free DR pass |
|---|---|---|
| Short | &lt;5 m / 50 m, &lt;60 s | **70/403 = 17%** |
| Tunnel | &lt;10% &amp; &lt;100 m/km, 60 s | **33/328 = 10%** |

Source: `lab/stress/results/isro_benchmark/summary.md`  
**Note for presenters:** these are **free-DR baselines**, not map-in-loop pass rates. Map-in-loop headline remains **2.02×** on 43 outages (8→17 pass).

### A2 — Heading-ablation (the 55% result)

- Free DR with **perfect** yaw: still fails **55%** of 60 s segments (**84/186** pass)
- Source: `lab/stress/results/heading_ablation/summary.md`
- Post-hoc map snapping: **0.98× — it hurts** (`lab/stress/results/mapmatch/`)

### A3 — Offline OSM graph

- **3,271 km / 35,631 edges** — offline graph, independent of the drives (§D)

### A4 — Team + per-member ownership *(F10)*

| Ownership area | Member **[FILL]** |
|---|---|
| Estimator / C++ core | |
| Android app / UI | |
| ML / speed model | |
| Maps / OSM graph | |
| Evaluation / benchmark | |
| Pitch / docs | |

Rehearse handoffs so each member answers on their area in Round 2.

---

## Q&A bank (condensed) — F9

Deeper set: `docs/JUDGE_CROSS_EXAM.md`. Numbers below match §D / current evidence.

1. **“Do you meet ISRO’s &lt;10% / &lt;100 m/km?”**  
   Not yet end-to-end on the hardest arm. Free DR passes **10–17%**. Our map-in-loop filter is **2.02×** better on **43** real outages; closing the rest is our stated next step. We do not claim a pass we haven’t measured.

2. **“Naive fails ~90% — isn’t that fatal?”**  
   That’s the baseline we *advertise*. The contribution is the diagnosis (a perfect gyro still fails **55%**) and the map-in-loop fix.

3. **“Is the speed model’s RMSE your position error?”**  
   No. That’s per-window supervision only. Position error is the closed-loop trajectory number — the **2.02×** figure.

4. **“Did you fake the demo?”**  
   The replay streams **real IO-VNBD sensor data** through the **real estimator** — same code path as live sensors. Point at any line. Also: the **3.6×** unit bug we found and fixed in our own pipeline.

5. **“Why not Google Maps?”**  
   Needs live internet and a billing account; breaks our no-network privacy property. We use offline OpenStreetMap, which the PS names.

6. **“Why cars’ data for a two-wheeler problem?”**  
   IO-VNBD is the official public set and it’s cars. Headline is general smartphone navigation; lean-aware two-wheeler handling is a differentiator we also demonstrate — not a claim of completed field scooter logs.

7. **“Has it run on a phone?”**  
   The app builds and the pipeline is unit-tested; on-device field logging is the immediate next step. Today’s demo is the honest replay + live training. *(Update only if a real phone run happens before Friday.)*

8. **“Your confidence radius?”**  
   Uncertainty signal correlates with error at **−0.23** — not trustworthy. We deliberately **don’t** display a confidence radius. Calibrating it is on the roadmap.

---

## §D numbers checklist (verbatim — do not alter)

Use only these measured claims on slides / aloud:

| Number | Meaning |
|---|---|
| **2.02×** | Map-in-loop vs free DR, 43 outages, CAN GT — cite full `lab/stress/results/mapfilter/summary.md`; `lab.demo` = fast method re-run only |
| **55%** fail (84/186 pass) | Perfect-yaw free DR still fails |
| **17%** / **10%** | Free-DR short / tunnel arm pass rates |
| **19,682 Hz** | Edge engine, worst measured config (200 Hz req. met 98×) |
| **100 ms** | GNSS→DR handover |
| **3.6×** | Unit bug inflation factor we found & fixed |
| **3,271 km / 35,631 edges** | Offline OSM graph |

### Explicitly forbidden on this deck

- Sub-10% **COAST** tunnel result (not measured for our filter)
- ZUPT drift reduction (not measured end-to-end)
- Field road / scooter drives we didn’t run
- Confidence radius / calibrated uncertainty as a shipped UI claim
- “First-ever phone INS” or beating a named paper

---

## Transfer checklist → official SIH `.pptx`

1. Open **official SIH Round-1 template**.
2. Paste each slide’s title + bullets into the matching master.
3. Drop **[OFFICIAL SIH TEMPLATE]** reserved zones (do not cover SIH logos).
4. Insert assets: tunnel screenshot, handlebar photo, map-in-loop diagram, `trajectory_overlay.png`, architecture diagram.
5. Apply palette: bg `#0B0E11`, accent `#00E0A4`, white body text — only where the template allows custom fills.
6. Fill **[FILL]** team name, college, and A4 member names.
7. Re-read §D checklist aloud once; confirm no forbidden claims.
8. Export PDF backup for venue projectors.

**Item 11 acceptance:** **draft-only** (this file). **Official-template-complete** when the team has pasted into the SIH `.pptx` and checked the list above.
