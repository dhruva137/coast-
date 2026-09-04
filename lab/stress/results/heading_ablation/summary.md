# Heading ablation - where 60 s of DR error comes from

Drives: **23** with paired CAN ground truth. Segments per drive: 10. Speed is held at the phone's GNSS speed in every row, so only heading varies.

`C`-`F` consume CAN data and are **oracles**, not deployable methods. They bound what an online alignment engine could ever buy. Only `A` and `B` are achievable from the phone alone.

| Config | What it is | median err | median drift % | PASS_ISRO |
|---|---|---:|---:|---:|
| `A_raw` | raw `-gyro_pitch` (shipped contract) | 321.6 m | 40.2 | 32/186 |
| `B_lowpass` | + 0.5 Hz causal low pass | 341.8 m | 37.8 | 29/186 |
| `C_mount` | + CAN-fitted 3-axis mount *(oracle)* | 233.7 m | 30.8 | 37/186 |
| `D_mount_lp` | + mount and low pass *(oracle)* | 205.2 m | 24.7 | 42/186 |
| `E_mount_lp_bias` | + stationary bias removal *(oracle)* | 207.5 m | 26.2 | 41/186 |
| `F_oracle` | CAN yaw rate directly *(ceiling)* | 87.6 m | 12.4 | 84/186 |

## Reading

1. **Filtering alone is nearly worthless.** Low pass sharply improves correlation against CAN yaw rate, but correlation is not the objective: integrated heading error is dominated by the slowly-varying component that a low pass passes straight through.
2. **Mount and filter pay off only together.** Neither is sufficient alone, which is why one hardcoded axis fails outside the quiet urban drives.
3. **Even a perfect linear mount leaves a large gap to the sensor ceiling, and the ceiling itself barely clears the ISRO bar.** A phone gyro cannot carry 60 s of heading on its own. Map constraint is a requirement, not an enhancement.

## Per-drive

| Drive | mean v | gyro std | CAN yaw std | A raw | D mount+LP | F oracle |
|---|---:|---:|---:|---:|---:|---:|
| `S-M.csv` | 11.8 | 0.182 | 0.165 | 99 m | 146 m | 53 m |
| `S-S1.csv` | 9.4 | 0.132 | 0.125 | 65 m | 98 m | 61 m |
| `S-S2.csv` | 10.5 | 0.150 | 0.136 | 150 m | 257 m | 35 m |
| `S-S3a.csv` | 12.2 | 0.137 | 0.127 | 88 m | 359 m | 67 m |
| `S-S3b.csv` | 7.1 | 0.379 | 0.188 | 48 m | 234 m | 29 m |
| `S-S3c.csv` | 13.7 | 0.115 | 0.115 | 47 m | 48 m | 59 m |
| `S-S4.csv` | 12.4 | 0.135 | 0.118 | 204 m | 398 m | 110 m |
| `S-Vfa01.csv` | 18.0 | 0.279 | 0.062 | 106 m | 186 m | 172 m |
| `S-Vfa02.csv` | 24.9 | 0.242 | 0.042 | 360 m | 272 m | 60 m |
| `S-Vta16.csv` | 13.5 | 0.296 | 0.085 | 379 m | 197 m | 95 m |
| `S-Vta1a.csv` | 16.3 | 0.344 | 0.074 | 441 m | 392 m | 124 m |
| `S-Vta2.csv` | 11.4 | 0.326 | 0.085 | 116 m | 70 m | 29 m |
| `S-Vta29.csv` | 13.1 | 0.424 | 0.087 | 233 m | 205 m | 89 m |
| `S-Vta30.csv` | 11.1 | 0.305 | 0.059 | 428 m | 19 m | 21 m |
| `S-Vtb1.csv` | 14.8 | 0.320 | 0.073 | 387 m | 209 m | 110 m |
| `S-Vtb2.csv` | 10.9 | 0.396 | 0.075 | 322 m | 235 m | 135 m |
| `S-Vtb5.csv` | 18.4 | 0.253 | 0.046 | 378 m | 261 m | 116 m |
| `S-Vw14b.csv` | 21.1 | 0.242 | 0.014 | 429 m | 231 m | 86 m |
| `S-Vw14c.csv` | 15.5 | 0.257 | 0.059 | 465 m | 175 m | 95 m |
| `S-Vw16a.csv` | 16.3 | 0.272 | 0.048 | 309 m | 120 m | 116 m |
| `S-Vw2.csv` | 20.3 | 0.275 | 0.066 | 415 m | 48 m | 43 m |
| `S-Vw4.csv` | 18.9 | 0.349 | 0.095 | 725 m | 188 m | 88 m |
| `S-Y1.csv` | 10.6 | 0.172 | 0.134 | 365 m | 232 m | 179 m |

Where `gyro std` runs several times `CAN yaw std`, the channel is vibration-dominated and the raw signal carries little heading information. Those are the fast drives.
