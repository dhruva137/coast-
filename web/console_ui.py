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
    <a id="openapp" href="#" style="text-decoration:none"><button class="go" type="button">Open in COAST app</button></a>
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
const appLink = "coast://pair" + location.search;
const openApp = $("#openapp");
if(openApp) openApp.href = appLink;

if(!window.isSecureContext && location.hostname!=="localhost" && location.hostname!=="127.0.0.1"){
  $("#ctx").innerHTML = "This page is plain HTTP, so the <b>browser</b> will not give GPS. "+
    "Open the QR <b>inside the COAST app</b> (SCAN QR), or tap Open in COAST app. "+
    "The app keeps tracking in a tunnel and uploads when radio returns.";
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
  .pair-code{margin:10px 0 8px;padding:14px 12px;text-align:center;
             font:700 clamp(22px,2.4vw,32px)/1.25 ui-monospace,Menlo,Consolas,monospace;
             letter-spacing:.08em;color:var(--accent);word-break:break-all;
             background:#11161E;border:1px solid var(--line);border-radius:12px;
             user-select:all;-webkit-user-select:all}
  .pair-code-lab{display:block;margin:0 0 4px;font:600 10px ui-monospace,Menlo,Consolas,monospace;
                 letter-spacing:.1em;text-transform:uppercase;color:var(--faint);text-align:center}
  .grow{flex:1 1 auto;min-width:0}
  .col{display:flex;flex-direction:column;gap:14px;min-height:0}
  .cwrap{position:relative;flex:1 1 auto;min-height:0}
  canvas{display:block;width:100%;height:100%}
  .map-seg{display:inline-flex;border:1px solid var(--line);border-radius:7px;overflow:hidden;flex:0 0 auto}
  .map-seg button{min-height:28px;padding:3px 9px;border:0;background:transparent;color:var(--dim);
                  font:600 10px ui-monospace,Menlo,Consolas,monospace;letter-spacing:.08em;
                  text-transform:uppercase;cursor:pointer}
  .map-seg button.is-on{background:var(--accent);color:#04120e}
  #fleet-stage .world-map,#fleet-stage > canvas{position:absolute;inset:0;width:100%;height:100%}
  .legend{position:absolute;left:12px;bottom:10px;display:flex;gap:14px;font-size:11px;
          color:var(--dim);background:color-mix(in srgb,var(--bg) 78%,transparent);
          padding:6px 10px;border-radius:6px;border:1px solid var(--line);z-index:3}
  .legend i{display:inline-block;width:14px;height:0;border-top-width:2px;
            border-top-style:solid;vertical-align:middle;margin-right:5px}
  .scalebar{position:absolute;right:12px;bottom:10px;font-size:11px;color:var(--dim);
            background:color-mix(in srgb,var(--bg) 78%,transparent);padding:5px 9px;
            border-radius:6px;border:1px solid var(--line);z-index:3}

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
  .stat .sub.mono{font-family:ui-monospace,Menlo,Consolas,monospace}
  .stat .val.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:20px}

  /* ——— MODEL landing page components ——— */
  .model-io-strip{display:flex;align-items:stretch;gap:10px;margin:10px 0 14px}
  .model-io-box{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:3px;
                padding:10px 12px;border:1px solid var(--line);border-radius:8px;
                background:color-mix(in srgb,var(--panel) 55%,transparent)}
  .model-io-box .lab{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint)}
  .model-io-box .val{font-family:ui-monospace,Menlo,Consolas,monospace;
                     font-size:18px;color:var(--text);font-variant-numeric:tabular-nums}
  .model-io-box .sub{font-size:11px;color:var(--dim);line-height:1.35}
  .model-io-arrow{align-self:center;color:var(--accent);font-size:22px;line-height:1;padding:0 2px}

  .model-legend{display:flex;flex-wrap:wrap;gap:14px;padding:10px 12px;margin-top:10px;
                border-top:1px solid var(--line);font-size:11px;color:var(--dim)}
  .model-legend__item{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
  .model-legend__swatch{display:inline-block;width:9px;height:9px;border-radius:2px}

  .honesty-band{border:1px solid color-mix(in srgb,var(--bad) 30%,var(--line));
                border-radius:8px;padding:10px 12px;
                background:color-mix(in srgb,var(--bad) 5%,transparent)}
  .honesty-band .stat{padding:6px 0}
  .honesty-band .val{font-size:16px;color:var(--text)}
  .honesty-band .val.num{font-size:20px}

  a.model-download{display:block;text-decoration:none;color:inherit;
                   border:1px solid var(--line);border-radius:8px;padding:9px 12px;
                   transition:border-color .15s ease,background .15s ease}
  a.model-download:hover{border-color:var(--accent);
                         background:color-mix(in srgb,var(--accent) 8%,transparent)}
  a.model-download .lab{color:var(--text);text-transform:none;letter-spacing:0;font-size:13px}
  a.model-download .sub{color:var(--dim)}

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

  /* Proper Light Mode Theme for Front Door using CSS Variables */
  .front-door {
    --bg: #f8f9fa;
    --panel: #ffffff;
    --panel2: #f1f3f5;
    --line: #dee2e6;
    --text: #212529;
    --dim: #495057;
    --faint: #868e96;
    --accent: #0070f3;
    
    background-color: var(--bg);
    background-image: 
      linear-gradient(to right, rgba(0, 112, 243, 0.05) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(0, 112, 243, 0.05) 1px, transparent 1px);
    background-size: 40px 40px;
  }
  
  /* Make the new model release badge vibrant */
  .front-door__kicker {
    background: linear-gradient(90deg, #0070f3, #ff3366);
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 112, 243, 0.2);
  }
  .front-door__kicker::before {
    background: white;
  }

  /* Fade out the dark mode canvas so it doesn't clash with light mode text */
  #door-bg {
    opacity: 0.05;
  }
</style>
</head>
<body>

