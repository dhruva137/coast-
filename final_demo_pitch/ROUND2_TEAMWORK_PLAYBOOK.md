# Round 2 — Teamwork Playbook (F10)

**Source:** `win_tuning/F10_TEAMWORK.md`  
**Paired with:** `ROUND2_SCRIPT.md`, `ROUND2_QA_BANK.md`  
**Numbers:** `win_tuning/CLAIMS.json` + Phase 0 FIX-1 (2.02× = median position error only).

F10 is scored on **observable behaviour in the room**. Presence ≠ participation. Design the round so every member speaks.

---

## 1. Domain ownership table (fill names today)

Each person writes their own two-sentence cold answer — do not hand them a scripted paragraph they did not author.

| # | Domain | Owns | Speaks during | Must answer cold | Name |
|---|---|---|---|---|---|
| 1 | **Team lead / pitch** | Narrative, timing, handoffs | Act 1 open, Act 3 close; creates Q&A openings | "What is this and why does it matter?" | `[NAME_LEAD]` ____________ |
| 2 | **Estimator / core** | Map-in-loop filter, C++ engine | Act 2 (the insight) | "Why in-loop and not post-hoc? Why not a Kalman filter?" | `[NAME_ESTIMATOR]` ____________ |
| 3 | **Android / product** | The app, the demo | Act 1 (drives the phone) | "Walk me through what's on this screen." | `[NAME_ANDROID]` ____________ |
| 4 | **ML / speed model** | AVNet, ONNX, training | Act 3 (optional live Train) | "What does the neural net actually do, and why is it a wash per-window?" | `[NAME_ML]` ____________ |
| 5 | **Evaluation / data** | Benchmark, every number | Act 3 (claims linter) | "How do I know these numbers are real?" | `[NAME_EVAL]` ____________ |
| 6 | **Maps / systems** | OSM graph, offline, privacy | Q&A / optional Act 3 line | "Why OSM not Google? Does data leave the phone?" | `[NAME_MAPS]` ____________ |

**Rule:** nobody answers a question in someone else's domain. Hand off: *"That's `[NAME_X]`'s area — `[NAME_X]`?"*

**Logistics owner (extra hat):** one person owns charging, cables, USB backup, water — assign: ____________ (often `[NAME_MAPS]` or `[NAME_ANDROID]`).

---

## 2. Handoff choreography (three planned + reactive)

Rehearse until they sound unrehearsed. Physical staging: speaker half a pace forward; others orient toward them, not only toward the judge.

### Planned

1. **Lead → Android (Act 1)**  
   `[NAME_LEAD]`: *"`[NAME_ANDROID]`, hand the judge the phone."*  
   `[NAME_ANDROID]` drives and narrates. Lead stays quiet.

2. **Lead → Estimator (Act 2)**  
   `[NAME_LEAD]`: *"The reason this works isn't obvious — `[NAME_ESTIMATOR]` found it."*  
   `[NAME_ESTIMATOR]` delivers 55% → 0.98× → **2.02× lower median position error** → along-track limitation.

3. **Estimator → Evaluation (Act 3)**  
   `[NAME_ESTIMATOR]`: *"Every number I just gave you is checked automatically — `[NAME_EVAL]`, show them."*  
   `[NAME_EVAL]` runs `python tools/verify_claims.py --demo-failure`.

### Reactive (Q&A)

- Lead routes; does not answer for owners.
- If a domain gets no question, Lead creates an opening before time ends:  
  *"`[NAME_MAPS]`, tell them about the offline map."*  
  *"`[NAME_ML]`, one sentence on what Train actually runs."*
- Credit by name: *"`[NAME_ESTIMATOR]` found that."* *"`[NAME_EVAL]` caught the unit bug."*

---

## 3. Problem-solving stories (rehearse owners)

### Self-audit (~20 s) — `[NAME_EVAL]`

> "We found a unit bug in our own pipeline that was inflating every drift number by **3.6×**. `[NAME_EVAL]` caught it while building the benchmark harness — we stopped, fixed it, and re-ran everything it invalidated, including results we'd already written up. That's why we now lint every number in the deck against its source file automatically."

### Disagreement settled by measurement (~15 s) — `[NAME_ESTIMATOR]` or `[NAME_EVAL]`

> "We disagreed about whether snapping to the road afterwards would be good enough. Rather than argue, we measured it — it scored **0.98×**, it made things worse. That settled it."

