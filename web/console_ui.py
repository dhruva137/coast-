"""The COAST Command console page.

Deliberately dependency-free: no CDN, no map tiles, no web fonts. Everything
renders on a canvas so the whole console works with the venue's wifi dead, which
is the same property the phone app claims and the same one the demo relies on.

Design species is an operations console, not a phone app: dense, structured,
dark, information-first. See design_v3/00_DESIGN_THESIS.md and
cursor_v3/PHASE_1_SHELL.md.
"""

from __future__ import annotations

PAIR_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>COAST · pair this phone</title>
<style>
  :root{--bg:#07090D;--panel:#0C1016;--line:#1C232D;--text:#E8EDF2;--dim:#8B97A6;
        --faint:#5A6673;--accent:#00D4AA;--gnss:#4A9EFF;--bad:#FF6B6B;--warn:#FFD166;
        --mono:ui-monospace,Menlo,Consolas,monospace;
        --tap:48px;--safe-b:env(safe-area-inset-bottom,0px);--safe-t:env(safe-area-inset-top,0px)}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html{height:100%}
  body{margin:0;min-height:100dvh;background:var(--bg);color:var(--text);
       font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       padding:calc(16px + var(--safe-t)) 16px calc(20px + var(--safe-b))}
  .wrap{max-width:28rem;margin:0 auto}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:18px}
  .brand b{letter-spacing:.02em;font-size:17px}
  .brand small{display:block;color:var(--dim);font-size:11px;letter-spacing:.08em;
               text-transform:uppercase;font-weight:500;margin-top:2px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
        padding:16px;margin-bottom:12px}
  h1{font-size:20px;margin:0 0 6px;line-height:1.25}
  p{margin:0 0 12px;color:var(--dim);font-size:15px}
  .num{font-family:var(--mono);font-variant-numeric:tabular-nums}
  button{width:100%;min-height:var(--tap);border:0;border-radius:12px;padding:14px 16px;
         font:600 16px system-ui;cursor:pointer;margin-bottom:10px}
  .go{background:var(--accent);color:#04120E}
  .go:disabled{opacity:.45}
  .ghost{background:transparent;color:var(--dim);border:1px solid var(--line)}
  .status{display:flex;align-items:center;gap:10px;min-height:var(--tap);padding:12px 14px;border-radius:12px;
          background:#11161E;border:1px solid var(--line);margin-bottom:12px}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--faint);flex:0 0 auto}
  .dot.on{background:var(--accent);box-shadow:0 0 10px var(--accent)}
  .dot.bad{background:var(--bad)}
  .kv{display:grid;grid-template-columns:auto 1fr;gap:8px 14px;font-size:14px}
  .kv .k{color:var(--faint)}
  .kv .v{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
  .note{font-size:13px;color:var(--faint);line-height:1.5;margin:0}
  code{font-family:var(--mono);font-size:12px;color:var(--accent);word-break:break-all}
  .warn{background:#1a1508;border:1px solid #46370f;color:var(--warn);border-radius:12px;
        padding:12px 14px;font-size:13px;margin-bottom:14px}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <svg width="28" height="28" viewBox="0 0 108 108" aria-hidden="true">
      <path fill="#00D4AA" d="M54,24 L70,60 L54,51 L38,60 Z"/>
      <path stroke="#00D4AA" stroke-width="7" stroke-linecap="round" stroke-opacity=".75" d="M54,67 L54,73"/>
      <path stroke="#00D4AA" stroke-width="7" stroke-linecap="round" stroke-opacity=".4" d="M54,80 L54,84"/>
    </svg>
    <div><b>COAST</b><small>pair this phone</small></div>
  </div>

  <div class="warn" id="ctx"></div>

  <div class="card">
    <h1>Put this phone on the console</h1>
    <p>Your position streams to the laptop dashboard. Nothing else is sent. Stop anytime.</p>
    <div class="status"><span class="dot" id="dot"></span><span id="msg">Not sharing yet</span></div>
    <button class="go" id="go" type="button">Start sharing my position</button>
    <button class="ghost" id="stop" type="button" style="display:none">Stop &amp; unpair</button>
    <div class="kv" id="stats" style="display:none">
      <span class="k">Sent</span><span class="v" id="n">0</span>
      <span class="k">Latitude</span><span class="v" id="la">—</span>
      <span class="k">Longitude</span><span class="v" id="lo">—</span>
      <span class="k">Accuracy</span><span class="v" id="ac">—</span>
      <span class="k">Speed</span><span class="v" id="sp">—</span>
    </div>
  </div>

  <div class="card">
    <p class="note"><b style="color:var(--text)">What this demo is.</b>
      This page shares GPS for the fleet map. Dead reckoning after GPS dies is what the
      <b>COAST Android app</b> does.</p>
    <p class="note" style="margin-top:10px">Install the app for the real thing:</p>
    <a href="/download/apk" style="text-decoration:none"><button class="ghost" type="button">Download the APK</button></a>
  </div>

  <div class="card">
    <p class="note">Session <code id="tok">—</code><br/>
      Expires automatically. No account, no device ID.</p>
  </div>
</div>

<script>
"use strict";
const qs = new URLSearchParams(location.search);
const token = qs.get("s") || "";
const base = (qs.get("lan") || location.origin).replace(/\/+$/,"");
let watchId = null, sent = 0;
const $ = s => document.querySelector(s);
$("#tok").textContent = token ? token.slice(0,10)+"…" : "missing";

if(!window.isSecureContext && location.hostname!=="localhost" && location.hostname!=="127.0.0.1"){
  $("#ctx").textContent = "Browsers only give location to https or localhost. Over plain http on LAN, use the COAST app instead.";
} else { $("#ctx").style.display="none"; }

function post(p){
  const b = {
    token, lat: p.coords.latitude, lon: p.coords.longitude,
    mode: "GNSS",
    speed_mps: (p.coords.speed==null||Number.isNaN(p.coords.speed)) ? 0 : p.coords.speed,
    acc_m: p.coords.accuracy, source: "browser-geolocation"
  };
  fetch(base+"/ingest", {method:"POST", headers:{"Content-Type":"application/json"},
                         body: JSON.stringify(b)})
    .then(r=>r.json())
    .then(d=>{
      if(!d.ok){ $("#dot").className="dot bad"; $("#msg").textContent = d.error || "rejected"; return; }
      sent++;
      $("#dot").className="dot on";
      $("#msg").textContent = "Sharing as "+(d.label||"this phone");
      $("#stats").style.display="grid";
      $("#n").textContent=sent;
      $("#la").textContent=b.lat.toFixed(5);
      $("#lo").textContent=b.lon.toFixed(5);
      $("#ac").textContent=(b.acc_m==null?"—":Math.round(b.acc_m)+" m");
      $("#sp").textContent=(b.speed_mps*3.6).toFixed(1)+" km/h";
    })
    .catch(()=>{ $("#dot").className="dot bad"; $("#msg").textContent="Cannot reach console at "+base; });
}

$("#go").onclick = () => {
  if(!token){ $("#dot").className="dot bad"; $("#msg").textContent="No pairing token in this link."; return; }
  if(!navigator.geolocation){ $("#dot").className="dot bad"; $("#msg").textContent="No geolocation on this browser."; return; }
  $("#go").disabled = true; $("#msg").textContent="Asking for location permission…";
  watchId = navigator.geolocation.watchPosition(post,
    err => { $("#dot").className="dot bad";
             $("#msg").textContent = "Location refused ("+err.message+")";
             $("#go").disabled=false; },
    {enableHighAccuracy:true, maximumAge:1000, timeout:15000});
  $("#go").style.display="none"; $("#stop").style.display="block";
};
$("#stop").onclick = () => {
  if(watchId!=null) navigator.geolocation.clearWatch(watchId);
  watchId=null; $("#dot").className="dot"; $("#msg").textContent="Stopped sharing";
  $("#stop").style.display="none"; $("#go").style.display="block"; $("#go").disabled=false;
};
</script>
</body>
</html>
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>COAST Command</title>
<link rel="stylesheet" href="/static/tokens.css" />
<link rel="stylesheet" href="/static/components.css" />
<link rel="stylesheet" href="/static/engine_viz.css" />
<link rel="stylesheet" href="/static/engine_calc.css" />
<style>
  /* Page-local layout — browser ops console standards (Linear/Grafana density). */
  html,body{height:100%;margin:0;overflow:hidden;background:var(--bg);color:var(--text);
            font-family:var(--font);font-size:var(--fs-body);line-height:1.45}
  [hidden]{display:none !important}
  #app:not([hidden]){display:grid !important}
  #front-door:not([hidden]){display:flex !important}
  .view{display:flex;flex:1 1 auto;min-height:0;min-width:0;padding:16px;gap:12px}
  .view[hidden]{display:none !important}
  #engine-viz-host{flex:1 1 auto;min-height:280px;min-width:0;padding:10px;
                   display:flex;flex-direction:column}

  .view-panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
              display:flex;flex-direction:column;min-height:0;min-width:0;padding:0}
  .view-panel > h2{margin:0;padding:11px 14px;font-size:11px;letter-spacing:.09em;
                   text-transform:uppercase;color:var(--dim);font-weight:600;
                   border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px}
  .view-panel > h2 .sp{margin-left:auto;font-weight:400;letter-spacing:0;text-transform:none}
  .body{padding:12px 14px;overflow:auto;min-height:0}
  .body.flush{padding:0}
  .rail{width:262px;flex:0 0 262px}
  .pairrail{width:300px;flex:0 0 300px}
  .grow{flex:1 1 auto;min-width:0}
  .col{display:flex;flex-direction:column;gap:14px;min-height:0}
  .cwrap{position:relative;flex:1 1 auto;min-height:0}
  canvas{display:block;width:100%;height:100%}
  .legend{position:absolute;left:12px;bottom:10px;display:flex;gap:14px;font-size:11px;
          color:var(--dim);background:color-mix(in srgb,var(--bg) 78%,transparent);
          padding:6px 10px;border-radius:6px;border:1px solid var(--line)}
  .legend i{display:inline-block;width:14px;height:0;border-top-width:2px;
            border-top-style:solid;vertical-align:middle;margin-right:5px}
  .scalebar{position:absolute;right:12px;bottom:10px;font-size:11px;color:var(--dim);
            background:color-mix(in srgb,var(--bg) 78%,transparent);padding:5px 9px;
            border-radius:6px;border:1px solid var(--line)}

  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  .muted{color:var(--dim);font-size:var(--fs-meta)}
  .tiny{color:var(--faint);font-size:11px}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
       font-size:11.5px;color:var(--accent);word-break:break-all}

  .dev{display:flex;gap:10px;padding:9px 10px;border-radius:8px;cursor:pointer;
       border:1px solid transparent;align-items:flex-start}
  .dev:hover{background:var(--panel2)}
  .dev.sel{background:var(--panel2);border-color:var(--line)}
  .swatch{width:9px;height:9px;border-radius:50%;margin-top:5px;flex:0 0 auto}
  .dev .nm{font-weight:600;font-size:13px}
  .dev .meta{color:var(--dim);font-size:11px}
  .dev.off .nm,.dev.off .meta{color:var(--faint)}

  .kv{display:grid;grid-template-columns:1fr auto;gap:5px 12px;font-size:12.5px}
  .kv .k{color:var(--dim)}
  .kv .v{font-family:ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}

  .stat{display:flex;flex-direction:column;gap:2px;padding:9px 0}
  .stat .lab{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
  .stat .val{font-size:23px;font-family:ui-monospace,Menlo,Consolas,monospace;
             font-variant-numeric:tabular-nums;line-height:1.15}
  .stat .sub{font-size:11px;color:var(--dim)}

  button.act{background:var(--accent);color:var(--bg);border:0;border-radius:8px;
             padding:9px 15px;font:600 13px var(--font);cursor:pointer}
  button.act:hover{filter:brightness(1.08)}
  button.act:disabled{opacity:.45;cursor:default;filter:none}
  button.ghost{background:transparent;color:var(--dim);border:1px solid var(--line);
               border-radius:8px;padding:8px 13px;font:13px var(--font);cursor:pointer}
  button.ghost:hover{color:var(--text);border-color:var(--dim)}
  button.danger{border-color:color-mix(in srgb,var(--bad) 40%,var(--line));color:var(--bad)}
  button.danger:hover{background:color-mix(in srgb,var(--bad) 12%,var(--panel));color:var(--bad)}

  .qrbox{background:#fff;border-radius:10px;padding:10px;display:inline-block;line-height:0}
  .qrbox svg{width:186px;height:186px;display:block}
  .empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
         gap:12px;height:100%;color:var(--dim);text-align:center;padding:24px}
  .banner-box{padding:9px 12px;border-radius:8px;font-size:12.5px;margin-bottom:10px}
  .banner-box.err{background:color-mix(in srgb,var(--bad) 12%,var(--panel));
                  border:1px solid color-mix(in srgb,var(--bad) 40%,var(--line));color:var(--bad)}
  .banner-box.note{background:var(--panel2);border:1px solid var(--line);color:var(--dim)}
  .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}

  table{border-collapse:collapse;width:100%;font-size:12.5px}
  th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--faint);font-weight:600;font-size:10.5px;letter-spacing:.07em;
     text-transform:uppercase;position:sticky;top:0;background:var(--panel)}
  td.n{font-family:ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums;
       text-align:right;white-space:nowrap}
  .tagm{color:var(--accent)} .tagn{color:var(--warn)} .tagd{color:var(--gnss)} .tagh{color:var(--faint)}

  .bars{display:flex;flex-direction:column;gap:11px}
  .bar{display:flex;flex-direction:column;gap:4px}
  .bar .top{display:flex;justify-content:space-between;font-size:12px}
  .bar .top b{font-family:ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums;font-weight:600}
  .track{height:9px;border-radius:5px;background:var(--panel2);overflow:hidden;border:1px solid var(--line)}
  .fill{height:100%;border-radius:5px;background:var(--accent)}
  .fill.dim{background:var(--gnss)} .fill.warnc{background:var(--warn)}

  /* Mark entrance ≤600ms, once */
  @keyframes mark-in{
    from{opacity:0;transform:translateY(8px) scale(.96)}
    to{opacity:1;transform:none}
  }
  @keyframes crumb-in{
    from{stroke-dashoffset:24;opacity:0}
    to{stroke-dashoffset:0;opacity:1}
  }
  .mark-anim{animation:mark-in 480ms var(--ease) both}
  .mark-anim .crumb{stroke-dasharray:24;animation:crumb-in 520ms var(--ease) both}
  .mark-anim .crumb.c2{animation-delay:80ms}

  /* Sign-in overlay */
  .signin-backdrop{position:fixed;inset:0;z-index:900;display:flex;align-items:center;
                   justify-content:center;padding:24px;
                   background:color-mix(in srgb,var(--bg) 72%,transparent)}
  .signin-backdrop[hidden]{display:none !important}
  .signin-card{width:min(360px,100%);background:var(--panel);border:1px solid var(--line);
               border-radius:var(--radius);padding:var(--panel-pad)}
  .signin-card h2{margin:0 0 8px;font-size:var(--fs-title)}
  .signin-card p{margin:0 0 16px;color:var(--dim);font-size:var(--fs-meta)}
  .signin-card input{width:100%;padding:10px 12px;margin-bottom:12px;border-radius:var(--radius);
                     border:1px solid var(--line);background:var(--panel2);color:var(--text);
                     font:inherit}
  .signin-err{color:var(--bad);font-size:var(--fs-meta);margin:0 0 10px;min-height:1.2em}

  .front-door__proof.is-error{grid-template-columns:1fr}
  .front-door__proof .state{min-height:0;padding:0}

  @media (max-width:1180px){
    .view{flex-direction:column;overflow:auto}
    .rail,.pairrail{width:auto;flex:0 0 auto}
    .rail .body{max-height:210px}
    .cwrap{min-height:300px}
    .view-panel.grow{min-height:340px}
  }
  @media (max-width:640px){
    .view{padding:10px;gap:10px}
    .qrbox svg{width:150px;height:150px}
    .app-header__ops .op-name{max-width:7em;overflow:hidden;text-overflow:ellipsis}
  }