<!-- ========== FRONT DOOR ========== -->
<section id="front-door" class="front-door" aria-label="COAST entry">
  <canvas class="front-door__bg" id="door-bg" aria-hidden="true"></canvas>
  <div class="front-door__content">
    <p class="front-door__kicker">New model release &middot; COAST-VNet-1</p>

    <div class="front-door__brand">
      <svg class="front-door__mark mark-anim" viewBox="0 0 108 108" aria-hidden="true">
        <path fill="currentColor" d="M54,24 L70,60 L54,51 L38,60 Z"/>
        <path class="crumb" stroke="currentColor" stroke-width="7" stroke-linecap="round"
              stroke-opacity=".75" fill="none" d="M54,67 L54,73"/>
        <path class="crumb c2" stroke="currentColor" stroke-width="7" stroke-linecap="round"
              stroke-opacity=".4" fill="none" d="M54,80 L54,84"/>
      </svg>
      <div class="front-door__name">COAST</div>
      <div class="front-door__tag">GNSS-denied navigation &middot; SIH 2026 &middot; ISRO PS 26168</div>
    </div>

    <h1 class="front-door__claim">Navigation that keeps working when GPS doesn&rsquo;t.</h1>
    <p class="front-door__lede">
      COAST-VNet-1 is a small dual-band neural inertial-odometry model &mdash;
      released with the code and the measurements &mdash; that keeps a vehicle&rsquo;s
      position moving through tunnels, urban canyons, and jam zones. Runs on-device
      on a phone at 10&nbsp;Hz. 96,086 parameters. 392&nbsp;KB ONNX. Nothing in the
      cloud.
    </p>

    <div class="front-door__proof" id="door-proof" aria-live="polite">
      <div class="skeleton skeleton--num" style="margin:0 auto"></div>
      <div class="skeleton skeleton--num" style="margin:0 auto"></div>
      <div class="skeleton skeleton--num" style="margin:0 auto"></div>
    </div>

    <div class="front-door__cta">
      <button type="button" class="btn btn--primary" id="btn-enter">Open the console &rarr;</button>
      <a class="btn btn--ghost" href="/docs" target="_blank" rel="noopener">See docs</a>
      <button type="button" class="btn btn--ghost" id="btn-signin">Operator sign-in</button>
    </div>

    <!-- FULL 3D INTERACTIVE SIMULATION -->
    <div id="sim-section" style="
      position: relative;
      width: 100%;
      background: #0a0e14;
      border: 1px solid #1c232d;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 0 0 1px rgba(0,212,170,0.08), 0 20px 60px rgba(0,0,0,0.5);
    ">
      <!-- Top bar -->
      <div style="display:flex; align-items:center; justify-content:space-between; padding:12px 18px; background:#0c1016; border-bottom:1px solid #1c232d;">
        <div style="display:flex; align-items:center; gap:10px;">
          <div style="width:10px;height:10px;border-radius:50%;background:#ff6b6b;"></div>
          <div style="width:10px;height:10px;border-radius:50%;background:#ffd166;"></div>
          <div style="width:10px;height:10px;border-radius:50%;background:#00d4aa;"></div>
          <span style="font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#5a6673;margin-left:8px;font-family:ui-monospace,monospace;">COAST · Live Simulation</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <div id="sim-gps-dot" style="width:8px;height:8px;border-radius:50%;background:#00d4aa;box-shadow:0 0 8px #00d4aa;transition:all 0.4s;"></div>
          <span id="sim-gps-label" style="font-size:11px;font-family:ui-monospace,monospace;color:#00d4aa;letter-spacing:0.05em;transition:color 0.4s;">GNSS LOCKED</span>
        </div>
      </div>

      <!-- Main canvas area -->
      <div style="position:relative; display:flex;">
        <!-- 3D Scene Canvas -->
        <canvas id="sim-canvas" width="1200" height="520" style="display:block; width:100%; max-height:520px; cursor:pointer;"></canvas>

        <!-- Phone mock overlay -->
        <div id="sim-phone" style="
          position:absolute; right:20px; top:50%; transform:translateY(-50%);
          width:120px;
          background:#111827;
          border-radius:18px;
          border: 2px solid #2d3748;
          box-shadow: 0 8px 32px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05);
          overflow:hidden;
          padding:6px;
        ">
          <!-- Phone notch -->
          <div style="height:14px;background:#111827;display:flex;align-items:center;justify-content:center;margin-bottom:4px;">
            <div style="width:32px;height:4px;background:#2d3748;border-radius:2px;"></div>
          </div>
          <!-- Phone screen -->
          <div style="background:#0a0e14;border-radius:12px;overflow:hidden;">
            <!-- Status bar -->
            <div style="padding:4px 8px 2px;display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:7px;color:#9daec0;font-family:system-ui;">10:42</span>
              <div style="display:flex;gap:2px;align-items:center;">
                <div id="phone-signal-bars" style="display:flex;gap:1px;align-items:flex-end;">
                  <div style="width:2px;height:3px;background:#9daec0;border-radius:0.5px;"></div>
                  <div style="width:2px;height:5px;background:#9daec0;border-radius:0.5px;"></div>
                  <div style="width:2px;height:7px;background:#9daec0;border-radius:0.5px;"></div>
                  <div style="width:2px;height:9px;background:#9daec0;border-radius:0.5px;"></div>
                </div>
              </div>
            </div>
            <!-- Map area -->
            <canvas id="sim-phone-canvas" width="216" height="160" style="display:block;width:100%;"></canvas>
            <!-- Notification -->
            <div id="sim-phone-notif" style="margin:4px;padding:6px 8px;background:#0c2820;border-radius:8px;border:1px solid rgba(0,212,170,0.2);">
              <div style="font-size:6px;font-weight:600;color:#00d4aa;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:2px;font-family:system-ui;">COAST</div>
              <div id="sim-phone-notif-text" style="font-size:7px;color:#9daec0;font-family:system-ui;line-height:1.4;">GPS active · tracking</div>
            </div>
            <!-- Metrics -->
            <div style="padding:4px 8px 6px;display:grid;grid-template-columns:1fr 1fr;gap:3px;">
              <div style="background:#0c1016;border-radius:4px;padding:3px 5px;">
                <div style="font-size:5.5px;color:#5a6673;text-transform:uppercase;letter-spacing:0.08em;font-family:system-ui;">Speed</div>
                <div id="phone-speed" style="font-size:9px;color:#e8edf2;font-family:ui-monospace,monospace;font-weight:600;">38 km/h</div>
              </div>
              <div style="background:#0c1016;border-radius:4px;padding:3px 5px;">
                <div style="font-size:5.5px;color:#5a6673;text-transform:uppercase;letter-spacing:0.08em;font-family:system-ui;">Lean</div>
                <div id="phone-lean" style="font-size:9px;color:#e8edf2;font-family:ui-monospace,monospace;font-weight:600;">0.0°</div>
              </div>
              <div style="background:#0c1016;border-radius:4px;padding:3px 5px;">
                <div style="font-size:5.5px;color:#5a6673;text-transform:uppercase;letter-spacing:0.08em;font-family:system-ui;">Mode</div>
                <div id="phone-mode" style="font-size:8px;color:#00d4aa;font-family:ui-monospace,monospace;font-weight:600;">GNSS</div>
              </div>
              <div style="background:#0c1016;border-radius:4px;padding:3px 5px;">
                <div style="font-size:5.5px;color:#5a6673;text-transform:uppercase;letter-spacing:0.08em;font-family:system-ui;">Drift</div>
                <div id="phone-drift" style="font-size:9px;color:#e8edf2;font-family:ui-monospace,monospace;font-weight:600;">0.0%</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Scene info bar -->
      <div style="display:flex; align-items:center; gap:12px; padding:10px 18px; background:#0c1016; border-top:1px solid #1c232d;">
        <div style="flex:1;">
          <div id="sim-scene-label" style="font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:#5a6673;font-family:ui-monospace,monospace;">Scene 1 / 3</div>
          <div id="sim-scene-desc" style="font-size:12px;color:#9daec0;margin-top:2px;">GNSS locked — both vehicles tracking accurately</div>
        </div>
        <div style="display:flex; gap:8px; align-items:center; flex-shrink:0;">
          <button id="sim-btn-prev" style="background:transparent;border:1px solid #1c232d;color:#7a8999;border-radius:6px;padding:5px 10px;font-size:11px;cursor:pointer;font-family:system-ui;">&#8592; Prev</button>
          <button id="sim-btn-play" style="background:#00d4aa;border:none;color:#04120e;border-radius:6px;padding:5px 14px;font-size:11px;font-weight:700;cursor:pointer;font-family:system-ui;min-width:64px;">&#9654; Play</button>
          <button id="sim-btn-next" style="background:transparent;border:1px solid #1c232d;color:#7a8999;border-radius:6px;padding:5px 10px;font-size:11px;cursor:pointer;font-family:system-ui;">Next &#8594;</button>
        </div>
        <div style="display:flex; gap:16px; flex-shrink:0;">
          <div style="display:flex;align-items:center;gap:5px;">
            <div style="width:24px;height:4px;background:#ff3366;border-radius:2px;"></div>
            <span style="font-size:10px;color:#9daec0;">COAST Scooter</span>
          </div>
          <div style="display:flex;align-items:center;gap:5px;">
            <div style="width:24px;height:4px;background:#4a9eff;border-radius:2px;"></div>
            <span style="font-size:10px;color:#9daec0;">Naive Car</span>
          </div>
          <div style="display:flex;align-items:center;gap:5px;">
            <div style="width:24px;height:4px;background:rgba(255,107,107,0.3);border-radius:2px;"></div>
            <span style="font-size:10px;color:#9daec0;">GPS-denied zone</span>
          </div>
        </div>
      </div>
    </div>


    <div class="front-door__section">
      <p class="front-door__section-title">The model at a glance</p>
      <dl class="front-door__spec">
        <div><dt>Architecture</dt><dd>frequency-decoupled CNN-GRU</dd></div>
        <div><dt>Parameters</dt><dd>96,086</dd></div>
        <div><dt>ONNX size</dt><dd>392 KB</dd></div>
        <div><dt>Input</dt><dd>(20, 6) &middot; 2.0 s &middot; 10 Hz</dd></div>
        <div><dt>Output</dt><dd>forward speed + log &sigma;&sup2;</dd></div>
        <div><dt>Runtime</dt><dd>ONNX Runtime Mobile &middot; CPU</dd></div>
      </dl>
    </div>

    <div class="front-door__section">
      <p class="front-door__section-title">Closed-loop benchmark &middot; leave-file-out over 23 IO-VNBD drives</p>
      <p class="front-door__section-body">
        Every number below is measured on held-out data. Train on 22 drives,
        score on the drive never seen &mdash; 12 epochs per fold. Median distance
        error after a mid-route outage; drift as % of distance travelled.
      </p>
      <table class="front-door__bench" aria-label="Closed-loop benchmark against naive baselines">
        <thead>
          <tr>
            <th scope="col">Method</th>
            <th scope="col">Median error</th>
            <th scope="col">Median drift</th>
            <th scope="col">Folds won</th>
          </tr>
        </thead>
        <tbody>
          <tr class="is-us">
            <th scope="row">COAST-VNet-1 &middot; ours</th>
            <td>150.3 m</td>
            <td>18.0%</td>
            <td><span class="front-door__win">9 / 23</span></td>
          </tr>
          <tr>
            <th scope="row">Frozen onset speed &middot; hold last known</th>
            <td>163.2 m</td>
            <td>21.1%</td>
            <td>&mdash;</td>
          </tr>
          <tr>
            <th scope="row">Naive dead reckoning &middot; free-DR integrate</th>
            <td>303.6 m</td>
            <td>36.4%</td>
            <td>&mdash;</td>
          </tr>
          <tr class="is-target">
            <th scope="row">ISRO PS 26168 bar</th>
            <td>&mdash;</td>
            <td>&lt; 10%</td>
            <td>target</td>
          </tr>
        </tbody>
      </table>
      <p class="front-door__section-body" style="margin-top:12px">
        System-level (map-in-loop over 43 outages): <b>2.02&times; lower median
        position error</b> than naive DR. Full protocol and per-fold table live
        in <b>Evidence &middot; Model</b> inside the console.
      </p>
    </div>


    <div class="front-door__foot">SIH 2026 &middot; PS 26168 &middot; ISRO / Dept. of Space</div>
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
    <button type="button" class="icon-rail__item" data-nav="model">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
      <span class="icon-rail__label">Model</span>
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
    <a class="icon-rail__item" href="/static/trace_replay.html" title="Map-in-loop trace replay">
      <svg class="icon-rail__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
        <rect x="3" y="5" width="18" height="14" rx="2"/>
        <path d="M10 9l6 3-6 3z" fill="currentColor" stroke="none"/></svg>
      <span class="icon-rail__label">Replay</span>
    </a>
  </nav>

  <main class="app-main">
    <!-- FLEET -->
    <section class="view is-active" data-view="fleet" data-live id="tab-fleet">
      <div class="view-panel rail col" style="gap:0">
        <h2>Devices <span class="sp num" id="dev-count">0</span></h2>
        <div class="body" id="dev-list" style="flex:1 1 auto">
          <div class="state state--empty fleet-empty">
            <p class="state__title">No phone paired yet</p>
            <p class="state__body">This console owns the recorded UK demo clip the APK also replays. Play it to populate the map with a scripted GNSS→IDR handover <b>and the reverse</b> (IDR→GNSS reacquire), or scan the code to pair a live phone. Fleet playback is not the on-phone particle filter.</p>
            <button class="act fleet-empty__cta" type="button" id="btn-uk-demo-empty">Play UK demo track</button>
            <p class="fleet-empty__legend">
              <span><i style="border-color:var(--gnss)"></i>GNSS</span>
              <span><i style="border-color:var(--accent)"></i>IDR (dead reckoning)</span>
            </p>
          </div>
        </div>
        <div id="fleet-rail-actions" style="border-top:1px solid var(--line);padding:12px 14px;display:none;flex-direction:column;gap:8px">
          <button class="act" id="btn-uk-demo" style="width:100%">Play UK demo track</button>
          <button class="ghost" id="btn-uk-demo-stop" style="width:100%;display:none">Stop UK demo</button>
          <button class="ghost" id="btn-forget-all" style="width:100%">Forget all devices</button>
          <p class="tiny" id="uk-demo-hint" style="margin:0">Coventry / Midlands · APK IO-VNBD clip · GNSS → IDR (20–80 s) → GNSS. Not a live phone PF.</p>
        </div>
      </div>

      <div class="view-panel grow">
        <h2>Fleet map
          <span class="map-seg" id="fleet-mode" role="group" aria-label="Map mode">
            <button type="button" data-mode="world" class="is-on">World</button>
            <button type="button" data-mode="track">Track</button>
          </span>
          <span class="map-seg" id="fleet-tiles" role="group" aria-label="OpenStreetMap style">
            <button type="button" data-style="osm" class="is-on">OSM</button>
            <button type="button" data-style="dark">Dark OSM</button>
          </span>
          <span class="sp tiny" id="fleet-hint">OpenStreetMap · no API key · click a device</span>
        </h2>
        <div class="cwrap" id="fleet-stage">
          <div class="world-map" id="fleet-map-world"></div>
          <canvas id="cv-fleet" hidden></canvas>
          <div class="legend">
            <span><i style="border-color:var(--gnss)"></i>GNSS</span>
            <span><i style="border-color:var(--accent)"></i>IDR (dead reckoning)</span>
            <span><i style="border-color:var(--warn);border-style:dashed"></i>queued catch-up</span>
          </div>
          <div class="scalebar num" id="fleet-scale">drag · scroll zoom</div>
        </div>
      </div>

      <div class="view-panel pairrail">
        <h2>Pair a phone</h2>
        <div class="body" id="pair-body">
          <div class="row" style="justify-content:center"><div class="qrbox" id="qr"></div></div>
          <span class="pair-code-lab">pairing code</span>
          <div class="pair-code" id="pair-code">—</div>
          <div class="pair-phone-entry" style="margin:12px 0;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--panel2)">
            <label class="pair-code-lab" for="pair-phone-code">Type the phone’s 6-digit code</label>
            <div class="row" style="gap:8px;margin-top:8px;align-items:center">
              <input id="pair-phone-code" inputmode="numeric" maxlength="6" pattern="[0-9]{6}"
                     placeholder="123456" autocomplete="one-time-code"
                     style="flex:1;min-width:0;font:700 22px ui-monospace,Menlo,Consolas,monospace;letter-spacing:0.25em;text-align:center;padding:10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--text)"/>
              <button type="button" class="act" id="btn-open-phone-code">Pair</button>
            </div>
            <p class="tiny" id="pair-phone-hint" style="margin:8px 0 0;color:var(--dim)">
              Phone and laptop on the same Wi‑Fi (or relay). No VLAN. Bluetooth is optional later — this path is wireless over IP.
            </p>
          </div>
          <div class="pair-hint">
            <b style="color:var(--text)">Fastest path:</b> phone taps <b>NEW CODE</b>, you type the six digits here.
            Same Wi‑Fi hotspot works; AP isolation is why a public relay exists as backup.
            <div class="pair-ips" id="pair-ips"></div>
          </div>
          <p class="muted" style="margin:12px 0 4px">Scan with the COAST app. The QR is a pairing URL
            (token + LAN + optional relay). The phone queues points while underground and
            flushes them when radio returns.</p>
          <p class="tiny" style="margin:0 0 10px">Endpoint <code id="pair-url">—</code></p>
          <div class="row">
            <button class="act" id="btn-copy-pair" title="Copy the pairing link — paste it into the phone's Connect field">Copy pairing link</button>
            <button class="ghost" id="btn-newqr">New code</button>
            <a class="ghost" id="btn-apk" href="/download/apk"
               style="text-decoration:none;display:inline-block">Download APK</a>
          </div>
          <p class="tiny" id="pair-copy-hint" style="margin:6px 0 0;color:var(--dim)">
            No camera needed — the phone has a <b>Connect</b> field that accepts this link.
          </p>
          <div id="privacy" style="margin-top:16px"></div>
        </div>
      </div>
    </section>

    <!-- MODEL ARCHITECTURE -->
    <section class="view" data-view="model" id="tab-model" hidden>
      <div class="view-panel grow col" style="gap:0;overflow:hidden">
        <h2>COAST-VNet-1
          <span class="sp tiny">frequency-decoupled CNN-GRU &middot; 96,086 params &middot; 392 KB ONNX</span></h2>
        <p class="view-context">
          A phone on a dashboard sees two superimposed signals: vehicle motion (low band) and road / engine vibration (high band).
          Rather than filter one away, COAST-VNet-1 <b>splits the band and treats them as different information</b>,
          then fuses them into a single forward-speed estimate for dead reckoning when GNSS drops.
          Drag to orbit the tensor decomposition. Scroll to zoom.
        </p>

        <div class="model-io-strip" aria-label="Model input and output">
          <div class="model-io-box">
            <span class="lab">Input tensor</span>
            <span class="val mono">(20, 6)</span>
            <span class="sub">2.0 s window &middot; 10 Hz &middot; ax ay az gx gy gz (SI, phone frame)</span>
          </div>
          <div class="model-io-arrow" aria-hidden="true">&rarr;</div>
          <div class="model-io-box">
            <span class="lab">Output</span>
            <span class="val mono">v&#770;<sub>t</sub>, log&#8202;&sigma;&sup2;</span>
            <span class="sub">forward speed (m/s) + a log-variance head</span>
          </div>
        </div>

        <div id="tab-model-canvas" style="flex:1 1 auto;min-height:0;cursor:grab"></div>

        <div class="model-legend" aria-label="Architecture legend">
          <span class="model-legend__item"><span class="model-legend__swatch" style="background:#FACC15"></span>High-band Conv1D &middot; vibration 5&ndash;50 Hz</span>
          <span class="model-legend__item"><span class="model-legend__swatch" style="background:#60A5FA"></span>Low-band GRU &middot; motion 0&ndash;5 Hz</span>
          <span class="model-legend__item"><span class="model-legend__swatch" style="background:#34D399"></span>Dense fusion &middot; forward speed + variance</span>
        </div>
      </div>

      <div class="view-panel rail col" style="gap:0">
        <h2>Validated metrics <span class="sp tiny">measured &middot; not projected</span></h2>
        <div class="body">
          <div class="stat">
            <span class="lab">Closed-loop position error</span>
            <span class="val num">2.02&times;</span>
            <span class="sub">lower median vs naive DR &middot; 43 outages &middot; map-in-loop</span>
          </div>
          <div class="stat">
            <span class="lab">Speed model gain</span>
            <span class="val num">~8%</span>
            <span class="sub">150.3 m vs 163.2 m median &middot; wins 9 / 23 folds</span>
          </div>
          <div class="stat">
            <span class="lab">Edge engine</span>
            <span class="val num">19,682 Hz</span>
            <span class="sub">worst-case throughput &middot; 98&times; the 200 Hz requirement</span>
          </div>
          <div class="stat">
            <span class="lab">GNSS handover</span>
            <span class="val num">&lt;100 ms</span>
            <span class="sub">DR transition, measured on device</span>
          </div>
          <div class="stat">
            <span class="lab">Compass drift</span>
            <span class="val num">7.22%</span>
            <span class="sub">down from 16.87% &middot; 60% of runs pass ISRO bar</span>
          </div>
          <div class="stat">
            <span class="lab">Parameters &middot; size</span>
            <span class="val num">96,086 &middot; 392 KB</span>
            <span class="sub">ONNX Runtime Mobile &middot; CPU only, on device</span>
          </div>
        </div>

        <h2 style="margin-top:20px">Training protocol</h2>
        <div class="body">
          <div class="stat">
            <span class="lab">Dataset</span>
            <span class="val">IO-VNBD</span>
            <span class="sub">23 clean drives &middot; labels from vehicle CAN bus, not phone GNSS</span>
          </div>
          <div class="stat">
            <span class="lab">Protocol</span>
            <span class="val">leave-file-out</span>
            <span class="sub">train on 22, score on the held-out drive only &middot; 12 epochs / fold</span>
          </div>
          <div class="stat">
            <span class="lab">Baseline it must beat</span>
            <span class="val">frozen onset</span>
            <span class="sub">hold last known speed through the outage &middot; strongest naive competitor</span>
          </div>
        </div>

        <h2 style="margin-top:20px">What this release delivers</h2>
        <div class="body">
          <div class="stat">
            <span class="lab">Closed-loop position</span>
            <span class="val num">2.02&times; better</span>
            <span class="sub">median error vs naive DR &middot; measured over 43 GNSS outages</span>
          </div>
          <div class="stat">
            <span class="lab">Beats the strongest naive baseline</span>
            <span class="val num">9 / 23 folds</span>
            <span class="sub">on drives the model has never seen &middot; leave-file-out protocol</span>
          </div>
          <div class="stat">
            <span class="lab">Compass channel drift</span>
            <span class="val num">7.22%</span>
            <span class="sub">down from 16.87% &middot; onset-calibrated fusion on device</span>
          </div>
          <div class="stat" style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
            <span class="lab">Edge throughput headroom</span>
            <span class="val num">98&times;</span>
            <span class="sub">worst-case 19,682 Hz &middot; requirement is 200 Hz</span>
          </div>
        </div>

        <h2 style="margin-top:20px">Downloads</h2>
        <div class="body">
          <a class="stat model-download" href="/static/model_card.md" target="_blank" rel="noopener">
            <span class="lab">Model card &middot; MODEL_CARD.md</span>
            <span class="sub">full protocol, per-fold results, refusals &rarr; open</span>
          </a>
          <div class="stat">
            <span class="lab">ONNX weights</span>
            <span class="sub mono">android/app/src/main/assets/avnet_tiny.onnx</span>
          </div>
        </div>
      </div>
    </section>

    <!-- TRAINING -->
    <section class="view" data-view="training" data-live id="tab-train" hidden>
      <div class="view-panel grow col" style="gap:0">
        <h2>Model learning — held-out UK drive
          <span class="sp tiny" id="tr-held">IO-VNBD · Coventry / Midlands · re-integrated continuously while it trains</span></h2>
        <p class="view-context">Frequency-decoupled VNet (low-band motion / high-band vibration) is the PS speed filter. This quick run is real IO-VNBD &mdash; CAN truth, hold-last-speed baseline, and the model path re-integrated after each epoch. Closed-loop it delivers <b>~8% lower distance error</b> than the strongest naive baseline, winning 9&nbsp;/&nbsp;23 held-out folds.</p>
        <div class="cwrap"><canvas id="cv-traj"></canvas>
          <div class="legend">
            <span><i style="border-color:var(--text)"></i>CAN truth</span>
            <span><i style="border-color:var(--bad)"></i>hold-last-speed baseline</span>
            <span><i style="border-color:var(--accent)"></i>COAST @ epoch <b class="num" id="tr-ep">0</b></span>
          </div>
          <div class="row" style="gap:8px;padding:8px 10px;border-top:1px solid var(--line);align-items:center">
            <span class="tiny" style="color:var(--dim)">Path playback</span>
            <button type="button" class="ghost" data-train-speed="0.25">0.25×</button>
            <button type="button" class="ghost" data-train-speed="0.5">0.5×</button>
            <button type="button" class="ghost is-on" data-train-speed="1">1×</button>
            <button type="button" class="ghost" data-train-speed="2">2×</button>
            <button type="button" class="ghost" id="btn-train-replay-path">Replay path</button>
            <span class="scalebar num" id="traj-scale" style="margin-left:auto">—</span>
          </div>
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
        <p class="view-context">The claim registry — every published number tied to a source file and re-verified by <code>tools/verify_claims.py</code>.</p>
        <div class="body flush"><table id="claims"><tbody><tr><td class="tiny">loading…</td></tr></tbody></table></div>
      </div>
      <div class="view-panel rail">
        <h2>How to read this</h2>
        <div class="body">
          <div class="gaps-publish">
            <p class="gaps-publish__title">Gaps we publish</p>
            <ul class="gaps-publish__list">
              <li>GNSS+INS classical LC-EKF is <b>1.07×</b> vs phone GNSS — a wash.
                IO-VNBD has no pseudoranges, so no tight coupling.</li>
              <li>Map-in-loop median drift <b>27.58% → 16.77%</b> vs the PS bar &lt;10% —
                we do not meet the bar. The headline is <b>2.02×</b> lower median
                position error, not drift %.</li>
              <li>Magnetometer is now fused in the APK as an onset-calibrated compass
                (heading channel: gyro <b>16.87%</b> → <b>7.22%</b>).</li>
            </ul>
          </div>
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

