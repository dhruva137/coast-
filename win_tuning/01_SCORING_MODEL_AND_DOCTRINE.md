# 01 — The Scoring Model & Doctrine

**Read this before any other file in `win_tuning/`.** Every F-file (`F1_…` to
`F10_…`) is an application of the doctrine set here. Cursor does not get to
re-decide any of this; it executes against it.

---

## A. The format reality (this changes the optimisation target)

From the official schedule PDF (Friday 11 Sep 2026):

| Time | What | Criteria |
|---|---|---|
| 8:45 | **Team leader** reports to B Block Seminar Hall | — |
| 9:00 | **Team members** report to assigned classrooms | — |
| 10:00–11:30 | Inauguration + guidelines + setup | — |
| **11:30–12:00** | **ROUND 1 — evaluation** | **F1–F8** |
| 12:00–12:30 | Result compilation | — |
| **12:30** | **Round 1 results — shortlist announced** | — |
| **13:00 onwards** | **ROUND 2 — final evaluation** | **F9 & F10 only** |

Three consequences that most teams will miss, and that we design around:

### A1. Round 1 is ~30 minutes for an entire classroom of teams.

Eight criteria (F1–F8) get scored in a window that, split across the teams in a
room, gives each team **roughly 90 seconds to 3 minutes**. A judge is not going
to read a dense slide. They will assign eight scores from an impression formed in
the first 20 seconds, then look for one or two pieces of evidence that justify it.

**Therefore: the deck is not a document. It is a scoring instrument.** Each slide
must hand the judge the score it wants, in the largest type on the slide.

### A2. Round 2 scores NOTHING technical.

F9 is *Presentation & Communication — clarity, pitch effectiveness, and Q&A
handling.* F10 is *Collaboration & Teamwork — team dynamics & problem-solving
approach.* Neither mentions the product.

**Therefore: no code change can improve F9 or F10.** They are won by rehearsal,
by a script with named speaking parts, and by visible shared ownership. Files
`F9_…` and `F10_…` are choreography documents, not engineering tasks. Budget
human time for them accordingly — they are 2 of the 10 criteria and the *only*
two that decide the final round.

### A3. All 6 members must be present in Round 2, in white shirt / black pants.

F10 is scored on the team, not the leader. A team where one person talks and five
stand silent scores badly by construction. See `F10_TEAMWORK.md`.

---

## B. The judge model — and the doctrine that follows

The room will contain a mix we cannot predict:

- **Judge type A — the non-specialist.** An average college professor from an
  unrelated department. Does not know what a particle filter is, will not ask.
  Scores on: did I understand the problem, did the solution seem clever, did it
  look finished, did the team seem competent.
- **Judge type B — the specialist.** Knows signal processing, robotics, or
  aerospace. Scores on: is the claim defensible, did they measure it, do they
  know what they don't know. Actively hunts for overclaiming.

Optimising for A alone reads as shallow to B. Optimising for B alone loses A in
the first 15 seconds. Most teams pick one and lose the other half of the room.

### The doctrine: LAYERED COMMUNICATION

Every artifact — every slide, every screen, every sentence — is built in four
layers. A judge stops at whatever layer their interest and expertise ends, and
**the score they give at that layer must already be a 10.**

| Layer | Time | Who it is for | Form |
|---|---|---|---|
| **L0** | 5 seconds | Everyone, including someone glancing from across the room | **One picture.** Red dot sprays off the road; green dot stays on it. No text needed to understand it. |
| **L1** | 30 seconds | Judge type A | **One sentence.** "When GPS dies your map freezes. Ours keeps moving — and we proved a *perfect* sensor still can't do it. Only the map can." |
| **L2** | 2 minutes | Both types | **Three numbers with sources on screen.** 2.02× · perfect gyro still fails 55% · 120,305 Hz. |
| **L3** | Q&A, unbounded | Judge type B | **The repo.** Ablations, the negative results, the papers, the bug we found in our own pipeline. |

**The hard rule this creates:** *no artifact may require L2 comprehension to
deliver its L0 impression.* If a slide's meaning depends on the judge reading a
table, the slide has failed and must be redesigned around a picture.

**The second hard rule:** *L1 must never be a simplification that L3 contradicts.*
The one-sentence version and the repo must tell the same story. This is what
separates us from a team that oversimplified — when judge B pulls the thread, it
holds.

---

## C. What "10/10" means here — and the trap

The instruction was "score outstanding on every criterion." The failure mode of
that instruction is **inflation**: teams respond by claiming more. At an
ISRO-adjacent evaluation, that is exactly backwards.

**Our thesis: the highest-scoring posture is calibrated confidence.**

A team that says *"we achieved 2.02× on real data, and we do not yet clear the
hardest bar end-to-end — here is our plan"* outscores a team claiming 5× with no
sources, because:

1. Judge type B can verify the first team and cannot verify the second.
2. Volunteering a limitation is a competence signal. It reads as *"this team
   knows the difference between what they measured and what they hope."*
3. It makes the Q&A unloseable. Nobody can catch you out on a weakness you
   raised first.

