"""
COAST localhost live console (induction Block 3).

One command from the repo root:

    python -m web.coast_console

Open http://127.0.0.1:8787/ — live phone map, Train (real lab.demo epochs),
measured algorithm ledger, and figures/ when training finishes.

Endpoints
---------
GET  /            console / front-door HTML shell
GET  /static/*    design-system assets (MIME + Cache-Control: no-store)
GET  /api/claims  headline + full claim registry from win_tuning/CLAIMS.json
POST /api/login   operator passcode → session cookie (when auth configured)
POST /api/logout  clear operator session
GET  /api/session open_mode / authenticated snapshot
POST /ingest      phone LAN frames (same contract as tracker_server; LAN fallback)
POST /api/pair/open  adopt a token typed from the phone; register relay mailbox
GET  /feed        latest + trail
POST /train       start real ``python -m lab.demo`` subprocess (quick-run)
GET  /train/stream  SSE: real stdout lines + parsed epoch metrics (no fake loss)
GET  /train/status  JSON snapshot of the current / last train run
GET  /metrics     baseline ledger from committed measured summary files
GET  /figures/<name>  serve PNGs under figures/
GET  /api/traces  list filter traces under lab/stress/results/traces/ (name, honesty, bytes)
GET  /api/traces/<name.json>  filter traces (basename only; ``latest.json`` → newest)
GET  /lab/stress/results/traces/<name.json>  same traces (legacy path)
GET  /replay      302 → /static/trace_replay.html (truth vs free-DR vs COAST)

``/pair``, ``/ingest``, and ``/api/claims`` stay reachable without an operator
session. Static assets stay public so the front-door / sign-in can load offline.

Stdlib only (http.server + SSE). Bind 0.0.0.0:8787 so a phone on LAN can POST /ingest.
Cold start with no network and no phone must still render a useful page (CDN map/chart
are optional; Train/ledger stay local).
"""

from __future__ import annotations

import importlib
import json
import mimetypes
import os
import queue
import re
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse
import urllib.error
import urllib.request

HOST = "0.0.0.0"
PORT = 8787
MAX_TRAIL = 400
REPO = Path(__file__).resolve().parents[1]
FIGURES = REPO / "figures"
TRACES_DIR = REPO / "lab" / "stress" / "results" / "traces"
STATIC_DIR = Path(__file__).resolve().parent / "static"
_API_TRACE_PREFIX = "/api/traces/"
_TRACE_URL_PREFIX = "/lab/stress/results/traces/"

# Console UI and the pairing/fleet layer. Imported both ways so the module runs
# as `python -m web.coast_console` and as a plain script.
try:  # pragma: no cover - import shim
    from web.console_ui import PAGE as CONSOLE_PAGE
    from web.console_ui import PAIR_PAGE
    from web.pairing import (
        Fleet,
        configured_relay_base,
        pair_payload,
        pull_relay_into_fleet,
        qr_svg,
        register_relay_mailbox,
    )
    from web import uk_demo as _uk_demo
except ImportError:  # pragma: no cover
    from console_ui import PAGE as CONSOLE_PAGE  # type: ignore
    from console_ui import PAIR_PAGE  # type: ignore
    from pairing import (  # type: ignore
        Fleet,
        configured_relay_base,
        pair_payload,
        pull_relay_into_fleet,
        qr_svg,
        register_relay_mailbox,
    )
    import uk_demo as _uk_demo  # type: ignore

_UI_PY = Path(__file__).resolve().parent / "console_ui.py"
_ui_mtime = 0.0


def _reload_ui() -> None:
    """Pick up console_ui.py edits without restarting the process.

    PAGE/PAIR_PAGE are imported once at boot; a long-lived laptop console
    otherwise keeps serving yesterday's HTML until you kill Python.
    """
    global CONSOLE_PAGE, PAIR_PAGE, _ui_mtime
    try:
        mtime = _UI_PY.stat().st_mtime
    except OSError:
        return
    if mtime == _ui_mtime:
        return
    try:
        from web import console_ui as cui
    except ImportError:  # pragma: no cover
        import console_ui as cui  # type: ignore
    cui = importlib.reload(cui)
    CONSOLE_PAGE = cui.PAGE
    PAIR_PAGE = cui.PAIR_PAGE
    _ui_mtime = mtime


_STATIC_HREF = re.compile(r"""(/static/)([A-Za-z0-9_./-]+)""")


def _with_asset_versions(html: str) -> str:
    """Stamp /static/... URLs with file mtime so the browser cannot keep old JS."""

    def _repl(match: re.Match[str]) -> str:
        prefix, rel = match.group(1), match.group(2)
        fp = STATIC_DIR / rel
        try:
            ver = int(fp.stat().st_mtime)
        except OSError:
            ver = int(time.time())
        return f"{prefix}{rel}?v={ver}"

    return _STATIC_HREF.sub(_repl, html)

# Operator session auth (Phase 1 §1.3). Optional only if the module is absent.
try:  # pragma: no cover - import shim
    from web import auth as _auth
except ImportError:  # pragma: no cover
    try:
        import auth as _auth  # type: ignore
    except ImportError:
        _auth = None  # type: ignore

# Input hardening (Phase 6) — optional if another agent has not landed yet.
try:  # pragma: no cover - import shim
    from web.security import (
        FIGURE_SUFFIXES,
        MAX_BODY_BYTES,
        RateLimiter,
        assert_path_in_roots,
        parse_content_length,
        require_json_content_type,
        safe_join,
    )
except ImportError:  # pragma: no cover
    try:
        from security import (  # type: ignore
            FIGURE_SUFFIXES,
            MAX_BODY_BYTES,
            RateLimiter,
            assert_path_in_roots,
            parse_content_length,
            require_json_content_type,
            safe_join,
        )
    except ImportError:
        MAX_BODY_BYTES = 65_536
        FIGURE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".json"})

        def parse_content_length(headers: Any, *, max_bytes: int = MAX_BODY_BYTES):  # type: ignore
            raw = headers.get("Content-Length") if headers is not None else None
            if raw is None or raw == "":
                return 0, None
            try:
                length = int(raw)
            except (TypeError, ValueError):
                return None, "invalid Content-Length"
            if length < 0:
                return None, "invalid Content-Length"
            if length > max_bytes:
                return None, f"body too large (max {max_bytes} bytes)"
            return length, None

        def require_json_content_type(headers: Any) -> str | None:  # type: ignore
            return None

        class RateLimiter:  # type: ignore
            def __init__(self, **kwargs: Any) -> None:
                pass

            def allow(self, key: str) -> bool:
                return True

            def reset(self) -> None:
                pass

        def safe_join(root: Path, *parts: str) -> Path | None:  # type: ignore
            if not parts or any(("/" in p or "\\" in p or ".." in p) for p in parts):
                return None
            return (root.joinpath(*parts)).resolve()

        def assert_path_in_roots(path: Path, roots: list[Path]) -> bool:  # type: ignore
            try:
                resolved = path.resolve()
                return any(resolved == r.resolve() or r.resolve() in resolved.parents for r in roots)
            except OSError:
                return False

FLEET = Fleet()
# Per-IP token buckets for deliberately unauthenticated write surfaces.
_INGEST_LIMITER = RateLimiter(rate=60, per_s=60.0, burst=30)
_PAIR_LIMITER = RateLimiter(rate=20, per_s=60.0, burst=10)
_LOGIN_LIMITER = RateLimiter(rate=10, per_s=60.0, burst=5)
CLAIMS_JSON = REPO / "win_tuning" / "CLAIMS.json"
EDGE_README = REPO / "core" / "cpp" / "apps" / "README.md"

# Front-door headline claim ids (PHASE_1_SHELL §1.2). Never invent values.
_HEADLINE_CLAIM_IDS = (
    "map_in_loop_improvement_x",
    "perfect_gyro_fail_pct",
    "edge_worst_case_hz",
    "edge_worst_case_multiple",
)

# Console HTML gated when an operator hash is configured (unless open mode).
# Phone paths stay public: /pair, /ingest, /api/health, /static/*.
# Operator HTML and control APIs (fleet, pair/new, forget, demo, train) gate
# when a passcode is configured.
_PROTECTED_HTML = frozenset({"/", "/index.html"})
_OPERATOR_POST = frozenset(
    {
        "/train",
        "/train/start",
        "/train/clear",
        "/api/demo/uk",
        "/api/demo/uk/start",
        "/api/demo/uk/stop",
        "/api/pair/new",
        "/api/pair/open",
        "/api/forget_all",
    }
)

_MAPFILTER_REPORT = REPO / "lab" / "stress" / "results" / "mapfilter" / "report.json"
_MAPFILTER_SUMMARY = "lab/stress/results/mapfilter/summary.md"
_ISRO_REPORT = REPO / "lab" / "stress" / "results" / "isro_benchmark" / "report.json"
_ISRO_SUMMARY = "lab/stress/results/isro_benchmark/summary.md"
_HEADING_REPORT = REPO / "lab" / "stress" / "results" / "heading_ablation" / "report.json"
_HEADING_SUMMARY = "lab/stress/results/heading_ablation/summary.md"
_SPEED_SUMMARY = "lab/models/results/speed_bakeoff/summary.md"

