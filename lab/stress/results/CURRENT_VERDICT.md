# SIH26168 current verdict

Canonical evidence status after the corrected IO-VNBD mapping:
`vehicle yaw rate = -GYROSCOPE Pitch` (`gz = -gyro_pitch_raw`).

| Gate / claim | Status | Corrected result | Provenance |
|---|---|---|---|
| Alignment gate | **GREEN** | `PASS_ALIGNMENT`; S-S1 correlation 0.992 bearing / 0.930 displacement; S-S2 0.983 / 0.956 | Real IO-VNBD car phone IMU against true GPS bearing and lat/lon course changes; `results/alignment/alignment_report.json` |
| Real car open-loop 60 s | **RED** | Basic car-style mid/high-speed: 0/8 competitive passes; final error 170.3–1154.1 m, drift 136.1–253.9%. Focused corrected replay: 0 ISRO passes. | Real IO-VNBD held-out GNSS replay; `results/report.json` and focused alignment rerun |
| Real car map-aided 60 s | **YELLOW** | 3 passing methods, but only 1 independent low-speed scenario: S-M early, v0 1.85 m/s, 15.52 m final, 14.33% drift. Focused corrected replay has 0 ISRO passes. | Real car replay with in-dataset known-route geometry built from the full GNSS polyline, including the evaluated interval; not independent OSM/fleet-map proof |
| Injected-lean claim | **GREEN** | `PASS_CLAIM`: car 10.56% drift vs lean-aware 3.84% | `INJECTED_LEAN`: synthetic 26° coordinated-lean kinematics plus corrected IO-VNBD channel samples; not a field result |
| Real two-wheeler field proof | **RED** | No qualifying bicycle/scooter field logs or loop-closure acceptance battery | IO-VNBD files used here are cars; injected evidence cannot close this gate |

## Product-gate interpretation

`product_gate.py --level prototype` may exit **0** only as
`RESEARCH_PROTOTYPE_PASS`: injected-lean claim, car lean≈car sanity, and at
least one competitive map-aided 60 s scenario. The three passing map rows are
methods on one scenario, not three trials. The default deployment level exits
nonzero as `DEPLOYMENT_READY_FAIL`; it requires corrected alignment on at least
two files, ≥80% real 60 s road-speed ISRO passes, calibrated covariance, and at
least 10 real two-wheeler field logs.

Generated evidence:

- `lab/stress/results/report.json`
- `lab/stress/results/summary.md`
- `lab/stress/results/hardened_report.json`
- `lab/stress/results/hardened_summary.md`
- `lab/stress/results/product_gate_output.md`
- `lab/stress/results/alignment/alignment_report.json`