</style>
</head>
<body>

<!-- ========== FRONT DOOR ========== -->
<section id="front-door" class="front-door" aria-label="COAST entry">
  <canvas class="front-door__bg" id="door-bg" aria-hidden="true"></canvas>
  <div class="front-door__content">
    <div class="front-door__brand">
      <svg class="front-door__mark mark-anim" viewBox="0 0 108 108" aria-hidden="true">
        <path fill="currentColor" d="M54,24 L70,60 L54,51 L38,60 Z"/>
        <path class="crumb" stroke="currentColor" stroke-width="7" stroke-linecap="round"
              stroke-opacity=".75" fill="none" d="M54,67 L54,73"/>
        <path class="crumb c2" stroke="currentColor" stroke-width="7" stroke-linecap="round"
              stroke-opacity=".4" fill="none" d="M54,80 L54,84"/>
      </svg>
      <div class="front-door__name">COAST</div>
      <div class="front-door__tag">GNSS-denied navigation</div>
    </div>
    <p class="front-door__claim">Navigation that keeps working when GPS doesn't.</p>
    <div class="front-door__proof" id="door-proof" aria-live="polite">
      <div class="skeleton skeleton--num" style="margin:0 auto"></div>
      <div class="skeleton skeleton--num" style="margin:0 auto"></div>
      <div class="skeleton skeleton--num" style="margin:0 auto"></div>
    </div>
    <div class="front-door__cta">
      <button type="button" class="btn btn--primary" id="btn-enter">Enter Command Console</button>
      <button type="button" class="btn btn--ghost" id="btn-signin">Operator sign-in</button>
    </div>
    <div class="front-door__foot">SIH 2026 · PS 26168 · ISRO / Dept. of Space</div>
  </div>
</section>

<!-- ========== OPERATOR SIGN-IN ========== -->
<div class="signin-backdrop" id="signin-modal" hidden>
  <form class="signin-card" id="signin-form" autocomplete="off">
    <h2>Operator sign-in</h2>
    <p>Session passcode — no accounts. Phones keep pairing without this.</p>
    <div class="signin-err" id="signin-err"></div>
    <input type="password" id="signin-pw" name="passcode" placeholder="Passcode"
           aria-label="Operator passcode" />
    <div class="row" style="justify-content:flex-end;gap:8px">
      <button type="button" class="btn btn--ghost" id="signin-cancel">Cancel</button>
      <button type="submit" class="btn btn--primary">Sign in</button>
    </div>
  </form>
