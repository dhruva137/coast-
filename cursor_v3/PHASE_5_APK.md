# Phase 5 — The Android app

**Read `design_v3/03_APP_DESIGN_SPEC.md` first.** It carries the root-cause
analysis for the icon, the exact adaptive-icon geometry, and the priority order.

The app is a **consumer navigation app**. Its job is to *hide* information —
opposite to the console, which reveals it. Reference: Google Maps, Uber driver.
Do not port console density onto the phone.

**Already landed** (verify, do not redo): the launcher icon is now a
VectorDrawable with a monochrome layer (it was a JPEG renamed `.png`, hence the
cropping); a platform splash screen with an animated mark and an exit handoff
into Compose; `uses-feature gyroscope required="false"`; `onTimeout()` on the
recording service for Android 15's 6-hour `dataSync` cap.

**Ground truth — never touch:** `assets/demo/iovnbd_demo.csv`,
`assets/maps/demo_neighbourhood.mbtiles`.

---

## 5.1 — Pairing with the console

The console mints a QR carrying a one-time token plus **both** a LAN and a relay
endpoint (`web/pairing.py`). The app must scan it and stream position.

- **ML Kit barcode scanning, BUNDLED model** (`+2.4 MB`). **Not** the unbundled
  variant — it downloads via Play Services on first use and fails with no wifi,
  which is exactly the venue condition. Fallback: `journeyapps/zxing-android-embedded`.
- **Race both endpoints** with a ~1.5 s timeout, pin whichever answers, re-race
  after three consecutive failures. Guest wifi commonly runs AP isolation, which
  kills phone→laptop with a silent timeout you cannot detect in advance.
- **Manual code entry** as a guaranteed fallback — a short code the console also
  displays. Never leave pairing dependent on a camera working.
- **Consent before scanning**, in plain words: *"Pairing shares your live
  position with this console until you unpair. Nothing else is sent. No account,
  no device ID."*
- **A persistent, unmissable indicator while paired** — same visual weight as a
  recording indicator — and **one-tap unpair reachable from Drive**, not buried.
- Post `{token, lat, lon, mode, speed_mps, acc_m}` at ~1 Hz. **Never send a
  device identifier, IMEI, or advertising ID.** The console's privacy panel
  claims we hold none; that must be true by construction.
- Tracking stays **off by default** and lives only in the `tracker` flavour. The
  `standard` flavour must continue to contain no uploader at all.

## 5.2 — Vehicle Check

`sensor/DeviceProbe.kt` already does a two-pass sensor inventory plus a measured
2500 ms burst count of achieved rates. It is good work and completely invisible.
Surface it as a **pre-flight check**, styled like an aircraft checklist, on first
launch and on demand.

```
  VEHICLE CHECK
  Accelerometer   ✓  197 Hz measured
  Gyroscope       ✓  198 Hz measured
  Magnetometer    ✓  captured · not yet fused  ⓘ
  Barometer       ✓  floor-change detection
  GNSS            ✓  3.2 m accuracy
  Mount alignment ✓  calibrated · pitch 12° roll 3°
  Ready. Dead reckoning available.
```

Rows resolve one at a time, ~150 ms apart. It should feel like a system arming
itself — and it uses time cold start needs anyway.

**The magnetometer row is our honest disclosure surface.** Tapping ⓘ explains
that we read and log it but do not yet fuse it, and that we *measured* why:
compass heading carries ~16.6° error even after a perfect offset, versus ~29.7°
for a free-running gyro over 60 s. **If Phase 4.6 lands, update this row** — the
compass then becomes a fused input and the honest text changes to say so.

**No gyroscope present:** a designed explanatory screen, not a crash. Say what is
degraded and what still works.

## 5.3 — The smooth marker (a graded requirement)

The problem statement asks for *"a smooth, uninterrupted vehicle icon."* A 10 Hz
fix driving a marker directly visibly teleports ten times a second.

Hoist position **out of Compose state**, animate between fixes with
`Animatable.animateTo`, and defer reads to layout/draw (`Modifier.offset { }`,
`graphicsLayer { }`, `drawBehind { }`) so a position update never triggers
recomposition. Target a steady 60 fps.

This is the highest perceived-quality-per-line change in the app.

## 5.4 — Theming

Tri-state light / dark / system, persisted. Material 3 over a custom scheme built
on `#00D4AA`; dynamic colour guarded on API 31+.

**The gotcha that will bite:** MapLibre's `setStyle()` tears down and re-adds all
layers and sources. The track polyline must be re-registered inside the
style-loaded callback (`ui/MapLibreDriveMap.kt`, around the track layer) or the
user's path silently vanishes the moment they switch theme.

Dark is the primary theme and the one demoed. Light must exist and be correct;
do not spend equal effort on it.

## 5.5 — Sessions and history

The console gains multi-session support (Phase 2); the app should match.

- A session list: start/end, distance, GNSS vs IDR share, max outage, a track
  thumbnail.
- Export one session as JSON/CSV to share — and make **local-only** explicit.
- Replay a stored session through the map.
- **Delete a session, and mean it.** Same posture as the console's delete.

## 5.6 — Drive screen subtraction

One question per screen: *where am I?*

**Keep visible:** map · vehicle marker · mode pill (GNSS ↔ IDR) · speed ·
Start/Stop · recenter.
**Move to the bottom sheet:** diagnostics, accuracy, loop closure, sensor detail,
ZUPT state.
**Move to settings/demo:** blackout toggle, ghost puck, ZUPT tabletop.

The `BottomSheetScaffold` already exists — collapsed peek shows speed, mode and
the primary action, nothing else.

## 5.7 — Demo mode front door

One tap from cold launch to the blackout replay. No login, no permission wall,
works in airplane mode.

- Plain-language line, always visible: *"GPS is off. Position is coming from the
  phone's motion sensors + the road map."*
- The GNSS→IDR handover must be **visually loud** — it is the beat the whole
  demo rests on.
- Permanent `REPLAY — real dataset, real estimator` label **inside the map
  layer** so no screenshot can crop it off.
- **Also demo the reverse.** The PS says "and vice-versa"; most teams only ever
  show the drop, never the reacquisition.

## 5.8 — Optional: emit filter internals

If Phase 3.7 (live engine view) is wanted, the app must publish particle
summary, `n_eff`, and edge posterior alongside position. Gate it behind the
tracker flavour and the same opt-in.

**If not implemented, say so** — the console then shows a recorded trace with a
REPLAY badge. Do not synthesise internals.

---

## Acceptance

- [ ] QR pairing works; endpoint racing verified with the laptop unreachable
- [ ] Manual code entry works with the camera denied
- [ ] Consent shown before scanning; persistent indicator; one-tap unpair
- [ ] No device identifier transmitted — verified by reading the payload
- [ ] `standard` flavour still contains no uploader
- [ ] Vehicle Check ships; magnetometer row carries the honest ⓘ
- [ ] Missing gyroscope produces a designed screen, not a crash
- [ ] Marker holds 60 fps from 10 Hz fixes
- [ ] Theme switch does not lose the track polyline
- [ ] Sessions list, replay, export, delete
- [ ] Demo mode: cold launch → running in one tap, airplane mode
- [ ] Both handover directions demonstrated
- [ ] `./gradlew testStandardDebugUnitTest` and `assembleStandardRelease` green
