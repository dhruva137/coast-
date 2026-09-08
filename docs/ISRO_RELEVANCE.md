# Why ISRO asked this, and where the technology actually goes

**COAST** — SIH 2026, problem statement 26168, Indian Space Research Organisation,
Department of Space.

This document answers the question a judge will ask in some form within the
first two minutes: *"This is a maps app. Why is the space agency asking for it?"*

The short answer: **it isn't a maps app. It is a sovereignty problem wearing a
delivery-rider costume.**

---

## 1. The founding story: Kargil, 1999

In 1999, during the Kargil conflict, India requested GPS data for the Kargil
region from the United States. **The request was denied.** India was operating
in its own territory, in a live conflict, and could not get positioning from a
constellation it did not own.

That denial is the reason the Indian Regional Navigation Satellite System
exists. NavIC — *Navigation with Indian Constellation* — was built so that
access to precise positioning over India could never again be somebody else's
decision.

**This is the frame for the entire problem statement.** ISRO is not asking for a
better Google Maps. It is asking: *when the signal is not there, for whatever
reason, what does the receiver do?*

The problem statement says this itself, in its own words — it names
"unintentional electromagnetic interferences from variety of sources such as
jamming" alongside tunnels and urban canyons. Jamming is not a tunnel. It is in
that sentence deliberately.

---

## 2. The threat is current, not historical

| Threat | What it does | Why inertial navigation answers it |
|---|---|---|
| **Jamming** | Floods the band with noise; the receiver sees nothing | An IMU has no antenna. There is nothing to jam. |
| **Spoofing** | Feeds *believable but false* position; the receiver happily reports a lie | An independent inertial solution disagrees with the spoof, which is how you *detect* it |
| **Structural denial** | Tunnels, urban canyons, parking structures, deep valleys | The PS's stated civilian case |

Spoofing is the nastier of the two, and it is the one where dead reckoning earns
its keep twice over. Jamming is loud and obvious — you know you have lost the
signal. Spoofing is silent: the system keeps working, confidently, on wrong
data. An inertial solution running in parallel gives you a second opinion that
cannot be forged from outside the vehicle.

GPS interference along India's western border has been a live aviation concern,
and Indian defence and aviation bodies have publicly pushed for jam-resistant
navigation. This is not a hypothetical.

---

## 3. Where this exact mathematics is already used

Dead reckoning is not a smartphone trick. It is one of the oldest and most
load-bearing techniques in aerospace, and the same equations scale across four
orders of magnitude of hardware cost.

### Space

- **Launch vehicles.** Every rocket flies on an inertial navigation system.
  There is no GNSS fix worth trusting through the plume, the roll programme, and
  the staging events; the vehicle integrates its own accelerometers and gyros.
- **Lunar and planetary landing.** Chandrayaan-3's lander had **no GNSS at all** —
  there is no satellite constellation around the Moon. Powered descent ran on
  inertial navigation providing state estimates relative to the Moon's centre,
  updated by other sensors during defined hold phases. That is dead reckoning,
  in the strictest sense, with the entire mission riding on it.
- **Spacecraft attitude and orbit determination**, when star trackers are
  blinded or ground contact is unavailable.

### Defence and aviation

- Aircraft INS, missile and munition guidance, and the "GPS-denied battlefield"
  problem generally. Strategic-grade systems couple a **fibre-optic gyroscope
  (FOG)** INS with sensor fusion to hold position and attitude through complete
  GNSS outage.
- **Note the problem statement's own wording here:** it asks for an edge engine
  running at *"around 200Hz"* using *"FOG based IMU sensors data"*. That phrase
  is not about smartphones. It is ISRO telling you the algorithm must scale up to
  their hardware, not just down to a phone.

### Subsurface and indoor

- **Submarines** — the classic case. No GNSS underwater; months of navigation on
  pure inertial.
- Underground mining, firefighters and soldiers inside buildings, underground
  metro (named explicitly in the PS benchmark).

### The civilian case the PS actually names

Vehicle logistics, ride-hailing, quick commerce, emergency responders — and
**"millions of two-wheelers (motorcycles/scooters)"** whose only navigation
device is the rider's phone.

---

## 4. Why the phone is the interesting hard case, not the easy one

It would be reasonable to ask why ISRO wants this on a ₹15 000 phone rather than
on the FOG-grade hardware they already fly.

