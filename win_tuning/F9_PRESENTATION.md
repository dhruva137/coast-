# F9 — Presentation & Communication
*"Clarity, pitch effectiveness, and Q&A handling"* · **ROUND 2** · 1:00 PM onwards

---

## A. This is half of the final round

Round 2 scores **only F9 and F10**. No code changes this score. It is won by
rehearsal, and it is the criterion most teams under-prepare because it feels less
concrete than building.

**Budget accordingly: two full rehearsals before Friday, timed, with all six
members.** That is worth more than any remaining feature.

## B. The three-act script (target 4 minutes, hard cap 5)

Time each act. If the whole thing runs over 5:00, cut from Act 2, never Act 1.

### ACT 1 — The handoff (60 s) · *the whole pitch lives here*

**This is the demo. Everything else is support.** If you only get sixty seconds,
this is the sixty seconds.

1. Hand the phone **to the judge**. Physically. Let them hold it.
2. Say: *"You've all had your map freeze in a tunnel. Watch what ours does."*
3. Turn on **airplane mode in front of them** — or hit Simulate GNSS Blackout.
4. The dot keeps moving on the road.
5. Say: *"No GPS. No internet. That position is coming from the phone's motion
   sensors and the road map — nothing else."*

Why this order works: the judge experiences the result *before* any explanation.
The explanation then lands on an experience instead of an abstraction. And
handing over the phone is a confidence signal — teams hide their demos when they
don't trust them.

**If it fails:** do not debug on stage. Say *"that's the live path being
stubborn — here's the recorded run"* and cut to the backup video. Then continue.
Rehearse this transition; it must take under five seconds. See §F.

### ACT 2 — The insight (90 s) · *the part that scores F1*

> "The obvious way to do this is to make the sensor better. We tested that. We
> gave our algorithm a **perfect** gyroscope — simulated, zero error, physically
> impossible — and it **still failed 55% of the time.**
>
> So the sensor was never the problem. We changed the geometry instead. Most
> systems estimate a free position and then snap it to the nearest road
> afterwards. We measured that: it scores **0.98× — it actually makes things
> worse.** What we do is put the road map *inside* the filter. The estimate lives
> on the road graph; there is no way to represent being off the road. Result:
> **2.02× lower median position error** across 43 real GNSS outages, with vehicle
> CAN data as ground truth."

Then the credibility beat, unprompted:

> "And here's what we *don't* claim. This fixes sideways error. It does not fix
> how far along the road you are — right street, wrong distance. That's a known
> open problem, and it's exactly why the rail industry still installs physical
> beacons to reset odometry. It's our next milestone."

**Volunteering the limitation here is the highest-value fifteen seconds in the
entire pitch.** It is what converts a technical judge from skeptic to advocate.

### ACT 3 — The proof and the ask (90 s)

1. **The laptop:** run `python tools/verify_claims.py --demo-failure`. Show the
   build failing on a planted fake number. *"Every number in our deck is linted
   against a measured source file. If someone typed a number we hadn't measured,
   this fails."* — 15 seconds, and it is unforgettable.
2. **Optional if time:** the live console — press Train, real epochs stream, the
   loss curve moves. Label it honestly as a fast re-run.
3. **The close:**
   > "Nineteen million two-wheelers sold in India last year. Almost none of them
   > have any navigation fallback, because the fallback the industry sells needs
   > wheel sensors the vehicle has to provide. We built one that needs nothing but
   > the phone already in your pocket."

## C. The Q&A bank — tiered by judge type

**The rule: answer the question that was asked, at the level it was asked.** A
non-technical judge who gets a technical answer feels talked down to; a technical
judge who gets a simple answer feels handled. Read the questioner, then pick a
column.

