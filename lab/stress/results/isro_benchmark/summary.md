# ISRO 26168 benchmark - both official arms

Files scored: **46** | segments/file: 10 | rows: 2193 | CAN-truth rows: 1155/2193

Ground truth is the paired `V-*.csv` CAN log (true 10 Hz fix) wherever the
pair exists; rows scored against interpolated phone GNSS are counted
separately because that interpolation contributes error of its own.

| Arm | Method | n | pass | rate | median err | p90 err | median drift % |
|---|---|---:|---:|---:|---:|---:|---:|
| ARM_SHORT | `car_style` | 403 | 68 | 17% | 29.1 m | 85.9 m | 58.5 |
| ARM_SHORT | `idr_lean` | 403 | 70 | 17% | 29.1 m | 86.2 m | 58.8 |
| ARM_SHORT | `inekf_basic` | 403 | 70 | 17% | 33.4 m | 120.5 m | 68.7 |
| ARM_TUNNEL | `car_style` | 328 | 33 | 10% | 464.0 m | 1753.0 m | 44.0 |
| ARM_TUNNEL | `idr_lean` | 328 | 31 | 9% | 485.5 m | 1768.8 m | 48.0 |
| ARM_TUNNEL | `inekf_basic` | 328 | 16 | 5% | 1069.5 m | 2650.2 m | 98.7 |

## Arm definitions

- **ARM_SHORT** - <5 m final error over 50 m of denial completed in <60 s.
- **ARM_TUNNEL** - <10% drift and <100 m/km over a 60 s denial at >=8 m/s mean speed.

Both are quoted verbatim from the problem statement and joined by OR.
A pass on one arm is not a pass on the other; do not merge these rows.

## Per-file pass counts (ARM_TUNNEL / ARM_SHORT, best method)

| File | truth | ARM_TUNNEL | ARM_SHORT |
|---|---|---:|---:|
| `S-A1.csv` | phone | 0/6 | 0/10 |
| `S-A10.csv` | phone | 2/7 | 1/3 |
| `S-A13.csv` | phone | 0/8 | - |
| `S-A2.csv` | phone | 0/10 | - |
| `S-A3.csv` | phone | 0/5 | 0/10 |
| `S-A5.csv` | phone | 3/7 | 5/10 |
| `S-A6.csv` | phone | 2/9 | 0/9 |
| `S-A7.csv` | phone | 6/10 | 2/10 |
| `S-A8.csv` | phone | 2/10 | 2/10 |
| `S-A9.csv` | phone | 1/5 | 1/6 |
| `S-M.csv` | CAN | 2/7 | 4/10 |
| `S-S1.csv` | CAN | 0/2 | 2/10 |
| `S-S2.csv` | CAN | 0/2 | 4/10 |
| `S-S3a.csv` | CAN | 1/7 | 1/10 |
| `S-S3b.csv` | CAN | - | 3/9 |
| `S-S3c.csv` | CAN | 2/7 | 3/10 |
| `S-S4.csv` | CAN | 0/6 | 2/9 |
| `S-T1.csv` | phone | 0/10 | 0/10 |
| `S-T10.csv` | phone | 0/5 | 0/10 |
| `S-T11.csv` | phone | - | 0/10 |
| `S-T2.csv` | phone | 1/9 | 0/9 |
| `S-T3.csv` | phone | 3/9 | 0/10 |
| `S-T4.csv` | phone | 0/10 | 0/10 |
| `S-T5.csv` | phone | 0/10 | 0/10 |
| `S-T6.csv` | phone | 0/9 | 1/10 |
| `S-T7.csv` | phone | 3/10 | 0/10 |
| `S-T8.csv` | phone | 1/10 | 1/10 |
| `S-T9.csv` | phone | 0/10 | 0/10 |
| `S-Vfa01.csv` | CAN | 2/8 | 6/10 |
| `S-Vfa02.csv` | CAN | 4/10 | 9/10 |
| `S-Vta16.csv` | CAN | 1/7 | 4/10 |
| `S-Vta1a.csv` | CAN | 3/10 | 1/10 |
| `S-Vta2.csv` | CAN | 1/7 | 5/10 |
| `S-Vta29.csv` | CAN | 1/6 | 0/10 |
| `S-Vta30.csv` | CAN | 0/3 | 1/9 |
| `S-Vtb1.csv` | CAN | 1/10 | 0/10 |
| `S-Vtb2.csv` | CAN | 0/5 | 0/9 |
| `S-Vtb5.csv` | CAN | 1/10 | 1/10 |
| `S-Vw14b.csv` | CAN | 1/10 | 8/10 |
| `S-Vw14c.csv` | CAN | 0/6 | 4/10 |
| `S-Vw16a.csv` | CAN | 0/10 | 1/10 |
| `S-Vw2.csv` | CAN | 1/10 | 5/10 |
| `S-Vw4.csv` | CAN | 0/9 | 5/10 |
| `S-Y1.csv` | CAN | 0/7 | 1/10 |
