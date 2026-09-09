# Research 2025 — SOTA we align with, and the enhancement backlog

Two jobs: (1) record the links so the deck's References slide and Q&A are backed;
(2) list concrete, measurable improvements — each must be **measured** if built,
never claimed.

## A. Directly on-point (cite + borrow ideas)

| Work | Why it matters to COAST | Use |
|---|---|---|
| **Shared-bike inertial tracking in GNSS-blocked environments** (arXiv 2605.07412) | Literally two-wheeler inertial positioning with GNSS blocked — our exact thesis | **Cite as closest prior**; borrow eval framing |
| **EqNIO: Subequivariant Neural Inertial Odometry** (ICLR 2025, arXiv 2408.06321) | Exploits gravity-axis roto-reflection symmetry → generalizes across phone mount/orientation | **Enhancement idea**: make the AVNet speed model mount-invariant |
| **Neural-Augmented Kalman Filters for Road-Network-assisted GNSS** (arXiv 2507.00654) | Neural KF + road network — same shape as our map-in-loop + fusion | **Enhancement idea**: learned gain for our filter |
| **Tracing-KalmanNet** (UbiComp 2025) | Deep KF for nonlinear + **intermittent** inertial data (= GNSS outages) | **Enhancement idea**: outage-robust filter |
| **AirIO** (RA-L 2025) | Enhanced IMU feature observability | Cite; feature-eng idea for AVNet |

## B. SOTA landscape (cite for "we're in the current family")

- **TinyOdom** (NESL) — on-device tiny neural IO (our on-device cousin).
- **TLIO** (CathIAS) / **RoNIN** — the reference line.
- **FTIN: Frequency-Time Integration Network** (arXiv 2507.16120) — cousin of our FrequencyDecoupledNet AVNet.
- **X-IONet** (2511.08277), **MosaicIMU** (2606.09355), **GNIO** (2603.15281) — generalizable neural IO.
- **AI-IMU-DR** (Brossard) — invariant-EKF vehicle DR on KITTI (our car cousin).
- **Newson & Krumm 2009** — HMM map matching (we cite + implement).

## C. Baseline / our-number sources (record these — asked for)

Our measured rows a judge can open:
- Free-DR **17%** short-arm / **10%** tunnel-arm; **28%** median free drift vs **17%** COAST →
  `lab/stress/results/isro_benchmark/summary.md`, `lab/stress/results/mapfilter/summary.md`.
- **2.02×** map-in-loop → `lab/stress/results/mapfilter/summary.md`.
- **Perfect gyro still fails 55%** → `lab/stress/results/heading_ablation/summary.md`.
- IO-VNBD dataset (the corpus these are measured on).

## D. Enhancement backlog (measure, don't claim)

Priority order, each writes a `summary.md` with the honest result:
1. **Mount-invariant speed model (EqNIO-style)** — add gravity-axis canonicalization to AVNet input; measure per-window + closed-loop vs current. Expect: better generalization across phone orientations.
2. **Neural-augmented filter gain (KalmanNet / road-network)** — learn the filter's trust between AI-speed, gyro, and map; measure vs the hand-tuned particle filter.
3. **Differentiable particle filter** — end-to-end train the map-in-loop filter; measure vs current 2.02×.
4. **Outage-robust deep KF (Tracing-KalmanNet)** — handle intermittent GNSS; measure handover.

## Sources
- [Shared-bike inertial, GNSS-blocked (arXiv 2605.07412)](https://arxiv.org/pdf/2605.07412)
- [EqNIO (arXiv 2408.06321)](https://arxiv.org/abs/2408.06321)
- [Neural-Augmented KF, road-network GNSS (arXiv 2507.00654)](https://arxiv.org/pdf/2507.00654)
- [Tracing-KalmanNet (ACM UbiComp 2025)](https://dl.acm.org/doi/10.1145/3714394.3756276)
- [AirIO (arXiv 2501.15659)](https://arxiv.org/pdf/2501.15659)
- [FTIN (arXiv 2507.16120)](https://arxiv.org/pdf/2507.16120)
- [X-IONet (arXiv 2511.08277)](https://arxiv.org/pdf/2511.08277)
- [Deep Learning for Inertial Positioning: A Survey (arXiv 2303.03757)](https://arxiv.org/pdf/2303.03757)
