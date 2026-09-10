# Compass-on map-in-loop experiment

Follow-on experiment only; the frozen mapfilter baseline is unchanged.
Compass offset is calibrated from the last phone GNSS bearing at outage onset.

Protocol: segments=12, particles=600, yaw_sigma=0.3.
Frozen mapfilter/report.json (2.02x, n=43) was not overwritten.

## junctions

| policy | median error | median drift | under 10% |
|---|---:|---:|---:|
| `free` | 252.66 m | 27.58% | 8/43 |
| `map_gyro` | 125.20 m | 16.77% | 17/43 |
| `map_compass` | 376.56 m | 33.21% | 3/43 |

Compass/map-gyro endpoint ratio: **0.332x**; compass helped 14/43 windows.

## corridor

| policy | median error | median drift | under 10% |
|---|---:|---:|---:|
| `free` | 252.66 m | 27.58% | 8/43 |
| `map_gyro` | 122.69 m | 16.89% | 17/43 |
| `map_compass` | 263.98 m | 25.69% | 4/43 |

Compass/map-gyro endpoint ratio: **0.465x**; compass helped 15/43 windows.

## Headline impact (frozen 2.02x not overwritten)

Same 43 junctions-live windows as the frozen mapfilter result: `map_gyro` median 125.20 m reproduces **2.02x** vs free DR.
`map_compass` median 376.56 m is **0.332x** vs gyro and **0.67x** vs free DR (worse than free).
Replacing the shipped map-in-loop policy with onset-calibrated compass would move
the 2.02x headline. That replacement is **not** applied here.
Heading-channel 16.87%→7.22% does not transfer to map-in-loop position.

## Scope

Follow-on experiment only. Frozen `lab/stress/results/mapfilter/` claims stay
until the parent decides. Smoke results under `mapfilter_compass/smoke/` are untouched.
