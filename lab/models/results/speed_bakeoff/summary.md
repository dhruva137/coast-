# Speed bake-off - leave-file-out, CAN labels

Device: cuda | epochs/fold: 12 | folds: 23

Protocol confirmed: labels are CAN indicated vehicle speed (`speed_data`, `can_only` / `can_10hz`); leave-file-out — train on N-1 drives, score the held-out drive only.

The question is whether the learned speed model beats simply **holding** the last known speed, which is what free dead reckoning does in an outage. RMSE alone is not the point; beating `hold` is.

## Per-window (RMSE)

| | median RMSE | note |
|---|---:|---|
| **Model (AVNet-tiny)** | **5.061 m/s** | beats hold on 0/23 folds |
| Hold last speed | 1.280 m/s | the baseline to beat |
| Predict the mean | 7.970 m/s | the floor |

Median improvement over hold: **-295.3%**.

## Closed-loop / outage distance (60 s)

Integrates model speed vs freezing onset speed over mid-route 60 s windows. This is the along-track metric free DR actually cares about; per-window RMSE can lose while distance still wins.

| | median dist err | median drift % | folds model wins |
|---|---:|---:|---:|
| **Model** | **150.3 m** | **18.0** | 9/23 |
| Frozen onset speed | 163.2 m | 21.1 | — |

## Uncertainty calibration

The model has a Gaussian NLL head. Empirical coverage of its nominal intervals (median over folds): 68% target -> **0.43**, 95% target -> **0.75**. This is what the GNSS+INS fusion reads to decide how far to trust the speed; a well-calibrated head has coverage close to its nominal.

## Per fold

| held-out drive | n | model RMSE | hold RMSE | beats hold | outage model m | outage frozen m | outage win | cov68 | cov95 |
|---|---:|---:|---:|:--:|---:|---:|:--:|---:|---:|
| `S-M` | 52978 | 4.248 | 3.448 | no | 80 | 169 | yes | 0.53 | 0.82 |
| `S-S1` | 25864 | 3.137 | 1.324 | no | 61 | 228 | yes | 0.69 | 0.93 |
| `S-S2` | 46929 | 5.061 | 1.481 | no | 67 | 229 | yes | 0.43 | 0.75 |
| `S-S3a` | 12301 | 4.870 | 1.251 | no | 123 | 44 | no | 0.45 | 0.76 |
| `S-S3b` | 3397 | 4.228 | 1.521 | no | 120 | 81 | no | 0.55 | 0.81 |
| `S-S3c` | 18582 | 7.634 | 1.236 | no | 208 | 167 | no | 0.39 | 0.65 |
| `S-S4` | 47291 | 6.719 | 4.634 | no | 276 | 243 | no | 0.37 | 0.63 |
| `S-Vfa01` | 5734 | 5.454 | 1.277 | no | 150 | 156 | yes | 0.37 | 0.64 |
| `S-Vfa02` | 33752 | 5.548 | 0.799 | no | 250 | 32 | no | 0.40 | 0.68 |
| `S-Vta16` | 5658 | 4.099 | 1.147 | no | 149 | 102 | no | 0.48 | 0.80 |
| `S-Vta1a` | 12829 | 6.049 | 1.280 | no | 224 | 163 | no | 0.32 | 0.60 |
| `S-Vta2` | 5486 | 5.791 | 1.295 | no | 268 | 193 | no | 0.26 | 0.61 |
| `S-Vta29` | 11843 | 4.780 | 1.463 | no | 146 | 206 | yes | 0.45 | 0.75 |
| `S-Vta30` | 8559 | 4.500 | 1.172 | no | 176 | 106 | no | 0.47 | 0.75 |
| `S-Vtb1` | 16220 | 5.831 | 4.444 | no | 168 | 154 | no | 0.39 | 0.70 |
| `S-Vtb2` | 2847 | 4.788 | 1.142 | no | 136 | 140 | yes | 0.49 | 0.76 |
| `S-Vtb5` | 32185 | 5.944 | 0.980 | no | 203 | 75 | no | 0.40 | 0.67 |
| `S-Vw14b` | 9785 | 4.070 | 0.731 | no | 116 | 43 | no | 0.52 | 0.82 |
| `S-Vw14c` | 7904 | 4.505 | 1.283 | no | 115 | 190 | yes | 0.54 | 0.79 |
| `S-Vw16a` | 2930 | 5.255 | 1.090 | no | 109 | 236 | yes | 0.40 | 0.69 |
| `S-Vw2` | 26347 | 4.197 | 1.080 | no | 154 | 54 | no | 0.52 | 0.81 |
| `S-Vw4` | 63254 | 5.599 | 1.287 | no | 169 | 257 | yes | 0.39 | 0.69 |
| `S-Y1` | 35133 | 6.847 | 1.698 | no | 177 | 168 | no | 0.33 | 0.56 |

## ONNX / Android asset contract

- App loads `android/app/src/main/assets/avnet_tiny.onnx` (`OnnxSpeedModel` ASSET = `avnet_tiny.onnx`).
- Byte-identical to `lab/models/weights/avnet_tiny.onnx`: **yes** (sha256 `352c6ce456ad4a5d`).
- ONNX I/O: input `imu` shape `[1, 6, 20]` to output `outputs` shape `[1, 6]` — matches Kotlin `(1, 6, 20)` channel-major layout.
- `lab/models/weights/avnet_v2.onnx` is a **different** bakeoff export (layout `[batch,20,6]` + `avnet_v2_norm.npz` standardiser). The app does **not** load it and does not apply that norm. Do not swap assets without changing `OnnxSpeedModel`.
- Weights **not** regenerated this pass: leave-file-out numbers above are the measured wash (0/23 folds beat hold on per-window RMSE; closed-loop 9/23 outage wins). Retraining would not change the honesty of that finding without new evidence.

## Verdict

**Per-window wash (negative vs hold):** model median RMSE 5.061 m/s vs hold 1.280 m/s; beats hold on 0/23 folds.

**Closed-loop mixed:** model median 60 s distance error 150.3 m vs frozen 163.2 m (9/23 folds). Slight along-track help on some drives does not overturn the per-window wash headline.
