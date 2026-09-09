# Slide 8 — Privacy & security *(F8)*

**Status:** final text for paste into official SIH template. **Not** a finished `.pptx`.

## On-slide

- **No user data leaves the device** — no uploads, no analytics, no crash reporting, no account
- Navigation runs **with the radio off**
- **Basemap-off = zero network** — only optional outbound traffic is public map-tile GETs (no API key, no account)
- Optional phone-tracker demo is **LAN-only and opt-in** (`tracker` flavor)
- Login is optional — not required to navigate

## Speaker (~15 s)

> “Privacy is a property, not a promise. No user data leaves the device. Basemap off — zero network calls. With the basemap on, the only traffic is public map tiles. Navigation itself runs with the radio off.”

## Honesty / F8 guard

- Main manifest still declares **INTERNET** for MapLibre tiles (B6 offline-only drop **not** done).
- Claim exactly: **no user data leaves the device; basemap-off = zero network**.
- Do **not** claim “no INTERNET permission”.