Do **not** claim the team never disagreed.

---

## 4. Behaviours that score / cost

**Score**

- Credit by name; listen visibly (look at the teammate speaking).
- Support without rescuing — let a stumble finish.
- One voice at a time.
- Leader speaks least in Q&A.

**Cost**

- Leader answering inside someone else's domain.
- A member silent the entire round (non-negotiable: every member speaks ≥ once).
- Correcting a teammate in front of the judge (except `[NAME_EVAL]` gently fixing a wrong **number**, once).
- Checking a phone while a teammate speaks.
- Two different numbers for the same claim — worst case for F9+F10.

---

## 5. Five-number drill (every member, no others)

Memorise exactly these five. Evening-before: Lead asks each member all five in random order. Hesitation → drill again (~10 min).

| Claim | Say exactly |
|---|---|
| Map-in-loop improvement | **2.02× lower median position error** (252.66 m → 125.20 m) |
| The negative result | **A perfect gyroscope still fails 55%** of 60-second segments |
| The control | Post-hoc road snapping: **0.98× — it hurts** |
| Edge throughput | **120,305 Hz** (200 Hz required) |
| Market | **19.6 million** two-wheelers sold in India, FY2024-25 |

**Also know, but do not volunteer unless asked — and do not confuse with 2.02×:**

- Median drift: **27.6% → 16.8%** (ratio ≈ 1.65× if pressed; never call this 2.02×).
- Cohort: **43** real GNSS outages, CAN truth.
- Unit-bug story: **3.6×** inflation (self-audit).

**If asked any other numeric:** *"I'd have to check the exact figure — `[NAME_EVAL]` owns the benchmark."*

---

## 6. Rehearsal plan (two sessions, all six)

### Rehearsal 1 — Wednesday night (~45 min)

- [ ] Full run, timed. Expect long; cut from Act 2.
- [ ] Each member delivers their own section. Nobody reads.
- [ ] Round-robin: each person answers three Q&A-bank questions cold (A and B).
- [ ] Five-number drill.
- [ ] Fill remaining blank names if any.

### Rehearsal 2 — Thursday night (~45 min)

- [ ] Full run, timed, aim ≤5:00.
- [ ] **Adversarial round:** Lead plays hostile judge — interrupts, hardest F9 questions, challenges a number, expresses doubt. Practise staying warm.
- [ ] **Failure drill:** crash → backup video until **<5 seconds**.
- [ ] Handoffs until they sound unrehearsed.
- [ ] Confirm every member has a guaranteed speaking moment.
- [ ] Self-audit story timed (~20 s).

---

## 7. Logistics checklist (F10 starts at 8:45, not 1:00)

### Day-of reporting

- [ ] Team leader to **B Block Seminar Hall by 8:45**
- [ ] Members to assigned classrooms by **9:00**
- [ ] Shortlisted teams stay in allotted classrooms after 12:30 announcement
- [ ] Only Round-2 qualified teams receive certificates

### Dress

- [ ] **White formal shirt, black formal pants** — all six

### Kit (logistics owner)

- [ ] Phone charged; airplane mode; demo pre-warmed and tested that morning
- [ ] Backup video on phone **and** laptop **and** USB stick
- [ ] Laptop charged; `verify_claims --demo-failure` tested; figures pre-generated
- [ ] Deck on laptop **and** PDF on USB **and** emailed to leader
- [ ] Cables / adapter for venue projection
- [ ] Water for all six
- [ ] Everything works with venue wifi dead

### Pre-event team readiness

- [ ] Two timed full rehearsals with all six
- [ ] Every member answered five random Q&A questions cold
- [ ] Five-number drill passed without hesitation
- [ ] Failure drill under 5 seconds

---

## 8. Acceptance (F10)

- [ ] Ownership table filled with real names; each person wrote their own cold answers
- [ ] Three handoffs choreographed and rehearsed
- [ ] Every member has a guaranteed speaking moment
- [ ] Self-audit story rehearsed by `[NAME_EVAL]` (~20 s)
- [ ] All six pass the five-number drill without hesitation
- [ ] Two full timed rehearsals done, including adversarial round
- [ ] Failure drill under 5 seconds
- [ ] Dress and reporting times confirmed with all six
- [ ] Number wording matches Phase 0: **2.02× lower median position error**; drift never carries 2.02×
