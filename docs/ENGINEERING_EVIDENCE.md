# Engineering evidence — Phase 2 surface for judges

This file points at **inspectable** architecture and test/bench entry points. It
does not invent field results.

## Architecture (map constraint)

The map is a **plug-in**, not a hard-coded road assumption:

| Layer | Symbol | Role |
|---|---|---|
| Interface | `ConstraintManifold` | `project`, `neighbours`, `transition_cost`, `dim` |
| Shipping | `RoadGraphManifold` | Existing road-graph geometry behind the interface |
| Demo | `CorridorManifold` | 1-D polyline + lateral tolerance |

**Implementations**

- C++ core: `core/cpp/include/nav/manifold.h`, `core/cpp/src/manifold.cpp`
- TypeScript mirror: `core/ts/src/graphpf/manifold.ts`
- Python mirror: `lab/nav/manifold.py`

Production road filters (`GraphParticleFilter` / `RoadParticleFilter`) keep their
prior numeric behaviour. `GraphParticleFilter::mapProject` delegates to
`RoadGraphManifold::project` with the same scoring as before.

### Honesty limitation — corridor

`CorridorManifold` is a **synthetic demonstration** of the interface (rail /
channel / tunnel-bore *shape*). It is exercised only on synthetic motion in unit
tests. We have **not** field-validated rail, undersea, or planetary navigation.
Do not claim otherwise in the deck or Q&A.

## Test entry points

| Suite | Command |
|---|---|
| C++ golden (incl. manifold) | Configure + build `core/cpp`, then `ctest` or run `nav_golden` |
| TypeScript core | `cd core/ts && npm test` |
| Python manifold | `python tests/test_manifold.py` |
| Claim / sanity gate | `python tools/verify_all.py` (includes `tests/test_manifold.py`) |

Expected manifold checks:

1. Corridor clamps an 8 m offset to the lateral tolerance and keeps a synthetic
   filter’s lateral error bounded.
2. The **same** tiny manifold filter run against `RoadGraphManifold` and
   `CorridorManifold` both exhibit bounded lateral-error semantics.
3. `mapProject` / `RoadGraphManifold.project` agree on the campus graph.

## Bench entry points (map-in-loop headline)

Committed measured result (do not re-tune prose off a different run):

- Summary: `lab/stress/results/mapfilter/summary.md`
- Machine-readable: `lab/stress/results/mapfilter/report.json`
- Recompute (expensive, needs IO-VNBD + graph):  
  `python lab/stress/run_mapfilter_eval.py`

Headline (junctions / open road): **2.02×** lower median position error
(252.66 m → 125.20 m). `RoadParticleFilter` was **not** rewritten onto the
manifold interface in this phase; the committed report is therefore unchanged
by construction. `tests/test_manifold.py::test_mapfilter_headline_unchanged`
pins those floats.

## Filter-trace export (Phase 3 engine viz)

Per-step particle cloud for the `/engine` canvas — not a headline number.

```text
python lab/stress/export_filter_trace.py
python lab/stress/export_filter_trace.py --drive S-M --t0 1830 --particles 200 --show 180
python lab/stress/export_filter_trace.py --synthetic
```

Writes `lab/stress/results/traces/<drive>_<t0>.json`. Real exports set
`meta.honesty: "REAL"` (IO-VNBD + midlands OSM + `RoadParticleFilter`). If data
or graph is missing, the script writes a tiny `honesty: "SYNTHETIC"` plumbing
trace instead — never invent particles labelled as real. Particles are
downsampled (`particles_shown` / `particles_total`); `n_eff` is the pre-resample
effective sample size. Do not resurrect spread-based confidence radii.

## Related product docs

- `docs/ARCHITECTURE_V2.md` — map-in-loop doctrine
- `docs/ENTERPRISE_PRODUCT.md` — evidence classes (REAL / INJECTED / SYNTHETIC)
- `docs/SDK.md` — integration surface
