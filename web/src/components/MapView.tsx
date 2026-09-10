import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { DemoBundle } from "../lib/runDemo";
import type { INavState, IRoadGraph } from "@sih26168/nav-core";

function graphFc(graph: IRoadGraph) {
  return {
    type: "FeatureCollection" as const,
    features: graph.edges.map((e) => {
      const a = graph.nodes.find((n) => n.id === e.from)!;
      const b = graph.nodes.find((n) => n.id === e.to)!;
      return {
        type: "Feature" as const,
        properties: { id: e.id, tunnel: e.tunnel, garage: e.garage },
        geometry: { type: "LineString" as const, coordinates: [[a.lon, a.lat], [b.lon, b.lat]] },
      };
    }),
  };
}

function lineOf(states: INavState[], n: number) {
  const slice = states.slice(0, Math.max(2, n));
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "LineString" as const,
      coordinates: slice.map((s) => [s.lon, s.lat]),
    },
  };
}

export function MapView({ demo, idx }: { demo: DemoBundle | null; idx: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const demoRef = useRef(demo);
  const idxRef = useRef(idx);
  demoRef.current = demo;
  idxRef.current = idx;

  const paint = (map: maplibregl.Map) => {
    const d = demoRef.current;
    if (!map.getSource("graph")) return;
    if (d) {
      (map.getSource("graph") as maplibregl.GeoJSONSource).setData(graphFc(d.graph));
      const i = Math.min(idxRef.current, d.ours.length - 1);
      (map.getSource("ours") as maplibregl.GeoJSONSource).setData({
        type: "FeatureCollection",
        features: [lineOf(d.ours, i + 1)],
      });
      (map.getSource("base") as maplibregl.GeoJSONSource).setData({
        type: "FeatureCollection",
        features: [lineOf(d.baseline, i + 1)],
      });
      const p = d.ours[i];
      if (p) {
        (map.getSource("dot") as maplibregl.GeoJSONSource).setData({
          type: "FeatureCollection",
          features: [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [p.lon, p.lat] } }],
        });
        map.jumpTo({ center: [p.lon, p.lat] });
      }
    }
  };

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://tiles.openfreemap.org/styles/dark",
      center: [-1.5969, 52.4095],
      zoom: 15.6,
      pitch: 48,
      bearing: -18,
      attributionControl: false,
    });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(ref.current);
    map.on("load", () => {
      map.addSource("graph", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("ours", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("base", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("dot", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "graph-tun",
        type: "line",
        source: "graph",
        filter: ["==", ["get", "tunnel"], true],
        paint: { "line-color": "#ff6b2d", "line-width": 6, "line-opacity": 0.85 },
      });
      map.addLayer({
        id: "graph-gar",
        type: "line",
        source: "graph",
        filter: ["==", ["get", "garage"], true],
        paint: { "line-color": "#ffc14a", "line-width": 5, "line-opacity": 0.7 },
      });
      map.addLayer({
        id: "graph-out",
        type: "line",
        source: "graph",
        filter: ["all", ["!=", ["get", "tunnel"], true], ["!=", ["get", "garage"], true]],
        paint: { "line-color": "#2a3a4a", "line-width": 4 },
      });
      map.addLayer({
        id: "base-line",
        type: "line",
        source: "base",
        paint: { "line-color": "#ff4d6a", "line-width": 3.5, "line-dasharray": [2, 1.2] },
      });
      map.addLayer({
        id: "ours-line",
        type: "line",
        source: "ours",
        paint: { "line-color": "#4da3ff", "line-width": 4.5 },
      });
      map.addLayer({
        id: "dot-glow",
        type: "circle",
        source: "dot",
        paint: { "circle-radius": 14, "circle-color": "#00d4aa", "circle-opacity": 0.25 },
      });
      map.addLayer({
        id: "dot",
        type: "circle",
        source: "dot",
        paint: {
          "circle-radius": 6,
          "circle-color": "#00d4aa",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#07090d",
        },
      });
      paint(map);
    });
    mapRef.current = map;
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.isStyleLoaded()) paint(map);
  }, [demo, idx]);

  return <div className="map" ref={ref} />;
}
