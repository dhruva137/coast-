# Phase 4 — Training lab and model design framework

**The complaint:** *"In training, I see weird numbers here: trained and held out.
I want to stress test whether it is actually displaying properly and actually
showing the improvements. The graph is very terrible."*

**The complaint is pointing at a real bug.** Read §4.1 before anything else.

---

## 4.1 — The loss curve is currently meaningless. Fix it first.

Here is an actual run:

```
epoch 1/4  loss=149.7390  rmse=8.724  (MSE)
epoch 2/4  loss= 68.6629  rmse=5.248  (MSE)
epoch 3/4  loss= 60.9503  rmse=5.238  (NLL)
epoch 4/4  loss=  3.7320  rmse=5.390  (NLL)
```

Two separate problems, both visible here:

**(a) The objective changes mid-run.** `lab/demo.py` warms up on MSE and then
switches to Gaussian NLL. Those are different quantities on different scales.
Plotting them on one axis draws a cliff at the switch that means nothing. The
149 → 3.7 "improvement" a judge sees is largely a **change of units**.

**(b) The loss and the metric disagree, and the metric is what matters.**
Between epochs 3 and 4 the loss falls 16× while held-out RMSE gets *worse*
(5.238 → 5.390). That is the classic signature of an NLL head learning to
**inflate its predicted variance** instead of improving its mean: NLL is happily
reduced by admitting more uncertainty. **Investigate and report this.** It may
also be why our uncertainty signal correlates −0.23 with real error.

**Required fixes:**
1. **Never plot MSE and NLL on the same axis.** Either use two panels, or
   normalise each phase to its own start, and **shade the objective switch with a
   labelled marker** (`MSE → NLL`).
2. **Promote held-out RMSE to the headline chart.** Train loss becomes secondary
   and smaller. The judge-facing question is "is it getting better at the task",
   and RMSE answers it; loss does not.
3. **Plot the "hold last speed" baseline as a flat reference line.** Our model
   *loses* to it per-window (4.65 vs 1.48 m/s) and *wins* closed-loop. Both facts
   must be on screen — hiding the first is exactly the kind of thing we do not do.
4. **Add closed-loop distance error per epoch** (the 60 s outage endpoint error).
   That is the number that tracks the actual product, and it is what the
   per-epoch trajectory already shows geometrically.
5. **Investigate (b).** Log predicted sigma per epoch. If variance inflation is
   confirmed, write it into
   `lab/models/results/nll_diagnosis/summary.md` — it is a real finding either
   way, and it may explain the broken confidence radius.

## 4.2 — Stress-test the display end to end

The user asked whether the panel is *actually* showing improvement. Prove it,
mechanically.

Build `lab/models/test_training_display.py`:
- Feed the SSE parser a recorded stdout capture from a real run; assert every
  epoch event round-trips with the right loss, RMSE, mode and path.
- Assert the per-epoch trajectory **converges**: endpoint error to truth must be
  monotonically non-increasing across a synthetic run where the model provably
  improves. If it is not, the plotting or the integration is wrong.
- Assert a failed subprocess produces an error state and **plots nothing**.
- Assert the objective-switch marker lands on the right epoch.

Also record one **golden run** (`lab/models/results/golden_run.jsonl`) so the
console has a real replay when live training is not safe to run. Label it
`REPLAY of run <date>` in the same layer as the chart.

## 4.3 — The experiment framework

*"a lot more sophisticated framework for training the models, trying to build our
own models from scratch, like designing and experimentation."*

Build `lab/models/lab/` — a small, honest experiment harness. Not a
hyperparameter zoo; a thing that makes claims checkable.

**Core contract:** every experiment is a declarative config, runs leave-file-out,
writes `results/<name>/{config.json, metrics.json, summary.md}`, and is
reproducible from a seed.

```python
@dataclass(frozen=True)
class Experiment:
    name: str
    arch: ArchSpec          # see 4.4
    objective: str          # "mse" | "nll" | "huber" | "quantile"
    features: FeatureSpec   # raw | gravity-canonical | freq-decoupled | ...
    folds: int | None       # None = all clean drives
    epochs: int
    seed: int
```

