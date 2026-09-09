# Online alignment eval — branch accuracy vs mount correction

Measured on IO-VNBD with paired CAN truth for scoring. Graph is the independent OSM midlands graph (not built from drives).

Documented baseline correct-edge rate (mapfilter junctions): **26%**. Documented oracle free-DR bound (heading ablation A→D): **~1.57×** — cited as a ceiling, not a claim.

Particles: 600, yaw σ 0.3 rad/s, outage 60 s, gyro LP 0.5 Hz.

## Junctions-live map-in-loop

| Method | What it is | median PF err | PASS_ISRO | correct-edge |
|---|---|---:|---:|---:|
| `baseline` | LP(`-gyro_pitch`) shipped contract | 123.9 m | 8/19 | **32%** of 19 |
| `online` | GNSS-prefix scale+bias on mapped gz *(deployable)* | 120.4 m | 8/19 | **32%** of 19 |
| `oracle_mount` | CAN 3-axis mount + LP *(oracle)* | 153.9 m | 7/19 | **37%** of 19 |

## Free-DR median error (same segments; heading only)

| Method | median free-DR err | vs baseline |
|---|---:|---:|
| `baseline` | 136.9 m | 1.00× |
| `online` | 160.3 m | 0.85× |
| `oracle_mount` | 252.1 m | 0.54× |

Oracle free-DR improvement measured here: **0.54×** (document bound ~1.57×). Online free-DR improvement measured here: **0.85×**.

Note: this junctions cohort is n=19 PF-successful segments (mapfilter paper run was 43). Compare online to **this run's** baseline; the published 26% / ~1.57× figures are cited as context only.

## Online calibration trust

Prefix fits attempted: **26**. Trusted (applied): **13**. Abstained → baseline: **13**.

Abstention reasons are recorded in `report.json` (`online_calibration.reasons`). A rejected prefix never invents a mount.

## Verdict

**Edge: wash** — 32% vs baseline 32% (doc baseline 26%).

**Free-DR: negative** — online median 160.3 m vs baseline 136.9 m (0.85×; <1 means worse). The documented ~1.57× oracle bound was **not** achieved by the deployable online method on this cohort.

## Limitations

- `oracle_mount` consumes CAN and is **not** a phone method.
- Online fit needs a GNSS-visible turning prefix; many highway segments abstain (weak excitation / scale gate).
- Android `MountCalibration.kt` remains the **straight-line start** UX path (accel gravity + Δv). GNSS-prefix scale+bias was **not** ported into that class in this commit — different protocol, would risk the existing unit suite without a measured on-device win.
- Do not quote online free-DR improvement above the measured ratio, and do not imply the ~1.57× bound was achieved online.