</div>

<!-- ========== COMMAND SHELL ========== -->
<div id="app" class="app-shell" hidden>
  <div class="app-top">
    <div class="banner" id="open-banner" hidden>Open mode — no operator passcode configured</div>
    <div class="conn-banner" id="coast-conn-banner" role="status">Connection lost — showing last-known state</div>
    <header class="app-header">
      <div class="app-header__mark">
        <svg viewBox="0 0 108 108" aria-hidden="true" width="24" height="24">
          <path fill="currentColor" d="M54,24 L70,60 L54,51 L38,60 Z"/>
          <path stroke="currentColor" stroke-width="7" stroke-linecap="round"
                stroke-opacity=".75" fill="none" d="M54,67 L54,73"/>
          <path stroke="currentColor" stroke-width="7" stroke-linecap="round"
                stroke-opacity=".4" fill="none" d="M54,80 L54,84"/>
        </svg>
        <span>COAST</span>
        <span class="op-name" id="op-name" style="color:var(--dim);font-size:var(--fs-meta);font-weight:500;margin-left:4px">open</span>
      </div>
      <div class="app-header__status" aria-label="Live status">
        <span class="pill" id="pill-srv"><span class="pill__dot" id="p-srv"></span>
          <span class="pill__label" id="p-srv-t">server</span></span>
        <span class="pill" id="pill-dev"><span class="pill__dot" id="p-dev"></span>
          <span class="pill__label" id="p-dev-t">0 devices</span></span>
        <span class="pill" id="pill-trn"><span class="pill__dot" id="p-trn"></span>
          <span class="pill__label" id="p-trn-t">idle</span></span>
        <span class="pill pill--ok"><span class="pill__dot"></span>
          <span class="pill__label">offline-capable</span></span>
        <button type="button" class="btn btn--ghost" id="btn-signout"
                style="min-height:32px;padding:4px 10px;font-size:var(--fs-meta)">Sign out</button>
      </div>
    </header>
  </div>

  <nav class="icon-rail" aria-label="Views">
    <button type="button" class="icon-rail__item is-active" data-nav="fleet" aria-current="page">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <circle cx="12" cy="12" r="3"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/></svg>
      <span class="icon-rail__label">Fleet</span>
    </button>
    <button type="button" class="icon-rail__item" data-nav="engine">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <rect x="4" y="6" width="16" height="12" rx="2"/><path d="M8 10h8M8 14h5"/></svg>
      <span class="icon-rail__label">Engine</span>
    </button>
    <button type="button" class="icon-rail__item" data-nav="training">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <path d="M4 19V5M4 19h16"/><path d="M8 15l3-6 3 3 3-7"/></svg>
      <span class="icon-rail__label">Training</span>
    </button>
    <button type="button" class="icon-rail__item" data-nav="evidence">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <path d="M7 4h7l3 3v13H7z"/><path d="M14 4v3h3"/></svg>
      <span class="icon-rail__label">Evidence</span>
    </button>
    <button type="button" class="icon-rail__item" data-nav="sessions">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/></svg>
      <span class="icon-rail__label">Sessions</span>
    </button>
  </nav>

  <main class="app-main">
    <!-- FLEET -->
    <section class="view is-active" data-view="fleet" data-live id="tab-fleet">
      <div class="view-panel rail col" style="gap:0">
        <h2>Devices <span class="sp num" id="dev-count">0</span></h2>
        <div class="body" id="dev-list" style="flex:1 1 auto">
          <div class="state state--empty">
            <p class="state__title">No phone paired yet</p>
            <p class="state__body">Scan the code, or play the UK IO-VNBD demo track (same geography as training).</p>
          </div>
        </div>
        <div style="border-top:1px solid var(--line);padding:12px 14px;display:flex;flex-direction:column;gap:8px">
          <button class="act" id="btn-uk-demo" style="width:100%">Play UK demo track</button>
          <button class="ghost" id="btn-uk-demo-stop" style="width:100%;display:none">Stop UK demo</button>
          <button class="ghost" id="btn-forget-all" style="width:100%">Forget all devices</button>
          <p class="tiny" id="uk-demo-hint" style="margin:0">Coventry / Midlands · measured S-S1 filter trace · GNSS → IDR handover</p>
        </div>
      </div>

      <div class="view-panel grow">
        <h2>Live tracks <span class="sp tiny" id="fleet-hint">GNSS blue · IDR teal — where the line changes colour, GPS was gone</span></h2>
        <div class="cwrap">
          <canvas id="cv-fleet"></canvas>
          <div class="legend">
            <span><i style="border-color:var(--gnss)"></i>GNSS</span>
            <span><i style="border-color:var(--accent)"></i>IDR (dead reckoning)</span>
          </div>
          <div class="scalebar num" id="fleet-scale">—</div>
        </div>
      </div>

      <div class="view-panel pairrail">
        <h2>Pair a phone</h2>
        <div class="body" id="pair-body">
          <div class="row" style="justify-content:center"><div class="qrbox" id="qr"></div></div>
          <p class="muted" style="margin:12px 0 4px">Scan with the COAST app. The code carries a
            one-time token plus both a LAN and a relay endpoint — the phone uses whichever answers.</p>
          <p class="tiny" style="margin:0 0 10px">Endpoint <code id="pair-url">—</code></p>
          <div class="row">
            <button class="ghost" id="btn-newqr">New code</button>
            <a class="ghost" id="btn-apk" href="/download/apk"
               style="text-decoration:none;display:inline-block">Download APK</a>
          </div>
          <div id="privacy" style="margin-top:16px"></div>
        </div>
      </div>
    </section>

    <!-- ENGINE -->
    <section class="view" data-view="engine" data-live id="tab-engine" hidden>
      <div class="view-panel grow col" style="gap:0;padding:0">
        <h2>Estimator — live arithmetic
          <span class="sp tiny" id="ec-src">real IO-VNBD strip · Coventry UK · CAN speed truth</span>
        </h2>

        <div class="ec">
          <!-- ── column 1: what the sensors report ── -->
          <div class="ec-col ec-in">
            <div class="ec-h">SENSOR INPUT<span class="ec-hz" id="ec-hz">10 Hz</span></div>
            <div class="ec-grp">
              <div class="ec-lbl">accelerometer · phone frame · m/s²</div>
              <div class="ec-vec">
                <span>a<sub>x</sub></span><b class="num" id="ec-ax">—</b>
                <span>a<sub>y</sub></span><b class="num" id="ec-ay">—</b>
                <span>a<sub>z</sub></span><b class="num" id="ec-az">—</b>
              </div>
              <canvas class="ec-scope" id="ec-scope-a"></canvas>
            </div>
            <div class="ec-grp">
              <div class="ec-lbl">gyroscope · rad/s</div>
              <div class="ec-vec">
                <span>ω<sub>x</sub></span><b class="num" id="ec-gx">—</b>
                <span>ω<sub>y</sub></span><b class="num" id="ec-gy">—</b>
                <span>ω<sub>z</sub></span><b class="num" id="ec-gz">—</b>
              </div>
              <canvas class="ec-scope" id="ec-scope-g"></canvas>
            </div>
            <div class="ec-grp">
              <div class="ec-lbl">gravity estimate · m/s²</div>
              <div class="ec-vec">
                <span>g<sub>x</sub></span><b class="num" id="ec-grx">—</b>
                <span>g<sub>y</sub></span><b class="num" id="ec-gry">—</b>
                <span>g<sub>z</sub></span><b class="num" id="ec-grz">—</b>
              </div>
            </div>
          </div>

          <!-- ── column 2: the calculation itself ── -->
          <div class="ec-col ec-calc">
            <div class="ec-h">COMPUTATION<span class="ec-hz" id="ec-t">t = 0.00 s</span></div>

            <div class="ec-stage" id="ec-s1">
              <div class="ec-sn">1</div>
              <div class="ec-sb">
                <div class="ec-st">Gravity removal</div>
                <code class="ec-eq">a<sub>lin</sub> = a − g</code>
                <div class="ec-out num" id="ec-alin">—</div>
                <div class="ec-note">Skip this and any tilt leaks ~9.8 m/s² into the
                  horizontal axes — velocity explodes within a second.</div>
              </div>
            </div>

            <div class="ec-stage" id="ec-s2">
              <div class="ec-sn">2</div>
              <div class="ec-sb">
                <div class="ec-st">Heading integration</div>
                <code class="ec-eq">ψ ← ψ − ω<sub>z</sub>·Δt</code>
                <div class="ec-out num" id="ec-dpsi">—</div>
                <div class="ec-note">Gyro drifts. The compass does not, but it is noisy —
                  we measured 16.87% vs 7.22% drift over 60 s.</div>
              </div>
            </div>

            <div class="ec-stage" id="ec-s3">
              <div class="ec-sn">3</div>
              <div class="ec-sb">
                <div class="ec-st">Speed integration <span class="ec-zupt" id="ec-zupt">ZUPT</span></div>
                <code class="ec-eq">v ← v + a<sub>y</sub>·Δt</code>
                <div class="ec-out num" id="ec-vint">—</div>
                <div class="ec-note">Zero-velocity update clamps v to 0 when the IMU says
                  stationary. <span id="ec-zn">0</span> clamps so far.</div>
              </div>
            </div>

            <div class="ec-stage" id="ec-s4">
              <div class="ec-sn">4</div>
              <div class="ec-sb">
                <div class="ec-st">Dead reckoning</div>
                <code class="ec-eq">Δlat = v·cos ψ·Δt / R &nbsp; Δlon = v·sin ψ·Δt / (R·cos φ)</code>
                <div class="ec-out num" id="ec-dpos">—</div>
                <div class="ec-note">Error integrates. This is the whole problem, and why
                  the map goes inside the filter loop.</div>
              </div>
            </div>
          </div>

          <!-- ── column 3: what comes out ── -->
          <div class="ec-col ec-out-col">
            <div class="ec-h">OUTPUT<span class="ec-mode" id="ec-mode">—</span></div>

            <div class="ec-card">
              <div class="ec-lbl">heading · degrees</div>
              <div class="ec-kv"><span>gyro</span><b class="num" id="ec-hg">—</b>
                <i class="num" id="ec-hge">—</i></div>
              <div class="ec-kv"><span>compass</span><b class="num" id="ec-hm">—</b>
                <i class="num" id="ec-hme">—</i></div>
              <div class="ec-kv ec-truth"><span>truth</span><b class="num" id="ec-ht">—</b><i></i></div>
            </div>

            <div class="ec-card">
              <div class="ec-lbl">speed · m/s</div>
              <div class="ec-kv"><span>estimate</span><b class="num" id="ec-ve">—</b><i></i></div>
              <div class="ec-kv ec-truth"><span>CAN truth</span><b class="num" id="ec-vc">—</b><i></i></div>
            </div>

            <div class="ec-card ec-err">
              <div class="ec-lbl">position error · metres</div>
              <div class="ec-big num" id="ec-err">—</div>
              <canvas class="ec-errchart" id="ec-errchart"></canvas>
            </div>

            <div class="ec-card">
              <div class="ec-lbl">throughput</div>
              <div class="ec-kv"><span>µs / sample</span><b class="num" id="ec-us">—</b><i></i></div>
              <div class="ec-kv"><span>samples</span><b class="num" id="ec-n">—</b><i></i></div>
            </div>
          </div>
        </div>

        <div class="ec-bar">
          <button class="btn btn--primary" id="ec-run">Run estimator</button>
          <button class="btn btn--ghost" id="ec-stop" disabled>Stop</button>
          <label class="ec-rate">speed
            <select id="ec-rate">
              <option value="1">1×</option>
              <option value="4" selected>4×</option>
              <option value="10">10×</option>
              <option value="20">20×</option>
            </select>
          </label>
          <span class="ec-status tiny" id="ec-status">idle</span>
        </div>
      </div>

      <div class="view-panel rail col" style="gap:0">
        <h2>Requirement</h2>
        <div class="body">
          <div class="stat"><span class="lab">Problem statement</span>
            <span class="val num">200 Hz</span><span class="sub">edge engine, FOG-grade IMU</span></div>
          <div class="stat"><span class="lab">Phone</span>
            <span class="val num">10 Hz</span><span class="sub">met on device</span></div>
          <hr style="border:0;border-top:1px solid var(--line);margin:14px 0"/>
          <div class="stat"><span class="lab">Worst measured config</span>
            <span class="val num" id="eng-worst">—</span>
            <span class="sub">180-particle graph filter, 100% GNSS-denied</span></div>
          <p class="tiny">We publish the <b>worst</b> configuration, not the best. A headline nobody
            can attack by picking a harder scenario is worth more than a bigger number.</p>
        </div>
        <h2>Measured throughput <span class="sp tiny">core/cpp/apps/README.md</span></h2>
        <div class="body" id="eng-body" style="flex:1 1 auto">
          <div class="state state--loading">
            <div class="skeleton skeleton--block"></div>
            <p class="state__body">Loading engine benchmarks…</p>
          </div>
        </div>
      </div>
    </section>

    <!-- TRAINING -->
    <section class="view" data-view="training" data-live id="tab-train" hidden>
      <div class="view-panel grow col" style="gap:0">
        <h2>Model learning — held-out UK drive
          <span class="sp tiny" id="tr-held">IO-VNBD · Coventry / Midlands · re-integrated after every epoch</span></h2>
        <div class="cwrap"><canvas id="cv-traj"></canvas>
          <div class="legend">
            <span><i style="border-color:var(--text)"></i>CAN truth</span>
            <span><i style="border-color:var(--bad)"></i>hold-last-speed baseline</span>
            <span><i style="border-color:var(--accent)"></i>COAST @ epoch <b class="num" id="tr-ep">0</b></span>
          </div>
          <div class="scalebar num" id="traj-scale">—</div>
        </div>
        <div style="border-top:1px solid var(--line);height:220px;flex:0 0 220px">
          <canvas id="cv-loss"></canvas>
        </div>
      </div>

      <div class="view-panel rail">
        <h2>Run</h2>
        <div class="body">
          <div id="tr-banner"></div>
          <div class="stat"><span class="lab">Epoch</span>
            <span class="val" id="s-ep">—</span><span class="sub" id="s-ep-sub">not started</span></div>
          <div class="stat"><span class="lab">Train loss</span>
            <span class="val" id="s-loss">—</span><span class="sub" id="s-loss-sub">phase-normalised on chart</span></div>
          <div class="stat"><span class="lab">Held-out RMSE</span>
            <span class="val" id="s-rmse">—</span><span class="sub">m/s · never trained on</span></div>
          <div class="stat"><span class="lab">σ mean</span>
            <span class="val" id="s-sigma">—</span><span class="sub" id="s-sigma-sub">shown when demo emits it</span></div>
          <div class="stat"><span class="lab">Elapsed</span><span class="val" id="s-el">—</span></div>
          <div style="height:10px"></div>
          <button class="act" id="btn-train" style="width:100%">Train now</button>
          <p class="tiny" style="margin-top:10px">Runs <code>python -m lab.demo</code> as a real
            subprocess on <b>local IO-VNBD (UK)</b> drives. Every point plotted is parsed from its
            stdout — nothing is simulated. If it fails you will see the error, not a curve.</p>
          <div class="banner-box note" style="margin-top:10px">Fast re-run. The committed
            mapfilter headline (lower median <b>position error</b>, not drift %) lives under
            <code>lab/stress/results/mapfilter/</code> — same UK corpus.</div>
          <div id="figs"></div>
        </div>
      </div>
    </section>

    <!-- EVIDENCE -->
    <section class="view" data-view="evidence" data-live id="tab-evidence" hidden>
      <div class="view-panel grow">
        <h2>Claim registry <span class="sp tiny">every number re-derived from its measured file</span></h2>
        <div class="body flush"><table id="claims"><tbody><tr><td class="tiny">loading…</td></tr></tbody></table></div>
      </div>
      <div class="view-panel rail">
        <h2>How to read this</h2>
        <div class="body">
          <p class="muted"><code>tools/verify_claims.py</code> re-reads every source file and fails
            the build if a slide states a number the registry does not know.</p>
          <p class="muted">The registry deliberately includes our <b>negative</b> results. A registry
            containing only wins is a registry nobody should believe.</p>
          <div class="kv" style="margin-top:14px">
            <span class="k"><span class="tagm">measured</span></span><span class="v">ran it</span>
            <span class="k"><span class="tagn">measured-negative</span></span><span class="v">a wash or a loss</span>
            <span class="k"><span class="tagd">derived</span></span><span class="v">arithmetic on measured</span>
            <span class="k"><span class="tagh">historical</span></span><span class="v">our own bug story</span>
          </div>
        </div>
      </div>
    </section>

    <!-- SESSIONS -->
    <section class="view" data-view="sessions" id="tab-sessions" hidden>
      <div class="view-panel grow">
        <h2>Sessions</h2>
        <div class="body">
          <div class="state state--empty">
            <p class="state__title">No session archive yet</p>
            <p class="state__body">Live fleet tracks stay in memory for this console run.
              Persistent session replay lands with Phase 2.</p>
          </div>
        </div>
      </div>
    </section>
  </main>
