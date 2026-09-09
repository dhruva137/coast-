# 05 — Live Training Visualisation

**The complaint:** *"the live training looks like shit… the figures should be
generated live rather than just popping up randomly."*

**The diagnosis:** the current panel shows a loss number going down. A loss curve
is meaningful to about one judge in five, and *emotionally* meaningful to none.
Figures then appear fully-formed at the end, so nothing connects the training to
the result — it reads as "some numbers happened, then a picture appeared."

**The fix is not prettier charts. It is showing the learning happen *on the map*.**

---

## A. The core idea — per-epoch trajectory replay

> After every training epoch, run inference with the **current weights** on one
> held-out drive, and redraw the estimated path on the map. The judge watches the
> red line converge onto the road, epoch by epoch, in real time.

That is it. It is the single best visualisation available to this project and we
are not using it.

**Why it works on every axis:**

- **For a non-technical judge:** they do not need to know what a loss function is.
  They see a wrong line become a right line. The learning is *legible without
  explanation* — which is the entire L0 requirement.
- **For a technical judge:** it is real inference with real weights on genuinely
  held-out data. It is a far stronger claim than a loss curve, because a loss
  curve can go down while the model gets worse at the actual task. This shows the
  task.
- **For our honesty posture:** nothing is simulated. Each frame is the actual
  output of the actual model at that actual epoch.
- **It is memorable.** Judges will discuss forty projects. "The one where you
  watched the path snap onto the road while it trained" is a thing they can
  describe to each other afterwards. That matters more than most teams realise.

**Implementation sketch** (do not build yet — Cursor is busy):
- Training loop already streams epochs to the browser. After each epoch, run
  inference on one fixed held-out drive (cap it — a few thousand samples, ~100 ms).
- Emit the resulting lat/lon polyline in the epoch event alongside the metrics.
- Frontend draws it as a new layer, cross-fading from the previous epoch's path.
- Keep ground truth pinned as a white line, and the free-DR baseline pinned as a
  static red line. The learned path animates between them.

**The honesty label, permanently on the panel:** *"Live: model weights at epoch N,
inference on held-out drive S-XX. Fast re-run — the committed 2.02× headline is
the full protocol run."*

---

## B. The layout — "mission control", not "a chart"

Three regions, fixed proportions, nothing moves position during the run.
**Reserve every element's space before training starts** — the current "figures
pop up randomly" complaint is a layout-shift problem as much as a design one.
Empty states occupy their final footprint from the first frame.

```
┌──────────────────────────────────────────────┬───────────────────┐
│                                              │  EPOCH  7 / 12    │
│         MAP — trajectory convergence         │  ▓▓▓▓▓▓▓░░░░ 58%  │
│                                              │                   │
│    ── ground truth (white)                   │  train loss 0.412 │
│    ── free dead reckoning (red, static)      │  val RMSE   1.83  │
│    ── COAST @ epoch 7 (teal, animating)      │  lr      3.2e-4   │
│                                              │  elapsed    18.4s │
│                                              │                   │
├──────────────────────────────────────────────┤  device    cuda   │
│  loss ╲                                      │  drive     S-M    │
│       ╲___                    val RMSE ╲__   │                   │
│           ╲______                        ╲   │  [ STOP ]         │
└──────────────────────────────────────────────┴───────────────────┘
```

- **Map dominates.** It is the point. Roughly 60% of the area.
- **Curves are secondary**, in a strip beneath — they support the map, they are
  not the headline.
- **Metrics rail on the right**, fixed width, **tabular figures** so nothing
  reflows as numbers change. A metric readout that shifts width when 1 becomes 8
  is the single most common thing that makes a dashboard feel amateur.
- **One accent** for the live series. Ground truth white, baseline red, current
  model teal. No other colours.

---

## C. Motion rules

- **Curves extend, they do not redraw.** Append a point and animate the line
  growing. Never re-render the whole series — it flickers and reads as a refresh.
- **Axes rescale smoothly** (200 ms ease) when a new point exceeds the current
  range. Never jump.
- **The trajectory cross-fades** between epochs (~400 ms) rather than snapping, so
  the eye tracks the improvement as *motion* rather than as a cut.
- **The epoch counter ticks with a subtle scale pulse.** One small thing that
  makes the whole panel feel alive.
- **On completion:** the final trajectory settles, the metrics rail shows the
  delta versus epoch 1, and the three committed figures fade in *into space
  already reserved for them.* Nothing shifts. That directly answers the
  "figures popping up randomly" complaint.

---

## D. What must never happen (honesty guardrails)

These are hard rules — the value of this panel is entirely that it is real.

- **No simulated progress.** No timer-driven fake epochs, no interpolated curve
  while waiting for the subprocess, no `Math.random()`.
- **No smoothing that hides noise.** If validation RMSE bounces, it bounces. A
  suspiciously smooth curve is exactly what a technical judge looks for.
- **If the subprocess fails, the panel shows the real error.** It does not fall
  back to a cached run and it does not show remembered numbers. (This is FIX-2 in
  `win_tuning/PHASE0_BLOCKING_FIXES.md` — the same defect, same rule.)
- **The "fast re-run" label is permanent**, not a tooltip. A quick training run
  cannot reproduce the full committed protocol and we never imply it does.
- **The held-out drive is genuinely held out.** Say which one on screen.

---

## E. The narration that goes with it (~25 seconds)

> "This is training right now on the laptop — real epochs, real GPU. The white
> line is ground truth from the vehicle's CAN bus. The red line is what plain
> dead reckoning does: it leaves the road within seconds. Watch the teal line —
> that's our model's estimate, redrawn after every epoch with the current weights,
> on a drive it has never seen.
>
> *(pause — let it converge)*
>
> That's the model learning to read vehicle speed out of raw phone vibration.
> And that's a fast re-run — the 2.02× we quote is the full protocol, committed
> in the repo."

**The pause is the most important part.** Stop talking and let the line converge.
Silence while something visibly works is far more persuasive than narration over
it, and most presenters cannot resist filling it.

---

## F. Fallback if the live run fails

Never debug on stage. One click switches to a **pre-recorded replay of a real
previous run** — the actual epoch-by-epoch trajectory data from a genuine training
run, saved to a JSON file and played back at the same cadence.

**Label it honestly and visibly: "REPLAY of run 2026-09-XX".** It is real data
from a real run, just not happening this second — which is exactly what we say.
Same discipline as the blackout demo's "REPLAY — real dataset, real estimator."

Have this recorded and tested before Friday. It costs nothing and removes the
single biggest live-demo risk in Act 3.

---

## G. Build order (when Cursor is free)

1. Emit per-epoch held-out trajectory alongside existing epoch metrics.
2. Map panel with the three pinned series + cross-fade between epochs.
3. Layout with reserved space for everything, tabular figures, no reflow.
4. Growing-line curve animation with smooth axis rescale.
5. Figures fade into pre-reserved slots on completion.
6. Record the fallback replay JSON from a real run; wire the one-click switch.

**Item 1 is 80% of the value.** If only one thing gets built, build that.
