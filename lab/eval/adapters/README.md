# Dataset column adapters

Map any public smartphone-IMU (+ optional GPS) CSV into the COAST session
schema used by `lab/stress/run_dataset_stress.py`.

## Manager logistics (local pipeline)

1. Download one dataset yourself (Kaggle / IEEE DataPort / OxIOD — see
   `final_demo_pitch/FIELD_DATASETS.md`).
2. Drop the raw files under `data/field/<name>/` in this repo.
3. Run::

       python lab/stress/run_dataset_stress.py data/field/<name> --adapter iovnbd

Do **not** fork the pipeline into a Kaggle notebook. The stress harness,
metrics, and figures live here; notebooks would diverge and invent numbers.

Recommended first picks (two-wheeler / GPS truth):

- Kaggle *Reckless Motorcycle Riders — Smartphone Sensors*
- IEEE DataPort *Smartphone IMU and GPS Dataset*

## Adapters

| name | purpose |
|---|---|
| `synthetic` | Committed tiny fixture under `lab/eval/fixtures/dataset_stress_synthetic/` — harness runs green without a download |
| `iovnbd` | IO-VNBD smartphone CSV headers (GPS latitude / Accelerometer X / …) |

Add a new adapter by subclassing `ColumnAdapter` in `base.py`, registering it in
`__init__.py`, and mapping that dataset's columns → `SessionArrays`.
