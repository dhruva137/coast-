import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

/** Quiet map for the APK phone frame — no desktop zoom chrome. */
export function PhoneMap({ blackout }: { blackout: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://tiles.openfreemap.org/styles/dark",
      center: [77.5523, 12.9912],
      zoom: 16.1,
      pitch: 42,
      bearing: -12,
      attributionControl: false,
      interactive: true,
    });
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(ref.current);
    map.on("load", () => {
      map.resize();
      map.addSource("coast", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: [
              [77.5514, 12.9904],
              [77.5523, 12.9912],
              [77.5531, 12.992],
            ],
          },
        },
      });
      map.addLayer({
        id: "coast-line",
        type: "line",
        source: "coast",
        paint: { "line-color": "#00E0A4", "line-width": 4.5 },
      });
      map.addSource("puck", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: [77.5523, 12.9912] },
        },
      });
      map.addLayer({
        id: "puck-glow",
        type: "circle",
        source: "puck",
        paint: { "circle-radius": 16, "circle-color": "#00E0A4", "circle-opacity": 0.22 },
      });
      map.addLayer({
        id: "puck",
        type: "circle",
        source: "puck",
        paint: {
          "circle-radius": 7,
          "circle-color": "#00E0A4",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#0B0E11",
        },
      });
    });
    mapRef.current = map;
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className={`apk-map ${blackout ? "apk-map-blackout" : ""}`} ref={ref} />
  );
}
