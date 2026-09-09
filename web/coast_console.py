"""
COAST localhost live console (induction Block 3).

One command from the repo root:

    python -m web.coast_console

Open http://127.0.0.1:8787/ — live phone map, Train (real lab.demo epochs),
measured algorithm ledger, and figures/ when training finishes.

Endpoints
---------
GET  /            single dark console page
POST /ingest      phone LAN frames (same contract as tracker_server)
GET  /feed        latest + trail
POST /train       start real ``python -m lab.demo`` subprocess (quick-run)
GET  /train/stream  SSE: real stdout lines + parsed epoch metrics (no fake loss)
GET  /train/status  JSON snapshot of the current / last train run
GET  /metrics     baseline ledger from committed measured summary files
GET  /figures/<name>  serve PNGs under figures/

Stdlib only (http.server + SSE). Bind 0.0.0.0:8787 so a phone on LAN can POST /ingest.
Cold start with no network and no phone must still render a useful page (CDN map/chart
are optional; Train/ledger stay local).
"""

from __future__ import annotations

import json
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
from urllib.parse import unquote, urlparse

HOST = "0.0.0.0"
PORT = 8787
MAX_TRAIL = 400
REPO = Path(__file__).resolve().parents[1]
FIGURES = REPO / "figures"

_MAPFILTER_REPORT = REPO / "lab" / "stress" / "results" / "mapfilter" / "report.json"
_MAPFILTER_SUMMARY = "lab/stress/results/mapfilter/summary.md"
_ISRO_REPORT = REPO / "lab" / "stress" / "results" / "isro_benchmark" / "report.json"
_ISRO_SUMMARY = "lab/stress/results/isro_benchmark/summary.md"
_HEADING_REPORT = REPO / "lab" / "stress" / "results" / "heading_ablation" / "report.json"
_HEADING_SUMMARY = "lab/stress/results/heading_ablation/summary.md"
_SPEED_SUMMARY = "lab/models/results/speed_bakeoff/summary.md"

# lab.demo prints: "epoch 1/4  loss=1.2345  rmse=0.456  (MSE)  2.3s"
_EPOCH_RE = re.compile(
    r"epoch\s+(\d+)\s*/\s*(\d+)\s+loss=([0-9.eE+-]+)(?:\s+rmse=([0-9.eE+-]+))?\s+\((\w+)\)\s+([0-9.]+)s",
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
        Loss curve is real stdout epochs — not simulated. If training fails, the real error is shown; no invented curve.
        Headline <strong>2.02× lower median position error</strong> always cites the full committed mapfilter run, not this fast re-run.
      </p>
      <div class="chart-wrap" id="chartWrap"><canvas id="lossChart"></canvas></div>
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
      center: [77.59, 12.97],
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
    return;
  }
  const canvas = document.getElementById('lossChart');
  if (!canvas) return;
  lossChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'train loss (real)',
        data: [],
        borderColor: IDR,
        backgroundColor: 'rgba(0,224,164,0.12)',
        tension: 0.25,
        pointRadius: 3,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      scales: {
        x: { ticks: { color: '#8A929B' }, grid: { color: 'rgba(255,255,255,0.04)' }, title: { display: true, text: 'epoch', color: '#8A929B' } },
        y: { ticks: { color: '#8A929B' }, grid: { color: 'rgba(255,255,255,0.06)' }, title: { display: true, text: 'loss', color: '#8A929B' } }
      },
      plugins: { legend: { labels: { color: '#E8EDF2' } } }
    }
  });
}

function resetChart() {
  if (!lossChart) return;
  lossChart.data.labels = [];
  lossChart.data.datasets[0].data = [];
  lossChart.update();
}

function appendEpoch(epoch, loss) {
  if (!lossChart) return;
  if (typeof loss !== 'number' || !Number.isFinite(loss)) return;
  lossChart.data.labels.push(String(epoch));
  lossChart.data.datasets[0].data.push(loss);
  lossChart.update();
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
    if (msg.type === 'epoch') {
      appendEpoch(msg.epoch, msg.loss);
      setTrainUi(true, 'epoch ' + msg.epoch + '/' + msg.epochs + ' · real loss');
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


class Handler(BaseHTTPRequestHandler):
    server_version = "COASTConsole/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
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

        if path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
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
            with _train_lock:
                snap = dict(_train_status)
                snap["epochs"] = list(_train_status["epochs"])
            self._json(200, snap)
            return

        if path == "/train/stream":
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
            if "/" in name or "\\" in name or name.startswith(".") or ".." in name:
                self.send_error(400, "bad name")
                return
            fp = FIGURES / name
            if not fp.is_file() or fp.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".json"}:
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
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
            return

        self.send_error(404, "not found")

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
        self.send_header("Cache-Control", "no-cache")
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

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/train":
            result = _start_train()
            self._json(200 if result.get("ok") else 409, result)
            return

        if path == "/train/clear":
            self._json(200, _clear_demo_output())
            return

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
        self._json(200, {"ok": True})


def main(argv: list[str] | None = None) -> int:
    global _jsonl_path
    args = list(sys.argv[1:] if argv is None else argv)
    if "--jsonl" in args:
        i = args.index("--jsonl")
        _jsonl_path = args[i + 1] if i + 1 < len(args) else "tracker_ingest.jsonl"

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"COAST live console on http://{HOST}:{PORT}/  "
        f"(open http://127.0.0.1:{PORT}/)",
        flush=True,
    )
    print(
        "Phone: POST /ingest  |  Train: POST /train -> GET /train/stream (SSE)  |  "
        "Ledger: GET /metrics",
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
