# Scalability beyond roads — the cross-domain evidence

**Purpose.** Two jobs. (1) Give the deck and the Q&A a *sourced*, defensible
story that our idea is a member of a proven family, not a hackathon novelty.
(2) Fix the exact line between what we may claim and what we may not.

Every claim below carries a source and a tag:
**[P]** primary / peer-reviewed / agency · **[S]** secondary / trade press ·
**[INF]** our own inference or framing, not a sourced fact.

---

## A. The one-sentence version

> Constraining an inertial estimate with a prior map is **flight-proven
> doctrine** — submarines, cruise missiles, rail, indoor robotics, and lunar
> landers all do it. Nobody had done it on a commodity smartphone with a road
> graph. That is our contribution: not the principle, but the platform.

This framing is deliberately chosen. It makes the idea feel **innovative**
(nobody did it on a phone) *and* **safe** (the principle is proven). With a
conservative or aerospace-adjacent judge, that combination outscores a claim of
pure novelty, because pure novelty reads as unvalidated risk.

---

## B. The critical distinction — hold this line

There are two different ways to use a map, and conflating them is the mistake a
technical judge will catch:

| | Map as **measurement model** | Map as **state constraint** ← ours |
|---|---|---|
| How | "Does the depth/terrain I just measured match the map here?" | "The state *is* (which edge, how far along). Off-road is not representable." |
| Used by | Submarine gravity/bathymetric matching, TERCOM, MagNav | Rail path-constrained estimation, indoor floor-plan particle filters, **COAST** |
| Effect | Bounds drift by periodic correction | Structurally forbids lateral divergence |

**What we may say:** "the same philosophy — bound inertial drift with prior
geospatial knowledge." **[INF]**
**What we may not say:** that submarines use our exact method. They use the same
philosophy with a different mechanism.

---

## C. Rail — the closest match, and our strongest technical citation

**This is not kinship. This is the same idea, arrived at independently.**

> von Einem, Cramariuc, Siegwart, Cadena, Tschopp — *Path-Constrained State
> Estimation for Rail Vehicles*. **"The state is modeled in 1D along the track
> geometry,"** with multi-hypothesis tracking over candidate routes.
> **RMSE 4.78 m**, track selectivity up to **94.9%** on Zurich tram data.
> **[P]** https://arxiv.org/abs/2308.12082

Their state: *(which track, how far along it)* + hypotheses over branches.
Ours: *(which road edge, how far along it)* + particles over branches.

**Defensible claim:** "The rail robotics literature independently arrived at our
exact state parameterisation. We apply it to a road graph, which branches far
more often than a rail network." **[INF on the comparative-difficulty half —
present that as our judgement, not as a fact.]**

Operationally, ETCS trains localise by odometry, reset intermittently by
**balises** — georeferenced trackside points. **[S/P]** — note this: it becomes
important in §G.

## D. Indoor pedestrian — our honest academic ancestor

> Woodman & Harle, *Pedestrian Localisation for Indoor Environments*, UbiComp
> 2008 (Cambridge). Foot-mounted IMU + building model + **particle filter** gives
> absolute positioning "despite the presence of drift in the inertial unit and
> without knowledge of the user's initial location."
> **[P]** https://www.semanticscholar.org/paper/437739f2b3e2bffbbc3b59a09c2b25e952fbf443
> Won the **ACM UbiComp 10-Year Impact Award, 2018.**
> **[P]** https://www.cst.cam.ac.uk/news/dr-robert-harle-receives-acm-ubicomp-10-year-impact-award-0

Walls kill particles there exactly as road edges constrain particles here.

**This is the citation that protects us.** The correct framing is *"we are the
road-network descendant of a line of work that holds an ACM 10-year impact
award."* Claiming we invented map-constrained particle filtering is the single
thing a technical judge would catch us on. Citing this **raises** the F1 score.

## E. Underwater — the philosophy, in naval language

- Marine INS accuracy "reaches up to 1 nautical mile / 3 days or even greater."
  In a real South China Sea trial over ~340 nm, INS error accumulated to **~12 nm**;
  gravity-anomaly map matching corrected it to **2.83 nm**.
  **[P]** https://pmc.ncbi.nlm.nih.gov/articles/PMC5751537/
- **The quote worth memorising** — from that paper, our architecture in naval
  terms: *"the primary role of INS was to define a confidence search area of the
  real location. The matched location was not substantially affected by the INS
  drift as long as the real location was in its confidence area."* **[P]** same URL
- Bathymetric terrain-aided navigation is **literally a particle filter**: prior
  seafloor map + sonar → **9.7 m mean horizontal error** against a 10 m map, with
  "absolute and bounded position error."
  **[P]** https://pmc.ncbi.nlm.nih.gov/articles/PMC5419793/
- US Navy AN/WSN-7 (Northrop Grumman Sperry Marine), Safran Sigma 40 on Scorpène
  and Suffren classes. **[S]**

**DO NOT put on a slide:** any drift spec for Safran Sigma 40, or Honeywell /
Kearfott naval INS accuracy figures — these could not be verified.

## F. Aviation and space

- **TERCOM** — radar altimeter profile correlated to a stored terrain map;
  TERCOM-equipped missiles "receive constant fixes during the flight, and thus do
  not have any drift," unlike INS. **[S]** https://en.wikipedia.org/wiki/TERCOM
  **DO NOT quote a TERCOM CEP figure — the circulating "~30 m" belongs to
  scene-matching (DSMAC), not TERCOM, and was not verified.**
- **TERPROM** (Collins) — terrain-referenced navigation fielded on "over 5000"
  military aircraft. **[S]** https://en.wikipedia.org/wiki/TERPROM
