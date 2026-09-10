# Model work

Read `00_CONTEXT.md` first.

---

## Start with the honest framing

The ask was *"what can make the model 10× or 100× better in a few hours."*
The truthful answer is that **10–100× on the speed model is not available, and
it is also not where the leverage is.**

Look at where the accuracy actually comes from:

| Component | Measured effect |
|---|---|
| **Map-in-loop particle filter** | **2.02×** lower median position error |
| Onset-calibrated compass heading | heading drift 16.87% → 7.22% |
| **COAST-VNet-1 speed model** | **~8%** closed-loop over frozen speed |
| Post-hoc snapping (control) | 0.98× — worse than nothing |

The speed model is one input worth ~8%. Even a perfect speed estimate would not
move the system result much, because **heading error dominates lateral drift**,
and the map is what bounds it. Chasing the speed model is optimising the wrong
term.

**Where a few hours actually buys the most, in order:**

1. **The trace bug** (`00_CONTEXT.md` §5) — blocks the single best demo visual.
2. **AI-based GNSS+INS fusion** — the one PS requirement we outright fail.
3. **Fix the uncertainty head** — turns a hidden, broken output into a working one.
4. **A second dataset** — turns "works on the given data" into "generalises".
5. Speed-model architecture — last, and expect single-digit percentages.

---

## 1. Do not revive the residual model without fixing exposure bias

It is already measured and rejected. Teacher-forced it beats persistence
**13/23** folds; under closed-loop rollout — the actual deployment contract — it
wins **0/23**, with median 60 s distance error **213.5 m** against hold's
**7.7 m**. `lab/models/results/residual_speed/`.

