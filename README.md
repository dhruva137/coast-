# IDR — Intelligent Dead Reckoning

Smartphone SDK for ride-hailing / delivery / ambulance when GNSS dies. Lean-aware dead reckoning for two-wheelers. Framed for ISRO / fleet buyers (SIH problem 26168).

**Current progress:** see [`PROGRESS.md`](PROGRESS.md) (updated 4 Sep 2026). Android field logger **v0.3.0** — RECORD + quality gate + session zip; deployment gate still red until real scooter logs.

## Product quickstart

```bash
npm install
npm run dev
```

Open **http://localhost:26168**

1. **Landing** — brand IDR, product pitch, SDK tiers, claims / ISRO bars  
2. **Open console** — Acts 1–5 research HUD on a full-bleed MapLibre map  
3. **Run live demo** — jumps into Act 1 and starts estimating immediately  

Everything is client-side. No API keys. No backend. Build the web app with `npm run build -w @sih26168/web`.

## Why this exists

Published vehicle DR assumes a car that cannot lean. India runs on ~200 million scooters and motorcycles. We treat outage navigation as a **graph decision** ("which ramp did you take"), not a regression.

## What to show a jury (5 minutes)

1. **Act 1 — Handoff.** GPS dies in the basement. The dot keeps moving. Loop-closure error is the score.
2. **Act 2 — Vehicle.** Same bicycle ride: car-style AI-IMU baseline vs lean-aware IDR.
3. **Act 3 — Tunnel.** Underpass replay vs ISRO's <10% / <100 m per km.
4. **Act 4 — Branch.** Junction posterior: the metric drivers actually feel.
5. **Act 5 — Ask.** SDK for ride-hailing, delivery, ambulance. Zero extra hardware.

## Layout

| Path | What |
|---|---|
| `core/ts` | Lean solver, InEKF, graph particle filter, simulator (the maths) |
| `core/cpp` | C++17 port + golden-vector tests |
| `web` | MapLibre research console / judge demo |
| `android` | Kotlin RECORD + SESSIONS + NAVIGATE (v0.3.0 field logger) |
| `lab` | Python experiments F1–F12, training, eval |
| `maps` | Offline campus graph |
| `SIH26168_PROJECT_BIBLE.md` | Problem, claims, execution |

## Architecture

- Product mode uses **vector edge embeddings** with particle filter only at junctions (see `docs/ARCHITECTURE_VECTOR.md`).

## Novel, defensible claims (say only this)

- First smartphone DR system that handles **leaning two-wheelers**
- Fixed-point coordinated-turn solver with `cos(Δφ)` insensitivity
- Error budget: heading hurts 6.3× more than speed
- **Branch-decision accuracy** as the user metric

Do not claim discovery of roll/yaw kinematics (textbook) or map-matching (Newson & Krumm 2009).

## Lab

```bash
pip install -r lab/requirements.txt
python lab/research/run_all.py
python lab/models/train_avnet.py
python lab/eval/harness.py
```

## Benchmark

ISRO: < 10% drift · < 100 m error over 1 km at 60 km/h · 10 Hz on-device.

## Claim Verification

Every number we publish is linted against `win_tuning/CLAIMS.json`.

```bash
python tools/verify_claims.py
python tools/verify_all.py
```

Readiness gates are intentionally distinct:

```bash
npm run gate:prototype   # may report RESEARCH_PROTOTYPE_PASS; not deployment
npm run gate:deployment  # default-strength gate; currently fails
```

## Licence

Prototype for Smart India Hackathon 2026. Dataset IO-VNBD remains under its upstream licence.
