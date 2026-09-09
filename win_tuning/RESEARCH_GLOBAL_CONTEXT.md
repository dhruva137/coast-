# Global context — the sourced evidence pack

**Purpose.** Give F4 (Impact), F6 (Sustainability), F7 (Business) and the Q&A a
factual base that a judge can verify. Every fact carries a source and a label.

**Label key:**
`P-VERIFIED` — official source, retrieved and read ·
`P-UNFETCHED` — official URL, blocked, content from search index only ·
`SECONDARY` — news / trade press ·
`INFERENCE` — our own reasoning, not a sourced fact ·
`NOT VERIFIED` — **must never appear on a slide**

---

## 0. THE FIVE STRONGEST FACTS (use these, in this order)

### 1. NavIC cannot currently provide standalone positioning — stated in Parliament
> "Presently the NavIC constellation has three satellites… minimum four
> operational satellites are required in orbit. **Hence, the NavIC constellation
> cannot provide standalone positioning service**, however timing service is
> functional. … Next NavIC satellite viz., NVS-03 is ready for launch and two
> more satellites viz., NVS-04 & NVS-05 are in advanced stage of realization."
> — Dr Jitendra Singh, Lok Sabha written reply, **29 July 2026**
> `P-VERIFIED` https://www.pib.gov.in/PressReleasePage.aspx?PRID=2291079&reg=48&lang=1

**HANDLE WITH CARE — read this before using it.**

This is the single most powerful fact we have with this audience, and the single
easiest to get wrong. The room may contain people who work on NavIC.

- **Frame it as national interest, never as criticism.** The correct framing:
  *during the constellation rebuild window, India is temporarily more dependent
  on a non-satellite fallback layer — which is exactly what we built.*
- **Always pair it with the recovery.** NVS-03 is ready for launch; NVS-04 and
  NVS-05 are in advanced realisation. Say that in the same breath. The point is
  the *transition period*, not a deficiency.
- **Never say** "NavIC is broken", "NavIC doesn't work", or anything a listener
  could repeat as a criticism of ISRO.
- **Suggested wording:** *"India's own constellation is mid-rebuild — the
  Government told Parliament in July that NavIC can't yet provide standalone
  positioning until the next satellites are up. That's precisely the window where
  a device-side fallback matters most, and it's why we built one that needs no
  satellite at all."*

Also `P-VERIFIED` (25 Mar 2026, PRID 2244977): eleven NavIC satellites launched,
eight functional, three broadcasting navigation signals; GAGAN operational;
discussions ongoing with AAI/MoCA on NavIC in air traffic management.
https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2244977&reg=1&lang=1

### 2. GPS spoofing up 193%, jamming up 67% (2025 vs 2023) — IATA
`P-VERIFIED`, released 9 Mar 2026.
https://www.iata.org/en/pressroom/2026-releases/2026-03-09-01/
One line, named global body, recent. Works for both judge types.

### 3. 122,607 flights, 365 airlines hit by GNSS interference in four months
Jan–Apr 2025 over Sweden, Finland, Poland, Lithuania, Latvia, Estonia. In April
alone **27.4% average** of flights in affected airspace disrupted, **>42% in some
areas**. Submitted jointly to ICAO by six states; ITU Radio Regulations Board
geolocated sources to Russian territory.
`SECONDARY` for the numbers (underlying doc ICAO A42-WP/553 could not be fetched)
https://news.err.ee/1609792437/svt-gps-disruption-has-affected-123-000-flights-in-the-baltic-region
**Say "as reported to ICAO", not "ICAO says."**

### 4. GPS signal-loss events up 220% between 2021 and 2024
> "The number of global positioning system signal loss events increased by 220%
> between 2021 and 2024" — Nick Careen, IATA SVP, in the joint EASA–IATA
> mitigation plan, 18 Jun 2025. `P-VERIFIED`
https://www.easa.europa.eu/en/newsroom-and-events/press-releases/easa-and-iata-outline-comprehensive-plan-mitigate-gnss

