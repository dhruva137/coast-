# Barometer floor-change (B7)

## Status

**Detector implemented and unit-tested** in
`android/.../nav/BaroFloorDetector.kt` (+ `BaroFloorDetectorTest`).

**Field data: pending.** There is no multi-storey car-park barometer log in this
repo to score against. IO-VNBD / demo CSV pressure columns are flat road drives,
not floor-change ground truth.

## Method (phone path)

- Input: `SensorFrame.pressureHpa` (already in the frozen IMU CSV schema).
- EMA smooth → compare to pressure locked at the last accepted floor.
- Accept a step when `|ΔP| ≥ 0.40 hPa` (~one storey near sea level) holds for
  ≥ 1.5 s.
- HUD / Diagnostics: `floorChanged`, relative `floorIndex`, pressure readout.

## Next measurement

Collect a still / walking log in a multi-level car park (phone baro present),
import via RecordService CSV, and replace this note with measured
true-positive / false-positive rates. Until then, do not claim field accuracy.
