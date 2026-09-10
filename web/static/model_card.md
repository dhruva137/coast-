# COAST-VNet-1

**Velocity network for GNSS-denied vehicle navigation.** Estimates vehicle
forward speed from a smartphone's raw inertial sensors, on-device, so dead
reckoning can continue when the satellite signal is gone.

Released as part of COAST, Smart India Hackathon 2026, problem statement 26168
(ISRO / Dept. of Space).

| | |
|---|---|
| **Model** | COAST-VNet-1 |
| **Architecture** | Frequency-decoupled CNN-GRU |
| **Parameters** | **96,086** (all trainable) |
| **Size** | 375 KB fp32 · **392 KB ONNX** as shipped |
| **Input** | `(20, 6)` — 2.0 s window at 10 Hz: `ax, ay, az, gx, gy, gz` (SI units, phone frame) |
| **Output** | forward speed (m/s), plus a log-variance head |
| **Runtime** | ONNX Runtime Mobile, CPU, on-device |
| **Training data** | IO-VNBD, 23 clean drives, labelled from vehicle CAN bus |
| **Licence / weights** | `android/app/src/main/assets/avnet_tiny.onnx` |

---

## Why this architecture

A phone on a dashboard sees two superimposed signals: the **vehicle's motion**,
which is low-frequency, and **road and engine vibration**, which is high-frequency
and is exactly what the problem statement names as the thing to filter
("engine idling vibrations, pothole shocks, bumps").

Rather than filter the noise away and hope the signal survives, COAST-VNet-1
**splits the band and treats the two as different information**:

```
IMU (20×6) ──▶ FrequencySplit
                 │
    low  band ───┼──▶ Conv1d(6→32) ──▶ GRU(32→80, 2 layers)   ── vehicle motion
                 │
    high band ───┴──▶ Conv1d(6→48) ──▶ GroupNorm ──▶ Conv×2    ── surface / vibration
                                            │
                              concat ───▶ Linear(135→96) ──▶ Linear(96→6)
```

The high-frequency branch is not discarded noise — road texture and engine
harmonics carry information about speed. The low-frequency branch, with the GRU,
carries the motion state across the window.

## Measured performance

**Protocol: leave-file-out over 23 drives** — train on 22, score the held-out
drive only, never trained on. 12 epochs per fold. Labels are CAN-bus indicated
vehicle speed at 10 Hz, not phone GNSS.
Source: `lab/models/results/speed_bakeoff/summary.md`

### Per-window accuracy

| | median RMSE | verdict |
|---|---:|---|
| Predict the mean (floor) | 7.970 m/s | the trivial baseline |
| **COAST-VNet-1** | **5.061 m/s** | comfortably beats the floor |
| Hold last known speed | **1.280 m/s** | **beats the model on 23/23 folds** |

**We report this against ourselves: on per-window RMSE the model loses to simply
holding the last known speed.** That is the honest result and it is in the
committed summary.

### Closed-loop — the metric that matters

Per-window RMSE is not what a navigation system cares about. What matters is
where you end up after an outage. Integrated over mid-route 60-second windows:

| | median distance error | median drift | folds won |
|---|---:|---:|---:|
| **COAST-VNet-1** | **150.3 m** | **18.0%** | **9 / 23** |
| Frozen onset speed | 163.2 m | 21.1% | — |

The model is **~8% better than freezing the speed**, and wins on 9 of 23 drives.
A real but modest improvement — and the errors decorrelate in a way a frozen
estimate's do not, which is why it wins closed-loop while losing per-window.

### Where the actual accuracy comes from

**Be clear about this, because it is the honest architecture story:** the speed
model is *one input*. The system-level result comes from constraining the
estimate to the road graph.

| Component | Measured effect |
|---|---|
| **Map-in-loop particle filter** | **2.02× lower median position error** (252.66 m → 125.20 m), 43 real GNSS outages |
| Onset-calibrated compass heading | heading-induced drift **16.87% → 7.22%**, 655 windows |
| COAST-VNet-1 speed | ~8% closed-loop over frozen speed |
| Post-hoc road snapping (control) | **0.98× — worse than nothing** |

## Intended use

- Consumer navigation continuity through tunnels, underpasses, car parks and
  urban canyons, on a phone with no external sensors.
- Fleet and logistics tracking where GNSS gaps break continuity.
- The edge deployment the problem statement also requires: the same core runs
  headless against external IMU data, measured at **19,682 Hz** in its worst
  configuration — 98× the 200 Hz requirement.

## Limitations — read these before quoting the model

1. **It loses to a naive baseline on per-window RMSE.** Stated above; not hidden.
2. **Trained on cars.** IO-VNBD is car data. Two-wheelers — our stated
   differentiator — are **not** represented in training. Cross-vehicle
   generalisation is untested.
3. **Mount dependence.** Gravity-axis canonicalisation reduced mount-swap
   degradation by ~63% in ablation, but full orientation invariance is not
   implemented.
4. **The uncertainty head is not trustworthy.** Its spread correlates **−0.23**
   with actual error, so it is **gated off in the UI**. We do not show a user a
   confidence number we cannot stand behind. Diagnosis in
   `lab/models/results/nll_diagnosis/`.
5. **No real field drives.** Everything is validated on recorded public data and
   on-device replay. The app has never logged an original road drive.
6. **The ISRO 10% drift bar is not met end-to-end.** Median drift with the full
   system is 16.77% against a <10% target. We have roughly halved the gap from
   the 27.58% free-DR baseline.
7. **Residual-on-persistence (7th channel) does not survive rollout.** Leave-file-
   out over 23 drives with scheduled sampling (`lab/models/results/residual_speed/`):
   teacher-forced residual beats hold on **13/23** folds (median RMSE 1.248 vs
   1.280 m/s), but under closed-loop rollout — the deployment contract — it wins
   **0/23** and median 60 s distance error is **213.5 m** vs hold **7.7 m**.
   Not adopted; 6-ch ONNX stays. At 10 Hz Nyquist is 5 Hz while road/engine
   vibration is 20–100 Hz — resampling may beat further architecture changes.

## Reproducing

```bash
python -m lab.models.run_speed_bakeoff     # full leave-file-out, 23 folds
python -m lab.demo                          # quick train + regenerate figures
python tools/verify_claims.py               # re-derive every published number
```

Every number in this card is re-derived from a committed results file by
`tools/verify_claims.py`, which fails the build if a published figure has no
measured source.

## Provenance

Training labels come from the vehicle CAN bus, not from phone GNSS, so the model
is not learning to imitate a noisy GPS. The offline road graph used by the
filter was built from OpenStreetMap only — its build report records
`built_from_drive_data: false`: *"No IO-VNBD trajectory, GNSS fix or CSV column
was read while building this graph."* That is a deliberate guard against the
test set leaking into the map.