# lab.demo human line (legacy) OR COAST_EVENT JSON (preferred).
_EPOCH_RE = re.compile(
    r"epoch\s+(\d+)\s*/\s*(\d+)\s+(?:objective=\w+\s+)?loss=([0-9.eE+-]+)"
    r"(?:\s+(?:held_)?rmse=([0-9.eE+-]+))?(?:\s+\((\w+)\))?\s+.*?([0-9.]+)s",
    re.IGNORECASE,
)
_RMSE_RE = re.compile(
    r"quick RMSE model=([0-9.eE+-]+)\s+hold=([0-9.eE+-]+)\s+\(([0-9.]+)s\)",
    re.IGNORECASE,
)

_lock = threading.Lock()
_latest: dict[str, Any] | None = None
_trail: deque[dict[str, Any]] = deque(maxlen=MAX_TRAIL)
_jsonl_path: str | None = None

RELAY_POLL_S = 1.5
_relay_stop = threading.Event()
_relay_thread: threading.Thread | None = None


def _pair_response(s: Any, lan: str, relay: str | None) -> dict[str, Any]:
    if relay:
        register_relay_mailbox(s.token, relay)
    payload = pair_payload(s.token, lan, relay)
    return {
        "token": s.token,
        "payload": payload,
        "lan": lan,
        "relay": relay,
        "candidates": _lan_candidates(),
        "qr_svg": qr_svg(payload),
        "expires_in_s": 15 * 60,
        "tip": (
            "Same Wi-Fi often blocks phone→laptop (AP isolation). "
            "Use the laptop hotspot, or keep the public relay — phone never needs a route to this PC."
        ),
    }


def _relay_pull_loop() -> None:
    """Laptop pulls GET {relay}/feed?s=TOKEN; phone never needs a route here."""
    while not _relay_stop.wait(RELAY_POLL_S):
        base = configured_relay_base()
        if not base:
            continue
        for token in FLEET.active_tokens():
            try:
                pull_relay_into_fleet(FLEET, token, relay_base=base)
            except Exception as exc:  # noqa: BLE001 — never kill the poller
                sys.stderr.write(f"relay pull {token[:8]}…: {exc}\n")


def _start_relay_puller() -> None:
    global _relay_thread
    if _relay_thread is not None and _relay_thread.is_alive():
        return
    _relay_stop.clear()
    _relay_thread = threading.Thread(target=_relay_pull_loop, name="coast-relay-pull", daemon=True)
    _relay_thread.start()


