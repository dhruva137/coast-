# `idr_edge` — edge-deployable software engine

SIH26168 asks for **two** deliverables:

> "The Final solution and AI/ML models developed should not be constricted to smart
> phone IMU sensors data alone (Mobile application). These algorithms/models should
> also work with any other external IMU sensors data (**Edge deployable software
> engine**)."

> "Position update rate of 10Hz with processing on smartphones (Mobile application)
> and **higher update rates on Edge deployable software engine using FOG based IMU
> sensors data (around 200Hz)**."

`idr_edge` is deliverable (b): a standalone C++17 CLI over the *same* `nav_core`
static library the Android app links. No new dependencies, no package manager, no
runtime — one `.exe` / ELF binary plus a JSON column-mapping file.

---

## Build

```sh
cd core/cpp
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build            # golden + edge_selftest
```

Produces `build/idr_edge` (`.exe` on Windows) alongside the existing
`build/nav_golden` test binary. On Windows the target links `psapi` for the
peak-memory readout; nothing else is linked beyond the C++ standard library.

## Usage

```
idr_edge --input <imu.csv> --map <cols.json> [--rate <hz>] [--out <traj.csv>] [--bench]
idr_edge --synth <seconds> [options]
```

| Flag | Meaning |
|---|---|
| `--input <path>` | IMU CSV of **any** layout — see the mapping format below |
| `--map <path>` | JSON column mapping (`apps/mappings/*.json`) |
| `--synth <seconds>` | Generate a coordinated-turn IMU stream instead of reading a file |
| `--limit <n>` | Use only the first `n` rows |
| `--no-gnss` | Ignore `lat`/`lon`/`speed` columns — pure dead reckoning |
| `--session-longest` | Keep only the longest monotonic-time run (see *Time resets*) |
| `--rate <hz>` | Declared IMU rate. Default: median of the timestamp deltas |
| `--resample <hz>` | Linearly resample the input to `<hz>` before running |
| `--mode stream\|batch` | `stream` (default) = per-sample; `batch` = `nav::runEngine` |
| `--vehicle <name>` | `car` \| `scooter` \| `motorcycle` \| `bicycle` (overrides the mapping's `meta`) |
| `--graph campus\|none` | Enable the built-in demo road graph + particle filter |
| `--particles <n>` | Graph particle count (default 180) |
| `--origin lat,lon,alt` | Fallback origin when the input carries no GNSS |
| `--out <path>` | Write the trajectory CSV |
| `--emit-input <path>` | Write the ingested IMU stream back out as a CSV readable by `external_imu_200hz.json` |
| `--bench` | Report throughput, latency percentiles and peak memory |
| `--repeat <k>` | Bench: replay the stream `k` times |
| `--quiet` | Suppress the ingestion summary |

Exit code is `0` on success, `1` if the trajectory contains a non-finite
position, `2` on a usage error.

### Output trajectory CSV

```
t_ns,lat,lon,alt,ve,vn,vu,roll_deg,pitch_deg,yaw_deg,lean_deg,speed,mode,edge_id,gnss_aided
```

`mode` is `gnss` while a fix is within 1.5 s, otherwise `ins`. Angles are degrees,
velocities are ENU m/s, `speed` is m/s.

---

## Column-mapping format

The whole point of the mapping file is that **no external IMU header is hardcoded**.
Point the engine at any CSV and describe its columns:

```json
{
  "name": "my-imu",
  "has_header": true,
  "delimiter": ",",
  "time": { "match": "timestamp", "unit": "us" },
  "fields": {
    "ax": { "match": "accel x" },
    "ay": { "match": "accel y" },
    "az": { "match": "accel z" },
    "gx": { "match": "rate x" },
    "gy": { "match": "rate y" },
    "gz": { "match": "rate z", "scale": -1.0 },
    "speed": { "index": 14, "scale": 0.2777777777777778 }
  },
  "meta": { "vehicle": "motorcycle", "leans": true, "imu_hz": 200 }
}
```

* **`time`** is required. `unit` is one of `s`, `ms`, `us`, `ns`, or `auto`
  (`auto` picks the scale that puts the median step between 0.1 ms and 1 s).
* **`fields`** must contain `ax ay az gx gy gz`. Optional: `mx my mz`,
  `pressure_hpa`, `lux`, `lat`, `lon`, `alt`, `speed`, `bearing`, `acc_h`,
  `acc_v`, `n_sats`. Any other key is a hard error, so typos are caught.
* A field spec is either a **string** (header match), a **number** (0-based
  column index), or an **object** with `match`/`column`, `index`, `scale`,
  `offset`. Applied as `value * scale + offset`, so unit conversion (km/h → m/s,
  deg/s → rad/s, g → m/s²) and axis sign flips live in the mapping, not in code.
* `index` wins over `match` and is required when `has_header` is `false`.
* Header matching is unit-glyph tolerant: the cell is lowercased, non-ASCII bytes
  (`°`, `²`, `µ`) become spaces, punctuation collapses to single spaces. So
  `" ACCELEROMETER X (m/s²) "` normalises to `accelerometer x m s` and matches
  `"accelerometer x"`. Exact matches are tried across all columns first, then
  substring matches — that is why `"ax"` binds to `ax` and not to `max`.
* `meta` supplies `phone_model`, `vehicle`, `mount_type`, `leans`, `imu_hz`
  defaults. `vehicle: "car"` selects the car-style (`ψ̇ = ω_z`) integration;
  anything else selects the lean-aware solver.

Every run prints exactly which header cell each field bound to, so a
mis-mapped log is visible before you read a single number:

```
bound columns:
  ax            <- " ACCELEROMETER X (m/s?) "
  gz            <- " GYROSCOPE Pitch (rad/s)"
  speed         <- " GPS SPEED (Kmh)"
  time          <- " TIME SINCE START (ms)"
```

### Shipped mappings

| File | For |
|---|---|
| `mappings/iovnbd_smartphone.json` | IO-VNBD `S-*.csv` smartphone logs, ~10 Hz. Speed is km/h, time is ms, and the gyro triad is remapped to the vehicle frame as `[gx, gy, gz] = [raw Roll, raw Yaw, −raw Pitch]` — the mapping validated against GPS orientation in `lab/stress/load_iovnbd.py`. |
| `mappings/external_imu_200hz.json` | Generic external / FOG-class IMU already in SI vehicle-frame units with nanosecond timestamps. Column names match `lab/datasets/log_schema.py` `IMU_COLUMNS`, so the project's own Android logs and any edge-box logger share this mapping. |

### Time resets

Real logs concatenate drives. IO-VNBD `S-*.csv` restarts `TIME SINCE START`
mid-file, which makes `dt < 0` and destroys the estimator. `idr_edge` **always**
counts backward timestamp steps and warns:

```
time resets  : 1 backward timestamp step(s) in this file  *** WARNING: dt < 0
               corrupts the estimator. Re-run with --session-longest ***
```

`--session-longest` keeps only the longest strictly-increasing run and reports how
many rows it dropped. It is opt-in — the tool will not silently reshape your data.

---

## Measured benchmarks

**Machine:** AMD Ryzen 7 260 (16 logical cores), Windows 11, single-threaded.
**Compiler:** g++ 15.2.0 (MSYS2 MinGW-w64), CMake `Release`.
**Method:** `--bench` wraps `std::chrono::steady_clock` around *each* `step()` call;
the clock-call overhead is charged to the engine, so these numbers are pessimistic.
Throughput = samples ÷ summed engine time; file parsing is excluded and reported
separately as `load time`.

All numbers below are the actual observed spread across repeated runs on a
**loaded developer laptop** (other agents and a dataset download were running
concurrently). `p50` is stable; `mean`, `p99` and `max` are contaminated by OS
scheduling stalls of 5–39 ms, which is why the table quotes `p50`/`p99` rather
than a single mean.

### A — Synthetic 200 Hz, INS + lean solver, no road graph (10 runs)

```
idr_edge --synth 60 --rate 200 --bench
```

| | min | max |
|---|---|---|
| Sustained throughput | **58,369 Hz** | **99,762 Hz** |
| p50 latency | 9.30 µs | 10.10 µs |
| p99 latency | 19.40 µs | 109.12 µs |
| Peak RSS | 9.8 MB | 9.9 MB |

**292× to 499× the 200 Hz requirement.**

### B — Real IO-VNBD data resampled to 200 Hz, 1,034,900 samples (3 runs)

```
idr_edge --input "data/raw/IO-VNBD/.../S (Driver A)/S1/S-S1.csv" \
         --map core/cpp/apps/mappings/iovnbd_smartphone.json \
         --session-longest --resample 200 --bench
```

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| Engine time for 1,034,900 samples | 7.442 s | 7.145 s | 7.269 s |
| Sustained throughput | **139,065 Hz** | **144,851 Hz** | **142,370 Hz** |
| p50 latency | 5.90 µs | 5.90 µs | 6.00 µs |
| p99 latency | 13.30 µs | 13.10 µs | 11.20 µs |
| Peak RSS | 416 MB | 416 MB | 416 MB |

**695× to 724× the 200 Hz requirement**, on a 5,174-second real drive log
(68.7 % of samples GNSS-denied).

The 416 MB is the *CLI* holding the whole 1.03 M-sample input and output
trajectory in RAM at once, not the engine. The streaming engine's own state is
O(window): 9.8–11 MB total process RSS on the 60 s runs above.

### C — Worst case: 180-particle graph filter, 100 % GNSS-denied, 200 Hz (5 runs)

```
idr_edge --synth 60 --rate 200 --graph campus --bench
```

| | min | max |
|---|---|---|
| Sustained throughput | **19,682 Hz** | **26,351 Hz** |
| p50 latency | 33.00 µs | 44.50 µs |
| p99 latency | 83.30 µs | 202.10 µs |

**98× to 132× the 200 Hz requirement**, with the particle filter resampling on
every single sample — a configuration the real pipeline never runs, because the
PF only engages during GNSS outage and the architecture reserves heavy compute
for junctions.

### D — 1000 Hz headroom

```
idr_edge --synth 60 --rate 1000 --bench
```
39,030 Hz sustained, mean 25.62 µs/sample, p50 23.20 µs, p99 68.10 µs, 28.9 MB.
39× realtime at 1 kHz. Per-sample cost rises with rate because
`FrequencyDecoupledOdo` keeps a 2-second window (`windowForRate`) and rescans it
each push — 2000 samples at 1 kHz vs 400 at 200 Hz. That is a known O(window)
cost in `src/inference.cpp`, not a limit of the estimator.

### Verdict on the 200 Hz requirement

**Met, with 2–3 orders of magnitude of margin, in every configuration tested.**
The binding constraint on this engine is not CPU.

---

## What has *not* been verified

Stated plainly, because the numbers above are only worth what their caveats are:

1. **No ARM / edge-SoC measurement.** Everything above is x86-64 on a laptop.
   The engine has no SIMD, no threads and a ~10 MB footprint, so an ARM Cortex-A
   board should clear 200 Hz comfortably — but that is a prediction, not a
   measurement, and it is not claimed as evidence.
2. **No real FOG IMU data.** No 200 Hz fibre-optic-gyro log exists on this
   machine. Set B is genuine IO-VNBD road data but was captured at 10 Hz and
   linearly upsampled to 200 Hz, so it exercises the engine at 200 Hz without
   containing genuine 200 Hz *information*. Set A is synthetic.
3. **These are throughput numbers, not accuracy numbers.** The trajectory
   statistics `idr_edge` prints (`path length`, `closure err`) are raw outputs of
   an unaided INS run and are large — e.g. 3,685 m closure error on the 5,174 s
   S-S1 drive with no road graph and 68.7 % of samples GNSS-denied. Accuracy
   evidence lives in `lab/` and `docs/PROOF_PROTOCOL.md`, not here.
4. **Lowpass cutoff is clamped below 20 Hz inputs.** `nav_core` designs its
   Butterworth at 8 Hz, which is above Nyquist for a 10 Hz log. `idr_edge` clamps
   the cutoff to `0.4 × fs` and prints a `note:` line when it does. `nav::runEngine`
   avoids this by resampling to 50 Hz first; the streaming path does not resample
   by default, because an external 200 Hz IMU should not be decimated.
5. **`--mode batch` always uses the built-in campus graph.** `nav::runEngine`
   falls back to `defaultCampusGraph()` when no graph is supplied, and it also
   runs the car-style baseline, so batch-mode benchmark samples are counted as
   `2 × samples` and its throughput is not comparable to stream mode.

---

## Relationship to `nav_core`

`idr_edge` adds no mathematics. `--mode batch` calls `nav::runEngine` directly.
`--mode stream` composes the same public objects that `src/engine.cpp`'s inner
loop composes — `SixAxisFilter`, `BiasCalibrator`, `FrequencyDecoupledOdo`,
`InvariantEKF`, `solveLean`, `GraphParticleFilter`, `stepLightCount` — one sample
at a time, so per-sample latency is measurable. The one deliberate deviation is
GNSS outage detection: `nav::gnssOutageMask` rescans the whole fix list per call
(O(n) per sample), so the streaming path keeps a cursor into the time-sorted fix
list instead. For sorted fixes the two produce identical results.
