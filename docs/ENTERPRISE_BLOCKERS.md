# Enterprise sale — honest blockers (SIH26168)

Do **not** soft-pedal these in a commercial deck. They are real.

`npm run gate:prototype` may emit `RESEARCH_PROTOTYPE_PASS`; that status is not
deployment readiness. Enterprise close is governed by
`npm run gate:deployment`, which currently emits `DEPLOYMENT_READY_FAIL`.

## Must-fix before enterprise close

1. **No two-wheeler field proof on real bikes.** Adversarial TW `PASS_CLAIM` uses injected lean on car-phone noise. IO-VNBD regression logs are **cars**. Ship requires instrumented bicycle / motorcycle / scooter logs with GNSS outage segments.
2. **Open-loop 40–60 s ISRO bars fail on phone gyros.** Bias cal helps; it does not meet drift &lt;10% / &lt;100 m/km without a map. Selling “pure IMU tunnel mode” as ISRO-compliant is false.
3. **Product mode needs a known route / corridor.** Map-aided snap + heading blend assumes a polyline (active nav route, fleet graph, or OSM edge). No corridor ⇒ no product claim.
4. **Along-track residual remains after snap.** Cross-track is killed (F9); distance-along-road still drifts with speed error. Lane-level / meter-class along-track needs better speed (wheel / learned odometry) or GNSS fragments.
5. **Speed hold during outage.** Current stress uses last-good GPS speed. Real tunnels often decelerate; held speed biases along-track. Need speed estimator or vehicle speed API.
6. **Map prior portability.** Fast projection / sequential blend is proven in Python (`lab/stress/map_aid.py`). Web/Android product builds still need a production port + memory budget for city graphs.
7. **Device diversity.** One phone family in IO-VNBD-style logs ≠ SKU matrix (OEM gyro bias instability, mount orientation, thermal drift).
8. **Safety / liability.** DR is a **fallback**, not a primary navigation integrity source. No SIL/ASIL claim. Must expose uncertainty / “degraded” UI.
9. **Licensing & map data.** If OSM / commercial map tiles are used for corridors, clear redistribution and offline cache terms.
10. **No patented “secret sauce” filing yet.** See `docs/DISCLOSURE.md` — unpublished prototype; do not imply granted IP.

The deployment gate requires: corrected alignment on at least two files; at
least 80% of real 60 s mid/high-speed trials meeting both ISRO limits;
nominal-95% covariance coverage of at least 90% or an explicitly documented
calibrated target; and at least 10 qualifying real two-wheeler field logs.

## Acceptable near-term product framing

- “GNSS-denied **map-aided** dead reckoning for two-wheelers, with lean-aware heading on the phone IMU.”
- Backed by: car sanity on real data and an injected adversarial TW claim. The corrected full battery has one low-speed competitive map-aided scenario (three methods on the same scenario), using in-dataset route geometry; this is not independent OSM/fleet-map proof.
- Explicit non-claims: open-loop ISRO compliance; bike field validation until logs land.
