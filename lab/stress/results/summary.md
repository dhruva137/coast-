# SIH26168 real-data stress battery

Seed: `26168`  ·  Generated deterministically.

## CSVs used (real, >1 MB)

| file | bytes | n | hz |
|---|---:|---:|---:|
| `S-M.csv` | 19,798,721 | 105974 | 10.00 |
| `S-S1.csv` | 9,631,499 | 51746 | 10.00 |
| `S-S2.csv` | 17,469,302 | 93876 | 10.00 |
| `S-S4.csv` | 17,574,514 | 94600 | 10.00 |

## Car outage pass/fail (honest)

IO-VNBD is **cars** — lean-aware must **not** magically crush car-style. ISRO bars: drift <10%, <100 m/km. Competitive = not exploding.

| csv | site | deny_s | v0 | method | final_m | ate_m | drift% | m/km | verdict |
|---|---|---:|---:|---|---:|---:|---:|---:|---|
| S-M.csv | mid_route | 20 | 2.6 | car_style | 49.2 | 41.4 | 94.7 | 947 | **FAIL** |
| S-M.csv | mid_route | 20 | 2.6 | inekf_basic | 91.4 | 63.9 | 176.1 | 1761 | **FAIL** |
| S-M.csv | mid_route | 20 | 2.6 | idr_lean | 49.1 | 41.3 | 94.5 | 945 | **FAIL** |
| S-M.csv | mid_route | 40 | 2.6 | car_style | 167.8 | 94.9 | 166.1 | 1626 | **FAIL** |
| S-M.csv | mid_route | 40 | 2.6 | inekf_basic | 257.2 | 146.1 | 254.6 | 2492 | **FAIL** |
| S-M.csv | mid_route | 40 | 2.6 | idr_lean | 167.8 | 94.8 | 166.1 | 1626 | **FAIL** |
| S-M.csv | mid_route | 60 | 2.6 | car_style | 188.7 | 129.3 | 136.1 | 1217 | **FAIL** |
| S-M.csv | mid_route | 60 | 2.6 | inekf_basic | 286.9 | 195.1 | 206.9 | 1850 | **FAIL** |
| S-M.csv | mid_route | 60 | 2.6 | idr_lean | 189.2 | 129.2 | 136.4 | 1220 | **FAIL** |
| S-M.csv | mid_route | 90 | 2.6 | car_style | 326.1 | 191.4 | 143.4 | 1402 | **FAIL** |
| S-M.csv | mid_route | 90 | 2.6 | inekf_basic | 431.3 | 273.0 | 189.6 | 1854 | **FAIL** |
| S-M.csv | mid_route | 90 | 2.6 | idr_lean | 343.8 | 194.7 | 151.1 | 1478 | **FAIL** |
| S-M.csv | high_speed | 20 | 5.4 | car_style | 282.7 | 185.3 | 234.5 | 2345 | **FAIL** |
| S-M.csv | high_speed | 20 | 5.4 | inekf_basic | 350.5 | 218.1 | 290.7 | 2907 | **FAIL** |
| S-M.csv | high_speed | 20 | 5.4 | idr_lean | 282.8 | 185.3 | 234.6 | 2346 | **FAIL** |
| S-M.csv | high_speed | 40 | 5.4 | car_style | 564.2 | 368.9 | 235.0 | 2350 | **FAIL** |
| S-M.csv | high_speed | 40 | 5.4 | inekf_basic | 666.4 | 439.9 | 277.5 | 2775 | **FAIL** |
| S-M.csv | high_speed | 40 | 5.4 | idr_lean | 564.4 | 369.0 | 235.1 | 2351 | **FAIL** |
| S-M.csv | high_speed | 60 | 5.4 | car_style | 844.8 | 550.9 | 235.7 | 2357 | **FAIL** |
| S-M.csv | high_speed | 60 | 5.4 | inekf_basic | 1016.0 | 647.0 | 283.5 | 2835 | **FAIL** |
| S-M.csv | high_speed | 60 | 5.4 | idr_lean | 845.4 | 551.1 | 235.9 | 2359 | **FAIL** |
| S-M.csv | high_speed | 90 | 5.4 | car_style | 1286.6 | 827.4 | 239.3 | 2393 | **FAIL** |
| S-M.csv | high_speed | 90 | 5.4 | inekf_basic | 1589.6 | 985.6 | 295.6 | 2956 | **FAIL** |
| S-M.csv | high_speed | 90 | 5.4 | idr_lean | 1288.8 | 828.0 | 239.7 | 2397 | **FAIL** |
| S-S1.csv | mid_route | 20 | 2.4 | car_style | 39.3 | 41.0 | 108.3 | 811 | **FAIL** |
| S-S1.csv | mid_route | 20 | 2.4 | inekf_basic | 98.5 | 67.8 | 271.5 | 2034 | **FAIL** |
| S-S1.csv | mid_route | 20 | 2.4 | idr_lean | 39.3 | 41.0 | 108.3 | 811 | **FAIL** |
| S-S1.csv | mid_route | 40 | 2.4 | car_style | 74.4 | 53.7 | 107.5 | 767 | **FAIL** |
| S-S1.csv | mid_route | 40 | 2.4 | inekf_basic | 168.0 | 106.5 | 242.6 | 1730 | **FAIL** |
| S-S1.csv | mid_route | 40 | 2.4 | idr_lean | 74.2 | 53.5 | 107.1 | 764 | **FAIL** |
| S-S1.csv | mid_route | 60 | 2.4 | car_style | 190.2 | 108.5 | 147.8 | 1305 | **FAIL** |
| S-S1.csv | mid_route | 60 | 2.4 | inekf_basic | 389.7 | 208.2 | 302.7 | 2673 | **FAIL** |
| S-S1.csv | mid_route | 60 | 2.4 | idr_lean | 189.8 | 108.1 | 147.4 | 1302 | **FAIL** |
| S-S1.csv | mid_route | 90 | 2.4 | car_style | 361.1 | 215.3 | 177.8 | 1651 | **FAIL** |
| S-S1.csv | mid_route | 90 | 2.4 | inekf_basic | 706.9 | 397.0 | 348.0 | 3232 | **FAIL** |
| S-S1.csv | mid_route | 90 | 2.4 | idr_lean | 360.0 | 214.7 | 177.2 | 1646 | **FAIL** |
| S-S1.csv | high_speed | 20 | 4.4 | car_style | 154.0 | 120.2 | 174.1 | 1741 | **FAIL** |
| S-S1.csv | high_speed | 20 | 4.4 | inekf_basic | 210.0 | 141.5 | 237.5 | 2375 | **FAIL** |
| S-S1.csv | high_speed | 20 | 4.4 | idr_lean | 153.9 | 120.2 | 174.1 | 1741 | **FAIL** |
| S-S1.csv | high_speed | 40 | 4.4 | car_style | 358.0 | 255.0 | 199.6 | 1996 | **FAIL** |
| S-S1.csv | high_speed | 40 | 4.4 | inekf_basic | 557.5 | 349.5 | 310.8 | 3108 | **FAIL** |
| S-S1.csv | high_speed | 40 | 4.4 | idr_lean | 358.0 | 255.0 | 199.6 | 1996 | **FAIL** |
| S-S1.csv | high_speed | 60 | 4.4 | car_style | 585.8 | 398.9 | 211.9 | 2119 | **FAIL** |
| S-S1.csv | high_speed | 60 | 4.4 | inekf_basic | 823.2 | 548.6 | 297.7 | 2977 | **FAIL** |
| S-S1.csv | high_speed | 60 | 4.4 | idr_lean | 585.8 | 398.9 | 211.9 | 2119 | **FAIL** |
| S-S1.csv | high_speed | 90 | 4.4 | car_style | 739.7 | 549.3 | 221.5 | 1851 | **FAIL** |
| S-S1.csv | high_speed | 90 | 4.4 | inekf_basic | 1029.1 | 734.5 | 308.2 | 2576 | **FAIL** |
| S-S1.csv | high_speed | 90 | 4.4 | idr_lean | 739.8 | 549.4 | 221.5 | 1851 | **FAIL** |
| S-S2.csv | mid_route | 20 | 3.3 | car_style | 65.9 | 63.4 | 131.1 | 990 | **FAIL** |
| S-S2.csv | mid_route | 20 | 3.3 | inekf_basic | 135.2 | 90.7 | 269.0 | 2031 | **FAIL** |
| S-S2.csv | mid_route | 20 | 3.3 | idr_lean | 65.9 | 63.4 | 131.1 | 990 | **FAIL** |
| S-S2.csv | mid_route | 40 | 3.3 | car_style | 39.3 | 58.8 | 75.5 | 294 | **FAIL** |
| S-S2.csv | mid_route | 40 | 3.3 | inekf_basic | 193.9 | 135.7 | 373.1 | 1453 | **FAIL** |
| S-S2.csv | mid_route | 40 | 3.3 | idr_lean | 39.3 | 58.8 | 75.6 | 294 | **FAIL** |
| S-S2.csv | mid_route | 60 | 3.3 | car_style | 182.2 | 80.5 | 177.6 | 909 | **FAIL** |
| S-S2.csv | mid_route | 60 | 3.3 | inekf_basic | 466.5 | 222.8 | 454.8 | 2329 | **FAIL** |
| S-S2.csv | mid_route | 60 | 3.3 | idr_lean | 182.3 | 80.6 | 177.8 | 910 | **FAIL** |
| S-S2.csv | mid_route | 90 | 3.3 | car_style | 275.1 | 169.5 | 166.8 | 915 | **FAIL** |
| S-S2.csv | mid_route | 90 | 3.3 | inekf_basic | 736.1 | 417.5 | 446.4 | 2448 | **FAIL** |
| S-S2.csv | mid_route | 90 | 3.3 | idr_lean | 276.2 | 169.8 | 167.5 | 919 | **FAIL** |
| S-S2.csv | high_speed | 20 | 7.8 | car_style | 229.3 | 185.2 | 157.6 | 1468 | **FAIL** |
| S-S2.csv | high_speed | 20 | 7.8 | inekf_basic | 290.8 | 199.6 | 199.8 | 1861 | **FAIL** |
| S-S2.csv | high_speed | 20 | 7.8 | idr_lean | 228.9 | 185.1 | 157.3 | 1465 | **FAIL** |
| S-S2.csv | high_speed | 40 | 7.8 | car_style | 542.3 | 389.9 | 182.8 | 1740 | **FAIL** |
| S-S2.csv | high_speed | 40 | 7.8 | inekf_basic | 929.7 | 555.5 | 313.3 | 2982 | **FAIL** |
| S-S2.csv | high_speed | 40 | 7.8 | idr_lean | 543.0 | 389.9 | 183.0 | 1742 | **FAIL** |
| S-S2.csv | high_speed | 60 | 7.8 | car_style | 1154.1 | 648.7 | 253.9 | 2466 | **FAIL** |
| S-S2.csv | high_speed | 60 | 7.8 | inekf_basic | 1848.1 | 992.9 | 406.7 | 3949 | **FAIL** |
| S-S2.csv | high_speed | 60 | 7.8 | idr_lean | 1163.2 | 651.3 | 255.9 | 2485 | **FAIL** |
| S-S2.csv | high_speed | 90 | 7.8 | car_style | 1233.3 | 880.0 | 216.3 | 1756 | **FAIL** |
| S-S2.csv | high_speed | 90 | 7.8 | inekf_basic | 2281.0 | 1457.9 | 400.0 | 3247 | **FAIL** |
| S-S2.csv | high_speed | 90 | 7.8 | idr_lean | 1255.6 | 888.8 | 220.2 | 1787 | **FAIL** |
| S-S4.csv | mid_route | 20 | 1.4 | car_style | 175.5 | 101.4 | 447.8 | 4478 | **FAIL** |
| S-S4.csv | mid_route | 20 | 1.4 | inekf_basic | 177.7 | 102.8 | 453.3 | 4533 | **FAIL** |
| S-S4.csv | mid_route | 20 | 1.4 | idr_lean | 175.5 | 101.4 | 447.8 | 4478 | **FAIL** |
| S-S4.csv | mid_route | 40 | 1.4 | car_style | 321.6 | 208.0 | 372.1 | 3721 | **FAIL** |
| S-S4.csv | mid_route | 40 | 1.4 | inekf_basic | 325.2 | 210.5 | 376.3 | 3763 | **FAIL** |
| S-S4.csv | mid_route | 40 | 1.4 | idr_lean | 321.7 | 208.1 | 372.2 | 3722 | **FAIL** |
| S-S4.csv | mid_route | 60 | 1.4 | car_style | 170.3 | 215.4 | 139.1 | 1391 | **FAIL** |
| S-S4.csv | mid_route | 60 | 1.4 | inekf_basic | 180.6 | 219.0 | 147.5 | 1475 | **FAIL** |
| S-S4.csv | mid_route | 60 | 1.4 | idr_lean | 170.2 | 215.5 | 139.0 | 1390 | **FAIL** |
| S-S4.csv | mid_route | 90 | 1.4 | car_style | 7.3 | 183.4 | 4.3 | 43 | **PASS_ISRO** |
| S-S4.csv | mid_route | 90 | 1.4 | inekf_basic | 44.0 | 188.3 | 26.1 | 261 | **PASS_COMPETITIVE** |
| S-S4.csv | mid_route | 90 | 1.4 | idr_lean | 8.4 | 183.5 | 5.0 | 50 | **PASS_ISRO** |
| S-S4.csv | high_speed | 20 | 7.0 | car_style | 338.5 | 224.1 | 226.7 | 2267 | **FAIL** |
| S-S4.csv | high_speed | 20 | 7.0 | inekf_basic | 407.9 | 258.4 | 273.2 | 2732 | **FAIL** |
| S-S4.csv | high_speed | 20 | 7.0 | idr_lean | 338.5 | 224.2 | 226.7 | 2267 | **FAIL** |
| S-S4.csv | high_speed | 40 | 7.0 | car_style | 701.1 | 451.9 | 229.8 | 2298 | **FAIL** |
| S-S4.csv | high_speed | 40 | 7.0 | inekf_basic | 804.8 | 520.9 | 263.8 | 2638 | **FAIL** |
| S-S4.csv | high_speed | 40 | 7.0 | idr_lean | 701.4 | 452.1 | 229.9 | 2299 | **FAIL** |
| S-S4.csv | high_speed | 60 | 7.0 | car_style | 1040.8 | 681.6 | 229.6 | 2296 | **FAIL** |
| S-S4.csv | high_speed | 60 | 7.0 | inekf_basic | 1189.2 | 771.7 | 262.4 | 2624 | **FAIL** |
| S-S4.csv | high_speed | 60 | 7.0 | idr_lean | 1042.0 | 682.1 | 229.9 | 2299 | **FAIL** |
| S-S4.csv | high_speed | 90 | 7.0 | car_style | 1436.7 | 983.3 | 233.3 | 2283 | **FAIL** |
| S-S4.csv | high_speed | 90 | 7.0 | inekf_basic | 1655.8 | 1114.2 | 268.8 | 2631 | **FAIL** |
| S-S4.csv | high_speed | 90 | 7.0 | idr_lean | 1439.6 | 984.6 | 233.7 | 2288 | **FAIL** |

