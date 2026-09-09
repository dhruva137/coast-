# 03 — PPT Spec (Round 1 decider)

**This wins Round 1.** A judge spends 2–3 minutes on the deck against F1–F8.
Every slide below names which F-criteria it scores. Use the **official SIH
template**. Numbers are verbatim from `01_DECISION_LAYER.md` §D — do not alter.

**Design:** dark theme matching the app (near-black `#0B0E11`, one accent
`#00E0A4` teal-green, white text). One idea per slide. Big numbers, small words.
No clip-art. Screenshots of the real app and the real plots only.

---

## Slide 1 — Title (first impression)

- **COAST** — *when GPS dies, you coast on sensors.*
- One line: "AI-ML Intelligent Dead Reckoning for seamless navigation — SIH 26168, ISRO / Dept. of Space."
- Team name, 6 members, college.
- Background: a dark map screenshot with the green track entering a tunnel.

## Slide 2 — The problem *(F4)*

- "GPS dies in tunnels, underpasses, metros, multi-level car parks, and under
  jamming. The map freezes. The dot stops."
- "Most vehicles on Indian roads — trucks, older cars, **200M+ two-wheelers** —
  have **no built-in inertial navigation**. Their only navigation device is the
  driver's phone."
- One photo: a phone in a handlebar mount at a tunnel mouth.

## Slide 3 — Who needs it + why ISRO *(F4, F6)*

- Civilian: logistics, ride-hailing, quick-commerce, ambulances, metro riders.
- Strategic (why *ISRO* owns this PS): GNSS jamming/spoofing is a sovereignty
  issue; NavIC exists for this reason; inertial nav is the fallback on launch
  vehicles and spacecraft. "The same discipline ISRO flies, on a ₹15,000 phone."
- Cite `docs/ISRO_RELEVANCE.md` in the appendix.

## Slide 4 — The idea, and why it's non-obvious *(F1)* ← **the innovation slide**

- Naive dead-reckoning double-integrates noisy acceleration → drifts to oblivion
  in ~15 s.
- **Our key finding (measured, volunteer it):** *even with a **perfect** yaw
  sensor, free dead-reckoning still fails 55% of 60-second segments.* So the
  problem is **not** a better gyro.
- **Our answer:** put the **road map *inside* the filter loop** — the vehicle
  state lives *on* the road graph, so lateral error **cannot** grow without
  bound. Map-matching as a property of the state space, not a cleanup pass.
- Small diagram: `free DR → off-road spray` vs `map-in-loop → hugs the road`.

## Slide 5 — Proof it works *(F1, F5)* ← **the numbers slide**

Three numbers, big:

- **2.02×** better than free dead-reckoning — measured on **43 real GNSS
  outages**, against a car's own **CAN-bus ground truth** (IO-VNBD).
- Free DR baseline: **17%** (short arm) / **10%** (tunnel arm) pass.
- **Perfect gyro still fails 55%** → the reason the map is in the loop.
- Footer: "Every number here has a source file we can open on request."
- Put the **3-line trajectory overlay** plot here (green truth / red naive /
  teal ours) — generated live in the demo (`06_...`).

## Slide 6 — The 3.6× bug story *(F5)* ← **the "we really built this" slide**

- "We found a unit error **in our own pipeline** — a dataset column labelled
  km/h was actually m/s — that had been inflating every drift figure **3.6×**.
  Same code went from a reported 972% drift to 2.4% once fixed."
- Why it matters: "You can only find that by understanding the physics and the
  data. It is our answer to 'did you actually build this?'"

## Slide 7 — Architecture & the dual deliverable *(F2)*

- Block diagram: **one shared C++ math core** → (a) **JNI/Android @ 10 Hz**
  (consumer phone app), (b) **headless C++ daemon @ 200 Hz** for external
  FOG-grade IMUs (the edge-deployable engine the PS explicitly demands).
- Measured: edge engine runs at **120,305 Hz** (200 Hz requirement met 600×),
  8.3 µs/sample, 7.5 MB.
