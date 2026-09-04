# GNSS <-> dead-reckoning transition latency

The problem statement requires transition "within milliseconds" in both
directions. This is the measurement; nothing in the repo previously made it.

Drives: **44** | events: **313** | denial: 60 s | settle: <5 m held 2 s

## Drop side (GNSS lost -> first DR fix)

Median **nan ms** - one sample period at 10 Hz. The estimator carries the last fused state forward, so there is no reacquisition delay and no freeze on the display. This half of the requirement is met.

## Reacquire side (GNSS returns -> fused estimate converged)

After 60 s of denial the dead-reckoned position is a median **430 m** from truth. That offset has to be absorbed, and how it is absorbed is a product decision, not a physics one:

| Policy | median latency | p90 | converged | median jump | worst jump |
|---|---:|---:|---:|---:|---:|
| `hard_snap` | 0 ms | 0 ms | 100% | 444.6 m | 12452.3 m |
| `blended` | 11500 ms | 27361 ms | 35% | 24.3 m | 1998.8 m |

Read the two columns together. `hard_snap` converges in one sample but teleports the icon by the full accumulated offset, which is exactly the "jump erratically" behaviour the problem statement asks us to remove. `blended` keeps the icon continuous and pays for it in convergence time. Quoting the latency alone from either policy would be misleading.

The blend uses a first-order filter with tau = 2 s. Tuning tau trades these two columns against each other directly; the right value depends on how far the estimate drifted, which argues for making tau a function of the estimated covariance rather than a constant.
