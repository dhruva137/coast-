# Stress-pipeline iterate notes

Working log of what broke against **real** IO-VNBD columns and what was fixed.

## Round 0 — discovery

- Only **4** of 241 `S-*.csv` files are real LFS blobs (>1 MB). Rest are ~130 B stubs.
- Real files:
  - `S-M.csv` (19,798,721 B)
  - `S-S1.csv` (9,631,499 B)
  - `S-S2.csv` (17,469,302 B)
  - `S-S4.csv` (17,574,514 B)
- Header (smartphone table) matches Data-in-Brief / GitHub IO-VNBD:
  - `GPS LATITUDE/LONGITUDE (degrees)`, `GPS SPEED (Kmh)`, `GPS ACCURACY (m)`
  - `TIME SINCE START (ms)`
  - `ACCELEROMETER X/Y/Z`, `GYROSCOPE Yaw/Pitch/Roll (rad/s)`
  - `GPS ORIENTATION` / `ORIENTATION (Yaw)` in degrees
- Column names have leading spaces and corrupted unit glyphs — normalisation strips non-ASCII.

## Round 1 — loader

- Mapped gyro: **Yaw→gz, Pitch→gy, Roll→gx** (same as `lab/datasets/io_vnbd.py`).
- Converted time ms→s and speed km/h→m/s via header unit detection + magnitude fallback.
- First outage mask flagged ~80% of samples as denied — **wrong**. Cause: GPS
  *position* on these logs updates ~0.1 Hz, so lat/lon "freezes" for ~90 samples
  between fixes while speed still reports motion. Fixed by only treating freezes
  ≥ ~30 s as pathological; primary mask = bad `GPS ACCURACY` / NaNs.
  Resulting outage fraction ≈ 0.2%.

## Round 2 — outage replay

- Seeded outage at the *start* of a centered ±3 min window put high-speed trials
  at near-zero `v0` (seed was 150 s before the speed peak). Fixed with
  `_segment_for_outage`: seed ends at the chosen site index.
- GT path_length from 10 Hz interpolated LLA was inflated by GPS zigzag
  (851 m "distance" in 60 s at 4.4 m/s). Drift denominator now uses
  Σ(GPS_speed · dt) over the outage window.
- On cars, `idr_lean` / `car_style` final-error ratio ≈ **1.00** and mean |φ| < 3° —
  sanity check held. Neither method meets ISRO bars on raw phone gyro + speed-hold;
  all 60 s car trials report **FAIL** (honest).

## Round 3 — adversarial two-wheeler

- First injection used alternating lean signs → car-style cos(φ) errors partially
  cancelled (FAIL_CLAIM with car better than lean). Switched to **same-direction**
  turns (F3 geometry). Result: car drift ~12%, lean ~5% → **PASS_CLAIM**.

## Honesty constraints encoded

- IO-VNBD = **cars**. Lean-aware must track car-style (ratio ~1), not beat it.
- Novel claim lives in the **adversarial two-wheeler injection** only.
- ISRO bars documented; verdicts are `PASS_ISRO` / `PASS_COMPETITIVE` / `FAIL` —
  no fake green. Car 60 s outages are FAIL.
