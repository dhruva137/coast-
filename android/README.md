# IDR Android — navigation app + field logger (v0.4.0, versionCode 4)

See also root [`PROGRESS.md`](../PROGRESS.md) for project-wide status.

The app has two faces. **DRIVE** is the end-user navigation interface a judge
can pick up and use. **RECORD** / **SESSIONS** are the research field-logging
tools the team uses to gather training data; they are unchanged.

## Install

1. Build: `build-apk.bat assembleDebug` (or use a shared APK from Drive).
2. APK output: `app/build/outputs/apk/debug/app-debug.apk`.
3. Install on phone → allow unknown sources.
4. Open **IDR Navigator**. Onboarding runs on first launch and can be replayed
   from HELP.

Package id (debug): `in.sih26168.idr.debug` · release: `in.sih26168.idr`

No permission is required to start tracking. Location is optional and the app
says so, in those words, on the permissions page. **Nothing is requested at
launch** — every permission dialog in this app is fired by a control the user
pressed, next to the sentence explaining it.

## Permissions — what is declared and why

Every permission below is reached by code in this app. Verified against the
built release APK with `aapt2 dump badging`, not against the manifest source.

| Permission | Level | Where it is used | Why it cannot be dropped |
|---|---|---|---|
| `FOREGROUND_SERVICE` | normal | `record/RecordService.kt` | Tracking and logging must survive the screen going off. |
| `FOREGROUND_SERVICE_LOCATION` | normal | `RecordService.startInForeground` | API 34+ requires one permission per declared `foregroundServiceType`. Declared only when the location grant is actually held; see below. |
| `FOREGROUND_SERVICE_DATA_SYNC` | normal | `RecordService.startInForeground` | Same, for the CSV stream. Also the fallback type when location is denied. |
| `POST_NOTIFICATIONS` | dangerous, API 33+ | `ui/Permissions.kt`, asked at START | Without it the ongoing "tracking is running" notice is invisible. A foreground service the user cannot see is the definition of sketchy. |
| `WAKE_LOCK` | normal | `RecordService.onCreate` | The CPU has to stay awake to integrate the IMU with the screen off. |
| `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` | dangerous | `sensor/GnssHub.kt`, `sensor/LocationGate.kt` | The initial anchor fix and re-acquisition after an outage. **Optional at runtime** — refusing them puts the app in RELATIVE mode, which is a supported, tested state. |
| `HIGH_SAMPLING_RATE_SENSORS` | normal, API 31+ | `sensor/SensorHub.kt`, `sensor/DeviceProbe.kt` | Required to sample above 200 Hz. `SENSOR_DELAY_FASTEST` is what the estimator and the 10 Hz mean-decimation window are built on. Install-time, never shown to the user. |

`in.sih26168.idr.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` also appears in the
built APK. It is injected by androidx.core, is signature-level, and is scoped to
this app's own package — it grants nothing to anyone else.

### Removed in v0.4.0, and why

