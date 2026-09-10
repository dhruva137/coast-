/**
 * COAST Model Architecture Visualizer — 3Blue1Brown-inspired 3D Tensor Mathematics.
 *
 * Renders an interactive 3D isometric tensor decomposition of COAST-VNet-1:
 * - Input Tensor: X in R^(B x 20 x 6) @ 10 Hz
 * - High-Frequency Manifold: 1D Temporal Convolutional filter stack (>2 Hz chassis vibration)
 * - Low-Frequency Manifold: Recurrent GRU hidden state (<2 Hz vehicle motion)
 * - Dense Latent Fusion: R^128 -> (v_t, sigma_t^2)
 * - Manifold Projection: pi_G(x) -> (edge e, offset s) on OSM graph
 *
 * Dependency-free: Pure HTML5 Canvas 2D isometric projection with 60 FPS animation.
 */
(function (global) {
  "use strict";

  function createModelViz(containerId) {
    var container = typeof containerId === "string" ? document.getElementById(containerId) : containerId;
    if (!container) return null;

    var canvas = container.querySelector("canvas") || document.createElement("canvas");
    if (!canvas.parentNode) container.appendChild(canvas);
    var ctx = canvas.getContext("2d");

    var state = {
      angle: 0.52,      // Isometric yaw (rad)
      pitch: 0.42,      // Isometric pitch (rad)
      zoom: 1.0,
      t: 0,             // Animation time (s)
      hoveredBlock: null,
      isDragging: false,
      lastMouseX: 0,
      lastMouseY: 0,
      activeLayer: "all"
    };

    var dpr = window.devicePixelRatio || 1;
    var width = 800;
    var height = 500;

    function resize() {
      var rect = container.getBoundingClientRect();
      width = Math.max(320, rect.width || 800);
      height = Math.max(340, rect.height || 500);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
    }

    // 3D Isometric projection helper
    function project(x, y, z, cx, cy) {
      var cosA = Math.cos(state.angle);
      var sinA = Math.sin(state.angle);
      var cosP = Math.cos(state.pitch);
      var sinP = Math.sin(state.pitch);

      // Rotate around Y axis (yaw)
      var x1 = x * cosA - z * sinA;
      var z1 = x * sinA + z * cosA;

      // Rotate around X axis (pitch)
      var y2 = y * cosP - z1 * sinP;
      var z2 = y * sinP + z1 * cosP;

      var scale = state.zoom * 1.15;
      return {
        px: cx + x1 * scale,
        py: cy - y2 * scale,
        depth: z2
      };
    }

    // Draw an isometric 3D voxel / cuboid
    function drawCuboid(c, opt) {
      var ox = opt.x, oy = opt.y, oz = opt.z;
      var dx = opt.dx, dy = opt.dy, dz = opt.dz;
      var cx = opt.cx, cy = opt.cy;
      var stroke = opt.stroke || "#00D4AA";
      var fillTop = opt.fillTop || "rgba(0, 212, 170, 0.22)";
      var fillFront = opt.fillFront || "rgba(0, 212, 170, 0.12)";
      var fillSide = opt.fillSide || "rgba(0, 212, 170, 0.06)";

      // 8 vertices
      var p000 = project(ox, oy, oz, cx, cy);
      var p100 = project(ox + dx, oy, oz, cx, cy);
      var p110 = project(ox + dx, oy + dy, oz, cx, cy);
      var p010 = project(ox, oy + dy, oz, cx, cy);

      var p001 = project(ox, oy, oz + dz, cx, cy);
      var p101 = project(ox + dx, oy, oz + dz, cx, cy);
      var p111 = project(ox + dx, oy + dy, oz + dz, cx, cy);
      var p011 = project(ox, oy + dy, oz + dz, cx, cy);

      // Top face (p010 -> p110 -> p111 -> p011)
      c.fillStyle = fillTop;
      c.strokeStyle = stroke;
      c.lineWidth = 1;
      c.beginPath();
      c.moveTo(p010.px, p010.py);
      c.lineTo(p110.px, p110.py);
      c.lineTo(p111.px, p111.py);
      c.lineTo(p011.px, p011.py);
      c.closePath();
      c.fill();
      c.stroke();

      // Front face (p000 -> p100 -> p110 -> p010)
      c.fillStyle = fillFront;
      c.beginPath();
      c.moveTo(p000.px, p000.py);
      c.lineTo(p100.px, p100.py);
      c.lineTo(p110.px, p110.py);
      c.lineTo(p010.px, p010.py);
      c.closePath();
      c.fill();
      c.stroke();

      // Right side face (p100 -> p101 -> p111 -> p110)
      c.fillStyle = fillSide;
      c.beginPath();
      c.moveTo(p100.px, p100.py);
      c.lineTo(p101.px, p101.py);
      c.lineTo(p111.px, p111.py);
      c.lineTo(p110.px, p110.py);
      c.closePath();
      c.fill();
      c.stroke();

      // Draw grid lines inside block for 3Blue1Brown matrix look
      if (opt.slicesX && opt.slicesX > 1) {
        c.strokeStyle = "rgba(232, 237, 242, 0.08)";
        c.lineWidth = 0.8;
        for (var i = 1; i < opt.slicesX; i++) {
          var stepX = ox + (dx * i) / opt.slicesX;
          var pA = project(stepX, oy, oz, cx, cy);
          var pB = project(stepX, oy + dy, oz, cx, cy);
          var pC = project(stepX, oy + dy, oz + dz, cx, cy);
          c.beginPath();
          c.moveTo(pA.px, pA.py);
          c.lineTo(pB.px, pB.py);
          c.lineTo(pC.px, pC.py);
          c.stroke();
        }
      }
    }

    // Connecting mathematical spline / flow arrow
    function drawTensorFlow(c, fromP, toP, label, color) {
      c.strokeStyle = color || "rgba(0, 212, 170, 0.45)";
      c.lineWidth = 1.4;
      c.setLineDash([4, 4]);

      var midX = (fromP.px + toP.px) / 2;
      var midY = (fromP.py + toP.py) / 2 - 14;

      c.beginPath();
      c.moveTo(fromP.px, fromP.py);
      c.quadraticCurveTo(midX, midY, toP.px, toP.py);
      c.stroke();
      c.setLineDash([]);

      // Flow particle animation
      var phase = (state.t * 0.7) % 1;
      var px = (1 - phase) * (1 - phase) * fromP.px + 2 * (1 - phase) * phase * midX + phase * phase * toP.px;
      var py = (1 - phase) * (1 - phase) * fromP.py + 2 * (1 - phase) * phase * midY + phase * phase * toP.py;

      c.fillStyle = color || "#00D4AA";
      c.beginPath();
      c.arc(px, py, 2.5, 0, Math.PI * 2);
      c.fill();

      if (label) {
        c.font = "9px ui-monospace, Menlo, Consolas, monospace";
        c.fillStyle = "rgba(139, 151, 166, 0.9)";
        c.textAlign = "center";
        c.fillText(label, midX, midY - 6);
      }
    }

    function render() {
      state.t += 0.016;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);

      // Deep abyss canvas background with subtle coordinate guide
      ctx.fillStyle = "#07090D";
      ctx.fillRect(0, 0, width, height);

      // Ambient mathematical grid lines (Faint 3Blue1Brown grid)
      ctx.strokeStyle = "rgba(28, 35, 45, 0.55)";
      ctx.lineWidth = 1;
      var gridSpacing = 40;
      ctx.beginPath();
      for (var gx = 0; gx < width; gx += gridSpacing) {
        ctx.moveTo(gx, 0);
        ctx.lineTo(gx, height);
      }
      for (var gy = 0; gy < height; gy += gridSpacing) {
        ctx.moveTo(0, gy);
        ctx.lineTo(width, gy);
      }
      ctx.stroke();

      var cx = width * 0.44;
      var cy = height * 0.52;

      // ── STAGE 1: Input Tensor X in R^(20 x 6) ──
      var inP = project(-180, 0, 0, cx, cy);
      drawCuboid(ctx, {
        x: -240, y: -45, z: -35,
        dx: 48, dy: 90, dz: 70,
        cx: cx, cy: cy,
        slicesX: 4,
        stroke: "#00D4AA",
        fillTop: "rgba(0, 212, 170, 0.18)",
        fillFront: "rgba(0, 212, 170, 0.10)",
        fillSide: "rgba(0, 212, 170, 0.05)"
      });

      ctx.fillStyle = "#E8EDF2";
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      ctx.textAlign = "center";
      ctx.fillText("INPUT TENSOR X", inP.px - 28, inP.py + 72);
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#8B97A6";
      ctx.fillText("R^(20 × 6) @ 10 Hz", inP.px - 28, inP.py + 86);
      ctx.fillStyle = "#5A6673";
      ctx.fillText("[ax, ay, az, ωx, ωy, ωz]", inP.px - 28, inP.py + 98);

      // ── STAGE 2A: High-Band Temporal Conv1D Manifold (Vibration Filter) ──
      var convP = project(-70, 65, 0, cx, cy);
      drawCuboid(ctx, {
        x: -110, y: 35, z: -30,
        dx: 54, dy: 50, dz: 60,
        cx: cx, cy: cy,
        slicesX: 3,
        stroke: "#FFD166",
        fillTop: "rgba(255, 209, 102, 0.22)",
        fillFront: "rgba(255, 209, 102, 0.12)",
        fillSide: "rgba(255, 209, 102, 0.06)"
      });
      ctx.fillStyle = "#FFD166";
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillText("CONV-1D VIBRATION STACK", convP.px, convP.py - 48);
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#8B97A6";
      ctx.fillText("High-band (>2 Hz) · Road Noise Filter", convP.px, convP.py - 34);

      // ── STAGE 2B: Low-Band Recurrent GRU Manifold (Vehicle Kinematics) ──
      var gruP = project(-70, -65, 0, cx, cy);
      drawCuboid(ctx, {
        x: -110, y: -95, z: -30,
        dx: 54, dy: 50, dz: 60,
        cx: cx, cy: cy,
        slicesX: 3,
        stroke: "#4A9EFF",
        fillTop: "rgba(74, 158, 255, 0.22)",
        fillFront: "rgba(74, 158, 255, 0.12)",
        fillSide: "rgba(74, 158, 255, 0.06)"
      });
      ctx.fillStyle = "#4A9EFF";
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillText("RECURRENT GRU MANIFOLD", gruP.px, gruP.py + 58);
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#8B97A6";
      ctx.fillText("Low-band (<2 Hz) · Kinematic State ht", gruP.px, gruP.py + 72);

      // Connect input to upper and lower stream
      drawTensorFlow(ctx, { px: inP.px + 20, py: inP.py - 10 }, { px: convP.px - 30, py: convP.py }, "high-pass", "#FFD166");
      drawTensorFlow(ctx, { px: inP.px + 20, py: inP.py + 10 }, { px: gruP.px - 30, py: gruP.py }, "low-pass", "#4A9EFF");

      // ── STAGE 3: Dense Latent Fusion (R^128) ──
      var fuseP = project(45, 0, 0, cx, cy);
      drawCuboid(ctx, {
        x: 25, y: -30, z: -20,
        dx: 36, dy: 60, dz: 40,
        cx: cx, cy: cy,
        slicesX: 2,
        stroke: "#00D4AA",
        fillTop: "rgba(0, 212, 170, 0.24)",
        fillFront: "rgba(0, 212, 170, 0.14)",
        fillSide: "rgba(0, 212, 170, 0.07)"
      });
      ctx.fillStyle = "#E8EDF2";
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillText("DENSE FUSION", fuseP.px + 10, fuseP.py + 56);
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#8B97A6";
      ctx.fillText("z ∈ R^128 → (vt, σt²)", fuseP.px + 10, fuseP.py + 68);

      drawTensorFlow(ctx, { px: convP.px + 30, py: convP.py }, { px: fuseP.px - 20, py: fuseP.py - 10 }, "W_conv", "#FFD166");
      drawTensorFlow(ctx, { px: gruP.px + 30, py: gruP.py }, { px: fuseP.px - 20, py: fuseP.py + 10 }, "W_gru", "#4A9EFF");

      // ── STAGE 4: Road Graph Manifold Projection π_G ──
      var projP = project(155, 0, 0, cx, cy);

      // Draw the road edge manifold curve
      ctx.strokeStyle = "rgba(74, 158, 255, 0.75)";
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      var rP0 = project(130, -50, -40, cx, cy);
      var rP1 = project(155, 0, 0, cx, cy);
      var rP2 = project(185, 45, 35, cx, cy);
      ctx.moveTo(rP0.px, rP0.py);
      ctx.quadraticCurveTo(rP1.px, rP1.py, rP2.px, rP2.py);
      ctx.stroke();

      // Draw road graph nodes
      [rP0, rP1, rP2].forEach(function (np, idx) {
        ctx.fillStyle = "#0C1016";
        ctx.strokeStyle = "#4A9EFF";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(np.px, np.py, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      });

      // Constrained State Particle on road edge (e, s)
      var sNorm = (Math.sin(state.t * 1.5) + 1) / 2;
      var ptX = (1 - sNorm) * (1 - sNorm) * rP0.px + 2 * (1 - sNorm) * sNorm * rP1.px + sNorm * sNorm * rP2.px;
      var ptY = (1 - sNorm) * (1 - sNorm) * rP0.py + 2 * (1 - sNorm) * sNorm * rP1.py + sNorm * sNorm * rP2.py;

      ctx.fillStyle = "#00D4AA";
      ctx.beginPath();
      ctx.arc(ptX, ptY, 5.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1;
      ctx.stroke();

      drawTensorFlow(ctx, { px: fuseP.px + 24, py: fuseP.py }, { px: ptX, py: ptY }, "π_G: R^2 → (e, s)", "#00D4AA");

      ctx.fillStyle = "#E8EDF2";
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      ctx.textAlign = "left";
      ctx.fillText("GRAPH STATE (e, s)", rP2.px + 12, rP2.py - 14);
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#00D4AA";
      ctx.fillText("Off-road non-representable", rP2.px + 12, rP2.py);
      ctx.fillStyle = "#8B97A6";
      ctx.fillText("2.02× lower median error", rP2.px + 12, rP2.py + 13);

      // Top-left technical readout badge
      ctx.textAlign = "left";
      ctx.font = "600 12px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#E8EDF2";
      ctx.fillText("COAST-VNet-1 ARCHITECTURE", 18, 26);
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#8B97A6";
      ctx.fillText("96,086 Params · 392 KB ONNX · 8.3 µs/step Edge Execution", 18, 42);

      // Bottom instruction note
      ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillStyle = "#5A6673";
      ctx.fillText("DRAG TO ORBIT 3D TENSOR SPACE · SCROLL TO ZOOM", 18, height - 16);

      ctx.restore();
      requestAnimationFrame(render);
    }

    // Interactive mouse / touch orbit handlers
    canvas.addEventListener("mousedown", function (e) {
      state.isDragging = true;
      state.lastMouseX = e.clientX;
      state.lastMouseY = e.clientY;
    });

    window.addEventListener("mouseup", function () {
      state.isDragging = false;
    });

    window.addEventListener("mousemove", function (e) {
      if (!state.isDragging) return;
      var dx = e.clientX - state.lastMouseX;
      var dy = e.clientY - state.lastMouseY;
      state.angle += dx * 0.008;
      state.pitch = Math.max(0.1, Math.min(1.2, state.pitch + dy * 0.008));
      state.lastMouseX = e.clientX;
      state.lastMouseY = e.clientY;
    });

    canvas.addEventListener("wheel", function (e) {
      e.preventDefault();
      var factor = e.deltaY < 0 ? 1.08 : 0.92;
      state.zoom = Math.max(0.65, Math.min(2.0, state.zoom * factor));
    }, { passive: false });

    window.addEventListener("resize", resize);
    resize();
    requestAnimationFrame(render);

    return {
      destroy: function () {
        window.removeEventListener("resize", resize);
      }
    };
  }

  global.COASTModelViz = {
    mount: createModelViz
  };
})(window);
