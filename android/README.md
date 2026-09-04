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

## Quality gate

Auto-writes `quality.json` on stop. Fails on missing meta, short/low-rate IMU, IMU gaps, too few GNSS fixes, short path/duration. Soft RETRY for poor GNSS accuracy or far loop mark.

Session files: `imu.csv`, `gnss.csv`, `meta.json`, `quality.json`

## Rebuild

```bat
android\build-apk.bat testDebugUnitTest assembleDebug
```

Needs JDK 17 + Android SDK (`local.properties` is local-only, gitignored).