</div>

<script src="/static/engine_viz.js"></script>
<script src="/static/engine_calc.js"></script>
<script src="/static/app.js"></script>
<script>
"use strict";
const $ = s => document.querySelector(s);
const fmt = (v, d=2) => (v===null||v===undefined||Number.isNaN(v)) ? "—" : Number(v).toFixed(d);
const commas = v => Math.round(v).toLocaleString("en-US");

const CLAIM_DOOR = [
  { id:"map_in_loop_improvement_x",
    fmt: v => Number(v).toFixed(2)+"×",
    label:"lower median position error vs naive DR" },
  { id:"perfect_gyro_fail_pct",
    fmt: v => Math.round(Number(v))+"%",
    label:"a perfect gyro still fails" },
  { id:"edge_worst_case_multiple",
    fmt: v => Math.round(Number(v))+"×",
    label:"the 200 Hz edge requirement" },
];

let session = { open_mode: true, authenticated: false, operator: "open" };
let consoleReady = false;

/* ---------- front door claims ---------- */
async function loadDoorClaims(){
  const box = $("#door-proof");
  try{
    const r = await fetch("/api/claims");
    const d = await r.json();
    if(!r.ok || d.error || !Array.isArray(d.claims) || !d.claims.length){
      const err = (d && d.error) || ("Could not read claim registry (HTTP "+r.status+")");
      box.className = "front-door__proof is-error";
      box.innerHTML = `<div class="state state--error"><p class="state__title">Claims unavailable</p>
        <p class="state__body">${err}</p></div>`;
      return;
    }
    const byId = {};
    d.claims.forEach(c => { byId[c.id] = c; });
    const missing = CLAIM_DOOR.filter(h => !byId[h.id] || byId[h.id].value==null);
    if(missing.length){
      box.className = "front-door__proof is-error";
      box.innerHTML = `<div class="state state--error"><p class="state__title">Claims incomplete</p>
        <p class="state__body">Missing: ${missing.map(m=>m.id).join(", ")}</p></div>`;
      return;
    }
    box.className = "front-door__proof";
    box.innerHTML = CLAIM_DOOR.map(h => {
      const c = byId[h.id];
      return `<div><div class="front-door__proof-value num">${h.fmt(c.value)}</div>
        <div class="front-door__proof-label">${h.label}</div></div>`;
    }).join("");
  }catch(e){
    box.className = "front-door__proof is-error";
    box.innerHTML = `<div class="state state--error"><p class="state__title">Claims unavailable</p>
      <p class="state__body">Could not reach /api/claims.</p></div>`;
  }
}

