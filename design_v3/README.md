# `design_v3/` — the design and platform layer

**Status: design only. No code changes have been made.** Cursor is still working
on the previous wave; this folder is ready to hand over when it finishes.

Where `win_tuning/` decides *how we score*, this folder decides *what we build
and what it looks like.*

---

## Read in this order

| # | File | What it decides |
|---|---|---|
| 1 | **`00_DESIGN_THESIS.md`** | **Start here.** Why the UI feels wrong (one structural mistake), the design principles, and the three moments that decide the demo. |
| 2 | **`01_PS_COMPLIANCE_AUDIT.md`** | Every explicit problem-statement requirement vs what is actually in the repo. **The most important file for Round 2 Q&A.** |
| 3 | `02_PLATFORM_ARCHITECTURE.md` | Hosting, QR pairing, LAN-vs-internet, the domain, auth. All free, all verified 9 Sep 2026. |
| 4 | `03_APP_DESIGN_SPEC.md` | Navigator: the logo root cause, splash, Vehicle Check, theming, two live bugs. |
| 5 | `04_DASHBOARD_DESIGN_SPEC.md` | Command: Fleet view, the four screens, the visual system, empty states. |
| 6 | `05_LIVE_TRAINING_VISUALIZATION.md` | The per-epoch trajectory replay — the best visual we are not yet using. |
| 7 | `06_PRIVACY_MODEL_FOR_TRACKING.md` | How live tracking coexists with "nothing leaves the device". |
| 8 | `07_DEMO_CHOREOGRAPHY.md` | The QR-pairing demo, minute by minute, with a five-rung fallback ladder. |
| 9 | `08_STRETCH_DOMAINS.md` | Aviation, logistics security, and exactly where the honesty line is. |

---

## The five findings that matter most

**1. The UI feels wrong for one structural reason.** A navigation app and an
operations dashboard are opposite design problems — one hides information, the
other reveals it — and we have been building them as one product. Split them into
**COAST Navigator** (phone) and **COAST Command** (laptop). They share a palette
and a logo, nothing else. *(`00`)*

**2. The logo problem has a concrete root cause.** `ic_launcher_fg.png` is
actually a **1024×1024 JPEG renamed `.png`**. JPEG has no alpha, so the icon
foreground is an opaque square that the launcher mask crops — hence the visible
box and cut corners. It also sits in density-less `res/drawable/`, so it upscales
~4× and blurs. And there is **no splash screen at all** — no `core-splashscreen`
dependency exists, and the theme still parents a 2014 framework theme. *(`03`)*

**3. Two live bugs found.** The manifest declares
`uses-feature gyroscope required="true"`, which would make Google Play **filter
the app out entirely** for gyro-less devices. And on targetSdk 35, the `dataSync`
foreground service hits Android 15's 6-hour cap and crashes because `onTimeout()`
is not implemented. *(`03` §D)*

**4. The demo's biggest risk is the venue network, and it has a free fix.**
**AP isolation** is the default on most guest wifi and would silently kill
phone→laptop traffic. Run the laptop as a **Windows Mobile Hotspot** — the host is
always at `192.168.137.1`, hotspots do not isolate clients, and the QR can carry
that fixed address. The QR encodes **both** a LAN and a relay endpoint, and the
app races them. *(`02`)*

**5. Our biggest PS compliance gap is the AI fusion engine.** The PS asks for an
**AI-based** GNSS+INS fusion model; ours is a classical EKF measuring **1.07× — a
wash**. We are also at **16.8% drift against a 10% benchmark**. Both must be
volunteered before a judge finds them. Separately, the **magnetometer is captured
but not used** — that needs a stated reason, ideally a measured one. *(`01`)*

---

## The best new ideas in here

- **Per-epoch trajectory replay** — after every training epoch, re-run inference
  on a held-out drive and redraw the path. The judge *watches the line snap onto
  the road* as the model learns. Legible without any explanation, and far
  stronger evidence than a loss curve. *(`05`)*
- **"What we know about you"** — a live panel showing every field held about a
  paired device, and a delete button pressed in front of the judge. Turns the
  tracking-vs-privacy tension into our best F8 moment. *(`06`)*
- **Vehicle Check** — an aircraft-style pre-flight panel that surfaces the
  excellent sensor-probing work already in `DeviceProbe.kt`, and gives us an
  honest place to disclose the magnetometer decision. *(`03`)*
- **The PS authorises the stretch.** Requirement six explicitly asks for an edge
  engine that works with *any* IMU, not just a phone's. Domain generality is
  compliance work, not scope creep. *(`08`)*

---

## Scope reality

Friday is two days away.

**Achievable by Friday:** laptop hotspot + fixed-IP tracker, QR generate/scan,
2–3 pre-installed phones, multi-phone fleet view, the icon fix, the splash, the
gyroscope manifest fix, marker interpolation.

**Finals scope (30 Sep):** `paper2anything.com` on Cloudflare Pages, the Render
relay, judge self-service APK download, accounts and session history, the
AI-based fusion engine.

**The Friday demo must work with zero internet.** Anything hosted is a bonus
surface, never the critical path.

---

## Not decided here

Nothing in this folder has been implemented. When Cursor finishes its current
wave, the intended order is:

1. Apply `win_tuning/PHASE0_BLOCKING_FIXES.md` (the six honesty defects)
2. The `03` §I priority list — icon, splash, manifest bug, marker interpolation
3. `04` Fleet view + `02` QR pairing
4. `05` per-epoch trajectory
5. Everything else

A separate implementer document with exact drop-in Android code (icon, splash,
theming, both bug fixes, marker interpolation, sensor degradation) accompanies
`03`.
