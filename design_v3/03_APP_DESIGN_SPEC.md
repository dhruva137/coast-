# 03 — COAST Navigator: the phone app

**Design species:** consumer navigation app. Its job is to **hide** information.
Reference points: Google Maps, Uber driver, Rapido. Not a dashboard.

**A separate implementer document carries the exact drop-in code** (icon,
splash, theming, the two bug fixes, marker interpolation, sensor degradation).
This file decides *what it should be*; that one decides *how to build it*.

---

## A. The logo problem — root cause found

The complaint was *"the logo still doesn't fit, it's not working properly."*
It is not a design-taste problem. It is two concrete defects:

**1. `res/drawable/ic_launcher_fg.png` is not a PNG.** Its magic bytes are
`ff d8 ff e0` — it is a **1024×1024 JPEG renamed `.png`**. JPEG has no alpha
channel, so the adaptive-icon foreground layer is an **opaque square**. The
launcher then masks that square to a circle or squircle, which guillotines the
logo's corners and leaves it sitting on a visible box. That is exactly the
reported symptom.

**2. It lives in density-less `res/drawable/`**, so Android treats it as mdpi
baseline and upscales it roughly 4× on an xxxhdpi phone — hence blurry.

**3. There is no `<monochrome>` layer** in `mipmap-anydpi-v26/ic_launcher.xml`,
so Android 13+ themed icons fall back to a shrunken grey blob.

### The spec the designer must work to (verified)

| Spec | Total canvas | Where the art must sit |
|---|---|---|
| **Adaptive launcher icon** | 108 × 108 dp | 72 dp masked area · **66 dp safe zone** · 18 dp reserved each side · logo 48–66 dp |
| **Splash icon, no background** | 288 × 288 dp | art inside a **192 dp** circle |
| **Splash icon, with background** | 240 × 240 dp | art inside a **160 dp** circle |

**What to hand the developer:** a true transparent asset — ideally a
**VectorDrawable** for a simple mark, which sidesteps density entirely — with the
art inside the 66 dp safe zone, plus a single-colour `<monochrome>` version.
Never a JPEG. Never a full-bleed square.

---

## B. The launch sequence — the most valuable three seconds in the project

**There is currently no splash screen at all.** No `core-splashscreen` dependency
exists, and `themes.xml` still parents `android:Theme.Material.NoActionBar` — a
2014 framework theme, hardcoded dark, with no splash attributes. So this is not a
fix; it is a build.

**The design target — one continuous motion, no cut:**

```
0ms      Cold launch. System splash paints our background colour immediately.
         No white flash. (This is why the platform API matters — a hand-rolled
         splash Activity ADDS cold-start time and causes exactly that flash.)

0-600ms  The COAST mark draws itself — an animated vector. Keep it simple:
         a stroke that traces, or a mark that assembles. Not a bouncing logo.

600ms+   setKeepOnScreenCondition holds the splash only while the map surface
         and the model are genuinely initialising. Never hold it artificially.

exit     setOnExitAnimationListener takes over the splash view and hands off
         into Compose: the mark scales/fades as the map fades up UNDERNEATH it.
         The two overlap. That overlap is the entire "Uber feel" — the app does
         not start, it ARRIVES.
```

**Constraints:** animated vector max ~1000 ms on phones; delayed start ≤166 ms.
Android 13+ infers duration from the AVD; Android 12 needs
`windowSplashScreenAnimationDuration` set explicitly.

**The rule that matters most:** the splash must never be held longer than real
initialisation takes. A splash that lingers for effect is the single most common
way apps feel slow. If we boot in 300 ms, show it for 300 ms.

---

## C. Vehicle Check — turning a stability feature into a premium one

The user asked: *"you should also tell them if the sensors are working or not"*
and *"I don't want my phone sensors to be a limitation, and I don't want to
underuse them either."*

`sensor/DeviceProbe.kt` already does the hard part — a two-pass sensor inventory
plus a **measured 2500 ms burst count** of actual achieved sample rates. It is
genuinely good work and it is completely invisible. **Surface it.**

**Design it as a pre-flight check, like an aircraft checklist.** Runs on first
launch and on demand from settings. Takes ~3 seconds, animated, one row at a time.

```
  VEHICLE CHECK

  Accelerometer      ✓   197 Hz measured
  Gyroscope          ✓   198 Hz measured
  Magnetometer       ✓   captured · not used in estimate  ⓘ
  Barometer          ✓   floor-change detection
  GNSS               ✓   3.2 m accuracy
  Mount alignment    ✓   calibrated · pitch 12°  roll 3°

  Ready. Dead reckoning available.
```

Why this earns its place on four separate axes:

- **It is a genuine stability feature** — it detects a missing gyroscope before
  the user hits a dead end.
- **It builds trust** — the machine visibly checks itself. (Design principle 4:
  *show the machine working.*)
- **It answers a problem-statement question directly.** A judge asking "are you
  using all the sensors?" gets shown, not told.
- **The magnetometer row is our honest disclosure surface.** Tapping ⓘ explains:
  *"A compass inside a steel vehicle cabin, next to a magnetic phone mount, is not
  a compass. We read it and log it, but we don't fuse it — we'd rather have honest
  gyro drift the map can correct than confident magnetic error it can't."*
  See `01_PS_COMPLIANCE_AUDIT.md` §C — this is a known gap and this is where we
  turn it into a deliberate, visible decision.

**Motion:** rows resolve one at a time, ~150 ms apart, each with a small check
animation. It should feel like a system arming itself — that is the emotional
note, and it takes three seconds we are spending on initialisation anyway.

---

