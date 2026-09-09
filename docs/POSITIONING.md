# COAST positioning — what we say we are

**Written:** 9 Sep 2026. Supersedes the two-wheeler-first framing in the older
README and project bible.

## The correction

Earlier material led with "the first smartphone dead-reckoning system for
**leaning two-wheelers**". Re-reading the problem statement 26168 in full, that
is the wrong headline. Two-wheelers are named, but as *one of three* vehicle
classes, and the theme is "Smart Vehicles" — general, not two-wheeler.

The exact PS sentence:

> "the vast majority of vehicles on Indian roads — including **commercial
> trucks, older cars, and millions of two-wheelers (motorcycles/scooters)** —
> rely solely on the driver's smartphone."

What unifies that list is not "two wheels". It is **"rely solely on the driver's
smartphone"**. That is the real target: *any vehicle whose only navigation
device is a phone.* And the dataset ISRO gave us, IO-VNBD, is entirely **cars**.

## The headline, corrected

> **COAST turns any smartphone into a self-contained navigator that keeps
> working when GNSS dies — no OBD-II, no extra hardware, no network.**

Two-wheeler / lean-awareness moves from *the pitch* to *a differentiator*:

- **Primary claim (general, matches the PS and the dataset):** smartphone-only
  IDR with map-constrained dead reckoning, an AI speed/vibration filter, and
  GNSS+INS fusion. Evaluated on IO-VNBD (cars) against CAN ground truth.
- **Differentiator (ours, defensible, optional):** the estimator also handles
  the *leaning* single-track case that published vehicle-DR work ignores, via a
  coordinated-turn solver. This is a bonus we can additionally demonstrate, not
  the thing the submission stands on.

## Why this framing is stronger, not weaker

1. **It matches what we can prove.** Every measured number we have — the 2.02x
   map-in-loop result, the heading ceiling, the benchmark rows — is on IO-VNBD
   cars. Leading with two-wheelers while all our evidence is cars invites the
   obvious question "where is your two-wheeler data?", to which the honest
   answer is "we have none yet". Leading with the general case, the evidence
   backs the claim.
2. **It is a bigger market, stated ISRO's way.** Trucks + older cars +
   two-wheelers + the metro/tunnel civilian cases is the whole road network, not
   a segment.
3. **The lean work still lands, as a "we also handle the hard case nobody else
   does" moment** — which is a strength precisely because it is offered, not
   leaned on.

## One-liners by audience

- **To an ISRO scientist:** "GNSS-denied inertial navigation on a consumer MEMS
  phone — the same discipline you fly, at four orders of magnitude worse sensor
  noise, constrained by a road map instead of a star tracker."
- **To an industry judge:** "When a delivery rider enters a tunnel, the dot
  keeps moving and the ETA stays honest — no hardware, no OBD port, works on the
  phone they already have."
- **To a user:** "Your map doesn't freeze in the parking garage anymore."

## What to change in older docs

- README: replace the two-wheeler-first novelty list with the general headline
  above; keep lean-awareness under a "differentiators" subhead.
- Any slide that opens on two-wheelers: open on "smartphone-only vehicles",
  bring two-wheelers in as the hard case we additionally handle.
- Keep `docs/ISRO_RELEVANCE.md` as the "why ISRO cares" companion; it already
  frames the general case correctly.