/* Subtle texture: committed trajectory overlay figure, if served */
function paintDoorBg(){
  const cv = $("#door-bg");
  if(!cv) return;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || window.innerWidth;
  const h = cv.clientHeight || window.innerHeight;
  cv.width = Math.max(1, Math.round(w*dpr));
  cv.height = Math.max(1, Math.round(h*dpr));
  const g = cv.getContext("2d");
  g.setTransform(dpr,0,0,dpr,0,0);
  g.clearRect(0,0,w,h);
  const img = new Image();
  img.onload = () => {
    g.globalAlpha = 0.14;
    const s = Math.max(w/img.width, h/img.height);
    const iw = img.width*s, ih = img.height*s;
    g.drawImage(img, (w-iw)/2, (h-ih)/2, iw, ih);
    g.globalAlpha = 1;
  };
  img.onerror = () => {};
  img.src = "/figures/trajectory_overlay.png";
}

/* ---------- session / enter ---------- */
async function refreshSession(){
  try{
    const r = await fetch("/api/session");
    if(!r.ok){ session = { open_mode:true, authenticated:false, operator:"open" }; }
    else {
      const d = await r.json();
      session = {
        open_mode: !!d.open_mode,
        authenticated: !!d.authenticated,
        operator: d.operator || (d.open_mode ? "open" : "operator"),
      };
    }
  }catch(_){
    session = { open_mode:true, authenticated:false, operator:"open" };
  }
  $("#op-name").textContent = session.operator;
  const ban = $("#open-banner");
  if(ban){
    if(session.open_mode){ ban.hidden = false; }
    else { ban.hidden = true; }
  }
  return session;
}

function showConsole(){
  document.body.classList.add("is-console");
  document.body.classList.remove("is-door");
  $("#front-door").hidden = true;
  $("#app").hidden = false;
  if(window.COAST && typeof window.COAST.setConsoleActive === "function"){
    window.COAST.setConsoleActive(true);
  }
  if(!consoleReady){
    consoleReady = true;
    bootConsole();
  }
  resizeAll();
  if(window.COAST) window.COAST.setView(window.COAST.getState().view || "fleet");
}

function showFrontDoor(){
  document.body.classList.add("is-door");
  document.body.classList.remove("is-console");
  $("#app").hidden = true;
  $("#front-door").hidden = false;
  if(window.COAST && typeof window.COAST.setConsoleActive === "function"){
    window.COAST.setConsoleActive(false);
  }
  paintDoorBg();
}

function canEnter(){
  return session.open_mode || session.authenticated;
}

$("#btn-enter").onclick = async () => {
  await refreshSession();
  if(canEnter()) showConsole();
  else openSignIn(true);
};

$("#btn-signin").onclick = () => openSignIn(false);
$("#signin-cancel").onclick = () => { $("#signin-modal").hidden = true; };
$("#signin-modal").addEventListener("click", e => {
  if(e.target === $("#signin-modal")) $("#signin-modal").hidden = true;
});

let enterAfterSignIn = false;
function openSignIn(thenEnter){
  enterAfterSignIn = !!thenEnter;
  $("#signin-err").textContent = "";
  $("#signin-pw").value = "";
  $("#signin-modal").hidden = false;
  $("#signin-pw").focus();
}

$("#signin-form").onsubmit = async e => {
  e.preventDefault();
  const pw = $("#signin-pw").value;
  $("#signin-err").textContent = "";
  try{
    const r = await fetch("/api/login", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ passcode: pw }),
    });
    const d = await r.json().catch(()=>({}));
    if(!r.ok || !d.ok){
      $("#signin-err").textContent = d.error || "Sign-in failed";
      return;
    }
    $("#signin-modal").hidden = true;
    await refreshSession();
    showConsole();
  }catch(err){
    $("#signin-err").textContent = "Could not reach /api/login";
  }
};

$("#btn-signout").onclick = async () => {
  try{ await fetch("/api/logout", { method:"POST" }); }catch(_){}
  await refreshSession();
  showFrontDoor();
};

document.addEventListener("coast:command", ev => {
  const a = ev.detail && ev.detail.action;
  if(a === "signout"){ $("#btn-signout").click(); }
  else if(a === "pair"){ if(window.COAST) window.COAST.setView("fleet"); newQR(); }
  else if(a === "train"){ if(window.COAST) window.COAST.setView("training"); $("#btn-train").click(); }
});

document.addEventListener("coast:view", ev => {
  setTimeout(resizeAll, 30);
  if(ev.detail && ev.detail.view === "engine") ensureEngineViz();
});

/* ---------- canvas helpers ---------- */
function fit(cv){
  const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  cv.width = Math.max(1, Math.round(r.width*dpr));
  cv.height = Math.max(1, Math.round(r.height*dpr));
  const g = cv.getContext("2d");
  g.setTransform(dpr,0,0,dpr,0,0);
  return {g, w:r.width, h:r.height};
}
function niceScale(m){
  const steps=[1,2,5,10,20,50,100,200,500,1000,2000,5000,10000];
  for(const s of steps) if(m<=s) return s;
  return 20000;
}
function projector(paths, w, h, pad){
  let xs=[], ys=[];
  for(const p of paths) for(const q of p){ xs.push(q[0]); ys.push(q[1]); }
  if(!xs.length) return null;
  const x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
  const sx=(w-2*pad)/Math.max(x1-x0,1e-6), sy=(h-2*pad)/Math.max(y1-y0,1e-6);
  const s=Math.min(sx,sy);
  const cx=(x0+x1)/2, cy=(y0+y1)/2;
  return {
    s,
    px: x => w/2 + (x-cx)*s,
    py: y => h/2 - (y-cy)*s,
    spanM: Math.max(x1-x0, y1-y0)
  };
}
function stroke(g, pts, pr, color, width, dash){
  if(!pts || pts.length<2) return;
  g.save(); g.strokeStyle=color; g.lineWidth=width; g.lineJoin="round"; g.lineCap="round";
  if(dash) g.setLineDash(dash);
  g.beginPath();
  pts.forEach((q,i)=>{ const X=pr.px(q[0]), Y=pr.py(q[1]); i?g.lineTo(X,Y):g.moveTo(X,Y); });
  g.stroke(); g.restore();
}
function gridBg(g,w,h){
  g.fillStyle=getComputedStyle(document.documentElement).getPropertyValue("--bg").trim()||"#07090D";
  g.fillRect(0,0,w,h);
  g.strokeStyle="#121821"; g.lineWidth=1;
  for(let x=0;x<w;x+=44){g.beginPath();g.moveTo(x+.5,0);g.lineTo(x+.5,h);g.stroke();}
  for(let y=0;y<h;y+=44){g.beginPath();g.moveTo(0,y+.5);g.lineTo(w,y+.5);g.stroke();}
}

/* ================= FLEET ================= */
let fleet = {devices:[]}, selected = null, pairToken = null;

