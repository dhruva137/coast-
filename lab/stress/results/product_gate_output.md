# SIH26168 product gates — corrected yaw rerun

Mapping: `vehicle yaw rate = -GYROSCOPE Pitch` (`gz = -gyro_pitch_raw`)

Readiness is split into two explicit levels (`product_gate.py --level`):

## Prototype (`--level prototype`) — exit 0

Status string: `RESEARCH_PROTOTYPE_PASS` (not deployment readiness).

- [PASS] `injected_adversarial_TW_PASS_CLAIM`: `PASS_CLAIM` (`INJECTED_LEAN`, not field proof)
- [PASS] `real_car_lean_approx_car_sanity`: 36 sanity rows, 0 bad
- [PASS] `map_aided_60s_PASS_COMPETITIVE+`: 3 passing methods across 1 independent scenario

### Passing map-aided methods (research only)

| csv | site | method | v0 m/s | final m | drift % | verdict |
|---|---|---|---:|---:|---:|---|
| S-M.csv | early_route | `car_bias_map` | 1.85 | 15.52 | 14.33 | `PASS_COMPETITIVE` |
| S-M.csv | early_route | `idr_bias_map` | 1.85 | 15.52 | 14.33 | `PASS_COMPETITIVE` |
| S-M.csv | early_route | `inekf_bias_map` | 1.85 | 15.52 | 14.33 | `PASS_COMPETITIVE` |

Provenance warning: three methods on the same low-speed scenario. Known-route geometry is built from the full dataset GNSS polyline, including the evaluated interval — not independent OSM/fleet-map field proof.

## Deployment (`--level deployment`, default) — exit 1

Status string: `DEPLOYMENT_READY_FAIL`.

- [PASS] corrected alignment on ≥2 files
- [FAIL] real 60 s mid/high-speed ISRO rate (0/8; required ≥80%)
- [FAIL] covariance calibration (nominal-95% coverage 25%; required ≥90% or documented calibrated target)
- [FAIL] real two-wheeler field logs (0; required ≥10)

Canonical verdict: `lab/stress/results/CURRENT_VERDICT.md`. Corrected blind proof: 120 placements / 4 files / 8 sessions; median 223.1 m; p95 695.0 m; coverage 25%; 90.8% >50 m; **NOT deployment-ready**.
