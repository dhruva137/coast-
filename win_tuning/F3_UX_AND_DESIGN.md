# F3 — User Experience & Design
*"UI/UX, accessibility, and inclusivity"* · Round 1 · judged off the deck (and the phone, if they pick it up)

---

## A. What this criterion actually rewards

Read the criterion carefully — it has **three** parts and most teams answer only
the first:

1. **UI/UX** — does it look and feel like a finished product?
2. **Accessibility** — can someone with a disability use it?
3. **Inclusivity** — can someone unlike the developers use it?

Parts 2 and 3 are where the points are, because almost every competing team will
show a pretty screenshot and stop. **We have an unusually strong inclusivity
story that falls out of the architecture for free** — and nobody thinks to claim
it. See §C. That alone is the difference between 7 and 10 here.

## B. UI/UX — current state and remaining work

Cursor has already rebuilt Drive around a proper `BottomSheetScaffold` with
FABs and `contentDescription` semantics throughout. The foundation is real. What
remains is polish and, more importantly, **the first five seconds**.

### 3.1 — The five-second screen
A judge holds the phone for ninety seconds. They will not read a manual, and they
may never press anything. So:

- **One tap from cold launch to the demo.** No login, no permission wall, no
  setup. If the first thing a judge sees is a permission dialog, we have lost
  the impression before the product renders.
- **A plain-language line, always on screen** during the demo:
  *"GPS is off. Position is coming from the phone's motion sensors + the road map."*
  Not jargon. This single sentence is what a non-technical judge takes away.
- **The handover must be visually loud.** The moment GNSS drops and IDR takes
  over is the entire pitch. Mode pill changes, colour changes, and it is
  unmissable from arm's length.
- **Permanent honesty label:** "REPLAY — real dataset, real estimator." It must
  be inside the same visual layer as the map, so no screenshot can crop it off.
  (Same rule as FIX-4 in `PHASE0_BLOCKING_FIXES.md`.)

### 3.2 — Restraint
One accent colour (`#00E0A4`); blue reserved exclusively for the GNSS track. No
other colours. Consistent type scale. Nothing smaller than 14sp. Generous tap
targets (≥48dp). If a control does not serve the ninety-second demo, move it into
the expanded sheet or delete it.

### 3.3 — Never show a broken signal
The confidence radius is measurably broken (−0.23 correlation with actual error).
It stays gated off. `mapfilter/summary.md` already says a near-zero correlation
makes the uncertainty "decorative and must not be shown to a user."
**Shipping a UI that deliberately hides a metric we could not validate is itself
a design-integrity story worth telling in Q&A.**

## C. Accessibility — concrete, checkable

Do these and say them. Each is a real change, not a claim:

- **Screen-reader labels on every interactive element.** Largely done — audit for
  gaps and make the announced strings meaningful ("Start navigation", not "button").
- **Contrast ratios ≥4.5:1** for all text on the dark theme. Measure it, record
  the numbers, put the measurement in `docs/ACCESSIBILITY.md`. A measured
  contrast table is checkable evidence; "we used a dark theme" is not.
- **Never encode meaning in colour alone.** The GNSS/IDR distinction must also
  differ by shape, label, or dash pattern — this covers colour-blind users and,
  usefully, also makes the deck survive greyscale printing.
- **Respect system font scaling.** Test at the largest accessibility font size and
  make sure nothing clips or overlaps.
- **Large touch targets** (≥48dp) — matters for motor impairment and for anyone
  using the app on a moving vehicle, which is our actual use case.
- **No reliance on audio.** Everything is visual; nothing requires hearing.

**Deliverable:** `docs/ACCESSIBILITY.md` with the measured contrast table, the
screen-reader coverage list, and the font-scaling screenshots. One slide line:
*"WCAG-aligned contrast, full TalkBack labelling, no colour-only signals."*

## D. Inclusivity — our hidden 10/10  ← do not skip this

This is the strongest and least obvious card in the entire deck, and it costs us
nothing because the architecture already delivers it. Four genuine inclusivity
properties, all of which fall directly out of design decisions we made for other
reasons:

| Property | Why it is inclusive | Source of the property |
|---|---|---|
| **Works with no internet** | Serves users with no data plan, poor rural coverage, or who cannot afford continuous data. Navigation is a safety function — it should not require a subscription to the network. | Fully on-device + offline MBTiles basemap |
| **Works on a cheap phone** | No flagship required, no dedicated hardware to buy. Our whole thesis is a ₹15,000 phone. | ONNX Runtime Mobile, tiny model, 8.3 µs/sample core |
| **Requires no account** | No sign-up, no identity, no literacy barrier, no exclusion of people without email or KYC. | Local-only auth stub, guest continue |
| **Costs the user nothing to run** | No map licence, no per-query cost, no ads, no data harvesting | OSM + MapLibre, zero cloud |

And the population framing: **the vehicles that lack built-in inertial navigation
are disproportionately the ones owned by people with less money** — older cars,
trucks, and India's very large two-wheeler fleet. Premium cars ship with INS.
Everyone else gets nothing. **We are building the navigation fallback for the
people the automotive industry did not build it for.**

That sentence is an F3 *and* F4 answer simultaneously, and it is true.

## E. The layered delivery

| Layer | Content |
|---|---|
| **L0** | A clean, dark, full-screen map screenshot on the deck that simply looks like a real product. |
| **L1** | "No login, no internet, no new hardware. It works on a cheap phone with no data plan." |
| **L2** | The inclusivity table (§D) + the measured accessibility numbers (§C). |
| **L3** | The phone in the judge's hand; TalkBack turned on; the contrast measurements. |

## F. Tasks

- **3.1** Five-second screen: one-tap demo from cold launch, plain-language line,
  loud handover, permanent REPLAY label inside the frame.
- **3.2** Restraint pass: one accent, type scale, ≥48dp targets.
- **3.3** Accessibility audit → `docs/ACCESSIBILITY.md` with measured contrast
  table, TalkBack coverage, large-font screenshots.
- **3.4** Non-colour redundancy for GNSS vs IDR everywhere, including the deck
  diagrams.
- **3.5** Add the inclusivity table to the deck. One slide element, four rows.
- **3.6** Take **three** high-quality screenshots for the deck: idle map, mid-blackout
  with the handover visible, expanded diagnostics sheet. Real device, real render,
  no mockups. These are what a judge who never touches the phone will score.
- **3.7** Apply FIX-4 from `PHASE0_BLOCKING_FIXES.md` — "MOCK — not live data"
  badge inside the web APK-preview frame.

## G. Language discipline

**Say:**
- "No login, no internet, no extra hardware, no data plan."
- "Full screen-reader labelling and measured 4.5:1 contrast."
- "We deliberately hide our uncertainty estimate because we measured it and it
  doesn't correlate with real error. We won't show a user a number we don't
  trust."

**Never say:**
- "Beautiful", "intuitive", "user-friendly" — unearned adjectives, and judge type
  B discounts them. Show the screenshot instead.
- "Accessible" without the measurements behind it.
- That the app has been used by real users. It has not.

## H. The question that decides this criterion

> *"Has anyone outside your team actually used this?"*

Answer honestly and immediately — this is a known gap and pretending otherwise is
fatal:

> "No. It has run on our own devices and on recorded real-world data, not with
> outside users. What we did instead was remove the things that usually block a
> first-time user — there's no login, no setup, no network requirement, and one
> tap from launch to a working demo. You're holding it now; that's the first
> external test."

Handing the phone over at that exact moment is the strongest possible move, and
it converts an admitted weakness into a demonstration.

## I. Acceptance

- [ ] Cold launch → working demo in one tap, airplane mode, no permissions
- [ ] Plain-language explainer line always visible during demo
- [ ] REPLAY label inside the map layer, unccroppable
- [ ] `docs/ACCESSIBILITY.md` with measured contrast + TalkBack coverage
- [ ] No colour-only signals anywhere, deck included
- [ ] Inclusivity table on a slide
- [ ] Three real-device screenshots in the deck
- [ ] Confidence radius still gated off