Because the hardware is the whole difficulty. The gap between a strategic-grade
FOG IMU and a smartphone MEMS IMU is roughly **four orders of magnitude in bias
stability**. The mathematics is identical; only the error budget changes. A
method that survives a consumer MEMS gyro will survive anything better, and it
does so on a device that is already in 800 million Indian pockets with no
procurement, no installation, and no unit cost.

That is the actual thesis of this project:

> **Take the navigation discipline ISRO uses on launch vehicles and lunar
> landers, and make it survive the worst inertial sensor in widespread use.**

Our measurements are consistent with exactly that framing. We found that free
inertial dead reckoning on a phone fails the ISRO drift bar on **55% of
segments even when handed a perfect yaw sensor** — i.e. the sensor is not the
only problem, the *architecture* is. That is why COAST constrains the estimate
to a road/rail graph rather than integrating freely, and why that change is
worth 2.02x on real data.

---

## 5. The demo, told in this frame

The judge does not need the Kargil story to understand a walking demo. But the
walking demo means something different once they have heard it.

**What they see:** you hand them a phone, turn location off in front of them,
walk a loop, and come back to a marked tile. The dot never stopped moving. The
screen says how far off it thinks it is.

**What you say:** *"That is the same class of problem as landing on the Moon
with no satellites overhead, and the same class of solution. We are running it
on a phone because that is the hardest version of it, and because it is the
version that reaches two hundred million riders tomorrow morning."*

**What you do NOT claim:** that we have solved GNSS-denied navigation, that this
is flight software, or that our numbers are comparable to a FOG INS. We are a
research prototype with measured results and named failures. That is enough, and
overclaiming in front of a space agency is how teams lose.

---

## 6. Advanced scenarios worth naming if asked

Ranked by how defensible they are for us:

1. **Multi-level parking** — the PS names it, we have a barometer in the log
   schema for floor detection, and it is demoable in any mall.
2. **Underground metro** — named in the PS benchmark. Topologically 1D, no
   junctions, so it is the *easy* case for our map-constrained filter, and we
   have a metro profile with zero-velocity updates at stations.
3. **Urban canyon** — GNSS present but lying (multipath). This is where the
   spoof-detection framing applies: an inertial second opinion flags a fix that
   jumped 80 m sideways through a building.
4. **Convoy / fleet operations under jamming** — plausible extension, but say
   "extension", not "capability". We have not tested it.
5. **UAV / drone navigation in contested airspace** — adjacent field, real
   literature, but a different vehicle dynamics problem. Cite it as future work
   only.

---

## Sources

- [Securing India's Skies: Countering the Threat of GPS Spoofing and Hybrid Warfare](https://www.orfonline.org/expert-speak/securing-india-s-skies-countering-the-threat-of-gps-spoofing-and-hybrid-warfare) — Observer Research Foundation
- [Resilient PNT for a Self-Reliant India](https://geospatialworld.net/prime/technology-and-innovation/resilient-pnt-for-a-self-reliant-india/) — Geospatial World
- [How Advanced Navigation Strengthens Resilient PNT in GPS Contested Environments](https://www.unmannedsystemstechnology.com/feature/how-advanced-navigation-strengthens-resilient-pnt-in-gps-contested-environments/)
- [Indian Aviation Experts Demand Jamming-Resistant Overhaul](https://idrw.org/indian-aviation-experts-demand-jamming-resistant-overhaul-as-gps-interference-from-pakistan-border-endangers-skies/) — IDRW
- [Decoupled Thrust-Axis Attitude Control Using Quaternions for Chandrayaan-3 Lunar Landing Mission](https://arxiv.org/pdf/2605.29409) — arXiv
- [Powered Descent Trajectory Optimization of Chandrayaan-3](https://arxiv.org/pdf/2511.03594) — arXiv
- [Dead reckoning for GNSS denied scenarios](https://www.uavnavigation.com/company/blog/dead-reckoning-gnss-denied-scenarios) — UAV Navigation
- [The GPS-Denied Battlefield](https://www.defencexp.com/the-gps-denied-battlefield/) — DefenceXP

**Caveat on the Chandrayaan-3 material:** the arXiv papers above confirm that the
lander's navigation provided state estimates relative to the Moon's centre within
an NGC system, but they focus on attitude control and trajectory optimisation
rather than the navigation sensor suite. Do not quote specific Chandrayaan-3
sensor models or accuracy figures — we have not verified them. The defensible
statement is the obvious one: **there is no GNSS at the Moon, so descent
navigation is inertial by necessity.**
