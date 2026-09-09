# 05 — Demo Modes + Stability + Sensor-Injection

**Goal:** the features that make the claims *believable in the room*, and the
hardening that keeps the app from crashing while a judge holds it. Owner: Cursor.
Files owned here: `sensor/**`, `nav/**`, `record/**`, `IdrBus.kt`,
`IdrApplication.kt`, `test/**`. **Do not** restyle `ui/**` (that's file 04);
you may *add* state to `IdrBus` that file 04 reads.

---

## P0-1. The Replay / Blackout-Injection engine (the money shot)

The demo cannot take judges on a highway. So we stream a **real IO-VNBD drive
through the real estimator**, indistinguishable from live sensors. This is
honest because it is the real code path fed real recorded sensor data.

### Design — `sensor/SensorSource.kt`

Introduce an interface and two implementations:

```
interface SensorSource {
    fun start(onFrame: ( ImuFrame ) -> Unit, onGnss: (GnssFix?) -> Unit)
    fun stop()
}
```

- **`LiveSensorSource`** — wraps the current `SensorHub` / `GnssHub`
  (`SensorManager`, `SENSOR_DELAY_FASTEST`). This is the existing behaviour,
  refactored behind the interface. The rest of the pipeline must not change.
- **`ReplaySensorSource`** — reads an IO-VNBD `S-*.csv` (smartphone stream) from
  app assets and emits `ImuFrame`s on the **same callback at the recorded 10 Hz
  cadence** (use the real row timestamps, not a fixed delay). Emits GNSS fixes
  from the paired columns until the blackout point.

The estimator downstream (`SimpleIns`, map filter, `OnnxSpeedModel`) **cannot
tell which source it is**. That is the whole point — do not special-case replay
inside the estimator.

### The blackout toggle — `IdrBus`

- Add `val gnssBlackout: StateFlow<Boolean>` + `fun setBlackout(on: Boolean)`.
- When `true`, `ReplaySensorSource` (and in live mode, the location path)
  suppresses GNSS fixes → the estimator runs pure inertial + map-lock.
- The HUD pill (file 04) flips GNSS→IDR off this flow.

### Demo flow this enables (Round 2)

1. Play a bundled drive. GNSS green, dot on road.
2. Tap **"Simulate GNSS Blackout"**. Pill flips amber → "IDR MODE". Satellites → 0.
3. Dot keeps following the curved road through the tunnel stretch.
4. Tap **"Restore GNSS"**. Pill back to green, **no teleport jump** (the
   `VehicleSmoother` snap-vs-slide logic already handles the re-acquisition).

**Acceptance:** with airplane mode ON, the full blackout demo runs start to
finish from bundled assets, dot visibly following the road.

### Assets to bundle

- 1–2 short IO-VNBD `S-*.csv` drives that (a) have a clean 50–200 m straight +
  curve, (b) are inside the OSM mbtiles bbox (file 04). Pick with
  `lab/eval/demo_plots.py`'s validated picker (dt sanity + 200–1600 m segment).
  Keep them small; strip to the demo window.

---

## P0-2. Stability hardening (so it survives a judge's hands)

Audit and fix across `nav/**`, `sensor/**`, `record/**`, `IdrBus`:

1. **NaN/Inf guards** — every estimator output (position, speed, heading,
   uncertainty) passes through a `sanitize()` that drops NaN/Inf and holds the
   last good value. The existing `uncertaintyDrawable()` test shows the pattern.
2. **ONNX load-fail fallback** — if `OnnxSpeedModel` fails to load or infer,
   fall back to the physics speed estimate and log it; **never crash**. Add a
   unit test that forces a load failure.
3. **Lifecycle** — rotation, background/foreground, screen-off must not crash or
   lose the track. Foreground service keeps recording. Test config-change
   survival.
4. **Permission denial** — if location denied, the app still runs in RELATIVE
   mode (Canvas grid) with an honest message; never a blank screen or crash.
5. **Empty/garbage sensor data** — zero frames, frozen timestamps, duplicate
   timestamps must not divide-by-zero or spin. Guard `dt<=0`.
6. **Memory** — long sessions (20 min) must not grow the trail unbounded; cap /
   decimate the drawn polyline.

## P0-3. Sensor-injection test (prove the pipeline actually moves)

This is the "is the app *really* working, or just animating?" proof the user
asked for. Add instrumented + JVM tests under `test/`:

- **`InjectionPipelineTest`** — feed a synthetic `ReplaySensorSource` a scripted
  motion: 3 s still → accelerate forward → **steady left yaw** → **steady right
  yaw** → stop. Assert:
  - forward motion produces eastward/northward displacement (estimate MOVES);
  - a sustained left yaw turns the heading left (sign correct), right yaw right;
  - the "still" segments produce ~zero displacement (ZUPT works);
  - no NaN in any output frame.
- **`LoopClosureTest`** — scripted square path returns near origin; assert
  closure error is bounded (documents drift honestly, does not assert a fake
  small number — just that it's finite and in a sane range).
- These tests are also **demo content**: their pass/fail is the honest answer to
  "does the input pipeline really drive the output?"

**Acceptance:** injecting left vs right yaw visibly moves the estimate in the
correct direction; stationary input yields no drift; all tests green.

---

## P1-1. Ghost car (the visual killer)

Run a **second, deliberately naive estimator** in parallel: pure double-
integration, no map lock, no ZUPT. Render its position as a **red ghost puck**.

- New `nav/NaiveGhostEstimator.kt` — minimal `s = ∬a dt`, heading from raw gyro.
- `IdrBus` exposes `ghostTrack: StateFlow<TrackSnapshot>`.
- File 04 draws the red puck + faint red trail.
- During blackout the red ghost **flies off the road into buildings** while the
  teal puck **hugs the street**. This is the single most persuasive visual we
  have. Label it "naive DR (no map)" vs "COAST".

**Honesty note:** the ghost must be a *real* naive integrator on the *same*
input, not a scripted "bad path". It has to actually diverge on its own.

## P1-2. Tabletop proofs (live, unfakeable, on the judging table)

Two in-app modes that work on a desk, no driving:

- **ZUPT test** — leave phone still; show naive speed drifting to 5→15→40 km/h
  while COAST holds **0.00 m/s**. Two side-by-side speed readouts.
- **Dynamic-alignment test** — place phone at ~35° skew, slide it straight
  forward; show the alignment engine registers motion along the *vehicle* axis,
  not the phone's tilted axis. (If the alignment engine isn't robust enough by
  Friday, mark this **P2** and drop it — do not fake it.)

---

## Constraints

- The estimator's numeric behaviour must NOT change when refactoring behind
  `SensorSource`. Run the full existing test suite before and after; identical
  results on `LiveSensorSource`.
- Replay is clearly labelled "REPLAY — real dataset, real estimator" in the UI
  so no one can say we passed it off as a live drive.
- Nothing here adds a network call.