That gap *is* exposure bias: it trains on the true `v_prev` and deploys on its
own estimate, so error compounds. If revisited, it needs full rollout training
(feed the model's own chained output during training, not just at eval) —
scheduled sampling alone was not enough. Do not re-adopt it on teacher-forced
numbers.

## 2. The sampling-rate ceiling — the biggest untapped lever

**At 10 Hz, Nyquist is 5 Hz. Road and engine vibration lives at 20–100 Hz.**
The architecture's "high-frequency" branch was designed to read vibration and
physically cannot observe it at this rate — it sees aliased sub-5 Hz content.
Peer methods use 100–200 Hz windows.

**Action:** check whether IO-VNBD carries a higher-rate stream (the vehicle
stream may be faster than the 10 Hz phone stream), and whether the phone can
sample at 100 Hz on-device (`HIGH_SAMPLING_RATE_SENSORS` is already declared).
If either is true, **resampling is likely worth more than any architecture
change** — the frequency-decoupled design only pays off above ~40 Hz.

Report this honestly either way: if the data is 10 Hz only, then the
high-frequency branch is currently decorative, and the model card should say so.

## 3. Fix the uncertainty head — cheap, and it unlocks a hidden feature

Symptom: Gaussian NLL falls while held-out RMSE rises; the resulting spread
correlates **−0.23** with real error, so the UI hides it.

**Cause is named and published:** Seitzer et al., *On the Pitfalls of
Heteroscedastic Uncertainty Estimation*, ICLR 2022 (arXiv 2203.09168). The
`1/σ²` factor in the NLL gradient means hard regions get inflated variance,
which down-weights their own gradients.

**Cheapest fix — two-stage, no architecture change:**
1. Train the mean with **Huber** only. No variance head in the loss.
2. Freeze the mean.
3. Fit the log-variance head on **held-out residuals**.

This removes the coupling entirely. If it flips the −0.23 correlation positive,
we can **stop hiding the uncertainty** — which converts a documented weakness
into a working feature. Alternatives if that is not enough: β-NLL (reimplement,
~5 lines; the reference repo states no licence so do not vendor it), or quantile
/ pinball loss, which has no `1/σ²` term and structurally cannot exhibit this
pathology.

**Avoid evidential regression** — multiple 2023–2024 papers show its epistemic
uncertainty is not faithful.

## 4. AI-based GNSS+INS fusion — the PS requirement we fail

The PS demands *"an innovative AI based Sensor Fusion Algorithm."* Ours is a
classical loosely-coupled EKF at **1.07×** — a wash.

**Recommended recipe (AI-IMU-DR style):** keep the EKF; make a network set the
**measurement covariance `R`** online.

- Reference: Brossard et al., arXiv 1904.06064; `github.com/mbrossar/ai-imu-dr`,
  **MIT**, ~1.0k★. Reports ~1.10% translational error on KITTI, IMU-only.
- Three pseudo-measurements between GNSS fixes: **non-holonomic constraint**
  (zero lateral and vertical velocity), the **COAST-VNet speed** estimate, and
  **zero-velocity** when stopped.
- The existing log-variance head emits `diag(R)` per window.
- **Train in two stages:** freeze the speed mean, then optimise *only* the
  covariance head against 60 s integrated position error — **not NLL**, which
  is what caused the variance inflation in the first place.

Why this one: it needs **no pseudoranges** (IO-VNBD has none, which rules out
learned-`R`-from-GNSS-features), it reuses code that already exists, and it
makes "AI-based sensor fusion" a literally accurate claim — a neural network is
setting the filter's noise model at runtime.

**Report the result either way.** A measured negative is still a real answer to
the requirement, and this project's credibility is built on publishing those.

**Do not vendor KalmanNet** — its repository states no licence.

## 5. Second dataset

Everything is IO-VNBD. One more corpus turns a single-dataset result into a
generalisation claim.

| Option | Size | Licence | Labels |
|---|---|---|---|
| **comma2k19** (recommended) | 97 GB total, ~10 GB chunks | **MIT** — the only vendorable one | CAN-bus speed + raw GNSS, phone-class 9-axis IMU |
| **GSDC 2023-24** (`taroz/gsdc2023`) | **2.7 GB** preprocessed | Kaggle comp rules — verify before publishing | Real smartphones, `device_imu.csv`, NovAtel SPAN `SpeedMps` |
| KITTI raw (OXTS only) | few hundred MB | CC BY-NC-SA — non-commercial | OXTS 100 Hz `vf`; but tactical-grade IMU ≠ phone noise |

```bash
pip install -U "huggingface_hub[cli]"
hf download commaai/comma2k19 --repo-type dataset --local-dir ./comma2k19
# use --include to pull a single ~10 GB chunk first
```

If disk or time is tight, **GSDC at 2.7 GB is the pragmatic pick** — and it is
*actual smartphones*, which is closer to our domain than KITTI.

Add an adapter under `lab/eval/adapters/` following the existing pattern, and
score with the same leave-file-out protocol so the numbers are comparable.

## 6. Architecture, last

If there is time after the above:

- **TCN / dilated causal convolutions** — Brossard's gyro denoiser
  (`mbrossar/denoise-imu-gyro`, MIT, 418★) uses them with no RNN and beats VIO
  systems on attitude from a low-cost IMU. Exports to ONNX cleanly, fastest CPU
  path. **Best risk-adjusted option.**
- **Multi-scale 1D CNN** — IONext (arXiv 2507.17089) reports −10% ATE / −12%
  RTE against a Transformer baseline.
- **Skip Transformers** at 20 timesteps — no evidence attention helps at that
  length, and IONext explicitly beats Transformer baselines.
- **Skip Mamba/S4** — ONNX has no selective-scan op; it decomposes into a `Loop`
  reported ~17× slower than realtime on CPU. The *architectural idea*
  (frequency split, which we already do) is fine; the operator is not shippable.

**Score everything on integrated displacement (RTE@60 s), not per-window RMSE.**
Per-window RMSE is a diagnostic; the field scores ATE/RTE, and our own results
show the two disagree.

---

## Acceptance

- [ ] Sampling-rate question answered with evidence; model card updated
- [ ] Two-stage uncertainty tried; correlation re-measured and reported
- [ ] Learned-covariance fusion implemented and scored on the same 43 outages
- [ ] Second dataset adapter added and scored leave-file-out
- [ ] Any new number registered via `tools/verify_claims.py` (never hand-edit
      `CLAIMS.json`)
- [ ] Negative results written up as summary.md alongside the wins
