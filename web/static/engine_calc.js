/* Engine — live arithmetic.
 *
 * Streams /api/engine/stream and renders each step's real computed values.
 * Nothing here generates a number: every field displayed comes from
 * web/engine_compute.py running over the committed Coventry UK recording.
 * If the stream errors, the view says so and stops -- it never keeps drawing.
 */
(function () {
  "use strict";

  var $ = function (s) { return document.querySelector(s); };
  var es = null;
  var accHist = [];
  var gyrHist = [];
  var errHist = [];
  var HIST = 180;

  function fmt(v, d) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toFixed(d === undefined ? 2 : d);
  }
  function setText(id, v) {
    var el = $(id);
    if (el) el.textContent = v;
  }

  function fitCanvas(cv) {
    if (!cv) return null;
    var r = cv.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    var dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(r.width * dpr);
    cv.height = Math.round(r.height * dpr);
    var g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { g: g, w: r.width, h: r.height };
  }

  /* Rolling oscilloscope trace, auto-scaled to what is on screen. */
  function drawScope(cv, hist, color) {
    var c = fitCanvas(cv);
    if (!c) return;
    var g = c.g, w = c.w, h = c.h;
    g.clearRect(0, 0, w, h);
    g.fillStyle = "#04060A";
    g.fillRect(0, 0, w, h);
    if (hist.length < 2) return;

    var lo = Infinity, hi = -Infinity, i, j;
    for (i = 0; i < hist.length; i++)
      for (j = 0; j < 3; j++) {
        if (hist[i][j] < lo) lo = hist[i][j];
        if (hist[i][j] > hi) hi = hist[i][j];
      }
    var span = Math.max(hi - lo, 1e-6);
    var pad = span * 0.12;
    lo -= pad; hi += pad; span = hi - lo;

    // zero line, so sign is readable at a glance
    if (lo < 0 && hi > 0) {
      var zy = h - ((0 - lo) / span) * h;
      g.strokeStyle = "#131A22";
      g.lineWidth = 1;
      g.beginPath(); g.moveTo(0, zy); g.lineTo(w, zy); g.stroke();
    }

    var cols = color;
    for (j = 0; j < 3; j++) {
      g.strokeStyle = cols[j];
      g.lineWidth = 1.3;
      g.beginPath();
      for (i = 0; i < hist.length; i++) {
        var x = (i / (HIST - 1)) * w;
        var y = h - ((hist[i][j] - lo) / span) * h;
        i ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.stroke();
    }
  }

  /* Position error over time. The line that makes the problem obvious. */
  function drawErr() {
    var c = fitCanvas($("#ec-errchart"));
    if (!c) return;
    var g = c.g, w = c.w, h = c.h;
    g.clearRect(0, 0, w, h);
    g.fillStyle = "#04060A";
    g.fillRect(0, 0, w, h);
    if (errHist.length < 2) return;
    var hi = 0;
    for (var i = 0; i < errHist.length; i++) if (errHist[i] > hi) hi = errHist[i];
    hi = Math.max(hi, 1);

    g.beginPath();
    for (i = 0; i < errHist.length; i++) {
      var x = (i / (HIST - 1)) * w;
      var y = h - (errHist[i] / hi) * (h - 4) - 2;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.strokeStyle = "#FF6B6B";
    g.lineWidth = 1.6;
    g.stroke();
    g.lineTo((errHist.length - 1) / (HIST - 1) * w, h);
    g.lineTo(0, h);
    g.closePath();
    g.fillStyle = "rgba(255,107,107,.13)";
    g.fill();

    g.fillStyle = "#5A6673";
    g.font = "9px ui-monospace,monospace";
    g.textAlign = "right";
    g.fillText(Math.round(hi) + " m", w - 4, 10);
  }

  function pulse(id) {
    var el = $(id);
    if (!el) return;
    el.classList.add("is-hot");
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.classList.remove("is-hot"); }, 220);
  }

  function onStep(d) {
    setText("#ec-t", "t = " + fmt(d.t, 2) + " s");
    var mode = $("#ec-mode");
    if (mode) {
      mode.textContent = d.mode;
      mode.className = "ec-mode " + (d.mode === "IDR" ? "is-idr" : "is-gnss");
    }

    setText("#ec-ax", fmt(d.raw.ax, 3));
    setText("#ec-ay", fmt(d.raw.ay, 3));
    setText("#ec-az", fmt(d.raw.az, 3));
    setText("#ec-gx", fmt(d.raw.gx, 4));
    setText("#ec-gy", fmt(d.raw.gy, 4));
    setText("#ec-gz", fmt(d.raw.gz, 4));
    setText("#ec-grx", fmt(d.gravity.x, 3));
    setText("#ec-gry", fmt(d.gravity.y, 3));
    setText("#ec-grz", fmt(d.gravity.z, 3));

    setText("#ec-alin", "[" + fmt(d.linear.x, 3) + ", " + fmt(d.linear.y, 3) +
      ", " + fmt(d.linear.z, 3) + "]   |a| = " + fmt(d.linear.mag, 3));
    pulse("#ec-s1");

    var dpsi = -d.raw.gz * d.dt * 180 / Math.PI;
    setText("#ec-dpsi", "Δψ = " + fmt(dpsi, 3) + "°   ψ = " + fmt(d.heading.gyro, 2) + "°");
    pulse("#ec-s2");

    var z = $("#ec-zupt");
    if (z) z.className = "ec-zupt" + (d.speed.zupt ? " is-on" : "");
    setText("#ec-vint", "Δv = " + fmt(d.linear.y * d.dt, 4) + " m/s   v = " +
      fmt(d.speed.est, 3) + " m/s");
    setText("#ec-zn", d.perf.zupt_count);
    pulse("#ec-s3");

    setText("#ec-dpos", "lat " + d.position.lat.toFixed(6) + "   lon " +
      d.position.lon.toFixed(6));
    pulse("#ec-s4");

    setText("#ec-hg", fmt(d.heading.gyro, 1) + "°");
    setText("#ec-hm", fmt(d.heading.mag, 1) + "°");
    setText("#ec-ht", fmt(d.heading.truth, 1) + "°");
    setText("#ec-hge", "±" + fmt(d.heading.err_gyro, 1));
    setText("#ec-hme", "±" + fmt(d.heading.err_mag, 1));
    setText("#ec-ve", fmt(d.speed.est, 2));
    setText("#ec-vc", fmt(d.speed.can, 2));
    setText("#ec-err", fmt(d.position.err_m, 1));
    setText("#ec-us", fmt(d.perf.us_per_sample, 2));
    setText("#ec-n", d.perf.samples);

    var errCard = $(".ec-err");
    if (errCard) errCard.classList.toggle("is-quiet", d.mode !== "IDR");

    accHist.push([d.raw.ax, d.raw.ay, d.raw.az]);
    gyrHist.push([d.raw.gx, d.raw.gy, d.raw.gz]);
    errHist.push(d.position.err_m);
    while (accHist.length > HIST) accHist.shift();
    while (gyrHist.length > HIST) gyrHist.shift();
    while (errHist.length > HIST) errHist.shift();

    drawScope($("#ec-scope-a"), accHist, ["#4A9EFF", "#00D4AA", "#8B97A6"]);
    drawScope($("#ec-scope-g"), gyrHist, ["#C88BFF", "#FFD166", "#5CE1E6"]);
    drawErr();
  }

  function stop(msg) {
    if (es) { es.close(); es = null; }
    var run = $("#ec-run"), st = $("#ec-stop");
    if (run) { run.disabled = false; run.textContent = "Run estimator"; }
    if (st) st.disabled = true;
    if (msg) setText("#ec-status", msg);
  }

  function run() {
    stop(null);
    accHist = []; gyrHist = []; errHist = [];
    var rate = ($("#ec-rate") || {}).value || "4";
    var run = $("#ec-run"), st = $("#ec-stop");
    if (run) { run.disabled = true; run.textContent = "Running…"; }
    if (st) st.disabled = false;
    setText("#ec-status", "streaming");

    es = new EventSource("/api/engine/stream?rate=" + encodeURIComponent(rate));
    es.onmessage = function (ev) {
      var d;
      try { d = JSON.parse(ev.data); } catch (e) { return; }
      if (d.type === "meta") {
        setText("#ec-src", d.provenance);
        setText("#ec-hz", d.hz + " Hz");
        setText("#ec-status", d.n_samples + " samples · " + d.duration_s + " s");
      } else if (d.type === "step") {
        onStep(d);
      } else if (d.type === "error") {
        stop("error: " + d.error);
      } else if (d.type === "done") {
        stop("complete · " + d.samples + " samples");
      }
    };
    es.onerror = function () { stop("stream closed"); };
  }

  function init() {
    var r = $("#ec-run");
    if (!r || r._wired) return;
    r._wired = true;
    r.addEventListener("click", run);
    var s = $("#ec-stop");
    if (s) s.addEventListener("click", function () { stop("stopped"); });
    window.addEventListener("resize", function () {
      drawScope($("#ec-scope-a"), accHist, ["#4A9EFF", "#00D4AA", "#8B97A6"]);
      drawScope($("#ec-scope-g"), gyrHist, ["#C88BFF", "#FFD166", "#5CE1E6"]);
      drawErr();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  window.COASTEngineCalc = { init: init, run: run, stop: stop };
})();
