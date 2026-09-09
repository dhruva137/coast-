# Mount-invariant speed model — gravity-axis canonicalization (EqNIO-style)

Device: cuda | epochs/fold: 4 | folds: 3 | cap: 80000

**Label:** quick measured ablation on 3 of 23 clean folds (not a full bakeoff
rerun). Re-run with `--folds 0 --epochs 12` for the full protocol.

Protocol: identical to `lab/models/run_speed_bakeoff.py` (CAN labels, leave-file-out, hold baseline, 60 s outage distance). The only change is whether IMU windows are gravity-axis canonicalized before the standardiser (`lab/models/gravity_canonical.py`).

Paper: EqNIO — Subequivariant Neural Inertial Odometry (ICLR 2025, [arXiv 2408.06321](https://arxiv.org/abs/2408.06321)).

## Verdict

**Mixed / near-wash.** See tables. Do not claim a win without a clear signed delta.

- Δ median per-window RMSE (canon − raw): **+0.037 m/s**
- Δ median 60 s dist err (canon − raw): **-19.8 m**
- Δ median outage drift % (canon − raw): **-5.71 pp**

## Per-window (RMSE)

| condition | median RMSE | beats hold | vs hold |
|---|---:|---:|---:|
| **raw (current bakeoff path)** | **4.651 m/s** | 0/3 | -214.0% |
| **gravity_canon** | **4.689 m/s** | 0/3 | -216.5% |
| Hold last speed | 1.481 m/s | — | — |

## Closed-loop / outage distance (60 s)

| condition | median dist err | median drift % | folds model wins |
|---|---:|---:|---:|
| **raw** | **100.0 m** | **22.8** | 3/3 |
| **gravity_canon** | **80.2 m** | **17.0** | 3/3 |
| Frozen onset speed | 228.5 m | 59.5 | — |

## Mount-swap probe (fixed random SO(3) on held-out IMU)

Same trained weights; test IMU rotated once per fold (shared rotation seed). `probe ΔRMSE` = probe RMSE − unrotated RMSE (lower/near-zero is more mount-stable).

| condition | median probe RMSE | median probe ΔRMSE |
|---|---:|---:|
| raw | 6.927 | +2.110 |
| gravity_canon | 5.176 | +0.785 |

Δ (canon − raw) median probe ΔRMSE: **-1.325 m/s**.

## Gravity diagnostics (sanity)

After canonicalize on pooled clean windows: median |g_xy| = 0.000 m/s², median |g_z| = 9.894 m/s² (raw |g_xy| was 0.686).

## Limitations

- IO-VNBD phone mounts are already near-upright across drives; tilt diversity is limited, so canonicalization may be a wash on *this* corpus even if it helps a pocket/handlebar mix.
- Residual yaw about gravity is not removed (full EqNIO subequivariance not implemented — preprocess only).
- Does not change the bakeoff headline that the speed model still loses to hold on per-window RMSE; map-in-loop remains the position win.
- ONNX phone asset not swapped; this is a lab ablation only.

## Per fold (model RMSE)

| held-out | n | raw RMSE | canon RMSE | Δ (c−r) | raw outage m | canon outage m |
|---|---:|---:|---:|---:|---:|---:|
| `S-M` | 52978 | 4.651 | 4.689 | +0.037 | 113 | 127 |
| `S-S1` | 25864 | 3.503 | 3.355 | -0.148 | 100 | 80 |
| `S-S2` | 46929 | 5.339 | 5.378 | +0.039 | 74 | 80 |
