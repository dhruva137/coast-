# SIH 26168 — current progress

**Updated:** 4 Sep 2026 (independent audit + harness rebuild)
**Repo:** https://github.com/dhruva137/SIH-2026
**Deadline:** **30 September 2026** (verified live on sih.gov.in — not the 20th)

## One-line status

The previous "everything is RED, honestly" verdict was **wrong**: three of its
four causes were defects in the evaluation harness, not physics. Those are
fixed. The corrected evidence produces a stronger and more defensible claim
than the original — see [`docs/AUDIT_AND_PLAN.md`](docs/AUDIT_AND_PLAN.md).

## What was broken

| Defect | Effect | Status |
|---|---|---|
| `GPS SPEED (Kmh)` is actually m/s; loader divided by 3.6 | **every drift % inflated ~3.6x** | fixed, resolved geometrically |
| Ground truth was phone GNSS (498 unique fixes / 51 746 rows) interpolated to 10 Hz | tens of metres of fabricated error | fixed, now paired CAN 10 Hz |
| 559 of 564 dataset CSVs were unpulled LFS stubs | all conclusions drawn from 4 low-speed files | fixed, 564 real, 24 drives |
| Only the hard benchmark arm was scored | the easier official arm was never measured | fixed, both arms scored |

Same code on S-M went from a reported **972% drift to 2.4%** once units and
ground truth were corrected.

## Measured, honestly (23–24 drives, CAN ground truth)

### Both official benchmark arms

| Arm | n | pass | rate | median err |
|---|---:|---:|---:|---:|
| ARM_SHORT (<5 m over 50 m, <60 s) | 403 | 70 | 17% | 29.1 m |
| ARM_TUNNEL (<10% and <100 m/km over 60 s) | 328 | 33 | 10% | 464.0 m |

### The two results that decide the architecture

**Finding 7 — a phone gyro cannot carry 60 s of heading, at all.**
186 outages, speed held fixed so only heading varies:

| config | median err | PASS |
|---|---:|---:|
| raw `-gyro_pitch` (shipped contract) | 321.6 m | 32/186 |
| + 0.5 Hz causal low pass | 341.8 m | 29/186 |
| + 3-axis mount + low pass *(oracle)* | 205.2 m | 42/186 |
| **CAN yaw rate directly *(ceiling)*** | **87.6 m** | **84/186** |

Substituting a *perfect* yaw sensor still fails 55% of segments.

**Finding 8 — post-hoc map matching does not rescue it either.**
Real OSM graph (35 631 edges, 3 271 km, independent of the drives), HMM
matching, 37 outages: **0.98x**. It *hurts* the near-miss cases (2.3–2.6x worse
under 100 m of error) and does nothing beyond 500 m.

**Consequence:** the map must be *inside* the filter loop, not a cleanup pass.
That is what the problem statement means by "UKF + Hidden Markov Map Matching".
Building that tightly-coupled estimator is the top remaining task.

## Shipped this session

| Artifact | Role |
|---|---|
| `lab/stress/audit_can_truth.py` | Audits the S-file contract against paired CAN truth |
| `lab/stress/run_heading_ablation.py` | Finding 7 — where heading error comes from |
| `lab/stress/run_isro_benchmark.py` | Both official benchmark arms, scored separately |
| `lab/stress/run_mapmatch_eval.py` | Finding 8 — post-hoc map matching, measured |
| `lab/stress/run_transition_latency.py` | The "within milliseconds" deliverable |
| `lab/stress/gyro_preprocess.py` | Causal *and* zero-phase filters, never confused |
| `lab/nav/mapmatch.py` | HMM map matching (Newson & Krumm 2009, cited) |
| `maps/osm_extract.py` + graph | Offline OSM road graph, independent of drive data |
| `core/cpp/apps/idr_edge.cpp` | Edge engine CLI — **200 Hz requirement MET** |
| `android/.../OnnxSpeedModel.kt` | On-device ONNX inference (build unverified) |

## PS deliverables

| Requirement | State |
|---|---|
| Edge deployable engine, ~200 Hz, external IMU | **done** — 120 305 Hz, 8.3 us/sample, 7.5 MB |
| Seamless handover, "within milliseconds" | **measured** — 500 ms drop; rejoin is a real tradeoff |
| In-vehicle alignment & calibration | not built; oracle bound measured (Finding 7) |
| AI speed & vibration filter | model exists, retraining on CAN labels not finished |
| Map matching + NHC | built and measured; post-hoc form insufficient (Finding 8) |
| GNSS+INS fusion (GNSS present) | not measured |
| Real-time navigation UI | app builds; ONNX wired, MapLibre still off |

## Next

1. **Tightly-coupled map filter.** Findings 7 and 8 are the evidence for why.
2. Online alignment engine — oracle says it is worth ~1.57x, not more.
3. Retrain speed on CAN labels; leave-file-out.
4. Verify the Android build and get a measured on-device latency.
5. Expand the OSM extract — only 9 of 24 drives are inside the current bbox.
