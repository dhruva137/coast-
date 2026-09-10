/**
 * COAST pairing relay — Cloudflare Worker + KV.
 *
 * Same HTTP contract as `python -m relay` (relay/server.py):
 *   GET  /api/health
 *   GET  /pair                 human landing (get the app)
 *   POST /pair/open            {token?} → register mailbox, TTL 2h
 *   POST /ingest               token + lat/lon/mode/speed_mps/acc_m or points[]
 *   GET  /feed?s=TOKEN[&peek=1][&after=N]
 *   GET  /mailbox/{token}
 *
 * Pages cannot do this. Bind this Worker to coast.paper2anything.com (or a
 * subdomain) and create a KV namespace bound as MAILBOX.
 *
 *   cd relay
 *   npx wrangler kv namespace create MAILBOX
 *   # paste the id into wrangler.toml
 *   npx wrangler deploy
 *
 * This file is not claimed deployed by the repo.
 */

const TTL_S = 2 * 60 * 60;
const MAX_POINTS = 4000;
const MAX_INGEST_POINTS = 400;
const MAX_BODY = 262144;
const TOKEN_RE = /^[A-Za-z0-9_-]{8,64}$/;
const MODES = new Set(["GNSS", "IDR", "HOLD"]);
const FORBIDDEN = /^(imei|imeisv|imsi|iccid|android_?id|advertising_?id|gaid|idfa|idfv|mac|serial|phone(_number)?|email|device_fingerprint)$/i;

