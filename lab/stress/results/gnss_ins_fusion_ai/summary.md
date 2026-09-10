# AI-IMU-DR-style GNSS+INS fusion (learned diag(R))

Falsification test for PS 26168 expected solution 4: an **AI-based**
sensor-fusion algorithm. The frozen classical loosely-coupled EKF measured
**1.07× vs phone GNSS — a wash** (`lab/stress/results/gnss_ins_fusion/`).
This run keeps that EKF structure, adds NHC / speed / ZUPT
pseudo-measurements, and trains a small log-variance head to emit
`diag(R)` against **60 s integrated position error** (not NLL).

**Coupling:** loosely-coupled (position-domain). IO-VNBD has **no
pseudoranges / carrier** — true tight coupling is not runnable on this corpus.

Drives used: **23** | windows: **151** | 
window length: 60 s | 
gyro LP causal 0.5 Hz | 
degraded: acc_h ≥ 8 m **or** held phone fix. 
Truth: paired CAN 10 Hz (`truth_source=can_10hz` only).

Speed mean: **frozen / skipped** (no exported residual-speed ONNX). ONNX probe: `ONNX opened on CPUExecutionProvider; runner still freezes speed mean.`.

Speed ablations (labelled):
- `ai_fused_persistence` — hold last unique-fix **phone** speed (online).
- `ai_fused_oracle_can` — CAN indicated speed at 10 Hz (**ORACLE**, not a product claim).

Training (drive-level split, seed 26168): stage-2a Nelder-Mead on global log-R bias, then SPSA on the MLP, 
loss = mean 60 s position RMSE on training windows only. Init loss 171.73512643826336 → final 118.24991045687295.

## All samples (same windowing as classical fusion defaults)

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone hold) | 52.63 m | 71.45 m | 115.16 m |
| INS-only (open DR) | 114.57 m | 150.95 m | 254.22 m |
| Classical LC-EKF (reimplemented) | 49.29 m | 51.88 m | 79.35 m |
| AI fused + persistence speed | 38.86 m | 60.38 m | 95.22 m |
| AI fused + CAN speed (ORACLE) | 32.54 m | 48.29 m | 79.57 m |

Classical fused vs GNSS-only: **1.07×** (beats GNSS-only).
AI persistence vs GNSS-only: **1.35×** (beats GNSS-only).
AI persistence vs classical EKF: **1.27×** — **POSITIVE (AI persistence beats classical median-of-medians)**.
AI oracle-CAN vs classical EKF: **1.51×** (ORACLE speed; not a product number).
Windows AI-persistence median < GNSS: **88/151**.
Windows AI-persistence median < classical: **73/151**.

## Degraded subset (acc_h ≥ threshold OR held phone fix)

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone hold) | 53.14 m | 71.88 m | 113.74 m |
| INS-only (open DR) | 114.90 m | 151.17 m | 254.03 m |
| Classical LC-EKF (reimplemented) | 49.30 m | 51.92 m | 79.36 m |
| AI fused + persistence speed | 39.36 m | 60.73 m | 95.28 m |
| AI fused + CAN speed (ORACLE) | 32.71 m | 48.33 m | 79.81 m |

AI persistence vs GNSS-only (degraded): **1.35×**.
AI persistence vs classical EKF (degraded): **1.25×**.
Windows where AI-persistence beats GNSS on degraded mask: **88/151**.

## Held-out drives only (leakage-safe)

Windows: **41**. R-head was not fit on these basenames.

Classical vs GNSS: **1.44×**. 
AI persistence vs GNSS: **0.94×**. 
AI persistence vs classical: **0.65×**.

## Method notes

- Precedent: Brossard et al. learn NHC covariance inside an IEKF; they do
  **not** learn the motion. Same split here: EKF kinematics + learned `diag(R)`.
- Classical LC-EKF is the in-script reimplementation of
  `run_gnss_ins_fusion.py` (5-state, GNSS R from `acc_h`) on the **same** windows.
- AI state is 6-D planar: east, north, v_fwd, v_lat, yaw, gyro bias.
- Pseudo-measurements between unique phone fixes: NHC `v_lat≈0`, speed
  (persistence or oracle CAN), ZUPT when speed < 0.4 m/s and |gyro| < 0.05 rad/s.
- Vertical NHC is not applied (no `v_up` in the planar state).
- Feature-dependent MLP (8 → hidden → 4 log-variances) + output-bias fit.
- Features: log1p_acc_h_m, log1p_innovation_m, log1p_predicted_sigma_m, log1p_fix_age_s, log1p_abs_gyro, log1p_highband_energy, log1p_speed_mps, stopped.

## Limitations

- IO-VNBD exposes LLA/speed/acc_h only — loosely-coupled fusion, not tight (no pseudoranges).
- Phone GNSS is sparse (~0.1 Hz unique fixes held across ~10 Hz rows).
- IMU is 10 Hz (Nyquist 5 Hz). AI-IMU-DR used automotive IMU at 100–200 Hz; road/engine vibration the high-band was designed for is already aliased.
- Planar EKF: vertical NHC (v_up≈0) is not applied; lateral NHC is v_lat≈0.
- Phone mount yaw vs vehicle is weakly observable (online alignment measured a wash); NHC assumes a vehicle-frame lateral axis we do not perfectly have.
- Speed mean is skipped (residual/COAST ONNX not loaded). Persistence is online; CAN indicated speed is an ORACLE ablation and must be labelled as such.
- Covariance head is trained against 60 s position RMSE, not NLL (NLL caused variance inflation in lab/models/results/nll_diagnosis/).
- IO-VNBD drives scored here are cars; untilted NHC is the wrong model on two-wheelers.
- All-corpus AI numbers include training-drive windows (R was fit there). Use the held-out table for the leakage-safe claim.

Do not quote this as tightly-coupled fusion. Do not quote oracle-CAN as an
on-device result. A measured negative vs the classical 1.07× EKF is still
the honest answer to the AI-fusion requirement.
