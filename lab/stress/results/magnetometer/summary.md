# Magnetometer heading study — why COAST does not fuse the compass

Reproduce: `python -m lab.stress.run_magnetometer_study`

Problem statement 26168 lists the magnetometer/compass among the app's inputs.
COAST reads and logs it but does **not** fuse it into the heading estimate. This
is the measurement behind that decision.

## Verdict

**This measurement does NOT support our current design, and we are reporting it against ourselves.** Magnetic heading (16.6° median) is *better* than letting the gyro free-run for a 60 s outage (29.7° median). On this corpus we are leaving usable heading information unfused. Fusing the compass — with the mount and declination offset estimated online rather than granted, as it is here — is a named next step with a measured expected gain, not a guess.

**But the conclusion the pitch rests on is unchanged, and this strengthens it.** A 16.6° heading error held over a distance puts you roughly 29% of that distance sideways. Neither source is remotely good enough to navigate on: the compass is confidently wrong, the gyro is honestly drifting, and both blow the lateral budget long before a tunnel ends. This is the same conclusion as the perfect-gyro ablation (`../heading_ablation/summary.md`, still fails 55% of segments) reached from an independent direction — **the fix is not a better heading sensor, it is the map in the loop.**

## Aggregate (26 drives, 187 skipped)

Truth is GPS course over ground, scored only above **18 km/h**.
A per-drive circular offset is removed first, which grants the compass perfect
mount-alignment and declination correction — so these are **lower bounds** on
real-world compass error.

Drives need at least **3000 moving samples** (5 min at 10 Hz)
and must contain real turning to be scored. Without that guard, removing a
per-drive offset on a short straight run absorbs nearly all the error and the
compass scores near-zero for the wrong reason — an earlier pass of this study
did exactly that, and the guard is what corrected it.

| Heading source | Median of per-drive medians | p90 of per-drive medians |
|---|---:|---:|
| Phone fused compass (`ORIENTATION (Yaw)`) | **16.6°** | 44.0° |
| Tilt-compensated raw magnetometer | **18.4°** | 41.8° |
| Free-running gyro over 60 s | **29.7°** | — |

## Why this matters for the heading budget

A heading error of θ degrees held over a distance d puts you roughly
`d · sin(θ)` metres sideways. The map-in-loop filter exists precisely because
lateral error is what kills a dead-reckoned fix. A compass that is confidently
wrong is worse than a gyro that is honestly drifting, because the filter can
model drift but cannot model a bias it has been told to trust.

## Limitations

- Removing a per-drive constant offset is **best case** for the magnetometer. A
  shipping app would also have to estimate mount yaw and declination online.
- Gyro yaw is integrated in the phone frame; for a near-flat mount that
  approximates vehicle yaw. Tilted mounts need the full projection the estimator
  performs.
- GPS course is itself noisy, which is why samples below 18 km/h are dropped.
- This measures **heading only**, and says nothing about position accuracy.
- IO-VNBD is car data. A handlebar-mounted phone on a two-wheeler sits in a
  different magnetic environment and is not covered here.

## Per drive

| drive | scored samples | phone compass (°) | tilt-comp mag (°) | gyro 60 s (°) |
|---|---:|---:|---:|---:|
| `S-M` | 9179 | 34.9 | 80.4 | 30.1 |
| `S-S2` | 5489 | 16.3 | 31.4 | 22.7 |
| `S-S3c` | 6570 | 24.3 | 15.5 | 8.0 |
| `S-S4` | 11190 | 19.4 | 67.4 | 41.4 |
| `S-Vfa01` | 5940 | 17.3 | 9.6 | 29.8 |
| `S-Vfa02` | 58490 | 38.9 | 17.9 | 19.9 |
| `S-Vta1a` | 9950 | 69.3 | 19.7 | 36.6 |
| `S-Vta29` | 3198 | 21.4 | 14.6 | 29.7 |
| `S-Vtb1` | 4950 | 84.9 | 47.5 | — |
| `S-Vtb5` | 30355 | 49.0 | 36.1 | 16.9 |
| `S-Vw2` | 34112 | 11.0 | 16.7 | 29.6 |
| `S-Vw4` | 58134 | 10.5 | 29.7 | 25.1 |
| `S-Vw14b` | 14818 | 16.8 | 27.9 | 30.8 |
| `S-Vw14c` | 4299 | 12.2 | 9.2 | 18.3 |
| `S-A1` | 4577 | 19.3 | 19.1 | 30.5 |
| `S-A10` | 6663 | 5.9 | 5.9 | 36.1 |
| `S-A11` | 3182 | 15.1 | 30.8 | 32.6 |
| `S-A12` | 3316 | 6.4 | 18.9 | 38.4 |
| `S-A13` | 5402 | 8.1 | 12.4 | 31.2 |
| `S-A2` | 11314 | 20.1 | 20.0 | 44.9 |
| `S-A3` | 7590 | 19.9 | 19.3 | 29.4 |
| `S-A5` | 43665 | 9.7 | 8.8 | 12.0 |
| `S-A6` | 65951 | 8.5 | 9.2 | 15.3 |
| `S-A7` | 40100 | 5.1 | 6.1 | 12.9 |
| `S-A8` | 48750 | 3.5 | 3.9 | 11.0 |
| `S-A9` | 7929 | 7.7 | 7.6 | 36.0 |
