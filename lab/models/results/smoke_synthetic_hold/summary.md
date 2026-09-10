# Experiment: `smoke_synthetic_hold`

- status: **dry_run**
- arch: `hold_baseline`
- objective: `mse`
- features: `raw`
- folds: 3
- epochs: 1
- seed: 26168

## Metrics

| field | value |
|---|---|
| per-window RMSE (m/s) | 0.4378 |
| hold baseline RMSE (m/s) | 0.4304 |
| RMSE vs hold (m/s) | 0.0074 |
| closed-loop 60 s dist err (m) | 0.0000 |
| outage drift % | 0.0000 |
| mount-swap ΔRMSE | null |
| params | 0 |
| ONNX size (bytes) | null |
| on-device latency (ms) | null |

**Closed-loop note:** closed-loop measured on synthetic 60 s integrate; not a field / IO-VNBD product number

## Allowed claims

- *(none)*

## Honesty / disagreement flags

- disagreement: per-window loses to hold, closed-loop wins  -  report both (this pattern appears in the AVNet bake-off)
- suppressed synthetic win_claims  -  dry-run is not a product result

## Notes

- Harness smoke / dry-run unless a real fold_fn and IO-VNBD trainer are plugged in.
- IO-VNBD found locally
- mount_swap / onnx / latency left null deliberately  -  not measured.

## Rule

A run cannot claim a product win from per-window RMSE alone. Closed-loop must be present (value or null + note).
