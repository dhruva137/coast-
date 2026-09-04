# Map-aided dead reckoning through a 60 s GNSS outage

Graph: `maps/graphs/iovnbd_midlands.graph.npz` - 35631 edges, 3271 km, built from OpenStreetMap only (`built_from_drive_data: False`).

Drives scored: **8** of 25 with CAN truth | segments: **37** | method: `idr_lean`

16 drives were skipped as outside the graph bounding box. IO-VNBD spans the UK Midlands, Derbyshire and several regions of France; one OSM extract covers one bbox. Skipped drives would score `map_error == free_error` and silently dilute the result toward "the map does nothing", so they are excluded rather than counted.

| | median error | median drift % | PASS_ISRO |
|---|---:|---:|---:|
| Free DR | 498.9 m | 45.4 | 3/37 |
| **Map-aided** | **507.7 m** | **45.4** | **4/37** |

Improvement: **0.98x** on median error. Segments where the map helped: 20/37. Segments where it hurt: 16/37.

## Honesty notes

- The map never sees the evaluated drive. The graph is built from OpenStreetMap by `maps/osm_extract.py`; this script asserts `built_from_drive_data == false` before scoring. Contrast `lab/stress/map_aid.py`, which snapped to the drive's own GNSS polyline and is not admissible.
- Map matching can **hurt**: snapping to a confidently wrong road is worse than an honest drift. The `hurt` count above is that failure mode, reported rather than hidden.
- The DR track is decimated 10:1 (10 Hz to 1 Hz) before matching, which is standard for HMM map matching and keeps the Viterbi tractable.
- Scoring is final-position error at the end of the outage, against the CAN trajectory.
