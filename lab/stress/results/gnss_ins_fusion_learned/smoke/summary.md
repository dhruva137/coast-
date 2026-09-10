# GNSS+INS fusion while GNSS is present

Falsification test for AUDIT item 10 / Block B1: does a loosely-coupled
GNSS+INS filter beat phone GNSS-only and INS-only against CAN ground truth,
especially on degraded-accuracy / held-fix rows?

**Coupling:** loosely-coupled (position-domain). IO-VNBD has no
pseudoranges/carrier — true tight coupling is not runnable on this corpus.

Drives used: **2** | windows: **2** | window length: 60 s | gyro LP causal 0.5 Hz | degraded threshold: acc_h ≥ 8 m **or** held phone fix. Truth: paired CAN 10 Hz (`truth_source=can_10hz` only).

## All samples (GNSS-available windows)

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone) | 82.76 m | 91.46 m | 127.12 m |
| INS-only (open DR) | 58.33 m | 58.75 m | 80.69 m |
| Fused LC-EKF | 64.66 m | 66.82 m | 83.75 m |
| Learned-gain fused | 66.31 m | 68.97 m | 90.79 m |

Fused vs GNSS-only: **1.28×** (beats GNSS-only on median-of-medians).
Fused vs INS-only: **0.90×** (DOES NOT beat INS-only).
Windows where fused median < GNSS median: **1/2**.
Windows where fused median < INS median: **1/2**.

## Degraded subset (acc_h ≥ threshold OR held phone fix)

This is the AUDIT acceptance slice: fusion should help when the phone
fix is noisy or stale between sparse updates.

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone) | 83.14 m | 91.48 m | 126.69 m |
| INS-only (open DR) | 58.26 m | 58.79 m | 80.71 m |
| Fused LC-EKF | 64.54 m | 66.83 m | 83.77 m |
| Learned-gain fused | 66.33 m | 68.98 m | 90.78 m |

**AUDIT item 10 verdict: PASS (fused beats GNSS-only on degraded median-of-medians)**
Fused vs GNSS-only (degraded): **1.29×**.
Fused vs INS-only (degraded): **0.90×**.
Windows where fused beats GNSS on degraded mask: **1/2**.

## Learned gain policy (held-out drives)

Learned vs GNSS-only (degraded): **1.25×**.
Learned vs classical fused (degraded): **0.97×**.
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
