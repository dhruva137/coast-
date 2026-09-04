# Finals winner architecture — SIH 26168

**Rule zero:** Credibility beats theatre. A scientist-proof demo **owns RED gates** and never sells prototype PASS as ISRO PASS.

## What judges reward

1. Negative results published first (open-loop fails; we measured why).
2. Narrow novelty (lean + branch metric + mount protocol) — not “first InEKF.”
3. Closed-loop learned odometry on **official IO-VNBD**.
4. Live APK that logs and demos the same stack offline.
5. A deployment gate that can fail us.

## Novelty we own (paper-safe)

| Claim | Status |
|---|---|
| Lean-aware phone VDR for two-wheelers | Method ready; field logs still RED |
| Branch / ramp decision metric (not only drift %) | Defined (F12); sim + architecture |
| Mount / axis audit protocol | GREEN on IO-VNBD |
| 10 Hz AVNet-tiny prior → closed-loop outage | **Wired** + leave-file-out (**0 PASS_ISRO** mid 60 s — honest) |
| Map-aided / arclength product mode | Wired; mid-route still RED; label separately from free-DR |

We do **not** claim: first phone InEKF, global SOTA over Qian 2025, ISRO pass without measured rows.

## Stack (finals)

```
phone IMU @ 10 Hz
    → axis contract (gz = -Pitch on IO-VNBD phones)
    → AVNet-tiny speed / yaw prior (~3 ms)
    → bias-calibrated yaw integrate / InEKF
    → known-route map snap (cross-track kill)
    → HUD: mode + uncertainty + abstain
```

## Demo surfaces

| Surface | Purpose |
|---|---|
| Evidence Room / web | Replay FAIL and PASS with provenance |
| `lab/stress/results/` | Canonical numbers |
| Android RECORD | Field enablement |
| Android NAVIGATE | Forced GNSS-deny coast (method demo ≠ certified accuracy) |
| `docs/JUDGE_CROSS_EXAM.md` | 25 hostile Q&As |

## Path beyond the PS

PS asks: software + IO-VNBD plots + &lt;10%/&lt;100 m/km ambition.  
We go beyond with: lean theory, branch metric, blind proof protocol, dual gates, Android quality-gated logging.
