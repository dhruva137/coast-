# Advanced estimator roadmap for SIH26168

**Date:** 4 September 2026  
**Scope:** consent-based GNSS-denied phone/fleet navigation; no covert tracking  
**Evidence rule:** literature numbers are prior art, not our results. Our only measured
numbers below come from the four real IO-VNBD smartphone CSVs currently materialised
from Git LFS.

## Executive recommendation

The immediate blocker is not the choice between an InEKF and a factor graph. The
corrected loader mapping (`vehicle yaw = -GYROSCOPE Pitch`) is strongly supported
on S-S1/S-S2, but not every outage prefix contains enough turning updates and the
calibrated candidate does not materially improve the hardened map-aided baseline.
A smoother cannot recover information absent from an unexcited prefix.

Recommended stack:

1. **Make calibration and abstention a hard gate.** Require held-out
   gyro-to-course correlation and excitation before entering inertial mode.
2. **Keep InEKF as the 10 Hz forward estimator; add a 3–5 s fixed-lag smoother
   behind it.** The smoother handles delayed GNSS, map, learned displacement and
   opportunistic factors; publish the current InEKF state immediately and apply
   bounded retro-corrections.
3. **Represent map belief as a Rao-Blackwellized mixture:** discrete edge/branch
   probabilities and a Gaussian (or small Gaussian mixture) in along-edge distance.
   Escalate to particles only near ambiguous junctions.
4. **Train displacement plus covariance only after the real-data labels and
   sensor alignment are trustworthy.** Benchmark a causal TCN first; allow Mamba/SSM
   to win only on identical splits, parameter count and latency.

## Ranked research bets

The “expected gain” column is a planning prior for a correctly synchronised future
dataset, not a result. It must be replaced by measured deltas.

| Rank | Method | Expected gain / value | Phone compute | Data needed | Main failure modes | Decision |
|---:|---|---|---|---|---|---|
| 1 | **Self-supervised gyro scale/bias calibration on audited yaw** | Potentially removes the dominant heading term; F8 says 0.3°/s can cause 14.2% simulated drift | O(1) per tick; prefix fit is a tiny scale/bias robust regression | GNSS-visible turns, common timebase, speed >3 m/s | Straight prefix is unobservable; GNSS bearing noise; timestamp lag; mount changes after calibration | Implemented thin slice; accepts 12/36 but is neutral overall |
| 2 | **Conformal uncertainty + OOD/abstention** | May not improve point error, but prevents unjustified DR confidence and unsafe branch decisions | O(3²) Mahalanobis check plus quantile lookup | Temporally separate calibration residuals and cross-device holdout | Exchangeability breaks under a mount/vehicle shift; marginal coverage is not per-route conditional coverage | Ship with every estimator; use “unbounded/abstain” when calibration fails |
| 3 | **InEKF + fixed-lag factor graph** | Expected best fusion architecture for delayed/asynchronous factors; likely modest point gain over a well-tuned filter under identical models, larger gain when relinearisation matters | InEKF ~fixed 15-state work; 3–5 s graph at 10 Hz is 30–50 nodes, sparse solve off the UI thread | Calibrated IMU, GNSS, learned Δp/Σ; map factors | Marginalisation inconsistency, bad map factor dominating, phone thermal spikes; graph cannot fix unobservable yaw | Hybrid, not either/or: InEKF forward + fixed-lag correction |
| 4 | **Rao-Blackwellized graph filter** | Material branch-accuracy and cross-track gain; reduces particles by integrating Gaussian along-edge state analytically | O(K·fanout), K active edge hypotheses; target K≤8 normally | OSM/fleet graph and labelled junction traversals | Parallel roads, ±8° forks, wrong map topology, posterior collapse | Build after sensor contract; natural successor to `VectorMapLocator` |
| 5 | **Neural displacement vectors + heteroscedastic covariance** | Prior art shows covariance-aware fusion can beat direct concatenation; vehicle transfer gain unknown | Tiny causal CNN/TCN 50k–300k parameters; target <8 ms CPU/NNAPI | Many correctly aligned 2–5 s windows; leave-driver/phone/route-out splits | Learns speed prior or route identity; covariance collapse; cars do not validate two-wheelers | Train only on real labels; use Δp and full/low-rank Σ as a factor, not a replacement state |
| 6 | **Route fingerprints + change-point/branch calibration** | High value on repeated fleet routes; landmarks can reset along-track drift and sharpen branch posterior | Embedding lookup + cosine/DTW/HMM; feasible on-device with compact route cache | Repeated traversals across days, speeds, phones and mounts | Seasonal/traffic changes, route leakage, aliasing, privacy retention | Store opt-in, minimised embeddings; evaluate retrieval recall and expected calibration error |
| 7 | **Magnetic, light, barometer and audio factors** | Sparse but sometimes decisive: magnetic tunnel profile, counted light pulses, garage floor changes, acoustic speed | Low except continuous microphone; event-trigger and discard raw audio | Sensor-specific repeated routes and negative controls | Magnetic engine/frame distortion; light occlusion; weather/HVAC pressure drift; audio privacy and domain shift | Magnetic/light/baro before audio; each factor gets a likelihood and OOD gate |
| 8 | **Frequency Mamba/SSM vs causal TCN** | Frequency split is physically motivated; Mamba-specific gain is unknown on 10 Hz vehicle windows | TCN is simplest; SSM value appears only with long context. Match MACs, parameters and peak RAM | Same real train/validation/test windows, ≥30–120 s context for long-memory claim | Small-data overfit, non-causal preprocessing, driver leakage, inflated latency | TCN is the control. No “Mamba” claim without a paired benchmark |