const PAIR_LANDING = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>COAST · pair this phone</title>
<style>
  :root{--bg:#07090D;--panel:#0C1016;--line:#1C232D;--text:#E8EDF2;--dim:#8B97A6;
        --faint:#5A6673;--accent:#00D4AA;--mono:ui-monospace,Menlo,Consolas,monospace}
  *{box-sizing:border-box}
  body{margin:0;min-height:100dvh;background:var(--bg);color:var(--text);
       font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:28px 16px}
  .wrap{max-width:28rem;margin:0 auto}
  .brand small{display:block;color:var(--dim);font-size:11px;letter-spacing:.08em;
               text-transform:uppercase;margin-top:4px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
        padding:16px;margin-bottom:12px}
  h1{font-size:22px;margin:0 0 8px}
  p{margin:0 0 12px;color:var(--dim)}
  .code{font-family:var(--mono);font-size:28px;letter-spacing:.06em;font-weight:700;
        color:var(--accent);word-break:break-all;line-height:1.25;padding:12px;
        background:#11161E;border:1px solid var(--line);border-radius:12px;text-align:center}
  a.btn{display:block;text-align:center;text-decoration:none;border-radius:12px;
        padding:14px 16px;font:600 16px system-ui;margin-bottom:10px}
  .go{background:var(--accent);color:#04120E}
  .ghost{background:transparent;color:var(--dim);border:1px solid var(--line)}
  .note{font-size:13px;color:var(--faint);margin:0}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand"><b>COAST</b><small>pair this phone</small></div>
  <div class="card">
    <h1>Open this in the COAST app</h1>
    <p>A generic camera cannot run dead reckoning. Install the app, then scan
      or type the code. Position only — no account, no device ID.</p>
    <div class="code" id="code">—</div>
  </div>
  <a class="btn go" id="openapp" href="#">Open in COAST app</a>
  <a class="btn ghost" href="/">What is COAST?</a>
  <div class="card">
    <p class="note">This page is a public relay. Your phone talks to the internet;
      the operator laptop pulls the track. Guest Wi-Fi does not need to reach
      the laptop.</p>
  </div>
</div>
<script>
const qs = location.search || "";
const token = new URLSearchParams(qs).get("s") || "";
document.getElementById("code").textContent = token || "(no pairing code in this link)";
document.getElementById("openapp").href = "coast://pair" + qs;
</script>
</body>
</html>`;

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }
    try {
      return await handle(request, env);
    } catch (err) {
      return json(500, { ok: false, error: String(err && err.message ? err.message : err) });
    }
  },
};

async function handle(request, env) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  if (request.method === "GET" || request.method === "HEAD") {
    if (path === "/api/health") {
      return json(200, { ok: true, service: "coast-relay", kv: Boolean(env.MAILBOX) });
    }
    if (path === "/pair") {
      return html(PAIR_LANDING, request.method === "HEAD");
    }
    if (path === "/") {
      return html(
        `<!doctype html><html><head><meta charset="utf-8"/><title>COAST relay</title>
         <style>body{background:#07090D;color:#E8EDF2;font:16px system-ui;padding:48px 20px}
         a{color:#00D4AA}</style></head><body>
         <h1>COAST pairing relay</h1>
         <p>Store-and-forward. <a href="/pair">/pair</a> · <a href="/api/health">/api/health</a></p>
         </body></html>`,
        request.method === "HEAD",
      );
    }
    let token = null;
    let peek = false;
    let after = 0;
    if (path === "/feed") {
      token = url.searchParams.get("s") || "";
      peek = url.searchParams.get("peek") === "1";
      after = parseInt(url.searchParams.get("after") || "0", 10) || 0;
    } else if (path.startsWith("/mailbox/")) {
      token = decodeURIComponent(path.slice("/mailbox/".length));
      peek = url.searchParams.get("peek") === "1";
      after = parseInt(url.searchParams.get("after") || "0", 10) || 0;
    }
    if (token !== null) {
      if (!token) return json(400, { ok: false, error: "missing token" });
      return feed(env, token, { consume: !peek, after });
    }
    return json(404, { ok: false, error: "not found" });
  }

  if (request.method !== "POST") {
    return json(405, { ok: false, error: "method not allowed" });
  }

  const len = Number(request.headers.get("content-length") || "0");
  if (len > MAX_BODY) {
    return json(413, { ok: false, error: `body too large (max ${MAX_BODY} bytes)` });
  }

  if (path === "/pair/open") {
    const body = await readJson(request, false);
    if (body.error) return json(body.status, { ok: false, error: body.error });
    const token = body.value && body.value.token;
    return openBox(env, token);
  }

  if (path === "/ingest") {
    const body = await readJson(request, true);
    if (body.error) return json(body.status, { ok: false, error: body.error });
    return ingest(env, body.value);
  }

  return json(404, { ok: false, error: "not found" });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
    "Access-Control-Allow-Headers": "Content-Type",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
  };
}

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...corsHeaders(),
    },
  });
}

function html(text, headOnly) {
  return new Response(headOnly ? null : text, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      ...corsHeaders(),
    },
  });
}

async function readJson(request, requireBody) {
  const text = await request.text();
  if (!text) {
    if (requireBody) return { error: "empty body", status: 400 };
    return { value: {} };
  }
  try {
    const value = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { error: "invalid json", status: 400 };
    }
    return { value };
  } catch {
    return { error: "invalid json", status: 400 };
  }
}

function kvKey(token) {
  return "mbox:" + token;
}

function newToken() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function validateToken(token) {
  const t = String(token || "").trim();
  if (!t) return { error: "missing token" };
  if (!TOKEN_RE.test(t)) return { error: "invalid token" };
  return { token: t };
}

function hasForbidden(obj) {
  if (obj && typeof obj === "object") {
    if (Array.isArray(obj)) {
      for (const item of obj) {
        const hit = hasForbidden(item);
        if (hit) return hit;
      }
    } else {
      for (const [k, v] of Object.entries(obj)) {
        if (FORBIDDEN.test(String(k).trim())) {
          return "device identifier field rejected: " + k;
        }
        const hit = hasForbidden(v);
        if (hit) return hit;
      }
    }
  }
  return null;
}

function numFinite(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function cleanPoint(row) {
  const lat = numFinite(row.lat);
  const lon = numFinite(row.lon);
  if (lat === null || lon === null) return "lat/lon required and must be numeric";
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return "lat/lon out of range";
  const mode = String(row.mode == null ? "GNSS" : row.mode).trim().toUpperCase();
  if (!MODES.has(mode)) return "mode must be one of " + [...MODES].sort().join(",");
  let speed = 0;
  if (row.speed_mps != null && row.speed_mps !== "") {
    speed = numFinite(row.speed_mps);
    if (speed === null || speed < 0 || speed > 120) return "speed_mps out of range [0, 120]";
  }
  let acc = null;
  if (row.acc_m != null && row.acc_m !== "") {
    acc = numFinite(row.acc_m);
    if (acc === null || acc < 0 || acc > 10000) return "acc_m out of range [0, 10000]";
  }
  const queued = row.queued === true || row.queued === 1 || row.queued === "1" || row.queued === "true";
  let t = row.t != null ? numFinite(row.t) : row.t_client != null ? numFinite(row.t_client) : null;
  if (t !== null && t > 1e12) t = t / 1000;
  return {
    lat,
    lon,
    mode,
    speed_mps: speed,
    acc_m: acc,
    queued,
    t,
  };
}

function cleanIngest(payload) {
  const forbidden = hasForbidden(payload);
  if (forbidden) return forbidden;
  const tok = validateToken(payload.token);
  if (tok.error) return tok.error;
  if (Array.isArray(payload.points)) {
    if (!payload.points.length) return "empty points";
    if (payload.points.length > MAX_INGEST_POINTS) {
      return "too many points (max " + MAX_INGEST_POINTS + ")";
    }
    const points = [];
    for (const p of payload.points) {
      if (!p || typeof p !== "object") return "bad point";
      const one = cleanPoint(p);
      if (typeof one === "string") return one;
      points.push(one);
    }
    return { token: tok.token, points };
  }
  const one = cleanPoint(payload);
  if (typeof one === "string") return one;
  return { token: tok.token, points: [one] };
}

async function loadBox(env, token) {
  if (!env.MAILBOX) return null;
  const raw = await env.MAILBOX.get(kvKey(token), "json");
  if (!raw || typeof raw !== "object") return null;
  const now = Date.now() / 1000;
  if (Number(raw.expires_at) <= now) {
    await env.MAILBOX.delete(kvKey(token));
    return null;
  }
  return raw;
}

async function saveBox(env, box) {
  const now = Date.now() / 1000;
  const ttl = Math.max(60, Math.floor(box.expires_at - now));
  await env.MAILBOX.put(kvKey(box.token), JSON.stringify(box), { expirationTtl: ttl });
}

async function openBox(env, token) {
  if (!env.MAILBOX) {
    return json(503, { ok: false, error: "MAILBOX KV binding missing" });
  }
  const now = Date.now() / 1000;
  let tok = token;
  if (tok != null && String(tok).trim() !== "") {
    const v = validateToken(tok);
    if (v.error) return json(400, { ok: false, error: v.error });
    tok = v.token;
    const existing = await loadBox(env, tok);
    if (existing) {
      existing.expires_at = now + TTL_S;
      await saveBox(env, existing);
      return json(200, { ok: true, token: tok, expires_in_s: TTL_S, existing: true });
    }
  } else {
    tok = newToken();
  }
  const box = { token: tok, created: now, expires_at: now + TTL_S, seq: 0, points: [] };
  await saveBox(env, box);
  return json(200, { ok: true, token: tok, expires_in_s: TTL_S, existing: false });
}

async function ingest(env, payload) {
  if (!env.MAILBOX) {
    return json(503, { ok: false, error: "MAILBOX KV binding missing" });
  }
  const cleaned = cleanIngest(payload);
  if (typeof cleaned === "string") {
    return json(400, { ok: false, error: cleaned });
  }
  const box = await loadBox(env, cleaned.token);
  if (!box) {
    return json(400, { ok: false, error: "unknown or expired pairing token" });
  }
  const now = Date.now() / 1000;
  box.expires_at = now + TTL_S;
  for (const row of cleaned.points) {
    box.seq = (box.seq || 0) + 1;
    box.points.push({
      seq: box.seq,
      t: row.t || now,
      lat: row.lat,
      lon: row.lon,
      mode: row.mode,
      speed_mps: row.speed_mps,
      acc_m: row.acc_m,
      queued: Boolean(row.queued),
    });
  }
  if (box.points.length > MAX_POINTS) {
    box.points = box.points.slice(box.points.length - MAX_POINTS);
  }
  await saveBox(env, box);
  return json(200, {
    ok: true,
    accepted: cleaned.points.length,
    n_points: box.points.length,
    expires_in_s: TTL_S,
  });
}

async function feed(env, token, { consume, after }) {
  const v = validateToken(token);
  if (v.error) return json(400, { ok: false, error: v.error });
  const box = await loadBox(env, v.token);
  if (!box) {
    return json(400, { ok: false, error: "unknown or expired pairing token" });
  }
  const now = Date.now() / 1000;
  const selected = (box.points || []).filter((p) => (p.seq || 0) > after);
  if (consume) {
    box.points = (box.points || []).filter((p) => (p.seq || 0) <= after);
    await saveBox(env, box);
  }
  return json(200, {
    ok: true,
    token: v.token,
    points: selected,
    n: selected.length,
    cursor: box.seq || 0,
    expires_in_s: Math.max(0, Math.floor(box.expires_at - now)),
  });
}
