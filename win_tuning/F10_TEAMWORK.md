# F10 — Collaboration & Teamwork
*"Team dynamics & problem-solving approach"* · **ROUND 2** · all 6 members present

---

## A. This is the most winnable criterion, and the most commonly thrown away

F10 is scored on **observable team behaviour during Round 2.** The judge cannot
see your git history or your group chat. They score what happens in the room over
a few minutes.

**The default failure is brutal and extremely common:** the team leader delivers
everything while five people stand behind them in silence. That is a low F10 by
construction, no matter how good the project is — the judge has been given no
evidence of a team.

The rules mandate all six members present. **Presence is not participation.**
Design the round so that participation is unavoidable and visible.

## B. The core mechanic: every member owns a domain and speaks in it

Fill this table with real names **today**, and have each person actually write
their own two-sentence answer rather than being handed one.

| # | Domain | Owns | Speaks during | Must answer cold |
|---|---|---|---|---|
| 1 | **Team lead / pitch** | The narrative, timing, handoffs | Act 1 (the handoff), the close | "What is this and why does it matter?" |
| 2 | **Estimator / core** | Map-in-loop filter, C++ engine | Act 2 (the insight) | "Why in-loop and not post-hoc? Why not a Kalman filter?" |
| 3 | **Android / product** | The app, the demo | Act 1 (drives the phone) | "Walk me through what's on this screen." |
| 4 | **ML / speed model** | AVNet, ONNX, training | Act 3 (live training) | "What does the neural net actually do, and why is it a wash per-window?" |
| 5 | **Evaluation / data** | The benchmark, every number | Act 3 (the linter demo) | "How do I know these numbers are real?" |
| 6 | **Maps / systems** | OSM graph, offline, privacy | Q&A on privacy and maps | "Why OSM not Google? Does data leave the phone?" |

**The rule: nobody answers a question in someone else's domain.** Hand off
instead. *"That's Arjun's area — Arjun?"*

This single behaviour is the highest-leverage thing in this document. Each handoff
is a visible, unmistakable demonstration of distributed ownership. Do it three
times in Round 2 and F10 is effectively decided. Judges score what they observe,
and a clean handoff is the clearest possible observation of a functioning team.

## C. Choreographed handoffs — rehearse these exact moments

Handoffs must look natural, which means they must be rehearsed. Three planned,
plus reactive ones in Q&A:

1. **Lead → Android** (Act 1): *"Ravi, hand the judge the phone."* Ravi drives
   the demo and narrates it. The lead stays quiet during this.
2. **Lead → Estimator** (Act 2): *"The reason this works isn't obvious — Sneha
   found it."* Sneha delivers the 55% negative result and the in-loop insight.
3. **Estimator → Evaluation** (Act 3): *"Every number Sneha just gave you is
   checked automatically — Karthik, show them."* Karthik runs the linter demo.

**Physical staging matters.** Do not stand in a line. Whoever is speaking steps
half a pace forward; the others orient toward them rather than toward the judge.
This reads as a team listening to a colleague, not five people waiting their turn.

## D. Demonstrating "problem-solving approach" — the second half of the criterion

The criterion is not only *dynamics*, it is *problem-solving approach*. So show
how the team actually works. One rehearsed 20-second story does this better than
any claim:

> **The self-audit story.** "We found a unit bug in our own pipeline that was
> inflating every drift number by 3.6×. Karthik caught it while building the
> benchmark harness, we stopped, fixed it, and re-ran everything it invalidated —
> including results we'd already written up. That's why we now lint every number
> in the deck against its source file automatically."

Why this works: it demonstrates (a) that people check each other's work,
(b) that the team stops for correctness rather than pushing through, and
(c) a process improvement that came out of a failure. That is precisely what
"problem-solving approach" means, and it is a true story.

**A second story, if there is time — disagreement resolved by measurement:**

> "We disagreed about whether snapping to the road afterwards would be good
> enough. Rather than argue, we measured it — it scored 0.98×, it made things
> worse. That settled it, and it became one of our strongest results."

Teams that resolve disagreements with data score higher than teams that report no
disagreements. **Do not claim you never disagreed.** It reads as either dishonest
or as a team where only one person's view mattered.

## E. Behaviours that visibly score

