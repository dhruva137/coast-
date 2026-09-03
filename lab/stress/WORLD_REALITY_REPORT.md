# Real-world stress report — SIH26168

**Date:** 4 Sept 2026  
**Status:** Stress-tested on **real IO-VNBD** smartphone CSVs. Not jury theatre.

## Data used (real, Git LFS, >1 MB)

| File | Bytes | Samples |
|---|---:|---:|
| `S-S1.csv` | 9,631,499 | 51,746 |
| `S-S2.csv` | 17,469,302 | 93,876 |
| `S-S4.csv` | 17,574,514 | 94,600 |
| `S-M.csv` | 19,798,721 | 105,974 |

Path: `data/raw/IO-VNBD/...` (237 other `S-*.csv` remain LFS stubs).

## What was tried (iterate until honest)

1. **Open-loop car_style / idr_lean** — FAIL on essentially all 60 s forced outages (100–1000 m+ final error).
2. **Gyro bias cal from seed + speed hold** — still FAIL.
3. **Known-route map snap / heading blend** — occasional `PASS_COMPETITIVE` (e.g. S-S1 late 40 s: 58 m → 13.7 m); most 60 s still FAIL. Full-drive maps self-intersect and fool nearest-snap.
4. **Oracle GPS speed** (diagnostic) — still FAIL → **heading**, not only speed-hold, is broken.
5. **Along-track map odometry** — FAIL on full and local corridors with current map builder.
6. **Rigorous axis/time audit** — the original mapping was wrong. Vehicle yaw rate is **`-GYROSCOPE Pitch`**, not `GYROSCOPE Yaw`. On complete-drive, true-GPS-update turning samples, correlation is **0.992 / 0.930** (GPS orientation / lat-lon course) on S-S1 and **0.983 / 0.956** on S-S2, with best lags between -0.3 s and +0.2 s. S-M is weaker (0.489 / 0.462); S-S4 has only 11 eligible turn updates and is not scoreable. The common mapping gate passes on two independent files. Course identifies the yaw axis but not the full mount; raw accelerometer Z carries gravity, so these gyro labels appear semantic/app-defined rather than physical Android axes.
7. **Post-mapping focused 60 s replay** — axis alignment is fixed, but navigation accuracy is not: zero ISRO passes. One S-S1 late-route map-aided scenario is `PASS_COMPETITIVE` (44.5 m final, 75.0% drift); S-S1 mid-route and both S-M sites fail.
8. **Full corrected hardened battery** — 60 s results contain 5 passing method rows and 55 failures. Three map-aided passing rows are three methods on the **same** S-M early-route scenario, not three independent trials: 15.52 m final, 14.33% drift, at only 1.85 m/s seed speed. Its route geometry is built from the full dataset trajectory, including the evaluated interval, so it is an in-dataset known-route proxy rather than independent OSM/fleet-map proof.

## What does pass (keep claiming)

| Test | Result |
|---|---|
| Lean ≈ car on cars (sanity) | ratio ≈ 1.00, mean \|φ\| ≪ 5° |
| Adversarial two-wheeler (`INJECTED_LEAN`, corrected IO-VNBD channels + 26° injected lean) | **car 10.6% drift vs lean 3.8% → PASS_CLAIM** |
| F5/F6 maths (golden tests) | PASS |

## ISRO bars on real cars today

**Not met in the focused corrected-yaw replay** for 60 s GNSS deny. The full battery has one low-speed `inekf_bias` row inside the numeric ISRO thresholds (9.38 m, 8.66%, 86.6 m/km), but this 1.85 m/s scenario does not establish the intended road-speed/tunnel claim.

The current scripted product gate passes its deliberately weaker criteria: injected-lean claim, car sanity, and at least one competitive map-aided scenario. That exit code is **not** an ISRO or field-readiness pass. Heading alignment alone does not fix speed hold, gyro bias growth, or ambiguous map snapping. AVNet/Qian get usable tunnel numbers with a **learned** attitude+velocity network + InEKF + rigid mount — not raw `∫gz`. Reproducing that on IO-VNBD at **10 Hz windows** is the next real milestone (weights exist; not yet closed-loop on these CSVs).

## What a big org would actually buy

1. **Sensor contract:** calibrated mount, axis convention, timebase — proven by gyro↔course correlation > 0.7 on hold-out.
2. **Learned odometry** (10 Hz-correct AVNet-class) feeding InEKF — not speed-hold.
3. **Graph particle filter on OSM** (branch decisions), not nearest-point snap on a multi-hour self-intersecting polyline.
4. **Two-wheeler field logs** (bicycle/scooter + loop closure) — IO-VNBD cannot prove the novel claim alone (cars, φ≈0).
5. **Loop-closure + branch accuracy** as acceptance tests, same as the demo metric.

## Artifacts

- `lab/stress/results/summary.md` — raw battery (honest FAILs)
- `lab/stress/results/hardened_summary.md` — full corrected bias + map rerun
- `lab/stress/results/hardened_report.json` — machine-readable corrected rerun
- `lab/stress/results/product_gate_output.md` — current gate result and provenance warning
- `lab/stress/results/CURRENT_VERDICT.md` — canonical status table
- `lab/stress/results/oracle_speed_report.json`
- `lab/stress/results/local_corridor_report.json`
- `lab/stress/results/along_track_report.json`
- `lab/stress/results/alignment/alignment_report.json`
- `lab/stress/results/alignment/ALIGNMENT_REPORT.md`
- `lab/stress/results/alignment/figures/*.png`
- `lab/stress/iterate_notes.md`

## Bottom line for leadership

We have a **real demonstrable prototype** of the *method* and a **hard evaluation harness on official data**. The weak scripted product gate currently exits 0, but we do **not** yet have a deployable GNSS-denied car tracker or real two-wheeler field proof. Use `results/CURRENT_VERDICT.md`, not the gate label alone, for claim decisions.

Next physical week: (1) close AVNet→InEKF on S-*.csv with 10 Hz windows, (2) validate the corrected mount mapping on additional pulled real files / controlled calibration drives, (3) ≥10 bicycle loop-closure rides for the two-wheeler claim.
