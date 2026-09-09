# Slide 5 — Proof it works *(F1, F5)*

**Status:** final text for paste into official SIH template. **Not** a finished `.pptx`.

## Conclusion headline (largest type)

**2.02× better median position error than free dead reckoning — on 43 real outages.**

## Dominant visual (one)

`diagrams/money_shot.png` (primary) — truth / free DR / COAST on the road network. Do **not** also place CDF + drift bars on this slide; those are backup/appendix.

## Support (≤18 pt body)

- **43** real GNSS outages — car **CAN-bus** ground truth (IO-VNBD)
- Free DR baseline pass: **17%** (short arm) / **10%** (tunnel arm)
- **Perfect gyro still fails 55%** → why the map is in the loop
- Footer: *Every number here has a source file we can open on request.*

## Sources

| Claim | Source |
|---|---|
| 2.02× median position error, 43 outages (8→17 pass) | **Full** run: `lab/stress/results/mapfilter/summary.md` |
| 17% / 10% free DR | `lab/stress/results/isro_benchmark/summary.md` |
| 55% perfect-yaw fail | `lab/stress/results/heading_ablation/summary.md` |

## `lab.demo`

- Live `python -m lab.demo` = **fast re-run of the method** (regenerates figures ≤90 s).
- Headline **2.02×** always cites the full mapfilter summary — never a quick-run substitute.
- Wording: **2.02× applies only to median position error**, not drift %.

## Assets (this folder)

- `diagrams/money_shot.png` (primary; also `.gif` / `.mp4`)
- `trajectory_overlay.png`, `cdf_error.png`, `drift_comparison.png` (backup / appendix)

## Speaker (~30 s)

> “On forty-three real GNSS outages, against the car’s own CAN ground truth, map-in-loop cuts median position error by two-point-oh-two times versus free dead reckoning — that’s the full mapfilter result file. Free DR passes seventeen percent short arm and ten percent tunnel arm — the baseline we beat. Perfect gyro still fails fifty-five percent.”

## Honesty

- Do **not** claim a sub-10% tunnel result for our filter.
- **10%** is free-DR tunnel-arm baseline, not a COAST pass rate.
- Do **not** show a confidence radius.
