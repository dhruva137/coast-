# 04 — App UI Spec (Uber-black, full-screen)

**Goal:** the app must read as a real consumer navigator — full-screen dark map,
a dot that keeps moving, a clean HUD — not a lab tool with a map in a box. Owner:
Cursor. Files owned here: `ui/**`, `ui/theme/**`, `data/Prefs.kt`, `res/**`.
**Do not** touch `nav/**`, `sensor/**`, `record/**`, `IdrBus.kt` except to
*read* state (those belong to file 05's owner).

---

## P0-1. Kill the box → full-screen map

**File:** `android/app/src/main/java/in/sih26168/idr/ui/DriveScreen.kt`

- Line ~170: the map panel is `Modifier.height(300.dp)`. **Replace with
  `Modifier.fillMaxSize()`** and make `DriveMapPanel` the *bottom* layer of a
  `Box(Modifier.fillMaxSize())`.
- Everything else (HUD, buttons, bottom sheet) becomes an **overlay** drawn on
  top of the map with `Modifier.align(...)`, not stacked in a `Column` that
  steals height from the map.
- Status bar: draw the map edge-to-edge behind the system bars
  (`enableEdgeToEdge()` in `MainActivity`, transparent system bar scrims).

**Acceptance:** the map fills 100% of the screen on a phone; HUD floats over it.

## P0-2. Uber-black theme

**Files:** `ui/theme/Color.kt`, `ui/theme/Theme.kt`, and the MapLibre style.

Design tokens (dark, restrained — one accent only):

| Token | Value | Use |
|---|---|---|
| `surface` | `#0B0E11` | app background |
| `surfaceElevated` | `#161A1F` | sheets, cards |
| `onSurface` | `#FFFFFF` | primary text |
| `onSurfaceMuted` | `#8A929B` | secondary text |
| `accent` | `#00E0A4` | our track, active states, CTA |
| `gnss` | `#4FC3F7` (calm blue) | GNSS-fix track segment |
| `idr` | `#00E0A4` (teal) | dead-reckoned track segment |
| `ghost` | `#FF5252` (red) | naive/ghost puck (file 05) |
| `warn` | `#FFB300` (amber) | IDR-mode HUD pill |

- **MapLibre basemap must be dark.** Use a dark raster/vector style (OSM dark or
  a minimal dark style JSON bundled in assets). No bright default OSM tiles — it
  must look like a night-mode navigator.
- Remove all leftover "blue everywhere" — blue is reserved strictly for the
  GNSS-fix track segment.

**Acceptance:** screenshot reads as a dark Uber/ride map at a glance.

## P0-3. The HUD overlay

A floating top pill + a bottom sheet, over the map:

- **Top-center pill** — the navigation-state indicator (the demo's emotional
  core):
  - GNSS good → green pill: "GPS" + satellite count.
  - GNSS lost → amber pill, animated: **"IDR MODE — AI speed + road lock"**.
  - This pill flipping is the moment the whole pitch lands. Drive it off
    `IdrBus.hud` / `IdrBus.location`.
- **Bottom sheet** (collapsed by default, drag up for detail):
  - Collapsed: current speed (km/h), mode, distance since last fix.
  - Expanded (the "System Health / diagnostic drawer" judges love):
    inference latency (ms), active mode, IMU polling rate (Hz), fusion rate
    (10 Hz), vehicle profile. Pull these from existing `DiagnosticsPanel.kt`
    state — reuse, restyle, don't rebuild.
- **The vehicle puck**: a directional chevron that *slides* toward the estimate
  (the existing `VehicleSmoother` already does frame-rate-independent easing and
  snaps on large jumps — keep it).
- **DO NOT draw an uncertainty radius.** The confidence signal is broken
  (−0.23). If a radius control exists, hide it behind a debug flag, off by
  default.

## P0-4. Offline map persistence (the tunnel guarantee)

**Files:** `ui/MapLibreDriveMap.kt`, `res/assets/`, `ui/MapBackend.kt`.

- Bundle a **small raster `.mbtiles`** of the demo neighbourhood into
  `app/src/main/assets/` and load it via the `mbtiles://` source (see
  `02_RESEARCH_FINDINGS.md` §B). This guarantees the basemap is present **with
  wifi off** — the tunnel demo cannot depend on venue wifi.
- Extend `chooseMapBackend(...)` preference order: **bundled mbtiles → cached
  live tiles → honest Canvas grid fallback.** Keep the existing rule that
  RELATIVE mode / no-anchor always falls back to the Canvas with a reason
  (the `MapBackendTest` tests must still pass).
- Keep the existing "map survives losing the radio once tiles cached" behaviour.

**Acceptance:** toggle airplane mode mid-session → map stays, dot keeps moving.

---

## P1-1. Settings screen

New `ui/SettingsScreen.kt`, state persisted in `data/Prefs.kt`:

- Vehicle profile picker (reads `VehicleKind`; use `IdrBus.setVehicle`).
- Map: dark/light, basemap on/off (feeds the privacy fallback), units.
- Demo: "Replay mode" toggle, "Show ghost car" toggle (file 05), "Simulate GNSS
  blackout" shortcut.
- Privacy: a read-only line stating "No internet permission · all on-device" —
  make the F8 claim visible in-product.
- Phone-tracker (file 07): opt-in toggle + laptop LAN address field, off by default.

## P1-2. Sessions / history

New `ui/SessionsScreen.kt` backed by the existing `record/SessionStore.kt`:

- List past sessions: date, duration, distance, vehicle, max drift-since-fix.
- Tap → a static map of that session's track (GNSS blue / IDR teal segments).
- "Last location" card on the home screen.

## P1-3. Login / sign-out stub

New `ui/AuthScreen.kt` — **stub only, no real auth, no network**:

- "Continue as guest" (default, one tap into the app).
- Email field + "Sign in" that just stores a display name in `Prefs` locally.
- Sign-out clears the local name. Make clear in code comments this is a
  placeholder; it must never add a network call (would break F8).

---

## Navigation structure

Bottom nav or a drawer with: **Drive** (the map, default) · **Sessions** ·
**Settings** · **About**. Keep `About/Help/Onboarding` screens that already
exist; restyle to the dark theme.

## Hard constraints (do not break)

- No new INTERNET-requiring dependency. The manifest must stay network-free for
  the core app (the phone-tracker in file 07 is a separate opt-in build flavor /
  guarded by a runtime toggle — see that file).
- All existing unit tests (`MapBackendTest`, `SimpleInsTest`, etc.) must still
  pass. If a change breaks a test, the change is wrong, not the test.
- `in.sih26168.idr` package, arm64 + armv7 ABIs, minify on for release.
