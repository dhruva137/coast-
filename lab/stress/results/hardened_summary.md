# Hardened real-data stress (bias + map)

CSVs: S-M.csv, S-S1.csv, S-S2.csv, S-S4.csv
Focus (60s outages): PASS=5 FAIL=55
Map-aided 60s PASS_*: 3 methods across 1 independent scenario
Car lean~car sanity: OK

## 60 s outages (selected methods)

| csv | site | method | final_m | drift% | m/km | verdict |
|---|---|---|---:|---:|---:|---|
| S-M.csv | early_route | `car_bias` | 33.87 | 31.28 | 312.8 | **PASS_COMPETITIVE** |
| S-M.csv | early_route | `idr_bias` | 33.82 | 31.23 | 312.3 | **PASS_COMPETITIVE** |
| S-M.csv | early_route | `car_bias_map` | 15.52 | 14.33 | 143.3 | **PASS_COMPETITIVE** |
| S-M.csv | early_route | `idr_bias_map` | 15.52 | 14.33 | 143.3 | **PASS_COMPETITIVE** |
| S-M.csv | early_route | `inekf_bias_map` | 15.52 | 14.33 | 143.3 | **PASS_COMPETITIVE** |
| S-M.csv | mid_route | `car_bias` | 348.32 | 251.16 | 2511.6 | **FAIL** |
| S-M.csv | mid_route | `idr_bias` | 348.52 | 251.31 | 2513.1 | **FAIL** |
| S-M.csv | mid_route | `car_bias_map` | 551.11 | 397.39 | 3973.9 | **FAIL** |
| S-M.csv | mid_route | `idr_bias_map` | 551.11 | 397.39 | 3973.9 | **FAIL** |
| S-M.csv | mid_route | `inekf_bias_map` | 551.11 | 397.39 | 3973.9 | **FAIL** |
| S-M.csv | late_route | `car_bias` | 463.12 | 281.55 | 2815.5 | **FAIL** |
| S-M.csv | late_route | `idr_bias` | 463.12 | 281.55 | 2815.5 | **FAIL** |
| S-M.csv | late_route | `car_bias_map` | 463.46 | 281.75 | 2817.5 | **FAIL** |
| S-M.csv | late_route | `idr_bias_map` | 463.46 | 281.75 | 2817.5 | **FAIL** |
| S-M.csv | late_route | `inekf_bias_map` | 463.46 | 281.75 | 2817.5 | **FAIL** |
| S-S1.csv | early_route | `car_bias` | 594.34 | 244.12 | 2441.2 | **FAIL** |
| S-S1.csv | early_route | `idr_bias` | 594.43 | 244.15 | 2441.5 | **FAIL** |
| S-S1.csv | early_route | `car_bias_map` | 586.52 | 240.9 | 2409.0 | **FAIL** |
| S-S1.csv | early_route | `idr_bias_map` | 586.52 | 240.9 | 2409.0 | **FAIL** |
| S-S1.csv | early_route | `inekf_bias_map` | 586.52 | 240.9 | 2409.0 | **FAIL** |
| S-S1.csv | mid_route | `car_bias` | 190.86 | 148.25 | 1482.5 | **FAIL** |
| S-S1.csv | mid_route | `idr_bias` | 190.68 | 148.12 | 1481.2 | **FAIL** |
| S-S1.csv | mid_route | `car_bias_map` | 206.06 | 160.06 | 1600.6 | **FAIL** |
| S-S1.csv | mid_route | `idr_bias_map` | 206.06 | 160.06 | 1600.6 | **FAIL** |
| S-S1.csv | mid_route | `inekf_bias_map` | 206.06 | 160.06 | 1600.6 | **FAIL** |
| S-S1.csv | late_route | `car_bias` | 181.77 | 218.78 | 2187.8 | **FAIL** |
| S-S1.csv | late_route | `idr_bias` | 178.11 | 214.39 | 2143.9 | **FAIL** |
| S-S1.csv | late_route | `car_bias_map` | 54.36 | 65.43 | 654.3 | **FAIL** |
| S-S1.csv | late_route | `idr_bias_map` | 54.36 | 65.43 | 654.3 | **FAIL** |
| S-S1.csv | late_route | `inekf_bias_map` | 54.36 | 65.43 | 654.3 | **FAIL** |
| S-S2.csv | early_route | `car_bias` | 106.31 | 230.98 | 2309.8 | **FAIL** |
| S-S2.csv | early_route | `idr_bias` | 106.31 | 230.98 | 2309.8 | **FAIL** |
| S-S2.csv | early_route | `car_bias_map` | 105.86 | 230.02 | 2300.2 | **FAIL** |
| S-S2.csv | early_route | `idr_bias_map` | 105.86 | 230.02 | 2300.2 | **FAIL** |
| S-S2.csv | early_route | `inekf_bias_map` | 105.86 | 230.02 | 2300.2 | **FAIL** |
| S-S2.csv | mid_route | `car_bias` | 176.71 | 172.27 | 1722.7 | **FAIL** |
| S-S2.csv | mid_route | `idr_bias` | 176.84 | 172.4 | 1724.0 | **FAIL** |
| S-S2.csv | mid_route | `car_bias_map` | 160.2 | 156.18 | 1561.8 | **FAIL** |
| S-S2.csv | mid_route | `idr_bias_map` | 160.2 | 156.18 | 1561.8 | **FAIL** |
| S-S2.csv | mid_route | `inekf_bias_map` | 160.2 | 156.18 | 1561.8 | **FAIL** |
| S-S2.csv | late_route | `car_bias` | 158.21 | 138.72 | 1387.2 | **FAIL** |
| S-S2.csv | late_route | `idr_bias` | 155.51 | 136.36 | 1363.6 | **FAIL** |
| S-S2.csv | late_route | `car_bias_map` | 90.8 | 79.61 | 796.1 | **FAIL** |
| S-S2.csv | late_route | `idr_bias_map` | 90.79 | 79.61 | 796.1 | **FAIL** |
| S-S2.csv | late_route | `inekf_bias_map` | 90.8 | 79.61 | 796.1 | **FAIL** |
| S-S4.csv | early_route | `car_bias` | 400.86 | 223.93 | 2239.3 | **FAIL** |
| S-S4.csv | early_route | `idr_bias` | 400.88 | 223.94 | 2239.4 | **FAIL** |
| S-S4.csv | early_route | `car_bias_map` | 402.79 | 225.01 | 2250.1 | **FAIL** |
| S-S4.csv | early_route | `idr_bias_map` | 402.79 | 225.01 | 2250.1 | **FAIL** |
| S-S4.csv | early_route | `inekf_bias_map` | 402.79 | 225.01 | 2250.1 | **FAIL** |
| S-S4.csv | mid_route | `car_bias` | 94.53 | 77.18 | 771.8 | **FAIL** |
| S-S4.csv | mid_route | `idr_bias` | 94.88 | 77.47 | 774.7 | **FAIL** |
| S-S4.csv | mid_route | `car_bias_map` | 94.3 | 77.0 | 770.0 | **FAIL** |
| S-S4.csv | mid_route | `idr_bias_map` | 94.66 | 77.29 | 772.9 | **FAIL** |
| S-S4.csv | mid_route | `inekf_bias_map` | 94.3 | 77.0 | 770.0 | **FAIL** |
| S-S4.csv | late_route | `car_bias` | 223.64 | 70.42 | 704.2 | **FAIL** |
| S-S4.csv | late_route | `idr_bias` | 224.23 | 70.61 | 706.1 | **FAIL** |
| S-S4.csv | late_route | `car_bias_map` | 223.43 | 70.36 | 703.6 | **FAIL** |
| S-S4.csv | late_route | `idr_bias_map` | 224.01 | 70.54 | 705.4 | **FAIL** |
| S-S4.csv | late_route | `inekf_bias_map` | 223.43 | 70.36 | 703.6 | **FAIL** |

## Adversarial two-wheeler
- **INJECTED_LEAN (not field proof):** car drift=10.6%  lean drift=3.8% → **PASS_CLAIM**

## Interpretation
- `*_map` = in-dataset known-route geometry + gyro-bias cal + forward snap + heading→tangent blend. It includes the evaluated interval's route geometry and is not independent OSM/fleet-map proof.
- Mid/late sites often still FAIL when free-DR leaves the corridor (honest). Early stable segments can be PASS_COMPETITIVE.
- Raw open-loop without map will fail on phone gyros; that is physics (F8), not a softener.
