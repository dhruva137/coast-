# 04 — COAST Command: the laptop dashboard

**Design species:** fleet operations console. Its job is to **reveal**
information. Reference points: Linear, Vercel, Stripe, Grafana — dense,
structured, dark, information-first. **Not** a stretched phone app.

This is the surface the judges watch on the big screen. It carries F5 (technical
execution), the fleet/logistics use case, and the live-training proof.

---

## A. The four screens

One route each. No nesting, no hamburger menu, no hidden navigation.

| Route | Name | Question it answers |
|---|---|---|
| `/` | **Mission** | What is this, and how do I get the app? *(public landing + APK + QR)* |
| `/fleet` | **Fleet** | Where is every paired device right now, and where has it been? |
| `/train` | **Training** | Is the model real, and is it learning? |
| `/evidence` | **Evidence** | Are the claims true? *(the measured ledger + source files)* |

**Fleet is the hero.** It should be what is on screen when judges walk up.

---

## B. Fleet — the operations view

```
┌────────────┬──────────────────────────────────────────────┐
│  DEVICES   │                                              │
│            │                                              │
│ ● Judge-1  │              MAP (dominant)                  │
│   IDR 34s  │                                              │
│   12 km/h  │     ── GNSS track (blue)                     │
│            │     ── IDR track (teal)                      │
│ ● Judge-2  │     ◆  live device markers, labelled         │
│   GNSS     │                                              │
│   0 km/h   │                                              │
│            │                                              │
│ ○ Truck-7  │                                              │
│   offline  │                                              │
│   2m ago   │                                              │
├────────────┼──────────────────────────────────────────────┤
│ + Pair     │  TIMELINE ──────●────────────────────────    │
│   device   │  09:41  Judge-1  GNSS → IDR   (tunnel)       │
└────────────┴──────────────────────────────────────────────┘
```

**Design rules:**

- **Map dominates**, roughly 70%. Device list is a fixed-width left rail.
- **One colour per device**, assigned on pairing, used consistently for its
  marker, its track, and its list row. This is how a viewer tracks "which one is
  mine" without reading labels.
- **Track segments are styled by mode, not by device:** GNSS segments solid blue,
  IDR segments solid teal. **A path that visibly changes colour when the phone
  entered a dead zone is the single most legible thing on this screen** — a
  non-technical judge understands it instantly without a legend.
- **The timeline is the narrative device.** Every mode transition is an event:
  `09:41 Judge-1 GNSS → IDR`. This is what turns a map into a *story* — where a
  device went dark and how it came back.
- **Offline devices stay visible**, greyed, with "last seen". Never disappear a
  device — that reads as a bug.

### Why this matters beyond the demo

This screen *is* the logistics/security use case the user described: a truck
carrying sensitive cargo, theft detection, path auditing. The judge sees a fleet
console, not a science project — and the mode-coloured path directly demonstrates
"we kept tracking it through the tunnel where everyone else loses it."

**The narration:** *"This is what a logistics operator sees. That blue line is
GPS. Where it turns teal, that vehicle was in a tunnel — every other system loses
the vehicle there. We don't. If that truck were carrying something valuable,
that teal section is exactly where you'd want visibility."*

---

## C. Mission — the public landing page

The first thing a judge sees. It must do three jobs in one screen, with no
scrolling required to reach the QR.

1. **What this is** — one sentence, large. *"Navigation that keeps working when
   GPS doesn't."*
2. **Get the app** — a big QR code linking to the GitHub Release, plus a direct
   download button. One line under it: *"Android · 34 MB · no account needed."*
3. **Pair your phone** — the session QR (§`02_PLATFORM_ARCHITECTURE.md` §C) with
   a live status: *"0 devices paired"* → *"Judge-1 connected"* the instant it
   lands. **That state change must be visible and animated** — it is the payoff
   moment of the whole pairing flow.

Below the fold: the three headline numbers with their source files, and a link to
Evidence.

**Keep it to one screen of content.** A landing page that requires scrolling to
find the QR has failed.

---

## D. Training — see `05_LIVE_TRAINING_VISUALIZATION.md`

The per-epoch trajectory replay is specified in full there. Summary: the map is
the hero, curves support it, metrics sit in a fixed rail with tabular figures,
and every element's space is reserved before the run starts so nothing shifts.

---

## E. Evidence — the honesty surface

A plain, dense table. Every claim, its value, its source file, and the command
that recomputes it — read live from `CLAIMS.json`.

**Include the failures.** GNSS+INS fusion 1.07×. Alignment 32% → 32%. Speed model
losing to hold on per-window RMSE. Confidence radius −0.23, gated off.

**Why this screen exists:** it is the visual form of our whole posture. A judge
who clicks here and finds our negative results listed alongside our wins will
believe the wins. One who finds only wins will not.

Put a **"Verify"** button that runs `tools/verify_claims.py` and shows the output
live, including the `--demo-failure` mode catching a planted number.

---

## F. The visual system

**Type.** One family (Inter, or the system stack). Four sizes only: 32 / 20 / 14 /
12. **Tabular figures everywhere a number updates** — a metric that changes width
as digits change is the most common tell of an amateur dashboard.

**Colour.** Near-black background (`#0A0B0D`), one elevated surface (`#141619`),
one border (`#232629`). Accent `#00E0A4`. GNSS blue `#4A9EFF`. Warning amber, error
red — used *only* for genuine warnings and errors, never decoratively.

**Space.** 8px grid, no exceptions. Panel padding 24px. Related items 8px apart,
unrelated groups 24px.

**Density.** This is a dashboard — dense is correct. But density comes from
*small, well-aligned type*, not from cramming. Whitespace between groups is what
makes density readable rather than cluttered.

**Motion.** 150–250 ms, ease-out. Values that change animate; layout never
shifts. New devices slide in. Nothing bounces, nothing spins.

**Light mode:** build it, but dark is the demo. An operations console is a
dark-mode product.

---

## G. The empty states — design these, they are half the demo

Judges will see empty states, because at the moment they walk up nothing is
paired yet. An unstyled empty state destroys the impression instantly.

| State | What it must show |
|---|---|
| No devices paired | The pairing QR, large, with *"Scan this with the COAST app to see your phone here."* **The empty state IS the call to action.** |
| Device paired, no fix yet | The device row with a pulsing indicator: *"Waiting for first position…"* |
| Training not started | The full layout with axes drawn and a **Train** button. Never a blank panel. |
| Backend unreachable | An explicit, calm error naming the endpoint tried. **Never remembered numbers** — this is FIX-2 in `win_tuning/PHASE0_BLOCKING_FIXES.md`. |
| No results file | *"Could not read `lab/stress/results/mapfilter/report.json` — no measured numbers to show."* |

---

## H. Build order

1. **Fleet** — map, device rail, mode-coloured tracks, multi-device. *The hero.*
2. **Mission** — landing with both QRs and live pairing status.
3. **Training** — per-epoch trajectory (see `05`).
4. **Evidence** — table from `CLAIMS.json` + the Verify button.
5. Empty states for all of the above.
6. The visual system applied consistently.
7. Light mode.

**If only one thing gets built: Fleet.** It carries the use case, the pairing
payoff, and the mode-transition story in a single screen.
