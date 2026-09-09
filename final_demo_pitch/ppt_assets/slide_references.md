# Slide — Research & References *(deck appendix / Q&A)*

**Status:** paste-ready text for the official SIH template References /
Research slide (or appendix). Sources live in
`cursor_induction_v2/RESEARCH_2025.md` — do not invent citations.

## On-slide

**Closest prior + 2025 enhancements we align with**

- **Shared-bike inertial tracking in GNSS-blocked environments**
  (arXiv [2605.07412](https://arxiv.org/pdf/2605.07412)) —
  two-wheeler inertial positioning with GNSS blocked — our exact thesis;
  cite as closest prior.
- **EqNIO: Subequivariant Neural Inertial Odometry**
  (ICLR 2025, arXiv [2408.06321](https://arxiv.org/abs/2408.06321)) —
  gravity-axis roto-reflection symmetry → mount-invariant IO;
  we measure an EqNIO-style gravity-axis canonicalize on AVNet
  (`lab/models/results/mount_invariant/summary.md`).
- **Neural-Augmented Kalman Filters for Road-Network-assisted GNSS**
  (arXiv [2507.00654](https://arxiv.org/pdf/2507.00654)) —
  neural KF + road network — same shape as our map-in-loop + fusion;
  backlog for a learned filter gain (not claimed as shipped).

**Family / baseline citations**

- IO-VNBD (our measured corpus) · Newson & Krumm 2009 (HMM map matching)
- TLIO / RoNIN / TinyOdom / AI-IMU-DR — neural / vehicle DR cousins

**Our measured sources (open on request)**

- 2.02× map-in-loop → `lab/stress/results/mapfilter/summary.md`
- Perfect-gyro still fails 55% → `lab/stress/results/heading_ablation/summary.md`
- Free-DR 17% / 10% → `lab/stress/results/isro_benchmark/summary.md`

## Speaker (~15 s)

> “Closest published prior is shared-bike inertial tracking under GNSS blockage.
> EqNIO is the 2025 mount-invariance idea we ablated on our speed model — measured,
> wash or win reported in the summary file. Neural-augmented road-network KF is
> the backlog shape of our filter. Every headline number has a file we can open.”

## Honesty

- Do not claim EqNIO / KalmanNet as *shipped product features* — cite + measured
  ablation / backlog only.
- Do not put arXiv IDs on the innovation slide as if they are our papers.
