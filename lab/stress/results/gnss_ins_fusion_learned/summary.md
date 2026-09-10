# GNSS+INS fusion while GNSS is present

Falsification test for AUDIT item 10 / Block B1: does a loosely-coupled
GNSS+INS filter beat phone GNSS-only and INS-only against CAN ground truth,
especially on degraded-accuracy / held-fix rows?

**Coupling:** loosely-coupled (position-domain). IO-VNBD has no
pseudoranges/carrier — true tight coupling is not runnable on this corpus.

Drives used: **6** | windows: **41** | window length: 60 s | gyro LP causal 0.5 Hz | degraded threshold: acc_h ≥ 8 m **or** held phone fix. Truth: paired CAN 10 Hz (`truth_source=can_10hz` only).

## All samples (GNSS-available windows)

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone) | 40.03 m | 53.70 m | 88.90 m |
| INS-only (open DR) | 90.81 m | 145.59 m | 240.92 m |
| Fused LC-EKF | 27.77 m | 45.18 m | 62.17 m |
| Learned-gain fused | 49.80 m | 57.20 m | 82.27 m |

Fused vs GNSS-only: **1.44×** (beats GNSS-only on median-of-medians).
Fused vs INS-only: **3.27×** (beats INS-only).
Windows where fused median < GNSS median: **24/41**.
Windows where fused median < INS median: **33/41**.

## Degraded subset (acc_h ≥ threshold OR held phone fix)

This is the AUDIT acceptance slice: fusion should help when the phone
fix is noisy or stale between sparse updates.

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone) | 40.50 m | 54.03 m | 89.06 m |
| INS-only (open DR) | 90.81 m | 145.79 m | 240.92 m |
| Fused LC-EKF | 27.80 m | 45.44 m | 62.17 m |
| Learned-gain fused | 49.79 m | 57.29 m | 82.29 m |

**AUDIT item 10 verdict: PASS (fused beats GNSS-only on degraded median-of-medians)**
Fused vs GNSS-only (degraded): **1.46×**.
Fused vs INS-only (degraded): **3.27×**.
Windows where fused beats GNSS on degraded mask: **24/41**.

## Learned gain policy (held-out drives)

Learned vs GNSS-only (degraded): **0.81×**.
Learned vs classical fused (degraded): **0.56×**.
Parameters were fitted only on training-drive CAN truth; no drive appears in both train and evaluation sets.

## Method notes

- Seed: CAN position + course-derived yaw at window start (same for all three).
- INS-only / fused propagation: causal low-passed yaw rate `gz = -GYROSCOPE Pitch`, phone speed soft-hold.
- Fused updates only on *changed* phone lat/lon (IO-VNBD holds fixes ~9 s).
- Measurement noise R uses reported `GPS ACCURACY` (floored at 2 m).

## Limitations

- IO-VNBD exposes LLA/speed/acc_h only — loosely-coupled fusion, not tight (no pseudoranges).
- Phone GNSS is sparse (~0.1 Hz unique fixes held across ~10 Hz rows); GNSS-only error includes hold quantization vs 10 Hz CAN.

Do not quote this as tightly-coupled fusion. Do not claim a win unless
the degraded table above shows fused median-of-medians strictly below GNSS-only.
