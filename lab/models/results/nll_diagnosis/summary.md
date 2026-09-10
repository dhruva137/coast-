# NLL diagnosis (lab.demo quick run)

Held-out drive: `S-M`

Hold-last-speed baseline RMSE: **3.448 m/s**

## Finding

PARTIAL: NLL loss fell while held-out RMSE rose (5.238→5.390); σ_mean 2.718→2.718. Investigate further — classic inflation if σ climbs.

## Per-epoch log

| epoch | objective | loss | held_rmse | sigma_mean | sigma_median | cl_end_err_m |
|------:|:----------|-----:|----------:|-----------:|-------------:|-------------:|
| 1 | MSE | 149.7390 | 8.724 | 0.239 | 0.239 | 15876.441275046496 |
| 2 | MSE | 68.6629 | 5.248 | 0.269 | 0.269 | 5464.388816693044 |
| 3 | NLL | 60.9500 | 5.238 | 2.718 | 2.718 | 4322.377166560084 |
| 4 | NLL | 3.7320 | 5.390 | 2.718 | 2.718 | 6512.3368278982625 |

Source: live `python -m lab.demo` stdout / `epoch_log.jsonl`. Numbers are measured, not invented.
