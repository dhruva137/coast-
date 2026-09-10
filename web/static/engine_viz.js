/**
 * COASTEngineViz — canvas particle-filter visualiser (Phase 3 §3.2–3.3).
 *
 * Shows belief on the road graph: particles, edge posterior, estimate,
 * free-DR ghost, and truth. Greyscale-safe via dash patterns, not colour alone.
 *
 * Global API (also returned from mount):
 *   COASTEngineViz.mount(el, opts?) → instance
 *   COASTEngineViz.syntheticTrace(opts?) → trace object
 *   COASTEngineViz.VERSION
 *
 * Instance:
 *   load(source)          // URL string | trace object
 *   play() / pause() / toggle()
 *   seek(tOrFraction)     // seconds, or 0–1 if |x|≤1 and beyond duration
 *   setSpeed(rate)        // 0.25 … 4
 *   step(dir)             // ±1 frame
 *   setLoop(bool)
 *   destroy()
 *   getState()            // { playing, t, i, speed, nEff, … }
 *   on(event, fn) / off(event, fn)
 */
(function (global) {
  "use strict";

  var VERSION = "1.0.0";
  var SPEEDS = [0.25, 0.5, 1, 2, 4];
  var FORK_THRESHOLD = 0.15;
  var FORK_MIN_EDGES = 2;
  var FORK_SLOW = 0.4;
  var FORK_HOLD_MS = 2000;
  var COLLAPSE_MS = 400;
  var DIVERGE_M = 30;
  var R = 6371000;

  function cssVar(el, name, fallback) {
    try {
      var v = getComputedStyle(el).getPropertyValue(name).trim();
      return v || fallback;
    } catch (_) {
      return fallback;
    }
  }

  function clamp(x, a, b) {
    return Math.max(a, Math.min(b, x));
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function haversine(lat1, lon1, lat2, lon2) {
    var φ1 = (lat1 * Math.PI) / 180;
    var φ2 = (lat2 * Math.PI) / 180;
    var dφ = ((lat2 - lat1) * Math.PI) / 180;
    var dλ = ((lon2 - lon1) * Math.PI) / 180;
    var s =
      Math.sin(dφ / 2) * Math.sin(dφ / 2) +
      Math.cos(φ1) * Math.cos(φ2) * Math.sin(dλ / 2) * Math.sin(dλ / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(s)));
  }

  function fmtTime(t) {
    if (!Number.isFinite(t)) return "—";
    var s = Math.max(0, t);
    var m = Math.floor(s / 60);
    var r = s - m * 60;
    return m + ":" + (r < 10 ? "0" : "") + r.toFixed(1);
  }

  function fmtM(m) {
    if (!Number.isFinite(m)) return "—";
    return m < 100 ? m.toFixed(1) + " m" : Math.round(m) + " m";
  }

  /* ── Synthetic offline demo trace ─────────────────────────────────── */

  function syntheticTrace(opts) {
    opts = opts || {};
    var hz = opts.hz || 10;
    var duration = opts.duration_s || 24;
    var nPart = opts.n_particles || 120;
    var nSteps = Math.floor(duration * hz);

    // T-junction graph in local metres → lat/lon around a fixed origin
    var originLat = 52.48;
    var originLon = -1.9;
    function xyToLatLon(x, y) {
      var lat = originLat + y / 111320;
      var lon = originLon + x / (111320 * Math.cos((originLat * Math.PI) / 180));
      return [lat, lon];
    }

    // Nodes: 0 stem-south, 1 junction, 2 left, 3 right, 4 ahead
    var nodesXY = [
      [0, 0],
      [0, 80],
      [-60, 80],
      [70, 80],
      [0, 150],
    ];
    var nodes = nodesXY.map(function (p) {
      return xyToLatLon(p[0], p[1]);
    });

    function edgePts(a, b, n) {
      n = n || 8;
      var out = [];
      for (var i = 0; i <= n; i++) {
        var t = i / n;
        out.push(
          xyToLatLon(
            lerp(nodesXY[a][0], nodesXY[b][0], t),
            lerp(nodesXY[a][1], nodesXY[b][1], t)
          )
        );
      }
      return out;
    }

    var edges = [
      { id: 0, a: 0, b: 1, pts: edgePts(0, 1) },
      { id: 1, a: 1, b: 2, pts: edgePts(1, 2) },
      { id: 2, a: 1, b: 3, pts: edgePts(1, 3) },
      { id: 3, a: 1, b: 4, pts: edgePts(1, 4) },
    ];

    function alongEdge(eid, s) {
      var e = edges[eid];
      var pts = e.pts;
      var u = clamp(s, 0, 1) * (pts.length - 1);
      var i0 = Math.floor(u);
      var i1 = Math.min(pts.length - 1, i0 + 1);
      var f = u - i0;
      return [
        lerp(pts[i0][0], pts[i1][0], f),
        lerp(pts[i0][1], pts[i1][1], f),
      ];
    }

    var steps = [];
    for (var k = 0; k < nSteps; k++) {
      var t = k / hz;
      var progress = t / duration; // 0..1

      // Truth: stem → right branch
      var truthEdge, truthS;
      if (progress < 0.35) {
        truthEdge = 0;
        truthS = progress / 0.35;
      } else {
        truthEdge = 2;
        truthS = (progress - 0.35) / 0.65;
      }
      var truthLL = alongEdge(truthEdge, clamp(truthS, 0, 1));

      // Free DR: follows early then drifts east off-road
      var freeXY;
      if (progress < 0.35) {
        freeXY = [0, 80 * (progress / 0.35)];
      } else {
        var u = (progress - 0.35) / 0.65;
        freeXY = [u * 95 + 8, 80 + u * 12];
      }
      var freeLL = xyToLatLon(freeXY[0], freeXY[1]);

      // Belief multimodality around junction
      var nearJunc = progress > 0.28 && progress < 0.55;
      var post;
      if (progress < 0.3) {
        post = [[0, 0.92], [2, 0.05], [1, 0.03]];
      } else if (progress < 0.42) {
        post = [[0, 0.25], [2, 0.38], [1, 0.28], [3, 0.09]];
      } else if (progress < 0.55) {
        post = [[2, 0.62], [1, 0.22], [3, 0.1], [0, 0.06]];
      } else {
        post = [[2, 0.88], [3, 0.07], [1, 0.05]];
      }

      var nEffBase = nPart * 0.75;
      var nEff = nearJunc
        ? nPart * (0.18 + 0.2 * Math.sin(progress * 40))
        : nEffBase * (0.85 + 0.1 * Math.sin(t));
      nEff = clamp(nEff, 8, nPart);

      var resampled = nearJunc && k % Math.round(hz * 1.2) === 0;

      var particles = [];
      for (var p = 0; p < nPart; p++) {
        var r = (p * 0.6180339887) % 1;
        var eid, s, w;
        if (progress < 0.3) {
          eid = 0;
          s = clamp(truthS + (r - 0.5) * 0.12, 0, 1);
          w = 0.6 + 0.4 * (1 - Math.abs(s - truthS) * 4);
        } else if (progress < 0.55) {
          // fork: left / right / ahead
          if (r < 0.4) {
            eid = 2;
            s = clamp((progress - 0.35) / 0.65 + (r - 0.2) * 0.15, 0, 1);
          } else if (r < 0.7) {
            eid = 1;
            s = clamp((progress - 0.32) / 0.5 + (r - 0.55) * 0.2, 0, 1);
          } else if (r < 0.88) {
            eid = 3;
            s = clamp((progress - 0.34) / 0.55, 0, 1);
          } else {
            eid = 0;
            s = clamp(0.85 + (r - 0.9) * 0.5, 0, 1);
          }
          w = eid === 2 ? 1.2 : eid === 1 ? 0.7 : 0.35;
        } else {
          eid = 2;
          s = clamp(truthS + (r - 0.5) * 0.08, 0, 1);
          w = 0.9 + 0.2 * r;
        }
        var ll = alongEdge(eid, s);
        particles.push({
          e: eid,
          s: s,
          w: w / nPart,
          lat: ll[0],
          lon: ll[1],
        });
      }

      // Estimate = weighted mean
      var sumW = 0,
        lat = 0,
        lon = 0;
      for (var i = 0; i < particles.length; i++) {
        sumW += particles[i].w;
        lat += particles[i].lat * particles[i].w;
        lon += particles[i].lon * particles[i].w;
      }
      if (sumW > 0) {
        lat /= sumW;
        lon /= sumW;
      } else {
        lat = truthLL[0];
        lon = truthLL[1];
      }

      var mode = progress < 0.08 ? "GNSS" : "IDR";
      steps.push({
        t: t,
        particles: particles,
        estimate: { lat: lat, lon: lon, edge: post[0][0], heading: 0 },
        truth: { lat: truthLL[0], lon: truthLL[1] },
        free_dr: { lat: freeLL[0], lon: freeLL[1] },
        speed_mps: 8 + 2 * Math.sin(t * 0.4),
        speed_truth_mps: 9.2,
        yaw_rate: nearJunc ? -0.18 + 0.05 * Math.sin(t * 3) : 0.01 * Math.sin(t),
        n_eff: nEff,
        resampled: resampled,
        edge_posterior: post,
        mode: mode,
      });
    }

    return {
      meta: {
        drive: "SYNTH",
        t0_s: 0,
        duration_s: duration,
        hz: hz,
        n_particles: nPart,
        particles_shown: nPart,
        particles_total: nPart,
        graph: "synthetic",
        source: "inline synthetic T-junction demo",
        built_from_drive_data: false,
        synthetic: true,
      },
      graph: { nodes: nodes, edges: edges },
      steps: steps,
    };
  }

  /* ── Projector ────────────────────────────────────────────────────── */

  function Projector() {
    this.lat0 = 0;
    this.lon0 = 0;
    this.scale = 1;
    this.cx = 0;
    this.cy = 0;
    this.pad = 36;
    this.w = 1;
    this.h = 1;
  }

  Projector.prototype.fit = function (bounds, w, h) {
    this.w = w;
    this.h = h;
    var dLat = Math.max(1e-9, bounds.maxLat - bounds.minLat);
    var dLon = Math.max(1e-9, bounds.maxLon - bounds.minLon);
    this.lat0 = (bounds.minLat + bounds.maxLat) / 2;
    this.lon0 = (bounds.minLon + bounds.maxLon) / 2;
    var cos = Math.cos((this.lat0 * Math.PI) / 180);
    var usableW = w - this.pad * 2;
    var usableH = h - this.pad * 2;
    var sx = usableW / (dLon * cos);
    var sy = usableH / dLat;
    this.scale = Math.min(sx, sy);
    this.cx = w / 2;
    this.cy = h / 2;
  };

  Projector.prototype.project = function (lat, lon) {
    var cos = Math.cos((this.lat0 * Math.PI) / 180);
    var x = this.cx + (lon - this.lon0) * cos * this.scale;
    var y = this.cy - (lat - this.lat0) * this.scale;
    return [x, y];
  };

  /* ── Instance ─────────────────────────────────────────────────────── */

  function createInstance(root, opts) {
    opts = opts || {};
    var listeners = {};
    var trace = null;
    var playing = false;
    var loop = opts.loop !== false;
    var speedIdx = 2; // 1×
    var baseSpeed = 1;
    var forkSlowUntil = 0;
    var frameI = 0;
    var tPlay = 0;
    var lastTs = 0;
    var raf = 0;
    var collapseUntil = 0;
    var prevPostKeys = "";
    var rippleUntil = 0;
    var rippleX = 0;
    var rippleY = 0;
    var destroyed = false;
    var yawHist = [];
    var proj = new Projector();
    var autoDemo = opts.autoDemo !== false;
    var defaultPath =
      opts.tracePath ||
      opts.defaultTrace ||
      "/lab/stress/results/traces/latest.json";

    // DOM
    root.classList.add("cev");
    root.innerHTML =
      '<div class="cev-main">' +
      '  <div class="cev-stage">' +
      '    <span class="cev-badge">REPLAY — recorded trace, real estimator</span>' +
      '    <canvas></canvas>' +
      '    <div class="cev-empty" aria-live="polite">' +
      "      <strong>No filter trace loaded</strong>" +
      "      <span>Load a trace JSON, or run the offline synthetic demo.</span>" +
      '      <button type="button" data-act="demo">Load synthetic demo</button>' +
      "    </div>" +
      "  </div>" +
      '  <aside class="cev-rail" aria-label="Telemetry">' +
      '    <div><h3>Effective sample size</h3>' +
      '      <div class="cev-metric"><span>n_eff</span><b data-k="neff">—</b></div>' +
      '      <div class="cev-bar"><i data-k="neffbar"></i></div>' +
      "    </div>" +
      '    <div><h3>Edge posterior</h3><div class="cev-post" data-k="post"></div></div>' +
      '    <div><h3>Speed (m/s)</h3>' +
      '      <div class="cev-metric"><span>model</span><b data-k="spd">—</b></div>' +
      '      <div class="cev-metric"><span>CAN truth</span><b data-k="spdT">—</b></div>' +
      "    </div>" +
      '    <div><h3>Yaw rate</h3><canvas class="cev-spark" data-k="yaw" width="240" height="36"></canvas></div>' +
      '    <div><h3>Error now</h3><div class="cev-err-pair">' +
      '      <div class="est-err"><span>estimate ↔ truth</span><b data-k="errE">—</b></div>' +
      '      <div class="ghost-err"><span>free-DR ↔ truth</span><b data-k="errG">—</b></div>' +
      "    </div></div>" +
      '    <div><h3>Mode</h3><div class="cev-mode" data-k="mode"><span class="dot"></span><span data-k="modeTxt">—</span></div></div>' +
      '    <div class="cev-legend">' +
      '      <span><i class="lg-road"></i>graph</span>' +
      '      <span class="lg-part">particles</span>' +
      '      <span><i class="lg-est"></i>estimate</span>' +
      '      <span><i class="lg-truth"></i>truth</span>' +
      '      <span><i class="lg-dr"></i>free-DR</span>' +
      "    </div>" +
      "  </aside>" +
      "</div>" +
      '<div class="cev-transport">' +
      '  <button type="button" class="primary" data-act="play">Play</button>' +
      '  <button type="button" data-act="step-">−1</button>' +
      '  <button type="button" data-act="step+">+1</button>' +
      '  <input class="cev-scrub" type="range" min="0" max="1000" value="0" data-act="scrub" />' +
      '  <span class="cev-time" data-k="time">0:00.0</span>' +
      '  <button type="button" data-act="speed">1×</button>' +
      '  <button type="button" data-act="loop" class="active">Loop</button>' +
      "</div>";

    var canvas = root.querySelector(".cev-stage canvas");
    var ctx = canvas.getContext("2d");
    var emptyEl = root.querySelector(".cev-empty");
    var badgeEl = root.querySelector(".cev-badge");
    var scrubEl = root.querySelector('[data-act="scrub"]');
    var playBtn = root.querySelector('[data-act="play"]');
    var speedBtn = root.querySelector('[data-act="speed"]');
    var loopBtn = root.querySelector('[data-act="loop"]');
    var spark = root.querySelector('[data-k="yaw"]');
    var sparkCtx = spark.getContext("2d");

    var colors = {
      road: "#3a4450",
      roadLit: null,
      particle: "#e8edf2",
      estimate: null,
      truth: "#c8d0d8",
      freeDr: null,
      bg: null,
    };

    function refreshColors() {
      colors.estimate = cssVar(root, "--accent", "#00d4aa");
      colors.freeDr = cssVar(root, "--bad", "#ff6b6b");
      colors.roadLit = colors.estimate;
      colors.bg = cssVar(root, "--panel", "#0c1016");
    }
    refreshColors();

    function emit(ev, payload) {
      var list = listeners[ev];
      if (!list) return;
      for (var i = 0; i < list.length; i++) {
        try {
          list[i](payload);
        } catch (_) {}
      }
    }

    function on(ev, fn) {
      (listeners[ev] || (listeners[ev] = [])).push(fn);
      return api;
    }

    function off(ev, fn) {
      var list = listeners[ev];
      if (!list) return api;
      listeners[ev] = list.filter(function (f) {
        return f !== fn;
      });
      return api;
    }

    function showEmpty(show) {
      emptyEl.classList.toggle("show", !!show);
    }

    function steps() {
      return (trace && trace.steps) || [];
    }

    function duration() {
      var s = steps();
      if (!s.length) return 0;
      return s[s.length - 1].t;
    }

    function nParticlesMeta() {
      var m = (trace && trace.meta) || {};
      return m.n_particles || m.particles_shown || 1;
    }

    function indexAtTime(t) {
      var s = steps();
      if (!s.length) return 0;
      var lo = 0,
        hi = s.length - 1;
      while (lo < hi) {
        var mid = (lo + hi) >> 1;
        if (s[mid].t < t) lo = mid + 1;
        else hi = mid;
      }
      if (lo > 0 && Math.abs(s[lo - 1].t - t) < Math.abs(s[lo].t - t)) return lo - 1;
      return lo;
    }

    function boundsFromTrace() {
      var g = trace.graph;
      var minLat = Infinity,
        maxLat = -Infinity,
        minLon = Infinity,
        maxLon = -Infinity;
      function add(lat, lon) {
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
      }
      if (g && g.nodes) {
        for (var i = 0; i < g.nodes.length; i++) {
          var n = g.nodes[i];
          if (Array.isArray(n)) add(n[0], n[1]);
          else add(n.lat, n.lon);
        }
      }
      if (g && g.edges) {
        for (var e = 0; e < g.edges.length; e++) {
          var pts = g.edges[e].pts || [];
          for (var j = 0; j < pts.length; j++) {
            var p = pts[j];
            if (Array.isArray(p)) add(p[0], p[1]);
            else add(p.lat, p.lon);
          }
        }
      }
      var s = steps();
      for (var k = 0; k < s.length; k += Math.max(1, Math.floor(s.length / 40))) {
        var st = s[k];
        if (st.truth) add(st.truth.lat, st.truth.lon);
        if (st.estimate) add(st.estimate.lat, st.estimate.lon);
        if (st.free_dr) add(st.free_dr.lat, st.free_dr.lon);
      }
      if (!Number.isFinite(minLat)) {
        minLat = 0;
        maxLat = 1;
        minLon = 0;
        maxLon = 1;
      }
      var padLat = (maxLat - minLat) * 0.12 || 0.0004;
      var padLon = (maxLon - minLon) * 0.12 || 0.0004;
      return {
        minLat: minLat - padLat,
        maxLat: maxLat + padLat,
        minLon: minLon - padLon,
        maxLon: maxLon + padLon,
      };
    }

    function resize() {
      var stage = canvas.parentElement;
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      var w = Math.max(1, stage.clientWidth);
      var h = Math.max(1, stage.clientHeight);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (trace) proj.fit(boundsFromTrace(), w, h);
      draw();
    }

    function edgePath(edge) {
      var pts = edge.pts;
      if (!pts || !pts.length) {
        var g = trace.graph;
        var a = g.nodes[edge.a];
        var b = g.nodes[edge.b];
        if (!a || !b) return null;
        pts = [a, b];
      }
      return pts;
    }

    function drawPolyline(pts, style) {
      if (!pts || pts.length < 2) return;
      ctx.beginPath();
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        var lat = Array.isArray(p) ? p[0] : p.lat;
        var lon = Array.isArray(p) ? p[1] : p.lon;
        var xy = proj.project(lat, lon);
        if (i === 0) ctx.moveTo(xy[0], xy[1]);
        else ctx.lineTo(xy[0], xy[1]);
      }
      ctx.strokeStyle = style.color;
      ctx.lineWidth = style.width || 1.5;
      ctx.setLineDash(style.dash || []);
      ctx.globalAlpha = style.alpha == null ? 1 : style.alpha;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    function posteriorMap(step) {
      var m = Object.create(null);
      var post = step.edge_posterior || [];
      for (var i = 0; i < post.length; i++) {
        var row = post[i];
        var id = Array.isArray(row) ? row[0] : row.id;
        var p = Array.isArray(row) ? row[1] : row.p;
        m[id] = p;
      }
      return m;
    }

    function isFork(step) {
      var post = step.edge_posterior || [];
      var n = 0;
      for (var i = 0; i < post.length; i++) {
        var p = Array.isArray(post[i]) ? post[i][1] : post[i].p;
        if (p >= FORK_THRESHOLD) n++;
      }
      return n >= FORK_MIN_EDGES;
    }

    function draw() {
      var w = canvas.clientWidth;
      var h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = colors.bg;
      ctx.fillRect(0, 0, w, h);

      if (!trace || !steps().length) {
        showEmpty(true);
        return;
      }
      showEmpty(false);

      var step = steps()[frameI] || steps()[0];
      var g = trace.graph || { edges: [], nodes: [] };
      var post = posteriorMap(step);
      var now = performance.now();

      // 1. Road graph
      for (var e = 0; e < (g.edges || []).length; e++) {
        var edge = g.edges[e];
        var eid = edge.id != null ? edge.id : e;
        drawPolyline(edgePath(edge), {
          color: colors.road,
          width: 1.4,
          alpha: 0.85,
        });
      }

      // 2. Edge posterior glow
      for (var e2 = 0; e2 < (g.edges || []).length; e2++) {
        var edge2 = g.edges[e2];
        var eid2 = edge2.id != null ? edge2.id : e2;
        var mass = post[eid2] || 0;
        if (mass < 0.05) continue;
        drawPolyline(edgePath(edge2), {
          color: colors.roadLit,
          width: 2 + mass * 4,
          alpha: 0.15 + mass * 0.55,
        });
      }

      // Collapse: fade losing branches (already handled by low posterior alpha)

      // 3. Particles (additive)
      var parts = step.particles || [];
      var maxW = 0;
      for (var pi = 0; pi < parts.length; pi++) {
        if (parts[pi].w > maxW) maxW = parts[pi].w;
      }
      if (maxW <= 0) maxW = 1;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      for (var pj = 0; pj < parts.length; pj++) {
        var part = parts[pj];
        var lat = part.lat;
        var lon = part.lon;
        if (!Number.isFinite(lat) && Number.isFinite(part.e) && Number.isFinite(part.s)) {
          var eg = g.edges[part.e];
          if (eg) {
            var epts = edgePath(eg);
            if (epts && epts.length) {
              var u = clamp(part.s, 0, 1) * (epts.length - 1);
              var i0 = Math.floor(u);
              var i1 = Math.min(epts.length - 1, i0 + 1);
              var f = u - i0;
              var a0 = epts[i0],
                a1 = epts[i1];
              var la0 = Array.isArray(a0) ? a0[0] : a0.lat;
              var lo0 = Array.isArray(a0) ? a0[1] : a0.lon;
              var la1 = Array.isArray(a1) ? a1[0] : a1.lat;
              var lo1 = Array.isArray(a1) ? a1[1] : a1.lon;
              lat = lerp(la0, la1, f);
              lon = lerp(lo0, lo1, f);
            }
          }
        }
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        var xy = proj.project(lat, lon);
        var nw = part.w / maxW;
        var r = 1.2 + nw * 2.8;
        var alpha = 0.12 + nw * 0.55;
        ctx.beginPath();
        ctx.fillStyle = "rgba(232,237,242," + alpha.toFixed(3) + ")";
        ctx.arc(xy[0], xy[1], r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // Trails for truth / free_dr / estimate (recent history)
      var trailN = 40;
      var iStart = Math.max(0, frameI - trailN);
      function trail(key, style) {
        var pts = [];
        for (var ti = iStart; ti <= frameI; ti++) {
          var st = steps()[ti][key];
          if (st && Number.isFinite(st.lat)) pts.push([st.lat, st.lon]);
        }
        drawPolyline(pts, style);
      }

      // 4. Free-DR ghost — dashed red
      trail("free_dr", {
        color: colors.freeDr,
        width: 2,
        dash: [7, 5],
        alpha: 0.95,
      });
      if (step.free_dr) {
        var fxy = proj.project(step.free_dr.lat, step.free_dr.lon);
        ctx.beginPath();
        ctx.strokeStyle = colors.freeDr;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.arc(fxy[0], fxy[1], 5, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // 5. Truth — dotted white/grey
      trail("truth", {
        color: colors.truth,
        width: 1.8,
        dash: [1.5, 3.5],
        alpha: 0.9,
      });
      if (step.truth) {
        var txy = proj.project(step.truth.lat, step.truth.lon);
        ctx.beginPath();
        ctx.fillStyle = colors.truth;
        ctx.arc(txy[0], txy[1], 3.2, 0, Math.PI * 2);
        ctx.fill();
      }

      // 6. Estimate — solid teal
      trail("estimate", {
        color: colors.estimate,
        width: 2.2,
        dash: [],
        alpha: 1,
      });
      if (step.estimate) {
        var exy = proj.project(step.estimate.lat, step.estimate.lon);
        ctx.beginPath();
        ctx.fillStyle = colors.estimate;
        ctx.arc(exy[0], exy[1], 4.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.strokeStyle = colors.estimate;
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.45;
        ctx.arc(exy[0], exy[1], 9, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Divergence connector
      if (step.free_dr && step.estimate) {
        var gap = haversine(
          step.free_dr.lat,
          step.free_dr.lon,
          step.estimate.lat,
          step.estimate.lon
        );
        if (gap >= DIVERGE_M) {
          var a = proj.project(step.estimate.lat, step.estimate.lon);
          var b = proj.project(step.free_dr.lat, step.free_dr.lon);
          ctx.beginPath();
          ctx.strokeStyle = colors.freeDr;
          ctx.lineWidth = 1;
          ctx.setLineDash([2, 4]);
          ctx.globalAlpha = 0.7;
          ctx.moveTo(a[0], a[1]);
          ctx.lineTo(b[0], b[1]);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.globalAlpha = 1;
          var mx = (a[0] + b[0]) / 2;
          var my = (a[1] + b[1]) / 2;
          ctx.font = "10px " + cssVar(root, "--mono", "monospace");
          ctx.fillStyle = colors.freeDr;
          ctx.fillText(Math.round(gap) + " m", mx + 6, my - 4);
        }
      }

      // Resample ripple
      if (now < rippleUntil && step.estimate) {
        var age = 1 - (rippleUntil - now) / 350;
        var rxy = proj.project(step.estimate.lat, step.estimate.lon);
        ctx.beginPath();
        ctx.strokeStyle = colors.estimate;
        ctx.lineWidth = 1.2;
        ctx.globalAlpha = 0.35 * (1 - age);
        ctx.arc(rxy[0], rxy[1], 6 + age * 22, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Particle count label
      var meta = trace.meta || {};
      var shown = meta.particles_shown || parts.length;
      var total = meta.particles_total || meta.n_particles || shown;
      ctx.font = "10px " + cssVar(root, "--mono", "monospace");
      ctx.fillStyle = cssVar(root, "--dim", "#8b97a6");
      ctx.fillText(
        "particles " + shown + (total !== shown ? " / " + total : ""),
        12,
        h - 12
      );
    }

    function updateRail() {
      if (!trace || !steps().length) {
        root.querySelector('[data-k="neff"]').textContent = "—";
        root.querySelector('[data-k="neffbar"]').style.width = "0%";
        root.querySelector('[data-k="post"]').innerHTML =
          '<div class="cev-metric"><span>no data</span></div>';
        root.querySelector('[data-k="spd"]').textContent = "—";
        root.querySelector('[data-k="spdT"]').textContent = "—";
        root.querySelector('[data-k="errE"]').textContent = "—";
        root.querySelector('[data-k="errG"]').textContent = "—";
        root.querySelector('[data-k="modeTxt"]').textContent = "—";
        root.querySelector('[data-k="mode"]').className = "cev-mode";
        root.querySelector('[data-k="time"]').textContent = "0:00.0";
        return;
      }
      var step = steps()[frameI];
      var nP = nParticlesMeta();
      var ne = step.n_eff;
      root.querySelector('[data-k="neff"]').textContent = Number.isFinite(ne)
        ? ne.toFixed(1) + " / " + nP
        : "—";
      root.querySelector('[data-k="neffbar"]').style.width =
        Number.isFinite(ne) ? clamp((100 * ne) / nP, 0, 100).toFixed(1) + "%" : "0%";

      var post = (step.edge_posterior || []).slice(0, 3);
      var postHtml = "";
      for (var i = 0; i < post.length; i++) {
        var row = post[i];
        var id = Array.isArray(row) ? row[0] : row.id;
        var p = Array.isArray(row) ? row[1] : row.p;
        postHtml +=
          '<div class="cev-post-row"><span>e' +
          id +
          '</span><div class="fill"><i style="width:' +
          clamp(p * 100, 0, 100).toFixed(1) +
          '%"></i></div><span>' +
          (p * 100).toFixed(0) +
          "%</span></div>";
      }
      if (!postHtml) postHtml = '<div class="cev-metric"><span>none</span></div>';
      root.querySelector('[data-k="post"]').innerHTML = postHtml;

      var spd = step.speed_mps;
      var spdT = step.speed_truth_mps != null ? step.speed_truth_mps : step.speed_can;
      root.querySelector('[data-k="spd"]').textContent = Number.isFinite(spd)
        ? spd.toFixed(2)
        : "—";
      root.querySelector('[data-k="spdT"]').textContent = Number.isFinite(spdT)
        ? spdT.toFixed(2)
        : "—";

      var errE = "—",
        errG = "—";
      if (step.truth && step.estimate) {
        errE = fmtM(
          haversine(
            step.estimate.lat,
            step.estimate.lon,
            step.truth.lat,
            step.truth.lon
          )
        );
      }
      if (step.truth && step.free_dr) {
        errG = fmtM(
          haversine(
            step.free_dr.lat,
            step.free_dr.lon,
            step.truth.lat,
            step.truth.lon
          )
        );
      }
      root.querySelector('[data-k="errE"]').textContent = errE;
      root.querySelector('[data-k="errG"]').textContent = errG;

      var mode = step.mode || (frameI === 0 ? "GNSS" : "IDR");
      var modeEl = root.querySelector('[data-k="mode"]');
      root.querySelector('[data-k="modeTxt"]').textContent = mode;
      modeEl.className =
        "cev-mode " + (String(mode).toUpperCase().indexOf("GNSS") >= 0 ? "on-gnss" : "on-idr");

      root.querySelector('[data-k="time"]').textContent =
        fmtTime(step.t) + " / " + fmtTime(duration());

      // yaw sparkline
      yawHist.push(step.yaw_rate || 0);
      if (yawHist.length > 80) yawHist.shift();
      var sw = spark.width;
      var sh = spark.height;
      sparkCtx.clearRect(0, 0, sw, sh);
      sparkCtx.strokeStyle = cssVar(root, "--line", "#1c232d");
      sparkCtx.beginPath();
      sparkCtx.moveTo(0, sh / 2);
      sparkCtx.lineTo(sw, sh / 2);
      sparkCtx.stroke();
      if (yawHist.length > 1) {
        var mn = Math.min.apply(null, yawHist);
        var mx = Math.max.apply(null, yawHist);
        var span = Math.max(0.05, mx - mn);
        sparkCtx.strokeStyle = cssVar(root, "--dim", "#8b97a6");
        sparkCtx.lineWidth = 1.2;
        sparkCtx.setLineDash([]);
        sparkCtx.beginPath();
        for (var yi = 0; yi < yawHist.length; yi++) {
          var x = (yi / (yawHist.length - 1)) * (sw - 2) + 1;
          var y = sh - 2 - ((yawHist[yi] - mn) / span) * (sh - 4);
          if (yi === 0) sparkCtx.moveTo(x, y);
          else sparkCtx.lineTo(x, y);
        }
        sparkCtx.stroke();
      }

      if (scrubEl && !scrubEl._dragging) {
        var dur = duration() || 1;
        scrubEl.value = String(Math.round((1000 * step.t) / dur));
      }
    }

    function applyFrameEffects(prevI, nextI) {
      var step = steps()[nextI];
      if (!step) return;
      if (step.resampled) {
        rippleUntil = performance.now() + 350;
      }
      if (isFork(step)) {
        forkSlowUntil = performance.now() + FORK_HOLD_MS;
      }
      var key = JSON.stringify(step.edge_posterior || []);
      if (prevPostKeys && key !== prevPostKeys) {
        collapseUntil = performance.now() + COLLAPSE_MS;
      }
      prevPostKeys = key;
    }

    function setFrame(i, fromSeek) {
      var s = steps();
      if (!s.length) return;
      var prev = frameI;
      frameI = clamp(i | 0, 0, s.length - 1);
      tPlay = s[frameI].t;
      if (!fromSeek) applyFrameEffects(prev, frameI);
      draw();
      updateRail();
      emit("frame", { i: frameI, t: tPlay, step: s[frameI] });
    }

    function effectiveSpeed() {
      var s = baseSpeed;
      if (performance.now() < forkSlowUntil) s = Math.min(s, FORK_SLOW);
      return s;
    }

    function tick(ts) {
      if (destroyed) return;
      raf = requestAnimationFrame(tick);
      if (!playing || !trace) {
        lastTs = ts;
        return;
      }
      var dt = (ts - lastTs) / 1000;
      lastTs = ts;
      if (dt > 0.1) dt = 0.1;
      tPlay += dt * effectiveSpeed();
      var dur = duration();
      if (tPlay > dur) {
        if (loop) tPlay = 0;
        else {
          tPlay = dur;
          playing = false;
          playBtn.textContent = "Play";
          emit("pause", getState());
        }
      }
      var i = indexAtTime(tPlay);
      if (i !== frameI) setFrame(i);
      else {
        draw();
        updateRail();
      }
    }

    function play() {
      if (!trace || !steps().length) return api;
      playing = true;
      playBtn.textContent = "Pause";
      lastTs = performance.now();
      emit("play", getState());
      return api;
    }

    function pause() {
      playing = false;
      playBtn.textContent = "Play";
      emit("pause", getState());
      return api;
    }

    function toggle() {
      return playing ? pause() : play();
    }

    function seek(tOrFrac) {
      var dur = duration();
      var t = tOrFrac;
      if (Math.abs(tOrFrac) <= 1 && dur > 1) {
        // treat as fraction when clearly 0..1
        if (tOrFrac >= 0 && tOrFrac <= 1) t = tOrFrac * dur;
      }
      tPlay = clamp(t, 0, dur);
      setFrame(indexAtTime(tPlay), true);
      emit("seek", getState());
      return api;
    }

    function setSpeed(rate) {
      var r = Number(rate);
      if (!Number.isFinite(r)) return api;
      baseSpeed = clamp(r, 0.25, 4);
      // snap index to nearest preset for button label
      var best = 0,
        bd = Infinity;
      for (var i = 0; i < SPEEDS.length; i++) {
        var d = Math.abs(SPEEDS[i] - baseSpeed);
        if (d < bd) {
          bd = d;
          best = i;
        }
      }
      speedIdx = best;
      speedBtn.textContent = baseSpeed + "×";
      return api;
    }

    function step(dir) {
      pause();
      setFrame(frameI + (dir < 0 ? -1 : 1));
      return api;
    }

    function setLoop(v) {
      loop = !!v;
      loopBtn.classList.toggle("active", loop);
      return api;
    }

    function getState() {
      var step = steps()[frameI];
      return {
        playing: playing,
        t: tPlay,
        i: frameI,
        speed: baseSpeed,
        loop: loop,
        nEff: step && step.n_eff,
        hasTrace: !!(trace && steps().length),
        meta: trace && trace.meta,
      };
    }

    function ingest(obj) {
      if (!obj || !obj.steps || !obj.steps.length) {
        trace = null;
        showEmpty(true);
        draw();
        updateRail();
        emit("empty", null);
        return;
      }
      trace = obj;
      yawHist = [];
      frameI = 0;
      tPlay = 0;
      prevPostKeys = "";
      forkSlowUntil = 0;
      var honesty = obj.meta && String(obj.meta.honesty || "").toUpperCase();
      var drive = obj.meta && String(obj.meta.drive || "").toUpperCase();
      if (
        obj.meta &&
        (obj.meta.synthetic ||
          honesty === "SYNTHETIC" ||
          (drive && drive.indexOf("SYNTHETIC") === 0))
      ) {
        badgeEl.textContent =
          honesty === "SYNTHETIC" || (drive && drive.indexOf("SYNTHETIC") === 0)
            ? "SYNTHETIC — plumbing only, not field evidence"
            : "DEMO — synthetic offline trace";
      } else {
        badgeEl.textContent = "REPLAY — recorded trace, real estimator";
      }
      resize();
      setFrame(0, true);
      emit("load", { meta: obj.meta });
    }

    function load(source) {
      if (source && typeof source === "object" && source.steps) {
        ingest(source);
        return Promise.resolve(api);
      }
      var path = typeof source === "string" ? source : defaultPath;
      return fetch(path, { cache: "no-store" })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(function (obj) {
          ingest(obj);
          return api;
        })
        .catch(function (err) {
          emit("error", err);
          if (autoDemo) {
            ingest(syntheticTrace());
            emit("fallback", { reason: String(err && err.message) });
          } else {
            trace = null;
            showEmpty(true);
            draw();
            updateRail();
          }
          return api;
        });
    }

    function destroy() {
      destroyed = true;
      playing = false;
      if (raf) cancelAnimationFrame(raf);
      if (ro) ro.disconnect();
      root.removeEventListener("click", onClick);
      scrubEl.removeEventListener("input", onScrub);
      scrubEl.removeEventListener("pointerdown", onScrubDown);
      scrubEl.removeEventListener("pointerup", onScrubUp);
      window.removeEventListener("resize", resize);
      root.innerHTML = "";
      listeners = {};
      emit("destroy", null);
    }

    function onClick(ev) {
      var btn = ev.target.closest("[data-act]");
      if (!btn) return;
      var act = btn.getAttribute("data-act");
      if (act === "play") toggle();
      else if (act === "step-") step(-1);
      else if (act === "step+") step(1);
      else if (act === "speed") {
        speedIdx = (speedIdx + 1) % SPEEDS.length;
        setSpeed(SPEEDS[speedIdx]);
      } else if (act === "loop") setLoop(!loop);
      else if (act === "demo") {
        ingest(syntheticTrace());
        play();
      }
    }

    function onScrub() {
      var dur = duration() || 1;
      seek((Number(scrubEl.value) / 1000) * dur);
    }
    function onScrubDown() {
      scrubEl._dragging = true;
      pause();
    }
    function onScrubUp() {
      scrubEl._dragging = false;
    }

    root.addEventListener("click", onClick);
    scrubEl.addEventListener("input", onScrub);
    scrubEl.addEventListener("pointerdown", onScrubDown);
    scrubEl.addEventListener("pointerup", onScrubUp);
    window.addEventListener("resize", resize);

    var ro = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(function () {
        resize();
      });
      ro.observe(canvas.parentElement);
    }

    showEmpty(true);
    resize();
    raf = requestAnimationFrame(tick);

    // Auto-load
    if (opts.trace) {
      ingest(opts.trace);
    } else if (opts.autoLoad !== false) {
      load(opts.tracePath || defaultPath);
    }

    var api = {
      load: load,
      play: play,
      pause: pause,
      toggle: toggle,
      seek: seek,
      setSpeed: setSpeed,
      step: step,
      setLoop: setLoop,
      destroy: destroy,
      getState: getState,
      on: on,
      off: off,
      root: root,
      VERSION: VERSION,
    };
    return api;
  }

  function mount(el, opts) {
    if (!el) throw new Error("COASTEngineViz.mount: element required");
    if (typeof el === "string") {
      el = document.querySelector(el);
      if (!el) throw new Error("COASTEngineViz.mount: selector not found");
    }
    // Ensure CSS present if page didn't link it
    if (!document.querySelector('link[data-cev], style[data-cev]')) {
      var link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = (opts && opts.cssUrl) || "/static/engine_viz.css";
      link.setAttribute("data-cev", "1");
      document.head.appendChild(link);
    }
    return createInstance(el, opts || {});
  }

  var COASTEngineViz = {
    VERSION: VERSION,
    mount: mount,
    syntheticTrace: syntheticTrace,
  };

  global.COASTEngineViz = COASTEngineViz;
})(typeof window !== "undefined" ? window : globalThis);
