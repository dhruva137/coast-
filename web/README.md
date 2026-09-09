# Web surfaces

## COAST live console (induction Block 3)

From the **repo root**:

```text
python -m web.coast_console
```

Open `http://127.0.0.1:8787/` on the laptop. One dark page with:

- **Live phone map** — GNSS `#4FC3F7` / IDR `#00E0A4` (same LAN ingest as the tracker)
- **Train** — runs real `python -m lab.demo` and streams epoch loss over SSE (not fake)
- **Algorithm ledger** — **2.02× lower median position error** (252.66 m → 125.20 m); median drift 27.6% → 16.8%; perfect-gyro fail 55%; ISRO 10%; each row cited
- **Figures** — inline `figures/*.png` after a successful train

### Endpoints

| Method | Path | Role |
|--------|------|------|
| GET | `/` | Console page |
| POST | `/ingest` | Phone LAN frames |
| GET | `/feed` | Latest + trail |
| POST | `/train` | Start `lab.demo` subprocess |
| GET | `/train/stream` | SSE real stdout / epoch metrics |
| GET | `/train/status` | Train snapshot JSON |
| GET | `/metrics` | Baseline ledger (committed summaries) |
| GET | `/figures/<name>` | Serve PNGs under `figures/` |

Bind: `0.0.0.0:8787`. Stdlib only.

### Honesty

Browser **Train** is a **fast re-run** (`lab.demo` quick AVNet + figure regen).
The headline **2.02× lower median position error** (252.66 m → 125.20 m) and
median drift **27.6%→16.8%** always cite
`lab/stress/results/mapfilter/summary.md`, not the short live session.
Perfect-gyro **55%** → `lab/stress/results/heading_ablation/summary.md`.
ISRO **17% / 10%** → `lab/stress/results/isro_benchmark/summary.md`.
If `mapfilter/report.json` is missing, the ledger shows an explicit error — never
remembered fallback numbers.

Enter this machine's **LAN IPv4** in the tracker-flavor app Settings (not
`127.0.0.1`). On Windows: `ipconfig` → **IPv4 Address** under Wi-Fi / Ethernet.

## Phone-tracker dashboard (map-only)

```text
python -m web.tracker_server
```

Same ingest/feed contract on port 8787 (map-only page). Prefer
`web.coast_console` when you also want live training + the measured ledger.
