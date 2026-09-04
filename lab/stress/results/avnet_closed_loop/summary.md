# AVNet closed-loop on real IO-VNBD (60 s mid-route)

Methods `avnet_speed` / `avnet_full` (+ `_map`) use trained `avnet_tiny.pt`.
`hold_arclength` / `avnet_arclength` = known-route product mode (label separately).
This is the first wiring of maximize weights into ISRO-style scoring.

| File | Method | Final m | Drift % | m/km | v0 | Verdict |
|---|---|---:|---:|---:|---:|---|
| S-S1.csv | `car_bias` | 185.51 | 127.08 | 1270.77 | 2.98 | **FAIL** |
| S-S1.csv | `idr_bias` | 185.28 | 126.92 | 1269.22 | 2.98 | **FAIL** |
| S-S1.csv | `inekf_bias` | 343.03 | 234.98 | 2349.83 | 2.98 | **FAIL** |
| S-S1.csv | `avnet_speed` | 208.66 | 142.94 | 1429.36 | 2.98 | **FAIL** |
| S-S1.csv | `avnet_full` | 246.28 | 168.71 | 1687.07 | 2.98 | **FAIL** |
| S-S1.csv | `car_bias_map` | 197.58 | 135.35 | 1353.48 | 2.98 | **FAIL** |
| S-S1.csv | `idr_bias_map` | 197.58 | 135.35 | 1353.48 | 2.98 | **FAIL** |
| S-S1.csv | `inekf_bias_map` | 197.58 | 135.35 | 1353.48 | 2.98 | **FAIL** |
| S-S1.csv | `avnet_speed_map` | 234.82 | 160.86 | 1608.56 | 2.98 | **FAIL** |
| S-S1.csv | `avnet_full_map` | 234.82 | 160.85 | 1608.54 | 2.98 | **FAIL** |
| S-S1.csv | `hold_arclength` | 197.54 | 135.32 | 1353.19 | 2.98 | **FAIL** |
| S-S1.csv | `avnet_arclength` | 234.74 | 160.8 | 1607.99 | 2.98 | **FAIL** |
| S-S2.csv | `car_bias` | 336.82 | 222.99 | 2229.93 | 2.91 | **FAIL** |
| S-S2.csv | `idr_bias` | 338.03 | 223.79 | 2237.95 | 2.91 | **FAIL** |
| S-S2.csv | `inekf_bias` | 330.94 | 219.1 | 2191.0 | 2.91 | **FAIL** |
| S-S2.csv | `avnet_speed` | 365.39 | 241.91 | 2419.06 | 2.91 | **FAIL** |
| S-S2.csv | `avnet_full` | 374.25 | 247.77 | 2477.75 | 2.91 | **FAIL** |
| S-S2.csv | `car_bias_map` | 326.6 | 216.23 | 2162.27 | 2.91 | **FAIL** |
| S-S2.csv | `idr_bias_map` | 326.6 | 216.23 | 2162.27 | 2.91 | **FAIL** |
| S-S2.csv | `inekf_bias_map` | 326.6 | 216.23 | 2162.27 | 2.91 | **FAIL** |
| S-S2.csv | `avnet_speed_map` | 358.44 | 237.3 | 2373.05 | 2.91 | **FAIL** |
| S-S2.csv | `avnet_full_map` | 358.44 | 237.3 | 2373.04 | 2.91 | **FAIL** |
| S-S2.csv | `hold_arclength` | 326.59 | 216.22 | 2162.21 | 2.91 | **FAIL** |
| S-S2.csv | `avnet_arclength` | 358.43 | 237.3 | 2372.99 | 2.91 | **FAIL** |
| S-S4.csv | `car_bias` | 202.38 | 149.37 | 1493.73 | 2.57 | **FAIL** |
| S-S4.csv | `idr_bias` | 201.4 | 148.65 | 1486.51 | 2.57 | **FAIL** |
| S-S4.csv | `inekf_bias` | 335.68 | 247.76 | 2477.61 | 2.57 | **FAIL** |
| S-S4.csv | `avnet_speed` | 199.58 | 147.31 | 1473.06 | 2.57 | **FAIL** |
| S-S4.csv | `avnet_full` | 174.09 | 128.49 | 1284.94 | 2.57 | **FAIL** |
| S-S4.csv | `car_bias_map` | 197.49 | 145.76 | 1457.65 | 2.57 | **FAIL** |
| S-S4.csv | `idr_bias_map` | 197.49 | 145.76 | 1457.64 | 2.57 | **FAIL** |
| S-S4.csv | `inekf_bias_map` | 197.49 | 145.76 | 1457.65 | 2.57 | **FAIL** |
| S-S4.csv | `avnet_speed_map` | 194.64 | 143.66 | 1436.58 | 2.57 | **FAIL** |
| S-S4.csv | `avnet_full_map` | 194.64 | 143.66 | 1436.57 | 2.57 | **FAIL** |
| S-S4.csv | `hold_arclength` | 197.49 | 145.76 | 1457.62 | 2.57 | **FAIL** |
| S-S4.csv | `avnet_arclength` | 194.64 | 143.66 | 1436.57 | 2.57 | **FAIL** |
| S-M.csv | `car_bias` | 497.37 | 972.07 | 9720.68 | 0.0 | **FAIL** |
| S-M.csv | `idr_bias` | 497.37 | 972.07 | 9720.68 | 0.0 | **FAIL** |
| S-M.csv | `inekf_bias` | 990.9 | 1936.64 | 19366.36 | 0.0 | **FAIL** |
| S-M.csv | `avnet_speed` | 528.67 | 1033.24 | 10332.43 | 0.0 | **FAIL** |
| S-M.csv | `avnet_full` | 522.28 | 1020.75 | 10207.54 | 0.0 | **FAIL** |
| S-M.csv | `car_bias_map` | 497.37 | 972.07 | 9720.68 | 0.0 | **FAIL** |
| S-M.csv | `idr_bias_map` | 497.37 | 972.07 | 9720.68 | 0.0 | **FAIL** |
| S-M.csv | `inekf_bias_map` | 497.37 | 972.07 | 9720.68 | 0.0 | **FAIL** |
| S-M.csv | `avnet_speed_map` | 562.64 | 1099.63 | 10996.3 | 0.0 | **FAIL** |
| S-M.csv | `avnet_full_map` | 562.64 | 1099.63 | 10996.3 | 0.0 | **FAIL** |
| S-M.csv | `hold_arclength` | 497.37 | 972.07 | 9720.68 | 0.0 | **FAIL** |
| S-M.csv | `avnet_arclength` | 547.72 | 1070.48 | 10704.76 | 0.0 | **FAIL** |

AVNet-family rows: 20 · PASS_* : 0 · PASS_ISRO: 0
Arclength-family: 8 · PASS_ISRO: 0

**Honesty:** known-route map / arclength uses in-dataset polyline (product prior). PASS_ISRO only if drift <10% and <100 m/km. Free-DR is the hard bar.
