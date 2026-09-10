# Phase 2 — Fleet: real maps, real devices, real sessions

**The complaint:** *"I just see Judge 1 and Judge 2 here, and it is obviously
fake. This should actually work in the sense that it is actually showing the
location properly."*

That reaction is correct and it is the most damaging one in the whole console.
Two separate causes:

1. **There is no basemap.** Tracks are drawn on a bare grid. Without roads
   underneath, a line is just a squiggle — and our entire thesis is *"the road
   network is the algorithm."* Drawing tracks with no roads misrepresents the
   product.
2. **Placeholder devices look like production data.** Anything not live must be
   unmistakably marked, or removed.

---

## 2.1 — Put a real basemap under the tracks

### The primary answer: serve the MBTiles you already have

`android/app/src/main/assets/maps/demo_neighbourhood.mbtiles` is a raster tile
pyramid for the Coventry UK demo area, zooms 13–18, ~1.5 MB. **It is already in
the repo, already matches the demo drive, and needs no network, no key and no
account.**

Add a tile route to the console:

```
GET /tiles/{z}/{x}/{y}.png   →  read from the MBTiles SQLite file
```

Notes that will bite you if you miss them:
- MBTiles stores rows in **TMS** order — `y` is flipped relative to XYZ/slippy.
  Convert: `tms_y = (1 << z) - 1 - y`. Getting this wrong yields a
  vertically-mirrored map, which looks almost right and is completely wrong.
- Serve with a long `Cache-Control` (tiles are immutable) and the correct
  content type from the `format` metadata.
- Return **204** for a missing tile, not 500.
- Read the `bounds` and `minzoom`/`maxzoom` from the `metadata` table and expose
  them at `/api/tiles/meta` so the client can clamp the view instead of
  requesting tiles that do not exist.

**This is the demo path.** It works with the venue wifi dead, which is the only
condition that matters on the day.

### Rendering

Two options; pick by measuring, not by preference:

- **Canvas tile layer** — keep the existing canvas, add a tile-drawing layer
  underneath. No dependency, full control, works with the existing track code.
  Roughly 150 lines: compute visible tile range from centre+zoom, fetch, cache,
  draw, then draw tracks in the same projection.
- **MapLibre GL JS, vendored locally** — more capable, but it is a build-free
  console today and MapLibre is a large file to vendor. Only take this if the
  canvas layer proves limiting.

**Recommendation: canvas tile layer.** The console has no build step and the
track rendering already works in a canvas projection. Do not add a bundler for
this.

### Online basemaps — treat as a bonus, and VERIFY before relying

Research on current free-tier terms did **not complete**, so the following are
leads, not facts. **Verify each against the provider's own current terms and
record what you find in `docs/BASEMAP_OPTIONS.md` before wiring anything in.**

| Candidate | What to verify |
|---|---|
| OpenStreetMap standard tiles | Their tile usage policy — bulk/automated use is restricted. A demo may be acceptable; confirm and honour attribution. |
| Carto basemaps (`dark_all`, `positron`) | Whether keyless access is still offered in 2026 and under what limits |
| **Protomaps / PMTiles** | Single-file, range-request tiles that work from local disk or static hosting. **Most promising for offline** — likely a better long-term answer than MBTiles |
| Esri ArcGIS Location Platform | The user mentioned Esri's free tier. Confirm whether a key and/or card is required |
| MapmyIndia / Mappls | India coverage and Indian place names; confirm free-tier signup burden |
| **ISRO Bhuvan** | Whether free WMS/tile services exist and are usable in a web map. **If real and free, this is a notable flavour for an ISRO-adjacent audience** — but do not claim it until verified |

**Rules:** attribution rendered on the map, always. No API key committed to the
repo. Any online basemap must degrade to the local MBTiles when the network is
gone — never to a blank canvas.

## 2.2 — Kill the fake devices

**Delete all seeded demo devices from the default path.** The empty state does
the work instead.

- **Empty fleet = the pairing QR at full size**, centred, with *"Scan this to put
  your phone on the map."* The empty state is the call to action. This is
  stronger than fake data and it is honest.
- If a demo device is genuinely needed (rehearsal, a screenshot), it must:
  - be behind an explicit **Demo device** button, never automatic;
  - carry a permanent badge **inside the map layer** — `SIMULATED` — in the same
    visual layer as the track, so no crop can separate them;
  - use a visibly different style (dashed, desaturated) from live devices;
  - be listed as `Demo-1`, never `Judge-1`. A name that implies a real person
    paired is the specific thing that read as fake.