- **Vision TRN flight test** (Cessna, Honeywell HG9900 IMU): mean position error
  **±1.19–1.58 m** at 3,000 m. Motivation stated as GPS jamming/spoofing.
  **[P]** https://pmc.ncbi.nlm.nih.gov/articles/PMC12473920/
- **MagNav** — USAF/MIT Lincoln Lab flew a C-17 in May 2023 at roughly **1 km**
  accuracy. **[S]** https://www.airandspaceforces.com/air-force-magnetic-navigation-gps/

### Chandrayaan-3 — the ISRO callback, and it is sourced

The powered descent comprised "a braking phase with inertial navigation, an
attitude hold, a braking phase with **absolute navigation**, and a terminal
descent phase." The rough braking phase is designed to set up conditions
favourable for the Lander Position Detection Camera, "**which provides lander
absolute position with respect to moon surface**… to provide absolute sensor
information to navigation **which otherwise operate only with inertial sensors**
in rough braking phase."
**[P]** https://arxiv.org/html/2511.03594v2

**Chandrayaan-3 flew on pure inertial, then switched to camera-to-map absolute
navigation before it dared to land.** That is our architecture, on the Moon, by
the agency that wrote our problem statement. Used respectfully — as *"the
principle we are applying is the one your own lander used"*, never as *"we are
like Chandrayaan-3"* — this is the strongest single line available to us with
this audience.

### Perseverance, February 2026 — the freshest example

Visual odometry drift left the rover "off by more than 100 feet (up to 35 metres)
on long drives." JPL's **Mars Global Localization** matches navcam panoramas
against onboard MRO orbital maps and pins the rover to **~25 cm in about two
minutes** — first used operationally **2 and 16 February 2026**.
**[P]** https://www.jpl.nasa.gov/news/nasas-perseverance-now-autonomously-pinpoints-its-location-on-mars/
**[S corroboration]** https://phys.org/news/2026-02-mars-gps-perseverance-centimeters.html

Mars 2020 entry TRN improved the landing estimate "from 2 miles (3.2 km) to
0.025 miles (40 metres) or better."
**[P]** https://www.nasa.gov/directorates/stmd/game-changing-development-program/impact-story-terrain-relative-navigation/

**The line for a non-technical judge** — every clause sourced above:

> "A Mars rover with a multi-million-dollar navigation suite still drifted
> thirty-five metres. NASA's fix was not a better gyroscope — it was a map.
> Chandrayaan-3 did the same thing: pure inertial on the way down, then switched
> to camera-and-map before it dared to land. We do that on a ₹15,000 phone, with
> a road map."

---

## G. The honest limitation — volunteer this, it is a strength

**Road constraint corrects *lateral* error. It does not correct accumulated
*longitudinal* (along-track) error.** That remains an open problem in the
literature. **[P]**
https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/iet-its.2018.5272

This is why our residual error after map-in-loop is largely *along the road* —
right street, wrong distance down it. It is also **exactly why rail still
installs physical balises**: the 1-D constraint alone was never enough for them
either, so they reset the odometer at known points. **[S/P]**

Saying this out loud does three things at once:
1. It pre-empts the sharpest technical question in the room.
2. It shows we know *which* error our method kills and which it does not.
3. It reframes our limitation as **domain maturity** — the same limitation the
   rail industry has, solved the same way (periodic absolute fixes).

Our roadmap answer follows naturally: along-track error is what map-matched
landmarks, ZUPT, and any recovered GNSS fix are for.

### Where the method simply fails — say this plainly
Off-road; parking structures and private campuses absent from the graph; newly
built or unmapped roads; open sea; any GNSS-denied environment with no prior map.
Canonically, TERCOM had the identical failure: "if the missile was launched from
an unexpected location or flew too far off-course, it would never fly over the
features included in the maps, and would become lost." **[S]**

Featureless regions break map matching in every domain — the AUV paper shows
9.7 m error in feature-rich terrain and "performance degraded substantially" in
flat terrain. **[P]** https://pmc.ncbi.nlm.nih.gov/articles/PMC5419793/

**Our fallback is honest:** with no map we degrade to free inertial dead
reckoning — the 17% baseline we already published. We fail *back*, not *closed*.

---

## H. How this feeds the `ConstraintManifold` refactor

§C and §D are the justification for Phase 2 Subagent 2.1. Rail is a **1-D
polyline** — that is exactly `CorridorManifold`. So implementing it is not
speculative future-proofing; it is implementing the state space that a
peer-reviewed rail paper validated at 4.78 m RMSE.

**What we may claim once the refactor lands:** "The constraint is an interface.
We ship a road-graph implementation and demonstrate a corridor implementation —
which is the same 1-D-along-the-path state space the rail literature uses."

**What we may still not claim:** that we have validated rail, underwater, or
planetary navigation. We have not. Those are roadmap, and the deck must say so.

---

## I. Slide-ready condensation (for the Future Scope slide)

One row per domain. Keep it to five rows and one sentence of framing.

| Domain | Their map | Status |
|---|---|---|
| Road (ours) | OSM road graph | **Shipping — 2.02× measured** |
| Rail / tunnel / channel | Track polyline | Corridor manifold — implemented + tested |
| Indoor | Floor plan | Prior art (Woodman & Harle, ACM 10-yr impact award) |
| Undersea | Bathymetry / gravity map | Proven doctrine — not our work |
| Planetary | Orbital imagery | Chandrayaan-3, Perseverance — not our work |

Framing sentence: *"Same filter. Different manifold. The algorithm never knew it
was a road."*
