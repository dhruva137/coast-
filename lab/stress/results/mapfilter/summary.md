# Road-constrained particle filter vs free dead reckoning

Falsification test for `docs/ARCHITECTURE_V2.md`. Ground truth is the paired CAN 10 Hz trajectory.

Graph: 35631 edges, 3271 km, OpenStreetMap only (`built_from_drive_data: False`). Particles: 600, yaw sigma 0.3 rad/s, gyro low-passed causally at 0.5 Hz.

## Junctions live (open road) - HARDER than the ISRO benchmark

| | median error | median drift % | PASS_ISRO |
|---|---:|---:|---:|
| Free DR | 252.7 m | 27.6 | 8/43 |
| **Map-in-loop PF** | **125.2 m** | **16.8** | **17/43** |

Improvement **2.02x** | helped 28 | hurt 15

- Correct-edge rate: 26% of 43 segments where the true edge could be identified (falsification test 2).
- Spread-vs-error correlation: -0.23 (falsification test 3 - if this is near zero the uncertainty is decorative and must not be shown to a user).

## Corridor (topologically 1D) - models a tunnel/underpass

| | median error | median drift % | PASS_ISRO |
|---|---:|---:|---:|
| Free DR | 252.7 m | 27.6 | 8/43 |
| **Map-in-loop PF** | **122.7 m** | **16.9** | **17/43** |

Improvement **2.06x** | helped 27 | hurt 16

- Correct-edge rate: 37% of 43 segments where the true edge could be identified (falsification test 2).
- Spread-vs-error correlation: -0.27 (falsification test 3 - if this is near zero the uncertainty is decorative and must not be shown to a user).

## Reading these two tables

The corridor scenario is the one the ISRO benchmark actually describes: a tunnel has no junctions, so no branch decision can be got wrong and only along-track speed error accumulates. The junctions scenario is open road with live branches, which IO-VNBD gives us throughout and which is strictly harder than the benchmark.

Quoting a corridor number as though it were a junctions number would be dishonest; quoting a junctions number as the tunnel benchmark would undersell the design. They are reported separately for that reason.
