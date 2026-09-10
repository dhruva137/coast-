# Experiment leaderboard

| name                 | status  | pw_rmse | hold_rmse | vs_hold | cl_60s_m | drift_% | mount_drmse | params | onnx_B | lat_ms |
| -------------------- | ------- | ------- | --------- | ------- | -------- | ------- | ----------- | ------ | ------ | ------ |
| smoke_synthetic_hold | dry_run | 0.438   | 0.430     | 0.007   | 0.000    | 0.000   | null        | 0      | null   | null   |

Rule: per-window RMSE alone is not a win. `cl_60s_m` must be present (value or null with note in metrics.json).
