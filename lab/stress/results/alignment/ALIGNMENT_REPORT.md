# IO-VNBD phone IMU alignment audit

Verdict: **PASS_ALIGNMENT**

GPS rates use only true field changes, robust angle differences, speed ≥ 3.0 m/s, and all eligible turns. Lag search: -30…+30 s at 0.1 s. No outage ground truth is loaded.

## Best discrete axis/sign/lag per CSV

| CSV | GPS source | axis/sign | lag s | corr | turn updates |
|---|---|---:|---:|---:|---:|
| S-M.csv | gps_orientation | `-1gyro_pitch_raw` | -0.5 | 0.489 | 297 |
| S-M.csv | latlon_displacement | `-1gyro_pitch_raw` | 0.2 | 0.462 | 284 |
| S-S1.csv | gps_orientation | `-1gyro_pitch_raw` | -0.1 | 0.992 | 83 |
| S-S1.csv | latlon_displacement | `-1gyro_pitch_raw` | -0.3 | 0.930 | 65 |
| S-S2.csv | gps_orientation | `-1gyro_pitch_raw` | 0.0 | 0.983 | 147 |
| S-S2.csv | latlon_displacement | `-1gyro_pitch_raw` | 0.2 | 0.956 | 147 |
| S-S4.csv | gps_orientation | `none` | n/a | n/a | 0 |
| S-S4.csv | latlon_displacement | `none` | n/a | n/a | 0 |

## Common mapping gate

**DEFENSIBLE_COMMON_MAPPING**. Best candidate: `-1gyro_pitch_raw`; 2 files exceed correlation 0.7 under the conservative dual-source score.

Per-file conservative correlations: `S-M.csv`=0.462, `S-S1.csv`=0.930, `S-S2.csv`=0.956, `S-S4.csv`=n/a

## Fixed mount transform diagnostics

| CSV | GPS source | CV corr | unit vehicle-yaw axis in phone [Roll, Pitch, Yaw] | observable |
|---|---|---:|---|---|
| S-M.csv | gps_orientation | 0.457 | [-0.111, -0.983, -0.146] | no |
| S-M.csv | latlon_displacement | 0.420 | [-0.583, -0.438, 0.684] | no |
| S-S1.csv | gps_orientation | 0.993 | [-0.329, -0.944, -0.035] | yes |
| S-S1.csv | latlon_displacement | 0.923 | [-0.303, -0.948, -0.096] | yes |
| S-S2.csv | gps_orientation | 0.982 | [-0.012, -0.989, -0.146] | yes |
| S-S2.csv | latlon_displacement | 0.959 | [-0.211, -0.957, -0.198] | yes |
| S-S4.csv | gps_orientation | n/a | n/a | no (no lag score) |
| S-S4.csv | latlon_displacement | n/a | n/a | no (no lag score) |

The fitted yaw-axis transform is reported with contiguous five-fold out-of-fold correlation. Course rate observes only the vehicle vertical axis: rotation about that axis and the full accelerometer mount are not identifiable. Raw accelerometer Z carries gravity in all four files, so the gyro labels are likely semantic/app labels rather than physical Android axes. The fit is diagnostic only and cannot make the product gate pass.

## Real-data verdict

The axis/time alignment gate passes and the loader now maps vehicle yaw to -GYROSCOPE Pitch. The focused navigation/ISRO gate remains red: mapped 60 s replay still has zero ISRO passes; only one S-S1 late-route scenario passes the weaker competitive map-aided criterion, while S-M and the other S-S1 site fail. The separate weak product_gate.py criterion may pass and must not be read as ISRO or field readiness.

## Post-mapping 60 s replay

Focused car/lean, map/no-map rows passing competitive-or-better: **2/16**; ISRO passes across all 60 s rows: **0**.

| CSV | site | method | final m | drift % | verdict |
|---|---|---|---:|---:|---|
| S-S1.csv | mid_route | `car_bias` | 190.86 | 148.25 | **FAIL** |
| S-S1.csv | mid_route | `idr_bias` | 190.68 | 148.12 | **FAIL** |
| S-S1.csv | mid_route | `car_bias_map` | 206.06 | 160.06 | **FAIL** |
| S-S1.csv | mid_route | `idr_bias_map` | 206.06 | 160.06 | **FAIL** |
| S-S1.csv | late_route | `car_bias` | 80.15 | 135.10 | **FAIL** |
| S-S1.csv | late_route | `idr_bias` | 80.06 | 134.95 | **FAIL** |
| S-S1.csv | late_route | `car_bias_map` | 44.48 | 74.98 | **PASS_COMPETITIVE** |
| S-S1.csv | late_route | `idr_bias_map` | 44.48 | 74.98 | **PASS_COMPETITIVE** |
| S-M.csv | mid_route | `car_bias` | 348.32 | 251.16 | **FAIL** |
| S-M.csv | mid_route | `idr_bias` | 348.52 | 251.31 | **FAIL** |
| S-M.csv | mid_route | `car_bias_map` | 551.11 | 397.39 | **FAIL** |
| S-M.csv | mid_route | `idr_bias_map` | 551.11 | 397.39 | **FAIL** |
| S-M.csv | late_route | `car_bias` | 677.54 | 284.31 | **FAIL** |
| S-M.csv | late_route | `idr_bias` | 677.29 | 284.20 | **FAIL** |
| S-M.csv | late_route | `car_bias_map` | 779.02 | 326.89 | **FAIL** |
| S-M.csv | late_route | `idr_bias_map` | 779.02 | 326.89 | **FAIL** |

JSON: `alignment_report.json`

Plots:
- `C:\Users\Dhruva P Gowda\Desktop\New folder\SIH 2026\lab\stress\results\alignment\figures\S-M_alignment.png`
- `C:\Users\Dhruva P Gowda\Desktop\New folder\SIH 2026\lab\stress\results\alignment\figures\S-S1_alignment.png`
- `C:\Users\Dhruva P Gowda\Desktop\New folder\SIH 2026\lab\stress\results\alignment\figures\S-S2_alignment.png`
- `C:\Users\Dhruva P Gowda\Desktop\New folder\SIH 2026\lab\stress\results\alignment\figures\S-S4_alignment.png`