<script src="/static/world_map.js"></script>
<script src="/static/model_viz.js"></script>
<script src="/static/app.js"></script>
<script>
  // Mount the 3D tensor architecture viz on first visit to the MODEL tab.
  (function () {
    var mounted = false;
    function mount() {
      if (mounted) return;
      if (!window.COASTModelViz) return;
      var el = document.getElementById("tab-model-canvas");
      if (!el) return;
      mounted = true;
      window.COASTModelViz.mount(el);
    }
    document.addEventListener("coast:view", function (e) {
      if (e && e.detail && e.detail.view === "model") mount();
    });
    // If MODEL is the initial view (deep link / restored state), mount now.
    if (document.querySelector('[data-view="model"]:not([hidden])')) mount();
  })();
</script>
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
let worldMap = null, lastFitId = "__init__";
const FLEET_MAP_KEY = "coast.fleetMap";
const FLEET_TILE_KEY = "coast.fleetTiles";
function fleetMapMode(){ return localStorage.getItem(FLEET_MAP_KEY) || "world"; }
function fleetTileStyle(){ return localStorage.getItem(FLEET_TILE_KEY) || "osm"; }
function applyFleetMapChrome(){
  const world = fleetMapMode()==="world";
  const w=$("#fleet-map-world"), cv=$("#cv-fleet"), tiles=$("#fleet-tiles"), hint=$("#fleet-hint");
  if(w) w.hidden = !world;
  if(cv) cv.hidden = world;
  if(tiles) tiles.hidden = !world;
  document.querySelectorAll("#fleet-mode button").forEach(b=>b.classList.toggle("is-on", b.dataset.mode===fleetMapMode()));
  document.querySelectorAll("#fleet-tiles button").forEach(b=>b.classList.toggle("is-on", b.dataset.style===fleetTileStyle()));
  if(hint) hint.textContent = world
    ? "OpenStreetMap · no API key · click a device · GNSS blue · IDR teal · dashed = radio catch-up"
    : "Track only · no tiles · same GNSS/IDR colours";
}
function setFleetMapMode(m){
  localStorage.setItem(FLEET_MAP_KEY, m);
  applyFleetMapChrome();
  lastFitId = "__init__";
  drawFleet();
}
function setFleetTileStyle(s){
  localStorage.setItem(FLEET_TILE_KEY, s);
  if(worldMap && worldMap.setStyle) worldMap.setStyle(s);
  applyFleetMapChrome();
}