| Removed | Reason |
|---|---|
| `BODY_SENSORS` | Never used. An accelerometer and a gyroscope are not body sensors and need no runtime grant at all; this was declared "so the permission sheet matches the problem statement". Asking for a dangerous permission the code never touches is the fastest way to make a stranger refuse the ones that matter. |
| `INTERNET` | The only thing that used it was IBM Plex over Play Services downloadable fonts. Removing both makes "nothing leaves this phone" enforced by Android rather than promised by us — see [Privacy](#privacy). Fonts are now `FontFamily.Monospace` / `SansSerif`, which also cannot fail to arrive at a venue with no wifi. |
| `FOREGROUND_SERVICE_SPECIAL_USE` | `specialUse` requires a hand-written justification reviewed manually on every Play submission. `location` and `dataSync` describe what the service actually does, so the special case was never needed. |

### Never declared

* **`ACCESS_BACKGROUND_LOCATION`** — not present, and must stay that way. The
  foreground service covers the real case (screen off, still riding). Play
  reviews this permission by hand and it would be a lie here.
* No analytics, crash reporting, advertising or network SDK of any kind. The one
  third-party runtime dependency is ONNX Runtime, which reads a file out of
  `assets/` and does arithmetic.

### Foreground service type

`location|dataSync` in the manifest. At runtime `RecordService` declares
`FOREGROUND_SERVICE_TYPE_LOCATION` **only when the location permission is held** —
declaring it without the grant throws and kills the process. Without it the
service still starts as `dataSync`, which is what the IMU stream is.

The notification names what is being read and where it goes, in four variants
(navigate/record × with/without GPS), because that notice is the only thing a
user sees while the screen is off. Navigation says "nothing is recorded to
disk"; recording says which files are written and that nothing is uploaded.

## Privacy

`ui/PrivacyNote.kt`, shown on onboarding page 2 and in HELP. Every claim in it
was checked against the code before it was written:

* No HTTP client, socket, WebSocket or network SDK in the dependency graph.
  `grep -rniE "http|url|socket|okhttp|retrofit"` over `app/src/main` returns two
  hits, both of them English prose in UI copy.
* No `INTERNET` permission, so the platform blocks any outbound connection
  regardless of what the code tries.
* `android:usesCleartextTraffic="false"`, `android:allowBackup="false"`, and both
  `res/xml/data_extraction_rules.xml` (API 31+) and `res/xml/backup_rules.xml`
  (API 30-) exclude every domain — ride logs are not swept into a cloud backup
  or a device-to-device transfer either.
* The model runs on-device under ONNX Runtime from `assets/avnet_tiny.onnx`.

**If any of that stops being true, the note has to change in the same commit.**

### What RECORD writes, and where

Shown in-app immediately above the START RECORDING button
(`ui/PrivacyNote.kt:RecordDataDisclosure`), naming each file:

```
Android/data/in.sih26168.idr/files/data/<rider>/<vehicle>/<YYYYMMDD_HHMMSS>/
  imu.csv       raw accel / gyro / mag / pressure / lux at the full sensor rate
  gnss.csv      every fix: lat, lon, alt, speed, bearing, accuracy, satellites
  meta.json     rider, route, vehicle, mount, phone model, as typed
  quality.json  the pass/fail score, written on stop
```

`gnss.csv` is a record of where a person actually went, so the disclosure says
that in those words. The folder is app-scoped: uninstalling deletes it, and the
only way a log leaves the phone is the user pressing SHARE on a session zip in
SESSIONS.

DRIVE-tab navigation writes **nothing at all**.

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
permissions and exactly why, plus the privacy note (motion sensors for dead
reckoning and no grant needed, location optional for the initial fix and
re-acquisition, notifications so screen-off tracking is visible) · how to mount
the phone (rigid mount best and worth buying, pocket/bag workable with reduced
accuracy, nothing loose or hand-held) · the calibration run · how to read the
main screen.

Page 2 is the only place a permission is requested during onboarding, and only
when the user presses GRANT PERMISSIONS. There is no automatic request anywhere
in the app.

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

Inference runs on a dedicated `idr-onnx` worker thread, never on the IMU handler
thread and never on the main thread. A window that closes while the previous
inference is still running is **dropped**, not queued — a queued window would be
delivered to the user as current speed.

Diagnostics shows the live source badge (`GNSS` / `MODEL` / `FALLBACK`),
per-window inference latency in ms, the sustained rate in Hz, and the dropped-
window count. If the session fails to load, the badge stays `FALLBACK` and a red
line names the error — the app never fakes a model run.

## Quality gate

Auto-writes `quality.json` on stop. Fails on missing meta, short/low-rate IMU,
IMU gaps, too few GNSS fixes, short path/duration. Soft RETRY for poor GNSS
accuracy or far loop mark.

Session files: `imu.csv`, `gnss.csv`, `meta.json`, `quality.json`

## Performance — why the UI is not laggy any more

Four compounding causes, found by reading the code, each fixed and commented at
the site so the fix can be explained out loud.

**1. The track was appended at the full IMU rate.** `SimpleIns.onImu` pushed a
`TrailPoint` on every sample. `SensorHub` runs at `SENSOR_DELAY_FASTEST`, so
that is 200-500 points a second. The 4000-point cap then meant the visible track
was only the last 8-20 **seconds** of the ride — everything older had already
fallen off the front of the deque. Points are now retained by distance (2 m) or
by time (1 s), whichever comes first, so the cap of 1500 means roughly 3 km of
track and the drawn line is geometrically the same to the eye. GNSS fixes are
never decimated away. `TrailDecimationTest` pins all of it.

**2. Every HUD frame copied the whole track.** `snapshot()` did
`insTrail.toList()` **and** `gnssTrail.toList()` on every call, at 20 Hz, into a
`StateFlow` the entire screen collected — up to 160 000 element copies a second
so that a speed readout could change. The track moved to its own
`TrackSnapshot` on its own flow (`IdrBus.track`), rebuilt only when a point is
actually appended and returned as the *same instance* otherwise, and published
at 4 Hz. The HUD itself is now 10 Hz rather than 20.

**3. `HudState` was unstable, so nothing could skip.** A `List` field makes the
Compose compiler infer the whole class unstable, and every composable taking one
becomes unskippable. Removing the two lists and adding `@Immutable` (with
`@Immutable` on the rest of `data/Models.kt`) makes `HudState` skippable, and
`ModeHeader` / `LoopClosureLine` now take narrow primitives instead of the whole
frame. `DriveScreen` also stopped calling `hud.copy(navMode = ...)` on every
recomposition, and the SPEED/DISTANCE strings go through `derivedStateOf` so the
tiles recompose when the printed text changes, not when the double does.

**4. The map recomposed at the display refresh rate, and rebuilt its path each
frame.** `val cx by animateFloatAsState(...)` subscribes the *reading composable*
to every animation frame; five springs run in `DriveMap` and while the vehicle
moves they never settle, so `BoxWithConstraints`, its content lambda and all four
`Text` overlays were recomposed continuously for the whole ride. The springs are
now held as `State` and read inside the `Canvas` draw lambda, which invalidates
the draw phase only. The two polylines are built once per track version in
**metres** and cached with `remember(track.version)`; the camera is applied as a
canvas transform rather than by rebuilding the `Path` in screen coordinates. The
camera bounds come from a box the estimator maintains incrementally instead of
rescanning every point in composition, and the scale-bar label is a
`derivedStateOf` so it recomposes only when the rounded value changes.

**Also: ONNX inference now has backpressure.** It was never on the main thread,
but it ran inline on the IMU handler thread, so a slow window stalled the sensor
looper and samples arrived in bursts — a stuttering readout and a jittery track.
`OnnxSpeedModel` now hands a **copy** of the window to a single `idr-onnx`
worker and returns immediately; if a window closes while an inference is still
running that window is **dropped** (`droppedWindows` counts them) rather than
queued, because a queued window would be delivered as current speed.

> **Untested on hardware.** All of the above is verified by compilation, by the
> unit tests, and by the Compose stability and phase rules. Nobody has run this
> build on a phone. Do not quote a frame rate.

## Release build

```bat
android\build-apk.bat testDebugUnitTest assembleRelease bundleRelease
```

| Artifact | Path | Size |
|---|---|---|
| Release APK (universal, both ABIs) | `app/build/outputs/apk/release/app-release.apk` | 31.6 MB |
| Release AAB (what Play wants) | `app/build/outputs/bundle/release/app-release.aab` | 15.3 MB |
| Debug APK | `app/build/outputs/apk/debug/app-debug.apk` | 46.0 MB |

Most of the size is ONNX Runtime's native library — 17.6 MB for arm64 and
11.7 MB for armv7, both stored uncompressed. The universal APK carries both; the
AAB splits them, so a real arm64 install is roughly 21 MB.

### Signing

`app/build.gradle.kts` reads `android/keystore.properties`, which is
**gitignored and must never be committed**:

```properties
storeFile=C:/path/to/idr-release.jks
storePassword=...
keyAlias=idr
keyPassword=...
```

When that file is missing — the normal case for a fresh clone, and for CI —
`assembleRelease` still succeeds, signed with the **debug** key, and Gradle
prints a warning saying so. That build installs and runs for testing; Play will
reject it. This repo contains no keystore and no passwords.

### Minification, and the one rule that matters

`isMinifyEnabled = true` and `isShrinkResources = true`. The resource shrinker
removed 199 unused resources, among them the whole font-provider attribute set.

`proguard-rules.pro` keeps `ai.onnxruntime.**` wholesale. ONNX Runtime is a thin
Java layer over a native library, and the C++ side resolves Java classes and
fields **by name** through JNI — references R8 cannot see. Strip or rename them
and you get a build that compiles, installs, launches, and then fails at
`OrtEnvironment.getEnvironment()`. It would not even crash: the app would fall
back to the labelled FALLBACK integrator and quietly stop being an ML project.

Verified on the actual minified release APK, not assumed:

* `mapping/release/usage.txt` contains **zero** `ai.onnxruntime` removals.
* All 62 ORT classes appear in `mapping.txt` with their original names.
* `dexdump` on the shipped `classes.dex` finds `OrtEnvironment`, `OrtSession`,
  `OrtSession$SessionOptions`, `OnnxTensor`, `OnnxRuntime`, `OnnxValue` and
  `OrtException`, plus the method names `getEnvironment`, `createSession`,
  `createTensor`, `setIntraOpNumThreads`, `setOptimizationLevel` and
  `initialiseAPIBase`, all unrenamed.
* `libonnxruntime.so` + `libonnxruntime4j_jni.so` present for both ABIs, and
  `assets/avnet_tiny.onnx` present at 401 542 bytes, STORED (uncompressed).
* `lintVitalRelease` passes.

> **Untested on hardware.** Nobody has executed a single inference from the
> minified APK on a phone. The evidence above is static analysis of the shipped
> dex; it is strong, but it is not the same as watching the MODEL badge light up.

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

`./gradlew testDebugUnitTest` — **41 tests**, all JVM, no device or emulator.

* `RelativeModeTest` (13) — every location-off state, the user-set origin, fix
  loss and re-acquisition, the uncertainty model, loop closure.
* `MountCalibrationTest` (11) — frame convention, orthonormality, sign
  resolution, and each rejection path.
* `TrailDecimationTest` (9) — **new.** Regression guards for the map
  performance fix: sample-rate independence, the distance/time retention rule,
  that decimation does not lag the estimator, the cap, that `trackSnapshot()`
  returns the same instance until a point is added (so the map's `Path` cache
  holds), that the incremental bounding box agrees with the points, that a GNSS
  fix is never decimated away, and that `reset()` clears and bumps the version.
* `LeanSolverTest` (3), `QualityGateTest` (5) — pre-existing.