## Car sanity: lean ≈ car on cars

| csv | site | deny_s | final_lean / final_car | phi_mean_deg |
|---|---|---:|---:|---:|
| S-M.csv | mid_route | 20 | 0.998 | 3.86 |
| S-M.csv | mid_route | 40 | 1.000 | 3.45 |
| S-M.csv | mid_route | 60 | 1.003 | 3.29 |
| S-M.csv | mid_route | 90 | 1.054 | 3.59 |
| S-M.csv | high_speed | 20 | 1.000 | 1.10 |
| S-M.csv | high_speed | 40 | 1.000 | 1.02 |
| S-M.csv | high_speed | 60 | 1.001 | 0.98 |
| S-M.csv | high_speed | 90 | 1.002 | 1.05 |
| S-S1.csv | mid_route | 20 | 1.000 | 0.86 |
| S-S1.csv | mid_route | 40 | 0.997 | 1.53 |
| S-S1.csv | mid_route | 60 | 0.997 | 1.24 |
| S-S1.csv | mid_route | 90 | 0.997 | 1.44 |
| S-S1.csv | high_speed | 20 | 1.000 | 0.73 |
| S-S1.csv | high_speed | 40 | 1.000 | 0.83 |
| S-S1.csv | high_speed | 60 | 1.000 | 0.92 |
| S-S1.csv | high_speed | 90 | 1.000 | 1.61 |
| S-S2.csv | mid_route | 20 | 1.000 | 0.52 |
| S-S2.csv | mid_route | 40 | 1.001 | 0.38 |
| S-S2.csv | mid_route | 60 | 1.001 | 0.50 |
| S-S2.csv | mid_route | 90 | 1.004 | 0.44 |
| S-S2.csv | high_speed | 20 | 0.998 | 2.45 |
| S-S2.csv | high_speed | 40 | 1.001 | 2.45 |
| S-S2.csv | high_speed | 60 | 1.008 | 2.28 |
| S-S2.csv | high_speed | 90 | 1.018 | 2.37 |
| S-S4.csv | mid_route | 20 | 1.000 | 0.35 |
| S-S4.csv | mid_route | 40 | 1.000 | 0.84 |
| S-S4.csv | mid_route | 60 | 0.999 | 0.64 |
| S-S4.csv | mid_route | 90 | 1.147 | 0.57 |
| S-S4.csv | high_speed | 20 | 1.000 | 1.98 |
| S-S4.csv | high_speed | 40 | 1.000 | 1.85 |
| S-S4.csv | high_speed | 60 | 1.001 | 1.87 |
| S-S4.csv | high_speed | 90 | 1.002 | 1.72 |

## Adversarial two-wheeler (INJECTED_LEAN claim test)

Noise from `S-M.csv` · lean=26.0° · v=12.0 m/s · verdict=**PASS_CLAIM**

| method | final_m | ate_m | drift% |
|---|---:|---:|---:|
| car_style | 37.0 | 15.9 | 12.4 |
| idr_lean | 16.8 | 15.9 | 5.6 |

Figure: `C:\Users\Dhruva P Gowda\Desktop\New folder\SIH 2026\lab\stress\results\figures\adversarial_tw_S-M.csv.png`

## Notes

- OK S-M.csv: lean~car on cars (ratio=1.003, phi~3.29 deg).
- OK S-S1.csv: lean~car on cars (ratio=0.997, phi~1.24 deg).
- OK S-S2.csv: lean~car on cars (ratio=1.001, phi~0.50 deg).
- OK S-S4.csv: lean~car on cars (ratio=0.999, phi~0.64 deg).
- Adversarial TW: car drift=12.4% vs lean drift=5.6% → PASS_CLAIM
