/**
 * COAST map-in-loop trace replay.
 *
 * Draws graph.edges[].pts, free_dr, truth, estimate, and particle lat/lon
 * from exported JSON. Particle positions are never synthesised.
 */
(function (global) {
  "use strict";

  var EARTH_R = 6371008.8;
  var SPEEDS = [0.25, 0.5, 1, 2, 4, 8];
  var MAX_PARTICLE_DRAW = 140;
  var LIST_URLS = ["/api/traces", "/api/traces/"];
  var FALLBACK_URLS = [
    "/api/traces/latest.json",
    "/lab/stress/results/traces/latest.json",
    "/static/traces/SYNTHETIC-Y_0.json",
  ];
  var PF_END_KEYS = [
    "pf_end_m",
    "coast_end_m",
    "estimate_end_m",
    "mapfilter_end_m",
    "pf_end_error_m",
    "end_err_pf_m",
    "end_error_pf_m",
  ];
  var FREE_END_KEYS = [
    "free_end_m",
    "free_dr_end_m",
    "free_end_error_m",
    "end_err_free_m",
    "end_error_free_m",
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function clamp(x, a, b) {
    return Math.max(a, Math.min(b, x));
  }

  function haversine(lat1, lon1, lat2, lon2) {
    if (
      !Number.isFinite(lat1) ||
      !Number.isFinite(lon1) ||
      !Number.isFinite(lat2) ||
      !Number.isFinite(lon2)
    ) {
      return NaN;
    }
    var p1 = (lat1 * Math.PI) / 180;
    var p2 = (lat2 * Math.PI) / 180;
    var dp = ((lat2 - lat1) * Math.PI) / 180;
    var dl = ((lon2 - lon1) * Math.PI) / 180;
    var s =
      Math.sin(dp / 2) * Math.sin(dp / 2) +
      Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * EARTH_R * Math.asin(Math.min(1, Math.sqrt(s)));
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
    if (Math.abs(m) < 10) return m.toFixed(2) + " m";
    if (Math.abs(m) < 100) return m.toFixed(1) + " m";
    return Math.round(m) + " m";
  }

  function latLonOf(p) {
    if (!p) return null;
    if (Array.isArray(p) && p.length >= 2) return [Number(p[0]), Number(p[1])];
    if (Number.isFinite(p.lat) && Number.isFinite(p.lon)) return [p.lat, p.lon];
    return null;
  }

  function metaNum(meta, keys) {
    if (!meta) return NaN;
    var i, v, nested;
    for (i = 0; i < keys.length; i++) {
      v = Number(meta[keys[i]]);
      if (Number.isFinite(v)) return v;
    }
    nested = meta.end_error || meta.end_err || meta.end;
    if (nested && typeof nested === "object") {
      var alias = keys === PF_END_KEYS ? ["pf", "coast", "estimate"] : ["free", "free_dr", "dr"];
      for (i = 0; i < alias.length; i++) {
        v = Number(nested[alias[i]]);
        if (Number.isFinite(v)) return v;
      }
    }
    return NaN;
  }

  /* ── Projector (local equirectangular + pan/zoom) ─────────────────── */

  function Projector() {
    this.lat0 = 0;
    this.lon0 = 0;
    this.scale = 1;
    this.cx = 0;
    this.cy = 0;
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.w = 1;
    this.h = 1;
    this.pad = 28;
  }

  Projector.prototype.fit = function (bounds, w, h) {
    this.w = w;
    this.h = h;
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    var dLat = Math.max(1e-9, bounds.maxLat - bounds.minLat);
    var dLon = Math.max(1e-9, bounds.maxLon - bounds.minLon);
    this.lat0 = (bounds.minLat + bounds.maxLat) / 2;
    this.lon0 = (bounds.minLon + bounds.maxLon) / 2;
    var cos = Math.max(0.2, Math.cos((this.lat0 * Math.PI) / 180));
    var usableW = Math.max(40, w - this.pad * 2);
    var usableH = Math.max(40, h - this.pad * 2);
    var sx = usableW / (dLon * cos);
    var sy = usableH / dLat;
    this.scale = Math.min(sx, sy);
    this.cx = w / 2;
    this.cy = h / 2;
  };

  Projector.prototype.project = function (lat, lon) {
    var cos = Math.max(0.2, Math.cos((this.lat0 * Math.PI) / 180));
    var z = this.scale * this.zoom;
    var x = this.cx + (lon - this.lon0) * cos * z + this.panX;
    var y = this.cy - (lat - this.lat0) * z + this.panY;
    return [x, y];
  };

  Projector.prototype.metresPerPx = function () {
    var z = this.scale * this.zoom;
    if (!Number.isFinite(z) || z <= 0) return NaN;
    return EARTH_R * ((Math.PI / 180) * (1 / z));
  };

  /* ── Player ───────────────────────────────────────────────────────── */

  var els = {
    canvas: $("map"),
    stage: $("stage"),
    empty: $("empty"),
    honesty: $("honesty"),
    source: $("source"),
    file: $("file"),
    select: $("trace-select"),
    reload: $("btn-reload"),
    play: $("btn-play"),
    prev: $("btn-prev"),
    next: $("btn-next"),
    scrub: $("scrub"),
    time: $("time"),
    speed: $("btn-speed"),
    loop: $("btn-loop"),
    fit: $("btn-fit"),
    follow: $("follow"),
    hud: $("hud"),
    errChart: $("err-chart"),
  };

  var ctx = els.canvas.getContext("2d");
  var errCtx = els.errChart ? els.errChart.getContext("2d") : null;
  var proj = new Projector();

  var state = {
    trace: null,
    url: "",
    playing: false,
    loop: true,
    speedIdx: 2,
    i: 0,
    t: 0,
    lastTs: 0,
    raf: 0,
    dragging: false,
    lastPtr: null,
    bounds: null,
    errors: [],
    endPf: NaN,
    endFree: NaN,
    endFromMeta: false,
    listed: [],
  };

  var layers = {
    graph: true,
    particles: true,
    free: true,
    truth: true,
    coast: true,
    post: true,
  };

  function steps() {
    return (state.trace && state.trace.steps) || [];
  }

  function duration() {
    var s = steps();
    if (!s.length) return 0;
    var last = s[s.length - 1];
    return Number(last.t) || 0;
  }

  function hzOf() {
    var m = (state.trace && state.trace.meta) || {};
    var hz = Number(m.hz);
    if (Number.isFinite(hz) && hz > 0) return hz;
    var s = steps();
    if (s.length >= 2 && s[s.length - 1].t > s[0].t) {
      return (s.length - 1) / (s[s.length - 1].t - s[0].t);
    }
    return 10;
  }

  function indexAtTime(t) {
    var s = steps();
    if (!s.length) return 0;
    var lo = 0;
    var hi = s.length - 1;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (s[mid].t < t) lo = mid + 1;
      else hi = mid;
    }
    if (lo > 0 && Math.abs(s[lo - 1].t - t) < Math.abs(s[lo].t - t)) return lo - 1;
    return lo;
  }

  function addBound(b, lat, lon) {
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    if (lat < b.minLat) b.minLat = lat;
    if (lat > b.maxLat) b.maxLat = lat;
    if (lon < b.minLon) b.minLon = lon;
    if (lon > b.maxLon) b.maxLon = lon;
  }

  function boundsFromTrace(tr) {
    var b = {
      minLat: Infinity,
      maxLat: -Infinity,
      minLon: Infinity,
      maxLon: -Infinity,
    };
    var g = tr.graph || {};
    var edges = g.edges || [];
    var e, j, pts, ll;
    for (e = 0; e < edges.length; e++) {
      pts = edges[e].pts || [];
      for (j = 0; j < pts.length; j++) {
        ll = latLonOf(pts[j]);
        if (ll) addBound(b, ll[0], ll[1]);
      }
    }
    var nodes = g.nodes || [];
    for (j = 0; j < nodes.length; j++) {
      ll = latLonOf(nodes[j]);
      if (ll) addBound(b, ll[0], ll[1]);
    }
    var s = tr.steps || [];
    var stride = Math.max(1, Math.floor(s.length / 80));
    for (j = 0; j < s.length; j += stride) {
      if (s[j].truth) addBound(b, s[j].truth.lat, s[j].truth.lon);
      if (s[j].estimate) addBound(b, s[j].estimate.lat, s[j].estimate.lon);
      if (s[j].free_dr) addBound(b, s[j].free_dr.lat, s[j].free_dr.lon);
    }
    if (s.length) {
      var last = s[s.length - 1];
      if (last.truth) addBound(b, last.truth.lat, last.truth.lon);
      if (last.estimate) addBound(b, last.estimate.lat, last.estimate.lon);
      if (last.free_dr) addBound(b, last.free_dr.lat, last.free_dr.lon);
    }
    if (!Number.isFinite(b.minLat)) {
      b.minLat = 0;
      b.maxLat = 0.001;
      b.minLon = 0;
      b.maxLon = 0.001;
    }
    var padLat = (b.maxLat - b.minLat) * 0.1 || 0.0003;
    var padLon = (b.maxLon - b.minLon) * 0.1 || 0.0003;
    b.minLat -= padLat;
    b.maxLat += padLat;
    b.minLon -= padLon;
    b.maxLon += padLon;
    return b;
  }

  function computeErrors(tr) {
    var s = tr.steps || [];
    var out = new Array(s.length);
    var i, st, pf, free;
    for (i = 0; i < s.length; i++) {
      st = s[i];
      pf = NaN;
      free = NaN;
      if (st.truth && st.estimate) {
        pf = haversine(st.truth.lat, st.truth.lon, st.estimate.lat, st.estimate.lon);
      }
      if (st.truth && st.free_dr) {
        free = haversine(st.truth.lat, st.truth.lon, st.free_dr.lat, st.free_dr.lon);
      }
      out[i] = { t: st.t, pf: pf, free: free };
    }
    return out;
  }

  function setHonesty(meta) {
    var raw = meta && meta.honesty != null ? String(meta.honesty) : "";
    var hon = raw.toUpperCase();
    els.honesty.classList.remove("is-real", "is-synthetic", "is-unknown");
    if (hon === "REAL") {
      els.honesty.classList.add("is-real");
      els.honesty.textContent = "REAL — field trace, not a win claim";
    } else if (hon === "SYNTHETIC") {
      els.honesty.classList.add("is-synthetic");
      els.honesty.textContent = "SYNTHETIC — plumbing only, not field evidence";
    } else if (raw) {
      els.honesty.classList.add("is-unknown");
      els.honesty.textContent = "honesty: " + raw;
    } else {
      els.honesty.classList.add("is-unknown");
      els.honesty.textContent = "honesty unknown";
    }
    els.honesty.title = (meta && meta.notes) || (meta && meta.source) || "meta.honesty";
    var src = [];
    if (meta && meta.drive) src.push(meta.drive);
    if (meta && Number.isFinite(meta.t0_s)) src.push("t0=" + meta.t0_s + "s");
    if (meta && meta.source) src.push(meta.source);
    els.source.textContent = src.join(" · ");
    els.source.title = els.source.textContent;
  }

  function setEnabled(on) {
    els.play.disabled = !on;
    els.prev.disabled = !on;
    els.next.disabled = !on;
    els.scrub.disabled = !on;
  }

  function showEmpty(show) {
    els.empty.classList.toggle("show", !!show);
  }

  function ingest(obj, url) {
    if (!obj || !Array.isArray(obj.steps) || !obj.steps.length) {
      throw new Error("JSON has no steps[]");
    }
    pause();
    state.trace = obj;
    state.url = url || "";
    state.i = 0;
    state.t = Number(obj.steps[0].t) || 0;
    state.bounds = boundsFromTrace(obj);
    state.errors = computeErrors(obj);
    var meta = obj.meta || {};
    var last = state.errors[state.errors.length - 1] || {};
    var metaPf = metaNum(meta, PF_END_KEYS);
    var metaFree = metaNum(meta, FREE_END_KEYS);
    state.endFromMeta = Number.isFinite(metaPf) || Number.isFinite(metaFree);
    state.endPf = Number.isFinite(metaPf) ? metaPf : last.pf;
    state.endFree = Number.isFinite(metaFree) ? metaFree : last.free;
    setHonesty(meta);
    $("k-notes").textContent = meta.notes || meta.source || "";
    var endSrc = [];
    if (Number.isFinite(metaPf) || Number.isFinite(metaFree)) {
      endSrc.push("meta end-error fields");
    }
    endSrc.push("last-step haversine from JSON lat/lon");
    $("k-end-src").textContent =
      (state.endFromMeta ? "Reported in meta when present; " : "") +
      "otherwise computed from the last step’s truth vs estimate vs free_dr.";
    $("k-end-pf").textContent = fmtM(state.endPf);
    $("k-end-free").textContent = fmtM(state.endFree);
    $("k-drive").textContent = meta.drive || "—";
    $("k-hz").textContent = hzOf().toFixed(2) + " Hz";
    setEnabled(true);
    els.reload.disabled = !(state.url && (state.url.charAt(0) === "/" || /^https?:/i.test(state.url)));
    showEmpty(false);
    resize();
    setFrame(0, true);
  }

  function loadUrl(url, quiet) {
    return fetch(url, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (obj) {
        ingest(obj, url);
        return true;
      })
      .catch(function (err) {
        if (!quiet) {
          els.empty.querySelector("strong").textContent = "Could not load trace";
          els.empty.querySelector("p").textContent = url + " — " + (err && err.message);
          showEmpty(true);
        }
        return false;
      });
  }

  function loadFile(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var obj = JSON.parse(String(reader.result));
          ingest(obj, file.name);
          resolve(true);
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = function () {
        reject(new Error("read failed"));
      };
      reader.readAsText(file);
    }).catch(function (err) {
      els.empty.querySelector("strong").textContent = "Invalid JSON";
      els.empty.querySelector("p").textContent = file.name + " — " + (err && err.message);
      showEmpty(true);
      return false;
    });
  }

  function fillSelect(list) {
    state.listed = list || [];
    var sel = els.select;
    sel.innerHTML = '<option value="">Console traces…</option>';
    for (var i = 0; i < state.listed.length; i++) {
      var t = state.listed[i];
      var opt = document.createElement("option");
      opt.value = t.url || "/api/traces/" + t.name;
      var hon = t.honesty ? String(t.honesty) : "?";
      var kb = t.bytes != null ? " · " + Math.round(t.bytes / 1024) + " KB" : "";
      opt.textContent = (t.name || opt.value) + "  [" + hon + "]" + kb;
      sel.appendChild(opt);
    }
  }

  function tryList() {
    var chain = Promise.resolve(null);
    LIST_URLS.forEach(function (u) {
      chain = chain.then(function (got) {
        if (got) return got;
        return fetch(u, { cache: "no-store" })
          .then(function (r) {
            if (!r.ok) return null;
            return r.json();
          })
          .then(function (j) {
            var list = j && (j.traces || j.files || j.items);
            return Array.isArray(list) && list.length ? list : null;
          })
          .catch(function () {
            return null;
          });
      });
    });
    return chain;
  }

  function resize() {
    var stage = els.stage;
    var dpr = Math.min(2, global.devicePixelRatio || 1);
    var w = Math.max(1, stage.clientWidth);
    var h = Math.max(1, stage.clientHeight);
    els.canvas.width = Math.floor(w * dpr);
    els.canvas.height = Math.floor(h * dpr);
    els.canvas.style.width = w + "px";
    els.canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (state.trace && state.bounds) {
      var keepZoom = proj.zoom;
      var keepPanX = proj.panX;
      var keepPanY = proj.panY;
      var had = proj.w > 1;
      proj.fit(state.bounds, w, h);
      if (had) {
        proj.zoom = keepZoom;
        proj.panX = keepPanX;
        proj.panY = keepPanY;
      }
    }
    draw();
  }

  function fitView() {
    if (!state.trace || !state.bounds) return;
    proj.fit(state.bounds, els.stage.clientWidth, els.stage.clientHeight);
    draw();
  }

  function edgePts(edge, graph) {
    if (edge.pts && edge.pts.length) return edge.pts;
    var nodes = (graph && graph.nodes) || [];
    var a = nodes[edge.a];
    var b = nodes[edge.b];
    if (a && b) return [a, b];
    return null;
  }

  function drawPolyline(pts, style) {
    if (!pts || pts.length < 2) return;
    ctx.beginPath();
    var started = false;
    for (var i = 0; i < pts.length; i++) {
      var ll = latLonOf(pts[i]);
      if (!ll) continue;
      var xy = proj.project(ll[0], ll[1]);
      if (!started) {
        ctx.moveTo(xy[0], xy[1]);
        started = true;
      } else {
        ctx.lineTo(xy[0], xy[1]);
      }
    }
    if (!started) return;
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

  function trailPts(key, upto) {
    var s = steps();
    var pts = [];
    var i, st, p;
    for (i = 0; i <= upto; i++) {
      st = s[i];
      p = st && st[key];
      if (p && Number.isFinite(p.lat) && Number.isFinite(p.lon)) {
        pts.push([p.lat, p.lon]);
      }
    }
    return pts;
  }

  function posteriorMap(step) {
    var m = Object.create(null);
    var post = (step && step.edge_posterior) || [];
    for (var i = 0; i < post.length; i++) {
      var row = post[i];
      var id = Array.isArray(row) ? row[0] : row.id;
      var p = Array.isArray(row) ? row[1] : row.p;
      m[id] = p;
    }
    return m;
  }

  function marker(lat, lon, style) {
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    var xy = proj.project(lat, lon);
    ctx.beginPath();
    if (style.fill) {
      ctx.fillStyle = style.fill;
      ctx.arc(xy[0], xy[1], style.r || 4, 0, Math.PI * 2);
      ctx.fill();
    }
    if (style.stroke) {
      ctx.strokeStyle = style.stroke;
      ctx.lineWidth = style.sw || 1.5;
      ctx.setLineDash(style.dash || []);
      ctx.globalAlpha = style.alpha == null ? 1 : style.alpha;
      ctx.beginPath();
      ctx.arc(xy[0], xy[1], style.r || 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }
    return xy;
  }

  function drawScale(w, h) {
    var mpp = proj.metresPerPx();
    if (!Number.isFinite(mpp) || mpp <= 0) return;
    var target = 80 * mpp;
    var nice = [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
    var best = nice[0];
    for (var i = 0; i < nice.length; i++) {
      if (Math.abs(nice[i] - target) < Math.abs(best - target)) best = nice[i];
    }
    var px = best / mpp;
    var x = 14;
    var y = h - 18;
    ctx.strokeStyle = "#8b97a6";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + px, y);
    ctx.moveTo(x, y - 4);
    ctx.lineTo(x, y + 4);
    ctx.moveTo(x + px, y - 4);
    ctx.lineTo(x + px, y + 4);
    ctx.stroke();
    ctx.fillStyle = "#8b97a6";
    ctx.font = "10px " + "ui-monospace, Menlo, Consolas, monospace";
    ctx.fillText(best >= 1000 ? best / 1000 + " km" : best + " m", x, y - 7);
  }

  function drawParticles(step) {
    var parts = step.particles;
    if (!Array.isArray(parts) || !parts.length) return { drawn: 0, skipped: 0 };
    var n = parts.length;
    var stride = n > MAX_PARTICLE_DRAW ? Math.ceil(n / MAX_PARTICLE_DRAW) : 1;
    var maxW = 0;
    var i;
    for (i = 0; i < n; i += stride) {
      if (parts[i].w > maxW) maxW = parts[i].w;
    }
    if (maxW <= 0) maxW = 1;
    var drawn = 0;
    var skipped = 0;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (i = 0; i < n; i += stride) {
      var part = parts[i];
      var lat = part.lat;
      var lon = part.lon;
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        skipped += 1;
        continue;
      }
      var xy = proj.project(lat, lon);
      var nw = part.w / maxW;
      var r = 1.15 + nw * 2.6;
      var alpha = 0.14 + nw * 0.5;
      ctx.beginPath();
      ctx.fillStyle = "rgba(232,237,242," + alpha.toFixed(3) + ")";
      ctx.arc(xy[0], xy[1], r, 0, Math.PI * 2);
      ctx.fill();
      drawn += 1;
    }
    ctx.restore();
    return { drawn: drawn, skipped: skipped, stride: stride, n: n };
  }

  function draw() {
    var w = els.stage.clientWidth;
    var h = els.stage.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#080b10";
    ctx.fillRect(0, 0, w, h);

    var s = steps();
    if (!s.length) {
      showEmpty(true);
      return;
    }
    showEmpty(false);

    var step = s[state.i] || s[0];
    var g = (state.trace && state.trace.graph) || { edges: [], nodes: [] };
    var post = posteriorMap(step);
    var e, edge, eid, mass, pts;

    if (layers.graph) {
      for (e = 0; e < (g.edges || []).length; e++) {
        edge = g.edges[e];
        drawPolyline(edgePts(edge, g), {
          color: "#3a4450",
          width: 1.35,
          alpha: 0.9,
        });
      }
    }

    if (layers.post && layers.graph) {
      for (e = 0; e < (g.edges || []).length; e++) {
        edge = g.edges[e];
        eid = edge.id != null ? edge.id : e;
        mass = post[eid] || 0;
        if (mass < 0.05) continue;
        drawPolyline(edgePts(edge, g), {
          color: "#00d4aa",
          width: 2 + mass * 5,
          alpha: 0.12 + mass * 0.5,
        });
      }
    }

    var pinfo = { drawn: 0, skipped: 0, n: 0, stride: 1 };
    if (layers.particles) pinfo = drawParticles(step);

    if (layers.free) {
      drawPolyline(trailPts("free_dr", state.i), {
        color: "#ff6b6b",
        width: 2,
        dash: [7, 5],
        alpha: 0.95,
      });
      if (step.free_dr) {
        marker(step.free_dr.lat, step.free_dr.lon, {
          stroke: "#ff6b6b",
          r: 5.5,
          dash: [3, 3],
          sw: 1.6,
        });
      }
    }

    if (layers.truth) {
      drawPolyline(trailPts("truth", state.i), {
        color: "#c8d0d8",
        width: 1.8,
        dash: [1.6, 3.4],
        alpha: 0.95,
      });
      if (step.truth) {
        marker(step.truth.lat, step.truth.lon, { fill: "#c8d0d8", r: 3.2 });
      }
    }

    if (layers.coast) {
      drawPolyline(trailPts("estimate", state.i), {
        color: "#00d4aa",
        width: 2.3,
        dash: [],
        alpha: 1,
      });
      if (step.estimate) {
        var xy = marker(step.estimate.lat, step.estimate.lon, {
          fill: "#00d4aa",
          r: 4.4,
        });
        if (xy) {
          ctx.beginPath();
          ctx.strokeStyle = "#00d4aa";
          ctx.lineWidth = 1.4;
          ctx.globalAlpha = 0.4;
          ctx.arc(xy[0], xy[1], 9, 0, Math.PI * 2);
          ctx.stroke();
          ctx.globalAlpha = 1;
          var head = Number(step.estimate.heading);
          if (Number.isFinite(head)) {
            var rad = (head * Math.PI) / 180;
            ctx.beginPath();
            ctx.strokeStyle = "#00d4aa";
            ctx.lineWidth = 1.8;
            ctx.moveTo(xy[0], xy[1]);
            ctx.lineTo(xy[0] + Math.sin(rad) * 16, xy[1] - Math.cos(rad) * 16);
            ctx.stroke();
          }
        }
      }
    }

    drawScale(w, h);
    updateRail(step, pinfo);
    drawErrChart();
  }

  function updateRail(step, pinfo) {
    var s = steps();
    var meta = (state.trace && state.trace.meta) || {};
    var nP = meta.n_particles || step.particles_total || 1;
    $("k-t").textContent = fmtTime(step.t);
    $("k-step").textContent = state.i + 1 + " / " + s.length;
    var ne = step.n_eff;
    $("k-neff").textContent = Number.isFinite(ne) ? ne.toFixed(1) + " / " + nP : "—";
    $("k-neffbar").style.width = Number.isFinite(ne)
      ? clamp((100 * ne) / nP, 0, 100).toFixed(1) + "%"
      : "0%";
    $("k-resample").hidden = !step.resampled;
    $("k-spd").textContent = Number.isFinite(step.speed_mps)
      ? step.speed_mps.toFixed(2) + " m/s"
      : "—";
    $("k-yaw").textContent = Number.isFinite(step.yaw_rate)
      ? step.yaw_rate.toFixed(4) + " rad/s"
      : "—";
    $("k-edge").textContent =
      step.estimate && step.estimate.edge != null ? String(step.estimate.edge) : "—";

    var post = (step.edge_posterior || []).slice(0, 6);
    var html = "";
    var i, row, id, p;
    for (i = 0; i < post.length; i++) {
      row = post[i];
      id = Array.isArray(row) ? row[0] : row.id;
      p = Array.isArray(row) ? row[1] : row.p;
      html +=
        '<div class="tr-post-row"><span>e' +
        id +
        '</span><div class="fill"><i style="width:' +
        clamp(p * 100, 0, 100).toFixed(1) +
        '%"></i></div><span>' +
        (p * 100).toFixed(1) +
        "%</span></div>";
    }
    $("k-post").innerHTML = html || '<div class="tr-post-row"><span>none</span></div>';

    var err = state.errors[state.i] || {};
    $("k-err-pf").textContent = fmtM(err.pf);
    $("k-err-free").textContent = fmtM(err.free);

    var shown = step.particles_shown;
    if (!Number.isFinite(shown) && step.particles) shown = step.particles.length;
    var total = step.particles_total || meta.n_particles || shown;
    $("k-pdraw").textContent = pinfo.drawn + (pinfo.stride > 1 ? " (stride " + pinfo.stride + ")" : "");
    $("k-pshown").textContent = Number.isFinite(shown) ? String(shown) : "—";
    $("k-ptotal").textContent = Number.isFinite(total) ? String(total) : "—";

    els.time.textContent = fmtTime(state.t) + " / " + fmtTime(duration());
    if (!els.scrub._dragging) {
      var dur = duration() || 1;
      els.scrub.value = String(Math.round((1000 * state.t) / dur));
    }
  }

  function drawErrChart() {
    if (!errCtx) return;
    var c = els.errChart;
    var w = c.width;
    var h = c.height;
    errCtx.clearRect(0, 0, w, h);
    var err = state.errors;
    if (!err.length) return;
    var max = 1;
    var i;
    for (i = 0; i < err.length; i++) {
      if (err[i].pf > max) max = err[i].pf;
      if (err[i].free > max) max = err[i].free;
    }
    function series(key, color, dash) {
      errCtx.beginPath();
      var started = false;
      for (i = 0; i < err.length; i++) {
        var v = err[i][key];
        if (!Number.isFinite(v)) continue;
        var x = (i / Math.max(1, err.length - 1)) * (w - 2) + 1;
        var y = h - 4 - (v / max) * (h - 10);
        if (!started) {
          errCtx.moveTo(x, y);
          started = true;
        } else errCtx.lineTo(x, y);
      }
      errCtx.strokeStyle = color;
      errCtx.lineWidth = 1.4;
      errCtx.setLineDash(dash || []);
      errCtx.stroke();
      errCtx.setLineDash([]);
    }
    series("free", "#ff6b6b", [4, 3]);
    series("pf", "#00d4aa", []);
    var xNow = (state.i / Math.max(1, err.length - 1)) * (w - 2) + 1;
    errCtx.strokeStyle = "#5a6673";
    errCtx.lineWidth = 1;
    errCtx.beginPath();
    errCtx.moveTo(xNow, 0);
    errCtx.lineTo(xNow, h);
    errCtx.stroke();
  }

  function setFrame(i, fromScrub) {
    var s = steps();
    if (!s.length) return;
    state.i = clamp(i, 0, s.length - 1);
    state.t = s[state.i].t;
    if (els.follow.checked && s[state.i].estimate) {
      var est = s[state.i].estimate;
      var xy = proj.project(est.lat, est.lon);
      proj.panX += els.stage.clientWidth / 2 - xy[0];
      proj.panY += els.stage.clientHeight / 2 - xy[1];
    }
    if (!fromScrub) {
      /* scrub updated in updateRail */
    }
    draw();
  }

  function play() {
    if (!steps().length) return;
    state.playing = true;
    els.play.textContent = "Pause";
    state.lastTs = performance.now();
  }

  function pause() {
    state.playing = false;
    els.play.textContent = "Play";
  }

  function toggle() {
    if (state.playing) pause();
    else play();
  }

  function tick(now) {
    state.raf = requestAnimationFrame(tick);
    if (!state.playing || !steps().length) return;
    var dt = (now - state.lastTs) / 1000;
    state.lastTs = now;
    var rate = SPEEDS[state.speedIdx];
    state.t += dt * rate;
    var dur = duration();
    if (state.t > dur) {
      if (state.loop) state.t = steps()[0].t || 0;
      else {
        state.t = dur;
        pause();
      }
    }
    setFrame(indexAtTime(state.t));
  }

  function onWheel(ev) {
    if (!state.trace) return;
    ev.preventDefault();
    var rect = els.canvas.getBoundingClientRect();
    var mx = ev.clientX - rect.left;
    var my = ev.clientY - rect.top;
    var factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
    var next = clamp(proj.zoom * factor, 0.25, 24);
    var k = next / proj.zoom;
    proj.panX = mx - proj.cx - k * (mx - proj.cx - proj.panX);
    proj.panY = my - proj.cy - k * (my - proj.cy - proj.panY);
    proj.zoom = next;
    draw();
  }

  function onPtrDown(ev) {
    state.dragging = true;
    state.lastPtr = { x: ev.clientX, y: ev.clientY };
    try {
      els.canvas.setPointerCapture(ev.pointerId);
    } catch (_) {}
  }

  function onPtrMove(ev) {
    if (!state.dragging || !state.lastPtr) return;
    proj.panX += ev.clientX - state.lastPtr.x;
    proj.panY += ev.clientY - state.lastPtr.y;
    state.lastPtr = { x: ev.clientX, y: ev.clientY };
    draw();
  }

  function onPtrUp() {
    state.dragging = false;
    state.lastPtr = null;
  }

  function boot() {
    els.loop.classList.toggle("primary", false);
    els.loop.style.outline = state.loop ? "1px solid #00d4aa" : "";

    els.file.addEventListener("change", function () {
      var f = els.file.files && els.file.files[0];
      if (f) loadFile(f);
    });
    els.select.addEventListener("change", function () {
      if (els.select.value) loadUrl(els.select.value);
    });
    els.reload.addEventListener("click", function () {
      if (state.url && (state.url.charAt(0) === "/" || /^https?:/i.test(state.url))) {
        loadUrl(state.url);
      }
    });
    els.play.addEventListener("click", toggle);
    els.prev.addEventListener("click", function () {
      pause();
      setFrame(state.i - 1);
    });
    els.next.addEventListener("click", function () {
      pause();
      setFrame(state.i + 1);
    });
    els.speed.addEventListener("click", function () {
      state.speedIdx = (state.speedIdx + 1) % SPEEDS.length;
      els.speed.textContent = SPEEDS[state.speedIdx] + "×";
    });
    els.loop.addEventListener("click", function () {
      state.loop = !state.loop;
      els.loop.style.outline = state.loop ? "1px solid #00d4aa" : "";
    });
    els.fit.addEventListener("click", fitView);
    els.scrub.addEventListener("pointerdown", function () {
      els.scrub._dragging = true;
      pause();
    });
    els.scrub.addEventListener("pointerup", function () {
      els.scrub._dragging = false;
    });
    els.scrub.addEventListener("input", function () {
      var dur = duration() || 1;
      state.t = (Number(els.scrub.value) / 1000) * dur;
      setFrame(indexAtTime(state.t), true);
    });

    ["graph", "particles", "free", "truth", "coast", "post"].forEach(function (k) {
      var el = $("ly-" + k);
      if (!el) return;
      el.addEventListener("change", function () {
        layers[k] = !!el.checked;
        draw();
      });
    });

    els.canvas.addEventListener("wheel", onWheel, { passive: false });
    els.canvas.addEventListener("pointerdown", onPtrDown);
    els.canvas.addEventListener("pointermove", onPtrMove);
    els.canvas.addEventListener("pointerup", onPtrUp);
    els.canvas.addEventListener("pointercancel", onPtrUp);

    document.addEventListener("keydown", function (ev) {
      var tag = (ev.target && ev.target.tagName) || "";
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (ev.code === "Space") {
        ev.preventDefault();
        toggle();
      } else if (ev.code === "ArrowLeft") {
        pause();
        setFrame(state.i - 1);
      } else if (ev.code === "ArrowRight") {
        pause();
        setFrame(state.i + 1);
      } else if (ev.code === "Home") {
        pause();
        setFrame(0);
      } else if (ev.code === "End") {
        pause();
        setFrame(steps().length - 1);
      } else if (ev.key === "f" || ev.key === "F") {
        fitView();
      }
    });

    document.addEventListener("dragover", function (ev) {
      ev.preventDefault();
    });
    document.addEventListener("drop", function (ev) {
      ev.preventDefault();
      var f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
      if (f) loadFile(f);
    });

    global.addEventListener("resize", resize);
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(resize).observe(els.stage);
    }

    state.raf = requestAnimationFrame(tick);
    resize();

    var params = new URLSearchParams(location.search);
    var src = params.get("src");
    tryList().then(function (list) {
      if (list) fillSelect(list);
      if (src) return loadUrl(src);
      if (list && list.length) {
        var prefer =
          list.filter(function (t) {
            return String(t.honesty || "").toUpperCase() === "REAL";
          })[0] || list[0];
        return loadUrl(prefer.url || "/api/traces/" + prefer.name);
      }
      var seq = Promise.resolve(false);
      FALLBACK_URLS.forEach(function (u) {
        seq = seq.then(function (got) {
          return got ? true : loadUrl(u, true);
        });
      });
      return seq;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  global.COASTTraceReplay = {
    loadUrl: loadUrl,
    loadFile: loadFile,
    ingest: ingest,
  };
})(typeof window !== "undefined" ? window : globalThis);
