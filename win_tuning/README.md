# `win_tuning/` — the winning layer

Everything here exists to answer one question: **how does this project score the
maximum defensible mark on each of F1–F10, for a judge who might be a specialist
or might not be?**

This folder is **strategy, not code**. Cursor reads it and executes; it must never
edit it.

---

## Read in this order

| # | File | What it is |
|---|---|---|
| 1 | **`01_SCORING_MODEL_AND_DOCTRINE.md`** | **Start here.** The format reality, the judge model, the layered-communication doctrine, the three structural bets, the time budget. Everything else applies this. |
| 2 | `00_MASTER_INDUCTION.md` | The prompt to paste into Cursor. Seven phases, parallel subagents inside each, gates between. |
| 3 | `PHASE0_BLOCKING_FIXES.md` | Six defects found by an independent honesty audit. **Blocks every other phase.** |
| 4 | `F1_INNOVATION.md` … `F10_TEAMWORK.md` | One file per criterion. What it rewards, our position, tasks, exact language, the question that decides it, acceptance. |
| 5 | `RESEARCH_GLOBAL_CONTEXT.md` | Sourced evidence pack — jamming, policy, NavIC, market, tunnels. Includes the **banned list**. |
| 6 | `SCALABILITY_BEYOND_ROADS.md` | Cross-domain evidence — rail, indoor, undersea, aviation, Chandrayaan-3, Perseverance. And the honest limits. |

---

## The three things that matter most

**1. Round 1 is ~90 seconds per team, judged off the deck.** Eight criteria
(F1–F8) scored in a 30-minute window for a whole classroom. Every slide must hand
the judge its score in the largest type on the slide, and must work for a judge
who is not technical.

**2. Round 2 scores only F9 and F10 — presentation and teamwork.** No code change
affects it. It is won by two timed rehearsals with all six members and by
choreographed handoffs. Budget human time for this; it decides the final round.

**3. We win by being checkable, not by claiming more.** The highest-scoring
posture at an ISRO-adjacent evaluation is calibrated confidence: maximise
*demonstrated* strength, and explicitly stage the honest gap. A defensible
negative result beats a polished overclaim every time.

---

## The five numbers everyone memorises

| Claim | Number |
|---|---|
| Map-in-loop | **2.02× lower median position error** (252.66 m → 125.20 m, 43 outages, CAN truth) |
| The negative result | **A perfect gyroscope still fails 55%** of 60-s segments |
| The control | Post-hoc road snapping: **0.98× — it hurts** |
| Edge throughput | **120,305 Hz** (200 Hz required) |
| Market | **19.6 million** two-wheelers sold in India, FY2024-25 (SIAM) |

**2.02× is median position *error*, not drift percentage.** Drift went
27.6% → 16.8%. Never merge those two facts — see `PHASE0_BLOCKING_FIXES.md` FIX-1.

---

## The one-paragraph strategy

> Round 1 gives us ninety seconds and eight scores, judged off a deck by someone
> who may not be technical. Round 2 scores only how we speak and how we work as a
> team. So: every slide leads with a picture and a sentence, every number on it is
> linted against a measured source file, we volunteer our biggest limitation
> before anyone asks, and all six of us can defend our own area. We do not win by
> claiming more than we measured. We win by being the only team whose claims a
> judge can check in ten seconds — and by being the only team whose "future scope"
> is a working interface instead of a bullet point.

---

## Relationship to the rest of the repo

- `final_demo_pitch/TEAM_MASTER_BRIEF.md` — the team-facing one-pager. Still
  valid. This folder is the *scoring strategy* behind it.
- `cursor_induction_v2/` — the previous build wave (bug fixes, UI, console,
  dataset harness, research). Delivered; audited in `PHASE0_BLOCKING_FIXES.md`.
- `final_demo_pitch/01_DECISION_LAYER.md` — the earlier F1–F10 mapping. This
  folder supersedes it for scoring strategy; the numbers there remain binding.