- Stack line: Kotlin/Compose · MapLibre+OSM (no key, no billing) · ONNX Runtime
  Mobile · C++ core. All offline.

## Slide 8 — Privacy & security *(F8)* ← **the checkable-claim slide**

- "**No user data ever leaves the device** — no uploads, no analytics, no
  account. The navigation runs with the radio off. The only outbound traffic is
  public OpenStreetMap tile requests, and **turning the basemap off makes zero
  network calls** — a property you can verify in the manifest, not a promise."
  (The app declares INTERNET *only* to fetch/cache tiles; do NOT claim "no
  INTERNET permission".)
- Optional live phone-tracker for demos is **LAN-only and opt-in**.
- No accounts required to navigate (login is optional).

## Slide 9 — Impact, sustainability, business *(F4, F6, F7)*

- Impact: works on phones people already own; no hardware; works underground.
- Sustainability: zero cloud, zero marginal cost, zero extra e-waste hardware.
- Business: free consumer app; **SDK licensing** to OEMs / logistics fleets /
  ride-hailing; edge-engine licensing for defence/industrial IMUs.

## Slide 10 — Demo + roadmap *(F5, F6)*

- "Live now: the app, a GNSS-blackout replay on real data, and model training
  that generates these exact plots in 90 seconds on this laptop."
- Honest roadmap (what's next, owned not hidden): GNSS+INS tight fusion ·
  on-phone latency measurement · field scooter loop-closure logs · calibrated
  uncertainty.

---

## Appendix slides (keep, show only if asked)

- A1: both benchmark arms, full table.
- A2: heading-ablation table (the 55% result in full).
- A3: the OSM graph stats (3,271 km / 35,631 edges).
- A4: team + per-member code ownership (feeds F10).

---

## Q&A bank (F9) — grounded in CURRENT numbers

Deeper hostile set: `docs/JUDGE_CROSS_EXAM.md`. The essentials, with today's
defensible answers:

1. **"Do you meet ISRO's <10% / <100 m/km?"** — "Not yet end-to-end on the
   hardest arm. Free DR passes 10–17%. Our map-in-loop filter is **2.02×**
   better on 43 real outages; closing the rest is our stated next step. We do not
   claim a pass we haven't measured."
2. **"Naive fails ~90% — isn't that fatal?"** — "That's the baseline we
   *advertise*. The contribution is the diagnosis (a perfect gyro still fails
   55%) and the map-in-loop fix."
3. **"Is the speed model's RMSE your position error?"** — "No. That's
   per-window supervision only. Position error is the closed-loop trajectory
   number, which is the 2.02× figure."
4. **"Did you fake the demo?"** — "The replay streams **real IO-VNBD sensor
   data** through the **real estimator** — same code path as live sensors. Point
   at any line."
5. **"Why not Google Maps?"** — "It needs live internet and a billing account,
   and it breaks our no-network privacy property. We use offline OpenStreetMap,
   which the PS names."
6. **"Why cars' data for a two-wheeler problem?"** — "IO-VNBD is the official
   public set and it's cars. Our headline is general smartphone navigation; the
   lean-aware two-wheeler handling is a differentiator we also demonstrate."
7. **"Has it run on a phone?"** — [If still true Friday] "The app builds and the
   pipeline is unit-tested; on-device field logging is our immediate next step.
   Today's demo is the honest replay + live training."
8. **"Your confidence radius?"** — "We measured our uncertainty signal's
   correlation with error at −0.23 — it's not trustworthy yet, so we deliberately
   **don't** display it as a confidence radius. Calibrating it is on the roadmap."

---

## Team slide content (F10)

Per-member ownership (fill names): estimator/C++ core · Android app/UI ·
ML/speed model · maps/OSM graph · evaluation/benchmark · pitch/docs. Rehearse
handoffs so each member answers on their area. F10 is scored on *visible* shared
ownership — every member speaks to their part in Round 2.
