# Heading fusion — does the compass reduce drift during an outage?

Reproduce: `python -m lab.stress.run_heading_fusion`

## Verdict

**Using the magnetometer for heading cuts drift 2.34x, and takes the median under the 10% bar.** Heading-induced drift falls from **16.87%** (gyro alone, today's behaviour) to **7.22%**, and the share of windows meeting the ISRO <10% criterion rises from **32%** to **61%**.

Compass-only (7.22%) and the complementary filter (7.23%) are **tied** on median drift — the gap is far inside the noise on 655 windows. The filter is marginally ahead on endpoint error (30.8 m vs 32.0 m) and pass rate, but not by enough to justify the extra state on that evidence alone. **Ship compass-only unless a tuning sweep separates them**; the gyro is still needed between compass samples and for rate limiting, so the filter stays the natural home if it later earns its place.

**This is implementable.** The only truth consulted after outage onset is the last GNSS bearing before the signal died, which any real system already holds. Unlike `../magnetometer/summary.md`, no per-drive oracle offset is granted.

**It also closes a problem-statement gap.** PS 26168 lists the magnetometer/compass among the app's inputs; we read it but did not fuse it. This is the measurement that says we should.

## Results (655 outage windows across 34 drives, 60 s each)

| heading policy | median drift | median endpoint error | median final heading error | windows under 10% |
|---|---:|---:|---:|---:|
| `gyro` — integrate yaw rate (today) | **16.87%** | 74.3 m | 17.7° | 32% |
| `compass` — onset-calibrated | **7.22%** | 32.0 m | 7.8° | 60% |
| `fused` — complementary, tau=6s | **7.23%** | 30.8 m | 7.9° | 61% |

## What this does and does not measure

Every policy integrates the **same true speed**, so the only difference between
the resulting paths is heading. That isolates the heading channel cleanly, and it
also means **these numbers are not an end-to-end system result**. The full
pipeline additionally carries speed-model error and gains the map-in-loop
correction; the headline
`lab/stress/results/mapfilter/summary.md` remains the system number.

The compass offset is calibrated **only** from the GNSS bearing at outage onset —
the last fix before the signal died. No truth is consulted afterwards, so this is
implementable on a phone. That is the difference between this study and
`../magnetometer/summary.md`, which granted a per-drive oracle offset.

## Limitations

- IO-VNBD is car data. A handlebar-mounted phone sits in a different magnetic
  environment and is not covered.
- A vehicle's magnetic environment is not constant: passing steel structures,
  and the vehicle's own electrics, move the field. Windows where that happens are
  in this sample, not excluded.
- Heading is integrated in the phone frame, which approximates vehicle yaw for a
  near-flat mount.
- Tau was not swept exhaustively; `--tau` is exposed so it can be.
