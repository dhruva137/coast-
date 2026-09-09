# F4 — Impact & Usefulness
*"Problem-solution fit, potential impact, and multiple use cases"* · Round 1

---

## A. What this criterion actually rewards

Three parts, and the third is where teams lose points:

1. **Problem-solution fit** — is this a real problem, and does this actually solve it?
2. **Potential impact** — how many people, how much does it matter?
3. **Multiple use cases** — does it generalise, or is it a one-trick demo?

The trap in part 3: teams list ten use cases and score *lower*, because a long
list reads as unfocused. **Depth beats breadth. One vivid primary use case plus a
credible ladder outscores ten bullets.**

## B. The problem, made undeniable

Use `RESEARCH_GLOBAL_CONTEXT.md` — every number here is sourced there.

**Layer 1 — the everyday problem everyone in the room has had:**
> "You've all had this happen. You're in a tunnel or an underground car park, and
> the blue dot freezes and jumps. That's GPS failing, and there is no fallback."

Universal, instantly understood, needs no expertise. This is the opening line.

**Layer 2 — it's not just inconvenience, it's a growing global threat:**
- GPS **spoofing incidents up 193%, jamming up 67%** in 2025 vs 2023 (IATA)
- **122,607 flights** across 365 airlines hit by GNSS interference in four months
  over the Baltic (as reported to ICAO)
- GPS signal-loss events **up 220% between 2021 and 2024** (IATA)

**Layer 3 — the India-specific, ISRO-relevant framing:**
- India's own constellation is mid-rebuild: the Government told Parliament in
  **July 2026** that NavIC "cannot provide standalone positioning service" with
  three operational satellites against a minimum of four — with NVS-03 ready for
  launch and NVS-04/05 in advanced realisation.
  **Read the handling rules in `RESEARCH_GLOBAL_CONTEXT.md` §0.1 before saying
  this out loud.** Frame as national interest, never as criticism, always paired
  with the recovery.
- India's GNSS-denied surface area is growing fast: Atal Tunnel 9.02 km, Zojila
  over 30 km by 2028, Kolkata's underwater metro, the Mumbai–Ahmedabad HSR
  undersea tunnel.

## C. Who this is for — the honest population argument

**Primary: the vehicles nobody built a fallback for.**

- India sold **1,96,07,332 two-wheelers in FY2024-25** alone — 4.6× passenger
  vehicle sales (SIAM, verified).
- Premium cars ship with built-in inertial navigation. Two-wheelers, older cars,
  and trucks do not. *(That last clause is our inference — label it as reasoning,
  not a sourced fact.)*
- Automotive dead reckoning as sold by the industry (u-blox ADR) needs
  **wheel-tick sensors the vehicle must provide**. A rider with a phone in their
  pocket has none.

**The sentence that carries F4 — and doubles as an F3 inclusivity answer:**
> *"The vehicles without a navigation fallback are disproportionately the ones
> owned by people with less money. Premium cars get inertial navigation as
> standard. Everyone else gets a frozen dot. We're building the fallback for the
> people the industry didn't build it for."*

**And the competitive line:**
> *"Google's answer to tunnels is Bluetooth beacons someone has to physically
> install in the tunnel. Off by default, Android-only, and no Indian city is on
> the deployment list. Ours needs nothing installed anywhere."*
> (Attribute to trade press — no official Google page was located.)

## D. The use-case ladder — five rungs, one scenario each

Present as a ladder (increasing stakes), not a list. One concrete sentence per
rung. **Do not add a sixth.**

| Rung | Who | The concrete scenario |
|---|---|---|
| **1. Everyday navigation** | Any rider or driver | The blue dot keeps moving through the tunnel instead of freezing and jumping you onto the wrong exit. |
| **2. Emergency response** | Ambulance, fire | An ambulance in an underpass doesn't lose its position at the moment dispatch most needs it. |
| **3. Logistics & fleet** | Trucking, delivery | Continuous tracking through tunnels and multi-level warehouses without fitting hardware to every vehicle. |
| **4. Sovereignty / jamming** | National interest | When the signal is denied — deliberately — positioning that needs no signal at all keeps working. |
| **5. Beyond roads** | Rail, marine, planetary | Same filter, different manifold. See `SCALABILITY_BEYOND_ROADS.md`. |

Rung 5 is where the Chandrayaan-3 / Perseverance material belongs — and it is
sourced. It is our strongest closing beat with this audience.

## E. The layered delivery

| Layer | Content |
|---|---|
| **L0** | One image: a frozen blue dot in a tunnel vs a moving one. |
| **L1** | "Everyone here has watched their map freeze in a tunnel. For an ambulance, that's not an inconvenience." |
| **L2** | The three sourced threat numbers + the two-wheeler figure + the use-case ladder. |
| **L3** | The NavIC transition-window argument, the policy landscape, the cross-domain roadmap. |

## F. Tasks

- **4.1** Build `win_tuning/IMPACT_MODEL.md`: every population and threat number
  with its source URL, each entered in `CLAIMS.json` as `confidence: external`.
  **No number without a link.** Pull only from `RESEARCH_GLOBAL_CONTEXT.md` — the
  banned list there is binding.
- **4.2** Put the use-case ladder on the impact slide as five rows. Not a
  paragraph, not ten bullets.
- **4.3** One sourced threat statistic in large type on the problem slide. One,
  not three — pick the IATA 193% spoofing figure.
- **4.4** Add the "built the fallback for the people the industry didn't build it
  for" line to the pitch script. It is the emotional centre of the deck and it is
  true.

## G. Language discipline

**Say:**
- "IATA reported spoofing incidents up 193% in 2025 versus 2023."
- "India sold 19.6 million two-wheelers last financial year — 4.6 times
  passenger-vehicle sales."
- "Automotive dead reckoning needs wheel sensors. A phone in a pocket has none."
- "Our credible claim is short-to-medium outages, and we say so."

**Never say:**
- "This will save lives." Unearned and unmeasurable. Say *"an ambulance in an
  underpass keeps its position"* — concrete, and lets the judge draw the
  conclusion themselves.
- "Millions of users." We have zero users.
- "NavIC is broken" or any phrasing repeatable as criticism of ISRO.
- Any banned number from `RESEARCH_GLOBAL_CONTEXT.md` §5 — especially the NavIC
  smartphone "mandate" (it is a stated intent, not a notification) or cumulative
  two-wheeler registrations.

## H. The questions that decide this criterion

> *"Doesn't Google Maps already do this?"*

> "Not with software. Their tunnel fix is Bluetooth beacons physically installed
> in the tunnel — off by default, Android-only, and as far as trade reporting
> shows, no Indian city is on the deployment list. It needs the tunnel operator
> to buy and install hardware. Ours needs nothing installed anywhere, because the
> map and the sensors are already in your pocket."

> *"How long can you actually keep position without GPS?"*

> "Honestly: short-to-medium outages. The industry's own framing is that
> untethered dead reckoning — no wheel sensors, which is our case — degrades
> faster than wheel-tick systems past about a minute. What the map-in-loop gives
> us is that lateral error stops growing, so we stay on the right road. What we
> don't fully fix is how far along that road you are. That's our stated next
> problem, and it's the same one the rail industry solves with trackside beacons."

## I. Acceptance

- [ ] `IMPACT_MODEL.md` with every number sourced and in `CLAIMS.json`
- [ ] Use-case ladder on a slide, five rows
- [ ] One threat statistic in large type on the problem slide
- [ ] NavIC framing rehearsed against `RESEARCH_GLOBAL_CONTEXT.md` §0.1 rules
- [ ] No banned numbers anywhere
- [ ] Every member can answer §H