_train_lock = threading.Lock()
_train_proc: subprocess.Popen[str] | None = None
_train_subscribers: list[queue.Queue[dict[str, Any] | None]] = []
_train_history: list[dict[str, Any]] = []
_train_status: dict[str, Any] = {
    "running": False,
    "pid": None,
    "started_at": None,
    "finished_at": None,
    "returncode": None,
    "mode": "idle",
    "label": "fast re-run (lab.demo quick AVNet) - full 2.02x lower median position error cites mapfilter",
    "epochs": [],
    "last_line": None,
    "error": None,
}


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>COAST · live console</title>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" media="print" onload="this.media='all'"/>
<style>
  :root {
    --bg: #0B0E11;
    --panel: #12161C;
    --border: rgba(232, 237, 242, 0.12);
    --gnss: #4FC3F7;
    --idr: #00E0A4;
    --amber: #FFB300;
    --mute: #8A929B;
    --text: #E8EDF2;
    --danger: #FF6B6B;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--bg); color: var(--text);
    font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; }
  body { display: grid; grid-template-rows: auto 1fr auto; min-height: 100%; }
  header {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    padding: 12px 18px; border-bottom: 1px solid var(--border);
    background: rgba(18, 22, 28, 0.95);
  }
  header h1 { margin: 0; font-size: 15px; letter-spacing: 0.12em; font-weight: 700; }
  header h1 span { color: var(--idr); }
  .badge {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px; color: var(--mute); letter-spacing: 0.04em;
  }
  .badge.live { color: var(--idr); }
  .badge.wait { color: var(--mute); }
  main {
    display: grid; grid-template-columns: 1.15fr 1fr; gap: 12px;
    padding: 12px; min-height: 0;
  }
  @media (max-width: 980px) { main { grid-template-columns: 1fr; } }
  .panel {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    display: flex; flex-direction: column; min-height: 0; overflow: hidden;
  }
  .panel h2 {
    margin: 0; padding: 12px 14px 8px; font-size: 12px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--mute); font-weight: 600;
  }
  #map { flex: 1; min-height: 320px; }
  .map-meta {
    padding: 8px 14px 12px; font-size: 12px; color: var(--mute);
    display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
  }
  .pill {
    display: inline-block; padding: 6px 12px; border-radius: 99px;
    border: 1.5px solid var(--mute); font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
  }
  .pill.gnss { border-color: var(--gnss); color: var(--gnss); }
  .pill.idr { border-color: var(--idr); color: var(--idr); }
  .pill.idle { border-color: var(--mute); color: var(--mute); }
  .train-body { padding: 0 14px 14px; display: flex; flex-direction: column; gap: 10px; flex: 1; min-height: 0; }
  .train-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  button#trainBtn {
    background: var(--idr); color: #04140F; border: 0; border-radius: 8px;
    padding: 10px 18px; font-weight: 700; letter-spacing: 0.06em; cursor: pointer;
    font-family: inherit; font-size: 13px;
  }
  button#trainBtn:disabled { opacity: 0.45; cursor: not-allowed; }
  .honest {
    font-size: 11px; color: var(--amber); line-height: 1.4; max-width: 42rem;
  }
  .chart-wrap { position: relative; height: 180px; }
  #log {
    flex: 1; min-height: 100px; max-height: 160px; overflow: auto;
    background: #0B0E11; border: 1px solid var(--border); border-radius: 6px;
    padding: 8px 10px; font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px; color: var(--mute); white-space: pre-wrap;
  }
  footer {
    border-top: 1px solid var(--border); padding: 12px 14px 16px;
    display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 12px;
  }
  @media (max-width: 980px) { footer { grid-template-columns: 1fr; } }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
  th { color: var(--mute); font-weight: 600; letter-spacing: 0.06em; font-size: 11px; text-transform: uppercase; }
  td.source { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10px; color: var(--mute); word-break: break-all; }
  td.value { color: var(--idr); font-weight: 700; white-space: nowrap; }
  .figures { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  @media (max-width: 980px) { .figures { grid-template-columns: 1fr; } }
  .figures figure { margin: 0; background: #0B0E11; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .figures img { width: 100%; display: block; background: #000; min-height: 80px; }
  .figures figcaption { padding: 6px 8px; font-size: 10px; color: var(--mute); }
  .empty-fig { padding: 18px; color: var(--mute); font-size: 12px; }
  .intro {
    margin: 0; padding: 10px 18px; font-size: 12px; line-height: 1.45; color: var(--mute);
    border-bottom: 1px solid var(--border); background: #0e1218;
  }
  .intro strong { color: var(--text); font-weight: 600; }
  .map-fallback {
    flex: 1; min-height: 320px; display: flex; flex-direction: column; justify-content: center;
    gap: 10px; padding: 24px; color: var(--mute); font-size: 13px; line-height: 1.5;
  }
  .map-fallback h3 { margin: 0; color: var(--text); font-size: 14px; letter-spacing: 0.06em; }
  .chart-fallback {
    height: 100%; display: flex; align-items: center; justify-content: center;
    color: var(--mute); font-size: 12px; text-align: center; padding: 12px;
  }
</style>
</head>
<body>
<header>
  <h1>COAST <span>LIVE CONSOLE</span></h1>
  <div id="lanBadge" class="badge wait">Waiting for phone stream over LAN</div>
</header>
<p class="intro" id="introBanner">
  <strong>What this is:</strong> a localhost presenter console for COAST —
  optional live phone map (LAN <code>/ingest</code>), real <code>python -m lab.demo</code> training
  (loss from stdout only — never simulated), and a measured algorithm ledger from committed
  <code>report.json</code> files. Works without a phone; offline CDN may disable the basemap/chart scripts only.
</p>
<main>
  <section class="panel">
    <h2>Live phone map</h2>
    <div id="map"></div>
    <div class="map-meta">
      <span id="modePill" class="pill idle">WAITING</span>
      <span id="speedMeta">—</span>
      <span style="color:var(--gnss)">■ GNSS</span>
      <span style="color:var(--idr)">■ IDR</span>
    </div>
  </section>
  <section class="panel">
    <h2>Live training</h2>
    <div class="train-body">
      <div class="train-row">
        <button id="trainBtn" type="button">Train</button>
        <span id="trainState" class="badge wait">idle</span>
      </div>
      <p class="honest">
        Train runs the same code as <code>python -m lab.demo</code> (quick AVNet).
        <strong>Held-out RMSE</strong> is the headline chart; train loss is secondary and
        MSE/NLL never share an axis (fake cliff at the objective switch). Hold-last-speed
        baseline is the flat reference. If training fails, the real error is shown; no invented curve.
        Headline <strong>2.02× lower median position error</strong> always cites the full committed mapfilter run, not this fast re-run.
      </p>
      <div class="chart-stack" id="chartStack">
        <div class="chart-wrap" id="chartWrap"><canvas id="rmseChart"></canvas></div>
        <div class="chart-wrap secondary" id="chartWrapLoss"><canvas id="lossChart"></canvas></div>
      </div>
      <div id="log"></div>
    </div>
  </section>
</main>
<footer>
  <section class="panel" style="overflow:auto">
    <h2>Algorithm ledger (measured)</h2>
    <div style="padding:0 0 8px">
      <table>
        <thead>
          <tr><th>Component</th><th>Result</th><th>Source</th></tr>
        </thead>
        <tbody id="ledgerBody">
          <tr><td colspan="3" style="color:var(--mute)">Loading /metrics…</td></tr>
        </tbody>
      </table>
      <p id="ledgerNote" class="honest" style="padding:10px 14px;margin:0"></p>
    </div>
  </section>
  <section class="panel">
    <h2>Figures</h2>
    <div id="figures" class="figures">
      <div class="empty-fig">Press Train to regenerate figures/ from the live demo (or they appear if already present).</div>
    </div>
  </section>
</footer>
<noscript>
  <p class="intro">JavaScript is off. This page is the COAST live console at localhost:8787 —
  phone LAN ingest, Train via lab.demo, and measured ledger. Enable JS for interactivity.</p>
</noscript>
<script>
window.__coastCdn = { maplibre: false, chart: false };
function __coastMaybeBoot() {
  if (window.__coastBooted) return;
  if (typeof maplibregl !== 'undefined') window.__coastCdn.maplibre = true;
  if (typeof Chart !== 'undefined') window.__coastCdn.chart = true;
  // Boot once DOM is ready; do not wait forever for CDN.
  if (document.readyState === 'loading') return;
  window.__coastBooted = true;
  if (typeof window.__coastBoot === 'function') window.__coastBoot();
}
</script>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"
  async onload="__coastMaybeBoot()" onerror="__coastMaybeBoot()"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
  async onload="__coastMaybeBoot()" onerror="__coastMaybeBoot()"></script>
<script>
(function () {
function boot() {
const SURFACE = '#0B0E11';
const GNSS = '#4FC3F7';
const IDR = '#00E0A4';
const FIGURE_NAMES = ['drift_comparison.png', 'cdf_error.png', 'trajectory_overlay.png'];

let map = null;
let follow = true;
let lossChart = null;
let rmseChart = null;
let holdBaselineRmse = null;
let switchEpoch = null;
let mseLossStart = null;
let nllLossStart = null;

function showMapFallback(reason) {
  const el = document.getElementById('map');
  if (!el) return;
  el.innerHTML =
    '<div class="map-fallback">' +
    '<h3>Map unavailable offline</h3>' +
    '<div>' + reason + '</div>' +
    '<div>This console still serves Train, the measured ledger, and LAN ingest when a phone connects. ' +
    'Reconnect to load MapLibre / OSM tiles, or stream the phone with the tracker APK.</div>' +
    '</div>';
  const badge = document.getElementById('lanBadge');
  if (badge && badge.classList.contains('wait')) {
    badge.textContent = 'No phone · map CDN optional · Train & ledger work locally';
  }
}

function initMap() {
  if (typeof maplibregl === 'undefined') {
    showMapFallback('MapLibre GL failed to load from the CDN (typical on airplane mode / no network).');
    pollFeed();
    setInterval(pollFeed, 400);
    return;
  }
  try {
    map = new maplibregl.Map({
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
      center: [-1.5969, 52.4095],  // Coventry / IO-VNBD (training + APK demo)
      zoom: 14
    });
  } catch (err) {
    showMapFallback('MapLibre init error: ' + err);
    pollFeed();
    setInterval(pollFeed, 400);
    return;
  }
  map.on('error', () => { /* tile failures offline — keep shell */ });
  map.on('load', () => {
    map.addSource('trail', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({
      id: 'trail-line', type: 'line', source: 'trail',
      paint: {
        'line-width': 4,
        'line-color': ['match', ['get', 'mode'], 'GNSS', GNSS, IDR],
        'line-opacity': 0.9
      }
    });
    map.addSource('dot', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({
      id: 'phone-dot', type: 'circle', source: 'dot',
      paint: {
        'circle-radius': 8,
        'circle-color': ['match', ['get', 'mode'], 'GNSS', GNSS, IDR],
        'circle-stroke-width': 2,
        'circle-stroke-color': '#fff'
      }
    });
    pollFeed();
    setInterval(pollFeed, 400);
  });
  map.on('dragstart', () => { follow = false; });
}

async function pollFeed() {
  try {
    const r = await fetch('/feed');
    if (!r.ok) return;
    renderFeed(await r.json());
  } catch (e) { /* silent — localhost may still be fine */ }
}

function renderFeed(data) {
  const pill = document.getElementById('modePill');
  const meta = document.getElementById('speedMeta');
  const badge = document.getElementById('lanBadge');
  const latest = data.latest;
  const trail = data.trail || [];
  if (!latest) {
    pill.className = 'pill idle';
    pill.textContent = 'WAITING';
    badge.className = 'badge wait';
    badge.textContent = map
      ? 'Waiting for phone stream over LAN'
      : 'No phone · map CDN optional · Train & ledger work locally';
    return;
  }
  badge.className = 'badge live';
  badge.textContent = 'Streaming from phone over LAN';
  const mode = (latest.mode === 'GNSS') ? 'GNSS' : 'IDR';
  pill.className = 'pill ' + (mode === 'GNSS' ? 'gnss' : 'idr');
  pill.textContent = mode === 'GNSS' ? 'GPS' : 'IDR';
  const spd = Number(latest.speed_mps);
  const kmh = Number.isFinite(spd) ? (spd * 3.6).toFixed(0) : '--';
  meta.textContent = kmh + ' km/h · session ' + (latest.session || '?');

  if (!map) return;

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
  try {
    const trailSrc = map.getSource('trail');
    if (trailSrc) trailSrc.setData({ type: 'FeatureCollection', features: feats });
    const lon = Number(latest.lon), lat = Number(latest.lat);
    if (Number.isFinite(lon) && Number.isFinite(lat)) {
      const dotSrc = map.getSource('dot');
      if (dotSrc) {
        dotSrc.setData({
          type: 'FeatureCollection',
          features: [{
            type: 'Feature',
            properties: { mode },
            geometry: { type: 'Point', coordinates: [lon, lat] }
          }]
        });
      }
      if (follow) map.easeTo({ center: [lon, lat], duration: 300 });
    }
  } catch (_) { /* map not ready */ }
}

function initChart() {
  const wrap = document.getElementById('chartWrap');
  if (typeof Chart === 'undefined') {
    if (wrap) {
      wrap.innerHTML =
        '<div class="chart-fallback">Chart.js CDN unavailable offline. ' +
        'Train still runs; real epoch lines appear in the log below — no fake curve.</div>';
    }
    const lossWrap = document.getElementById('chartWrapLoss');
    if (lossWrap) lossWrap.innerHTML = '';
    return;
  }
  const rmseCanvas = document.getElementById('rmseChart');
  const lossCanvas = document.getElementById('lossChart');
  if (!rmseCanvas || !lossCanvas) return;
  const axisOpts = {
    x: { ticks: { color: '#8A929B' }, grid: { color: 'rgba(255,255,255,0.04)' }, title: { display: true, text: 'epoch', color: '#8A929B' } },
    y: { ticks: { color: '#8A929B' }, grid: { color: 'rgba(255,255,255,0.06)' } }
  };
  rmseChart = new Chart(rmseCanvas, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'held-out RMSE (m/s)',
          data: [],
          borderColor: IDR,
          backgroundColor: 'rgba(0,224,164,0.12)',
          tension: 0.2,
          pointRadius: 3,
          borderWidth: 2
        },
        {
          label: 'hold-last-speed baseline',
          data: [],
          borderColor: '#8A929B',
          borderDash: [6, 4],
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      scales: {
        ...axisOpts,
        y: { ...axisOpts.y, title: { display: true, text: 'held RMSE m/s', color: '#8A929B' } }
      },
      plugins: {
        legend: { labels: { color: '#E8EDF2' } },
        title: { display: true, text: 'Headline: held-out RMSE (task metric)', color: '#E8EDF2', font: { size: 12 } }
      }
    }
  });
  lossChart = new Chart(lossCanvas, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'MSE / phase-start',
          data: [],
          borderColor: '#FF6B2D',
          backgroundColor: 'rgba(255,107,45,0.10)',
          tension: 0.2,
          pointRadius: 3,
          borderWidth: 2,
          spanGaps: false
        },
        {
          label: 'NLL / phase-start',
          data: [],
          borderColor: '#C77DFF',
          backgroundColor: 'rgba(199,125,255,0.10)',
          tension: 0.2,
          pointRadius: 3,
          borderWidth: 2,
          spanGaps: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      scales: {
        ...axisOpts,
        y: { ...axisOpts.y, title: { display: true, text: 'train loss (phase-separated)', color: '#8A929B' } }
      },
      plugins: {
        legend: { labels: { color: '#E8EDF2' } },
        title: { display: true, text: 'Secondary: train loss — MSE & NLL never share meaning', color: '#E8EDF2', font: { size: 11 } },
        annotation: undefined
      }
    }
  });
}

function resetChart() {
  holdBaselineRmse = null;
  switchEpoch = null;
  mseLossStart = null;
  nllLossStart = null;
  if (rmseChart) {
    rmseChart.data.labels = [];
    rmseChart.data.datasets[0].data = [];
    rmseChart.data.datasets[1].data = [];
    rmseChart.update();
  }
  if (lossChart) {
    lossChart.data.labels = [];
    lossChart.data.datasets[0].data = [];
    lossChart.data.datasets[1].data = [];
    lossChart.options.plugins.title.text =
      'Secondary: train loss — each phase ÷ its own start (MSE/NLL not raw-shared)';
    lossChart.update();
  }
}

function appendEpoch(msg) {
  const epoch = msg.epoch;
  const loss = msg.loss;
  const held = (typeof msg.held_rmse === 'number') ? msg.held_rmse
    : (typeof msg.rmse === 'number' ? msg.rmse : null);
  const objective = String(msg.objective || msg.mode || '').toUpperCase();
  if (typeof msg.hold_baseline_rmse === 'number' && Number.isFinite(msg.hold_baseline_rmse)) {
    holdBaselineRmse = msg.hold_baseline_rmse;
  }
  const label = String(epoch);
  if (rmseChart && held != null && Number.isFinite(held)) {
    rmseChart.data.labels.push(label);
    rmseChart.data.datasets[0].data.push(held);
    rmseChart.data.datasets[1].data.push(
      holdBaselineRmse != null && Number.isFinite(holdBaselineRmse) ? holdBaselineRmse : null
    );
    rmseChart.update();
  }
  if (lossChart && typeof loss === 'number' && Number.isFinite(loss)) {
    lossChart.data.labels.push(label);
    let msePoint = null;
    let nllPoint = null;
    if (objective === 'MSE') {
      if (mseLossStart == null) mseLossStart = loss;
      msePoint = (mseLossStart > 0) ? (loss / mseLossStart) : loss;
    } else if (objective === 'NLL') {
      if (nllLossStart == null) nllLossStart = loss;
      nllPoint = (Math.abs(nllLossStart) > 1e-12) ? (loss / nllLossStart) : loss;
    }
    lossChart.data.datasets[0].data.push(msePoint);
    lossChart.data.datasets[1].data.push(nllPoint);
    if (switchEpoch != null && epoch === switchEpoch) {
      lossChart.options.plugins.title.text =
        'Secondary: train loss — MSE → NLL at epoch ' + switchEpoch + ' (normalised; not an accuracy cliff)';
    }
    lossChart.update();
  }
}

function appendLog(text) {
  const el = document.getElementById('log');
  el.textContent += text + '\n';
  el.scrollTop = el.scrollHeight;
}

function setTrainUi(running, label) {
  document.getElementById('trainBtn').disabled = !!running;
  const st = document.getElementById('trainState');
  st.textContent = label || (running ? 'running · fast re-run' : 'idle');
  st.className = 'badge ' + (running ? 'live' : 'wait');
}

let es = null;
async function startTrain() {
  resetChart();
  document.getElementById('log').textContent = '';
  setTrainUi(true, 'starting…');
  try {
    const r = await fetch('/train', { method: 'POST' });
    let body = {};
    try { body = await r.json(); } catch (_) { body = {}; }
    if (!r.ok || body.ok === false) {
      appendLog('ERROR: ' + (body.error || ('HTTP ' + r.status)));
      setTrainUi(false, 'error');
      return;
    }
    appendLog('started pid=' + body.pid + ' · ' + (body.label || 'fast re-run'));
  } catch (e) {
    appendLog('ERROR: ' + e);
    setTrainUi(false, 'error');
    return;
  }
  if (es) { es.close(); es = null; }
  es = new EventSource('/train/stream');
  es.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (_) { return; }
    if (msg.type === 'line' && msg.text) appendLog(msg.text);
    if (msg.type === 'train_baselines' && typeof msg.hold_baseline_rmse === 'number') {
      holdBaselineRmse = msg.hold_baseline_rmse;
    }
    if (msg.type === 'objective_switch') {
      switchEpoch = msg.at_epoch;
      appendLog('OBJECTIVE SWITCH ' + (msg.label || 'MSE → NLL') + ' at epoch ' + msg.at_epoch);
    }
    if (msg.type === 'epoch') {
      appendEpoch(msg);
      const obj = msg.objective || msg.mode || '?';
      const held = (msg.held_rmse != null) ? msg.held_rmse : msg.rmse;
      setTrainUi(true, 'epoch ' + msg.epoch + '/' + msg.epochs + ' · ' + obj +
        (held != null ? (' · held RMSE ' + Number(held).toFixed(3)) : ''));
    }
    if (msg.type === 'rmse') {
      appendLog('quick RMSE model=' + msg.model_rmse + ' hold=' + msg.hold_rmse + ' (' + msg.seconds + 's)');
    }
    if (msg.type === 'done') {
      if (msg.returncode !== 0) {
        appendLog('ERROR: training subprocess exited with code ' + msg.returncode + ' (no invented loss curve)');
      }
      setTrainUi(false, msg.returncode === 0 ? 'done · fast re-run' : 'failed rc=' + msg.returncode);
      es.close(); es = null;
      refreshFigures();
      loadMetrics();
    }
    if (msg.type === 'error') {
      appendLog('ERROR: ' + msg.error);
      setTrainUi(false, 'error');
      es.close(); es = null;
    }
  };
  es.onerror = () => {
    /* browser may reconnect; do not invent chart points */
  };
}

document.getElementById('trainBtn').addEventListener('click', startTrain);

async function loadMetrics() {
  try {
    const r = await fetch('/metrics');
    const data = await r.json();
    const tb = document.getElementById('ledgerBody');
    tb.innerHTML = '';
    if (data.report_error) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="3" style="color:#ff8a80">' +
        escapeHtml(data.report_error) + '</td>';
      tb.appendChild(tr);
      document.getElementById('ledgerNote').textContent = data.honesty || '';
      return;
    }
    for (const row of (data.ledger || [])) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td>' + escapeHtml(row.component) +
        (row.note ? '<div style="color:var(--mute);font-size:11px;margin-top:4px">' + escapeHtml(row.note) + '</div>' : '') +
        '</td><td class="value">' + escapeHtml(row.display) +
        '</td><td class="source">' + escapeHtml(row.source) + '</td>';
      tb.appendChild(tr);
    }
    document.getElementById('ledgerNote').textContent = data.honesty || '';
  } catch (e) {
    document.getElementById('ledgerBody').innerHTML =
      '<tr><td colspan="3" style="color:#ff8a80">Failed to load /metrics: ' +
      escapeHtml(String(e)) + '</td></tr>';
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

async function refreshFigures() {
  const box = document.getElementById('figures');
  const parts = [];
  for (const name of FIGURE_NAMES) {
    const url = '/figures/' + name + '?t=' + Date.now();
    try {
      const r = await fetch(url, { method: 'HEAD' });
      if (!r.ok) continue;
      parts.push(
        '<figure><img src="' + url + '" alt="' + name + '"/>' +
        '<figcaption>' + name + '</figcaption></figure>'
      );
    } catch (_) { /* skip */ }
  }
  box.innerHTML = parts.length
    ? parts.join('')
    : '<div class="empty-fig">No figures yet — press Train (writes figures/ via lab.demo).</div>';
}

initMap();
initChart();
loadMetrics();
refreshFigures();
} // end boot

window.__coastBoot = boot;
// Prefer waiting briefly for CDN; always boot by 1.5s so offline is useful.
setTimeout(function () {
  if (!window.__coastBooted) {
    window.__coastBooted = true;
    boot();
  }
}, 1500);
document.addEventListener('DOMContentLoaded', function () {
  // If both CDNs already resolved (cached), boot early via __coastMaybeBoot.
  __coastMaybeBoot();
});
})();
</script>
</body>
</html>
"""


def _broadcast(event: dict[str, Any]) -> None:
    with _train_lock:
        _train_history.append(event)
        if len(_train_history) > 2000:
            del _train_history[:500]
        dead: list[queue.Queue[dict[str, Any] | None]] = []
        for q in _train_subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            try:
                _train_subscribers.remove(q)
            except ValueError:
                pass


def _parse_train_line(line: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [{"type": "line", "text": line.rstrip("\n")}]
    marker = "COAST_EVENT "
    idx = line.find(marker)
    if idx >= 0:
        try:
            ev = json.loads(line[idx + len(marker) :])
            if isinstance(ev, dict) and ev.get("type") == "epoch":
                with _train_lock:
                    _train_status["epochs"].append(ev)
                    _train_status["last_line"] = line.rstrip("\n")
                events.append(ev)
                return events
            if isinstance(ev, dict):
                events.append(ev)
                return events
        except json.JSONDecodeError:
            pass
    m = _EPOCH_RE.search(line)
    if m:
        epoch_ev = {
            "type": "epoch",
            "epoch": int(m.group(1)),
            "epochs": int(m.group(2)),
            "loss": float(m.group(3)),
            "rmse": float(m.group(4)) if m.group(4) is not None else None,
            "mode": m.group(5),
            "elapsed_s": float(m.group(6)),
            "source": "lab.demo stdout",
        }
        events.append(epoch_ev)
        with _train_lock:
            _train_status["epochs"].append(epoch_ev)
            _train_status["last_line"] = line.rstrip("\n")
        return events
    m2 = _RMSE_RE.search(line)
    if m2:
        events.append(
            {
                "type": "rmse",
                "model_rmse": float(m2.group(1)),
                "hold_rmse": float(m2.group(2)),
                "seconds": float(m2.group(3)),
                "source": "lab.demo stdout",
            }
        )
    with _train_lock:
        _train_status["last_line"] = line.rstrip("\n")
    return events


def _reader_thread(proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            for ev in _parse_train_line(line):
                _broadcast(ev)
    finally:
        rc = proc.wait()
        with _train_lock:
            global _train_proc
            _train_status["running"] = False
            _train_status["finished_at"] = time.time()
            _train_status["returncode"] = rc
            _train_status["mode"] = "done" if rc == 0 else "failed"
            _train_proc = None
        done = {
            "type": "done",
            "returncode": rc,
            "figures": _list_figures(),
            "label": _train_status["label"],
        }
        _broadcast(done)
        _broadcast_end()


def _broadcast_end() -> None:
    """Wake SSE clients so they can close after done."""
    with _train_lock:
        for q in list(_train_subscribers):
            try:
                q.put_nowait(None)
            except queue.Full:
                pass


def _clear_demo_output() -> dict[str, Any]:
    with _train_lock:
        if _train_proc is not None and _train_proc.poll() is None:
            return {"ok": False, "error": "training still running", "deleted": []}
    deleted: list[str] = []
    if not FIGURES.is_dir():
        return {"ok": True, "deleted": deleted}
    for p in FIGURES.iterdir():
        if p.name == "_reference" or p.is_dir():
            continue
        if p.suffix.lower() == ".png" or p.name == "demo_run.json":
            p.unlink()
            deleted.append(p.name)
    return {"ok": True, "deleted": deleted}


def _list_figures() -> list[str]:
    if not FIGURES.is_dir():
        return []
    names = []
    for n in ("drift_comparison.png", "cdf_error.png", "trajectory_overlay.png"):
        if (FIGURES / n).is_file():
            names.append(n)
    return names


def _start_train() -> dict[str, Any]:
    with _train_lock:
        global _train_proc
        if _train_proc is not None and _train_proc.poll() is None:
            return {"ok": False, "error": "training already running", "pid": _train_proc.pid}
        _train_history.clear()
        _train_status.update(
            {
                "running": True,
                "started_at": time.time(),
                "finished_at": None,
                "returncode": None,
                "mode": "quick",
                "label": (
                    "fast re-run (python -m lab.demo) - "
                    "full 2.02x lower median position error cites lab/stress/results/mapfilter/summary.md"
                ),
                "epochs": [],
                "last_line": None,
                "error": None,
            }
        )
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "lab.demo"],
                cwd=str(REPO),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            _train_status["running"] = False
            _train_status["error"] = str(exc)
            _train_status["mode"] = "error"
            return {"ok": False, "error": str(exc)}
        _train_proc = proc
        _train_status["pid"] = proc.pid
        threading.Thread(target=_reader_thread, args=(proc,), daemon=True).start()
        return {
            "ok": True,
            "pid": proc.pid,
            "cmd": [sys.executable, "-m", "lab.demo"],
            "label": _train_status["label"],
            "mode": "quick",
            "note": (
                "This is a fast re-run of the training path. "
                "Headline 2.02× lower median position error cites committed "
                "mapfilter results, not this short session."
            ),
        }


def _best_isro_arm_pct(isro_report: dict[str, Any], arm: str) -> int:
    rates = [
        float(v["pass_rate"])
        for k, v in isro_report["summary"].items()
        if k.startswith(f"{arm}/")
    ]
    if not rates:
        raise KeyError(f"no {arm} rows")
    return int(round(max(rates) * 100))


def _load_metrics() -> dict[str, Any]:
    """Baseline ledger from committed measured files only — no invented rows."""
    report_err: str | None = None
    ledger: list[dict[str, Any]] = []

    try:
        report = json.loads(_MAPFILTER_REPORT.read_text(encoding="utf-8"))
        junc = report["scenarios"]["junctions"]
        free_err = float(junc["free_median_error_m"])
        coast_err = float(junc["pf_median_error_m"])
        free_drift = float(junc["free_median_drift_pct"])
        coast_drift = float(junc["pf_median_drift_pct"])
        improvement_x = float(junc["improvement_x"])
        free_pass = int(junc["free_pass"])
        pf_pass = int(junc["pf_pass"])
        n_outages = int(junc["n"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        report_err = (
            "Could not read lab/stress/results/mapfilter/report.json — "
            "no measured numbers to show."
        )
        return {
            "ledger": [],
            "story": "",
            "honesty": (
                "Browser Train = python -m lab.demo (quick AVNet + figure regen). "
                "Measured ledger requires lab/stress/results/mapfilter/report.json."
            ),
            "sources": {
                "mapfilter": _MAPFILTER_SUMMARY,
                "heading_ablation": _HEADING_SUMMARY,
                "isro": _ISRO_SUMMARY,
                "speed_bakeoff": _SPEED_SUMMARY,
            },
            "figures": _list_figures(),
            "report_error": report_err,
            "research_ref": "cursor_induction_v2/RESEARCH_2025.md §C",
        }

    # Perfect gyro: F_oracle from heading_ablation/report.json
    try:
        heading = json.loads(_HEADING_REPORT.read_text(encoding="utf-8"))
        oracle = heading["aggregate"]["F_oracle"]
        oracle_pass = int(oracle["pass_isro"])
        oracle_n = int(oracle["n_rows"])
        oracle_fail_pct = round(100.0 * (1.0 - oracle_pass / oracle_n))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        oracle_pass = oracle_n = oracle_fail_pct = None
        heading_err = str(exc)
    else:
        heading_err = None

    # ISRO free-DR arms from isro_benchmark/report.json
    try:
        isro = json.loads(_ISRO_REPORT.read_text(encoding="utf-8"))
        short_pct = _best_isro_arm_pct(isro, "ARM_SHORT")
        tunnel_pct = _best_isro_arm_pct(isro, "ARM_TUNNEL")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        short_pct = tunnel_pct = None
        isro_err = str(exc)
    else:
        isro_err = None

    ledger = [
        {
            "component": "Free DR (junctions / open road)",
            "metric": "median position error",
            "value": free_err,
            "display": f"{free_err:.2f} m",
            "source": _MAPFILTER_SUMMARY,
            "note": f"Measured on {n_outages} outages; CAN ground truth.",
        },
        {
            "component": "+ Map-in-loop particle filter (COAST)",
            "metric": "median position error",
            "value": coast_err,
            "display": (
                f"{coast_err:.2f} m  ({improvement_x:.2f}× lower median position error)"
            ),
            "source": _MAPFILTER_SUMMARY,
            "note": (
                f"Pass {free_pass}->{pf_pass} of {n_outages}. "
                "Full committed run - not the browser fast re-run. "
                "2.02× is median position error, not drift %."
            ),
        },
        {
            "component": "Free DR → COAST (junctions)",
            "metric": "median drift %",
            "value": coast_drift,
            "display": f"{free_drift:.2f}% → {coast_drift:.2f}%",
            "source": _MAPFILTER_SUMMARY,
            "note": (
                "Drift % is a separate quantity from the 2.02× position-error ratio. "
                "No multiplier on this row."
            ),
        },
    ]

    if oracle_fail_pct is not None and oracle_pass is not None and oracle_n is not None:
        ledger.append(
            {
                "component": "Perfect gyro still fails (heading ceiling)",
                "metric": "fail rate @ 60 s (oracle yaw)",
                "value": oracle_fail_pct,
                "display": f"{oracle_fail_pct}% fail ({oracle_pass}/{oracle_n} pass)",
                "source": _HEADING_SUMMARY,
                "note": "Config F_oracle = CAN yaw rate. Why map must sit inside the loop.",
            }
        )
    elif heading_err:
        ledger.append(
            {
                "component": "Perfect gyro still fails (heading ceiling)",
                "metric": "fail rate @ 60 s (oracle yaw)",
                "value": None,
                "display": "unavailable",
                "source": _HEADING_SUMMARY,
                "note": f"Could not read heading_ablation/report.json: {heading_err}",
            }
        )

    if short_pct is not None:
        ledger.append(
            {
                "component": "ISRO free-DR short arm",
                "metric": "pass rate",
                "value": short_pct,
                "display": f"{short_pct}%",
                "source": _ISRO_SUMMARY,
                "note": "Best free-DR method on ARM_SHORT (from isro_benchmark/report.json).",
            }
        )
    if tunnel_pct is not None:
        ledger.append(
            {
                "component": "ISRO free-DR tunnel arm / ISRO bar",
                "metric": "pass rate / drift bar",
                "value": tunnel_pct,
                "display": f"{tunnel_pct}%",
                "source": _ISRO_SUMMARY,
                "note": (
                    "Best free-DR method on ARM_TUNNEL; problem statement drift bar is 10%."
                    + (f" ({isro_err})" if isro_err else "")
                ),
            }
        )
    elif isro_err:
        ledger.append(
            {
                "component": "ISRO free-DR arms",
                "metric": "pass rate",
                "value": None,
                "display": "unavailable",
                "source": _ISRO_SUMMARY,
                "note": f"Could not read isro_benchmark/report.json: {isro_err}",
            }
        )

    return {
        "ledger": ledger,
        "story": (
            f"{improvement_x:.2f}× lower median position error "
            f"({free_err:.2f} m → {coast_err:.2f} m); "
            f"median drift {free_drift:.2f}% → {coast_drift:.2f}%; "
            f"perfect gyro fails ~55%; ISRO free-DR arms "
            f"{short_pct if short_pct is not None else '?'}%/"
            f"{tunnel_pct if tunnel_pct is not None else '?'}%"
        ),
        "honesty": (
            "Browser Train = python -m lab.demo (quick AVNet + figure regen). "
            "It does not re-score the full map-in-loop stress suite. "
            "Cite 2.02× lower median position error / drift 27.6%→16.8% from "
            f"{_MAPFILTER_SUMMARY}; 55% from {_HEADING_SUMMARY}; "
            f"17%/10% arms from {_ISRO_SUMMARY}."
        ),
        "sources": {
            "mapfilter": _MAPFILTER_SUMMARY,
            "heading_ablation": _HEADING_SUMMARY,
            "isro": _ISRO_SUMMARY,
            "speed_bakeoff": _SPEED_SUMMARY,
        },
        "figures": _list_figures(),
        "report_error": report_err,
        "research_ref": "cursor_induction_v2/RESEARCH_2025.md §C",
    }


def _lan_candidates() -> list[dict[str, str]]:
    """Private IPv4 addresses this laptop is actually listening on.

    Guest Wi-Fi AP isolation is why phone→laptop pairing dies silently.
    Windows Mobile Hotspot (192.168.137.1) is the most reliable venue path.
    """
    import socket

    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    virtual = ("192.168.56.", "192.168.19.", "172.29.", "172.23.", "198.18.")

    def hint(ip: str) -> str:
        if ip == "192.168.137.1" or ip.startswith("192.168.137."):
            return "Windows hotspot"
        if ip.startswith("192.168.43.") or ip.startswith("192.168.49."):
            return "phone USB tethering"
        if ip.startswith("10.42."):
            return "Linux hotspot"
        if any(ip.startswith(p) for p in virtual):
            return "VM / WSL — skip"
        if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return "LAN"
        return ""

    def rank(ip: str) -> tuple[int, str]:
        if ip == "127.0.0.1":
            return (90, ip)
        if ip == "192.168.137.1":
            return (0, ip)
        if ip.startswith("192.168.137."):
            return (1, ip)
        if any(ip.startswith(p) for p in virtual):
            return (80, ip)
        if ip.startswith("192.168.43.") or ip.startswith("192.168.49."):
            return (2, ip)
        if ip.startswith("10.42."):
            return (3, ip)
        if ip.startswith("192.168."):
            return (10, ip)
        if ip.startswith("10."):
            return (20, ip)
        if ip.startswith("172."):
            return (30, ip)
        return (70, ip)

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for ip in sorted(set(ips), key=rank):
        if ip in seen or ip.startswith("127."):
            continue
        seen.add(ip)
        out.append({"ip": ip, "url": f"http://{ip}:{PORT}", "hint": hint(ip)})
    if not out:
        out.append({"ip": "127.0.0.1", "url": f"http://127.0.0.1:{PORT}", "hint": "this laptop only"})
    return out


def _lan_base(preferred_host: str | None = None) -> str:
    """The address a phone on the same network should POST to.

    Override with COAST_LAN_BASE when running the laptop as a hotspot -- Windows
    Mobile Hotspot always puts the host at 192.168.137.1, which is a fixed,
    printable address and is immune to the AP isolation that guest wifi applies.
    """
    override = os.environ.get("COAST_LAN_BASE")
    if override and not preferred_host:
        return override.rstrip("/")
    cands = _lan_candidates()
    if preferred_host:
        host = preferred_host.strip().split("/")[0].split(":")[0]
        for c in cands:
            if c["ip"] == host:
                return c["url"]
    return cands[0]["url"]


_ENG_HEAD = re.compile(r"^###\s+([A-Z])\s+[-—]+\s+(.+?)\s*$", re.MULTILINE)
_ENG_ROW = re.compile(r"\|\s*Sustained throughput\s*\|([^\n]+)")
_ENG_HZ = re.compile(r"([\d,]+)\s*Hz")


def _engine_report() -> dict[str, Any]:
    """Measured C++ edge-engine throughput, read from the engine's own README.

    The README reports a range per configuration rather than one number, which
    is the honest way to report it -- so the console shows the spread and leads
    with the worst case.
    """
    try:
        text = EDGE_README.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"Could not read {EDGE_README.name}: {exc}"}

    heads = list(_ENG_HEAD.finditer(text))
    scenarios: list[dict[str, Any]] = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[h.start() : end]
        row = _ENG_ROW.search(block)
        if not row:
            continue
        rates = [float(m.group(1).replace(",", "")) for m in _ENG_HZ.finditer(row.group(1))]
        if not rates:
            continue
        title = h.group(2).strip()
        note = ""
        for line in block.splitlines():
            s = line.strip()
            if s.startswith("**") and "requirement" in s:
                note = s.strip("*").strip()
                break
        scenarios.append(
            {
                "id": h.group(1),
                "name": title,
                "min_hz": min(rates),
                "max_hz": max(rates),
                "note": note,
                "worst": False,
            }
        )
    if not scenarios:
        return {"error": "No 'Sustained throughput' rows found in the edge README."}

    worst = min(scenarios, key=lambda s: s["min_hz"])
    worst["worst"] = True
    machine = ""
    for line in text.splitlines():
        if line.startswith("**Machine:**"):
            machine = line.replace("**Machine:**", "").strip()
            break
    return {
        "machine": machine,
        "scenarios": scenarios,
        "worst_hz": worst["min_hz"],
        "worst_multiple": int(worst["min_hz"] / 200.0),
        "source": "core/cpp/apps/README.md",
    }


def _claims_payload() -> dict[str, Any]:
    """Load CLAIMS.json and project front-door headlines.

    Raises on read/parse/schema failure — the handler maps that to HTTP 500.
    Never invents headline numbers.
    """
    text = CLAIMS_JSON.read_text(encoding="utf-8")
    data = json.loads(text)
    claims = data.get("claims")
    if not isinstance(claims, list):
        raise ValueError("CLAIMS.json has no claims list")
    by_id: dict[str, Any] = {}
    for row in claims:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            by_id[row["id"]] = row
    missing = [cid for cid in _HEADLINE_CLAIM_IDS if cid not in by_id]
    if missing:
        raise KeyError(
            "CLAIMS.json missing headline claim id(s): " + ", ".join(missing)
        )
    headlines = {cid: by_id[cid] for cid in _HEADLINE_CLAIM_IDS}
    return {
        "claims": claims,
        "headlines": headlines,
        "source": "win_tuning/CLAIMS.json",
    }


def _static_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        if guessed.startswith("text/") and "charset" not in guessed:
            return guessed + "; charset=utf-8"
        return guessed
    ext = path.suffix.lower()
    return {
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8",
        ".map": "application/json; charset=utf-8",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
    }.get(ext, "application/octet-stream")


def _resolve_trace_file(name: str) -> Path | None:
    """Resolve a single basename under TRACES_DIR. ``latest.json`` picks newest.

    Prefer a non-SYNTHETIC* file for latest when both exist. Rejects path
    traversal via ``safe_join``. Returns None when missing/unsafe.
    """
    if name == "latest.json":
        if not TRACES_DIR.is_dir():
            return None
        files = [p for p in TRACES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
        if not files:
            return None
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        real = [p for p in files if not p.name.upper().startswith("SYNTHETIC")]
        return (real or files)[0]
    fp = safe_join(TRACES_DIR, name)
    if fp is None or not fp.is_file() or fp.suffix.lower() != ".json":
        return None
    return fp


def _list_traces() -> list[dict[str, Any]]:
    """Basename listing for the replay player."""
    if not TRACES_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(TRACES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        out.append(
            {
                "name": p.name,
                "bytes": p.stat().st_size,
                "mtime": int(p.stat().st_mtime),
            }
        )
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "COASTConsole/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _client_key(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def _cors(self) -> None:
        # Open CORS is required for phone pairing from a different origin on LAN;
        # keep it off session/cookie auth if that is added later (see threat model).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob: https:; "
            "style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https:; "
            "connect-src 'self'; frame-ancestors 'none'",
        )

    def _json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _reject(self, code: int, message: str) -> None:
        self._json(code, {"ok": False, "error": message})

    def _read_json_body(self, *, require_body: bool = True) -> dict[str, Any] | None:
        """Parse a capped JSON object body. Sends an error response and returns None on failure."""
        length, err = parse_content_length(self.headers, max_bytes=MAX_BODY_BYTES)
        if err:
            self._reject(413 if "too large" in err else 400, err)
            return None
        assert length is not None
        if require_body and length <= 0:
            self._reject(400, "empty body")
            return None
        ct_err = require_json_content_type(self.headers)
        if ct_err and length > 0:
            self._reject(415, ct_err)
            return None
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {} if not require_body else None
        try:
            frame = json.loads(raw.decode("utf-8"))
            if not isinstance(frame, dict):
                raise ValueError("expected object")
        except Exception:
            self._reject(400, "invalid json")
            return None
        return frame

    def _operator_ok(self) -> bool:
        """True when the console is open or the request carries a live session."""
        if _auth is None:
            return True
        if _auth.is_open_mode():
            return True
        cookie = _auth.parse_session_cookie(self.headers.get("Cookie"))
        return _auth.validate_session(cookie)

    def _require_operator(self) -> bool:
        """401 JSON when locked and the cookie is missing/expired."""
        if self._operator_ok():
            return True
        self._json(401, {"ok": False, "error": "operator sign-in required"})
        return False

    def _session_payload(self) -> dict[str, Any]:
        if _auth is None:
            return {"open_mode": True, "authenticated": True, "auth_available": False}
        open_mode = _auth.is_open_mode()
        cookie = _auth.parse_session_cookie(self.headers.get("Cookie"))
        authed = open_mode or _auth.validate_session(cookie)
        return {
            "open_mode": open_mode,
            "authenticated": authed,
            "auth_available": True,
        }

    def _redirect(self, location: str, code: int = 302) -> None:
        self.send_response(code)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self._security_headers()
        self.end_headers()

    def _serve_html(self, html: str, head_only: bool) -> None:
        _reload_ui()
        body = _with_asset_versions(html).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _deny_html(self) -> None:
        body = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            "<title>COAST · sign in</title>"
            "<link rel='stylesheet' href='/static/tokens.css'/>"
            "</head><body style='font-family:system-ui;padding:2rem'>"
            "<h1>Operator sign-in required</h1>"
            "<p>POST /api/login with a passcode JSON body.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str, head_only: bool) -> None:
        rel = unquote(path[len("/static/") :])
        # Allow one nested segment (e.g. tokens.css) via safe_join basename only,
        # or join path parts that contain no traversal.
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        if not parts:
            self.send_error(404, "not found")
            return
        fp = safe_join(STATIC_DIR, *parts)
        if fp is None or not fp.is_file():
            self.send_error(404, "not found")
            return
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _static_content_type(fp))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _serve_docs(self, head_only: bool) -> None:
        """Serve site/index.html at /docs with a rewritten stylesheet path."""
        docs_root = Path(__file__).resolve().parents[1] / "site"
        fp = docs_root / "index.html"
        if not fp.is_file():
            self.send_error(404, "docs page not found")
            return
        html = fp.read_text(encoding="utf-8")
        # The site's index.html links styles.css as a sibling — rewrite it so
        # the /docs URL scope resolves to /docs/styles.css.
        html = html.replace(
            'href="styles.css"',
            'href="/docs/styles.css"',
        )
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _serve_docs_asset(self, name: str, head_only: bool) -> None:
        """Serve an asset from site/ (styles.css, images, etc.)."""
        docs_root = Path(__file__).resolve().parents[1] / "site"
        fp = safe_join(docs_root, name)
        if fp is None or not fp.is_file():
            self.send_error(404, "not found")
            return
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _static_content_type(fp))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _handle_login(self) -> None:
        key = self._client_key()
        if not _LOGIN_LIMITER.allow(key):
            sys.stderr.write(f"rate limit: login from {key}\n")
            self._reject(429, "rate limit exceeded")
            return
        if _auth is None:
            self._json(503, {"ok": False, "error": "auth unavailable"})
            return
        if _auth.is_open_mode():
            self._json(200, {"ok": True, "open_mode": True, "message": "no passcode configured"})
            return
        if not _auth.check_rate_limit(key):
            sys.stderr.write(f"rate limit: auth module login from {key}\n")
            self._reject(429, "rate limit exceeded")
            return
        frame = self._read_json_body(require_body=True)
        if frame is None:
            return
        pw = frame.get("passcode") or frame.get("password") or ""
        if not isinstance(pw, str) or not _auth.verify_passcode(pw):
            self._json(401, {"ok": False, "error": "invalid passcode"})
            return
        token = _auth.create_session()
        body = json.dumps({"ok": True, "authenticated": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Set-Cookie", _auth.session_cookie_header(token))
        self._cors()
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _handle_logout(self) -> None:
        if _auth is not None:
            cookie = _auth.parse_session_cookie(self.headers.get("Cookie"))
            _auth.clear_session(cookie)
        body = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if _auth is not None:
            self.send_header("Set-Cookie", _auth.session_cookie_header("", clear=True))
        self._cors()
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle_get(head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        self._handle_get(head_only=False)

    def _handle_get(self, head_only: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/static/"):
            self._serve_static(path, head_only)
            return

        if path == "/docs" or path == "/docs/":
            # The public model release page (site/index.html). Served here so
            # the console front-door's "See docs" button works even when the
            # site is not proxied separately.
            self._serve_docs(head_only)
            return

        if path == "/docs/styles.css":
            self._serve_docs_asset("styles.css", head_only)
            return

        if path == "/api/health":
            # Phone pairing probes this — keep it tiny, ungated, no cookies.
            self._json(200, {"ok": True, "service": "coast"})
            return

        if path == "/api/session":
            self._json(200, self._session_payload())
            return

        if path == "/api/fleet":
            if not self._require_operator():
                return
            self._json(200, FLEET.snapshot())
            return

        if path == "/api/demo/uk":
            if not self._require_operator():
                return
            self._json(200, {"ok": True, **_uk_demo.status(), "track": _uk_demo.load_track().get("meta")})
            return

        if path.startswith("/api/privacy/"):
            if not self._require_operator():
                return
            did = unquote(path[len("/api/privacy/") :])
            rep = FLEET.privacy_report(did)
            if rep is None:
                self._json(404, {"error": "unknown device"})
            else:
                self._json(200, rep)
            return

        if path == "/api/engine/meta":
            try:
                from web.engine_compute import EngineRun

                self._json(200, EngineRun().meta())
            except Exception as exc:  # missing/damaged demo strip
                self._json(500, {"error": f"cannot load demo strip: {exc}"})
            return

        if path == "/api/engine/stream":
            self._sse_engine(parsed)
            return

        if path == "/api/engine":
            self._json(200, _engine_report())
            return

        if path == "/api/claims":
            try:
                self._json(200, _claims_payload())
            except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
                self._json(
                    500,
                    {
                        "error": (
                            "Could not read win_tuning/CLAIMS.json — "
                            f"{exc}. Run `python tools/verify_claims.py --json`."
                        ),
                    },
                )
            return

        if path == "/download/apk":
            self._serve_apk(head_only)
            return

        if path in ("/replay", "/replay/"):
            self._redirect("/static/trace_replay.html")
            return

        if path == "/pair":
            # Scanning the QR with ANY camera app lands here. Ungated — phones
            # must pair without an operator session.
            _reload_ui()
            self._serve_html(PAIR_PAGE, head_only)
            return

        if path in _PROTECTED_HTML:
            # Open mode (default cold-start): always serve. Locked mode without
            # a session: 401 HTML that still loads /static/* for the sign-in UI.
            if not self._operator_ok():
                self._deny_html()
                return
            _reload_ui()
            self._serve_html(CONSOLE_PAGE, head_only)
            return

        if path == "/feed":
            with _lock:
                payload = {
                    "t": int(time.time() * 1000),
                    "latest": _latest,
                    "trail": list(_trail),
                }
            self._json(200, payload)
            return

        if path == "/metrics":
            self._json(200, _load_metrics())
            return

        if path == "/train/status":
            if not self._require_operator():
                return
            with _train_lock:
                snap = dict(_train_status)
                snap["epochs"] = list(_train_status["epochs"])
            self._json(200, snap)
            return

        if path == "/train/stream":
            if not self._require_operator():
                return
            if head_only:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self._cors()
                self.end_headers()
                return
            self._sse_train()
            return

        if path.startswith("/figures/"):
            name = unquote(path[len("/figures/") :])
            fp = safe_join(FIGURES, name)
            if fp is None:
                self.send_error(400, "bad name")
                return
            if not fp.is_file() or fp.suffix.lower() not in FIGURE_SUFFIXES:
                self.send_error(404, "not found")
                return
            data = fp.read_bytes()
            ctype = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".json": "application/json",
            }[fp.suffix.lower()]
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self._security_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
            return

        if path in ("/api/traces", "/api/traces/"):
            self._json(200, {"ok": True, "traces": _list_traces()})
            return

        if path.startswith(_API_TRACE_PREFIX) or path.startswith(_TRACE_URL_PREFIX):
            prefix = (
                _API_TRACE_PREFIX
                if path.startswith(_API_TRACE_PREFIX)
                else _TRACE_URL_PREFIX
            )
            name = unquote(path[len(prefix) :])
            if not name:
                self._json(200, {"ok": True, "traces": _list_traces()})
                return
            fp = _resolve_trace_file(name)
            if fp is None:
                # Distinguish traversal (slashes / ..) from missing file.
                if not name or "/" in name or "\\" in name or ".." in name:
                    self.send_error(400, "bad name")
                else:
                    self.send_error(404, "not found")
                return
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self._security_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
            return

        self.send_error(404, "not found")

    def _sse_engine(self, parsed) -> None:
        """Stream the estimator's arithmetic over the real UK demo strip.

        Every field is computed in web/engine_compute.py from the committed
        IO-VNBD recording. If the strip cannot be read the stream says so and
        ends -- it never falls back to synthetic samples.
        """
        from urllib.parse import parse_qs

        q = parse_qs(parsed.query or "")
        try:
            rate = float(q.get("rate", ["4"])[0])
        except ValueError:
            rate = 4.0
        rate = max(0.25, min(20.0, rate))

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()

        def emit(obj: dict) -> bool:
            try:
                self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                return False

        try:
            from web.engine_compute import EngineRun

            run = EngineRun()
        except Exception as exc:
            emit({"type": "error", "error": f"cannot load demo strip: {exc}"})
            return

        if not emit({"type": "meta", **run.meta()}):
            return

        period = 1.0 / (10.0 * rate)  # source is 10 Hz; rate multiplies playback
        while True:
            step = run.step()
            if step is None:
                emit({"type": "done", "samples": run.samples})
                return
            step["type"] = "step"
            if not emit(step):
                return
            time.sleep(period)

    def _sse_train(self) -> None:
        q: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=500)
        with _train_lock:
            # Replay recent history so late subscribers still see epochs.
            for ev in _train_history[-200:]:
                try:
                    q.put_nowait(ev)
                except queue.Full:
                    break
            _train_subscribers.append(q)
            running = _train_status["running"]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        hello = {
            "type": "hello",
            "running": running,
            "label": _train_status["label"],
        }
        try:
            self.wfile.write(f"data: {json.dumps(hello)}\n\n".encode("utf-8"))
            self.wfile.flush()
            while True:
                try:
                    item = q.get(timeout=15.0)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    break
                self.wfile.write(f"data: {json.dumps(item)}\n\n".encode("utf-8"))
                self.wfile.flush()
                if item.get("type") in ("done", "error"):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _train_lock:
                try:
                    _train_subscribers.remove(q)
                except ValueError:
                    pass

    def _serve_apk(self, head_only: bool) -> None:
        """Hand the judge the installable build.

        Prefers a release standard-flavour APK, then anything else found, so the
        link works whether or not a signed release has been produced yet.
        """
        roots = [REPO / "android" / "dist", REPO / "android" / "app" / "build" / "outputs" / "apk"]
        found: list[Path] = []
        for root in roots:
            if root.is_dir():
                found.extend(sorted(root.rglob("*.apk")))
        if not found:
            self._json(
                404,
                {
                    "error": "No APK built yet.",
                    "hint": "cd android && gradlew assembleStandardRelease",
                },
            )
            return

        def rank(p: Path) -> tuple[int, float]:
            n = p.name.lower()
            score = 0
            if "release" in n:
                score -= 2
            if "standard" in n:
                score -= 1
            return (score, -p.stat().st_mtime)

        apk = sorted(found, key=rank)[0]
        if not assert_path_in_roots(apk, roots):
            self._json(500, {"error": "APK path rejected"})
            return
        size = apk.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.android.package-archive")
        self.send_header("Content-Disposition", f'attachment; filename="{apk.name}"')
        self.send_header("Content-Length", str(size))
        self._cors()
        self._security_headers()
        self.end_headers()
        if head_only:
            return
        with apk.open("rb") as f:
            while chunk := f.read(262_144):
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        # Cap Content-Length on every POST before routing.
        _length, len_err = parse_content_length(self.headers, max_bytes=MAX_BODY_BYTES)
        if len_err:
            self._reject(413 if "too large" in len_err else 400, len_err)
            return

        if path == "/api/login":
            self._handle_login()
            return

        if path == "/api/logout":
            self._handle_logout()
            return

        if path in _OPERATOR_POST or path.startswith("/api/forget/"):
            if not self._require_operator():
                return

        if path in ("/train", "/train/start"):
            result = _start_train()
            self._json(200 if result.get("ok") else 409, result)
            return

        if path in ("/api/demo/uk", "/api/demo/uk/start"):
            try:
                result = _uk_demo.start_demo(FLEET)
            except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self._json(200 if result.get("ok") else 409, result)
            return

        if path == "/api/demo/uk/stop":
            self._json(200, _uk_demo.stop_demo(FLEET))
            return

        if path == "/api/pair/new":
            key = self._client_key()
            if not _PAIR_LIMITER.allow(key):
                sys.stderr.write(f"rate limit: pair/new from {key}\n")
                self._reject(429, "rate limit exceeded")
                return
            parsed = urlparse(self.path)
            host = (parse_qs(parsed.query).get("host") or [None])[0]
            s = FLEET.new_session()
            lan = _lan_base(host)
            relay = configured_relay_base()
            self._json(200, _pair_response(s, lan, relay))
            return

        if path == "/api/pair/open":
            key = self._client_key()
            if not _PAIR_LIMITER.allow(key):
                sys.stderr.write(f"rate limit: pair/open from {key}\n")
                self._reject(429, "rate limit exceeded")
                return
            frame = self._read_json_body(require_body=False) or {}
            token = frame.get("token")
            if token is not None and str(token).strip() == "":
                token = None
            try:
                s = FLEET.open_session(token if isinstance(token, str) else None)
            except ValueError as exc:
                self._reject(400, str(exc))
                return
            parsed = urlparse(self.path)
            host = (parse_qs(parsed.query).get("host") or [None])[0]
            lan = _lan_base(host)
            relay = configured_relay_base()
            self._json(200, _pair_response(s, lan, relay))
            return

        if path.startswith("/api/forget/"):
            did = unquote(path[len("/api/forget/") :])
            self._json(200, {"ok": FLEET.forget(did)})
            return

        if path == "/api/forget_all":
            self._json(200, {"ok": True, "removed": FLEET.forget_all()})
            return

        if path == "/train/clear":
            self._json(200, _clear_demo_output())
            return

        if path != "/ingest":
            self.send_error(404, "not found")
            return

        # /ingest stays ungated — phones pair without an operator session.
        key = self._client_key()
        if not _INGEST_LIMITER.allow(key):
            sys.stderr.write(f"rate limit: ingest from {key}\n")
            self._reject(429, "rate limit exceeded")
            return

        frame = self._read_json_body(require_body=True)
        if frame is None:
            return
        # A frame carrying a pairing token belongs to the fleet view. Frames
        # without one keep the original single-device tracker behaviour, so an
        # older build still works against this server.
        if frame.get("token"):
            result = FLEET.ingest(frame)
            self._json(200 if result.get("ok") else 400, result)
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
        self._json(200, {"ok": True})


def main(argv: list[str] | None = None) -> int:
    global _jsonl_path
    args = list(sys.argv[1:] if argv is None else argv)
    if "--jsonl" in args:
        i = args.index("--jsonl")
        _jsonl_path = args[i + 1] if i + 1 < len(args) else "tracker_ingest.jsonl"

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    _start_relay_puller()
    relay = configured_relay_base()
    print(
        f"COAST live console on http://{HOST}:{PORT}/  "
        f"(open http://127.0.0.1:{PORT}/)",
        flush=True,
    )
    print(
        "Phone: POST /ingest (LAN)  |  relay pull: "
        f"{relay or 'off'}  |  Train: POST /train -> GET /train/stream (SSE)",
        flush=True,
    )
    print(
        "Train = python -m lab.demo (fast re-run). "
        "Full 2.02x lower median position error cites lab/stress/results/mapfilter/summary.md",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        httpd.server_close()
        with _train_lock:
            if _train_proc is not None and _train_proc.poll() is None:
                _train_proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