### 5. India sold 1,96,07,332 two-wheelers in FY2024-25 — 4.6× passenger vehicles
19.6 million units, up 9.1%, vs 43,01,848 passenger vehicles. SIAM, 15 Apr 2025.
`P-VERIFIED` https://www.siam.in/pressrelease-details.aspx?mpgid=48&pgidtrail=50&pid=579

**Use this annual-sales figure.** The cumulative "~250 million registered
two-wheelers" number is only `SECONDARY` (CEIC/Statista); the MoRTH Road
Transport Year Book stops at 2019-20. The claim "none of them ship with an
inertial navigation stack" is `INFERENCE` — label it as our reasoning.

---

## 1. The nuance that keeps us honest on the "fallback" claim

**Do not claim that inertial dead reckoning is aviation's designated GNSS
fallback. It is not.** EASA/IATA's 2025 plan names **conventional ground navaids**
(VOR/DME/ILS) as the backup to maintain: *"Maintain a backup for GNSS with a
minimum operational network of traditional navigation aids."* `P-VERIFIED`, same
EASA URL as fact 4.

Where the inertial-fallback consensus **is** solid is ground transport:

- **US DOT Complementary PNT Report to Congress** (15 Jan 2021, FY18 NDAA §1606):
  11 candidate technologies demonstrated, including one vendor using
  **map-matching + IMU + UWB**. Conclusion: the best strategy is to pursue
  **multiple technologies to promote diversity**. `P-UNFETCHED`
  https://www.transportation.gov/sites/dot.gov/files/2021-01/FY'18%20NDAA%20Section%201606%20DOT%20Report%20to%20Congress_January%202021.pdf
  *(Note: a US government report independently identified map-matching + IMU as a
  complementary PNT approach. That is useful validation of our architecture.)*
- **u-blox** markets Automotive Dead Reckoning (ADR) and Untethered Dead Reckoning
  (UDR) to extend positioning "deep into tunnels, multi-level car parks, and
  narrow urban canyons." `P-UNFETCHED` — **verify wording before quoting.**
  https://www.u-blox.com/en/technologies/udr-untethered-dead-reckoning
- u-blox states ADR outperforms UDR for outages **longer than about a minute**,
  because ADR has wheel-tick input. **This is an honest framing of our own
  limitation:** we are doing UDR-class work on a phone, so our credible claim is
  **short-to-medium outages**. Say that.

**The line that uses all of this:**
> *"Aviation's fallback is ground navaids. Automotive's fallback is inertial dead
> reckoning — but it needs wheel-tick sensors the vehicle has to provide. Neither
> exists for a rider on a two-wheeler with a phone in their pocket. That's the gap
> we're filling."*

## 2. Policy / sovereignty (for the strategic slide)

- **US** — Executive Order 13905, *Strengthening National Resilience Through
  Responsible Use of PNT Services*, 12 Feb 2020. `P-VERIFIED`
  https://www.federalregister.gov/documents/2020/02/18/2020-03337/strengthening-national-resilience-through-responsible-use-of-positioning-navigation-and-timing
  DHS S&T *Best Practices for Resilient PNT Supporting Critical Infrastructure*,
  25 Feb 2025. `P-UNFETCHED`
- **EU** — Galileo **OSNMA declared operational 24 July 2025**; the Commission
  states it "significantly enhances protection against spoofing, a growing threat
  as interference events increase worldwide." Since Dec 2025 all newly registered
  EU trucks and buses need a Smart Tachograph v2 with OSNMA. `P-VERIFIED` (date +
  quote), tachograph mandate `SECONDARY`
  https://defence-industry-space.ec.europa.eu/galileos-osnma-authentication-service-now-operational-2025-08-25_en
- **UK** — *Government Policy Framework for Greater PNT Resilience*, 18 Oct 2023:
  National PNT Office in DSIT, a cross-Government PNT Crisis Plan for GNSS loss,
  a National Timing Centre (£14m). `SECONDARY / parliamentary record`
  https://hansard.parliament.uk/Commons/2023-10-18/debates/23101820000004/PositionNavigationAndTimingResilienceGovernmentPolicyFramework
