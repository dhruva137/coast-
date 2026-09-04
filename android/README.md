# IDR Android — navigation app + field logger (v0.4.0)

See also root [`PROGRESS.md`](../PROGRESS.md) for project-wide status.

The app has two faces. **DRIVE** is the end-user navigation interface a judge
can pick up and use. **RECORD** / **SESSIONS** are the research field-logging
tools the team uses to gather training data; they are unchanged.

## Install

1. Build: `build-apk.bat assembleDebug` (or use a shared APK from Drive).
2. APK output: `app/build/outputs/apk/debug/app-debug.apk`.
3. Install on phone → allow unknown sources.
4. Open **IDR**. Onboarding runs on first launch and can be replayed from HELP.

Package id (debug): `in.sih26168.idr.debug`

No permission is required to start tracking. Location is optional and the app
says so, in those words, on the permissions page.

## DRIVE — the navigation interface

### Modes

The mode badge at the top is the honesty control for the whole app.

| Mode | Meaning | Uncertainty shown |
|---|---|---|
| `GNSS` | Live fix inside the 2 s staleness window | The horizontal accuracy the OS reports. Labelled **MEASURED**. |
| `DEAD RECKONING` | No fix, but an absolute origin exists | `accuracy of last fix + k · distance since`. Labelled **MODELLED**. |
| `RELATIVE` | No absolute anchor at all | `k · distance travelled`, described as displacement uncertainty only. |
| `READY` | Not armed | Nothing. |

`k` defaults to `SimpleIns.DEFAULT_DRIFT_RATE` (0.10), which is the project
benchmark **target**, not a measurement. The UI says so. Close a loop with
MARK HERE → CLOSE LOOP and `k` is replaced by the drift this session actually
measured, and relabelled.

### Working with location off

This is the core behaviour, and it is covered by
`app/src/test/java/in/sih26168/idr/nav/RelativeModeTest.kt`.

* **Permission denied / location switched off / no provider.** START still
  arms. `SimpleIns` integrates east/north displacement from the IMU regardless.
  `lat`/`lon` are `NaN` and the UI renders "unknown", never 0,0.
* **Permission granted, no fix yet.** Same, plus a banner saying a cold start
  takes a minute outdoors and may never arrive indoors.
* **Fix acquired then lost.** Mode drops to `DEAD RECKONING`, the origin is
  retained, the icon keeps moving, and the uncertainty circle grows and turns
  dashed. Re-acquisition snaps the track back and resets the error.
* **User-set start point.** Long-press the map (or SET START POINT) to type
  coordinates. `originSource` becomes `USER_COORDS`/`USER_MAP` and the error
  model reports growth only — the error of a hand-placed anchor is unknown and
  is excluded, which the dialog and the accuracy card both state.

### North

`headingDeg` is integrated from the gyro starting at an arbitrary zero. It is
a compass bearing only after a GNSS bearing has seeded it
(`HudState.headingReferenced`). Until then the map draws **no north arrow** and
labels the up axis "the way you were facing at start".

### Map

Canvas metre grid with a labelled scale bar, the estimator track in orange, the
raw GNSS track dashed teal, the origin crosshair, the vehicle chevron and the
uncertainty circle. The camera is spring-smoothed; positions are not.

**MapLibre is still off.** It needs tiles, and the repo has none: `maps/style.json`
points at a network CARTO raster source, and there are no `.mbtiles`/`.pmtiles`
anywhere. A basemap that blanks without wifi is worse at the venue than an
honest metre grid. Re-enable it only together with bundled offline tiles — the
commented dependency in `app/build.gradle.kts` and `settings.gradle.kts` is
still there.

### Diagnostics

Every research readout from the old NAVIGATE screen, moved behind the
DIAGNOSTICS toggle and nothing dropped: lean angle, car-style heading delta,
coordinated-turn flag, inference latency, sustained inference Hz, model speed
and sigma, model error string, IMU rate, measured sensor rates, satellite
count, fix age, outage, loop closure and measured drift. The toggle state
persists.

## Sensor self-check

`sensor/DeviceProbe.kt` runs at startup.

* `inventory()` — instant `SensorManager` query: presence, name, vendor,
  resolution, range, and the **advertised** rate from `minDelay`.
* `probe()` — registers accel + gyro at `SENSOR_DELAY_FASTEST` for 2.5 s and
  **counts events**, because advertised and real rates disagree on mid-range
  hardware. Both numbers are shown, each labelled.

