# Road-constrained particle filter vs free dead reckoning

Falsification test for `docs/ARCHITECTURE_V2.md`. Ground truth is the paired CAN 10 Hz trajectory.

Graph: 35631 edges, 3271 km, OpenStreetMap only (`built_from_drive_data: False`). Particles: 300, yaw sigma 0.3 rad/s, gyro low-passed causally at 0.5 Hz.

## Reading these two tables

The corridor scenario is the one the ISRO benchmark actually describes: a tunnel has no junctions, so no branch decision can be got wrong and only along-track speed error accumulates. The junctions scenario is open road with live branches, which IO-VNBD gives us throughout and which is strictly harder than the benchmark.

Quoting a corridor number as though it were a junctions number would be dishonest; quoting a junctions number as the tunnel benchmark would undersell the design. They are reported separately for that reason.
