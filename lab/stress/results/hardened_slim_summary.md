# Slim hardened stress (real IO-VNBD)

> **SUPERSEDED SNAPSHOT.** Retained only as provenance for the focused alignment
> audit. Do not use its aggregate or adversarial figures as current product
> evidence; use `hardened_report.json`, `hardened_summary.md`, and
> `CURRENT_VERDICT.md`.

Focused map 60 s: 3 passing method rows, not 3 independent trials.

| csv | site | method | final_m | drift% | m/km | verdict |
|---|---|---|---:|---:|---:|---|
| S-S1.csv | mid_route | `car_bias` | 190.86 | 148.25 | 1482.5 | **FAIL** |
| S-S1.csv | mid_route | `idr_bias` | 190.68 | 148.12 | 1481.2 | **FAIL** |
| S-S1.csv | mid_route | `car_bias_map` | 206.06 | 160.06 | 1600.6 | **FAIL** |
| S-S1.csv | mid_route | `idr_bias_map` | 206.06 | 160.06 | 1600.6 | **FAIL** |
| S-S1.csv | late_route | `car_bias` | 80.15 | 135.1 | 1351.0 | **FAIL** |
| S-S1.csv | late_route | `idr_bias` | 80.06 | 134.95 | 1349.5 | **FAIL** |
| S-S1.csv | late_route | `car_bias_map` | 44.48 | 74.98 | 749.8 | **PASS_COMPETITIVE** |
| S-S1.csv | late_route | `idr_bias_map` | 44.48 | 74.98 | 749.8 | **PASS_COMPETITIVE** |
| S-M.csv | mid_route | `car_bias` | 348.32 | 251.16 | 2511.6 | **FAIL** |
| S-M.csv | mid_route | `idr_bias` | 348.52 | 251.31 | 2513.1 | **FAIL** |
| S-M.csv | mid_route | `car_bias_map` | 551.11 | 397.39 | 3973.9 | **FAIL** |
| S-M.csv | mid_route | `idr_bias_map` | 551.11 | 397.39 | 3973.9 | **FAIL** |
| S-M.csv | late_route | `car_bias` | 677.54 | 284.31 | 2843.1 | **FAIL** |
| S-M.csv | late_route | `idr_bias` | 677.29 | 284.2 | 2842.0 | **FAIL** |
| S-M.csv | late_route | `car_bias_map` | 779.02 | 326.89 | 3268.9 | **FAIL** |
| S-M.csv | late_route | `idr_bias_map` | 779.02 | 326.89 | 3268.9 | **FAIL** |

Adversarial TW figure: **SUPERSEDED** by the corrected full-battery extraction.