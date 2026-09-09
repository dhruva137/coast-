# COAST — Demo video script (60–90 s)

**Purpose:** pre-recorded Round-2 backup (rules allow it). Shoot once; keep on
the laptop. Spoken lines are presenters' VO; on-screen action is the A-roll.

**Honesty:** replay = real IO-VNBD sensors through the real estimator. **2.02×**
cites the full mapfilter run (`lab/stress/results/mapfilter/summary.md`);
`python -m lab.demo` is a fast re-run of the method that regenerates figures.
F8: no user data leaves the device; basemap-off = zero network (app still
declares INTERNET for tiles — do not say "no INTERNET permission").

**Total target:** ~75 s (edit room 60–90).

---

## Shot list

| # | Time | Visual | Spoken line (VO) |
|---|------|--------|------------------|
| 1 | 0:00–0:08 | Title card: **COAST** + tagline on dark map still | “COAST — when GPS dies, you coast on sensors. Problem 26168, ISRO.” |
| 2 | 0:08–0:22 | **Phone, airplane mode ON.** Drive tab: REPLAY on, GNSS green track on dark basemap | “Airplane mode. Real recorded drive, real estimator. GPS is live on the track.” |
| 3 | 0:22–0:38 | Tap **SIMULATE BLACKOUT**. Pill flips to IDR / amber. Teal puck keeps the road; **red ghost diverges** off-road | “Simulate blackout. Our estimate stays on the road. Naive dead reckoning — the ghost — flies off.” |
| 4 | 0:38–0:55 | Cut to **laptop terminal**: `python -m lab.demo` scrolling epochs → writes `figures/` | “On the laptop: python -m lab.demo — a fast re-run of the method. Same plots as the deck in under ninety seconds.” |
| 5 | 0:55–1:05 | Open `figures/trajectory_overlay.png` (truth / naive / ours). Optional flash of CDF + drift | “Headline improvement is two-point-oh-two times better than free dead reckoning — from the full mapfilter run of forty-three outages, not invented live.” |
| 6 | 1:05–1:15 | **Laptop browser:** localhost phone-tracker page; live / last phone dot (tracker flavor, LAN) | “Optional demo build: the phone’s estimate on this laptop over the LAN only — opt-in, not the shipping privacy path.” |
| 7 | 1:15–1:20 | End card: F8 one-liner + “source files on request” | “No user data leaves the device. Basemap off — zero network. Every number has a file.” |

---

## Shot detail (director notes)

### Shot 2 — Airplane blackout setup
- Confirm status bar shows airplane / no cellular Wi‑Fi (or airplane).
- Settings → Replay mode ON; Show ghost car ON; Basemap ON (or bundled mbtiles).
- START → wait until GNSS pill shows sats / green track (~2–3 s of A-roll).

### Shot 3 — Ghost diverging
- Large tap on **SIMULATE BLACKOUT** (or Settings equivalent).
- Hold 8–12 s so divergence is obvious: teal hugs street, red ghost leaves the graph.
- Do **not** narrate a confidence radius.

### Shot 4 — `lab.demo`
- Pre-warm once before the take so wall time ≤90 s.
- Framing line if a judge asks: “fast re-run of the method; **2.02×** is the full committed mapfilter summary.”

### Shot 6 — Tracker page
- `tracker` flavor + Settings “Stream to laptop” + LAN IP; laptop `python -m web.tracker_server` (or project’s documented command).
- Say **LAN-only / opt-in** once — protects F8 for `standard`.

---

## Audio / edit checklist

- [ ] No invented metrics; no “no INTERNET permission”
- [ ] No sub-10% COAST tunnel claim; 10%/17% are free-DR baselines
- [ ] Burn in lower-third once: `lab/stress/results/mapfilter/summary.md → 2.02×`
- [ ] Export 1080p H.264 + a silent cut for venue projectors if VO fails