function llToXY(lat, lon, lat0, lon0){
  const R=6371000, rad=Math.PI/180;
  return [ (lon-lon0)*rad*R*Math.cos(lat0*rad), (lat-lat0)*rad*R ];
}
function drawFleet(){
  applyFleetMapChrome();
  const host=$("#fleet-map-world");
  if(fleetMapMode()==="world" && host && window.CoastWorldMap){
    if(!worldMap) worldMap = window.CoastWorldMap(host, {
      onSelect: function(id){
        selected = selected===id ? null : id;
        renderDevices(); drawFleet(); loadPrivacy();
      }
    });
    if(worldMap.setStyle) worldMap.setStyle(fleetTileStyle());
    const fit = lastFitId==="__init__" || selected!==lastFitId;
    worldMap.setDevices(fleet.devices||[], selected, {fit:fit});
    lastFitId = selected;
    const sc=$("#fleet-scale"); if(sc) sc.textContent="OpenStreetMap · drag · scroll zoom";
    return;
  }
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
  const railActions=$("#fleet-rail-actions");
  const footerDemo=$("#btn-uk-demo");
  if(!fleet.devices.length){
    el.innerHTML=`<div class="state state--empty fleet-empty">
      <p class="state__title">No phone paired yet</p>
      <p class="state__body">This console owns the recorded UK demo clip the APK also replays. Play it to populate the map with a scripted GNSS→IDR handover <b>and the reverse</b> (IDR→GNSS reacquire), or scan the code to pair a live phone. Fleet playback is not the on-phone particle filter.</p>
      <button class="act fleet-empty__cta" type="button" id="btn-uk-demo-empty">Play UK demo track</button>
      <p class="fleet-empty__legend">
        <span><i style="border-color:var(--gnss)"></i>GNSS</span>
        <span><i style="border-color:var(--accent)"></i>IDR (dead reckoning)</span>
      </p></div>`;
    const emptyBtn=$("#btn-uk-demo-empty");
    if(emptyBtn) emptyBtn.onclick=()=>$("#btn-uk-demo").click();
    if(railActions) railActions.style.display="none";
    if(footerDemo) footerDemo.style.display="none";
    $("#privacy").innerHTML=""; return;
  }
  if(railActions) railActions.style.display="flex";
  if(footerDemo) footerDemo.style.display="block";
  el.innerHTML = fleet.devices.map(d=>`
    <div class="dev ${selected===d.device_id?"sel":""} ${d.online?"":"off"}" data-id="${d.device_id}">
      <span class="swatch" style="background:${d.color}"></span>
      <span class="grow">
        <div class="nm">${d.label} <span class="tag ${d.online?"tagm":"tagh"}">${d.online?"LIVE":"DISCONNECTED"}</span></div>
        <div class="meta num">${d.latest? (d.latest.mode+" · "+fmt(d.latest.speed_mps*3.6,0)+" km/h") : "waiting for fix"}</div>
        <div class="meta num">${d.n_points} pts · ${fmt(d.distance_m,0)} m${d.online?"":" · last seen "+fmt(d.age_s,0)+"s ago"}</div>
        ${d.online?"":`<div class="tiny" style="color:var(--warn);margin-top:4px">GPS/radio gap — trail kept on the map.</div>`}
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
  const live=(fleet.devices||[]).find(d=>d.device_id===selected);
  const ev=(live&&live.events)||[];
  const timeline = ev.length ? `<h2 style="border:0;padding:0 0 8px;font-size:11px;letter-spacing:.09em;
        text-transform:uppercase;color:var(--dim)">Where it went</h2>
      <ul class="timeline">${ev.slice().reverse().slice(0,12).map(e=>{
        const to=(e.to||"").toUpperCase();
        const cls=to==="GNSS"?"gnss":to==="IDR"?"":"warn";
        const when=e.t?new Date(e.t*1000).toLocaleTimeString():"";
        const label=to==="IDR"?"GPS lost — coasting":to==="GNSS"?"GPS back":(e.from||"")+" → "+(e.to||"");
        return `<li><i class="${cls}"></i><span>${label}<br/><span class="tiny">${when}${e.lat!=null?" · "+Number(e.lat).toFixed(5)+", "+Number(e.lon).toFixed(5):""}</span></span></li>`;
      }).join("")}</ul>` : `<p class="tiny">No GPS/radio handovers recorded yet.</p>`;
  try{
    const r=await fetch("/api/privacy/"+encodeURIComponent(selected));
    if(!r.ok){ box.innerHTML=timeline; return; }
    const d=await r.json();
    const queued = live && live.n_queued_points ? `<span class="k">flushed after radio</span><span class="v">${live.n_queued_points}</span>` : "";
    box.innerHTML=`
      ${timeline}
      <p class="tiny">${live&&!live.online?"Radio last seen "+fmt(live.age_s,0)+"s ago — track is still here.":"Live."}</p>
      <h2 style="border:0;padding:12px 0 8px;font-size:11px;letter-spacing:.09em;
                 text-transform:uppercase;color:var(--dim)">What we know about ${d.label}</h2>
      <div class="kv">
        ${Object.entries(d.held).map(([k,v])=>`<span class="k">${k.replace(/_/g," ")}</span>
          <span class="v">${typeof v==="number"?commas(v):v}</span>`).join("")}
        ${queued}
      </div>
      <p class="tiny" style="margin:10px 0 4px">Not collected:</p>
      <ul class="tiny" style="margin:0 0 10px;padding-left:16px;color:var(--faint)">
        ${d.not_collected.map(x=>`<li>${x}</li>`).join("")}</ul>
      <button class="ghost danger" id="btn-forget" style="width:100%">Delete this device and all its data</button>`;
    $("#btn-forget").onclick=async()=>{
      await fetch("/api/forget/"+encodeURIComponent(selected),{method:"POST"});
      selected=null; await pollFleet();
    };
  }catch(e){ box.innerHTML=timeline; }
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
    else if(selected) loadPrivacy();
  }catch(e){
    $("#pill-srv").className="pill pill--warn";
    $("#p-srv-t").textContent="server unreachable";
  }
}

async function newQR(host){
  try{
    const q = host ? ("?host="+encodeURIComponent(host)) : "";
    const r=await fetch("/api/pair/new"+q,{method:"POST"});
    const d=await r.json();
    pairToken=d.token;
    const codeEl=$("#pair-code");
    if(codeEl) codeEl.textContent = d.token || "—";
    $("#qr").innerHTML = d.qr_svg || '<div style="color:#000;padding:20px;font:12px system-ui">QR encoder unavailable</div>';
    $("#pair-url").textContent = d.payload;
    const box=$("#pair-ips");
    if(box){
      const cands=d.candidates||[];
      box.innerHTML = cands.map(c=>`<button type="button" class="${c.url===d.lan?"is-on":""}" data-host="${c.ip}">${c.ip}${c.hint?" · "+c.hint:""}</button>`).join("");
      box.querySelectorAll("button").forEach(b=>b.onclick=()=>newQR(b.dataset.host));
    }
  }catch(e){ $("#pair-url").textContent="could not mint a pairing code"; }
}
$("#btn-newqr").onclick=newQR;

(function(){
  const input=$("#pair-phone-code"), btn=$("#btn-open-phone-code"), hint=$("#pair-phone-hint");
  if(!input || !btn) return;
  async function openPhoneCode(){
    const tok=(input.value||"").trim();
    if(!/^\d{6}$/.test(tok)){
      if(hint) hint.textContent="Enter the six digits shown on the phone.";
      return;
    }
    btn.disabled=true;
    try{
      const r=await fetch("/api/pair/open",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:tok})});
      const d=await r.json().catch(()=>({}));
      if(!r.ok){
        if(hint) hint.textContent=d.error||("Could not open session ("+r.status+")");
        return;
      }
      pairToken=d.token||tok;
      const codeEl=$("#pair-code");
      if(codeEl) codeEl.textContent=pairToken;
      if(d.qr_svg) $("#qr").innerHTML=d.qr_svg;
      if(d.payload) $("#pair-url").textContent=d.payload;
      if(hint) hint.textContent="Paired session open for "+pairToken+". Waiting for the phone on this Wi‑Fi / relay…";
      pollFleet();
    }catch(e){
      if(hint) hint.textContent="Network error — is the console running?";
    }finally{
      btn.disabled=false;
    }
  }
  btn.onclick=openPhoneCode;
  input.addEventListener("keydown",e=>{ if(e.key==="Enter"){ e.preventDefault(); openPhoneCode(); }});
})();

(function(){
  const b=$("#btn-copy-pair"), hint=$("#pair-copy-hint");
  if(!b) return;
  b.onclick=async()=>{
    const url=($("#pair-url")?.textContent||"").trim();
    if(!url || url==="—"){ if(hint) hint.textContent="No pairing link yet — press New code first."; return; }
    try{
      await navigator.clipboard.writeText(url);
      if(hint) hint.textContent="Copied. Paste on the phone's Connect screen.";
    }catch(e){
      // Fallback for browsers that block async clipboard on http:.
      const ta=document.createElement("textarea"); ta.value=url; document.body.appendChild(ta);
      ta.select(); try{ document.execCommand("copy"); if(hint) hint.textContent="Copied. Paste on the phone's Connect screen."; }
      catch(_){ if(hint) hint.textContent="Copy failed — long-press to select the link manually."; }
      document.body.removeChild(ta);
    }
  };
})();
$("#btn-forget-all").onclick=async()=>{ await fetch("/api/forget_all",{method:"POST"}); selected=null; pollFleet(); };

function setUkDemoUi(running){
  const go=$("#btn-uk-demo"), emptyGo=$("#btn-uk-demo-empty"),
        stop=$("#btn-uk-demo-stop"), hint=$("#uk-demo-hint"), rail=$("#fleet-rail-actions");
  [go, emptyGo].forEach(btn=>{
    if(btn){ btn.disabled=!!running; btn.textContent=running?"Playing UK demo…":"Play UK demo track"; }
  });
  if(stop) stop.style.display=running?"block":"none";
  if(rail){
    if(running){ rail.style.display="flex"; if(go) go.style.display="none"; }
    else if(!fleet.devices.length){ rail.style.display="none"; if(go) go.style.display="none"; }
    else { rail.style.display="flex"; if(go) go.style.display="block"; }
  }
  if(hint && !running) hint.textContent="Coventry / Midlands · APK IO-VNBD clip · GNSS → IDR (20–80 s) → GNSS. Not a live phone PF.";
}
const ukDemoEmpty=$("#btn-uk-demo-empty");
if(ukDemoEmpty) ukDemoEmpty.onclick=()=>$("#btn-uk-demo").click();
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
          holdBaselineRmse:null, switchEpoch:null, reveal:1, animStart:0,
          pathSpeed:1};
const TRAIN_MIX_MS = 4200;
function objOf(e){ return String(e.objective||e.mode||"").toUpperCase(); }
function heldOf(e){
  const v = (typeof e.held_rmse==="number") ? e.held_rmse
    : (typeof e.rmse==="number" ? e.rmse : NaN);
  return Number.isFinite(v) ? v : null;
}
function easeInOut(t){ t=Math.max(0,Math.min(1,t)); return t*t*(3-2*t); }
function resamplePath(pts, n){
  if(!pts || !pts.length) return [];
  if(pts.length===1) return Array.from({length:n},()=>[pts[0][0],pts[0][1]]);
  const out=[];
  for(let i=0;i<n;i++){
    const u=i/(n-1)*(pts.length-1), j=Math.floor(u), f=u-j;
    const a=pts[j], b=pts[Math.min(j+1,pts.length-1)];
    out.push([a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f]);
  }
  return out;
}
function lerpPath(a, b, t){
  if(!a||!a.length) return b||[];
  if(!b||!b.length) return a;
  const n=Math.max(a.length,b.length,2);
  const A=resamplePath(a,n), B=resamplePath(b,n);
  return A.map((p,i)=>[p[0]+(B[i][0]-p[0])*t, p[1]+(B[i][1]-p[1])*t]);
}
function growingPath(pts, reveal){
  if(!pts||pts.length<2) return pts||[];
  const r=Math.max(0.02, Math.min(1, reveal));
  const n=Math.max(2, Math.ceil(pts.length*r));
  return pts.slice(0,n);
}
function drawTraj(){
  const cv=$("#cv-traj"); if(!cv || !cv.getBoundingClientRect().width) return;
  const {g,w,h}=fit(cv); gridBg(g,w,h);
  const morph = (tr.prev && tr.cur) ? lerpPath(tr.prev, tr.cur, easeInOut(tr.mix)) : (tr.cur||tr.prev);
  const shown = growingPath(morph, tr.reveal);
  const all=[tr.truth,tr.hold,shown,tr.cur].filter(p=>p&&p.length);
  if(!all.length){
    g.fillStyle="#5A6673"; g.font="13px system-ui"; g.textAlign="center";
    g.fillText("Press Train — the estimated path will converge onto the truth as it learns.", w/2, h/2);
    return;
  }
  const pr=projector(all,w,h,46); if(!pr) return;
  stroke(g,tr.hold,pr,"#FF6B6B",2,[6,5]);
  stroke(g,tr.truth,pr,"#E8EDF2",2.4);
  if(shown && shown.length>=2) stroke(g,shown,pr,"#00D4AA",3);
  if(shown && shown.length){
    const last=shown[shown.length-1];
    g.fillStyle="#00D4AA"; g.beginPath();
    g.arc(pr.px(last[0]), pr.py(last[1]), 4.5, 0, Math.PI*2); g.fill();
  }
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
  // Prefer the dense per-batch series: 96 points instead of 4, so the
  // curve moves continuously instead of stepping once per epoch.
  const eps=(tr.live && tr.live.length) ? tr.live : tr.epochs;
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
function animateMix(now){
  if(!tr.animStart) tr.animStart = now || performance.now();
  const dur = TRAIN_MIX_MS / Math.max(0.25, tr.pathSpeed||1);
  const t = ((now||performance.now()) - tr.animStart) / dur;
  tr.mix = Math.min(1, easeInOut(t));
  // Reveal the path along the route like Replay — slow crawl, not a pop.
  tr.reveal = Math.min(1, t);
  drawTraj();
  if(tr.mix < 1 || tr.reveal < 1) requestAnimationFrame(animateMix);
}
function beginPathMorph(nextPath){
  if(!nextPath || !nextPath.length) return;
  tr.prev = tr.cur && tr.cur.length ? tr.cur : (tr.hold && tr.hold.length ? tr.hold : nextPath);
  tr.cur = nextPath;
  tr.mix = 0;
  tr.reveal = 0;
  tr.animStart = 0;
  requestAnimationFrame(animateMix);
}
document.querySelectorAll("[data-train-speed]").forEach(btn=>{
  btn.addEventListener("click",()=>{
    tr.pathSpeed=parseFloat(btn.dataset.trainSpeed)||1;
    document.querySelectorAll("[data-train-speed]").forEach(b=>b.classList.toggle("is-on", b===btn));
  });
});
const btnTrainReplay=$("#btn-train-replay-path");
if(btnTrainReplay) btnTrainReplay.onclick=()=>{
  const path = (tr.cur && tr.cur.length) ? tr.cur : (tr.hold && tr.hold.length ? tr.hold : null);
  if(path) beginPathMorph(path);
};
function onEpoch(e){
  if(typeof e.hold_baseline_rmse==="number" && Number.isFinite(e.hold_baseline_rmse))
    tr.holdBaselineRmse=e.hold_baseline_rmse;
  tr.epochs.push(e);
  if(e.path && e.path.length) beginPathMorph(e.path);
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
let _lossRaf=0;
function scheduleLoss(){
  // 96 batch events in ~34s; coalesce redraws onto animation frames so the
  // curve is smooth without repainting the canvas on every message.
  if(_lossRaf) return;
  _lossRaf=requestAnimationFrame(()=>{ _lossRaf=0; drawLoss(); });
}
function onBatch(d){
  tr.live.push(d);
  if(typeof d.progress==="number"){
    const pct=Math.round(d.progress*100);
    $("#p-trn-t").textContent="training "+pct+"%  ·  epoch "+(d.epoch||"?")+"/"+(d.epochs||"?");
    $("#pill-trn").className="pill pill--ok";
  }
  if(Number.isFinite(d.loss)) $("#s-loss").textContent=fmt(d.loss,4);
  if(Number.isFinite(d.elapsed_s)) $("#s-el").textContent=fmt(d.elapsed_s,1)+"s";
  scheduleLoss();
}
function onPathProgress(d){
  tr.live.push(d);
  if(d.path && d.path.length) beginPathMorph(d.path);
  if(typeof d.held_rmse==="number" && Number.isFinite(d.held_rmse))
    $("#s-rmse").textContent=fmt(d.held_rmse,3);
  $("#p-trn-t").textContent="learning epoch "+(d.epoch||"?")+" · step "+(d.step||"?");
  $("#pill-trn").className="pill pill--ok";
}
function trainBanner(html, cls){ $("#tr-banner").innerHTML = html?`<div class="banner-box ${cls}">${html}</div>`:""; }

$("#btn-train").onclick=async()=>{
  const b=$("#btn-train"); b.disabled=true; b.textContent="Training…";
  tr={truth:[],hold:[],epochs:[],live:[],cur:null,prev:null,mix:1,held:"",
      holdBaselineRmse:null, switchEpoch:null, reveal:1, animStart:0};
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
      $("#tr-held").textContent="held-out drive "+tr.held+" · re-integrated after every epoch";
      beginPathMorph(tr.hold.length?tr.hold:tr.truth); drawTraj(); }
    else if(d.type==="batch"){ onBatch(d); }
    else if(d.type==="path_progress"){ onPathProgress(d); }
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
function resizeAll(){ if(worldMap) worldMap.resize(); drawFleet(); drawTraj(); drawLoss(); }
function bootConsole(){
  applyFleetMapChrome();
  document.querySelectorAll("#fleet-mode button").forEach(b=>b.onclick=()=>setFleetMapMode(b.dataset.mode));
  document.querySelectorAll("#fleet-tiles button").forEach(b=>b.onclick=()=>setFleetTileStyle(b.dataset.style));
  newQR(); pollFleet(); loadClaims(); loadExistingFigs();
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
<script>
/* ======= COAST SIMULATION ENGINE v3 ======= */
(function(){
  'use strict';

  var canvas  = document.getElementById('sim-canvas');
  var phoneC  = document.getElementById('sim-phone-canvas');
  var btnPlay = document.getElementById('sim-btn-play');
  var btnPrev = document.getElementById('sim-btn-prev');
  var btnNext = document.getElementById('sim-btn-next');
  var gpsDot  = document.getElementById('sim-gps-dot');
  var gpsLbl  = document.getElementById('sim-gps-label');
  var sceneLbl= document.getElementById('sim-scene-label');
  var sceneDsc= document.getElementById('sim-scene-desc');
  var elSpeed = document.getElementById('phone-speed');
  var elLean  = document.getElementById('phone-lean');
  var elMode  = document.getElementById('phone-mode');
  var elDrift = document.getElementById('phone-drift');
  var elNotif = document.getElementById('sim-phone-notif-text');
  var elBars  = document.getElementById('phone-signal-bars');

  if(!canvas||!phoneC) return;

  var C  = canvas.getContext('2d');
  var PC = phoneC.getContext('2d');
  var W  = canvas.width;
  var H  = canvas.height;

  /* inject Mode / View buttons into the bottom bar */
  var bar2 = document.querySelector('#sim-section > div:last-child > div:nth-child(2)');
  if(bar2){
    var extra = document.createElement('div');
    extra.style.cssText='display:flex;gap:5px;align-items:center;margin-left:10px;padding-left:12px;border-left:1px solid #1c232d;';
    extra.innerHTML=
      '<span style="font-size:10px;color:#5a6673;letter-spacing:.1em;text-transform:uppercase;">Mode:</span>'+
      '<button id="sim-mode-scoot" style="background:#ff3366;border:none;color:#fff;border-radius:4px;padding:4px 9px;font-size:10px;font-weight:700;cursor:pointer;">Scooter</button>'+
      '<button id="sim-mode-car"   style="background:transparent;border:1px solid #1c232d;color:#7a8999;border-radius:4px;padding:4px 9px;font-size:10px;cursor:pointer;">Car</button>'+
      '<span style="font-size:10px;color:#5a6673;letter-spacing:.1em;text-transform:uppercase;margin-left:6px;">View:</span>'+
      '<button id="sim-view-pov" style="background:#0070f3;border:none;color:#fff;border-radius:4px;padding:4px 9px;font-size:10px;font-weight:700;cursor:pointer;">POV</button>'+
      '<button id="sim-view-map" style="background:transparent;border:1px solid #1c232d;color:#7a8999;border-radius:4px;padding:4px 9px;font-size:10px;cursor:pointer;">Map</button>';
    bar2.appendChild(extra);
  }

  /* ---- state ---- */
  var mode    = 'scooter';
  var view    = 'pov';
  var scene   = 0;
  var t       = 0;
  var playing = false;
  var rafId   = null;
  var scootTrail = [];
  var carTrail   = [];

  /* ---- road path: x=east (m), y=north (m) ---- */
  var ROAD=[
    {x:0,  y:0,   h:0   },
    {x:100,y:0,   h:0   },
    {x:200,y:0,   h:0   },     /* GPS lost ~here */
    {x:300,y:-40, h:-0.35},
    {x:390,y:-100,h:-0.55},
    {x:475,y:-145,h:-0.3 },
    {x:560,y:-155,h:-0.1 },
    {x:645,y:-140,h:0.15 },    /* GPS regained ~here */
    {x:730,y:-105,h:0.28 },
    {x:820,y:-60, h:0.22 },
    {x:900,y:-20, h:0.08 }
  ];

  /* cumulative arc-length */
  var ARC=[0];
  for(var i=1;i<ROAD.length;i++){
    var ddx=ROAD[i].x-ROAD[i-1].x, ddy=ROAD[i].y-ROAD[i-1].y;
    ARC.push(ARC[i-1]+Math.sqrt(ddx*ddx+ddy*ddy));
  }
  var TOTAL=ARC[ARC.length-1];

  function roadAt(s){
    s=Math.max(0,Math.min(TOTAL-0.01,s));
    for(var i=1;i<ROAD.length;i++){
      if(ARC[i]>=s){
        var f=(s-ARC[i-1])/(ARC[i]-ARC[i-1]);
        var a=ROAD[i-1], b=ROAD[i];
        return {
          x:a.x+(b.x-a.x)*f,
          y:a.y+(b.y-a.y)*f,
          h:a.h+(b.h-a.h)*f,
          curv:(b.h-a.h)/(ARC[i]-ARC[i-1]+0.001)
        };
      }
    }
    var last=ROAD[ROAD.length-1];
    return {x:last.x,y:last.y,h:last.h,curv:0};
  }

  /* ---- scenes ---- */
  var SDEFS=[
    {lbl:'Scene 1 / 3',desc:'GNSS locked — both vehicles tracking accurately'},
    {lbl:'Scene 2 / 3',desc:'GNSS denied — scooter leans into curve, car loses the road'},
    {lbl:'Scene 3 / 3',desc:'GNSS re-acquired — COAST loop closure: 2.02x better'}
  ];

  function sceneDist(){
    if(scene===0) return t*200;
    if(scene===1) return 200+t*390;
    return 590+t*260;
  }

  function isGPS(){ return scene===0||(scene===2&&t>0.4); }

  function getScoot(){
    var s=sceneDist(), rp=roadAt(s);
    var lean=Math.max(-0.88,Math.min(0.88,rp.curv*32));
    return {x:rp.x,y:rp.y,h:rp.h,lean:lean,s:s,rp:rp};
  }

  function getCar(){
    var sv=getScoot();
    var cy=sv.rp.y, ch=sv.rp.h;
    if(scene===1){ var dp=t; cy=sv.rp.y*(1-dp*0.88); ch=sv.rp.h*(1-dp*0.88); }
    else if(scene===2){ cy=sv.rp.y*0.10; ch=sv.rp.h*0.10; }
    return {x:sv.rp.x,y:cy,h:ch,lean:0,s:sv.s,rp:{x:sv.rp.x,y:cy,h:ch,curv:0}};
  }

  /* ============ MAP VIEW ============ */
  function drawMapView(){
    var veh=mode==='scooter'?getScoot():getCar();
    var gps=isGPS();
    C.clearRect(0,0,W,H);
    /* background */
    C.fillStyle='#070d14'; C.fillRect(0,0,W,H);

    C.save();
    /* camera: follow vehicle, rotate heading-up */
    var mapS=1.15;
    C.translate(W*0.40,H*0.54);
    C.scale(mapS,mapS);
    C.rotate(-veh.h-Math.PI/2);
    C.translate(-veh.x,-veh.y);

    /* grid */
    C.strokeStyle='rgba(255,255,255,0.025)'; C.lineWidth=0.5;
    for(var gx=-200;gx<1100;gx+=70){C.beginPath();C.moveTo(gx,-300);C.lineTo(gx,200);C.stroke();}
    for(var gy=-300;gy<200;gy+=70){C.beginPath();C.moveTo(-200,gy);C.lineTo(1100,gy);C.stroke();}

    /* buildings */
    var BLDG=[
      [210,-180,60,50,'#182233'],[215,-185,45,65,'#132032'],
      [330,-168,72,48,'#1b2740'],[420,-178,62,50,'#16212f'],
      [510,-162,56,50,'#182233'],[572,-167,50,50,'#1b2740'],
      [210,70,55,70,'#182233'],[312,72,52,60,'#132032'],
      [420,74,66,52,'#1b2740'],[512,65,56,58,'#16212f'],
      [50,-155,52,42,'#13202e'],[130,-148,48,55,'#182233']
    ];
    for(var bi=0;bi<BLDG.length;bi++){
      C.fillStyle=BLDG[bi][4]; C.strokeStyle='#1e2e42'; C.lineWidth=1;
      C.fillRect(BLDG[bi][0],BLDG[bi][1],BLDG[bi][2],BLDG[bi][3]);
      C.strokeRect(BLDG[bi][0],BLDG[bi][1],BLDG[bi][2],BLDG[bi][3]);
    }

    /* GPS outage zone */
    C.fillStyle='rgba(255,80,80,0.055)'; C.strokeStyle='rgba(255,80,80,0.22)';
    C.lineWidth=1; C.setLineDash([9,7]);
    C.fillRect(195,-182,400,262); C.strokeRect(195,-182,400,262);
    C.setLineDash([]);
    C.font='7px ui-monospace,monospace'; C.fillStyle='rgba(255,100,100,0.6)';
    C.fillText('GPS DENIED ZONE',398,-188);

    /* road */
    C.beginPath();
    for(var ri=0;ri<ROAD.length;ri++){
      if(ri===0) C.moveTo(ROAD[ri].x,ROAD[ri].y); else C.lineTo(ROAD[ri].x,ROAD[ri].y);
    }
    C.lineWidth=28; C.strokeStyle='#1a2535'; C.lineCap='round'; C.lineJoin='round'; C.stroke();
    C.setLineDash([12,12]); C.lineWidth=1.5; C.strokeStyle='rgba(255,255,255,0.07)'; C.stroke(); C.setLineDash([]);
    /* curbs */
    for(var side=-1;side<=1;side+=2){
      C.beginPath();
      for(var ri2=0;ri2<ROAD.length;ri2++){
        var ph2=ROAD[ri2].h+Math.PI/2;
        C.lineTo?null:null;
        var px2=ROAD[ri2].x+Math.cos(ph2)*15*side;
        var py2=ROAD[ri2].y+Math.sin(ph2)*15*side;
        if(ri2===0) C.moveTo(px2,py2); else C.lineTo(px2,py2);
      }
      C.lineWidth=2.5; C.strokeStyle='#28404f'; C.stroke();
    }

    /* trails in world space */
    if(scootTrail.length>1){
      C.beginPath();
      for(var ti=0;ti<scootTrail.length;ti++){
        if(ti===0) C.moveTo(scootTrail[ti].x,scootTrail[ti].y);
        else C.lineTo(scootTrail[ti].x,scootTrail[ti].y);
      }
      C.strokeStyle='rgba(255,51,102,0.55)'; C.lineWidth=2.5; C.stroke();
    }
    if(carTrail.length>1&&scene>=1){
      C.beginPath();
      for(var ti2=0;ti2<carTrail.length;ti2++){
        if(ti2===0) C.moveTo(carTrail[ti2].x,carTrail[ti2].y);
        else C.lineTo(carTrail[ti2].x,carTrail[ti2].y);
      }
      C.strokeStyle='rgba(74,158,255,0.5)'; C.lineWidth=2.5; C.stroke();
    }

    C.restore(); /* undo map transform */

    /* draw vehicles at fixed screen anchor */
    C.save(); C.translate(W*0.40,H*0.54);
    drawMapIcon(C,0,0,mode==='scooter'?veh.lean:0,mode==='scooter'?'#ff3366':'#4a9eff',mode);
    /* also draw naive car offset in scene 2 */
    if(scene===1&&t>0.18){
      var sv2=getScoot(), cv2=getCar();
      var cosH=Math.cos(-sv2.h-Math.PI/2), sinH=Math.sin(-sv2.h-Math.PI/2);
      var ddx=(cv2.x-sv2.x)*mapS, ddy=(cv2.y-sv2.y)*mapS;
      var ox=ddx*cosH-ddy*sinH, oy=ddx*sinH+ddy*cosH;
      if(Math.hypot(ox,oy)>8){
        C.save(); C.translate(ox,oy); C.rotate(cv2.h-sv2.h);
        drawMapIcon(C,0,0,0,'#4a9eff','car');
        C.restore();
        /* error dashed line */
        C.setLineDash([4,4]); C.strokeStyle='rgba(255,160,0,0.7)'; C.lineWidth=1.5;
        C.beginPath(); C.moveTo(0,0); C.lineTo(ox,oy); C.stroke(); C.setLineDash([]);
        var em=(Math.hypot(ox,oy)*0.13).toFixed(0);
        C.font='bold 9px ui-monospace,monospace'; C.fillStyle='rgba(255,160,0,0.9)';
        C.fillText(em+'m drift',ox*0.5-14,oy*0.5-8);
      }
    }
    C.restore();

    /* compass */
    drawCompass(veh.h);
    /* HUD */
    C.font='bold 12px ui-monospace,monospace'; C.fillStyle='#e8edf2';
    C.fillText(Math.round(35+Math.sin(veh.s*0.05)*5)+' km/h',16,30);
    C.font='9px ui-monospace,monospace'; C.fillStyle=gps?'#00d4aa':'#ff6b6b';
    C.fillText(gps?'GNSS LOCKED':'GNSS DENIED',16,46);
  }

  function drawMapIcon(ctx,sx,sy,lean,col,vmode){
    ctx.save(); ctx.translate(sx,sy);
    if(lean) ctx.transform(1,0,lean*0.32,1-Math.abs(lean)*0.08,0,0);
    /* shadow */
    ctx.beginPath(); ctx.ellipse(0,5,vmode==='car'?14:10,4,0,0,Math.PI*2);
    ctx.fillStyle='rgba(0,0,0,0.4)'; ctx.fill();
    if(vmode==='car'){
      ctx.fillStyle=col; ctx.shadowColor=col; ctx.shadowBlur=12;
      ctx.fillRect(-9,-14,18,11);    /* body, nose up */
      ctx.fillStyle='#3270c0'; ctx.fillRect(-6,-18,12,6);  /* roof */
      ctx.shadowBlur=0;
      ctx.fillStyle='rgba(170,210,255,0.5)'; ctx.fillRect(-5,-17,10,4);
      ctx.fillStyle='#0a1220';
      [[7,-12],[7,0],[-7,-12],[-7,0]].forEach(function(p){
        ctx.beginPath(); ctx.ellipse(p[0],p[1],3,2,0,0,Math.PI*2); ctx.fill();
      });
    } else {
      ctx.fillStyle=col; ctx.shadowColor=col; ctx.shadowBlur=14;
      ctx.fillRect(-6,-12,12,7); /* seat */
      ctx.fillRect(-5,-3,10,4);  /* step */
      ctx.shadowBlur=0;
      ctx.strokeStyle=col; ctx.lineWidth=2;
      ctx.beginPath(); ctx.moveTo(5,-12); ctx.lineTo(5,-17); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(2,-17); ctx.lineTo(8,-17); ctx.stroke();
      ctx.fillStyle='#0a1220';
      ctx.beginPath(); ctx.ellipse(0,-14,3,2,0,0,Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.ellipse(0,2,3,2,0,0,Math.PI*2); ctx.fill();
      ctx.fillStyle='#00d4aa'; ctx.shadowColor='#00d4aa'; ctx.shadowBlur=8;
      ctx.beginPath(); ctx.arc(0,-6,1.8,0,Math.PI*2); ctx.fill(); ctx.shadowBlur=0;
    }
    ctx.restore();
  }

  function drawCompass(heading){
    var cx=W-52,cy=46,r=20;
    C.save(); C.translate(cx,cy);
    C.beginPath(); C.arc(0,0,r,0,Math.PI*2);
    C.fillStyle='rgba(8,13,20,0.85)'; C.fill();
    C.strokeStyle='#2a3d52'; C.lineWidth=1; C.stroke();
    C.rotate(-heading);
    C.strokeStyle='#ff3366'; C.lineWidth=2.5; C.lineCap='round';
    C.beginPath(); C.moveTo(0,r-3); C.lineTo(0,-(r-3)); C.stroke();
    C.fillStyle='#ff3366'; C.font='bold 7px system-ui';
    C.textAlign='center'; C.fillText('N',0,-(r+4));
    C.restore();
    C.font='7px system-ui'; C.fillStyle='#5a6673';
    C.textAlign='center'; C.fillText('HDG',cx,cy+8); C.textAlign='left';
  }

  /* ============ POV VIEW ============ */
  function drawPOVView(){
    var veh=mode==='scooter'?getScoot():getCar();
    var gps=isGPS();
    var lean=veh.lean;
    C.clearRect(0,0,W,H);

    /* vanishing point shifts with road curve */
    var VPX=W/2+Math.max(-200,Math.min(200,(veh.rp?veh.rp.curv:0)*200));
    var VPY=H*0.39;

    C.save();
    /* camera lean (roll) */
    if(lean){
      C.translate(W/2,VPY);
      C.rotate(lean*0.19);
      C.translate(-W/2,-VPY);
    }

    /* sky gradient */
    var sky=C.createLinearGradient(0,0,0,VPY);
    sky.addColorStop(0,'#030810');
    sky.addColorStop(0.55,'#081422');
    sky.addColorStop(1,'#0c1e30');
    C.fillStyle=sky; C.fillRect(0,0,W,VPY+3);

    /* city glow on horizon */
    var hgl=C.createLinearGradient(0,VPY-55,0,VPY);
    hgl.addColorStop(0,'rgba(20,65,130,0)');
    hgl.addColorStop(1,'rgba(20,65,130,0.22)');
    C.fillStyle=hgl; C.fillRect(0,VPY-55,W,55);

    /* stars (static seed so they don't flicker) */
    if(gps){
      for(var si=0;si<50;si++){
        var ssx=((si*2971+13)%W);
        var ssy=((si*1847+7)%(Math.round(VPY*0.9)));
        var sal=0.2+0.5*(si%3)/3;
        C.beginPath(); C.arc(ssx,ssy,0.7,0,Math.PI*2);
        C.fillStyle='rgba(255,255,255,'+sal.toFixed(2)+')'; C.fill();
      }
    }

    /* ground */
    var gnd=C.createLinearGradient(0,VPY,0,H);
    gnd.addColorStop(0,'#0a1520'); gnd.addColorStop(1,'#060d14');
    C.fillStyle=gnd; C.fillRect(0,VPY,W,H-VPY);

    /* road surface trapezoid */
    var RW=W*0.72, RV=20;
    C.beginPath();
    C.moveTo(VPX-RW/2,H+8); C.lineTo(VPX+RW/2,H+8);
    C.lineTo(VPX+RV,VPY);   C.lineTo(VPX-RV,VPY);
    C.closePath();
    C.fillStyle='#19263a'; C.fill();

    /* depth grid on road */
    for(var di=1;di<=7;di++){
      var dp=di/8;
      var yd=VPY+(H-VPY)*(1-dp*dp);
      var xw=RW/2*(1-dp)+RV*dp;
      C.beginPath(); C.moveTo(VPX-xw,yd); C.lineTo(VPX+xw,yd);
      C.strokeStyle='rgba(255,255,255,0.035)'; C.lineWidth=0.5; C.stroke();
    }

    /* animated lane dashes */
    var dashT=(Date.now()/180)%1;
    for(var li=0;li<18;li++){
      var lp=(li+dashT)/18;
      var lpt=(lp+0.032<1)?(lp+0.032):1;
      var yt=VPY+(H-VPY)*(1-(1-lp)*(1-lp));
      var yb=VPY+(H-VPY)*(1-(1-lpt)*(1-lpt));
      if(yt>H||yb<VPY) continue;
      var lw=Math.max(1,3*(1-lp));
      C.fillStyle='rgba(255,255,255,0.10)';
      C.fillRect(VPX-lw/2,Math.max(VPY,yb),lw,Math.min(H,yt)-Math.max(VPY,yb));
    }

    /* sidewalks */
    var SW2=RW*0.11;
    C.beginPath();
    C.moveTo(VPX-RW/2-SW2,H+8); C.lineTo(VPX-RW/2,H+8);
    C.lineTo(VPX-RV,VPY); C.lineTo(VPX-RV-9,VPY);
    C.fillStyle='#0f1c2a'; C.fill();
    C.beginPath();
    C.moveTo(VPX+RW/2,H+8); C.lineTo(VPX+RW/2+SW2,H+8);
    C.lineTo(VPX+RV+9,VPY); C.lineTo(VPX+RV,VPY);
    C.fillStyle='#0f1c2a'; C.fill();

    /* buildings — left side */
    var BCOLS=['#182233','#1b2740','#132032','#1d2945','#14202e'];
    for(var bi2=0;bi2<5;bi2++){
      var bd=(bi2+1)/6;
      var xr=VPX-(RW/2*(1-bd)+RV*bd)-SW2*(1-bd);
      var yb2=VPY+(H-VPY)*(1-bd*bd);
      var yt2=VPY-(90+bi2*22)*(1-bd)-8;
      var bw2=(130+bi2*28)*(1-bd);
      C.fillStyle=BCOLS[bi2]; C.fillRect(xr-bw2,yt2,bw2,yb2-yt2);
      /* windows */
      C.fillStyle='rgba(200,215,255,0.14)';
      for(var wr=0;wr<4;wr++){
        for(var wc=0;wc<5;wc++){
          var wx2=xr-bw2+8+wc*(bw2/5.5);
          var wy2=yt2+12+wr*16;
          if(wy2<yb2-6) C.fillRect(wx2,wy2,Math.max(2,(bw2/7)*(1-bd)),Math.max(2,6*(1-bd)));
        }
      }
    }
    /* buildings — right side */
    for(var bi3=0;bi3<5;bi3++){
      var bd3=(bi3+1)/6;
      var xr3=VPX+(RW/2*(1-bd3)+RV*bd3)+SW2*(1-bd3);
      var yb3=VPY+(H-VPY)*(1-bd3*bd3);
      var yt3=VPY-(85+bi3*24)*(1-bd3)-8;
      var bw3=(120+bi3*32)*(1-bd3);
      C.fillStyle=BCOLS[bi3]; C.fillRect(xr3,yt3,bw3,yb3-yt3);
      C.fillStyle='rgba(200,215,255,0.14)';
      for(var wr3=0;wr3<4;wr3++){
        for(var wc3=0;wc3<5;wc3++){
          var wx3=xr3+8+wc3*(bw3/5.5);
          var wy3=yt3+12+wr3*16;
          if(wy3<yb3-6) C.fillRect(wx3,wy3,Math.max(2,(bw3/7)*(1-bd3)),Math.max(2,6*(1-bd3)));
        }
      }
    }

    /* GPS denied — red vignette + text */
    if(!gps){
      var rfog=C.createRadialGradient(VPX,VPY+(H-VPY)*0.3,20,VPX,H*0.5,H*0.75);
      rfog.addColorStop(0,'rgba(200,55,55,0)');
      rfog.addColorStop(1,'rgba(200,55,55,0.24)');
      C.fillStyle=rfog; C.fillRect(0,0,W,H);
      C.font='bold 13px ui-monospace,monospace';
      C.fillStyle='rgba(255,100,100,0.72)'; C.textAlign='center';
      C.fillText('GNSS DENIED  DEAD RECKONING ACTIVE',W/2,VPY*0.58);
      C.textAlign='left';
    }

    /* satellite orbs (GPS active) */
    if(gps){
      var now3=Date.now()/1100;
      for(var sbi=0;sbi<6;sbi++){
        var sph=(now3*0.55+sbi*0.38)%1;
        var sbx=VPX+(sbi-2.5)*80;
        var sby=VPY-18-sph*90;
        var sba=Math.sin(sph*Math.PI)*0.75;
        C.beginPath(); C.arc(sbx,sby,1.8,0,Math.PI*2);
        C.fillStyle='rgba(0,212,170,'+sba.toFixed(2)+')'; C.fill();
      }
    }

    /* vehicle FOV body */
    if(mode==='scooter') drawScooterFOV(lean,veh.s);
    else                 drawCarFOV(veh.s);

    C.restore(); /* un-lean */

    /* vignette */
    var vign=C.createRadialGradient(W/2,H*0.6,H*0.18,W/2,H*0.5,W*0.65);
    vign.addColorStop(0,'rgba(0,0,0,0)');
    vign.addColorStop(1,'rgba(0,0,0,0.42)');
    C.fillStyle=vign; C.fillRect(0,0,W,H);

    /* HUD (outside lean) */
    drawPOVHUD(veh,gps);
  }

  function drawScooterFOV(lean,s){
    var cx=W/2, lo=lean*28;
    /* dash shadow */
    C.fillStyle='rgba(0,0,0,0.5)';
    C.fillRect(cx-130,H-88,260,14);
    /* dashboard body */
    var dg=C.createLinearGradient(cx,H-92,cx,H-40);
    dg.addColorStop(0,'#1a2535'); dg.addColorStop(1,'#0d1620');
    C.fillStyle=dg;
    C.beginPath();
    C.moveTo(cx-210,H); C.lineTo(cx+210,H);
    C.lineTo(cx+115,H-92); C.lineTo(cx-115,H-92);
    C.closePath(); C.fill();
    /* speedo */
    C.strokeStyle='#2a3d52'; C.lineWidth=2;
    C.beginPath(); C.arc(cx,H-65,24,0,Math.PI*2); C.stroke();
    var spd=Math.round(35+Math.sin(s*0.05)*5);
    C.font='bold 13px ui-monospace,monospace'; C.fillStyle='#e8edf2'; C.textAlign='center';
    C.fillText(spd,cx,H-59); C.font='7px system-ui'; C.fillStyle='#5a6673'; C.fillText('km/h',cx,H-49);
    C.textAlign='left';
    /* handlebars */
    C.lineCap='round'; C.lineWidth=13;
    C.strokeStyle='#253240';
    C.beginPath(); C.moveTo(cx-12+lo,H-82); C.lineTo(cx-115+lo,H-60); C.stroke();
    C.beginPath(); C.moveTo(cx+12+lo,H-82); C.lineTo(cx+115+lo,H-60); C.stroke();
    C.strokeStyle='#3a5068'; C.lineWidth=10;
    C.beginPath(); C.moveTo(cx-12+lo,H-82); C.lineTo(cx-115+lo,H-60); C.stroke();
    C.beginPath(); C.moveTo(cx+12+lo,H-82); C.lineTo(cx+115+lo,H-60); C.stroke();
    /* grips */
    C.strokeStyle='#4a9eff'; C.lineWidth=9;
    C.beginPath(); C.moveTo(cx-90+lo,H-58); C.lineTo(cx-115+lo,H-58); C.stroke();
    C.beginPath(); C.moveTo(cx+90+lo,H-58); C.lineTo(cx+115+lo,H-58); C.stroke();
    /* IMU */
    C.fillStyle='#00d4aa'; C.shadowColor='#00d4aa'; C.shadowBlur=9;
    C.beginPath(); C.arc(cx+38,H-72,3,0,Math.PI*2); C.fill(); C.shadowBlur=0;
    C.font='7px ui-monospace,monospace'; C.fillStyle='#00d4aa'; C.fillText('IMU',cx+43,H-70);
  }

  function drawCarFOV(s){
    var cx=W/2;
    /* hood */
    var hg=C.createLinearGradient(cx,H*0.72,cx,H);
    hg.addColorStop(0,'#28405c'); hg.addColorStop(1,'#162840');
    C.fillStyle=hg;
    C.beginPath();
    C.moveTo(0,H); C.lineTo(W,H);
    C.lineTo(W*0.76,H*0.71); C.lineTo(W*0.24,H*0.71);
    C.closePath(); C.fill();
    /* dash panel */
    var dp=C.createLinearGradient(cx,H*0.67,cx,H*0.73);
    dp.addColorStop(0,'#0e1820'); dp.addColorStop(1,'#182535');
    C.fillStyle=dp; C.fillRect(0,H*0.67,W,H*0.065);
    /* speedo */
    var spd=Math.round(35+Math.sin(s*0.05)*5);
    C.strokeStyle='#2a3d52'; C.lineWidth=2;
    C.beginPath(); C.arc(cx,H*0.715,28,0,Math.PI*2); C.stroke();
    C.font='bold 14px ui-monospace,monospace'; C.fillStyle='#e8edf2'; C.textAlign='center';
    C.fillText(spd,cx,H*0.715+5);
    C.font='7px system-ui'; C.fillStyle='#5a6673'; C.fillText('km/h',cx,H*0.715+16);
    C.textAlign='left';
    /* steering wheel */
    C.strokeStyle='#253240'; C.lineWidth=9; C.lineCap='round';
    C.beginPath(); C.arc(cx,H*0.89,44,0,Math.PI*2); C.stroke();
    C.strokeStyle='#1a2535'; C.lineWidth=7;
    C.beginPath(); C.arc(cx,H*0.89,44,0,Math.PI*2); C.stroke();
    C.strokeStyle='#253240'; C.lineWidth=7;
    C.beginPath(); C.moveTo(cx,H*0.89-44); C.lineTo(cx,H*0.89+44); C.stroke();
    C.beginPath(); C.moveTo(cx-44,H*0.89); C.lineTo(cx+44,H*0.89); C.stroke();
  }

  function drawPOVHUD(veh,gps){
    /* top-left status box */
    C.fillStyle=gps?'rgba(0,212,170,0.12)':'rgba(255,80,80,0.12)';
    C.fillRect(12,12,165,40);
    C.strokeStyle=gps?'rgba(0,212,170,0.38)':'rgba(255,80,80,0.38)';
    C.lineWidth=1; C.strokeRect(12,12,165,40);
    C.font='bold 9px ui-monospace,monospace';
    C.fillStyle=gps?'#00d4aa':'#ff6b6b';
    C.fillText(gps?'GNSS LOCKED':'GNSS DENIED',20,27);
    C.font='8px ui-monospace,monospace'; C.fillStyle='#9daec0';
    C.fillText('MODE: '+(gps?'GPS':'DEAD RECKONING'),20,41);
    /* lean box (scooter only) */
    if(mode==='scooter'&&Math.abs(veh.lean)>0.06){
      C.fillStyle='rgba(255,51,102,0.12)'; C.fillRect(W-168,12,156,40);
      C.strokeStyle='rgba(255,51,102,0.4)'; C.strokeRect(W-168,12,156,40);
      C.font='bold 9px ui-monospace,monospace'; C.fillStyle='#ff3366';
      C.fillText('LEAN '+(veh.lean>0?'L':'R')+' '+(Math.abs(veh.lean)*22).toFixed(1)+'deg',W-160,27);
      C.font='8px ui-monospace,monospace'; C.fillStyle='#9daec0';
      C.fillText('ROLL-COMPENSATED IMU',W-160,41);
    }
  }

  /* ============ PHONE MAP ============ */
  function drawPhoneMap(sv,gps){
    var pw=216, ph=160;
    PC.fillStyle='#080d13'; PC.fillRect(0,0,pw,ph);
    PC.strokeStyle='rgba(255,255,255,0.025)'; PC.lineWidth=0.5;
    for(var gx=0;gx<=pw;gx+=18){PC.beginPath();PC.moveTo(gx,0);PC.lineTo(gx,ph);PC.stroke();}
    for(var gy=0;gy<=ph;gy+=18){PC.beginPath();PC.moveTo(0,gy);PC.lineTo(pw,gy);PC.stroke();}
    if(scene>=1){PC.fillStyle='rgba(255,80,80,0.1)';PC.fillRect(14+200*0.208,ph*0.54-68,310*0.208,136);}
    PC.beginPath();
    for(var ri4=0;ri4<ROAD.length;ri4++){
      var mx6=14+ROAD[ri4].x*0.208, my6=ph*0.54-ROAD[ri4].y*0.45;
      if(ri4===0) PC.moveTo(mx6,my6); else PC.lineTo(mx6,my6);
    }
    PC.lineWidth=7; PC.strokeStyle='#1a2535'; PC.lineCap='round'; PC.stroke();
    PC.setLineDash([5,5]); PC.lineWidth=1; PC.strokeStyle='rgba(255,255,255,0.06)'; PC.stroke(); PC.setLineDash([]);
    if(scootTrail.length>1){
      PC.beginPath();
      for(var ti5=0;ti5<scootTrail.length;ti5++){
        var mx7=14+scootTrail[ti5].x*0.208, my7=ph*0.54-scootTrail[ti5].y*0.45;
        if(ti5===0) PC.moveTo(mx7,my7); else PC.lineTo(mx7,my7);
      }
      PC.strokeStyle='rgba(255,51,102,0.6)'; PC.lineWidth=1.5; PC.stroke();
    }
    if(carTrail.length>1&&scene>=1){
      PC.beginPath();
      for(var ti6=0;ti6<carTrail.length;ti6++){
        var mx8=14+carTrail[ti6].x*0.208, my8=ph*0.54-carTrail[ti6].y*0.45;
        if(ti6===0) PC.moveTo(mx8,my8); else PC.lineTo(mx8,my8);
      }
      PC.strokeStyle='rgba(74,158,255,0.5)'; PC.lineWidth=1.5; PC.stroke();
    }
    var dx3=14+sv.x*0.208, dy3=ph*0.54-sv.y*0.45;
    var ar=gps?5:(11+Math.sin(Date.now()/500)*2.5);
    PC.beginPath(); PC.arc(dx3,dy3,ar,0,Math.PI*2);
    PC.fillStyle=gps?'rgba(0,212,170,0.12)':'rgba(255,80,80,0.12)'; PC.fill();
    PC.beginPath(); PC.arc(dx3,dy3,3,0,Math.PI*2);
    PC.fillStyle=gps?'#00d4aa':'#ff6b6b';
    PC.shadowColor=PC.fillStyle; PC.shadowBlur=8; PC.fill(); PC.shadowBlur=0;
    /* lean needle */
    if(mode==='scooter'&&Math.abs(sv.lean)>0.08){
      PC.save(); PC.translate(pw-14,ph*0.5); PC.rotate(sv.lean);
      PC.strokeStyle='#ff3366'; PC.lineWidth=1.5;
      PC.beginPath(); PC.moveTo(0,-11); PC.lineTo(0,11); PC.stroke();
      PC.beginPath(); PC.moveTo(-3,-8); PC.lineTo(0,-12); PC.lineTo(3,-8); PC.stroke();
      PC.restore();
    }
  }

  /* ============ DOM ============ */
  function updateDOM(veh,gps){
    var spd=(35+Math.sin(veh.s*0.05)*5).toFixed(0);
    var lDeg=(veh.lean*22).toFixed(1);
    var drift=scene===0?'0.0':scene===1?(t*17.5).toFixed(1):(17.5-t*15.5).toFixed(1);
    if(elSpeed) elSpeed.textContent=spd+' km/h';
    if(elLean)  elLean.textContent=lDeg+'deg';
    if(elMode){ elMode.textContent=gps?'GNSS':'DEAD REC'; elMode.style.color=gps?'#00d4aa':'#ff3366'; }
    if(elDrift) elDrift.textContent=drift+'%';
    if(elNotif){
      if(scene===0) elNotif.textContent='GPS active. tracking';
      else if(scene===1&&t<0.3) elNotif.textContent='GNSS lost. switching to DR';
      else if(scene===1) elNotif.textContent='Dead reckoning. lean '+lDeg+'deg';
      else elNotif.textContent='GPS restored. loop closed';
    }
    if(elBars){
      var bars=elBars.querySelectorAll('div');
      var cnt=gps?4:Math.max(0,2-Math.floor(t*3));
      bars.forEach(function(b,i){b.style.background=i<cnt?'#00d4aa':'#2d3748';});
    }
    if(gpsDot&&gpsLbl){
      gpsDot.style.background=gps?'#00d4aa':'#ff6b6b';
      gpsDot.style.boxShadow='0 0 8px '+(gps?'#00d4aa':'#ff6b6b');
      gpsLbl.style.color=gps?'#00d4aa':'#ff6b6b';
      gpsLbl.textContent=gps?'GNSS LOCKED':'GNSS DENIED';
    }
  }

  /* ============ RENDER + TICK ============ */
  function render(){
    var sv=getScoot(), cv=getCar(), gps=isGPS();
    var activeV=mode==='scooter'?sv:cv;
    if(view==='pov') drawPOVView();
    else             drawMapView();
    drawPhoneMap(sv,gps);
    updateDOM(activeV,gps);
  }

  function tick(){
    if(!playing) return;
    t+=0.0035;
    if(t>=1){
      t=0; scene=(scene+1)%3;
      scootTrail.length=0; carTrail.length=0;
      if(sceneLbl) sceneLbl.textContent=SDEFS[scene].lbl;
      if(sceneDsc) sceneDsc.textContent=SDEFS[scene].desc;
    }
    var sv=getScoot(), cv=getCar();
    scootTrail.push({x:sv.x,y:sv.y});
    carTrail.push({x:cv.x,y:cv.y});
    if(scootTrail.length>200) scootTrail.shift();
    if(carTrail.length>200)   carTrail.shift();
    render();
    rafId=requestAnimationFrame(tick);
  }

  /* ============ CONTROLS ============ */
  function setMode(m){
    mode=m;
    var bS=document.getElementById('sim-mode-scoot');
    var bC=document.getElementById('sim-mode-car');
    if(bS){bS.style.background=m==='scooter'?'#ff3366':'transparent';bS.style.border=m==='scooter'?'none':'1px solid #1c232d';bS.style.color=m==='scooter'?'#fff':'#7a8999';bS.style.fontWeight=m==='scooter'?'700':'400';}
    if(bC){bC.style.background=m==='car'?'#4a9eff':'transparent';bC.style.border=m==='car'?'none':'1px solid #1c232d';bC.style.color=m==='car'?'#fff':'#7a8999';bC.style.fontWeight=m==='car'?'700':'400';}
    render();
  }
  function setView(v){
    view=v;
    var bP=document.getElementById('sim-view-pov');
    var bM=document.getElementById('sim-view-map');
    if(bP){bP.style.background=v==='pov'?'#0070f3':'transparent';bP.style.border=v==='pov'?'none':'1px solid #1c232d';bP.style.color=v==='pov'?'#fff':'#7a8999';bP.style.fontWeight=v==='pov'?'700':'400';}
    if(bM){bM.style.background=v==='map'?'#0070f3':'transparent';bM.style.border=v==='map'?'none':'1px solid #1c232d';bM.style.color=v==='map'?'#fff':'#7a8999';bM.style.fontWeight=v==='map'?'700':'400';}
    render();
  }

  if(btnPlay) btnPlay.addEventListener('click',function(){
    playing=!playing;
    btnPlay.innerHTML=playing?'&#9646;&#9646; Pause':'&#9654; Play';
    if(playing) tick();
  });
  if(btnNext) btnNext.addEventListener('click',function(){
    scene=(scene+1)%3; t=0; scootTrail.length=0; carTrail.length=0;
    if(sceneLbl) sceneLbl.textContent=SDEFS[scene].lbl;
    if(sceneDsc) sceneDsc.textContent=SDEFS[scene].desc;
    render();
  });
  if(btnPrev) btnPrev.addEventListener('click',function(){
    scene=(scene+2)%3; t=0; scootTrail.length=0; carTrail.length=0;
    if(sceneLbl) sceneLbl.textContent=SDEFS[scene].lbl;
    if(sceneDsc) sceneDsc.textContent=SDEFS[scene].desc;
    render();
  });

  document.addEventListener('click',function(e){
    if(e.target.id==='sim-mode-scoot') setMode('scooter');
    else if(e.target.id==='sim-mode-car') setMode('car');
    else if(e.target.id==='sim-view-pov') setView('pov');
    else if(e.target.id==='sim-view-map') setView('map');
  });

  if(sceneLbl) sceneLbl.textContent=SDEFS[0].lbl;
  if(sceneDsc) sceneDsc.textContent=SDEFS[0].desc;
  setTimeout(function(){ render(); },80);

})();

</script>
</body>
</html>
"""
