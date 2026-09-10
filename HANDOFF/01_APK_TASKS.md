# APK tasks

Read `00_CONTEXT.md` first. Build with `./gradlew assembleStandardRelease`
(PowerShell: separate lines or `;`, never `&&`).

Priority order below is deliberate — 1 and 2 are what a judge sees in the first
ten seconds, and 3 is the one that could actively embarrass us.

---

## 1. LIVE SENSOR MODE — the highest-value thing in this document

**The idea:** a judge holds the phone, tilts it, walks with it, shakes it — and
watches the estimator respond in real time. No driving, no replay, no
explanation needed. They *feel* that it is real.

This is worth more than any other APK change because it converts a claim
("we estimate motion from IMU") into an experience the judge performs
themselves.

**Build a `LIVE SENSOR` screen** (its own destination, not buried):

- **Heading dial** — rotate the phone left, the dial rotates left. Driven by
  integrated gyro yaw, reset to zero on entry. This is the single most
  convincing element: the response is instant and unmistakably causal.
- **Motion state chip** — `STILL` / `WALKING` / `MOVING`, from the live
  accelerometer. When they stop, it must say STILL within ~1 s. When they walk,
  it must change. Threshold on `|a_linear|` with hysteresis so it does not
  flicker.
- **Step / displacement readout** — walking forward increases distance. Use
  step detection (there is already a `StepDetector` in the codebase per project
  history) rather than double-integrating accelerometer, which will drift
  visibly and undermine the demo.
- **Live event toasts** — this is what makes it feel intelligent:
  - Sharp vertical spike → **"Bump detected"**
  - Sustained high-frequency energy → **"High vibration — filtering"**
  - Sustained near-zero → **"Stationary — zero-velocity update applied"**
  - Large sudden orientation change → **"Mount moved — recalibrating"**
  Each maps to a real signal-processing branch that already exists. Show the
  numeric trigger value next to the toast so it is inspectable, not magic.
- **Raw sensor strip** — small live traces for accel and gyro. Proves the data
  is real and moving.

**Honesty constraint:** this screen shows *relative* motion from IMU only. Label
it clearly — `LIVE SENSOR — relative motion, no GNSS`. Do not draw it on a map
as if it were an absolute position fix.

---

## 2. DRIVE SCREEN UI — fix the layout

Current problems, verbatim from the team lead: *"why is the start button so
rectangular and big? It is taking up unnecessary space, and the pause button is
just on the top."*

- **Replace the big rectangular Start with a single circular FAB**, bottom
  centre, ~64 dp. One primary action. It becomes a square Stop when running —
  same position, same control, state change only. **Never two competing
  controls in different corners.**
- **Map fills the screen.** Everything else is an overlay on it.
- **Top:** one status pill, centred — `GNSS` ↔ `IDR` with the mode colour. That
  is the whole top chrome.
- **Bottom sheet, collapsed peek:** speed, mode, distance. Expanded: the
  diagnostics that currently clutter the main view.
- **Corner FABs:** recenter, and layers/basemap. Nothing else.
- Reference the Google Maps / Uber driver layout: map-first, minimal chrome,
  one primary action, generous tap targets (≥48 dp).

**Navigation:** `DRIVE | CONNECT | SETTINGS` is the right shape — keep three.
Add LIVE SENSOR either as a fourth or as a prominent entry from DRIVE. Fold
About into Settings (already done — verify it stayed).

**Rotation:** lock DRIVE to portrait, or handle configuration change without
losing session state. A rotation that resets the estimator mid-demo is fatal.

---

## 3. DEMO MODE MUST NOT SHOW FAKE MOVEMENT — do this before any demo

*"People click demo mode and see they are moving at 50 km/h while sitting
still."*

This is the most damaging bug in the app. A judge who spots it concludes the
whole thing is faked, and they would be right to.

