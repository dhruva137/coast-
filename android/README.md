# IDR Android — teammate field logger (v0.3.0)

See also root [`PROGRESS.md`](../PROGRESS.md) for project-wide status.

## Install

1. Build: `build-apk.bat assembleDebug` (or use a shared `app-debug.apk` from Drive).
2. APK output: `app/build/outputs/apk/debug/app-debug.apk` (also copied to local `dist/` which is gitignored).
3. Install on phone → allow unknown sources.
4. Open **IDR** → grant **Location (Precise)**, notifications, sensors.

Package id (debug): `in.sih26168.idr.debug`

## Ride protocol

1. **RECORD** → rider / route / vehicle / **handlebar** mount.
2. Clamp phone → **START RECORDING** (GPS **on**).
3. Chalk mark → **MARK LOOP CLOSURE**.
4. Ride ≥ ~2–3 min / ≥150 m → return → **STOP**.
5. Quality line: `KEEP` / `RETRY` / `FAIL`.
6. **SESSIONS** → CHECK / RENAME / ZIP / DELETE → share zip.

## On-device model (NAVIGATE)

`assets/avnet_tiny.onnx` is a byte-copy of `lab/models/weights/avnet_tiny.onnx`
(AVNet-tiny / FrequencyDecoupledNet) and runs under ONNX Runtime Mobile on the
phone — no server, no laptop. Re-copy it after every retrain.

* input `imu` float32 **(1, 6, 20)** — ax, ay, az, gx, gy, gz, raw SI **with
  gravity**, no normalisation (matches `train_avnet.py` exactly)
* window 20 samples @ 10 Hz = 2.0 s; the 100–500 Hz IMU is **mean-decimated**
  per 100 ms bin so mount vibration cannot alias into the motion band
* output `outputs` float32 (1, 6) — speed, ψ̇, roll_res, pitch_res,
  logvar_speed, logvar_psi; variance is `exp(clamp(logvar, -8, 4))`

The NAVIGATE header shows the live source badge (`GNSS` / `MODEL` / `FALLBACK`),
per-window inference latency in ms and the sustained inference rate in Hz. If the
session fails to load, the badge stays `FALLBACK` and the red line names the
error — the app never fakes a model run.

## Quality gate

Auto-writes `quality.json` on stop. Fails on missing meta, short/low-rate IMU, IMU gaps, too few GNSS fixes, short path/duration. Soft RETRY for poor GNSS accuracy or far loop mark.

Session files: `imu.csv`, `gnss.csv`, `meta.json`, `quality.json`

## Rebuild

```bat
android\build-apk.bat testDebugUnitTest assembleDebug
```

Needs JDK 17 + Android SDK (`local.properties` is local-only, gitignored).
