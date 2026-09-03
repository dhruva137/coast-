# SIH26168 Remote Proof Protocol — corrected-axis segmented v2

This protocol demonstrates dead-reckoning behavior without asking a witness to
move. Its strongest evidence is a **witness-seeded, commit → predict → reveal
challenge on a previously unseen real IO-VNBD car log**, followed by a
deterministic 120-placement reliability envelope across segmented sessions. It
is an evaluation protocol, not a claim that the current estimator meets a
deployment requirement.

All proof estimators consume `load_iovnbd.py` and fail closed unless vehicle yaw
is `gz = -GYROSCOPE Pitch`, the mapping established by the dual-source alignment
audit. Raw IO-VNBD gyro labels are retained only for provenance. The horizontal
completion (`gx = raw Roll`, `gy = raw Yaw`) is not claimed to be independently
observable from course rate.

## Evidence classes

Every artifact carries one of these labels:

- `real-car/IO-VNBD`: measured car GNSS and phone IMU. Outage GNSS is held out.
- `fixture/synthetic-route+real-car-noise/upright`: generated route and upright
  body rates with additive noise sampled from a real car log.
- `fixture/synthetic-route+real-car-noise/injected-lean`: the identical generated
  route, clock, speed, noise, and estimator with lean as the only changed variable.

The counterfactual is not represented as a real motorcycle recording. A
two-wheeler field claim still requires two-wheeler data.

## Witnessed blind challenge (strongest proof)

1. The customer supplies an unpredictable integer seed after receiving the code
   and raw-data hashes. A public randomness beacon or the last digits of a market
   close can be used.
2. In a clean checkout, run:

   ```powershell
   python lab/proof/blind_challenge.py --seed <CUSTOMER_SEED>
   ```

3. The program enumerates real `S-*.csv` files larger than 1 MB, segments each
   file, selects a duration from 20/40/60/90 seconds and an eligible
   2-second-grid placement using NumPy's deterministic generator, then writes
   `blind_commitment.json`.
4. The commitment binds the raw-file SHA-256, seed, exact sample interval,
   estimator identity, and predeclared covariance rule. The file is flushed
   before estimation starts. The witness copies or independently timestamps its
   SHA-256.
5. `blind_prediction.json` is written before the hidden GNSS is opened for
   scoring. It contains the 10 Hz state timeline, heading, inferred lean, and
   covariance. `map_posterior` is explicitly `null`: this implementation does not
   use a map.
6. Only then is held-out GNSS converted to ENU and written to
   `blind_reveal.json`, together with errors and the prediction-file SHA-256.

The estimator boundary accepts pre-outage GNSS and outage clock/IMU only.
Outage latitude, longitude, bearing, and GPS speed are not passed to estimation.
Speed is frozen to the median of the last two seconds before denial. Gyro bias is
estimated only from pre-outage GPS bearing and gyro.

## Session segmentation

IO-VNBD files may concatenate recordings and reset their clocks. Before any
placement is enumerated, the shared loader splits on:

- non-finite or non-positive `dt`;
- sample gaps above 5 seconds;
- coordinate discontinuities above 1,000 m, or implied speeds above 80 m/s
  between actual changed GNSS fixes.

Coordinate checks use elapsed time between changed fixes because IO-VNBD often
holds a coordinate for roughly nine seconds; a 250 m update after that interval
is not treated as a 0.1-second teleport. Segments shorter than 55 seconds or
covering less than 100 m by GPS speed integration are excluded. Placement still
requires 30 seconds of calibration history, a complete duration window, finite
held-out GNSS endpoints and IMU, and pre-outage speed of at least 1 m/s. Sample
ranges in every artifact refer back to the original source file.

For a higher-assurance ceremony, pause the process after each artifact write
(or run it under a witness wrapper), copy each hash to customer-controlled
storage, and publish the commitment hash to a third-party timestamp service.
Local timestamps alone are not trusted timestamps.

## Time-machine replay

`blind_prediction.json.timeline` is a renderer-independent 10 Hz replay source.
A reviewer can scrub `t_s` and inspect both estimator states, covariance
diagonal, heading and inferred lean while ground truth remains absent. The
ground-truth array exists only in `blind_reveal.json`; overlay it only after the
outage endpoint. This separation prevents UI code from accidentally displaying
or consuming held-out fixes early.

## Reliability envelope

Run at least 100 placements:

```powershell
python lab/proof/reliability_battery.py --trials 120 --seed 26168
```

The battery loads up to six eligible, deterministically selected real logs,
segments them, and samples placements without replacement over a 2-second grid.
It allocates trials equally across 20, 40, 60 and 90 seconds and round-robins
across eligible sessions so one concatenated recording cannot dominate merely
because it has more candidate starts. `reliability.json` retains every trial,
including failures. `reliability.png` shows:

- endpoint-error CDF;
- survival curve (tail risk);
- endpoint 95% covariance coverage versus nominal 95%;
- error versus turn severity, colored by duration.

The covariance rule (`sigma = 3 + elapsed seconds`, isotropic position) is
declared before reveals and is deliberately not fitted to this battery. Coverage
below 95% means overconfidence; coverage far above 95% means an uninformative or
over-conservative envelope. Report the gap, not just a pass/fail badge. The
reported post-hoc sigma multiplier needed for 95% empirical coverage is a
diagnostic only and must not be presented as held-out calibration without a new
frozen evaluation.

The JSON failure map bins endpoint error and >50 m incidence by speed, measured
gyro turn severity, and outage duration. The 90-second cases are the current
long-horizon evidence. Chained outages and true loop-closure evaluation are not
implemented by this proof and must not be claimed from these artifacts.

## Counterfactual twin

```powershell
python lab/proof/counterfactual_twin.py
```

This paired fixture uses one generated coordinated-turn route and one exact
segmented span of high-frequency gyroscope noise from a hashed real car log. The
upright twin uses zero lean. The injected twin projects the same true vehicle
yaw rate as `gy = yaw_rate*sin(phi)` and `gz = yaw_rate*cos(phi)`, then adds the
same fixed donor noise. A mandatory noiseless round-trip checks the estimator's
`yaw_rate = gy*sin(phi) + gz*cos(phi)` and coordinated-turn lean equations before
scoring. This tests whether the lean-aware kinematics responds to injected lean
while holding all other variables fixed; it does not establish real-world
motorcycle accuracy.

## Corrected v2 result snapshot

Seed 26168 produced 120 placements, exactly 30 per outage duration, from four
source files and eight viable sessions. For the primary `idr_lean_bias` estimator:

- 20 s: median 129.5 m, p95 287.4 m, 95% covariance coverage 20.0%, >50 m 80.0%;
- 40 s: median 262.9 m, p95 580.4 m, coverage 20.0%, >50 m 90.0%;
- 60 s: median 264.1 m, p95 761.8 m, coverage 26.7%, >50 m 96.7%;
- 90 s: median 297.6 m, p95 969.3 m, coverage 33.3%, >50 m 96.7%.

Overall median is 223.1 m, p95 is 695.0 m, nominal-95% endpoint coverage is
25.0%, and 90.8% exceed 50 m. This is materially under-calibrated and does not
support a deployment-readiness claim. The corrected injected-lean twin passes
its noiseless frame check and, in the noisy injected fixture, improves endpoint
error from 5.41 m (car-style) to 1.17 m (lean-aware). This remains explicitly
injected evidence.

## Bundle and one-command verification

After all runs:

```powershell
python lab/proof/evidence_manifest.py create
python lab/proof/evidence_manifest.py verify lab/proof/results/manifest.json
```

The manifest binds proof code, protocol, JSON/PNG outputs, and every raw log used
by SHA-256 and byte length. It records the Git commit when available and whether
the proof tree was dirty. Verification returns a non-zero exit code for a
missing, resized, or modified file.

## Threat model

| Threat | Control | Residual limitation |
|---|---|---|
| Cherry-picked log/window | Customer chooses unpredictable seed; all eligible placements are deterministic | Operator could withhold a bad run; witness should retain seed and terminal transcript |
| Raw-data substitution | Full raw-log SHA-256 in commitment and manifest | Witness must obtain the expected dataset hash independently |
| Ground-truth leakage | Estimator API excludes outage GNSS fields; prediction hash precedes reveal | Python runs in one trust domain; independent code review/sandbox raises assurance |
| Prediction edited after reveal | Reveal binds SHA-256 of prediction copied by witness | Local timestamps are not externally trusted |
| Favorable threshold invented after results | No battery pass threshold; raw rows, quantiles, tails and calibration all published | Product acceptance limits remain a customer decision |
| Synthetic evidence presented as field evidence | Explicit `fixture` and `injected-lean` labels | Real two-wheeler validation remains outstanding |
| Map leakage through hidden route | Blind estimator has no map and reports null posterior | This protocol does not evaluate a production map-aided mode |
| Repeated-seed tuning | Customer supplies fresh seed after code/config freeze | Public development runs may still influence later model versions |

## Acceptance ceremony

A large organization should: pin the Git commit; independently hash the raw
logs; provide the seed; observe commitment and prediction hashes entering
customer-controlled storage; allow reveal; rerun the 120-trial battery; verify
the manifest; and sign the manifest hash. Archive stdout, Python/NumPy versions,
the repository commit, and the exact manifest. Any changed estimator or
configuration requires a new ceremony and must not reuse the old evidence.
