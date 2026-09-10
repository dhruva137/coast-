/* COAST fleet world map — OpenStreetMap tiles (the basemap PS 26168 names).
   No API key. Dark style is Carto Dark Matter, still OSM data.
   Tracks stay on an overlay canvas. */
(function (global) {
  "use strict";

  var TILE = 256;
  var MIN_Z = 2;
  var MAX_Z = 18;
  var STYLES = {
    osm: {
      url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      attr: "© OpenStreetMap",
    },
    dark: {
      url: "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      attr: "© OpenStreetMap © CARTO",
    },
  };

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lon2x(lon, z) { return ((lon + 180) / 360) * Math.pow(2, z); }
  function lat2y(lat, z) {
    var s = Math.sin((lat * Math.PI) / 180);
    s = clamp(s, -0.9999, 0.9999);
    return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * Math.pow(2, z);
  }

  function CoastWorldMap(host, opts) {
    if (!host) return null;
    opts = opts || {};
    host.classList.add("world-map");
    host.innerHTML =
      '<div class="world-map__tiles" aria-hidden="true"></div>' +
      '<canvas class="world-map__overlay"></canvas>' +
      '<div class="world-map__hint">OpenStreetMap · drag · scroll to zoom</div>';
    var tilesEl = host.querySelector(".world-map__tiles");
    var cv = host.querySelector(".world-map__overlay");
    var hintEl = host.querySelector(".world-map__hint");
    var g = cv.getContext("2d");

    var z = 3;
    var cx = lon2x(0, z);
    var cy = lat2y(20, z);
    var devices = [];
    var selected = null;
    var dragging = false;
    var moved = 0;
    var lastX = 0;
    var lastY = 0;
    var tileCache = new Map();
    var styleName = "dark";

    function tileUrl() {
      return (STYLES[styleName] || STYLES.dark).url;
    }

    function size() {
      var r = host.getBoundingClientRect();
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.max(1, Math.floor(r.width * dpr));
      cv.height = Math.max(1, Math.floor(r.height * dpr));
      cv.style.width = r.width + "px";
      cv.style.height = r.height + "px";
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w: r.width, h: r.height };
    }

    function lonLatToPx(lon, lat, w, h) {
      var x = (lon2x(lon, z) - cx) * TILE + w / 2;
      var y = (lat2y(lat, z) - cy) * TILE + h / 2;
      return [x, y];
    }

    function fit(devs) {
      var pts = [];
      devs.forEach(function (d) {
        (d.points || []).forEach(function (p) {
          if (p && isFinite(p.lat) && isFinite(p.lon)) pts.push(p);
        });
        if ((!d.points || !d.points.length) && d.latest) pts.push(d.latest);
      });
      if (!pts.length) {
        z = 3; cx = lon2x(0, z); cy = lat2y(20, z); return;
      }
      var sel = selected && devs.filter(function (d) { return d.device_id === selected; })[0];
      if (sel && sel.latest) {
        var focus = sel.points && sel.points.length > 4 ? sel.points : [sel.latest];
        pts = focus;
      }
      var minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
      pts.forEach(function (p) {
        minLat = Math.min(minLat, p.lat); maxLat = Math.max(maxLat, p.lat);
        minLon = Math.min(minLon, p.lon); maxLon = Math.max(maxLon, p.lon);
      });
      var r = host.getBoundingClientRect();
      var pad = 48;
      for (var zz = MAX_Z; zz >= MIN_Z; zz--) {
        var dx = Math.abs(lon2x(maxLon, zz) - lon2x(minLon, zz)) * TILE;
        var dy = Math.abs(lat2y(minLat, zz) - lat2y(maxLat, zz)) * TILE;
        if (dx + pad * 2 <= r.width && dy + pad * 2 <= r.height) { z = zz; break; }
      }
      cx = (lon2x(minLon, z) + lon2x(maxLon, z)) / 2;
      cy = (lat2y(minLat, z) + lat2y(maxLat, z)) / 2;
    }

    function tileImg(zi, xi, yi) {
      var n = 1 << zi;
      xi = ((xi % n) + n) % n;
      if (yi < 0 || yi >= n) return null;
      var key = zi + "/" + xi + "/" + yi;
      var img = tileCache.get(key);
      if (img) return img.complete && img.naturalWidth ? img : null;
      img = new Image();
      img.decoding = "async";
      img.referrerPolicy = "no-referrer";
      img.onload = function () { draw(); };
      img.src = tileUrl().replace("{z}", zi).replace("{x}", xi).replace("{y}", yi);
      tileCache.set(key, img);
      if (tileCache.size > 250) {
        var first = tileCache.keys().next().value;
        tileCache.delete(first);
      }
      return null;
    }

    function drawTiles(w, h) {
      tilesEl.innerHTML = "";
      var nx = Math.ceil(w / TILE) + 2;
      var ny = Math.ceil(h / TILE) + 2;
      var x0 = Math.floor(cx - w / 2 / TILE);
      var y0 = Math.floor(cy - h / 2 / TILE);
      var frag = document.createDocumentFragment();
      for (var iy = 0; iy <= ny; iy++) {
        for (var ix = 0; ix <= nx; ix++) {
          var xi = x0 + ix;
          var yi = y0 + iy;
          var img = tileImg(z, xi, yi);
          var el = document.createElement("div");
          el.className = "world-map__tile";
          var left = (xi - cx) * TILE + w / 2;
          var top = (yi - cy) * TILE + h / 2;
          el.style.transform = "translate(" + left + "px," + top + "px)";
          if (img) {
            var copy = img.cloneNode(false);
            copy.src = img.src;
            el.appendChild(copy);
          }
          frag.appendChild(el);
        }
      }
      tilesEl.appendChild(frag);
    }

    function strokePath(pts, color, width, dash) {
      if (pts.length < 2) return;
      g.save();
      g.strokeStyle = color;
      g.lineWidth = width;
      g.lineJoin = "round";
      g.lineCap = "round";
      if (dash) g.setLineDash(dash);
      g.beginPath();
      g.moveTo(pts[0][0], pts[0][1]);
      for (var i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]);
      g.stroke();
      g.restore();
    }

    function draw() {
      var dim = size();
      var w = dim.w, h = dim.h;
      if (w < 8 || h < 8) return;
      drawTiles(w, h);
      g.clearRect(0, 0, w, h);
      var gnss = "#4A9EFF";
      var idr = "#00D4AA";
      var hold = "#FFD166";
      devices.forEach(function (d) {
        var pts = d.points || [];
        if (!pts.length && d.latest) pts = [d.latest];
        var run = [];
        var mode = pts[0] && pts[0].mode;
        var queued = pts[0] && pts[0].queued;
        function flush() {
          if (run.length < 2) return;
          var col = mode === "IDR" ? idr : mode === "HOLD" ? hold : gnss;
          strokePath(run, col, mode === "IDR" ? 3 : 2.2, queued ? [5, 5] : null);
        }
        pts.forEach(function (p) {
          var xy = lonLatToPx(p.lon, p.lat, w, h);
          if (p.mode !== mode || !!p.queued !== !!queued) {
            if (run.length) run.push(xy);
            flush();
            run = [xy];
            mode = p.mode;
            queued = p.queued;
          } else run.push(xy);
        });
        flush();
        var last = pts[pts.length - 1];
        if (!last) return;
        var xy = lonLatToPx(last.lon, last.lat, w, h);
        var sel = selected === d.device_id;
        g.save();
        if (d.online) { g.shadowColor = d.color; g.shadowBlur = sel ? 18 : 10; }
        g.fillStyle = d.online ? d.color : "#3A434F";
        g.beginPath();
        g.arc(xy[0], xy[1], sel ? 8 : 5.5, 0, 7);
        g.fill();
        g.restore();
        g.fillStyle = d.online ? "#E8EDF2" : "#5A6673";
        g.font = "600 11px system-ui";
        g.textAlign = "left";
        g.fillText(d.label || "device", xy[0] + 10, xy[1] + 4);
      });
    }

    host.addEventListener("pointerdown", function (e) {
      dragging = true;
      moved = 0;
      lastX = e.clientX;
      lastY = e.clientY;
      host.setPointerCapture(e.pointerId);
    });
    host.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var dx = e.clientX - lastX;
      var dy = e.clientY - lastY;
      moved += Math.abs(dx) + Math.abs(dy);
      cx -= dx / TILE;
      cy -= dy / TILE;
      lastX = e.clientX;
      lastY = e.clientY;
      draw();
    });
    host.addEventListener("pointerup", function (e) {
      dragging = false;
      if (moved >= 10 || typeof opts.onSelect !== "function") return;
      var r = host.getBoundingClientRect();
      var x = e.clientX - r.left;
      var y = e.clientY - r.top;
      var best = null;
      var bestD = 28;
      devices.forEach(function (d) {
        var last = (d.points && d.points.length) ? d.points[d.points.length - 1] : d.latest;
        if (!last || !isFinite(last.lat) || !isFinite(last.lon)) return;
        var xy = lonLatToPx(last.lon, last.lat, r.width, r.height);
        var dist = Math.hypot(xy[0] - x, xy[1] - y);
        if (dist < bestD) { bestD = dist; best = d.device_id; }
      });
      if (best) opts.onSelect(best);
    });
    host.addEventListener("pointercancel", function () { dragging = false; });
    host.addEventListener("wheel", function (e) {
      e.preventDefault();
      var r = host.getBoundingClientRect();
      var mx = e.clientX - r.left;
      var my = e.clientY - r.top;
      var beforeX = cx + (mx - r.width / 2) / TILE;
      var beforeY = cy + (my - r.height / 2) / TILE;
      var nz = clamp((z | 0) + (e.deltaY > 0 ? -1 : 1), MIN_Z, MAX_Z);
      if (nz === z) return;
      var scale = Math.pow(2, nz - z);
      z = nz;
      cx = beforeX * scale - (mx - r.width / 2) / TILE;
      cy = beforeY * scale - (my - r.height / 2) / TILE;
      draw();
    }, { passive: false });

    return {
      setDevices: function (devs, sel, opts) {
        devices = devs || [];
        var prev = selected;
        selected = sel || null;
        if (opts && opts.fit) fit(devices);
        else if (selected && selected !== prev) fit(devices);
        else if (!devices.length) fit([]);
        draw();
      },
      setStyle: function (name) {
        if (!STYLES[name] || styleName === name) return;
        styleName = name;
        tileCache.clear();
        if (hintEl) {
          hintEl.textContent = (STYLES[name].attr || "OpenStreetMap") + " · drag · scroll to zoom";
        }
        draw();
      },
      resize: function () { draw(); },
      fitAll: function () { fit(devices); draw(); },
    };
  }

  global.CoastWorldMap = CoastWorldMap;
})(window);