- Demo Mode replays a recorded IO-VNBD drive. That is legitimate — **but it
  must be unmistakably labelled**, in the same visual layer as the speed
  readout, so no screenshot or glance can separate them:
  `REPLAY — recorded drive, real estimator`.
- The label must be **persistent and non-dismissible** while replay runs.
- **Never show replayed speed in the same style as live speed.** Different
  colour, or a permanent badge attached to the number itself.
- Add an explicit mode switch so it is impossible to be confused about which
  you are in: `LIVE` / `REPLAY` / `LIVE SENSOR`.

---

## 4. QR PAIRING — still broken

*"Even if I open the camera, it's not working properly."*

Diagnose in this order and report what you find:

1. **Is CAMERA permission requested at runtime, before the scanner launches?**
   Declaring it in the manifest is not enough. If denied, the flow must route
   to manual code entry, not fail silently.
2. **Is the ZXing `CaptureActivity` resolving?** It merges from
   `zxing-android-embedded`'s own manifest — confirm it is present in the
   merged manifest, and that `ScanContract`/`ScanOptions` is wired to it.
3. **Is the decoded payload parsed correctly?** The QR carries a URL with `s`
   (nonce), `lan`, and `relay`. Log the raw decoded string on failure.
4. **Does the POST actually reach anything?** Cleartext to a LAN IP needs
   `usesCleartextTraffic` (present). For the relay path it is HTTPS.
5. **Always provide manual entry as a first-class fallback** — a short code the
   user types. The camera path must never be the only way in.

**Both directions must work:** console shows a QR the phone scans, *and* phone
shows a QR/code the console accepts. Whichever device has a working camera
should be able to initiate.

**Test matrix:** camera granted; camera denied; phone on mobile data with laptop
on wifi; both on the same wifi; airplane mode.

---

## 5. MAP INSIDE THE APK

*"There is no map available in this."*

- MapLibre + OpenStreetMap is already wired and needs **no API key and no
  billing**. If no map is rendering, the likely causes are: (a) the bundled
  MBTiles bounds check now correctly rejects Coventry tiles outside the UK, and
  there is no live tile fallback in that path; or (b) MapLibre native init is
  failing and silently falling back to the Canvas grid.
- **Fix:** when outside the bundled pack's bounds and online, use live OSM
  tiles. When offline and outside bounds, show the Canvas grid *with a visible
  reason* — never a blank dark rectangle.
- Attribution `© OpenStreetMap contributors` must be rendered on the map. It is
  a licence requirement.
- Do **not** use Google/Apple tiles. It violates their ToS and the PS names OSM.

---

## 6. Smooth marker — a graded requirement

The PS explicitly grades *"a smooth, uninterrupted vehicle icon."* A 10 Hz fix
driving a marker directly teleports ten times a second.

Hoist position **out of Compose state**, animate between fixes with
`Animatable.animateTo`, and defer reads to the layout/draw phase
(`Modifier.offset { }`, `graphicsLayer { }`, `drawBehind { }`) so a position
update never triggers recomposition. Target a steady 60 fps.

---

## 7. Onboarding

First run should be a short flow, not a permission wall:
one screen explaining what the app does in plain language → permissions
requested **in context** with a reason → ends in a working demo in one tap.

---

## Acceptance

- [ ] LIVE SENSOR screen: heading dial tracks rotation, motion chip changes on
      walking, bump/vibration/stationary events fire with visible trigger values
- [ ] One circular primary control on DRIVE; no second competing button
- [ ] Replay mode carries a permanent label in the same layer as the speed
- [ ] QR pairing works with camera granted AND denied; manual entry works;
      both-direction pairing works
- [ ] A map renders in the app, online and offline, with attribution
- [ ] Marker holds 60 fps from 10 Hz fixes
- [ ] Rotation does not reset a running session
- [ ] `./gradlew testStandardDebugUnitTest` and `assembleStandardRelease` green
- [ ] `python tools/verify_claims.py` still exits 0
