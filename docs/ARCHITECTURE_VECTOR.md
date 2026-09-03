# Vector / Graph Localisation Architecture

**Product:** SIH26168 Intelligent Dead Reckoning SDK (enterprise-shaped, not jury-theatre)  
**Status:** design + thin-slice (`VectorMapLocator`) — 4 Sept 2026  
**Related:** `SIH26168_PROJECT_BIBLE.md` §§4–5, 9–10 · `core/ts/src/graphpf/`

---

## 1. Problem we are selling

Phone INS drifts. Road graphs kill most of that drift **along an edge** [F9], but heading only matters at forks [F10]. A 180-particle filter on every tick is correct-ish and slow; sellable SDKs need a **latency budget**, an honest API, and adaptive compute.

We do **not** invent map matching. We ship an application stack: lean-aware INS + graph belief + junction-only heavy compute.

---

## 2. Prior art vs ours (say this in sales / jury)

| Claim | Status |
|---|---|
| HMM / soft map matching | **Prior art** — Newson & Krumm (2009), Map-Fusion 2024 |
| Road-signature / embedding localisation | **Prior art** — e.g. arXiv 2303.03942 |
| Learned IMU Δp + Σ (TLIO-style) | **Prior art method**; our use is composition with graph |
| Two-wheeler lean composition [F5/F6] | **Ours** (application + productisation) |
| Adaptive compute: cheap along edge, PF/mixture only at junctions [F10] | **Ours** (framing + implementation) |
| Branch-decision accuracy as product metric [F12] | **Ours** |

Under-claim deliberately (§9 of the bible).

---

## 3. Layered SDK (sellable surface)

```
┌─────────────────────────────────────────────────────────────┐
│  L4  Shells — Android / Web / Desktop (presentation only)   │
└──────────────────────────▲──────────────────────────────────┘
                           │ NavSnapshot {lla, P, edge, mode, ms}
┌──────────────────────────┴──────────────────────────────────┐
│  L3  NavCore (TypeScript now; C++/WASM later)               │
│                                                             │
│  preprocess → odo(Δv) → leansolver → InEKF                  │
│       │                                                     │
│       ▼                                                     │
│  ┌─ VectorMapLocator (default along-edge) ──────────────┐   │
│  │  edge embeddings · NN / softmax · Gaussian-on-s      │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │ approaching junction / multimodal     │
│                     ▼                                       │
│  ┌─ GraphParticleFilter (junction / high-entropy only) ─┐   │
│  │  N particles on outgoing fan · ESS resample          │   │
│  └──────────────────────────────────────────────────────┘   │
│  aiding (light count, baro) · metrics (loop / branch)       │
└──────────────────────────▲──────────────────────────────────┘
                           │ ISensorFrame
┌──────────────────────────┴──────────────────────────────────┐
│  L2  Sensors · L1  Offline road graph (OSM → binary)        │
└─────────────────────────────────────────────────────────────┘
```

**Public API sketch (stable names):**

```ts
interface NavCoreOpts {
  useVectorLocator?: boolean; // default true when productised
  pfJunctionOnly?: boolean;   // F10 adaptive
  topK?: number;              // soft edge candidates
}

NavCore.step(frame): NavSnapshot
NavCore.seed(lla, yaw)
NavCore.setGraph(graph)
```

---

## 4. Vector map matching (thin slice)

### 4.1 Edge feature vector

For each directed edge:

```
f_e = [ sin θ, cos θ, length_norm, tunnel_flag, garage_flag ]
```

- `θ` = edge heading (deg→rad)  
- `length_norm` = `length_m / L_ref` clipped to [0, 1] (`L_ref` = max edge length in graph)  
- flags ∈ {0, 1}

Precomputed once per `setGraph`. No heavy ANN library — campus/city extracts are small enough for brute-force top-k.

### 4.2 Query → posterior

Given `(yaw, speed, pos_hint)`:

1. Build query heading embedding `q = [sin yaw, cos yaw, …]` (length/flags neutral or weakly informed).  
2. Score each nearby edge:

   `score_e = cos_sim(q, f_e) + log κ(‖p − π_e(p)‖)`

   where `κ` is a Gaussian distance kernel on residual to the edge polyline projection, and `π_e` is along-track projection → `s ∈ [0,1]`.  
3. Softmax over top-k candidates → `p(e | z)`.  
4. Along-edge parameter: `s = project(pos_hint → e)`.

### 4.3 Belief representation (cheaper than PF)

Along a **single** dominant edge:

- Belief = univariate Gaussian (or 1–3 mixture components) on `s`  
- Propagate: `s ← s + v·Δt / length`, inflate `σ_s` with process noise  
- Observation: project INS/odo position onto edge → Kalman-style update on `s`

At **junctions** (metres-to-node < F10 horizon):

- Soft-assign over outgoing edges by heading likelihood  
- If entropy high or fan-out ≥ 3: **hand off to GraphParticleFilter** for one decision window  
- After a winner emerges (mass > τ): collapse back to Gaussian-on-s

Honest rule: **PF still needed** when the posterior is multimodal and edges are kinematically similar (garage 4-way, ±8° forks under speed error — see F10 table).

---

## 5. Learned displacement vectors (roadmap, not in this thin slice)

TLIO-style module: IMU window → `(Δp, Σ)` in body/ENU.

```
InEKF prior  ⊕  Δp,Σ  ⊕  graph constraint (VectorMapLocator / PF)
```

Product note: the network is a **velocity / displacement prior**, not a replacement for map decisions. Composes with lean solver [F5] the same way AVNet velocity does. Ship stub interface first; train on IO-VNBD + our two-wheeler set later.

---

## 6. Latency budget (on-device, 10 Hz requirement)

| Stage | Target p95 | Notes |
|---|---|---|
| Preprocess + lean | ≤ 1 ms | fixed-point 3–5 iters |
| InEKF prop/update | ≤ 1 ms | SE₂(3) small state |
| Vector locate (brute K≤64) | ≤ 0.5 ms | campus; city tiles via spatial hash later |
| Gaussian-on-s update | ≪ 0.1 ms | |
| Junction PF (N=64–180, rare) | ≤ 2 ms | only near nodes |
| Learned Δp (ONNX, future) | ≤ 8 ms | NNAPI / CPU |
| **Total tick** | **≤ 12 ms** | headroom vs 100 ms period |

Compare: always-on GraphPF N=180 ≈ several× Vector locate on the same graph; most ticks never need particles.

---

## 7. Accuracy / latency tradeoffs vs GraphParticleFilter

| Mode | Typical cost | When accurate | When it fails |
|---|---|---|---|
| Vector + Gaussian-on-s | O(E_local) | Straight / mildly curved edges, good yaw | Multimodal forks |
| Softmax top-k only | cheapest | Unique heading signature nearby | Parallel one-ways |
| PF at junction | O(N · fanout) | Competing exits [F10] | Always-on waste |
| Full PF every tick | O(N · E) | Robust but overkill | Battery / thermal |

**Product default:** `useVectorLocator=true`, promote to PF when `junctionMode && entropy > H*`.

---

## 8. Thin-slice deliverable (this PR)

| File | Role |
|---|---|
| `docs/ARCHITECTURE_VECTOR.md` | this document |
| `core/ts/src/graphpf/vector_locator.ts` | `VectorMapLocator` |
| `core/ts/src/engine.ts` | `RunOpts.useVectorLocator` |
| `core/ts/src/test/vector_locator.test.ts` | unit tests |

Limitations carried from §10: sim-validated findings only; hard brake mid-turn still hurts; speed still required from odo / GNSS hold.
