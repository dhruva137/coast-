# 02 — Research Findings: open-source landscape

**Purpose:** name exactly which open-source work to *adopt* (pull code/approach)
vs. merely *cite* (for the novelty/feasibility slides). We do NOT rebuild what
exists; we also do NOT bloat the app with heavy SDKs we don't need.

---

## A. Learned inertial odometry (for F1/F5 framing + the speed model)

| Project | What it is | Decision | Why |
|---|---|---|---|
| **nesl/tinyodom** (github.com/nesl/tinyodom) | Hardware-aware *tiny* neural inertial nav, **TFLite on-device**, NAS, eval + deploy | **ADOPT the idea, CITE the paper** | Closest to our on-device AVNet-tiny. Borrow its leave-trajectory-out eval framing and "tiny model on real hardware" positioning. We already have ONNX; do not switch frameworks. |
| **mbrossar/ai-imu-dr** (github.com/mbrossar/ai-imu-dr) | AI-IMU dead reckoning for **cars**, invariant EKF + CNN-learned measurement covariance, KITTI | **CITE (closest cousin)** | This is the vehicle analogue of what we do. On a slide: "prior art learns covariance for an EKF on KITTI; we constrain to a road graph and measure the heading ceiling." Differentiates us. |
| **CathIAS/TLIO** (github.com/CathIAS/TLIO) | Tight learned inertial odometry, 3D, beats RoNIN | **CITE** | Establishes the research family. We are the *tiny, road-constrained, phone* member. Do not adopt — full 3D EKF is overkill for our 2D road problem. |
| **RoNIN** (Robust Neural Inertial Navigation) | Pedestrian benchmark + methods | **CITE** | Pedestrian reference for the walking-PDR differentiator. Our StepDetector (Weinberg) is the classical baseline; RoNIN is the learned state of the art to name. |

**Net:** keep our own AVNet-tiny + ONNX. Use these four to say, truthfully, "we
are in the learned-inertial-odometry family (TLIO/RoNIN/AI-IMU-DR/TinyOdom), and
our specific contribution is road-graph-constrained state + a measured heading
ceiling on IO-VNBD that the literature doesn't report." That is a defensible F1.

---

## B. Offline map rendering (for F3 + the tunnel demo)

| Project | Decision | Integration note |
|---|---|---|
| **MapLibre Native Android** (already a dependency, `org.maplibre.gl:android-sdk:11.5.2`) | **KEEP** | This is the renderer. No change. |
| **Offline MBTiles via `mbtiles://`** (maplibre-native Discussion #393; Medium "How to display offline maps using Maplibre/Mapbox on Android") | **ADOPT for the tunnel demo** | Pre-pack a small raster `.mbtiles` of the demo area into app assets so the basemap is guaranteed present **even with wifi off at the venue**. This is the reliable version of "the map survives the tunnel". See `04_APP_UI_SPEC.md` §Offline. |
| **maplibre/maplibre-navigation-android** | **DO NOT ADOPT** | Full turn-by-turn nav SDK; heavy, and we draw our own track/puck. Cite only if asked "why not just use a nav SDK?" → answer: we need the *estimator*, not routing. |

**Reliability rule:** live OSM tiles over venue wifi are a risk. Ship a bundled
`.mbtiles` of the demo neighbourhood so the map is offline-guaranteed; fall back
to live OSM tiles only when online. The `chooseMapBackend` logic already models
online/offline/tiles-cached — extend it to prefer the bundled mbtiles.

---

## C. Sensor replay / injection (for the blackout demo + stability test)

No external dependency needed — this is ours to build (`05_DEMO_MODES_SPEC.md`).
The pattern (confirmed standard in juha-ylikoski/imu-dead-reckoning and the
TinyOdom replay harness): a `SensorSource` interface with two implementations —
`LiveSensorSource` (the phone's `SensorManager`) and `ReplaySensorSource` (reads
an IO-VNBD CSV and emits frames on the same callback at the recorded cadence).
The pipeline downstream cannot tell them apart. This is what makes the
blackout-injection demo *honest*: it is the real estimator, fed recorded real
sensor data.

---

## D. What NOT to pull in (scope discipline for a 2-day window)

- No new ML framework (we have ONNX Runtime Mobile; TinyOdom is TFLite — don't switch).
- No routing/navigation SDK (we render our own track).
- No cloud anything (breaks the F8 privacy story and the offline thesis).
- No Google Maps (settled; breaks no-INTERNET property and needs live wifi).

---

## Sources

- [nesl/tinyodom](https://github.com/nesl/tinyodom)
- [mbrossar/ai-imu-dr](https://github.com/mbrossar/ai-imu-dr)
- [CathIAS/TLIO](https://github.com/CathIAS/TLIO) · [TLIO paper (arXiv 2007.01867)](https://ar5iv.labs.arxiv.org/html/2007.01867)
- [Deep Learning for Inertial Positioning: A Survey (arXiv 2303.03757)](https://arxiv.org/pdf/2303.03757)
- [maplibre-native offline MBTiles (Discussion #393)](https://github.com/maplibre/maplibre-native/discussions/393)
- [How to display offline maps using Maplibre/Mapbox on Android (Medium)](https://medium.com/@ty2/how-to-display-offline-maps-using-maplibre-mapbox-39ad0f3c7543)
- [maplibre/maplibre-navigation-android](https://github.com/maplibre/maplibre-navigation-android)