- **Credit by name.** "Sneha found that." "That was Ravi's call." Costs nothing,
  observed immediately, and reads as a genuinely healthy team.
- **Listen visibly.** When a teammate speaks, look at them. Do not look at the
  judge, the floor, or your phone.
- **Support without rescuing.** If someone stumbles, let them finish. Cutting in
  to save a teammate looks worse than the stumble did, and it signals that only
  one person is trusted.
- **One voice at a time.** Never two people answering the same question.
- **The leader speaks least in Q&A.** Counter-intuitive, and correct: a leader
  who routes questions to owners demonstrates a team; a leader who answers
  everything demonstrates a solo project with five spectators.

## F. Behaviours that visibly cost

- The leader answering a question clearly inside someone else's domain.
- A member who says nothing for the entire round. **Every member must speak at
  least once — this is non-negotiable.** If someone's domain gets no question,
  the leader creates an opening: *"Priya, tell them about the offline map."*
- Correcting a teammate in front of the judge. If they say something slightly
  wrong, let it go unless it is a factual error about a number — and then it is
  the evaluation owner who corrects it, gently, once.
- Anyone visibly checking a phone or laptop while a teammate speaks.
- Contradicting each other on a number. **This is the worst-case scenario** — it
  destroys F9 and F10 together and casts doubt on every claim. Prevention: §G.

## G. Number discipline — the shared-facts drill

The fastest way to lose both Round 2 criteria is two members giving different
numbers for the same thing.

**Every member memorises exactly these five, and no others:**

| Claim | Number |
|---|---|
| Map-in-loop improvement | **2.02× lower median position error** (252.66 m → 125.20 m) |
| The negative result | **A perfect gyroscope still fails 55%** of 60-second segments |
| The control | Post-hoc road snapping: **0.98× — it hurts** |
| Edge throughput | **120,305 Hz** (200 Hz required) |
| Market | **19.6 million** two-wheelers sold in India, FY2024-25 |

**If asked anything else numeric:** *"I'd have to check the exact figure —
Karthik owns the benchmark."* Never estimate a number out loud. A wrong number
said confidently is worse than no number.

Note especially: 2.02× is **median position error**, not drift percentage. Drift
went 27.6% → 16.8%. Do not merge those two facts — see FIX-1 in
`PHASE0_BLOCKING_FIXES.md`.

**Drill:** the evening before, the leader asks each member all five numbers in
random order. Anyone who hesitates drills again. This takes ten minutes and it
prevents the single worst failure mode.

## H. The rehearsal plan (two sessions, both with all six)

### Rehearsal 1 — Wednesday night (~45 min)
- Full run, timed. Expect it to be too long; cut from Act 2.
- Each member delivers their own section. Nobody reads.
- Round-robin: each person answers three Q&A-bank questions cold.
- The five-number drill.

### Rehearsal 2 — Thursday night (~45 min)
- Full run, timed, aiming ≤5:00.
- **Adversarial round:** the leader plays a hostile judge — interrupts, asks the
  hardest questions in `F9` §C, challenges a number, expresses doubt. Practise
  staying warm.
- **Failure drill:** rehearse the crash → backup video transition until it takes
  under five seconds.
- Practise handoffs until they sound unrehearsed.

## I. Logistics (F10 is scored from 8:45, not 1:00)

- Team leader reports to **B Block Seminar Hall by 8:45**; members to assigned
  classrooms by **9:00**. Being late is an avoidable teamwork signal.
- **White formal shirt, black formal pants** — all six. Uniform appearance reads
  as a team before anyone speaks.
- Shortlisted teams **stay in their allotted classrooms** after the 12:30
  announcement.
- Only Round-2 qualified teams receive certificates.
- Assign one person to own logistics (charging, cables, USB backup, water) so
  nobody is scrambling at 12:55.

## J. Acceptance

- [ ] Ownership table filled with real names; each person wrote their own answers
- [ ] Three handoffs choreographed and rehearsed
- [ ] Every member has a guaranteed speaking moment
- [ ] The self-audit story rehearsed by its owner (~20 s)
- [ ] All six pass the five-number drill without hesitation
- [ ] Two full timed rehearsals done, including the adversarial round
- [ ] Failure drill under 5 seconds
- [ ] Dress and reporting times confirmed with all six
