# GNSS <-> dead-reckoning transition latency

The problem statement requires transition "within milliseconds" in both
directions. This is the measurement; nothing in the repo previously made it.

Drives: **15** | events: **15** | denial: 10 s | settle: <5 m held 2 s

## Drop side (GNSS lost -> first DR fix)

Median **100 ms** across 15/15 valid events. The estimator carries the last fused state forward; the metric is the first valid timestamped DR sample after loss.

## Reacquire side (GNSS returns -> fused estimate converged)

After 10 s of denial the dead-reckoned position is a median **37 m** from truth. That offset has to be absorbed, and how it is absorbed is a product decision, not a physics one:

| Policy | median latency | p90 | converged | median jump | worst jump |
|---|---:|---:|---:|---:|---:|
| `hard_snap` | 0 ms | 0 ms | 100% | 36.8 m | 2942.3 m |
| `blended` | 8000 ms | 68981 ms | 47% | 3.4 m | 650.8 m |
| `adaptive` | 15500 ms | 111741 ms | 20% | 2.2 m | 3.9 m |

Read the two columns together. `hard_snap` converges in one sample but teleports the icon by the full accumulated offset, which is exactly the "jump erratically" behaviour the problem statement asks us to remove. `blended` keeps the icon continuous and pays for it in convergence time. `adaptive` uses only online innovation and propagated covariance, and caps each correction according to uncertainty. Quoting latency without jump would be misleading.

The blend uses a first-order filter with tau = 2 s. Tuning tau trades these two columns against each other directly; the right value depends on how far the estimate drifted, which argues for making tau a function of the estimated covariance rather than a constant.
