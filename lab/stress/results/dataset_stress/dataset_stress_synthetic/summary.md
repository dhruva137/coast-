# Dataset stress — `dataset_stress_synthetic`

- Adapter: `synthetic`
- Dataset dir: `lab\eval\fixtures\dataset_stress_synthetic`
- Sessions scored: **1**
- Seed: `26168`
- OSM graph: `C:\Users\Dhruva P Gowda\Desktop\New folder\SIH 2026\maps\graphs\iovnbd_midlands.graph.npz`

> **SYNTHETIC / FIXTURE** — not field proof. Manager drops real data under `data/field/`. Avoid Kaggle notebooks; score locally.

## Honesty — free-DR only

Map-in-loop did **not** run on this dataset (no usable independent OSM coverage / graph). Metrics below are **free-DR only**. We are not inventing a map-aided improvement.

Skip reasons:

- track median lat/lon outside OSM graph bbox (iovnbd_midlands.graph.npz)

## Per-session free-DR

| session | n | dist_m | final_m | ate_m | drift% | CDF p50 | CDF p95 | ISRO <10% |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| dataset_stress_synthetic | 401 | 199.9 | 41.83 | 20.85 | 20.92 | 13.61 | 39.11 | FAIL |

## Aggregate (free-DR)

- median final error: **41.83 m**
- median drift: **20.92 %**
- pass rate (ISRO drift < 10%): **0/1** (0%)

## Figures

- `error_cdf.png` — empirical CDF of free-DR position error

## Logistics

Drop real public datasets under `data/field/<name>/` and re-run with `--adapter iovnbd` (or a new adapter). See `lab/eval/adapters/README.md` and `final_demo_pitch/FIELD_DATASETS.md`. Do not fork scoring into a Kaggle notebook.