function llToXY(lat, lon, lat0, lon0){
  const R=6371000, rad=Math.PI/180;
  return [ (lon-lon0)*rad*R*Math.cos(lat0*rad), (lat-lat0)*rad*R ];
}
function drawFleet(){
  const cv=$("#cv-fleet"); if(!cv || !cv.getBoundingClientRect().width) return;
  const {g,w,h}=fit(cv); gridBg(g,w,h);
  const devs=fleet.devices.filter(d=>d.points && d.points.length);
  if(!devs.length){
    g.fillStyle=getComputedStyle(document.documentElement).getPropertyValue("--faint").trim()||"#5A6673";
    g.font="13px system-ui"; g.textAlign="center";
    g.fillText("No positions yet — pair a phone, or Play UK demo track.", w/2, h/2);
    $("#fleet-scale").textContent="—"; return;
  }
  const lat0=devs[0].points[0].lat, lon0=devs[0].points[0].lon;
  const paths=devs.map(d=>d.points.map(p=>llToXY(p.lat,p.lon,lat0,lon0)));
  const pr=projector(paths,w,h,44); if(!pr) return;

  const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim()||"#00D4AA";
  const gnss = getComputedStyle(document.documentElement).getPropertyValue("--gnss").trim()||"#4A9EFF";

  devs.forEach((d,i)=>{
    const pts=paths[i]; let run=[pts[0]]; let mode=d.points[0].mode;
    for(let k=1;k<pts.length;k++){
      const m=d.points[k].mode;
      if(m!==mode){
        run.push(pts[k]);
        stroke(g,run,pr, mode==="IDR"?accent:gnss, mode==="IDR"?3:2.2, mode==="HOLD"?[4,4]:null);
        run=[pts[k]]; mode=m;
      } else run.push(pts[k]);
    }
    stroke(g,run,pr, mode==="IDR"?accent:gnss, mode==="IDR"?3:2.2, mode==="HOLD"?[4,4]:null);

    const last=pts[pts.length-1], X=pr.px(last[0]), Y=pr.py(last[1]);
    const sel = selected===d.device_id;
    g.save();
    if(d.online){ g.shadowColor=d.color; g.shadowBlur=sel?18:10; }
    g.fillStyle=d.online?d.color:"#3A434F";
    g.beginPath(); g.arc(X,Y,sel?7:5.5,0,7); g.fill();
    g.restore();
    g.fillStyle=d.online?"#E8EDF2":"#5A6673"; g.font="600 11px system-ui"; g.textAlign="left";
    g.fillText(d.label, X+10, Y+4);
  });

  const barM=niceScale(pr.spanM/4), px=barM*pr.s;
  $("#fleet-scale").textContent = (barM>=1000? (barM/1000)+" km" : barM+" m");
  g.strokeStyle="#5A6673"; g.lineWidth=2; g.beginPath();
  g.moveTo(w-24-px,h-38); g.lineTo(w-24,h-38); g.stroke();
}

function renderDevices(){
  const el=$("#dev-list");
  $("#dev-count").textContent = fleet.devices.length;
  const on = fleet.devices.filter(d=>d.online).length;
  $("#p-dev-t").textContent = fleet.devices.length + (fleet.devices.length===1?" device":" devices");
  $("#pill-dev").className = "pill" + (on ? " pill--ok" : "");
  if(!fleet.devices.length){
    el.innerHTML=`<div class="state state--empty">
      <p class="state__title">No phone paired yet</p>
      <p class="state__body">Scan the code to put your phone on the map.</p></div>`;
    $("#privacy").innerHTML=""; return;
  }
  el.innerHTML = fleet.devices.map(d=>`
    <div class="dev ${selected===d.device_id?"sel":""} ${d.online?"":"off"}" data-id="${d.device_id}">
      <span class="swatch" style="background:${d.color}"></span>
      <span class="grow">
        <div class="nm">${d.label}</div>
        <div class="meta num">${d.latest? (d.latest.mode+" · "+fmt(d.latest.speed_mps*3.6,0)+" km/h") : "waiting for fix"}</div>
        <div class="meta num">${d.n_points} pts · ${fmt(d.distance_m,0)} m${d.online?"":" · "+fmt(d.age_s,0)+"s ago"}</div>
      </span>
    </div>`).join("");
  el.querySelectorAll(".dev").forEach(n=>n.onclick=()=>{
    selected = selected===n.dataset.id ? null : n.dataset.id;
    renderDevices(); drawFleet(); loadPrivacy();
  });
}

async function loadPrivacy(){
  const box=$("#privacy");
  if(!selected){ box.innerHTML=""; return; }
  try{
    const r=await fetch("/api/privacy/"+encodeURIComponent(selected));
    if(!r.ok){ box.innerHTML=""; return; }
    const d=await r.json();
    box.innerHTML=`
      <h2 style="border:0;padding:0 0 8px;font-size:11px;letter-spacing:.09em;
                 text-transform:uppercase;color:var(--dim)">What we know about ${d.label}</h2>
      <div class="kv">
        ${Object.entries(d.held).map(([k,v])=>`<span class="k">${k.replace(/_/g," ")}</span>
          <span class="v">${typeof v==="number"?commas(v):v}</span>`).join("")}
      </div>
      <p class="tiny" style="margin:10px 0 4px">Not collected:</p>
      <ul class="tiny" style="margin:0 0 10px;padding-left:16px;color:var(--faint)">
        ${d.not_collected.map(x=>`<li>${x}</li>`).join("")}</ul>
      <button class="ghost danger" id="btn-forget" style="width:100%">Delete this device and all its data</button>`;
    $("#btn-forget").onclick=async()=>{
      await fetch("/api/forget/"+encodeURIComponent(selected),{method:"POST"});
      selected=null; await pollFleet();
    };
  }catch(e){ box.innerHTML=""; }
}

async function pollFleet(){
  try{
    const r=await fetch("/api/fleet");
    if(!r.ok) throw new Error("fleet "+r.status);
    fleet=await r.json();
    if(window.COAST) window.COAST.markConnectionOk();
    $("#p-srv").className="pill__dot";
    $("#pill-srv").className="pill pill--ok";
    $("#p-srv-t").textContent="server up";
    renderDevices(); drawFleet();
    if(selected && !fleet.devices.some(d=>d.device_id===selected)){ selected=null; $("#privacy").innerHTML=""; }
  }catch(e){
    $("#pill-srv").className="pill pill--warn";
    $("#p-srv-t").textContent="server unreachable";
  }
}

async function newQR(){
  try{
    const r=await fetch("/api/pair/new",{method:"POST"});
    const d=await r.json();
    pairToken=d.token;
    $("#qr").innerHTML = d.qr_svg || '<div style="color:#000;padding:20px;font:12px system-ui">QR encoder unavailable</div>';
    $("#pair-url").textContent = d.payload;
  }catch(e){ $("#pair-url").textContent="could not mint a pairing code"; }
}
$("#btn-newqr").onclick=newQR;
$("#btn-forget-all").onclick=async()=>{ await fetch("/api/forget_all",{method:"POST"}); selected=null; pollFleet(); };

function setUkDemoUi(running){
  const go=$("#btn-uk-demo"), stop=$("#btn-uk-demo-stop"), hint=$("#uk-demo-hint");
  if(go){ go.disabled=!!running; go.textContent=running?"Playing UK demo…":"Play UK demo track"; }
  if(stop) stop.style.display=running?"block":"none";
  if(hint && !running) hint.textContent="Coventry / Midlands · measured S-S1 filter trace · GNSS → IDR handover";
}
$("#btn-uk-demo").onclick=async()=>{
  setUkDemoUi(true);
  try{
    const r=await fetch("/api/demo/uk/start",{method:"POST"});
    const d=await r.json();
    if(!d.ok){ setUkDemoUi(false); alert(d.error||"UK demo failed"); return; }
    selected=d.device_id||"demo-uk-s1";
    const hint=$("#uk-demo-hint");
    if(hint) hint.textContent=(d.meta&&d.meta.region?d.meta.region:"UK")+" · "+(d.n_points||"?")+" pts · GNSS→IDR";
    await pollFleet();
  }catch(e){ setUkDemoUi(false); }
};
$("#btn-uk-demo-stop").onclick=async()=>{
  try{ await fetch("/api/demo/uk/stop",{method:"POST"}); }catch(_){}
  setUkDemoUi(false); selected=null; await pollFleet();
};

/* ================= TRAINING ================= */
let tr = {truth:[], hold:[], epochs:[], cur:null, prev:null, mix:1, held:"",
          holdBaselineRmse:null, switchEpoch:null};
