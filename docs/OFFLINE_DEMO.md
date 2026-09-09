# Offline / airplane-mode demo checklist

Product insurance for Round 2. Pair with the generated F8 artifact
[`PRIVACY_REPORT.md`](PRIVACY_REPORT.md).

## Phone (standard APK)

1. Install the **standard** flavour (not tracker).
2. Enable airplane mode (or disable Wi‑Fi + mobile data).
3. Turn **basemap off** (SHOW GRID) — expect **zero** tile traffic.
4. Arm and navigate without a GNSS fix; estimator must still run.
5. Optional: with bundled MBTiles, basemap can still render locally on airplane mode.
6. Confirm Settings / About privacy copy uses the INTERNET wording:
   *Declared for public OSM/Carto basemap tiles only; with basemap off, network traffic is zero.*
   Never say “no INTERNET permission”.

## Tracker flavour (demo only)

1. Opt-in LAN uploader only; enter presenter laptop LAN IP.
2. Confirm **standard** never POSTs HUD frames (`TrackerHooks` no-op).

## Laptop console

```text
python -m web.coast_console
```

Open http://127.0.0.1:8787/

1. Cold start with Wi‑Fi off and no phone: page must still explain what it is
   (Train + ledger work; MapLibre/Chart CDN may fall back).
2. Press **Train** — on failure, real error in the log; **no invented loss curve**.
3. Ledger: without `lab/stress/results/mapfilter/report.json`, `/metrics` returns
   `report_error` and an empty ledger (FIX-2).

## Regenerate privacy proof

```text
python tools/privacy_report.py
python tools/verify_all.py
```
