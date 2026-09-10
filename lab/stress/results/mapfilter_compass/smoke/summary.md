# Compass-on map-in-loop experiment

Follow-on experiment only; the frozen mapfilter baseline is unchanged.
Compass offset is calibrated from the last phone GNSS bearing at outage onset.

## junctions

| policy | median error | median drift | under 10% |
|---|---:|---:|---:|
| `free` | 284.04 m | 41.09% | 0/3 |
| `map_gyro` | 328.58 m | 20.87% | 1/3 |
| `map_compass` | 606.37 m | 27.11% | 0/3 |

Compass/map-gyro endpoint ratio: **0.542x**; compass helped 1/3 windows.

## corridor

| policy | median error | median drift | under 10% |
|---|---:|---:|---:|
| `free` | 284.04 m | 41.09% | 0/3 |
| `map_gyro` | 115.24 m | 19.48% | 1/3 |
| `map_compass` | 115.24 m | 19.48% | 1/3 |

Compass/map-gyro endpoint ratio: **1.000x**; compass helped 1/3 windows.

## Scope

This is an experiment result, not a replacement claim. A full run over all
eligible outage windows is required before changing any frozen report or claim.
