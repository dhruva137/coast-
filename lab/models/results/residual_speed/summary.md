# Residual-on-persistence speed model

Reproduce: `python -m lab.models.run_residual_speed --epochs 12`

## Claims registration — do not register this run

Source: `lab/models/results/residual_speed/report.json`. The rollout gate was not met (need residual rollout fold-wins > absolute fold-wins, and mean |Δ̂| ≥ 0.05 m/s). Numbers below are measured, not product claims:

| suggested claim | report.json field | measured value |
|---|---|---:|
| n_folds | `n_folds` | 23 |
| hold per-window RMSE (median) | `hold_rmse` | 1.280403 |
| absolute per-window RMSE (median) | `abs_rmse` | 5.319188 |
| residual teacher-forced RMSE (median, diagnostic) | `res_tf_rmse` | 1.247508 |
| residual **rollout** RMSE (median, headline) | `res_roll_rmse` | 6.980943 |
| hold 60 s distance error (median) | `hold_cl` | 7.748650 |
| absolute 60 s distance error (median) | `abs_cl` | 146.626090 |
| residual teacher-forced 60 s (median, diagnostic) | `res_tf_cl` | 11.491597 |
| residual **rollout** 60 s (median, headline) | `res_roll_cl` | 213.518402 |
| mean \|Δ̂\| teacher-forced | `mean_abs_delta_tf` | 0.398565 |
| mean \|Δ̂\| **rollout** (copier guard) | `mean_abs_delta_roll` | 0.368570 |
| absolute fold-wins vs hold | `abs_beats_hold` | 0/23 |
| residual rollout fold-wins vs hold | `res_roll_beats_hold` | 0/23 |
| residual teacher-forced fold-wins vs hold | `res_tf_beats_hold` | 13/23 |
| copier (`mean_abs_delta_roll` < 0.05) | `copier` | false |
| epochs | `epochs` | 12 |
| ss p_max | `scheduled_sampling.p_max` | 0.5 |

COAST-VNet-1 loses to "hold the last known speed" on every leave-file-out fold.
The diagnosis is structural: the 6-channel model sees only `(20, 6)` accelerometer
and gyroscope, and is never shown the previous speed -- the sole input the
baseline uses. This tests supplying it and predicting a correction:

    v̂ = v_prev + Δ̂        v_prev appended as a 7th input channel

**n_folds = 23** leave-file-out (all clean CAN-labelled drives this run:
23). `--folds 0` means every clean drive, not a
smoke subset. Headlines below are **rollout / closed-loop**. Teacher-forced
per-window RMSE is a diagnostic: in deployment `v_prev` is the model's own
estimate.

## Verdict

**No improvement on rollout.** Absolute beats persistence on 0/23 folds, residual rollout on 0/23 (teacher-forced residual 13/23). The reformulation did not help under the deployment contract and should not be adopted on this evidence. Median 60 s closed-loop distance error (rollout / headline): residual **213.5 m** vs persistence 7.7 m and absolute 146.6 m. Teacher-forced residual closed-loop is 11.5 m (diagnostic).

## Results (23 folds, 12 epochs, Huber on the mean, scheduled sampling p→0.5 after 4 warmup epochs, cuda, 1863.5s)

| model | median per-window RMSE | beats persistence | median 60 s distance error |
|---|---:|---:|---:|
| Hold last speed (baseline) | **1.280 m/s** | — | 7.7 m |
| Absolute (current 6-ch design) | 5.319 m/s | 0/23 | 146.6 m |
| Residual, teacher-forced (diagnostic) | 1.248 m/s | 13/23 | 11.5 m |
| **Residual, rollout (headline)** | **6.981 m/s** | **0/23** | **213.5 m** |

Mean |Δ̂| teacher-forced = 0.399 m/s. Mean |Δ̂| **rollout**
= **0.369 m/s**. Copier guard: reject if rollout
mean |Δ̂| < 0.05 m/s (this run: **not a copier**).

## Why persistence can no longer win outright on teacher-forcing

