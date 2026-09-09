# 07 — Demo choreography with QR pairing

**The new demo mechanic:** a judge scans a QR code with their own phone, and
**their** device appears live on the big screen. Then we black it out and their
dot keeps moving.

This is a significant upgrade on the previous demo, because it makes the judge a
*participant* rather than a viewer. It is also more fragile. This file makes it
robust.

---

## A. Why the QR pairing is worth the risk

The old Act 1 was: we hand the judge our phone. Good.
The new Act 1 is: **the judge's own phone appears on the screen, moves when they
move, and keeps moving when we cut the signal.**

The difference is ownership. A judge watching *their* dot cannot dismiss it as a
canned demo, because they are holding the input device. That is the single most
persuasive thing we can construct.

**But it must never be the only path.** See §D.

---

## B. Physical setup (before judges arrive)

| Item | Why |
|---|---|
| **Laptop running Windows Mobile Hotspot** | Fixed IP `192.168.137.1`, immune to AP isolation. See `02_PLATFORM_ARCHITECTURE.md` §C. |
| `tracker_server.py` running on `192.168.137.1:8787` | The demo's spine. Started and verified before 8:45. |
| Dashboard open on `/fleet`, projected | What judges see when they walk up |
| **2–3 phones pre-installed and already paired** | The critical path. Judge self-install is a bonus. |
| Printed card: hotspot name + password + the pairing QR | If the projector fails, the card still works |
| Backup video on laptop, phone, and USB | Act 1 fallback |
| All phones charged, airplane mode ready | |

**Verify the whole chain at 9:00 and again at 12:45.** The 12:45 check matters —
laptops sleep, hotspots drop, and Round 2 starts at 1:00.

---

## C. The sequence (target 4 min, hard cap 5)

### ACT 0 — Pairing (30 s) · *new, and the best opening we have*

1. Dashboard is projected, showing Fleet with **zero devices** and a large QR —
   the empty state *is* the invitation. (`04_DASHBOARD_DESIGN_SPEC.md` §G.)
2. *"Scan that with the phone in your hand."* Hand a judge a pre-installed phone,
   or let them use their own if they installed it.
3. Their device appears on the map, named, with a live dot. **The pairing status
   animates from "0 devices" to "Judge-1 connected."**
4. *"Walk a few steps."* The dot moves.

**Then the consent beat — do not skip it, it is fifteen seconds and it wins F8:**

> *"Before we go on — that pairing shared exactly one thing: position. Here's
> every field we hold about your phone."* *(open the panel)* *"No device ID, no
> account, nothing else. And this deletes all of it."*

Do not press delete yet — you need the device for Act 1. Press it at the end.

### ACT 1 — The blackout (60 s) · *the thesis*

1. *"Now watch what happens when GPS dies."*
2. **Airplane mode on, in front of them.**
3. The dot keeps moving. On the dashboard, **the track changes colour** — blue
   GNSS becomes teal IDR. The timeline logs `GNSS → IDR`.
4. *"No GPS. No internet. That position is coming from the phone's motion sensors
   and the road map — nothing else."*
5. **Turn airplane mode off** — show the reacquisition. The PS says "and
   vice-versa" explicitly, and most teams only ever demo one direction.

### ACT 2 — The insight (90 s) · *scores F1*

Delivered by the estimator owner, not the leader. Script in
`win_tuning/F9_PRESENTATION.md` §B — the perfect-gyroscope 55% result, the 0.98×
post-hoc control, the 2.02×, then the volunteered along-track limitation.

### ACT 3 — The proof (60 s)

1. **The claim linter:** `python tools/verify_claims.py --demo-failure`. Build
   fails on a planted number. 15 seconds.
2. **The training panel**, if time: press Train, watch the trajectory converge
   epoch by epoch (`05_LIVE_TRAINING_VISUALIZATION.md`). **Pause and let it run.**
3. **Delete the judge's device** from the dashboard, closing the privacy loop.

### THE CLOSE (20 s)

> *"Nineteen million two-wheelers sold in India last year. Almost none have any
> navigation fallback, because the fallback the industry sells needs wheel sensors
> the vehicle has to provide. We built one that needs nothing but the phone
> already in your pocket."*

---

## D. The fallback ladder — rehearse every rung

Each rung is a complete demo. **Never debug on stage; step down a rung.**

| Rung | If | Do |
|---|---|---|
| **1** | Everything works | Judge's own phone, live pairing |
| **2** | Judge won't/can't install | **Our pre-installed phone**, same flow. *This is the expected normal case.* |
| **3** | Pairing fails (hotspot, network) | Run the demo **on the phone alone** — the app's own map. Drop the dashboard entirely. |
| **4** | App crashes or phone dies | **Backup video.** Under 5 seconds to switch. |
| **5** | Projector dead | Pitch from the phone screen; printed card in hand. All six know the script without slides. |

**The critical drill:** stepping from rung 1 to rung 3 must take under five
seconds and must not be narrated as a failure. Say *"let me show you on the phone
directly"* and continue. Judges notice recovery far more than they notice the
fault.

**Rehearse rung 3 specifically.** It is the most likely one and the one nobody
practises.

---

## E. Multi-phone — use it, but keep it second

If two or three judges pair simultaneously, the Fleet view earns its keep: three
coloured dots, three tracks, one timeline. Narrate it as the logistics use case:

> *"This is what a fleet operator sees. Three vehicles, live. Where a line turns
> teal, that vehicle was somewhere GPS couldn't reach — and every other system
> loses it there. If that were a truck carrying something valuable, that teal
> stretch is exactly where you'd want visibility."*

**But do not open with multi-phone.** One judge, one dot, one blackout is a
cleaner story. Add devices only if the room is engaged and time allows.

---

## F. What can go wrong, ranked by likelihood

1. **Judges decline to install an APK.** *Very likely.* → Pre-installed phones.
2. **Venue wifi has AP isolation.** *Likely.* → Laptop hotspot, always.
3. **Install flow takes too long** (unknown sources + Play Protect ≈ 3 min).
   → Pre-installed phones; never spend Round 2 time on an install.
4. **Laptop sleeps between rounds.** → Re-verify at 12:45. Disable sleep.
5. **Live training subprocess fails.** → One-click switch to the recorded replay
   (`05` §F).
6. **Someone contradicts a teammate on a number.** *Most damaging.* → The
   five-number drill in `win_tuning/F10_TEAMWORK.md` §G.

---

## G. Pre-flight checklist

**Before 8:45**
- [ ] Hotspot up; `tracker_server.py` running on `192.168.137.1:8787`
- [ ] 2–3 phones installed, paired, charged, airplane-mode tested
- [ ] Dashboard projected on `/fleet`; QR renders
- [ ] Backup video on laptop + phone + USB
- [ ] Printed card: hotspot credentials + pairing QR
- [ ] Laptop sleep disabled; charger connected
- [ ] `verify_claims.py --demo-failure` tested
- [ ] Figures pre-generated; training replay JSON recorded

**At 12:45 (before Round 2)**
- [ ] Hotspot still up, server still responding
- [ ] Phones still paired and charged
- [ ] Dashboard reloaded and showing live
- [ ] All six present, formal dress, phones on silent