## 2.3 — Sessions

*"There should be an option for multiple sessions."*

A **session** is one recording window across the whole console: devices that
paired, their tracks, mode transitions, and any training runs started during it.

- `POST /api/session/new` — start; `POST /api/session/end` — close.
- `GET /api/sessions` — list with start/end, device count, distance, duration.
- `GET /api/session/<id>` — full replay payload.
- A **session switcher** in the header. Switching loads that session read-only
  with a clear `ARCHIVED` marker; the live session is always visually distinct.
- **Replay controls** on an archived session: play, pause, scrub, speed. Reuse
  the transport component from Phase 3 — do not write a second one.
- Persist to `web/sessions/<id>.json` **only if the operator opts in**; in-memory
  by default. Position history is exactly the data our privacy story says we do
  not hoard.
- **Export** a session as JSON; **delete** a session and mean it.

## 2.4 — Device registry

*"Register a device, and we can get this device out."*

- **Register**: pairing already mints a device. Add an operator-visible list with
  a rename control, so `Judge-1` can become `Ravi's phone` or `Truck 7`.
- **Deregister**: an explicit control that unpairs and deletes. Confirm first —
  it destroys data.
- **Device detail view**: track, mode timeline, distance, GNSS/IDR share, max
  outage, first/last seen, and the *"what we know about you"* panel.
- **Status is honest**: `live` (posting now) · `idle` (paired, silent >12 s) ·
  `offline` (silent >60 s). Never delete a device from the map because it went
  quiet — grey it and show "last seen". A disappearing vehicle reads as a bug.
- **Cap devices** and points per device (Phase 6), and say what the cap is.

## 2.5 — Make the fleet view carry the use case

This screen is the logistics/security story, so let it tell it:

- **Track segments coloured by mode** — GNSS blue, IDR teal. *Where the line
  changes colour, GPS was gone.* This is the most legible thing on the screen and
  needs no legend for a non-technical judge.
- **Mode-transition timeline** under the map: `09:41 · Ravi's phone · GNSS → IDR`.
  This turns a map into a narrative.
- **Outage summary per device**: how many outages, longest, total distance
  covered without GNSS. That last number *is* the product.
- **Follow mode**: keep a selected device centred.
- Scale bar, zoom, pan, and a **fit-all** control.

## 2.6 — Live phone location must actually be right

The user's underlying worry is that positions are not real. Prove it:

- Show **accuracy** as a translucent circle around the live marker, from the
  reported `acc_m`. It visibly shrinks outdoors and grows indoors — a viewer can
  see it responding to reality.
- Show **last-fix age** in seconds. If it stops updating, the number climbs and
  the marker greys. Never a frozen dot pretending to be live.
- Show the **source** on the device row: `browser GPS` vs `COAST app`. The
  browser pairing page reports GPS; only the app does dead reckoning. Conflating
  them would be the single most dishonest thing in this console.

---

## Ownership

| Item | Files |
|---|---|
| 2.1 tiles | `web/coast_console.py` (`/tiles`), `web/static/map.js` |
| 2.2–2.5 fleet UI | `web/static/fleet.js`, `web/static/fleet.css` |
| 2.3–2.4 sessions/devices | `web/pairing.py`, `web/sessions.py` |
| Tests | `web/test_console_routes.py`, `web/test_tiles.py` |

## Acceptance

- [ ] `/tiles/{z}/{x}/{y}.png` serves from MBTiles; **TMS y-flip verified against a known landmark**
- [ ] Missing tile → 204; `/api/tiles/meta` exposes bounds and zoom range
- [ ] Tracks render on real roads; verified offline with the network off
- [ ] No seeded devices on the default path; empty state is the QR
- [ ] Any demo device carries a `SIMULATED` badge inside the map layer
- [ ] Sessions: new / end / list / switch / replay / export / delete
- [ ] Devices: rename, deregister with confirmation, detail view
- [ ] Idle and offline devices grey out with "last seen" — never vanish
- [ ] Mode-coloured segments + transition timeline
- [ ] Accuracy circle and fix age shown; source labelled app vs browser GPS
- [ ] `docs/BASEMAP_OPTIONS.md` records what was actually verified
- [ ] `python web/test_console_routes.py` green
