# SIH 26168 — current progress

**Updated:** 4 Sep 2026  
**Repo:** https://github.com/dhruva137/SIH-2026  
**PS:** ISRO — AI-ML Intelligent Dead Reckoning (SIH26168)  
**App version:** Android IDR **0.3.0**

## One-line status

Research prototype is built and demoable; **field scooter proof is still the blocker**. Teammate **RECORD APK v0.3.0** is ready for campus loop collection.

## What is done

| Area | Status | Notes |
|---|---|---|
| Web console + Evidence Room | Done | `npm run dev` → http://localhost:26168 |
| Lean solver + InEKF + graph / vector locator | Done | `core/ts` (+ C++ port) |
| IO-VNBD stress + axis audit | Done | Yaw = `-GYROSCOPE Pitch`; alignment **GREEN** |
| Injected-lean claim | Done | Lean-aware **3.84%** vs car-style **10.56%** (synthetic, not field) |
| Prototype gate | Pass | `RESEARCH_PROTOTYPE_PASS` |
| Deployment gate | **Fail** | Expected until real TW logs + road-speed ISRO passes |
| Android RECORD / NAVIGATE | Done | Foreground logging, loop mark |
| **Sessions + quality gate + zip share** | **Done (v0.3.0)** | CHECK / RENAME / DELETE / ZIP; auto `quality.json` on stop |
| Unit tests (Android) | **8/8 pass** | LeanSolver + QualityGate |
| Debug APK built | Done | `android/dist/IDR-0.3.0-debug.apk` (local; `*.apk` gitignored) |

## Honest evidence (do not overclaim)

| Gate | Colour | Meaning |
|---|---|---|
| Alignment (IO-VNBD) | GREEN | Gyro axis mapping validated |
| Real car open-loop 60 s | RED | Does not meet ISRO &lt;10% / &lt;100 m/km |
| Real car map-aided 60 s | YELLOW | Only weak / low-speed competitive cases |
| Injected lean | GREEN | Sim claim only |
| Real two-wheeler field | **RED** | **No qualifying scooter/bike logs yet** |

Canonical detail: `lab/stress/results/CURRENT_VERDICT.md`

## Benchmark we must beat (ISRO)

- Drift **&lt; 10%** of distance travelled  
- **&lt; 100 m** error over **1 km** at **60 km/h**  
- **10 Hz** on-device  

Measure via **loop closure** and **forced GNSS outage replay** (GPS logged for truth; deny in software) — not by eyeballing Maps with GPS off.

## Next actions (team)

1. Install `android/dist/IDR-0.3.0-debug.apk` (or rebuild with `android/build-apk.bat assembleDebug`).
2. Collect **≥10 handlebar loop rides** (return to chalk mark; aim for quality **KEEP**).
3. Add **3–5 underpass / basement** outage rides.
4. Upload session zips → replay drift % in lab / Evidence Room.
5. Keep proposal IO-VNBD plots honest; regenerate if needed after axis fix.

## How teammates use the APK

1. RECORD → set rider / vehicle / **handlebar** → START (GPS **on**).  
2. MARK LOOP CLOSURE at start.  
3. Ride ≥ ~90 s / ≥150 m → STOP → read KEEP/RETRY/FAIL.  
4. SESSIONS → RENAME / ZIP / share.  

See `android/dist/README.md`.

## Build notes

- Rebuild: `android\build-apk.bat testDebugUnitTest assembleDebug`  
- Needs JDK 17 + Android SDK (`android/local.properties` is local-only).  
- APKs are **not** committed (`*.apk` ignored); build locally or share via Drive.
