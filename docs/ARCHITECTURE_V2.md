# IDR architecture v2 — designed from measurement, not from the literature

**Status:** design locked by evidence gathered 4 Sep 2026. Supersedes the
free-dead-reckoning-plus-cleanup design implied by `docs/FINALS_WINNER_ARCHITECTURE.md`.

Every design choice below cites the experiment that forced it. Where an
experiment killed an idea, the dead idea is kept on the page — that is the
point of having measured it.

---

## 1. What the measurements ruled out

| Idea | Verdict | Evidence |
|---|---|---|
| Integrate gyro for heading through a 60 s outage | **Dead** | Finding 7: a *perfect* yaw sensor still fails 55% of segments |
| Fix it with a low-pass filter | **Dead** | Finding 7: filtering lifts correlation 0.24 to 0.87 yet *worsens* median error |
| Fix it with better mount calibration | Helps, insufficient | Finding 7: oracle mount + filter is 1.57x, still 42/186 |
| Fix it with a better speed model | **Not the constraint** | Finding 7 holds speed fixed; heading is the binding term |
| Dead-reckon freely, then snap to the map | **Dead** | Finding 8: 0.98x, and *hurts* near-misses by 2.3-2.6x |

The pattern is one thing: **anything that lets position error grow freely
before the map is consulted has already lost.** Cross-track error from an
integrated heading grows without bound, and by the time it reaches hundreds of
metres no amount of post-processing can tell which road you were on.

## 2. The state change that fixes it

Free dead reckoning carries an unconstrained 2D position:

```
state = (x, y, heading)          heading error -> unbounded cross-track error
```

v2 carries **where the vehicle is on the road network**:

```
state = (edge, s along edge, direction, speed_scale)
position = f(graph, edge, s)     derived, therefore always on a road
```

Three consequences, and they are the whole design:

1. **Cross-track error is bounded by road width, structurally.** It cannot
   grow, because there is no degree of freedom in which it could.
2. **Only along-track error accumulates**, and it is driven by speed error
   alone. At 5% speed error over 900 m that is ~45 m — inside the ISRO bar.
3. **Heading stops being integrated and becomes evidence.** The gyro is no
   longer asked *"what is my absolute heading after 60 s"*, which Finding 7
   proves it cannot answer. It is asked *"does the turn I just felt match the
   geometry of the road this particle claims to be on"*, which it answers well.

That reframing is finding F9/F10 ("heading value is concentrated at junctions";
"this is a graph decision, not a regression") made concrete in the state vector
rather than asserted in a slide.

Implementation: `lab/nav/mapfilter.py`.

## 3. The failure mode changes, and that is honest

Free DR fails *gradually*: you drift further and further from the truth.
v2 fails *discretely*: you take the wrong branch at a junction and you are on
the wrong road entirely.

Discrete failure is worse when it happens and much better on average. It is
also the failure a user actually experiences — "it sent me down the wrong
ramp" — which is exactly why finding F12 defined **branch-decision accuracy**
as the user-facing metric. v2 makes that metric measurable rather than
theoretical.

The filter therefore reports its own **posterior spread**. A tight cloud on one
road means confident; a cloud split across branches means "I do not know which
ramp you took", and the UI must say so rather than picking one and drawing it
confidently. An early prototype run showed exactly the danger: 459 m of error
with 5.2 m of spread — confidently wrong. Surfacing spread is not decoration,
it is the guard against that.

## 4. Two scenarios, and the PS benchmark is the easier one

This distinction matters and the submission should make it explicitly.

**Tunnel / underpass — what the ISRO benchmark actually specifies.**
"less than 100m of drift over a 1km GNSS denied environment at a speed of
60kmph in tunnels/underground metro". A tunnel is topologically **1D**: there
are no junctions, so there is no branch decision to get wrong. The filter
degenerates to along-track tracking and the only error source is speed. This is
the *easy* case for v2 and the hard case for free DR.

**Urban canyon, multi-level car park, open road with junctions.**
Branch decisions are live and the discrete failure mode is real.

Our IO-VNBD evaluation is open road with junctions throughout — **a harder case
than the problem statement asks for**. That is deliberate and should be stated:
we do not want a number that only survives on the easy topology.

## 5. Full stack

```
  IMU 200 Hz (phone) or external IMU (edge engine)
      |
  [1] anti-alias decimate -> 10 Hz          gyro_preprocess.py
      causal low pass, never filtfilt on-device
      |
  [2] online mount estimation                (to build)
      3-axis, from GNSS course while GNSS is available
      |
  [3] learned speed + uncertainty            lab/models/
      falls back to speed-hold, honestly labelled
      |
  [4] ROAD-CONSTRAINED PARTICLE FILTER       lab/nav/mapfilter.py
      state = (edge, s, direction, speed_scale)
      gyro weights branch hypotheses; it is never integrated
      |
  [5] mode manager
      GNSS ok      -> fused, filter conditioned on fixes
      GNSS lost    -> filter free-runs on the graph
      GNSS back    -> blended rejoin (measured tradeoff, section 6)
      no map/fix   -> RELATIVE mode, displacement only, said out loud
      |
  UI: position + uncertainty radius + mode + honest abstention
```

Layers 1, 4 and 5 exist. Layers 2 and 3 are the remaining work, and Finding 7
says they are worth ~1.57x — real, but not the thing that wins.

## 6. Handover is a product decision, not a physics one

`lab/stress/run_transition_latency.py`, all drives:

| | converge | icon jump |
|---|---:|---:|
| hard snap | 0 ms | **444.6 m** |
| blended (tau = 2 s) | 11 500 ms | 24.3 m |

Drop side is 100 ms — one sample — so the "within milliseconds" requirement is
met in the direction that matters for not freezing the display.

Neither rejoin policy is correct in general, and quoting either number alone
would mislead. A 444 m teleport is precisely the "jump erratically" behaviour
the problem statement asks us to remove. The right answer is to drive the blend
time constant from the filter's own covariance rather than fixing it — small
drift snaps fast, large drift eases in — which is only possible because layer 4
produces a real uncertainty.

## 7. What would falsify this design

Stated in advance, so the evaluation cannot be tuned into agreement:

- If the road-constrained filter does not beat free DR on the same segments
  scored against CAN truth, the design is wrong and section 2 is refuted.
- If branch-decision accuracy at junctions is near chance, the gyro carries no
  usable turn evidence and the map cannot be used this way at all.
- If posterior spread does not correlate with actual error, the uncertainty is
  decorative and must not be shown to a user as if it meant something.

All three are measurable on the existing harness with CAN ground truth.