**Therefore: `10/10` is defined for us as "the maximum defensible score", and we
reach it by making the evidence trivially checkable, not by making the claim
bigger.** Every F-file works this way — it maximises *demonstrated* strength and
*explicitly stages* the honest gap.

### The claim discipline (non-negotiable, enforced in code)

- No number appears on a slide, in the app, or in the console unless it exists in
  `win_tuning/CLAIMS.json` with a source file and a command that recomputes it.
- Phase 0 builds a linter that **fails the build** if this is violated. See
  `00_MASTER_INDUCTION.md` Phase 0.
- Anything not yet measured is written as a roadmap item, never as a result.
- The list of things we explicitly **do not claim** lives in
  `final_demo_pitch/TEAM_MASTER_BRIEF.md` §2 and is binding.

---

## D. The three structural bets

These are the decisions that make the difference between "a good hackathon
project" and "the one they remember." Cursor implements them; it does not
relitigate them.

### Bet 1 — Turn honesty into an artifact, not a promise.

Every team will *say* they are rigorous. We will be the only team with
`tools/verify_claims.py`, a linter that refuses to build the deck if a slide
contains a number with no measured source. **Showing a judge a build that fails
on a fabricated number is a 10/10 moment on F5 and F8 simultaneously**, and takes
fifteen seconds to demonstrate.

### Bet 2 — Make the scalability story real in code, not in prose.

Right now the map constraint is hardcoded to road graphs. Every team's "future
scope" slide is hand-waving. Ours will not be:

> Refactor the constraint into an interface — `ConstraintManifold` — with
> `RoadGraphManifold` as the shipping implementation, and at least one other real
> implementation (a rail/corridor manifold) exercised by a passing test.

The moment that interface exists, "this same filter works for a train on a track,
a ship in a channel, a rover on a traverse" stops being a claim and becomes *a
type signature a judge can read.* The algorithm is unchanged; only the manifold
differs. That is the difference between a future-scope slide that scores 6 and
one that scores 10 — and it is genuinely true, which is why we can say it.

See `F2_TECHNICAL_FEASIBILITY.md` and `SCALABILITY_BEYOND_ROADS.md`.

### Bet 3 — Design the first five seconds of everything.

The L0 layer above. One picture on the deck, one screen in the app, one glance at
the console. Detailed per-artifact in `F3_UX_AND_DESIGN.md`.

---

## E. Where the criteria actually live

Mapping each criterion to the artifact that carries it, and who owns it.

| # | Criterion | Round | Primary artifact | Owner |
|---|---|---|---|---|
| F1 | Innovation & Creativity | 1 | Deck slide 2 + the 55% negative result | Estimator lead |
| F2 | Technical Feasibility | 1 | Deck slide 3 + `ConstraintManifold` + edge throughput | Core/C++ lead |
| F3 | UX & Design | 1 | The APK, screenshotted on the deck | Android lead |
| F4 | Impact & Usefulness | 1 | Deck slide 5, sourced impact numbers | Pitch lead |
| F5 | Technical Execution | 1 | Repo + claim linter + live console | Whole team |
| F6 | Sustainability & Future Scope | 1 | Deck slide 4/5 + the manifold roadmap | Core lead |
| F7 | Business Viability | 1 | Deck slide 5 + unit economics | Pitch lead |
| F8 | Security & Privacy | 1 | Privacy proof artifact + manifest honesty | Android lead |
| F9 | Presentation & Communication | **2** | The 3-act script + tiered Q&A bank | All, led by leader |
| F10 | Collaboration & Teamwork | **2** | Named speaking parts + visible handoffs | All 6 |

---

## F. Time budget for the remaining window

Today is **Tue 9 Sep**. The event is **Fri 11 Sep**. Two working days.

| Priority | Work | Deadline |
|---|---|---|
| **P0** | Phase 0 (truth lock) + deck L0/L1 pass + Round 2 script | Wed night |
| **P0** | Rehearsal #1 with all 6 members, timed | Wed night |
| **P1** | Phases 1–2 (money visual, manifold, code-quality surfacing) | Thu afternoon |
| **P1** | Rehearsal #2 + adversarial Q&A drill | Thu night |
| **P2** | Phases 3–4 (breadth, privacy artifact) | Thu, only if P0/P1 green |
| **Cut** | Anything not on a slide or in the 2-minute demo by Thu 18:00 | — |

**The gate:** if a phase is not finished by Thursday 18:00, it does not ship. A
half-finished feature scores worse than its absence, because it invites the
question "why doesn't this work?" during Q&A.

---

## G. The one-paragraph version (memorise this)

> Round 1 gives us ninety seconds and eight scores, judged off a deck by someone
> who may not be technical. Round 2 scores only how we speak and how we work as a
> team. So: every slide leads with a picture and a sentence, every number on it
> is linted against a measured source file, we volunteer our biggest limitation
> before anyone asks, and all six of us can defend our own area. We do not win by
> claiming more than we measured. We win by being the only team whose claims a
> judge can check in ten seconds — and by being the only team whose "future
> scope" is a working interface instead of a bullet point.
