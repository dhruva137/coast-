# 08 — Stretching the domain, without leaving the problem statement

The instruction was: *"find what else we can do — aviation, other sectors —
but this is what the problem statement is strictly about, so we have to strictly
be here."*

**Good news: the problem statement itself asks us to generalise.** We do not have
to choose between staying inside it and stretching beyond it.

---

## A. The PS explicitly authorises the stretch — quote it

> *"The Final solution and AI/ML models developed **should not be constricted to
> smart phone IMU sensors data alone** (Mobile application). These
> algorithms/models **should also work with any other external IMU sensors data**
> (Edge deployable software engine)."*

And:

> *"…higher update rates on Edge deployable software engine using **FOG based IMU
> sensors** data (around 200Hz)."*

**This changes the framing entirely.** Generality is not us going off-piste — it
is a graded requirement. The edge engine and the `ConstraintManifold` interface
are *compliance work*, and we should present them that way.

**The sentence to use:** *"The problem statement asks for two deliverables: a
phone app and an edge engine that works with any IMU, not just a phone's. So
domain generality isn't our stretch goal — it's requirement six. Here's how far
we took it."*

---

## B. What we can honestly claim, in three tiers

Discipline matters here more than anywhere else, because this is where a pitch
most easily tips into fantasy. Three tiers, and never blur them.

### Tier 1 — SHIPPED, measured
- Smartphone app: 10 Hz, on-device inference, map-in-loop, **2.02× lower median
  position error**.
- Edge engine: same C++ core, headless, **120,305 Hz measured** against a 200 Hz
  requirement (600× headroom) — this directly satisfies the FOG-IMU edge clause.
- `ConstraintManifold` interface with `RoadGraphManifold` (shipping) and
  `CorridorManifold` (implemented, tested on synthetic motion).

### Tier 2 — DEMONSTRATED in code, not validated in the field
- The corridor manifold: a 1-D polyline with lateral tolerance. This is the rail
  track / shipping channel / tunnel bore state space.
- **What we may say:** *"The constraint is a plug-in. We ship the road-graph
  implementation and demonstrate a corridor implementation — the same 1-D
  along-the-path state space the peer-reviewed rail literature uses."*
- **What we may NOT say:** that we have validated rail, marine, or aviation
  navigation. We have not.

### Tier 3 — ROADMAP and intellectual kinship, clearly labelled
Everything in `win_tuning/SCALABILITY_BEYOND_ROADS.md`: submarine gravity/
bathymetric matching, TERCOM/TERPROM terrain-referenced navigation,
Chandrayaan-3's switch from inertial to absolute camera-to-map navigation,
Perseverance's Mars Global Localization. **All are other people's work.** We cite
them to show our idea belongs to a proven family — never to imply we did them.

---

## C. On aviation specifically — the honest position

The user asked about jets. Be careful here; it is the easiest place to overclaim
and an aerospace-adjacent judge will catch it instantly.

**What is true:**
- Terrain-referenced navigation (TERPROM) is fielded on "over 5000" military
  aircraft. Vision-based TRN flight tests reach ±1.19–1.58 m at 3,000 m. MagNav
  flew on a C-17. Aviation's GNSS-denial problem is severe and growing — IATA
  reports spoofing incidents up 193% in 2025 vs 2023.
- The *principle* is identical to ours: bound inertial drift with a prior map.

**What is not true, and must never be implied:**
- That our phone-grade MEMS work transfers to an aircraft. It does not. Aviation
  uses navigation-grade IMUs orders of magnitude better than a phone's, in a
  certified safety-critical context.
- That aviation's designated GNSS fallback is inertial. **It is not** — the joint
  EASA/IATA 2025 plan names conventional ground navaids (VOR/DME/ILS).

**The honest aviation line, if asked:**
> "The principle is the same one aviation already uses — terrain-referenced
> navigation is fielded on thousands of aircraft. But I wouldn't claim our work
> transfers to a jet: that's navigation-grade hardware in a certified
> safety-critical system, and it's a different engineering problem. Where our
> work does transfer is anything running a low-cost MEMS IMU along a known
> route — which is most ground vehicles, and the edge engine the problem
> statement asks for."

**That answer scores better than an aviation claim would**, because it
demonstrates we know where our competence ends.

---

## D. The domains that are genuinely ours to claim

Ranked by how defensible the claim is. Stay in the top half.

| Domain | Constraint manifold | How defensible |
|---|---|---|
| **Road vehicles** | OSM road graph | **Shipped, measured.** Our result. |
| **Two-wheelers** | Same | Our differentiator; lean handling built; field data still pending |
| **Trucks / logistics fleets** | Same | Same tech, different console. **The Fleet view demo is this.** |
| **Metro / rail** | Track polyline | Corridor manifold implemented; rail literature validates the state space |
| **Mine / tunnel vehicles** | Tunnel bore centreline | Same corridor manifold; a natural next application |
| **Warehouse / port equipment** | Aisle or lane network | Plausible, unbuilt — say "plausible" |
| Marine channels | Charted channel | Roadmap only — cite others' work |
| Aviation | Terrain / magnetic map | **Others' work. Cite, never claim.** |

---

## E. The security / anti-theft angle — a strong, ownable use case

The user raised this: *"a truck carrying sensitive information or data centres,
or theft."* It is a genuinely good use case and it is entirely within the PS's
"vehicle logistics" framing.

**The insight that makes it more than a generic tracking pitch:**

> A GPS tracker is defeated by a $20 jammer. That is *why* cargo theft crews carry
> them — kill the signal and the vehicle vanishes from the operator's map.
>
> An inertial + map system **cannot be jammed**, because it is not receiving
> anything. Jam the GPS and our position keeps updating. The attack that defeats
> every conventional tracker is the exact scenario we were built for.

That is a real security property of the architecture, it follows directly from
the jamming evidence in `win_tuning/RESEARCH_GLOBAL_CONTEXT.md`, and it is
demonstrable on stage: **turn on airplane mode — the jamming stand-in — and the
dot keeps moving.**

**What we may say:** the architecture is immune to signal denial because it
depends on no signal.
**What we may not say:** that we have built anti-theft features, tested against
real jammers, or deployed with any operator.

**The Fleet view is the demo for this.** A path that turns teal exactly where a
vehicle went dark is the picture of the use case.

---

## F. How this lands in the deck

**One slide element, five rows** (from `SCALABILITY_BEYOND_ROADS.md` §I), plus one
framing sentence:

> *"Same filter. Different manifold. The algorithm never knew it was a road."*

Then the compliance callback, which is the part most teams will miss:

> *"And this isn't scope creep — the problem statement's sixth requirement is an
> edge engine that works with any IMU, not just a phone's. This is that
> requirement, taken seriously."*

**Do not spend more than one slide element on this.** The stretch is a
credibility multiplier on the core result; it is not the core result. A team that
talks more about submarines than about their measured 2.02× has lost the plot,
and a judge will notice.
