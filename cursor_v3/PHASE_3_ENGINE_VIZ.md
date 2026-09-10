# Phase 3 — Visualise the engine

**The complaint:** *"You have not visualized the engine at all. You just added
some data analysis. I thought you would visualize the engine itself, like
something is moving."*

Correct. The current Engine tab is three bar charts of benchmark numbers. That is
a report, not a visualisation.

**Read `01_THE_ENGINE.md` §D before starting.** You are drawing a specific
mechanism and it has to be the real one.

---

## The idea

> **Show the belief, not the dot.**

Every navigation demo shows a moving marker. Ours has something nobody else can
show: **a particle cloud living on a road graph** — spreading when the filter is
uncertain, forking at a junction, and collapsing the instant the motion resolves
which road you took.

That is the algorithm, visible. It is genuinely beautiful, it is completely
honest, and it explains the entire thesis without a word of narration: a
non-technical judge sees a cloud of possibilities narrow to one road, and
understands *"the map is doing the work."*

**This is the single highest-value thing in the whole programme.** Budget
accordingly.

---

## 3.1 — Export a filter trace (do this first, it gates everything)

The console cannot draw what the lab does not record. Add trace export to the
map-in-loop filter.

**New:** `lab/stress/export_filter_trace.py` →
`lab/stress/results/traces/<drive>_<t0>.json`

For one real IO-VNBD outage, at every filter step:

```jsonc
{
  "meta": {
    "drive": "S-M", "t0_s": 1830.0, "duration_s": 60, "hz": 10,
    "n_particles": 180,
    "graph": "maps/graphs/iovnbd_midlands.graph.npz",
    "source": "real IO-VNBD outage, CAN speed truth",
    "built_from_drive_data": false
  },
  "graph": { "nodes": [[lat,lon],...],
             "edges": [{"id":0,"a":0,"b":1,"pts":[[lat,lon],...]}] },
  "steps": [{
    "t": 0.0,
    "particles": [{"e":12,"s":40.2,"w":0.004,"lat":..,"lon":..}],
    "estimate":  {"lat":..,"lon":..,"edge":12,"heading":..},
    "truth":     {"lat":..,"lon":..},
    "free_dr":   {"lat":..,"lon":..},
    "speed_mps": 11.4, "yaw_rate": -0.02,
    "n_eff": 96.2,          // effective sample size — the uncertainty signal
    "resampled": false,
    "edge_posterior": [[12,0.71],[13,0.22],[41,0.07]]
  }]
}
```

Rules:
- **Downsample particles for transport, never invent them.** If you ship 180 of
  500, record `"particles_shown": 180, "particles_total": 500` and label it.
- Cap the file at a few MB. 60 s at 10 Hz × 180 particles is fine.
- Export **three** traces: a clean straight run, one with a real junction
  ambiguity, and the worst outage in the set. The third one matters most —
  see §3.5.
- `n_eff` (effective sample size) is the honest uncertainty signal. Record it.
  **Do not resurrect the spread-based confidence radius** — it measured −0.23
  correlation with real error and is gated off for that reason.

## 3.2 — The particle canvas

New view `/engine`. Canvas, 60 fps, no dependencies.

**Layers, back to front:**
1. **Road graph** — every edge in view, thin, `--line`. This is the manifold.
   Nothing may render outside it.
2. **Edge posterior** — edges tinted by probability mass. The road the filter
   currently believes glows faintly in `--accent`. At a junction two roads glow
   at once — *that is the multi-modality a Kalman filter cannot represent*, and
   it is visible.
3. **Particles** — one dot each, radius and alpha from weight. Additive blending
   so density reads as brightness.
4. **Free-DR ghost** — `--bad`, dashed, walking off the road network. The
   counterfactual, always on screen.
5. **Truth** — white, thin.
6. **Estimate** — `--accent`, solid, the weighted mean.

**The moments to make legible** — these are the beats of the demo:
- **Fork.** Approaching a junction the cloud splits down each outgoing edge.
  Slow the replay automatically to 0.4× for 2 s when the edge posterior has ≥2
  edges above 0.15. *The animation should linger exactly where the algorithm is
  interesting.*
