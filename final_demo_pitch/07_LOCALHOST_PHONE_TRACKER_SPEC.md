# 07 — Localhost Phone-Tracker Dashboard

**Goal (P1):** during a demo, the phone streams its estimated position to the
presenter's laptop over the **local network**, and a localhost web page shows the
phone's live dot — so the judge sees "we're tracking the actual phone, here, on
this laptop," alongside the laptop's own replay.

**Critical constraint:** this must **not** break the F8 privacy claim that **no
user data ever leaves the device**. The standard app already declares INTERNET
(for OSM tiles) but **uploads nothing**; the tracker adds a LAN uploader, so it
must be **isolated** and **opt-in**. Owner: Cursor. Files: a new Android product
**flavor**, a small laptop-side server, `web/**` for the page.

> **Stronger-claim option (P1):** make the `standard` flavor render from bundled
> + cached tiles only (no remote tile source), which lets you **drop INTERNET
> from `standard` entirely** and restore the maximal, literally-true "no INTERNET
> permission" claim. Live-online tiles then live in this tracker/online flavor.
> Do this only if P0 is solid; it limits `standard`'s live map to cached areas.

---

## P1-1. Keep the privacy claim intact: a separate flavor

- Add an Android product flavor, e.g. `tracker`, that:
  - adds `<uses-permission android:name="android.permission.INTERNET"/>` in the
    **flavor's** manifest only;
  - includes a `LanUploader` class.
- The default `standard` flavor **uploads nothing** (its only traffic is OSM
  tile GETs). The PPT's F8 slide refers to `standard`. On stage: "the app we'd
  ship never uploads your data; this demo build adds a LAN-only uploader so you
  can watch the phone from this laptop." (Unless you take the P1 offline-only
  option above, in which case `standard` truly has no INTERNET permission.)
- Build the demo from the `tracker` flavor; keep `standard` as the real artifact.

## P1-2. The uploader (phone side)

- `LanUploader` — when the demo toggle (file 04 Settings) is ON and a laptop LAN
  address is set, POST the current estimate every ~500 ms to
  `http://<laptop-ip>:8787/ingest`:
  ```json
  { "t": <epoch_ms>, "lat": .., "lon": .., "east": .., "north": ..,
    "mode": "GNSS|IDR", "speed_mps": .., "heading_deg": .., "session": "<id>" }
  ```
- Fire-and-forget, short timeout, failures are silent (never crash the app, never
  block the estimator thread). No data leaves the LAN; address is
  presenter-entered, never hard-coded to a cloud host.
- Off by default; a visible indicator when active ("Streaming to laptop · LAN").

## P1-3. The laptop server + page

- Tiny local server (Python, stdlib `http.server` or Flask — no heavyweight
  deps). Binds `0.0.0.0:8787` on the LAN, serves:
  - `POST /ingest` — stores the latest frame(s) in memory (+ optional JSONL log).
  - `GET /` — a dark MapLibre+OSM page that polls `/feed` and renders the phone's
    live dot + trail (GNSS blue / IDR teal, same palette as the app).
  - `GET /feed` — latest frames as JSON.
- Reuse the existing `web/` stack and the app's color tokens so it looks like one
  product. Show the same HUD pill (GPS vs IDR) as the phone.
- One command to start: `python -m web.tracker_server` (document the laptop IP
  discovery: `ipconfig` on Windows).

## Demo value

Split the laptop screen: left = the `lab.demo` replay + figures (file 06), right
= the live phone-tracker page. "On the left, our estimator scored on real car
data. On the right, the same estimator running on this phone, right now,
streaming here over wifi — and it keeps tracking when I put it in airplane
mode." (The phone's *estimate* keeps moving even when the uplink drops, because
the estimation is on-device; the uplink is only for you to watch it.)

## Honesty / constraints

- Be precise about what the LAN stream is: a **viewer**, not the navigation. The
  navigation runs on-device; the laptop is just watching. Do not imply the
  laptop is doing the positioning.
- LAN-only, no cloud, no external host. No credentials, no accounts.
- If wifi at the venue is locked down (no phone↔laptop LAN), this P1 feature may
  be undemoable — that's why it's P1, not P0. The blackout demo (file 05) and
  live training (file 06) are the P0 that must work regardless.
