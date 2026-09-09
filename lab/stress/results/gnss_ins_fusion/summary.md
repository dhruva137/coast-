# GNSS+INS fusion while GNSS is present

Falsification test for AUDIT item 10 / Block B1: does a loosely-coupled
GNSS+INS filter beat phone GNSS-only and INS-only against CAN ground truth,
especially on degraded-accuracy / held-fix rows?

**Coupling:** loosely-coupled (position-domain). IO-VNBD has no
pseudoranges/carrier — true tight coupling is not runnable on this corpus.

Drives used: **23** | windows: **151** | window length: 60 s | gyro LP causal 0.5 Hz | degraded threshold: acc_h ≥ 8 m **or** held phone fix. Truth: paired CAN 10 Hz (`truth_source=can_10hz` only).

## All samples (GNSS-available windows)

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone) | 52.63 m | 71.45 m | 115.16 m |
| INS-only (open DR) | 114.57 m | 150.95 m | 254.22 m |
| Fused LC-EKF | 49.29 m | 51.88 m | 79.35 m |

Fused vs GNSS-only: **1.07×** (beats GNSS-only on median-of-medians).
Fused vs INS-only: **2.32×** (beats INS-only).
Windows where fused median < GNSS median: **95/151**.
Windows where fused median < INS median: **103/151**.

## Degraded subset (acc_h ≥ threshold OR held phone fix)

This is the AUDIT acceptance slice: fusion should help when the phone
fix is noisy or stale between sparse updates.

| Estimator | median of window medians | median of RMSEs | median of p90 |
|---|---:|---:|---:|
| GNSS-only (phone) | 53.14 m | 71.88 m | 113.74 m |
| INS-only (open DR) | 114.90 m | 151.17 m | 254.03 m |
| Fused LC-EKF | 49.30 m | 51.92 m | 79.36 m |

**AUDIT item 10 verdict: PASS (fused beats GNSS-only on degraded median-of-medians)**
Fused vs GNSS-only (degraded): **1.08×**.
Fused vs INS-only (degraded): **2.33×**.
Windows where fused beats GNSS on degraded mask: **95/151**.

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