- **India** — NavIC L1: Qualcomm announced support in select Snapdragon platforms
  from H2 2024, jointly with ISRO. Manish Saxena, Director, ISRO Satellite
  Navigation Programme Office: *"The L1 signals will be a critical next step by
  enabling better performance of location-based services in the consumer
  segment."* `P-VERIFIED`
  https://www.qualcomm.com/news/releases/2023/12/qualcomm-announces-support-for-india-s-navic-satellite-navigatio

**One-line framing:** *"Every major space power has written a resilient-PNT
policy in the last five years. They all say the same thing: don't depend on one
signal. We're the device-side layer of that answer."*

## 3. Why Google Maps doesn't already solve this

Google Maps' tunnel navigation uses **Bluetooth beacons physically installed in
the tunnel** (rolled out Jan 2024, inherited from Waze's 2016 programme).
It is **off by default**, **Android only**, and deployments listed are New York,
Paris, Chicago, Rio, Oslo, Sydney, Brussels, Boston, Mexico City.
**No Indian city appears in any list found.** `SECONDARY`
https://9to5google.com/2024/01/15/google-maps-tunnel-navigation-beacons/

**This is a strong competitive line, delivered carefully:**
> *"Google's answer to tunnels is Bluetooth beacons that someone has to physically
> install in the tunnel. It's off by default, Android-only, and no Indian city is
> on the deployment list. Ours needs nothing installed anywhere."*

Say "as reported by trade press" — no official Google support page was located.
No Apple statement on tunnel navigation was found: `NOT VERIFIED`.

## 4. GNSS-denied surface area in India is growing

From the PIB Backgrounder *"India's Tunnels: Engineering Marvels Beneath the
Surface,"* 14 Jan 2026. `P-VERIFIED`
https://www.pib.gov.in/PressReleasePage.aspx?PRID=2214471&reg=3&lang=1

- **Atal Tunnel — 9.02 km** under Rohtang; world's longest highway tunnel above 10,000 ft
- **Tunnel T50 (USBRL) — 12.77 km**, Khari–Sumber
- **Sonamarg / Z-Morh — 12 km** project (6.4 km main tunnel), ₹2,700 crore, ~1,000 vehicles/hour
- **Banihal–Qazigund — 8.45 km** twin-tube; **Dr Syama Prasad Mookerjee Tunnel — 9 km** twin-tube
- **Zojila — over 30 km**, on track for **2028**; will be India's longest road tunnel
- **Mumbai–Ahmedabad HSR — 4.8 km undersea tunnel** breakthrough achieved
- **Kolkata's first underwater metro tunnel** opened 2024 (Esplanade–Howrah Maidan, under the Hooghly)

Maritime GNSS disruption, `SECONDARY`: >1,100 vessels experienced GPS/AIS
interference in the Middle East Gulf within 24 hours; container ship **MSC
Antonia grounded near Jeddah on 10 May 2025** attributed to GPS jamming.
https://windward.ai/blog/gps-jamming-disrupts-1100-ships-in-the-middle-east-gulf/

---

## 5. BANNED — could not be verified, must never appear on a slide

- **MeitY NavIC smartphone mandate as a formal notification.** Only ministerial
  statements to press exist; no gazette notification or MeitY order was found.
  Say *"the Government has publicly stated an intent to mandate NavIC support"*
  and cite Business Standard as `SECONDARY`. **Do not call it a legal mandate.**
- "60+ handset models support NavIC"
- "331 km road tunnel network by 2026-27"; the 42-completed / 57-under-construction
  tunnel counts
- India metro "1,076.585 km operational across 26 cities"
- Any Apple statement on tunnel navigation
- Verbatim EASA SIB 2022-02 text naming inertial navigation as the fallback
- Swedish airspace interference counts (55 → 733)
- Cumulative registered two-wheeler count (use the SIAM annual sales figure)

**Rule:** if a number is not in this file with a `P-VERIFIED` or `SECONDARY`
label, it does not go in the deck. Every number used from here must be entered
into `CLAIMS.json` with `confidence: external` and its URL.
