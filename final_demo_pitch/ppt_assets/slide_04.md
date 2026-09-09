# Slide 4 — The idea *(F1)*

**Status:** final text for paste into official SIH template. **Not** a finished `.pptx`.

## Conclusion headline (largest type)

**A perfect gyroscope still fails 55% — so we put the map in the loop.**

## Dominant visual (one)

`diagrams/money_shot.png` (or the three-bar contrast: post-hoc 0.98× | free DR 1.00× | map-in-loop **2.02×** median position error). One graphic only.

## Support (≤18 pt body)

- Naive dead-reckoning double-integrates noisy acceleration → drifts in ~15 s
- **Measured:** even with a **perfect** yaw sensor, free DR still fails **55%** of 60 s segments *(84/186 pass)* → the problem is **not** a better gyro
- **Our answer — map-in-the-loop:** state lives *on* the road graph; lateral error cannot grow without bound
- Map-matching as a property of the state space — not a cleanup pass

## Speaker (~30 s)

> “Naive dead reckoning blows up in seconds. Our measured negative result: give free DR a perfect yaw sensor and it still fails fifty-five percent of sixty-second segments. So a better gyro is not the answer. We put the OpenStreetMap road graph inside the filter loop — the state lives on the road — so lateral error cannot run away.”

## Honesty

- Volunteer the **55%** result; do not soften it.
- Do not claim first-ever phone INS or beating a named paper.
- **2.02×** is median *position error* only — never quote it as a drift-% ratio.

## Source

- `lab/stress/results/heading_ablation/summary.md`
- Money visual: `ppt_assets/diagrams/money_shot.png` (`python -m lab.eval.money_shot`)
