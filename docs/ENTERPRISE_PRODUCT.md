# SIH26168 Enterprise Product & Evidence Experience

## Product position

IDR is a phone-side, map-aided dead-reckoning fallback for GNSS outages. Its current enterprise value is an inspectable integration and evaluation surface—not an assertion that open-loop phone IMU navigation is production-ready.

“Palantir-level” means operational clarity, evidence lineage, access control, and explicit uncertainty. It does **not** mean covert surveillance. Hidden person tracking, off-shift monitoring, and repurposing location data without consent are prohibited product patterns.

## Buyer personas

- **Navigation / fleet engineering lead:** needs SDK boundaries, latency, device assumptions, map dependencies, and replayable failure cases.
- **Safety and operations lead:** needs degraded-state behavior, OOD/confidence alerts, incident workflows, and a clear statement that DR is a fallback rather than a safety-certified primary source.
- **Data science / validation lead:** needs blind challenge controls, held-out ground truth, calibration, stratified reliability, immutable configs, and downloadable machine-readable results.
- **Security / privacy reviewer:** needs purpose-bound collection, consent lifecycle, RBAC, retention controls, audit logs, and data-flow documentation.
- **Procurement / executive sponsor:** needs a concise view of supported claims, blockers, pilot acceptance criteria, and the difference between laboratory and field evidence.

## Evidence funnel

1. **Provenance:** identify source dataset, vehicle class, device, license, byte count, content digest, code commit, environment, and evaluation configuration.
2. **Commit:** lock dataset/config digests and prediction output location before the evaluator can access held-out truth.
3. **Run:** execute deterministic scenarios and write signed predictions. Preserve failures and stderr.
4. **Reveal:** join predictions to held-out GNSS ground truth only after prediction commitment.
5. **Stratify:** expose duration, speed, turn severity, device, and map/no-map slices. Never replace the distribution with one headline average.
6. **Calibrate:** show reliability CDF, covariance calibration, OOD behavior, and a failure matrix.
7. **Decide:** map evidence to explicit pilot gates and blockers. A failed gate stays red.

The web Evidence Room tries `/evidence/results.json`, `/proof/results.json`, then `/results/evidence.json`. If none exists, it uses embedded data clearly labelled **EMBEDDED DEMO DATA**. A real artifact must expose a `results` array and should include `generatedAt`, `commit`, and `sha256`.

## Evidence classes

- **REAL CAR:** measured phone and GNSS records from a real car. It can validate car baselines, device behavior, forced-outage evaluation, and lean≈car sanity. It cannot prove two-wheeler field performance.
- **INJECTED LEAN:** a controlled two-wheeler lean signal injected into real car-phone noise. It can support the directional algorithm claim that lean-aware kinematics improve same-direction turn error under that construction. It is not a real bike ride.
- **SYNTHETIC:** simulator-generated motion, sensors, graph, or scenario. It is useful for deterministic regression, edge cases, and UI demos. It is not field evidence.

These labels must always remain visible in tables, charts, exports, screenshots, and buyer reports. They must never share a visually ambiguous “validated” badge.

## Privacy and fleet operations principles

1. **Visible, revocable consent:** an operator knows when location collection is active and can stop it.
2. **Purpose limitation:** access must state an allowed purpose such as active navigation resilience, device diagnostics, or safety incident response.
3. **Least privilege:** role-, fleet-, shift-, and incident-scoped access; no universal location viewer.
4. **Time limitation:** shift consent expires. Raw traces have a short retention period; aggregate reliability evidence may be retained separately.
5. **Auditability:** consent changes, access, exports, policy decisions, and incident views are append-only and attributable.
6. **Data minimization:** on-device estimation by default; upload only the samples needed for opted-in diagnostics or evaluation.
7. **No covert tracking:** no hidden person tracking, off-shift collection, shadow identifiers, or customer-data reuse.

The Operations thin slice contains only a clearly marked seeded demo fleet. It intentionally uses `DEMO-RIDER-*` identifiers and non-geographic visuals; there are no fake customer names or claims of live deployment.

## Sellable now

- Evaluation pilot with the TypeScript core, replay console, dataset adapter harness (synthetic plumbing fixture), golden vectors, and joint acceptance protocol.
- Lean-aware kinematics as a laboratory method, with the injected-lean claim explicitly labelled.
- Real-car sanity and forced GNSS-outage evaluation on the available IO-VNBD logs.
- Integration work for map-aided known-route or corridor fallback, provided limitations are contractually explicit.
- Evidence and operations UX patterns for an opted-in pilot.

## Blocked before an enterprise production close

- Real bicycle, motorcycle, or scooter field evidence across devices, mounts, speeds, weather, and outage types.
- Open-loop 40–60 second compliance with the stated ISRO bars; current phone-gyro results broadly fail.
- Production graph map-aiding outside the Python stress implementation.
- Speed estimation through braking and acceleration rather than last-good-GNSS speed hold.
- Axis, mount, and timebase sensor contract with demonstrated gyro↔course correlation.
- Learned odometry / InEKF closure and calibrated covariance/OOD thresholds.
- Device SKU and thermal diversity, map-data licensing, security review, retention controls, and operational SLOs.
- Safety and liability qualification. No SIL/ASIL or lane-level claim exists.

## Pilot acceptance proposal

A credible pilot should pre-register routes, devices, map availability, outage windows, and pass thresholds; reserve held-out rides; require content-addressed artifacts; score loop closure and branch decisions; report every evidence class separately; and define a degraded-state operational response. Production procurement should remain blocked until real two-wheeler field gates pass.