| Question | For judge type A (non-specialist) | For judge type B (specialist) |
|---|---|---|
| **"Isn't this just map matching?"** | "Map matching cleans up a GPS trail after the fact. We use the map *while* estimating, so the position can never leave the road in the first place." | "Post-hoc snapping scores 0.98× — it hurts, because you snap a drifted estimate confidently onto the wrong road. Our state space *is* the graph: (edge, offset along edge). Lateral divergence isn't suppressed, it's unrepresentable. Same map, opposite architecture, 0.98× vs 2.02×." |
| **"How accurate is it?"** | "About twice as good as the standard approach on real drives — and more importantly, it stays on the right road." | "2.02× lower median position error: 252.66 m → 125.20 m across 43 outages, CAN ground truth. Median drift 27.6% → 16.8%. We don't yet clear the sub-10% tunnel bar end-to-end." |
| **"How long can it go without GPS?"** | "Short to medium outages — a tunnel, an underpass, a car park. Not a whole city." | "We're UDR-class — no wheel ticks — so we degrade faster than automotive ADR past about a minute. The map bounds lateral error indefinitely; along-track error still accumulates." |
| **"Does Google already do this?"** | "Their tunnel fix needs Bluetooth beacons physically installed in the tunnel. It's off by default and no Indian city is on the list. Ours needs nothing installed." | Same, plus: "It's a hardware-deployment answer, not an algorithmic one. It doesn't help outside instrumented tunnels." |
| **"Have real users used it?"** | "Not yet — you're the first person outside the team to hold it. That's why there's no login and no setup." | Same, plus the honest note that field drives are the top roadmap item. |
| **"How do I know the numbers are real?"** | "Watch this." *(run the linter demo)* | Plus: "The registry includes our failures — 1.07× on GNSS+INS fusion, a wash on alignment, our speed model losing to a naive hold. Nobody fabricating results fabricates those." |
| **"Did the map leak your test data?"** | "No — the map is independent public data." | "The graph build report records `built_from_drive_data: false`: no trajectory, GNSS fix, or CSV column from the drives was read while building it." |
| **"Why not a Kalman filter?"** | "At a junction you might be on either road. A Kalman filter has to pick one; ours keeps both until the motion decides." | "Multi-modal belief on a graph. A unimodal Gaussian collapses exactly at the branch point where the ambiguity matters most." |
| **"What about NavIC?"** | "NavIC is being expanded right now — more satellites are launching. Ours works even while that's happening, and works underground where no satellite reaches." | Use the §0.1 framing in `RESEARCH_GLOBAL_CONTEXT.md`. **Respectful, paired with the recovery, never a criticism.** |
| **"What's your biggest weakness?"** | "It's never been on a real road drive — only on recorded real-world data. And our confidence estimate doesn't work, so we hide it rather than show a number we don't trust." | Same, plus the along-track error problem. |

### The three rules of Q&A handling

1. **If you don't know, say so, then say what you'd do.** *"I don't know — I'd
   measure it by X."* This scores higher than a confident wrong answer. Every
   member must be willing to say it.
2. **Never answer a question you weren't asked.** Over-answering signals anxiety.
3. **Hand off to the owner.** *"That's Priya's area."* This scores F9 *and* F10
   simultaneously and is the single easiest thing to rehearse. See `F10`.

## D. Delivery mechanics

- **Lead with the conclusion, then support it.** Every answer: claim first,
  evidence second. Never build up to a point.
- **Numbers: say three, not ten.** 2.02× · 55% · 19.6 million. Repetition beats
  coverage; a judge remembers three numbers from a pitch, maximum.
- **Silence is fine.** A two-second pause before answering reads as considered.
  Filler ("um, basically, like") reads as unprepared.
- **Do not read the slides.** The judge can read. Say something the slide does not.
- **Watch the judge's face.** If they look lost, drop to the type-A column
  immediately. If they lean in, go deeper.
- **One person speaks at a time.** Interruptions and cross-talk kill F10.

## E. What loses this criterion

- Running over time. **Rehearse with a timer.** Being cut off mid-sentence is the
  worst possible ending.
- Jargon in the first thirty seconds. "Particle filter" before minute two loses
  every type-A judge in the room.
- Defensiveness when challenged. The correct response to a hard question is
  visible pleasure — *"good question"* and then a straight answer.
- One person delivering everything. That is an F10 failure inside an F9 slot.
- Apologising for what isn't finished. State it neutrally as roadmap, once, and
  move on. Do not repeat it.

## F. The failure drill — rehearse this explicitly

| If | Then |
|---|---|
| App crashes | "Let me show you the recorded run" → backup video. **Under 5 seconds.** No debugging on stage. |
| Phone won't connect / dies | Backup video. Phone stays charged and in airplane mode from 8:45. |
| Laptop won't project | Pitch from the phone. All six must know the script without slides. |
| Live training fails | Skip to the committed figures. They are on disk. Never wait on a subprocess. |
| Judge asks something nobody knows | "I don't know — here's how we'd find out." Never guess. |
| Judge is hostile or dismissive | Stay warm, answer the question, do not argue. Hostility often tests composure, and composure is what F9 is measuring. |

**Everything must work with the venue wifi dead.** Airplane mode from the start —
it is both the privacy proof and the insurance.

## G. Pre-event checklist

- [ ] Phone charged, airplane mode, demo pre-warmed and tested that morning
- [ ] Backup video on the phone **and** the laptop **and** a USB stick
- [ ] Laptop charged, `verify_claims --demo-failure` tested, figures pre-generated
- [ ] Deck on laptop **and** as PDF on a USB stick **and** emailed to the leader
- [ ] Two timed full rehearsals completed with all six members
- [ ] Every member has answered five random Q&A-bank questions cold
- [ ] Formal dress confirmed: white shirt, black pants, all six

## H. Acceptance

- [ ] Full 3-act script written out with named speaking parts (see `F10`)
- [ ] Timed at ≤5:00 in two separate rehearsals
- [ ] Q&A bank printed; every member has drilled both columns
- [ ] Failure drill rehearsed — including the 5-second cut to backup video
- [ ] All six can deliver Act 1 alone if needed
