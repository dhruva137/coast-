# Speed bake-off - leave-file-out, CAN labels

Device: cuda | epochs/fold: 12 | folds: 23

Protocol confirmed: labels are CAN indicated vehicle speed (`speed_data`, `can_only` / `can_10hz`); leave-file-out — train on N-1 drives, score the held-out drive only.

The question is whether the learned speed model beats simply **holding** the last known speed, which is what free dead reckoning does in an outage. RMSE alone is not the point; beating `hold` is.

## Per-window (RMSE)

| | median RMSE | note |
|---|---:|---|
| **Model (AVNet-tiny)** | **5.068 m/s** | beats hold on 0/23 folds |
| Hold last speed | 1.280 m/s | the baseline to beat |
| Predict the mean | 7.970 m/s | the floor |

Median improvement over hold: **-295.8%**.

## Closed-loop / outage distance (60 s)

Integrates model speed vs freezing onset speed over mid-route 60 s windows. This is the along-track metric free DR actually cares about; per-window RMSE can lose while distance still wins.

| | median dist err | median drift % | folds model wins |
|---|---:|---:|---:|
| **Model** | **158.3 m** | **19.1** | 9/23 |
| Frozen onset speed | 163.2 m | 21.1 | — |

## Uncertainty calibration

The model has a Gaussian NLL head. Empirical coverage of its nominal intervals (median over folds): 68% target -> **0.43**, 95% target -> **0.75**. This is what the GNSS+INS fusion reads to decide how far to trust the speed; a well-calibrated head has coverage close to its nominal.

## Per fold

| held-out drive | n | model RMSE | hold RMSE | beats hold | outage model m | outage frozen m | outage win | cov68 | cov95 |
|---|---:|---:|---:|:--:|---:|---:|:--:|---:|---:|
| `S-M` | 52978 | 4.223 | 3.448 | no | 82 | 169 | yes | 0.55 | 0.82 |
| `S-S1` | 25864 | 3.133 | 1.324 | no | 74 | 228 | yes | 0.69 | 0.93 |
| `S-S2` | 46929 | 5.068 | 1.481 | no | 73 | 229 | yes | 0.43 | 0.75 |
| `S-S3a` | 12301 | 4.812 | 1.251 | no | 98 | 44 | no | 0.46 | 0.76 |
| `S-S3b` | 3397 | 4.188 | 1.521 | no | 124 | 81 | no | 0.56 | 0.81 |
| `S-S3c` | 18582 | 7.522 | 1.236 | no | 196 | 167 | no | 0.40 | 0.65 |
| `S-S4` | 47291 | 6.712 | 4.634 | no | 257 | 243 | no | 0.37 | 0.64 |
| `S-Vfa01` | 5734 | 5.360 | 1.277 | no | 141 | 156 | yes | 0.38 | 0.65 |
| `S-Vfa02` | 33752 | 5.246 | 0.799 | no | 219 | 32 | no | 0.43 | 0.71 |
| `S-Vta16` | 5658 | 4.066 | 1.147 | no | 158 | 102 | no | 0.50 | 0.81 |
| `S-Vta1a` | 12829 | 6.142 | 1.280 | no | 214 | 163 | no | 0.32 | 0.60 |
| `S-Vta2` | 5486 | 5.678 | 1.295 | no | 264 | 193 | no | 0.25 | 0.61 |
| `S-Vta29` | 11843 | 4.707 | 1.463 | no | 144 | 206 | yes | 0.46 | 0.76 |
| `S-Vta30` | 8559 | 4.441 | 1.172 | no | 171 | 106 | no | 0.46 | 0.77 |
| `S-Vtb1` | 16220 | 6.016 | 4.444 | no | 167 | 154 | no | 0.39 | 0.69 |
| `S-Vtb2` | 2847 | 4.823 | 1.142 | no | 128 | 140 | yes | 0.49 | 0.76 |
| `S-Vtb5` | 32185 | 5.979 | 0.980 | no | 202 | 75 | no | 0.40 | 0.67 |
| `S-Vw14b` | 9785 | 4.019 | 0.731 | no | 115 | 43 | no | 0.53 | 0.82 |
| `S-Vw14c` | 7904 | 4.567 | 1.283 | no | 121 | 190 | yes | 0.55 | 0.79 |
| `S-Vw16a` | 2930 | 5.195 | 1.090 | no | 103 | 236 | yes | 0.39 | 0.69 |
| `S-Vw2` | 26347 | 4.192 | 1.080 | no | 158 | 54 | no | 0.51 | 0.81 |
| `S-Vw4` | 63254 | 5.492 | 1.287 | no | 163 | 257 | yes | 0.40 | 0.70 |
| `S-Y1` | 35133 | 6.922 | 1.698 | no | 196 | 168 | no | 0.33 | 0.56 |

## ONNX / Android asset contract

- Model and APK asset byte-identical: **True** (sha256 `352c6ce456ad4a5d`).
- ONNX I/O: `imu` [1, 6, 20] → `outputs` [1, 6].
- Evaluation and production export are separate: run `export_avnet_production.py` only after the leave-file-out gate.
- Physical-phone inference latency is not measured by this workstation run.

## Verdict

**Per-window wash:** model median RMSE 5.068 m/s vs hold 1.280 m/s; beats hold on 0/23 folds.

**Closed-loop mixed:** model median 60 s distance error 158.3 m vs frozen 163.2 m (9/23 folds win).