## D. Two live bugs found in the manifest and service

Both are real and both should be fixed. Details and code in the implementer doc.

**1. `uses-feature gyroscope required="true"`** in `AndroidManifest.xml`. This
makes Google Play **filter the app out of the store entirely** for every device
without a gyroscope — and it directly contradicts the graceful-degradation work
already sitting in `DeviceProbe`. Should be `required="false"`, with the runtime
verdict doing the gating and Vehicle Check explaining the consequence.

**2. Android 15 `dataSync` foreground-service timeout.** We target SDK 35, so
`dataSync` is capped at **6 hours per 24-hour period**. On expiry the system calls
`Service.onTimeout()` and throws `RemoteServiceException` if the service does not
`stopSelf()` within a few seconds. The recording service does not implement
`onTimeout`. The `location` type is **not** time-limited — so the fix is to attach
`dataSync` only while CSV logging is genuinely active, and keep `location` always.

---

## E. The smooth marker — a literal PS requirement

The problem statement asks for *"a smooth, uninterrupted vehicle icon showing
seamless navigation."* A 10 Hz position feeding a marker directly will visibly
teleport ten times a second. This is currently our weakest visual and it is
explicitly graded.

**The fix:** interpolate between fixes and drive the marker at 60 fps.
Concretely — hoist the high-frequency position **out of Compose state entirely**,
animate between fixes with `Animatable.animateTo`, and defer reads to the
layout/draw phase (`Modifier.offset { }`, `graphicsLayer { }`, `drawBehind { }`)
so a position update never triggers recomposition.

**This is the highest perceived-quality-per-line-of-code change in the app.**
Smooth motion is most of what separates "real product" from "student demo" in the
first ten seconds, and it satisfies a graded requirement at the same time.

---

## F. Light / dark / system

Tri-state (system · light · dark), user-selectable, persisted. Material 3 with
dynamic colour guarded on API 31+, over a custom scheme built on `#00E0A4`.

**The gotcha that will bite:** MapLibre's `map.setStyle()` **tears down and
re-adds all layers and sources**. The track polyline layer must be re-registered
inside the style-loaded callback, or the user's path silently vanishes the moment
they switch theme. This is the kind of bug that only appears in front of a judge.

**Design note:** dark is the primary theme and the one we demo. Light mode must
exist and be correct, but do not spend equal effort on it — a navigation app used
in a vehicle is a dark-mode product.

---

## G. Settings and accounts

The user asked for login, account configuration, and "Sign in with Google."

**Recommendation: do not build real authentication for Friday.** Reasons:

1. It adds a wall between a judge and the demo. Design principle: one tap from
   cold launch to a working demo, no login, no permission wall.
2. Google Sign-In needs OAuth client setup, a signing-certificate fingerprint,
   and a consent screen — an entire failure surface for zero score.
3. **It contradicts our F8 story.** "No account required — we hold no identity, so
   there is nothing to leak" is a genuine privacy strength. Adding accounts
   weakens it.

**What to build instead:** a local profile — a name, vehicle type, and preferences
stored on-device, with **"Continue as guest"** as the prominent default. It looks
like an account system, requires nothing, and preserves the privacy claim.

If a judge asks about accounts: *"Deliberately none. We don't want an identity we
don't need — there's nothing to breach. Profiles are local. If a fleet operator
deploys this, their operator console handles identity, not the driver's phone."*

That answer scores better than a working Google Sign-In would.

---

## H. What to delete from the Drive screen

Design principle 1: one thing per screen. Drive answers *"where am I?"*

**Keep visible:** the map · the vehicle marker · the mode pill (GNSS ↔ IDR) ·
speed · Start/Stop · recenter FAB.

**Move into the bottom sheet:** diagnostics, accuracy readouts, loop closure,
sensor detail, ZUPT state, last-location card.

**Move into settings/demo mode:** blackout toggle, ghost puck, ZUPT tabletop,
replay controls.

**Delete outright:** anything a moving driver would not read in one second and
that does not serve the ninety-second judge demo.

The bottom sheet already exists (`BottomSheetScaffold` with a drag handle). Use
it properly: collapsed peek shows speed, mode, and the primary action — nothing
else.

---

## I. Priority order

If time runs out, this is the cut line. Everything above the line changes the
judge's impression; everything below is polish.

1. **Fix the icon** — re-export as transparent vector/PNG inside the 66 dp safe
   zone, add the `<monochrome>` layer. *(Fixes the visible complaint immediately.)*
2. **Build the splash** — `core-splashscreen`, new theme, continuous handoff.
3. **Fix the gyroscope `uses-feature`** — one line, prevents a store-filtering bug.
4. **Marker interpolation** — 60 fps. A graded requirement.
5. **Vehicle Check screen** — surfaces work already done, answers the sensor question.
6. **Material 3 theming + the MapLibre `setStyle` fix.**
7. Drive-screen subtraction.
8. `onTimeout()` for the recording service.
9. Local profile / guest.
   — *cut line for Friday* —
10. Light mode refinement, animation polish, settings breadth.

---

## J. On APK size (68 MB)

R8 and `shrinkResources` are already on; ABIs are already filtered to arm64-v8a +
armeabi-v7a. The remaining bulk is **ONNX Runtime and MapLibre native `.so`
files, which R8 does not touch.**

The real levers: ship an **AAB** (Play delivers one ABI, roughly halving it), or
produce **per-ABI APK splits** for sideloading. For judges downloading from a
website, an **arm64-only release APK** is the right artifact — it covers
essentially every modern phone and roughly halves the download. A debug build
carries no shrinking at all, so ship release.