function objOf(e){ return String(e.objective||e.mode||"").toUpperCase(); }
function heldOf(e){
  const v = (typeof e.held_rmse==="number") ? e.held_rmse
    : (typeof e.rmse==="number" ? e.rmse : NaN);
  return Number.isFinite(v) ? v : null;
}
function drawTraj(){
  const cv=$("#cv-traj"); if(!cv || !cv.getBoundingClientRect().width) return;
  const {g,w,h}=fit(cv); gridBg(g,w,h);
  const all=[tr.truth,tr.hold,tr.cur].filter(p=>p&&p.length);
  if(!all.length){
    g.fillStyle="#5A6673"; g.font="13px system-ui"; g.textAlign="center";
    g.fillText("Press Train — the estimated path will converge onto the truth as it learns.", w/2, h/2);
    return;
  }
  const pr=projector(all,w,h,46); if(!pr) return;
  stroke(g,tr.hold,pr,"#FF6B6B",2,[6,5]);
  stroke(g,tr.truth,pr,"#E8EDF2",2.4);
  if(tr.prev && tr.mix<1){ g.globalAlpha=1-tr.mix; stroke(g,tr.prev,pr,"#00D4AA",2.2); g.globalAlpha=1; }
  if(tr.cur){ g.globalAlpha=tr.mix; stroke(g,tr.cur,pr,"#00D4AA",3); g.globalAlpha=1; }
  const barM=niceScale(pr.spanM/4);
  $("#traj-scale").textContent = (barM>=1000?(barM/1000)+" km":barM+" m");
  g.strokeStyle="#5A6673"; g.lineWidth=2; g.beginPath();
  g.moveTo(w-24-barM*pr.s,h-38); g.lineTo(w-24,h-38); g.stroke();
}
/* Two-band honesty chart: headline held RMSE ≠ train loss (never raw MSE+NLL together). */
function paintTrainBand(g, box, title, yLabel, series, flatRefs, markerIdx, nEpochs){
  const {x:left,y:top,w,h}=box;
  if(w<40||h<28) return;
  const pad={l:36,r:8,t:16,b:14};
  const pw=w-pad.l-pad.r, ph=h-pad.t-pad.b;
  if(pw<8||ph<8) return;
  const finite=[];
  series.forEach(s=>s.vals.forEach(v=>{ if(v!=null && Number.isFinite(v)) finite.push(v); }));
  flatRefs.forEach(r=>{ if(Number.isFinite(r.value)) finite.push(r.value); });
  const maxY=Math.max(0.05, ...(finite.length?finite:[1]));
  const n=Math.max(1, nEpochs);
  const xOf=i=>left+pad.l+(n<=1?pw/2:(i/(n-1))*pw);
  const yOf=v=>top+pad.t+(1-v/maxY)*ph;
  g.strokeStyle="rgba(220,228,236,0.08)"; g.lineWidth=1;
  g.fillStyle="#5A6673"; g.font="9px ui-monospace,monospace"; g.textAlign="left";
  for(let k=0;k<=2;k++){
    const yy=top+pad.t+(k/2)*ph;
    g.beginPath(); g.moveTo(left+pad.l,yy); g.lineTo(left+pad.l+pw,yy); g.stroke();
    g.fillText(((1-k/2)*maxY).toFixed(2), left+2, yy+3);
  }
  g.fillStyle="#E8EDF2"; g.font="10px system-ui"; g.fillText(title, left+pad.l, top+11);
  g.fillStyle="#5A6673"; g.font="8px ui-monospace,monospace"; g.fillText(yLabel, left+2, top+pad.t-2);
  flatRefs.forEach(r=>{
    if(!Number.isFinite(r.value)) return;
    const yy=yOf(r.value);
    g.setLineDash([5,4]); g.strokeStyle=r.color; g.lineWidth=1.2;
    g.beginPath(); g.moveTo(left+pad.l,yy); g.lineTo(left+pad.l+pw,yy); g.stroke();
    g.setLineDash([]);
    g.fillStyle=r.color; g.font="9px ui-monospace,monospace";
    g.fillText(r.label+" "+fmt(r.value,2), left+pad.l+4, yy-3);
  });
  if(markerIdx!=null && markerIdx>=0 && markerIdx<n){
    const xx=xOf(markerIdx);
    g.setLineDash([3,3]); g.strokeStyle="rgba(255,179,0,0.85)"; g.lineWidth=1.2;
    g.beginPath(); g.moveTo(xx, top+pad.t); g.lineTo(xx, top+pad.t+ph); g.stroke();
    g.setLineDash([]);
    g.fillStyle="#ffb300"; g.font="9px system-ui";
    g.fillText("MSE → NLL", xx+3, top+pad.t+10);
  }
  series.forEach(s=>{
    const pts=s.vals.map((v,i)=>(v!=null&&Number.isFinite(v)?{i,v}:null)).filter(Boolean);
    if(!pts.length) return;
    g.strokeStyle=s.color; g.fillStyle=s.color; g.lineWidth=1.8; g.lineJoin="round";
    g.beginPath();
    pts.forEach((p,k)=>{ const xx=xOf(p.i), yy=yOf(p.v); k?g.lineTo(xx,yy):g.moveTo(xx,yy); });
    g.stroke();
    pts.forEach(p=>{ g.beginPath(); g.arc(xOf(p.i), yOf(p.v), 2.2, 0, Math.PI*2); g.fill(); });
  });
  let lx=left+pad.l; const ly=top+h-3;
  g.font="9px ui-monospace,monospace";
  series.forEach(s=>{
    if(!s.vals.some(v=>v!=null&&Number.isFinite(v))) return;
    g.fillStyle=s.color; g.fillText(s.label, lx, ly);
    lx += g.measureText(s.label).width + 12;
  });
}
function drawLoss(){
  const cv=$("#cv-loss"); if(!cv || !cv.getBoundingClientRect().width) return;
  const {g,w,h}=fit(cv);
  g.fillStyle="#0C1016"; g.fillRect(0,0,w,h);
  const eps=tr.epochs;
  if(eps.length<1){
    g.fillStyle="#5A6673"; g.font="11px system-ui"; g.textAlign="center";
    g.fillText("Waiting for epoch 1… (no invented curve)", w/2, h/2); return;
  }
  const n=eps.length;
  const held=eps.map(heldOf);
  let baseline=tr.holdBaselineRmse;
  if(baseline==null || !Number.isFinite(baseline)){
    const fromEp=eps.map(e=>e.hold_baseline_rmse).find(v=>typeof v==="number"&&Number.isFinite(v));
    if(fromEp!=null) baseline=fromEp;
  }
  let switchIdx=-1;
  if(tr.switchEpoch!=null){
    switchIdx=eps.findIndex(e=>e.epoch===tr.switchEpoch);
  }
  if(switchIdx<0){
    switchIdx=eps.findIndex((e,i)=>{
      if(i===0) return false;
      return objOf(eps[i-1])==="MSE" && objOf(e)==="NLL";
    });
  }
  const markerIdx=switchIdx>=0?switchIdx:null;
  const mseRaw=eps.map(e=>objOf(e)==="MSE" && Number.isFinite(e.loss)?e.loss:undefined);
  const nllRaw=eps.map(e=>objOf(e)==="NLL" && Number.isFinite(e.loss)?e.loss:undefined);
  const mse0=mseRaw.find(v=>v!=null&&Number.isFinite(v));
  const nll0=nllRaw.find(v=>v!=null&&Number.isFinite(v));
  // Per-phase ÷ start so MSE and NLL never share raw units on one axis.
  const mseLoss=mseRaw.map(v=>v!=null&&mse0!=null&&mse0>0?v/mse0:undefined);
  const nllLoss=nllRaw.map(v=>v!=null&&nll0!=null&&Math.abs(nll0)>1e-12?v/nll0:undefined);
  const gap=6;
  const bandH=(h-gap)/2;
  paintTrainBand(g, {x:0,y:0,w,h:bandH},
    "Held-out RMSE (headline) — is the task improving?", "m/s",
    [{vals:held, color:"#00D4AA", label:"held RMSE"}],
    baseline!=null&&Number.isFinite(baseline)
      ?[{value:baseline, color:"#8A929B", label:"hold-last-speed"}]:[],
    markerIdx, n);
  paintTrainBand(g, {x:0,y:bandH+gap,w,h:bandH},
    "Train loss (secondary) — each phase ÷ its own start", "rel",
    [
      {vals:mseLoss, color:"#FF6B2D", label:"MSE / start"},
      {vals:nllLoss, color:"#C77DFF", label:"NLL / start"},
    ],
    [], markerIdx, n);
}
function animateMix(){
  if(tr.mix<1){ tr.mix=Math.min(1,tr.mix+0.06); drawTraj(); requestAnimationFrame(animateMix); }
}
function onEpoch(e){
  if(typeof e.hold_baseline_rmse==="number" && Number.isFinite(e.hold_baseline_rmse))
    tr.holdBaselineRmse=e.hold_baseline_rmse;
  tr.epochs.push(e);
  if(e.path && e.path.length){ tr.prev=tr.cur; tr.cur=e.path; tr.mix=0; requestAnimationFrame(animateMix); }
  const obj=objOf(e)||"?";
  const held=heldOf(e);
  $("#s-ep").textContent=e.epoch+" / "+e.epochs;
  $("#s-ep-sub").textContent=obj+" objective";
  $("#tr-ep").textContent=e.epoch;
  $("#s-loss").textContent=Number.isFinite(e.loss)?fmt(e.loss,4):"—";
  const lossSub=$("#s-loss-sub"); if(lossSub) lossSub.textContent=obj+" · chart uses phase ÷ start";
  $("#s-rmse").textContent=held!=null?fmt(held,3):"—";
  const sig=$("#s-sigma"), sigSub=$("#s-sigma-sub");
  if(typeof e.sigma_mean==="number" && Number.isFinite(e.sigma_mean)){
    if(sig) sig.textContent=fmt(e.sigma_mean,3);
    if(sigSub) sigSub.textContent="mean predicted σ";
  }else{
    if(sig) sig.textContent="—";
    if(sigSub) sigSub.textContent="not in this epoch payload";
  }
  $("#s-el").textContent=Number.isFinite(e.elapsed_s)?fmt(e.elapsed_s,1)+"s":"—";
  $("#pill-trn").className="pill pill--ok";
  $("#p-trn-t").textContent="training epoch "+e.epoch+(held!=null?" · held "+fmt(held,3):"");
  drawLoss(); drawTraj();
}
function trainBanner(html, cls){ $("#tr-banner").innerHTML = html?`<div class="banner-box ${cls}">${html}</div>`:""; }