Emitting Δ̂ = 0 reproduces the baseline exactly when `v_prev` is the true
previous speed, so the baseline is the model's floor rather than its competitor
on the teacher-forced metric. Rollout is the honest test: the first window uses
the true `v_prev`, then each later window's 7th channel is the model's own
estimate from ~2.0 s earlier (the same lag `_hold_label` uses).

## Limitations

- Scheduled sampling mixes the model's own `v_prev` with probability rising
  from 0 to 0.5 after 4 teacher-forced warmup
  epochs; it is not always-on full rollout training.
- Huber loss on the mean only. The log-variance head is not trained here,
  deliberately: the NLL coupling is what produced the variance-inflation
  pathology documented in `../nll_diagnosis/`.
- Closed-loop error is along-track distance from integrating speed. It does not
  include heading error, so it is not a full position result.
- Sampling is 10 Hz, so Nyquist is 5 Hz. The architecture's high-frequency
  branch was designed for road and engine vibration at 20–100 Hz and cannot
  observe it at this rate. Resampling the IMU to 50–100 Hz may be worth more
  than further architecture changes.

## Per fold

| held-out | n | hold RMSE | absolute | residual TF | residual rollout | mean \|Δ̂\| TF | mean \|Δ̂\| roll |
|---|---:|---:|---:|---:|---:|---:|---:|
| `S-M` | 52978 | 3.448 | 4.400 | 3.151 | 4.819 | 0.602 | 0.623 |
| `S-S1` | 25864 | 1.324 | 3.247 | 1.304 | 3.178 | 0.341 | 0.410 |
| `S-S2` | 46929 | 1.481 | 5.185 | 1.684 | 4.530 | 0.840 | 0.602 |
| `S-S3a` | 12301 | 1.251 | 5.319 | 1.864 | 4.782 | 0.620 | 0.481 |
| `S-S3b` | 3397 | 1.521 | 4.341 | 1.456 | 2.473 | 0.859 | 0.779 |
| `S-S3c` | 18582 | 1.236 | 8.298 | 1.248 | 8.081 | 0.526 | 0.522 |
| `S-S4` | 47291 | 4.634 | 6.818 | 4.444 | 6.981 | 0.667 | 0.485 |
| `S-Vfa01` | 5734 | 1.277 | 5.925 | 1.233 | 7.821 | 0.318 | 0.300 |
| `S-Vfa02` | 33752 | 0.799 | 6.021 | 0.799 | 15.224 | 0.223 | 0.169 |
| `S-Vta16` | 5658 | 1.147 | 4.418 | 0.998 | 3.727 | 0.357 | 0.369 |
| `S-Vta1a` | 12829 | 1.280 | 6.361 | 1.450 | 7.739 | 0.403 | 0.359 |
| `S-Vta2` | 5486 | 1.295 | 7.112 | 1.174 | 6.234 | 0.421 | 0.258 |
| `S-Vta29` | 11843 | 1.463 | 4.929 | 1.711 | 5.610 | 0.361 | 0.404 |
| `S-Vta30` | 8559 | 1.172 | 4.618 | 1.077 | 4.010 | 0.488 | 0.454 |
| `S-Vtb1` | 16220 | 4.444 | 6.398 | 4.644 | 7.704 | 0.338 | 0.303 |
| `S-Vtb2` | 2847 | 1.142 | 4.711 | 1.021 | 3.834 | 0.399 | 0.322 |
| `S-Vtb5` | 32185 | 0.980 | 6.205 | 1.306 | 10.291 | 0.367 | 0.272 |
| `S-Vw14b` | 9785 | 0.731 | 4.431 | 0.755 | 12.977 | 0.146 | 0.084 |
| `S-Vw14c` | 7904 | 1.283 | 4.626 | 1.181 | 4.558 | 0.470 | 0.483 |
| `S-Vw16a` | 2930 | 1.090 | 5.941 | 1.223 | 10.650 | 0.350 | 0.263 |
| `S-Vw2` | 26347 | 1.080 | 4.594 | 0.839 | 19.340 | 0.292 | 0.296 |
| `S-Vw4` | 63254 | 1.287 | 5.589 | 1.190 | 7.334 | 0.246 | 0.244 |
| `S-Y1` | 35133 | 1.698 | 7.155 | 2.368 | 9.588 | 1.101 | 0.369 |
