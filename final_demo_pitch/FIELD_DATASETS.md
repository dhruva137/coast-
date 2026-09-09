# Field datasets for B5 (loop-closure) / B7 (baro) — no real recording needed

We don't have to record a scooter ride ourselves — several public smartphone-IMU
datasets can feed `lab/eval/score_field_log.py`. Pick one, download it (needs a
free Kaggle/IEEE account), and Claude wires a ~30-line column adapter (same as
the IO-VNBD demo strip) to score drift / loop-closure.

## Recommended, in order

| Dataset | Why | Fits | Download |
|---|---|---|---|
| **Reckless Motorcycle Riders — Smartphone Sensors** (Kaggle) | Real **two-wheeler** phone accel/gyro — our exact differentiator | B5, two-wheeler demo | kaggle.com/datasets/vegatamafirdiady23/reckless-motorcycle-riders-smartphone-sensors |
| **Smartphone IMU and GPS Dataset** (IEEE DataPort) | Multi-mode incl. **two-wheeler + walking + cycling**, accel/gyro/mag + **GPS** (GPS = loop-closure truth) | B5 with GPS truth | ieee-dataport.org/documents/smartphone-imu-and-gps-dataset |
| **OxIOD** (Oxford) | Pedestrian handheld/pocket, 100 Hz, **Vicon mm ground truth** — cleanest loop-closure numbers | B5 walking demo | deepio.cs.ox.ac.uk |
| **E-Scooter surface recognition** (arXiv 2302.12720) | iPhone 13 on a scooter handle, 100 Hz, 100 min real two-wheeler IMU | two-wheeler vibration profile | linked in the paper |

## How each maps to our claims (honesty)

- **B5 loop-closure:** with GPS (IEEE set) or Vicon (OxIOD) as truth, we can report
  a REAL measured drift/closure number on a phone log we did not collect — honest,
  and defensible as "public data, not our own cherry-pick".
- **Two-wheeler differentiator:** the Kaggle motorcycle set is genuine two-wheeler
  phone data — lets us show the lean/vibration case on real data instead of the
  injected-lean counterfactual (which stays labelled as a counterfactual).
- **B7 barometer:** most IMU sets have **no barometer**, so floor-change validation
  needs an indoor multi-floor set (IPIN competition / UMinho baro logs). Lower
  priority — the detector is already unit-tested; mark baro field data "pending"
  unless a baro set is grabbed.

## Integration steps (once you download one)

1. Drop the raw file(s) under `data/field/<name>/`.
2. Claude writes `lab/eval/adapters/<name>.py` mapping its columns → our session
   schema (lat/lon/accel/gyro/time), exactly like the IO-VNBD demo-strip mapping.
3. Run `python lab/eval/score_field_log.py data/field/<name>/...` → measured drift
   + loop-closure, written to `lab/eval/results/field/<name>.md`.
4. If good, add one honest line to the PPT feasibility slide ("validated on public
   two-wheeler phone logs: X% drift over Y m").

## Sources

- [Reckless Motorcycle Riders (Kaggle)](https://www.kaggle.com/datasets/vegatamafirdiady23/reckless-motorcycle-riders-smartphone-sensors)
- [Smartphone IMU and GPS Dataset (IEEE DataPort)](https://ieee-dataport.org/documents/smartphone-imu-and-gps-dataset)
- [OxIOD (Oxford)](http://deepio.cs.ox.ac.uk/)
- [E-Scooter surface recognition (arXiv 2302.12720)](https://arxiv.org/pdf/2302.12720)
