# Slide 8 — Privacy & security *(F8)*

**Status:** final text for paste into official SIH template. **Not** a finished `.pptx`.

## Conclusion headline (largest type)

**No user data leaves the device — navigation runs with the radio off.**

## Dominant visual (one)

Phone screenshot: Drive in airplane mode / basemap-off (or the privacy claim card). One frame only.

## Support (≤18 pt body)

- No uploads, no analytics, no crash reporting, no account required
- **Basemap-off = no network traffic** — only optional outbound traffic is public map-tile GETs (no API key, no account)
- Optional phone-tracker demo is **LAN-only and opt-in** (`tracker` flavor)

## Speaker (~15 s)

> “Privacy is a property, not a promise. No user data leaves the device. Basemap off — no network traffic. With the basemap on, the only traffic is public map tiles. Navigation itself runs with the radio off.”

## Honesty / F8 guard

- Main manifest still declares **INTERNET** for MapLibre tiles (B6 offline-only drop **not** done).
- Claim exactly: **no user data leaves the device; basemap-off means no network traffic**.
- Do **not** claim there is no INTERNET permission in the manifest.