## 1. Fixed-lag smoother versus InEKF

This is not a clean winner-takes-all comparison.

**InEKF strengths**

- Constant memory, deterministic latency and immediate 10 Hz output.
- Invariant error coordinates improve consistency and convergence compared with a
  conventional trajectory-linearised EKF.
- Appropriate primary estimator for Android and for weak hardware.

**Fixed-lag strengths**

- Relinearises recent states after a delayed GNSS fix or a newly resolved branch.
- Expresses IMU preintegration, GNSS, Δp/Σ, map, barometer and landmark factors in
  one auditable objective.
- Retains cross-time correlations that the current simplified filter discards.

**Recommended graph**

- Keyframe at 2–5 Hz, not every raw IMU sample.
- State per keyframe: `R, v, p`; bias nodes every 1–2 s.
- Combined IMU preintegration factor; robust GNSS position/course factors; learned
  displacement factor with predicted covariance; switchable map cross-track and
  along-edge factors.
- 3–5 s lag initially. Marginalise with FEJ-style care, cap Gauss–Newton iterations,
  and monitor solve p95 and condition number.
- Feed graph correction to the live InEKF only when innovation and graph health pass
  gates. Never block the output thread.

Forster et al. provide on-manifold IMU preintegration
([DOI](https://doi.org/10.1109/TRO.2016.2597321)); GTSAM exposes
`IncrementalFixedLagSmoother` and `CombinedImuFactor`. Dong-Si and Mourikis analyse
fixed-lag consistency ([DOI](https://doi.org/10.1109/ICRA.2011.5980267)).
Barrau and Bonnabel establish the invariant-filter foundation
([DOI](https://doi.org/10.1109/TAC.2016.2594085)). A 2025 comparison also cautions
that filtering variants can match FGO when both use the same factors, while running
faster ([preprint](https://arxiv.org/abs/2511.00306)); therefore, any graph gain must
be demonstrated under matched measurement models.

## 2. Rao-Blackwellized graph belief

Use

`p(edge, s, v | z) = p(edge | z) · N([s,v]; μ_edge, Σ_edge)`.

Propagate `(s,v)` analytically along each edge. At a junction, split discrete mass
using transition legality, yaw/Δp likelihood and fingerprints. Merge near-identical
hypotheses; prune only with a floor so a temporarily weak correct branch can recover.
Report negative log likelihood, Brier score, expected calibration error and
branch-decision accuracy—not only top-1 accuracy.

This is established road-constrained tracking/map-matching territory, not a novelty
claim. Relevant prior art includes Cheng and Singh
([DOI](https://doi.org/10.1109/TAES.2007.4441751)), Bayesian map matching
([JOSS](https://doi.org/10.21105/joss.03651)), and the standard HMM map matcher of
Newson and Krumm ([DOI](https://doi.org/10.1145/1653771.1653818)).

## 3. Learned displacement and sequence backbone

Predict body- or gravity-frame `Δp` over a fixed time horizon plus Cholesky
parameters for covariance. Train with Gaussian NLL, but evaluate covariance with
normalised innovation squared, reliability curves and outage-level coverage.
TLIO demonstrates displacement-and-uncertainty fusion
([DOI](https://doi.org/10.1109/LRA.2020.3007421)); AirIMU learns correction and
uncertainty propagation and reports a 31.6% pose-graph ablation gain on its data
([paper](https://arxiv.org/abs/2310.04874)). Those results are motivation, not an
expected SIH26168 score.

Backbone experiment:

1. Causal dilated TCN.
2. GRU control matching the existing 96,086-parameter model.
3. Frequency-split TCN.
4. Frequency-split SSM/Mamba with matched parameters/MACs.

Use leave-route-and-driver-out data, identical augmentations and five seeds. Publish
median and paired bootstrap confidence intervals. MambaIO/FDIO is pedestrian prior
art and reports benefits from frequency decomposition
([arXiv:2511.15645](https://arxiv.org/abs/2511.15645)); it does not establish a
vehicle or 10 Hz advantage.

## 4. Opportunistic and route factors

- **Magnetic:** match magnitude/vehicle-frame profiles only after hard/soft-iron and
  engine-state checks. MGINS reports lane-level vehicle results on its instrumented
  setting ([DOI](https://doi.org/10.1109/TITS.2024.3386568)); phone/two-wheeler
  transfer is unproven.
- **Light:** count entry-relative pulses rather than phase-match; current simulation
  suggests 9–21% along-track gain, not yet real-data validated.
- **Barometer:** estimate relative floor/grade with a slowly varying weather/HVAC
  bias; make it a vertical/edge likelihood, never an absolute position.
- **Audio:** opt-in only. Extract a short-lived speed/event feature locally and
  discard waveform immediately. Continuous raw recording is outside the product
  requirement and creates avoidable privacy/power risk.
- **Fingerprints:** train route-segment contrastive embeddings with hard negatives
  from adjacent/parallel edges. Bayesian online change-point detection can mark
  landmarks (Adams and MacKay, [arXiv:0710.3742](https://arxiv.org/abs/0710.3742)).

## 5. Implemented thin slice and honest result

Files:

- `lab/advanced/gyro_mount_calibration.py`
- `lab/advanced/benchmark.py`
- `lab/advanced/results/benchmark_results.json`
- `lab/advanced/results/benchmark_comparison.png`

The calibrator consumes loader `gz = -GYROSCOPE Pitch` directly and does not fit a
second axis permutation. It learns only scale/bias and prefix-only timing lag, using
true GPS-orientation changes and gyro averages over the identical intervals.
Trust requires at least 48 turning updates, correlation ≥0.70 on the final 25% of
prefix updates, mapped-yaw scale in `[0.85, 1.15]`, and a prefix-held-out empirical
99.5% Mahalanobis OOD radius.

Protocol: 36 forced held-out outages (4 real logs × 3 sites × 20/40/60 s).
Calibration sees only the prefix. Outage GNSS is scoring-only. Both candidate and
baseline receive the same full-drive polyline as a stand-in for an offline route
map; this is a known-route benchmark, not blind map construction.

Corrected-axis measured result (deterministic rerun, seed 26168):

- Hardened baseline median final error: **128.0027 m** (mean **175.3255 m**).
- Ungated calibrated candidate median: **129.9719 m** (mean **185.3093 m**);
  median status **worsened** by **1.9692 m**, with a **44.4%** win rate.
- Safe system accepted **12/36** outages (S-S1/S-S2 mid/late) and abstained on
  **24/36**. Safe median: **128.0025 m**, a sub-millimetre **neutral** change
  under the explicit 0.01 m status tolerance.
- Safe abstention **prevented a regression**: suspect S-M/S-S4 scale fits and
  low-information early prefixes fell back to the hardened baseline.
- Overall verdict: **FAIL**. Empirical uncertainty coverage is **75%**, below the
  predeclared ≥85% requirement, and there is no material median improvement.

Provenance note: rerunning the original code against the corrected loader reproduced
the prior **128.00 m / 140.48 m / 0 accepted** numbers exactly. They were therefore
**not stale because of the yaw-axis mapping**. They are now superseded because the
old calibrator differentiated sample-held GPS orientation at IMU rate and learned
an unnecessary three-axis remap. The corrected artifacts use true GPS update
intervals and the audited loader yaw channel only.

Recommendation: retain the abstention gate, but do not claim or ship this thin slice
as an accuracy improvement. Fix the position-uncertainty model and validate on new
rigid-mount, monotonic-timebase drives before adding a smoother or neural backbone.

## Execution plan

### Next two weeks

1. Establish sensor contract on a new logger: monotonic timestamps, Android
   uncalibrated gyro, GNSS timestamps, mount metadata and an explicit frame diagram.
2. Record ≥10 bicycle/car loops with repeated turns and two mounts; require
   held-out gyro/course correlation >0.7 before DR scoring.
3. Estimate timestamp lag jointly with SO(3) mount and gyro bias; compare against
   the linear thin slice.
4. Add reliability plots: conformal coverage by device/mount, OOD AUROC and
   abstention-risk curve.
5. Implement a NumPy/GTSAM desktop 3 s fixed-lag prototype with exactly the same
   GNSS/IMU factors as an InEKF control.

### Six weeks

1. Collect leave-phone/driver/route-out training data, including two-wheelers.
2. Add learned `Δp + Σ` factor; compare fixed covariance, heteroscedastic diagonal
   and low-rank/full covariance.
3. Build the Rao-Blackwellized edge Gaussian and junction branch posterior.
4. Benchmark TCN/GRU/frequency-TCN/SSM under matched parameters and Android CPU
   latency.
5. Add magnetic/light/barometer factors one at a time with sensor-off ablations.

### Three months

1. Port the winning 3–5 s smoother or bounded retro-correction to C++/WASM; keep
   InEKF as deterministic forward output.
2. Run ≥100 route outages across phones, mounts, riders and weather; publish
   paired confidence intervals, branch calibration and worst-decile risk.
3. Validate 10 Hz sustained operation, p95 latency, thermal/battery and recovery
   after mount change.
4. Freeze acceptance gates: `<10%` drift, `<100 m/km`, branch accuracy by junction
   angle, finite 90% interval coverage, and explicit abstention rate.

## Next experiment

Record one 15-minute loop with a rigidly mounted phone and a single monotonic
timebase, including repeated left/right turns and three stationary periods. Fit
**SO(3) mount + 3-axis gyro bias + timestamp lag** on the first half; freeze it;
evaluate yaw-rate correlation and 20/40/60 s outages on the second half. If
correlation stays below 0.7, stop estimator work and fix logging/synchronisation.
If it passes, compare matched-factor InEKF versus a 3 s fixed-lag smoother before
adding any neural backbone.
