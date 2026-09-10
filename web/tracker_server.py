"""
Localhost phone-tracker dashboard (demo P1 / file 07).

One command from the repo root:

    python -m web.tracker_server

Then open http://127.0.0.1:8787/ on the laptop. On the phone (tracker flavor),
enable the LAN stream in Settings and enter this laptop's LAN IPv4.

Find the laptop IP on Windows
-----------------------------
1. Open Command Prompt or PowerShell.
2. Run:  ipconfig
3. Under the active Wi-Fi / Ethernet adapter, copy **IPv4 Address**
   (e.g. 192.168.1.42). Do not use 127.0.0.1 on the phone — that is the phone
   itself. Both devices must be on the same LAN (or hotspot).

Bind: 0.0.0.0:8787  ·  POST /ingest  ·  GET /feed  ·  GET /
Stdlib only (http.server). No cloud, no credentials.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8787
MAX_TRAIL = 400

_lock = threading.Lock()
_latest: dict[str, Any] | None = None
_trail: deque[dict[str, Any]] = deque(maxlen=MAX_TRAIL)
_jsonl_path: str | None = None

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>IDR · live phone</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  :root {
    --surface: #0B0E11;
    --gnss: #4FC3F7;
    --idr: #00E0A4;
    --amber: #FFB300;
    --mute: #8A929B;
    --text: #FFFFFF;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--surface); color: var(--text);
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif; }
  #map { position: absolute; inset: 0; }
  .hud {
    position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
    z-index: 2; display: flex; flex-direction: column; align-items: center; gap: 8px;
    pointer-events: none;
  }
  .pill {
    padding: 10px 18px; border-radius: 99px;
    background: rgba(22, 26, 31, 0.92);
    border: 1.5px solid var(--mute);
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 12px; font-weight: 700; letter-spacing: 0.08em;
  }
  .pill.gnss { border-color: var(--gnss); color: var(--gnss); }
  .pill.idr { border-color: var(--amber); color: var(--amber); }
  .pill.idle { border-color: var(--mute); color: var(--mute); }
  .meta { font-size: 11px; color: var(--mute); letter-spacing: 0.04em; }
  .note {
    position: absolute; bottom: 14px; left: 14px; z-index: 2;
    max-width: 320px; font-size: 11px; color: var(--mute); line-height: 1.45;
    background: rgba(11, 14, 17, 0.85); padding: 10px 12px; border-radius: 6px;
    border: 1px solid rgba(232, 237, 242, 0.1);
  }
</style>
</head>
<body>
<div id="map"></div>
<div class="hud">
  <div id="modePill" class="pill idle">WAITING FOR PHONE</div>
  <div id="meta" class="meta">LAN viewer · estimate runs on-device</div>
</div>
<div class="note">
  Laptop is watching only — navigation stays on the phone.
  GNSS segments are blue; IDR / outage segments are teal.
</div>
<script>
const SURFACE = '#0B0E11';
const GNSS = '#4FC3F7';
const IDR = '#00E0A4';

const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap'
      }
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': SURFACE } },
      { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.55, 'raster-saturation': -0.85, 'raster-brightness-min': 0.05 } }
    ]
  },
  center: [-1.5969, 52.4095],
  zoom: 14,
  attributionControl: true
});

map.on('load', () => {
  map.addSource('trail', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] }
  });
  map.addLayer({
    id: 'trail-line',
    type: 'line',
    source: 'trail',
    paint: {
      'line-width': 4,
      'line-color': ['match', ['get', 'mode'], 'GNSS', GNSS, IDR],
      'line-opacity': 0.9
    }
  });
  map.addSource('dot', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] }
  });
  map.addLayer({
    id: 'phone-dot',
    type: 'circle',
    source: 'dot',
    paint: {
      'circle-radius': 8,
      'circle-color': ['match', ['get', 'mode'], 'GNSS', GNSS, IDR],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#fff'
    }
  });
  poll();
  setInterval(poll, 400);
});

let follow = true;
map.on('dragstart', () => { follow = false; });

async function poll() {
  try {
    const r = await fetch('/feed');
    if (!r.ok) return;
    const data = await r.json();
    render(data);
  } catch (e) { /* silent */ }
}

function render(data) {
  const pill = document.getElementById('modePill');
  const meta = document.getElementById('meta');
  const latest = data.latest;
  const trail = data.trail || [];
  if (!latest) {
    pill.className = 'pill idle';
    pill.textContent = 'WAITING FOR PHONE';
    return;
  }
  const mode = (latest.mode === 'GNSS') ? 'GNSS' : 'IDR';
  pill.className = 'pill ' + (mode === 'GNSS' ? 'gnss' : 'idr');
  pill.textContent = mode === 'GNSS' ? 'GPS' : 'IDR MODE — AI speed + road lock';
  const spd = Number(latest.speed_mps);
  const kmh = Number.isFinite(spd) ? (spd * 3.6).toFixed(0) : '--';
  meta.textContent = kmh + ' km/h · session ' + (latest.session || '?') + ' · LAN viewer';

  const coords = [];
  const feats = [];
  for (const p of trail) {
    const lon = Number(p.lon), lat = Number(p.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    coords.push([lon, lat]);
    if (coords.length >= 2) {
      feats.push({
        type: 'Feature',
        properties: { mode: p.mode === 'GNSS' ? 'GNSS' : 'IDR' },
        geometry: { type: 'LineString', coordinates: coords.slice(-2) }
      });
    }
  }
  map.getSource('trail').setData({ type: 'FeatureCollection', features: feats });

  const lon = Number(latest.lon), lat = Number(latest.lat);
  if (Number.isFinite(lon) && Number.isFinite(lat)) {
    map.getSource('dot').setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { mode },
        geometry: { type: 'Point', coordinates: [lon, lat] }
      }]
    });
    if (follow) map.easeTo({ center: [lon, lat], duration: 300 });
  }
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "IDRTracker/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/feed":
            with _lock:
                payload = {
                    "t": int(time.time() * 1000),
                    "latest": _latest,
                    "trail": list(_trail),
                }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/ingest":
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 65536:
            self.send_error(400, "bad body")
            return
        raw = self.rfile.read(length)
        try:
            frame = json.loads(raw.decode("utf-8"))
            if not isinstance(frame, dict):
                raise ValueError("expected object")
        except Exception:
            self.send_error(400, "invalid json")
            return
        with _lock:
            global _latest
            _latest = frame
            _trail.append(frame)
            if _jsonl_path:
                try:
                    with open(_jsonl_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(frame, separators=(",", ":")) + "\n")
                except OSError:
                    pass
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    global _jsonl_path
    args = list(sys.argv[1:] if argv is None else argv)
    if "--jsonl" in args:
        i = args.index("--jsonl")
        _jsonl_path = args[i + 1] if i + 1 < len(args) else "tracker_ingest.jsonl"
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"IDR phone-tracker listening on http://{HOST}:{PORT}/  "
        f"(open http://127.0.0.1:{PORT}/ locally)",
        flush=True,
    )
    print(
        "Find this laptop's LAN IP with:  ipconfig   "
        "(IPv4 Address under Wi-Fi / Ethernet) — enter that on the phone.",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