$("#btn-train").onclick=async()=>{
  const b=$("#btn-train"); b.disabled=true; b.textContent="Training…";
  tr={truth:[],hold:[],epochs:[],cur:null,prev:null,mix:1,held:"",
      holdBaselineRmse:null, switchEpoch:null};
  $("#s-ep").textContent="—"; $("#s-ep-sub").textContent="not started";
  $("#s-loss").textContent="—";
  const lossSub=$("#s-loss-sub"); if(lossSub) lossSub.textContent="phase-normalised on chart";
  $("#s-rmse").textContent="—";
  const sig=$("#s-sigma"), sigSub=$("#s-sigma-sub");
  if(sig) sig.textContent="—";
  if(sigSub) sigSub.textContent="shown when demo emits it";
  $("#s-el").textContent="—"; $("#tr-ep").textContent="0";
  trainBanner(""); $("#figs").innerHTML=""; drawTraj(); drawLoss();
  try{
    const r=await fetch("/train/start",{method:"POST"});
    const d=await r.json().catch(()=>({}));
    if(!r.ok || d.ok===false){
      trainBanner("Could not start training: "+(d.error||("HTTP "+r.status)),"err");
      b.disabled=false; b.textContent="Train now"; return;
    }
  }catch(e){ trainBanner("Could not start training: "+e,"err"); b.disabled=false; b.textContent="Train now"; return; }
  const es=new EventSource("/train/stream");
  es.onmessage=ev=>{
    let d; try{ d=JSON.parse(ev.data); }catch(_){ return; }
    if(d.type==="traj_ref"){ tr.truth=d.truth||[]; tr.hold=d.hold_baseline||[]; tr.held=d.held||"";
      $("#tr-held").textContent="held-out drive "+tr.held+" · re-integrated after every epoch"; drawTraj(); }
    else if(d.type==="train_baselines"){
      if(typeof d.hold_baseline_rmse==="number" && Number.isFinite(d.hold_baseline_rmse))
        tr.holdBaselineRmse=d.hold_baseline_rmse;
      drawLoss();
    }
    else if(d.type==="objective_switch"){
      if(typeof d.at_epoch==="number") tr.switchEpoch=d.at_epoch;
      trainBanner("Objective switch "+(d.label||"MSE → NLL")+" at epoch "+(d.at_epoch??"?")+
        ". Train-loss chart is phase-normalised — not an accuracy cliff.","note");
      drawLoss();
    }
    else if(d.type==="epoch"){ onEpoch(d); }
    else if(d.type==="error"){ trainBanner("Training failed: "+(d.error||"unknown"),"err"); }
    else if(d.type==="done"){
      es.close(); b.disabled=false; b.textContent="Train again";
      $("#pill-trn").className="pill";
      $("#p-trn-t").textContent = d.returncode===0?"run complete":"run failed";
      if(d.returncode!==0) trainBanner("Training exited with code "+d.returncode+". No numbers are shown for a failed run.","err");
      if(d.figures && d.figures.length){
        $("#figs").innerHTML='<p class="tiny" style="margin:14px 0 6px">Regenerated figures</p>'+
          d.figures.map(f=>`<img src="/figures/${f}?t=${Date.now()}" style="width:100%;border-radius:8px;
            border:1px solid var(--line);margin-bottom:8px" alt="${f}"/>`).join("");
      }
    }
  };
  es.onerror=()=>{ es.close(); b.disabled=false; b.textContent="Train again"; };
};

/* ================= ENGINE ================= */
let engineViz = null;

function _markSyntheticBadge(reason){
  const host = $("#engine-viz-host");
  if(!host) return;
  const b = host.querySelector(".cev-badge");
  if(b) b.textContent = "SYNTHETIC — " + (reason || "offline demo");
}

function ensureEngineViz(){
  if(engineViz) return;
  const host = $("#engine-viz-host");
  if(!host || !window.COASTEngineViz) return;
  engineViz = window.COASTEngineViz.mount(host, {
    autoDemo: true,
    autoLoad: true,
    // Served by coast_console from lab/stress/results/traces/ (latest → newest).
    // Missing file falls back to inline synthetic with SYNTHETIC badge.
    tracePath: "/lab/stress/results/traces/latest.json",
  });
  engineViz.on("load", detail => {
    const meta = detail && detail.meta;
    if(!meta) return;
    const honesty = String(meta.honesty || "").toUpperCase();
    if(meta.synthetic || honesty === "SYNTHETIC"){
      _markSyntheticBadge(meta.source || "recorded plumbing trace");
    }
  });
  engineViz.on("fallback", () => {
    _markSyntheticBadge("inline autoDemo (no trace file)");
  });
}

async function loadEngine(){
  try{
    const r=await fetch("/api/engine"); const d=await r.json();
    if(d.error){
      $("#eng-body").innerHTML=`<div class="state state--error"><p class="state__title">Engine report failed</p>
        <p class="state__body">${d.error}</p></div>`;
      return;
    }
    $("#eng-worst").textContent=commas(d.worst_hz)+" Hz";
    const max=Math.max(...d.scenarios.map(s=>s.max_hz));
    $("#eng-body").innerHTML = `
      <p class="muted" style="margin:0 0 14px">${d.machine}</p>
      <div class="bars">${d.scenarios.map(s=>`
        <div class="bar">
          <div class="top"><span>${s.name}</span>
            <b>${commas(s.min_hz)}–${commas(s.max_hz)} Hz · ${Math.floor(s.min_hz/200)}×</b></div>
          <div class="track"><div class="fill ${s.worst?"":"dim"}"
               style="width:${Math.max(2,100*s.min_hz/max)}%"></div></div>
          <div class="tiny">${s.note}</div>
        </div>`).join("")}
      </div>
      <p class="tiny" style="margin-top:16px">Every bar is the observed spread across repeated runs
        on one machine, single-threaded, with clock-call overhead charged to the engine. The
        200 Hz requirement is the leftmost 0.2% of this axis.</p>`;
  }catch(e){
    $("#eng-body").innerHTML=`<div class="state state--error"><p class="state__title">Could not read engine benchmarks</p>
      <p class="state__body">Fetch /api/engine failed.</p></div>`;
  }
}

/* ================= EVIDENCE ================= */
async function loadClaims(){
  try{
    const r=await fetch("/api/claims"); const d=await r.json();
    if(d.error || !d.claims){
      $("#claims").innerHTML=`<tbody><tr><td><div class="state state--error">
        <p class="state__title">Registry unreadable</p>
        <p class="state__body">${d.error||"No claims array"}</p></div></td></tr></tbody>`;
      return;
    }
    const cls=c=>({measured:"tagm","measured-negative":"tagn",derived:"tagd",historical:"tagh"}[c]||"tagh");
    $("#claims").innerHTML =
      "<thead><tr><th>claim</th><th>value</th><th>confidence</th><th>source</th></tr></thead><tbody>"+
      d.claims.map(c=>`<tr>
        <td><b>${c.id}</b><div class="tiny">${c.statement}</div></td>
        <td class="n">${c.value===null?"—":(Math.abs(c.value)>=1000?commas(c.value):fmt(c.value,2))} ${c.unit}</td>
        <td class="${cls(c.confidence)}">${c.confidence}</td>
        <td class="tiny"><code>${c.source_file}</code></td></tr>`).join("")+"</tbody>";
  }catch(e){
    $("#claims").innerHTML='<tbody><tr><td><div class="state state--error">'+
      '<p class="state__title">Could not read the claim registry</p>'+
      '<p class="state__body">Run <code>python tools/verify_claims.py --json</code>.</p></div></td></tr></tbody>';
  }
}

/* ---------- boot console (after enter) ---------- */
function resizeAll(){ drawFleet(); drawTraj(); drawLoss(); }
function bootConsole(){
  newQR(); pollFleet(); loadEngine(); loadClaims(); loadExistingFigs();
  setInterval(pollFleet, 1000);
  setInterval(pollUkDemo, 1500);
  setTimeout(resizeAll, 60);
}
async function loadExistingFigs(){
  const names=["trajectory_overlay.png","cdf_error.png","drift_comparison.png"];
  const box=$("#figs"); if(!box) return;
  const found=[];
  for(const f of names){
    try{
      const r=await fetch("/figures/"+f,{method:"HEAD"});
      if(r.ok) found.push(f);
    }catch(_){}
  }
  if(!found.length) return;
  box.innerHTML='<p class="tiny" style="margin:14px 0 6px">Last demo figures (UK IO-VNBD)</p>'+
    found.map(f=>`<img src="/figures/${f}?t=${Date.now()}" style="width:100%;border-radius:8px;
      border:1px solid var(--line);margin-bottom:8px" alt="${f}"/>`).join("");
}
async function pollUkDemo(){
  try{
    const r=await fetch("/api/demo/uk");
    if(!r.ok) return;
    const d=await r.json();
    setUkDemoUi(!!d.running);
  }catch(_){}
}
window.addEventListener("resize", () => { paintDoorBg(); resizeAll(); });

/* ---------- initial: front door only ---------- */
document.body.classList.add("is-door");
document.body.classList.remove("is-console");
$("#app").hidden = true;
$("#front-door").hidden = false;
if(window.COAST && typeof window.COAST.setConsoleActive === "function"){
  window.COAST.setConsoleActive(false);
}
loadDoorClaims();
paintDoorBg();
refreshSession();
</script>
</body>
</html>
"""
