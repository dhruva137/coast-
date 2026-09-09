"""The COAST Command console page.

Deliberately dependency-free: no CDN, no map tiles, no web fonts. Everything
renders on a canvas so the whole console works with the venue's wifi dead, which
is the same property the phone app claims and the same one the demo relies on.

Design species is an operations console, not a phone app: dense, structured,
dark, information-first. See design_v3/00_DESIGN_THESIS.md.
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
        --faint:#5A6673;--accent:#00D4AA;--gnss:#4A9EFF;--bad:#FF6B6B;
        --mono:ui-monospace,Menlo,Consolas,monospace}
  *{box-sizing:border-box}
  body{margin:0;min-height:100dvh;background:var(--bg);color:var(--text);
       font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       padding:22px 18px calc(22px + env(safe-area-inset-bottom))}
  .wrap{max-width:30em;margin:0 auto}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:22px}
  .brand b{letter-spacing:.02em}
  .brand small{display:block;color:var(--dim);font-size:10px;letter-spacing:.07em;
               text-transform:uppercase;font-weight:400}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
        padding:18px;margin-bottom:14px}
  h1{font-size:20px;margin:0 0 6px}
  p{margin:0 0 12px;color:var(--dim);font-size:14px}
  .num{font-family:var(--mono);font-variant-numeric:tabular-nums}
  button{width:100%;border:0;border-radius:12px;padding:15px;font:600 16px system-ui;
         cursor:pointer;margin-bottom:10px}
  .go{background:var(--accent);color:#04120E}
  .go:disabled{opacity:.45}
  .ghost{background:transparent;color:var(--dim);border:1px solid var(--line)}
  .status{display:flex;align-items:center;gap:10px;padding:13px 15px;border-radius:12px;
          background:#11161E;border:1px solid var(--line);margin-bottom:12px}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--faint);flex:0 0 auto}
  .dot.on{background:var(--accent);box-shadow:0 0 10px var(--accent)}
  .dot.bad{background:var(--bad)}
  .kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:13.5px}
  .kv .k{color:var(--faint)}
  .kv .v{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
  .note{font-size:12.5px;color:var(--faint);line-height:1.5}
  code{font-family:var(--mono);font-size:12px;color:var(--accent);word-break:break-all}
  .warn{background:#1a1508;border:1px solid #46370f;color:#ffd166;border-radius:12px;
        padding:12px 14px;font-size:13px;margin-bottom:14px}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <svg width="26" height="26" viewBox="0 0 108 108" aria-hidden="true">
      <path fill="#00D4AA" d="M54,24 L70,60 L54,51 L38,60 Z"/>
      <path stroke="#00D4AA" stroke-width="7" stroke-linecap="round" stroke-opacity=".75" d="M54,67 L54,73"/>
      <path stroke="#00D4AA" stroke-width="7" stroke-linecap="round" stroke-opacity=".4" d="M54,80 L54,84"/>
    </svg>
    <div><b>COAST</b><small>pair this phone</small></div>
  </div>

  <div class="warn" id="ctx"></div>

  <div class="card">
    <h1>Put this phone on the console</h1>
    <p>Your position streams to the laptop dashboard so everyone can see it move.
       Nothing else is sent, and you can stop at any time.</p>
    <div class="status"><span class="dot" id="dot"></span><span id="msg">Not sharing yet</span></div>
    <button class="go" id="go">Start sharing my position</button>
    <button class="ghost" id="stop" style="display:none">Stop &amp; unpair</button>
    <div class="kv" id="stats" style="display:none">
      <span class="k">Sent</span><span class="v" id="n">0</span>
      <span class="k">Latitude</span><span class="v" id="la">—</span>
      <span class="k">Longitude</span><span class="v" id="lo">—</span>
      <span class="k">Accuracy</span><span class="v" id="ac">—</span>
      <span class="k">Speed</span><span class="v" id="sp">—</span>
    </div>
  </div>

  <div class="card">
    <p class="note"><b style="color:var(--text)">What this demo is, honestly.</b>
      This browser page shares your phone's <b>GPS</b>. It demonstrates the fleet console —
      many phones tracked live, with their paths. It is <b>not</b> dead reckoning:
      keeping the dot moving <i>after</i> GPS dies is what the COAST Android app does,
      using the accelerometer and gyroscope plus the road map.</p>
    <p class="note" style="margin-top:10px">Install the app for the real thing:</p>
    <a href="/download/apk" style="text-decoration:none"><button class="ghost">Download the APK</button></a>
  </div>

  <div class="card">
    <p class="note">Session <code id="tok">—</code><br/>
      Expires automatically. No account, no device identifier, nothing kept after you unpair.</p>
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
  $("#ctx").textContent = "Heads up: browsers only give location to secure (https) pages or "
    + "localhost. Over plain http on a LAN address, Start may be refused — use the COAST app "
    + "instead, which has no such restriction.";
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
    .catch(e=>{ $("#dot").className="dot bad"; $("#msg").textContent="Cannot reach console at "+base; });
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
<style>
  :root{
    --bg:#07090D; --panel:#0C1016; --panel2:#11161E; --line:#1C232D;
    --text:#E8EDF2; --dim:#8B97A6; --faint:#5A6673;
    --accent:#00D4AA; --gnss:#4A9EFF; --warn:#FFD166; --bad:#FF6B6B;
    --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --sans:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:var(--bg);color:var(--text);font:14px/1.5 var(--sans);
       display:flex;flex-direction:column;overflow:hidden}
  .num{font-variant-numeric:tabular-nums;font-family:var(--mono)}

  header{display:flex;align-items:center;gap:16px;padding:10px 18px;
         border-bottom:1px solid var(--line);background:var(--panel);flex:0 0 auto}
  .brand{display:flex;align-items:center;gap:10px;font-weight:600;letter-spacing:.02em}
  .brand svg{display:block}
  .brand small{color:var(--dim);font-weight:400;letter-spacing:.06em;
               text-transform:uppercase;font-size:10px}
  .pills{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}
  .pill{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;
        background:var(--panel2);border:1px solid var(--line);font-size:12px;color:var(--dim)}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--faint)}
  .dot.on{background:var(--accent);box-shadow:0 0 8px var(--accent)}
  .dot.warn{background:var(--warn)}

  nav{display:flex;gap:2px;padding:0 12px;border-bottom:1px solid var(--line);
      background:var(--panel);flex:0 0 auto}
  nav button{background:none;border:0;color:var(--dim);padding:10px 16px;cursor:pointer;
             font:inherit;border-bottom:2px solid transparent;transition:color .15s}
  nav button:hover{color:var(--text)}
  nav button.sel{color:var(--text);border-bottom-color:var(--accent)}

  main{flex:1 1 auto;min-height:0;position:relative}
  .tab{position:absolute;inset:0;display:none;padding:14px;gap:14px}
  .tab.sel{display:flex}

  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;
         display:flex;flex-direction:column;min-height:0;min-width:0}
  .panel > h2{margin:0;padding:11px 14px;font-size:11px;letter-spacing:.09em;
              text-transform:uppercase;color:var(--dim);font-weight:600;
              border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px}
  .panel > h2 .sp{margin-left:auto;font-weight:400;letter-spacing:0;text-transform:none}
  .body{padding:12px 14px;overflow:auto;min-height:0}
  .body.flush{padding:0}

  canvas{display:block;width:100%;height:100%}
  .cwrap{position:relative;flex:1 1 auto;min-height:0}
  .legend{position:absolute;left:12px;bottom:10px;display:flex;gap:14px;font-size:11px;
          color:var(--dim);background:rgba(7,9,13,.78);padding:6px 10px;border-radius:6px;
          border:1px solid var(--line)}
  .legend i{display:inline-block;width:14px;height:0;border-top-width:2px;
            border-top-style:solid;vertical-align:middle;margin-right:5px}
  .scalebar{position:absolute;right:12px;bottom:10px;font-size:11px;color:var(--dim);
            background:rgba(7,9,13,.78);padding:5px 9px;border-radius:6px;
            border:1px solid var(--line)}

  .rail{width:262px;flex:0 0 262px}
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
  .kv .v{font-family:var(--mono);font-variant-numeric:tabular-nums}

  .stat{display:flex;flex-direction:column;gap:2px;padding:9px 0}
  .stat .lab{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
  .stat .val{font-size:23px;font-family:var(--mono);font-variant-numeric:tabular-nums;
             line-height:1.15}
  .stat .sub{font-size:11px;color:var(--dim)}

  button.act{background:var(--accent);color:#04120E;border:0;border-radius:8px;
             padding:9px 15px;font:600 13px var(--sans);cursor:pointer}
  button.act:hover{filter:brightness(1.08)}
  button.act:disabled{opacity:.45;cursor:default;filter:none}
  button.ghost{background:transparent;color:var(--dim);border:1px solid var(--line);
               border-radius:8px;padding:8px 13px;font:13px var(--sans);cursor:pointer}
  button.ghost:hover{color:var(--text);border-color:var(--dim)}
  button.danger{border-color:#4a2226;color:#ff9d9d}
  button.danger:hover{background:#1d0f11;color:#ffbcbc;border-color:#6b2f35}

  .qrbox{background:#fff;border-radius:10px;padding:10px;display:inline-block;line-height:0}
  .qrbox svg{width:186px;height:186px;display:block}
  .muted{color:var(--dim);font-size:12px}
  .tiny{color:var(--faint);font-size:11px}
  code{font-family:var(--mono);font-size:11.5px;color:var(--accent);word-break:break-all}

  table{border-collapse:collapse;width:100%;font-size:12.5px}
  th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--faint);font-weight:600;font-size:10.5px;letter-spacing:.07em;
     text-transform:uppercase;position:sticky;top:0;background:var(--panel)}
  td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;
       white-space:nowrap}
  .tagm{color:var(--accent)} .tagn{color:var(--warn)} .tagd{color:var(--gnss)}
  .tagh{color:var(--faint)}

  .empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
         gap:12px;height:100%;color:var(--dim);text-align:center;padding:24px}
  .banner{padding:9px 12px;border-radius:8px;font-size:12.5px;margin-bottom:10px}
  .banner.err{background:#1d0f11;border:1px solid #4a2226;color:#ff9d9d}
  .banner.note{background:var(--panel2);border:1px solid var(--line);color:var(--dim)}
  .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .grow{flex:1 1 auto;min-width:0}
  .col{display:flex;flex-direction:column;gap:14px;min-height:0}
  .bars{display:flex;flex-direction:column;gap:11px}
  .bar{display:flex;flex-direction:column;gap:4px}
  .bar .top{display:flex;justify-content:space-between;font-size:12px}
  .bar .top b{font-family:var(--mono);font-variant-numeric:tabular-nums;font-weight:600}
  .track{height:9px;border-radius:5px;background:var(--panel2);overflow:hidden;
         border:1px solid var(--line)}
  .fill{height:100%;border-radius:5px;background:var(--accent)}
  .fill.dim{background:var(--gnss)} .fill.warnc{background:var(--warn)}
</style>
</head>
<body>

<header>
  <div class="brand">
    <svg width="24" height="24" viewBox="0 0 108 108" aria-hidden="true">
      <path fill="#00D4AA" d="M54,24 L70,60 L54,51 L38,60 Z"/>
      <path stroke="#00D4AA" stroke-width="7" stroke-linecap="round" stroke-opacity=".75" d="M54,67 L54,73"/>
      <path stroke="#00D4AA" stroke-width="7" stroke-linecap="round" stroke-opacity=".4" d="M54,80 L54,84"/>
    </svg>
    <div>COAST&nbsp;Command<br/><small>GNSS-denied navigation · SIH 26168</small></div>
  </div>
  <div class="pills">
    <span class="pill"><span class="dot on" id="p-srv"></span><span id="p-srv-t">server</span></span>
    <span class="pill"><span class="dot" id="p-dev"></span><span id="p-dev-t">0 devices</span></span>
    <span class="pill"><span class="dot" id="p-trn"></span><span id="p-trn-t">idle</span></span>
    <span class="pill"><span class="dot on"></span>offline-capable</span>
  </div>
</header>

<nav>
  <button data-tab="fleet" class="sel">Fleet</button>
  <button data-tab="train">Training</button>
  <button data-tab="engine">Engine</button>
  <button data-tab="evidence">Evidence</button>
</nav>

<main>
  <!-- ================= FLEET ================= -->
  <section class="tab sel" id="tab-fleet">
    <div class="panel rail col" style="gap:0">
      <h2>Devices <span class="sp num" id="dev-count">0</span></h2>
      <div class="body" id="dev-list" style="flex:1 1 auto">
        <div class="empty tiny">No phone paired yet.<br/>Scan the code to add one.</div>
      </div>
      <div style="border-top:1px solid var(--line);padding:12px 14px">
        <button class="ghost" id="btn-forget-all" style="width:100%">Forget all devices</button>
      </div>
    </div>

    <div class="panel grow">
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

    <div class="panel" style="width:300px;flex:0 0 300px">
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

  <!-- ================= TRAINING ================= -->
  <section class="tab" id="tab-train">
    <div class="panel grow col" style="gap:0">
      <h2>Model learning — held-out drive
        <span class="sp tiny" id="tr-held">re-integrated with the current weights after every epoch</span></h2>
      <div class="cwrap"><canvas id="cv-traj"></canvas>
        <div class="legend">
          <span><i style="border-color:#E8EDF2"></i>CAN truth</span>
          <span><i style="border-color:#FF6B6B"></i>hold-last-speed baseline</span>
          <span><i style="border-color:var(--accent)"></i>COAST @ epoch <b class="num" id="tr-ep">0</b></span>
        </div>
        <div class="scalebar num" id="traj-scale">—</div>
      </div>
      <div style="border-top:1px solid var(--line);height:150px;flex:0 0 150px">
        <canvas id="cv-loss"></canvas>
      </div>
    </div>

    <div class="panel rail">
      <h2>Run</h2>
      <div class="body">
        <div id="tr-banner"></div>
        <div class="stat"><span class="lab">Epoch</span>
          <span class="val" id="s-ep">—</span><span class="sub" id="s-ep-sub">not started</span></div>
        <div class="stat"><span class="lab">Train loss</span><span class="val" id="s-loss">—</span></div>
        <div class="stat"><span class="lab">Held-out RMSE</span>
          <span class="val" id="s-rmse">—</span><span class="sub">m/s · never trained on</span></div>
        <div class="stat"><span class="lab">Elapsed</span><span class="val" id="s-el">—</span></div>
        <div style="height:10px"></div>
        <button class="act" id="btn-train" style="width:100%">Train now</button>
        <p class="tiny" style="margin-top:10px">Runs <code>python -m lab.demo</code> as a real
          subprocess. Every point plotted is parsed from its stdout — nothing is simulated. If it
          fails you will see the error, not a curve.</p>
        <div class="banner note" style="margin-top:10px">Fast re-run. The committed
          <b class="num">2.02×</b> headline is the full protocol under
          <code>lab/stress/results/mapfilter/</code>.</div>
        <div id="figs"></div>
      </div>
    </div>
  </section>

  <!-- ================= ENGINE ================= -->
  <section class="tab" id="tab-engine">
    <div class="panel grow">
      <h2>C++ edge engine — measured throughput <span class="sp tiny">core/cpp/apps/README.md</span></h2>
      <div class="body" id="eng-body"><div class="empty tiny">loading…</div></div>
    </div>
    <div class="panel rail">
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
    </div>
  </section>

  <!-- ================= EVIDENCE ================= -->
  <section class="tab" id="tab-evidence">
    <div class="panel grow">
      <h2>Claim registry <span class="sp tiny">every number re-derived from its measured file</span></h2>
      <div class="body flush"><table id="claims"><tbody><tr><td class="tiny">loading…</td></tr></tbody></table></div>
    </div>
    <div class="panel rail">
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
</main>

<script>
"use strict";
const $ = s => document.querySelector(s);
const fmt = (v, d=2) => (v===null||v===undefined||Number.isNaN(v)) ? "—" : Number(v).toFixed(d);
const commas = v => Math.round(v).toLocaleString("en-US");

/* ---------- tabs ---------- */
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button").forEach(x => x.classList.remove("sel"));
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("sel"));
  b.classList.add("sel");
  $("#tab-" + b.dataset.tab).classList.add("sel");
  resizeAll();
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
// Fit a set of [x,y] paths into the canvas with equal aspect, return a projector.
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
  g.fillStyle="#07090D"; g.fillRect(0,0,w,h);
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
  const cv=$("#cv-fleet"); if(!cv.getBoundingClientRect().width) return;
  const {g,w,h}=fit(cv); gridBg(g,w,h);
  const devs=fleet.devices.filter(d=>d.points && d.points.length);
  if(!devs.length){
    g.fillStyle="#5A6673"; g.font="13px system-ui"; g.textAlign="center";
    g.fillText("No positions yet — pair a phone and start moving.", w/2, h/2);
    $("#fleet-scale").textContent="—"; return;
  }
  const lat0=devs[0].points[0].lat, lon0=devs[0].points[0].lon;
  const paths=devs.map(d=>d.points.map(p=>llToXY(p.lat,p.lon,lat0,lon0)));
  const pr=projector(paths,w,h,44); if(!pr) return;

  devs.forEach((d,i)=>{
    // Segment the track by mode so a colour change marks the moment GNSS died.
    const pts=paths[i]; let run=[pts[0]]; let mode=d.points[0].mode;
    for(let k=1;k<pts.length;k++){
      const m=d.points[k].mode;
      if(m!==mode){
        run.push(pts[k]);
        stroke(g,run,pr, mode==="IDR"?"#00D4AA":"#4A9EFF", mode==="IDR"?3:2.2, mode==="HOLD"?[4,4]:null);
        run=[pts[k]]; mode=m;
      } else run.push(pts[k]);
    }
    stroke(g,run,pr, mode==="IDR"?"#00D4AA":"#4A9EFF", mode==="IDR"?3:2.2, mode==="HOLD"?[4,4]:null);

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
  $("#p-dev").className = "dot" + (on?" on":"");
  if(!fleet.devices.length){
    el.innerHTML='<div class="empty tiny">No phone paired yet.<br/>Scan the code to add one.</div>';
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
    const r=await fetch("/api/fleet"); fleet=await r.json();
    $("#p-srv").className="dot on"; $("#p-srv-t").textContent="server up";
    renderDevices(); drawFleet();
    if(selected && !fleet.devices.some(d=>d.device_id===selected)){ selected=null; $("#privacy").innerHTML=""; }
  }catch(e){ $("#p-srv").className="dot warn"; $("#p-srv-t").textContent="server unreachable"; }
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

/* ================= TRAINING ================= */
let tr = {truth:[], hold:[], epochs:[], cur:null, prev:null, mix:1, held:""};
function drawTraj(){
  const cv=$("#cv-traj"); if(!cv.getBoundingClientRect().width) return;
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
  // Cross-fade between the previous epoch's path and the current one so the eye
  // reads improvement as motion rather than as a cut.
  if(tr.prev && tr.mix<1){ g.globalAlpha=1-tr.mix; stroke(g,tr.prev,pr,"#00D4AA",2.2); g.globalAlpha=1; }
  if(tr.cur){ g.globalAlpha=tr.mix; stroke(g,tr.cur,pr,"#00D4AA",3); g.globalAlpha=1; }
  const barM=niceScale(pr.spanM/4);
  $("#traj-scale").textContent = (barM>=1000?(barM/1000)+" km":barM+" m");
  g.strokeStyle="#5A6673"; g.lineWidth=2; g.beginPath();
  g.moveTo(w-24-barM*pr.s,h-38); g.lineTo(w-24,h-38); g.stroke();
}
function drawLoss(){
  const cv=$("#cv-loss"); if(!cv.getBoundingClientRect().width) return;
  const {g,w,h}=fit(cv);
  g.fillStyle="#0C1016"; g.fillRect(0,0,w,h);
  const eps=tr.epochs; const pad=26;
  if(eps.length<1){
    g.fillStyle="#5A6673"; g.font="11px system-ui"; g.textAlign="center";
    g.fillText("loss / held-out RMSE", w/2, h/2); return;
  }
  const series=[
    {key:"loss", col:"#FFD166", lab:"train loss"},
    {key:"rmse", col:"#00D4AA", lab:"held-out RMSE"},
  ];
  const n=Math.max(eps.length, 2);
  series.forEach(s=>{
    const vals=eps.map(e=>e[s.key]).filter(v=>Number.isFinite(v));
    if(!vals.length) return;
    const lo=Math.min(...vals), hi=Math.max(...vals), span=Math.max(hi-lo,1e-9);
    g.strokeStyle=s.col; g.lineWidth=2; g.lineJoin="round"; g.beginPath();
    eps.forEach((e,i)=>{
      const X=pad+(w-2*pad)*(i/(n-1));
      const Y=h-pad-(h-2*pad)*((e[s.key]-lo)/span);
      i?g.lineTo(X,Y):g.moveTo(X,Y);
    });
    g.stroke();
    const last=eps[eps.length-1];
    g.fillStyle=s.col; g.font="600 10px ui-monospace,monospace"; g.textAlign="right";
    g.fillText(s.lab+" "+fmt(last[s.key],3), w-6, series.indexOf(s)*13+14);
  });
  g.strokeStyle="#1C232D"; g.beginPath(); g.moveTo(pad,h-pad); g.lineTo(w-pad,h-pad); g.stroke();
}
function animateMix(){
  if(tr.mix<1){ tr.mix=Math.min(1,tr.mix+0.06); drawTraj(); requestAnimationFrame(animateMix); }
}
function onEpoch(e){
  tr.epochs.push(e);
  if(e.path && e.path.length){ tr.prev=tr.cur; tr.cur=e.path; tr.mix=0; requestAnimationFrame(animateMix); }
  $("#s-ep").textContent=e.epoch+" / "+e.epochs;
  $("#s-ep-sub").textContent=e.mode+" objective";
  $("#tr-ep").textContent=e.epoch;
  $("#s-loss").textContent=fmt(e.loss,4);
  $("#s-rmse").textContent=fmt(e.rmse,3);
  $("#s-el").textContent=fmt(e.elapsed_s,1)+"s";
  $("#p-trn").className="dot on"; $("#p-trn-t").textContent="training epoch "+e.epoch;
  drawLoss(); drawTraj();
}
function trainBanner(html, cls){ $("#tr-banner").innerHTML = html?`<div class="banner ${cls}">${html}</div>`:""; }

$("#btn-train").onclick=async()=>{
  const b=$("#btn-train"); b.disabled=true; b.textContent="Training…";
  tr={truth:[],hold:[],epochs:[],cur:null,prev:null,mix:1,held:""};
  trainBanner(""); $("#figs").innerHTML=""; drawTraj(); drawLoss();
  try{ await fetch("/train/start",{method:"POST"}); }
  catch(e){ trainBanner("Could not start training: "+e,"err"); b.disabled=false; b.textContent="Train now"; return; }
  const es=new EventSource("/train/stream");
  es.onmessage=ev=>{
    let d; try{ d=JSON.parse(ev.data); }catch(_){ return; }
    if(d.type==="traj_ref"){ tr.truth=d.truth||[]; tr.hold=d.hold_baseline||[]; tr.held=d.held||"";
      $("#tr-held").textContent="held-out drive "+tr.held+" · re-integrated after every epoch"; drawTraj(); }
    else if(d.type==="epoch"){ onEpoch(d); }
    else if(d.type==="error"){ trainBanner("Training failed: "+(d.error||"unknown"),"err"); }
    else if(d.type==="done"){
      es.close(); b.disabled=false; b.textContent="Train again";
      $("#p-trn").className="dot"; $("#p-trn-t").textContent = d.returncode===0?"run complete":"run failed";
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
async function loadEngine(){
  try{
    const r=await fetch("/api/engine"); const d=await r.json();
    if(d.error){ $("#eng-body").innerHTML=`<div class="banner err">${d.error}</div>`; return; }
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
  }catch(e){ $("#eng-body").innerHTML=`<div class="banner err">Could not read engine benchmarks.</div>`; }
}

/* ================= EVIDENCE ================= */
async function loadClaims(){
  try{
    const r=await fetch("/api/claims"); const d=await r.json();
    const cls=c=>({measured:"tagm","measured-negative":"tagn",derived:"tagd",historical:"tagh"}[c]||"tagh");
    $("#claims").innerHTML =
      "<thead><tr><th>claim</th><th>value</th><th>confidence</th><th>source</th></tr></thead><tbody>"+
      d.claims.map(c=>`<tr>
        <td><b>${c.id}</b><div class="tiny">${c.statement}</div></td>
        <td class="n">${c.value===null?"—":(Math.abs(c.value)>=1000?commas(c.value):fmt(c.value,2))} ${c.unit}</td>
        <td class="${cls(c.confidence)}">${c.confidence}</td>
        <td class="tiny"><code>${c.source_file}</code></td></tr>`).join("")+"</tbody>";
  }catch(e){
    $("#claims").innerHTML='<tbody><tr><td class="tiny">Could not read the claim registry. '+
      'Run <code>python tools/verify_claims.py --json</code>.</td></tr></tbody>';
  }
}

/* ---------- boot ---------- */
function resizeAll(){ drawFleet(); drawTraj(); drawLoss(); }
window.addEventListener("resize", resizeAll);
newQR(); pollFleet(); loadEngine(); loadClaims();
setInterval(pollFleet, 1000);
setTimeout(resizeAll, 60);
</script>
</body>
</html>
"""
