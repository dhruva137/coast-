# F7 — Business Viability
*"Market potential, revenue model, and affordability"* — note: **"(if applicable)"** · Round 1

---

## A. Read the criterion carefully

It says **"if applicable."** That matters. This is a government/space problem
statement, and a team that turns it into a startup pitch can actually score
*worse* — it reads as having missed the point of the problem statement.

**Our posture: treat this as "is this economically sustainable and affordable?"
rather than "how do you get rich?"** Show one clean slide element that proves we
have thought about it commercially, then get back to the mission framing.

**One clean answer beats three cluttered ones here.** Do not over-invest.

## B. The affordability argument — lead with this, it is the strongest part

Affordability is explicitly in the criterion and it is where we are genuinely
exceptional:

| Cost | Amount |
|---|---|
| To the end user | **₹0** — free app, no subscription, no ads, no data sale |
| Additional hardware | **₹0** — runs on the phone they own |
| Map licensing | **₹0** — OpenStreetMap |
| Our marginal cost per additional user | **≈₹0** — no cloud, no per-query cost, no server |

**The line:** *"Our marginal cost per user is effectively zero, because there is
no server. That's not a business model choice — it's an architectural one, and it's
why this can be free for the people who need it most."*

That single fact makes every other business question easy, and it ties directly
back to the F3 inclusivity and F6 sustainability arguments. **Same architecture,
three criteria.**

## C. Revenue paths — three, one line each, all labelled as estimates

We are not asking anyone to believe a financial model. We are showing that viable
paths exist and that we know which is which.

### 1. SDK licensing to OEMs and Tier-1s
Phone manufacturers and automotive suppliers who want GNSS-denied continuity
without adding hardware. Licence the positioning core.
*Anchor: a per-device royalty, in the range that navigation software components
typically command. **Label as an estimate — we have not validated pricing.***

### 2. Fleet and logistics B2B
Operators who need continuous tracking through tunnels, ports, and multi-level
warehouses without retrofitting hardware to every vehicle. Per-vehicle-per-month
SaaS on top of the free core.
*This is the most credible near-term revenue path, because the buyer already pays
for telematics and the value is measurable to them.*

### 3. Insurance telematics
Usage-based insurance depends on continuous trip data; GNSS gaps corrupt the
record. Sell the gap-filling layer.
*Longer sales cycle, regulated buyer — say so.*

**Public-good track (name it explicitly):** the consumer app stays free.
Emergency services and public transit use it at no cost. For an ISRO-adjacent
audience, stating that the mission use is free is worth more than a revenue
projection.

## D. Market sizing — one verified number, not a TAM cascade

Do **not** build a TAM/SAM/SOM pyramid. Judges discount them, and ours would rest
on unverified data.

Use exactly one verified anchor:
> India sold **1,96,07,332 two-wheelers in FY2024-25** — 4.6× passenger-vehicle
> sales (SIAM, verified). None of them ship with an inertial navigation stack.
> *(The second sentence is our inference — label it.)*

That is enough. It sizes the opportunity honestly in one line.

**Banned:** cumulative registered-vehicle counts (not verified to primary),
any revenue projection, any user-growth curve, "₹X crore market by 20YY" figures.

## E. Why we are defensible (if asked)

A sharp judge may ask what stops someone copying it. Honest answer:

> "The idea isn't secret — map-aided inertial navigation is established doctrine
> in aerospace. What's hard is the measured engineering: knowing that post-hoc
> snapping *hurts* (0.98×) while in-loop constraint helps (2.02× lower median
> error), and having the benchmark harness to prove it on real data with vehicle
> ground truth. The moat is the evaluation infrastructure, not the algorithm."

That is true, it is modest, and it demonstrates commercial realism — which scores
better than claiming a patent-pending breakthrough.

## F. The layered delivery

| Layer | Content |
|---|---|
| **L0** | "₹0 to the user. ₹0 marginal cost to us." |
| **L1** | "It's free for users because there's no server to pay for. We'd make money licensing the core to manufacturers and fleets." |
| **L2** | The affordability table + three revenue paths + the one verified market number. |
| **L3** | Unit economics, the defensibility answer, the public-good track. |

## G. Tasks

- **7.1** `win_tuning/BUSINESS_MODEL.md`: the affordability table, three revenue
  paths with one estimate anchor each (clearly labelled as estimates), the single
  verified market number, the defensibility answer.
- **7.2** **One** slide element only. Do not give this more deck space than F1 or
  F4 — it is the "if applicable" criterion and over-weighting it signals we
  misread the problem statement.
- **7.3** State the public-good track explicitly: consumer app free, emergency
  services free.

## H. Language discipline

**Say:**
- "Marginal cost per user is effectively zero — there's no server."
- "Free for users, licensed to manufacturers and fleets."
- "That's an estimate; we haven't validated pricing with buyers."

**Never say:**
- Any revenue projection or market-size figure that is not in
  `RESEARCH_GLOBAL_CONTEXT.md` with a verified source.
- "Disrupt", "unicorn", "10x market".
- "Patented" or "patent pending" — we have filed nothing.
- That we have customers, pilots, or LOIs. We have none.

## I. The question that decides this criterion

> *"How will you actually make money?"*

> "The consumer app is free and stays free — that's deliberate, because the people
> who most need a fallback are the ones who can least afford hardware. Revenue
> comes from licensing the positioning core: to handset and automotive suppliers
> who want GNSS-denied continuity without adding a sensor, and to fleet operators
> who need continuous tracking through tunnels. The reason we can afford to give
> the consumer version away is architectural — there's no server, so an extra user
> costs us nothing."

## J. Acceptance

- [ ] `BUSINESS_MODEL.md` written, estimates labelled as estimates
- [ ] Exactly one slide element, proportionate to "if applicable"
- [ ] Only the SIAM figure used for market size
- [ ] Public-good track stated
- [ ] No projections, no TAM pyramid, no patent claims