**Required outputs per run** — these are the columns of the comparison table:
per-window RMSE, RMSE vs the hold baseline, closed-loop 60 s distance error,
outage drift %, mount-swap probe ΔRMSE, params, ONNX size, on-device latency.

**A run is not allowed to report a win on per-window RMSE alone.** Closed-loop is
the product metric, and the two disagree in our data — the harness should print
both and flag disagreement rather than letting anyone cherry-pick.

**Parallelism:** the harness must support `--parallel N` over folds, and Cursor
should launch independent experiments as parallel subagents. Each writes to its
own results directory; a final `compare.py` builds the leaderboard.

## 4.4 — Architectures to design and measure

Build these **from scratch** in `lab/models/arch/`, each behind one `ArchSpec`
interface so the harness can swap them. Measure all of them; expect several to
lose, and report that.

| id | idea | why it might help |
|---|---|---|
| `avnet_tiny` | current CNN-GRU | the incumbent baseline |
| `tcn` | dilated temporal conv, no recurrence | large receptive field, cheap on-device, ONNX-friendly |
| `freq_decoupled` | split low-freq motion from high-freq vibration, separate branches | vibration is the noise the PS explicitly names |
| `eq_canon` | gravity-axis canonicalisation front-end (EqNIO-style) | already measured a 63% cut in mount-swap degradation — build on it |
| `resid_hold` | predict a **residual** on top of "hold last speed" | our baseline beats us per-window; learn the correction instead of the value |
| `seq2one_attn` | small self-attention over the window | learns which part of the window carries speed |

**`resid_hold` is the most promising and the least obvious.** If a naive hold
beats our model per-window, the honest move is to make hold the prior and learn
only the delta. Try it early.

**Constraint:** every architecture must export to ONNX and run on-device. An
architecture that cannot ship is not a result. Record ONNX size and measured
phone latency in the leaderboard, and drop anything that misses the 10 Hz budget.

## 4.5 — Ablations that answer real questions

Each writes its own `summary.md` and is quotable in Q&A:

1. **Window length** — 1 s / 2 s / 4 s. Trades latency against accuracy.
2. **Sensor set** — accel only / +gyro / +magnetometer. Given the heading result
   (16.87% → 7.22%), the magnetometer arm now matters a lot.
3. **Sample rate** — 50 / 100 / 200 Hz input. What do we actually need?
4. **Label source** — CAN truth vs phone GNSS. Quantifies how much the CAN
   labels buy us, which matters because judges will ask about label quality.
5. **Cross-vehicle generalisation** — train on cars, test on the two-wheeler
   arm. This is our stated differentiator and it is currently untested.
6. **Degradation** — inject bias, noise, dropped samples, and a 30° mount
   rotation. How gracefully does it fail? This is the robustness story.

## 4.6 — Wire the heading result into the estimator

`lab/stress/results/heading_fusion/summary.md` measured that an onset-calibrated
compass cuts heading-induced drift **16.87% → 7.22%** (2.34×, 655 windows) and
takes the median under the ISRO 10% bar. That is the largest single algorithmic
win available and it is **not yet in the estimator**.

- Implement onset-calibrated compass heading in the lab estimator, behind a flag.
- Re-run the **full map-in-loop benchmark** with it on and off.
- **This may move the 2.02× headline.** If it does: report the new number with
  its full protocol, update `CLAIMS.json`, and flag it prominently — do not
  quietly overwrite a published figure.
- Mirror it into the C++ core and the Android path only after the lab number is
  confirmed.

---

## Acceptance

- [ ] MSE and NLL never share an axis; objective switch is marked
- [ ] Held-out RMSE is the primary chart; hold baseline drawn as a reference line
- [ ] Closed-loop distance error plotted per epoch
- [ ] NLL variance-inflation investigated; finding written up either way
- [ ] `test_training_display.py` passes, including convergence and failure cases
- [ ] Golden replay recorded and labelled
- [ ] Experiment harness runs, supports `--parallel`, writes reproducible results
- [ ] ≥4 architectures built, measured, in one leaderboard with ONNX size + latency
- [ ] ≥4 ablations with `summary.md` each
- [ ] Heading fusion measured end-to-end against the full benchmark
- [ ] Every new number registered in `CLAIMS.json`; `verify_claims.py` exits 0
