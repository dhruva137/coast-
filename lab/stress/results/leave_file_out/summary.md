# Leave-file-out closed-loop (60 s mid-route)

Each eval CSV was **excluded** from AVNet training. Arc-length rows are
known-route product mode (cross-track killed); free-DR rows are the hard bar.

| File | Method | Final m | Drift % | m/km | Verdict |
|---|---|---:|---:|---:|---|
| S-S1.csv | `car_bias` | 185.51 | 127.08 | 1270.77 | **FAIL** |
| S-S1.csv | `avnet_speed` | 182.88 | 125.28 | 1252.75 | **FAIL** |
| S-S1.csv | `avnet_full` | 247.37 | 169.45 | 1694.54 | **FAIL** |
| S-S1.csv | `avnet_speed_map` | 200.7 | 137.48 | 1374.81 | **FAIL** |
| S-S1.csv | `hold_arclength` | 197.54 | 135.32 | 1353.19 | **FAIL** |
| S-S1.csv | `avnet_arclength` | 200.61 | 137.42 | 1374.23 | **FAIL** |
| S-S2.csv | `car_bias` | 336.82 | 222.99 | 2229.93 | **FAIL** |
| S-S2.csv | `avnet_speed` | 344.05 | 227.78 | 2277.78 | **FAIL** |
| S-S2.csv | `avnet_full` | 354.61 | 234.77 | 2347.73 | **FAIL** |
| S-S2.csv | `avnet_speed_map` | 334.73 | 221.61 | 2216.08 | **FAIL** |
| S-S2.csv | `hold_arclength` | 326.59 | 216.22 | 2162.21 | **FAIL** |
| S-S2.csv | `avnet_arclength` | 334.72 | 221.6 | 2216.03 | **FAIL** |
| S-S4.csv | `car_bias` | 202.38 | 149.37 | 1493.73 | **FAIL** |
| S-S4.csv | `avnet_speed` | 211.37 | 156.01 | 1560.12 | **FAIL** |
| S-S4.csv | `avnet_full` | 180.37 | 133.13 | 1331.26 | **FAIL** |
| S-S4.csv | `avnet_speed_map` | 201.22 | 148.52 | 1485.18 | **FAIL** |
| S-S4.csv | `hold_arclength` | 197.49 | 145.76 | 1457.62 | **FAIL** |
| S-S4.csv | `avnet_arclength` | 201.22 | 148.52 | 1485.16 | **FAIL** |
| S-M.csv | `car_bias` | 497.37 | 972.07 | 9720.68 | **FAIL** |
| S-M.csv | `avnet_speed` | 513.7 | 1003.99 | 10039.9 | **FAIL** |
| S-M.csv | `avnet_full` | 509.85 | 996.46 | 9964.64 | **FAIL** |
| S-M.csv | `avnet_speed_map` | 544.71 | 1064.6 | 10645.99 | **FAIL** |
| S-M.csv | `hold_arclength` | 497.37 | 972.07 | 9720.68 | **FAIL** |
| S-M.csv | `avnet_arclength` | 544.71 | 1064.6 | 10646.0 | **FAIL** |

AVNet-family: 20 rows · PASS_ISRO=0
Arclength-family: 8 rows · PASS_ISRO=0

**Honesty:** leave-file-out prevents train leakage. `*_arclength` assumes a known corridor graph (fleet/OSM) — label separately.
