# F6 — Sustainability & Future Scope
*"Long-term viability & eco-friendly practices"* · Round 1

---

## A. What this criterion actually rewards

Two things that are usually answered badly:

1. **Long-term viability** — will this still exist in five years, or does it die
   when the hackathon ends?
2. **Eco-friendly practices** — the criterion asks about environmental impact,
   and most software teams either skip it or invent something ("we save fuel by
   optimising routes!") that a judge immediately discounts.

**We have a genuine, structural environmental argument that costs us nothing**
because it falls out of the architecture. Most software projects cannot make it.

## B. The eco argument — real, and rare for software

### B1. Zero additional hardware — the strong claim

The alternative way to solve this problem is a dedicated inertial navigation
dongle in every vehicle. Compare:

| | Dedicated INS hardware | COAST |
|---|---|---|
| Devices manufactured | One per vehicle | **Zero** |
| Embodied carbon of deployment | One device's worth per vehicle | **Zero** |
| E-waste at end of life | One device per vehicle | **Zero** |
| Rare-earth / lithium demand | Yes | **None** |

**The claim, worded honestly:** *"The marginal hardware required to deploy this to
one more user is zero. We run on a phone they already own and a sensor that is
already in it. The most sustainable device is the one nobody had to manufacture."*

That is `confidence: derived` reasoning, not a measured LCA. **Do not attach a
fabricated tonnage figure to it.** The qualitative argument is strong on its own;
a made-up number would weaken it.

### B2. Zero server energy per query

Fully on-device inference means no data centre round-trip. A cloud-based
positioning service burns energy per request, per user, forever. Ours burns none,
because there is no server.

Again: state it qualitatively unless you can compute it. If you *can* compute a
defensible figure (e.g. energy per inference on-device × queries), show the
arithmetic and mark it `confidence: derived`.

### B3. Extends the useful life of existing phones

The model is tiny and the core runs at 8.3 µs/sample. It works on cheap and older
hardware, which means it does not push anyone toward a new phone. Software that
runs well on old devices is a genuine sustainability property.

**What NOT to claim:** fuel savings, emissions reductions from better routing, or
any "we reduce congestion" argument. We have not measured any of it and a judge
will know it is decoration.

## C. Long-term viability

### C1. No dependency that can be withdrawn
The most common way a student project dies is a dependency that gets priced,
deprecated, or rate-limited. Ours has none:

- **OpenStreetMap** — open data, no API key, no billing, cannot be revoked.
- **MapLibre** — open source, community-governed (forked precisely because a
  proprietary maps SDK changed its licence).
- **ONNX** — open standard, multi-vendor.
- **No cloud account, no paid API, no vendor lock-in anywhere in the runtime.**

**One line:** *"There is no bill that can arrive and no key that can be revoked.
Nothing in the runtime depends on a company's continued goodwill."*

### C2. The roadmap, honestly staged
Distinguish clearly between done, in progress, and future. A roadmap that
pretends everything is nearly done reads as naive; one that stages honestly reads
as planned.

| Stage | Item | Status |
|---|---|---|
| Done | Map-in-loop, measured 2.02× lower median error | **Measured** |
| Done | Edge engine, 120,305 Hz | **Measured** |
| Done | Mount-invariant preprocessing (EqNIO-style) | **Measured — mixed result, reported as such** |
| Next | Along-track error correction (the honest gap, see below) | Roadmap |
| Next | Real field drives on two-wheelers | Roadmap |
| Next | Calibrated uncertainty (current signal is broken, −0.23) | Roadmap |
| Future | Other constraint manifolds — rail, corridor, marine | **Interface exists; corridor implemented + tested** |

### C3. Future scope that is already code, not prose

**This is the differentiator for this criterion.** Every team's "future scope"
slide is a wish list. Ours points at a shipped interface:

> The map constraint is a plug-in (`ConstraintManifold`). We ship the road-graph
> implementation and demonstrate a corridor implementation — the same 1-D
> along-the-path state space that the peer-reviewed rail literature uses. The
> algorithm never knew it was a road.

See `SCALABILITY_BEYOND_ROADS.md` for the sourced cross-domain evidence and the
strict limits on what we may claim (we have **not** validated rail, underwater, or
planetary navigation — those are roadmap).

### C4. The honest technical gap, stated as the next milestone
Map constraint kills **lateral** error. It does not correct accumulated
**along-track** error — right road, wrong distance along it. This is a known open
problem in the literature, and it is exactly why the rail industry still installs
physical balises to reset odometry.

Putting this on the future-scope slide is a *strength*: it shows we know which
error our method kills and which it does not, and our roadmap addresses the right
thing.

## D. The layered delivery

| Layer | Content |
|---|---|
| **L0** | One graphic: "Devices manufactured to deploy this: 0." |
| **L1** | "The most sustainable hardware is the hardware nobody had to build. We run on the phone you already own, with no server and no subscription." |
| **L2** | The hardware-comparison table + the no-revocable-dependency list. |
| **L3** | The staged roadmap, the `ConstraintManifold` interface, the along-track gap. |

## E. Tasks

- **6.1** `win_tuning/SUSTAINABILITY_MODEL.md` — the zero-hardware argument, the
  no-server argument, the old-device argument. Compute what can be computed
  (`confidence: derived`, show the arithmetic); state the rest qualitatively.
  **No invented figures.**
- **6.2** Add the zero-hardware comparison table to the deck.
- **6.3** Add the staged roadmap table with honest status labels.
- **6.4** Add the "no revocable dependency" line — it is a viability argument most
  judges have seen projects fail on.
- **6.5** Put the along-track limitation on the future-scope slide as the named
  next milestone.

## F. Language discipline

**Say:**
- "Zero devices manufactured. Zero e-waste. Zero server energy."
- "No API key, no billing, no vendor who can change the terms."
- "Map-in-loop fixes sideways error. It doesn't fix how far along the road you
  are — that's the next problem, and it's the same one rail solves with balises."

**Never say:**
- Any carbon, fuel, or emissions figure we did not compute.
- "Carbon neutral", "green technology", "eco-friendly" as bare adjectives.
- That the corridor manifold validates rail or marine navigation.

## G. The question that decides this criterion

> *"What happens to this project after the hackathon?"*

> "Nothing has to happen for it to keep working — that's the point. There's no
> server to pay for, no API key that expires, no vendor who can change terms. It
> runs offline on hardware people already own. And the next step isn't a rewrite:
> the map constraint is already an interface, so extending it to a rail corridor
> or a shipping channel is a new implementation of an existing type, not a new
> project."

## H. Acceptance

- [ ] `SUSTAINABILITY_MODEL.md` with computed figures marked `derived` and
      qualitative claims left qualitative
- [ ] Zero-hardware table on the deck
- [ ] Staged roadmap with honest status labels
- [ ] Along-track gap named as the next milestone
- [ ] No invented environmental numbers anywhere
