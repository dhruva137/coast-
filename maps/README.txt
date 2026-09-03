SIH26168 offline nodal-campus maps
==================================

Fully offline vector graph + a MapLibre style that needs no API key.
Basemap is CARTO Dark Matter (OSM attribution). Overlay sources are local GeoJSON.

Origin (WGS84): lat 12.9912, lon 77.5523, alt 920 m
ENU → LLA (matches core/ts campus.ts):
  mLat = 111132.92 - 559.82*cos(2λ) + 1.175*cos(4λ)
  mLon = 111412.84*cos(λ) - 93.5*cos(3λ)
  (λ = origin latitude in radians)
Approximate form: mLat ≈ 111132.92, mLon ≈ 111412.84 * cos(lat)

Files
-----
  style.json                 MapLibre style v8 (raster + GeoJSON layers)
  graphs/campus.graph.json   IRoadGraph dump — nodes + edges
  graphs/campus.geojson      LineStrings (edges), Points (nodes),
                             Polygons (basement footprint, tunnel tube)
  graphs/lights.geojson      Tunnel luminaires every 20 m
  graphs/demo_acts.json      act1–act5 + named ROUTES from campus.ts

How the web app should load them
--------------------------------
Serve this folder as static files, e.g. copy maps/ → web/public/maps/
so Vite exposes them at /maps/...

Option A — whole style (simplest):

  import maplibregl from "maplibre-gl";

  const map = new maplibregl.Map({
    container: "map",
    style: "/maps/style.json",
    center: [77.5523, 12.9912],
    zoom: 16,
  });

  GeoJSON URLs inside style.json are relative to the style URL, so
  graphs/campus.geojson resolves to /maps/graphs/campus.geojson.

Option B — add GeoJSON sources on any existing style (no key either):

  map.on("load", () => {
    map.addSource("campus", {
      type: "geojson",
      data: "/maps/graphs/campus.geojson",
    });
    map.addSource("lights", {
      type: "geojson",
      data: "/maps/graphs/lights.geojson",
    });

    // Edges: filter LineString by properties.style
    //   "outdoor"  glow teal   #2EE6C7
    //   "garage"   glow amber  #F5A623
    //   "tunnel"   glow orange #FF6B2B
    // Nodes:    properties.feature === "node"
    // Polygons: properties.kind === "basement" | "tunnel_tube"
    // Lights:   /maps/graphs/lights.geojson  (feature === "light")
  });

Demo acts (node-id arrays, same as core/ts/src/sim/campus.ts ROUTES)
-------------------------------------------------------------------
  fetch("/maps/graphs/demo_acts.json")

  act1  == act1_handoff        gate → basement loop → xmark
  act2  == act2_bicycle        figure-8 + roundabout (web Act 5 reuses this)
  act3  == act3_tunnel         quad → portals → exit_true
  act4  == defaultConfigs act4  round_n → j25 → j25a, plus j15 → j15a
  act5  == act2_bicycle        SDK / "the ask" overlay (see web/src/lib/runDemo.ts)

  Also present: act4_branch25, act4_branch15, act4_branch8,
  garage_wrong_ramp, garage_true_ramp.

Graph consumption
-----------------
  campus.graph.json matches IRoadGraph (name, origin, nodes, edges) with
  heading_deg, length_m, tunnel, garage, light_spacing_m, grade, lanes,
  plus kind / kinds on each edge.

Colours
-------
  outdoor  #2EE6C7
  garage   #F5A623
  tunnel   #FF6B2B

No Mapbox token. No Google key. Attribution: © OpenStreetMap © CARTO.
