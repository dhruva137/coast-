# B6 decision — offline-only `standard` (drop INTERNET)

**Status: NOT TAKEN** (2026-09-09, branch `demo`)

## What B6 would have been

Per `07_LOCALHOST_PHONE_TRACKER_SPEC.md` / PPT F8 “stronger P1”:

- Remove `INTERNET` (and tile-fetch rationale) from the default **`standard`** flavor.
- Keep remote basemap tiles only in **`tracker`** / an online flavor.
- Then claim literally “no INTERNET permission” on the shippable APK.

## Evidence checked

| Source | Finding |
|--------|---------|
| `android/app/src/main/AndroidManifest.xml` | `INTERNET` + `ACCESS_NETWORK_STATE` declared on **main** (shared by both flavors) for MapLibre tile fetch/cache. |
| `android/app/src/tracker/AndroidManifest.xml` | Does **not** own INTERNET; only enables cleartext for LAN ingest. |
| `MapLibreDriveMap.kt` | Live style still points at remote raster tiles: `https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png` (`OSM_STYLE_JSON`). Used whenever bundled mbtiles path is null. |
| Bundled pack | `assets/maps/demo_neighbourhood.mbtiles` exists (Coventry IO-VNBD **S-S1** strip). |
| `assets/maps/README.md` | Bbox ≈ 52.398–52.4115 N, −1.601–−1.587 E; zooms 13–18. **Explicit:** demos outside this bbox show empty/dark tiles until live/cached tiles are available. |
| `MapBackend.kt` | Preference is bundled mbtiles → cached live → Canvas. When mbtiles are present, MapLibre is chosen even offline — but the style then stays on **`mbtiles://` only** (no hybrid remote fill outside the pack). |

## Why not taken

1. **Friday demo must not go blank.** Outside the Coventry mbtiles bbox (pan/zoom out, wrong drive, live GNSS elsewhere, venue dry-run off the strip) the basemap is already empty dark tiles when the pack is selected. Today, cold installs / missing copy / non-mbtiles path can still use Carto over INTERNET or fall back cleanly. Stripping INTERNET from `standard` removes that safety net without adding a hybrid “mbtiles inside bbox, remote outside” path.
2. **B6 is not a permission-only change.** Safe implementation needs flavor-split manifests, ensuring `standard` never loads `OSM_STYLE_JSON`, and re-testing blackout + airplane + outside-bbox. That is more risk than upside before the pitch.
3. **Blackout replay is covered by mbtiles only if the pack loads.** Asset-copy failure → remote style today; without INTERNET that path dies and the UI falls to Canvas (“Offline, no tiles cached”) — a worse-looking Friday failure mode.
4. **F8 stays honest without B6.** Checkable claim remains: **no user data leaves the device** (no uploads/analytics/account); optional public tile GETs only; basemap-off = zero network. Do **not** claim “no INTERNET permission” on `standard` until B6 is actually shipped.

## What we keep saying (F8)

- PPT / Settings: **“No data leaves the device”** (+ basemap-off = zero network).
- Manifest comment remains accurate: INTERNET exists for public basemap tiles only.
- Phone-tracker LAN uploader stays **`tracker`-only** and opt-in.

## Revisit later (post-demo)

Only after: hybrid style or guaranteed Canvas messaging outside bbox, mbtiles copy smoke-tested on install, and INTERNET moved exclusively to `tracker`/online with CI covering both flavors.