Verdict is `PASS` / `DEGRADED` / `FAIL`. No gyroscope is a `FAIL` and the card
says dead reckoning will not work on that phone. A driver name containing
`virtual`/`software`/`fusion`/... raises a `DEGRADED` warning — this is a
**heuristic**, and the card prints the raw name and vendor beside it so a reader
can judge. A `DEGRADED`/`FAIL` verdict also appears on the DRIVE screen.

## Mount calibration

`nav/MountCalibration.kt`. The user stands still, presses START, then moves
straight for 8 s.

* Gravity comes from the **stationary lead-in only**. Using the mean of the whole
  capture would cancel a constant forward acceleration exactly and make a real
  start look like standing still — this was caught by a unit test and is now a
  regression guard.
* `forward` = normalised horizontal integral of `(a − gravity)`. Starting from
  rest resolves the sign, which a principal-axis fit cannot.
* `right = down × forward`, giving the right-handed aerospace body frame
  (x forward, y right, z down) that `solveLean` and `stepHeading` are written
  against. `MountCalibrationTest` asserts a pure world-vertical rotation lands
  entirely on vehicle `gz`.

Rejected when the lead-in was not still, when the phone turned, or when the
speed change was too small. A rejected run stores nothing: a confidently wrong
mount frame is worse than none. Uncalibrated runs keep the historical raw-axis
behaviour and Diagnostics says `raw device axes -- not calibrated`.

## Onboarding

Five pages, skippable, replayable from HELP: what the app does · which
permissions and exactly why (motion sensors for dead reckoning, location for the
initial fix and re-acquisition, notifications for screen-off) · how to mount the
phone (rigid mount best and worth buying, pocket/bag workable with reduced
accuracy, nothing loose or hand-held) · the calibration run · how to read the
main screen.

## Ride protocol (research logging, unchanged)

1. **RECORD** → rider / route / vehicle / **handlebar** mount.
2. Clamp phone → **START RECORDING** (GPS **on**).
3. Chalk mark → **MARK LOOP CLOSURE**.
4. Ride ≥ ~2–3 min / ≥150 m → return → **STOP**.
5. Quality line: `KEEP` / `RETRY` / `FAIL`.
6. **SESSIONS** → CHECK / RENAME / ZIP / DELETE → share zip.

## On-device model

`assets/avnet_tiny.onnx` is a byte-copy of `lab/models/weights/avnet_tiny.onnx`
(AVNet-tiny / FrequencyDecoupledNet) and runs under ONNX Runtime Mobile on the
phone — no server, no laptop. Re-copy it after every retrain.

* input `imu` float32 **(1, 6, 20)** — ax, ay, az, gx, gy, gz, raw SI **with
  gravity**, no normalisation (matches `train_avnet.py` exactly)
* window 20 samples @ 10 Hz = 2.0 s; the 100–500 Hz IMU is **mean-decimated**
  per 100 ms bin so mount vibration cannot alias into the motion band
* output `outputs` float32 (1, 6) — speed, ψ̇, roll_res, pitch_res,
  logvar_speed, logvar_psi; variance is `exp(clamp(logvar, -8, 4))`

Diagnostics shows the live source badge (`GNSS` / `MODEL` / `FALLBACK`),
per-window inference latency in ms and the sustained rate in Hz. If the session
fails to load, the badge stays `FALLBACK` and a red line names the error — the
app never fakes a model run.

## Quality gate

Auto-writes `quality.json` on stop. Fails on missing meta, short/low-rate IMU,
IMU gaps, too few GNSS fixes, short path/duration. Soft RETRY for poor GNSS
accuracy or far loop mark.

Session files: `imu.csv`, `gnss.csv`, `meta.json`, `quality.json`

## Rebuild

```bat
android\build-apk.bat testDebugUnitTest assembleDebug
```

Needs JDK 17 + Android SDK (`local.properties` is local-only, gitignored).

On Windows, a short-path `TEMP` (`DHRUVA~1`) breaks the AF_UNIX pipes Gradle
uses. Set a clean one first:

```bat
set TEMP=C:\tmp
set TMP=C:\tmp
```

## Tests

`./gradlew testDebugUnitTest` — 32 tests, all JVM, no device or emulator.

* `RelativeModeTest` — every location-off state, the user-set origin, fix
  loss and re-acquisition, the uncertainty model, loop closure.
* `MountCalibrationTest` — frame convention, orthonormality, sign resolution,
  and each rejection path.
* `LeanSolverTest`, `QualityGateTest` — pre-existing.