- **Collapse.** When motion resolves it, the losing branch fades over ~400 ms.
- **Resample.** On a resample step, a brief ripple. Small; it must not become
  decoration.
- **Divergence.** The ghost leaving the road is the whole pitch. Once it is more
  than ~30 m off, draw a thin connector between ghost and estimate with the live
  gap in metres.

**Transport controls:** play/pause, scrub, 0.25×–4×, step-frame, loop. A judge
will ask "can you show that again" — make it one click.

## 3.3 — The telemetry rail

Beside the canvas, live and tied to the current frame. Every value from the
trace, none computed for show:

- **Effective sample size** — a bar, `n_eff / n_particles`. Watch it crater at a
  junction and recover. This is the filter's real confidence.
- **Edge posterior** — top 3 edges with probability bars, live.
- **Speed** — AI model output vs CAN truth, two values, tabular.
- **Yaw rate** — a small rolling sparkline.
- **Error now** — estimate-vs-truth and ghost-vs-truth, in metres, side by side.
  The gap between those two numbers is the product.
- **Mode** — GNSS / IDR pill, flipping at outage onset.

## 3.4 — The dataflow strip

A compact diagram under the canvas showing the actual pipeline (§D of
`01_THE_ENGINE.md`), with the current sample flowing through it:

```
IMU 100Hz ──▶ AVNet ──▶ ┌ PREDICT ─▶ WEIGHT ─▶ RESAMPLE ┐ ──▶ position
   accel      speed     │      ▲                         │
   gyro ────────────────┘   road graph                   │
                                                          └─ n_eff
```

Each block pulses as it processes. Not decorative — the pulse rate is the real
step rate, and the whole strip stalls if the trace stalls. **A judge should be
able to point at any block and ask what it does, and the label should answer.**

## 3.5 — The failure trace, shown deliberately

Include a **"Worst case"** button that loads the trace where COAST does badly.

This is not modesty, it is strategy. Every team shows their best run. Showing the
one where our own estimate drifts — with the along-track error visibly growing
while lateral stays pinned to the road — demonstrates that we know precisely
which error our method kills and which it does not. It is the visual form of the
limitation we already volunteer, and it makes everything else believable.

Caption it: *"Map-in-loop pins us to the right road. It does not fix how far
along it we are. That is our named next problem."*

## 3.6 — The throughput panel (keep, but subordinate)

Keep the measured C++ benchmarks, now below the visualisation:
- Lead with the **worst** configuration: 19,682 Hz, 98× the 200 Hz requirement.
- Show all three scenario spreads from `core/cpp/apps/README.md`, each with its
  configuration named. A range with its conditions is honest; a single big
  number is not.
- **If `idr_edge` is built**, add a **Run benchmark** button that executes it
  live and streams real output. If it is not built, say so — never show a
  remembered number.

## 3.7 — Live mode (only if a phone is paired)

When a real device is streaming, `/engine` can run on live phone data instead of
a recorded trace. Requires the app to emit filter internals (Phase 5).

**If live internals are unavailable, do not fake them** — show the recorded trace
with a permanent `REPLAY — recorded trace, real estimator` badge in the same
layer as the canvas.

---

## Ownership

| Item | Files |
|---|---|
| 3.1 trace export | `lab/stress/export_filter_trace.py`, `lab/nav/**` |
| 3.2–3.5 canvas + rail | `web/static/engine.js`, `web/static/engine.css` |
| 3.6 benchmarks | `web/coast_console.py` (`/api/engine`) |
| 3.7 live | `web/pairing.py` |

## Acceptance

- [ ] Three real traces exported, including the worst case
- [ ] Particles render on the graph at 60 fps; nothing drawn off-manifold
- [ ] Fork is visible: ≥2 edges lit at a junction, auto-slowdown fires
- [ ] Collapse animates; resample ripple present but subtle
- [ ] Ghost visibly leaves the road; live gap in metres shown
- [ ] `n_eff` craters at the junction and recovers — verified on a real trace
- [ ] Transport controls work; scrub is smooth
- [ ] Worst-case trace ships with its caption
- [ ] No confidence radius anywhere
- [ ] Particle counts labelled shown-vs-total
- [ ] Runs offline; no CDN
