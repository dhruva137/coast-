# 00 — The Design Thesis

**Read this before any other file in `design_v3/`. It explains why the product
currently feels wrong, and the single decision that fixes it.**

---

## A. Why it looks like "shit" right now — the actual diagnosis

It is not a colour problem, a font problem, or a "needs more polish" problem.

**It is one structural mistake: we are building two completely different products
and styling them as one.**

| | **COAST Navigator** (phone) | **COAST Command** (laptop web) |
|---|---|---|
| Who uses it | A rider or driver, moving, glancing for 1 second | An operator or analyst, seated, studying for minutes |
| Its job | **Hide** information. Show one thing: where am I. | **Reveal** information. Show many phones, paths, metrics, proof. |
| Attention budget | ~1 second, peripheral vision, possibly in sunlight | Sustained, focused, indoor |
| Design language | Google Maps / Uber — map-first, near-zero chrome, one primary action | Linear / Vercel / Stripe — dense, structured, information-rich |
| Success feels like | *"I didn't have to think."* | *"I can see everything."* |
| Failure looks like | A dashboard on a phone | A phone app stretched to 1920px |

**Right now both are drifting toward the middle** — the phone has too many panels
and readouts, and the web console has too little structure. Neither reads as a
finished product because neither has committed to what it is.

**The fix is a decision, not a redesign: commit each surface fully to its own
species, and let them share only a colour palette and a logo.** Everything in
this folder follows from that.

---

## B. The design principles (in priority order — when two conflict, the earlier wins)

### 1. One thing per screen
Every screen answers exactly one question. Navigator's Drive screen answers
"where am I?" — nothing else. If a second question needs answering, it belongs
behind a gesture, in a sheet, or on another screen. **Delete before you arrange.**

### 2. Motion explains, it does not decorate
Every animation must teach something: where a thing came from, where it went, or
that a state changed. The splash should *become* the map, not play and then cut.
A marker should *glide* between fixes so the eye tracks continuity. Animation
that says nothing is noise, and noise is what makes an app feel cheap.

### 3. Honest states are designed states
Loading, empty, error, degraded, and permission-denied are not afterthoughts —
they are where trust is won or lost. A missing gyroscope must produce a designed,
explanatory screen, not a crash or a frozen dot. **A product that explains its own
failure feels more trustworthy than one that never appears to fail.**

### 4. Show the machine working
This is the one place we deliberately *break* minimalism. Our entire pitch is
"this is real, measured, and honest." So the interface must expose its own
mechanism — sensor rates, mode transitions, what the filter is doing — as a
deliberate, beautiful surface (Navigator's Vehicle Check, Command's telemetry).
It is the difference between a demo and an instrument.

### 5. Typography and space do the work, not colour
One accent (`#00E0A4`). Blue reserved exclusively for the GNSS track. Everything
else is greyscale and spacing. Restraint is what reads as premium; a colourful
interface reads as a student project regardless of how good the colours are.

### 6. Nothing is instant, nothing is slow
Every state change is animated at 150–300 ms with a natural easing curve.
Instant changes feel like a page reload; anything past ~400 ms feels broken.

---

## C. What "Apple-level" actually means here

The user asked for Steve Jobs–level design. That is frequently misread as "more
animation." It means the opposite. Concretely, four things:

**1. Ruthless subtraction.** The Drive screen should have *fewer* elements than
it does now. Every element that survives must justify its existence against
"does a moving driver need this in one second?" Most do not. Move them into the
diagnostics sheet.

**2. One continuous motion from launch to use.** The logo mark appears, draws
itself, and *becomes* the map — one unbroken gesture with no cut, no flash, no
white frame. This is the single highest-impact change available to the phone app,
because it is the first three seconds and it sets every subsequent judgement.

**3. The details nobody names but everyone feels.** Consistent 8dp spacing grid.
Optical rather than mathematical centring. Matched corner radii. Text that never
reflows when a number changes (tabular figures — a speed readout that jitters
because "1" is narrower than "8" is the difference between cheap and expensive).
Icons on a single grid with one stroke weight.

**4. The product has a point of view.** Ours: *you should never have to think
about whether your position is trustworthy — but if you ask, we will show you
everything.* That is why Vehicle Check exists and why we hide the broken
confidence radius. A product with a point of view feels designed; a product that
exposes every option feels assembled.

---

## D. The three moments that decide the demo

A judge forms their entire impression in three moments. Design these first,
obsessively, and the rest can be merely good.

**Moment 1 — the first three seconds of the app.**
Cold launch → logo animates → becomes map → a live position. No white flash, no
permission wall, no jank. This is the whole "is this a real product?" judgement,
and it is made before a single word is spoken.

**Moment 2 — the QR pairing.**
Judge scans a code on the laptop screen with their own phone; **their** device
appears on the dashboard within a second, named, with a live dot. The reason this
is so powerful: it is *their* phone, *their* movement. It converts a passive
viewer into a participant. Nothing else in the demo is personal in this way.

**Moment 3 — the blackout.**
Airplane mode on, in front of them. The dot keeps moving. The mode pill flips
GNSS → IDR. This is the product thesis in one visual beat.

Everything else — the settings, the theming, the login, the figures — is
supporting cast. **Budget effort accordingly: if time is short, these three
moments are the last things to cut, not the first.**

---

## E. The tension we must resolve, and how

There is a genuine conflict between two things we want:

- **F8 privacy claim:** *"No user data leaves the device."*
- **The new fleet dashboard:** phones uploading live position to a hosted server.

If we are careless, the dashboard destroys our strongest privacy asset.

**The resolution — and it makes the story better, not worse:**

These are **two separate products with two separate data postures**, and we say so
plainly:

> **COAST Navigator** — the navigation product. Fully on-device. Nothing leaves
> the phone. This is the ISRO problem statement's deliverable.
>
> **COAST Command** — the fleet product. Tracking is the entire *point*: a
> logistics operator wants to know where their truck is. It is a separate opt-in
> surface, and pairing is an explicit act — you scan a QR code, you consent to
> exactly this, and you can see and delete everything we hold.

Then we add the move that turns this from a liability into an F8 win:
**a "What we know about you" panel** on the dashboard, showing every field
received from that device, plus a one-click **Delete my device and all its data**.
Live. In front of the judge.

Most teams either avoid the privacy question or make an unverifiable claim. We
will be the team that *shows the data we hold and deletes it on request*, on
stage. See `06_PRIVACY_MODEL_FOR_TRACKING.md`.

---

## F. What this folder contains

| File | What it decides |
|---|---|
| `00_DESIGN_THESIS.md` | This file. The two-products split and the principles. |
| `01_PS_COMPLIANCE_AUDIT.md` | Every explicit problem-statement requirement vs what we actually have. **Read second.** |
| `02_PLATFORM_ARCHITECTURE.md` | Hosting, pairing, QR, LAN-vs-internet, domain, auth. All free. |
| `03_APP_DESIGN_SPEC.md` | Navigator: splash, icon, theming, Vehicle Check, settings, stability. |
| `04_DASHBOARD_DESIGN_SPEC.md` | Command: fleet view, live training, figures, layout system. |
| `05_LIVE_TRAINING_VISUALIZATION.md` | The per-epoch trajectory idea — the best visual we are not yet using. |
| `06_PRIVACY_MODEL_FOR_TRACKING.md` | Resolving §E without weakening F8. |
| `07_DEMO_CHOREOGRAPHY.md` | The QR-pairing demo, minute by minute, with fallbacks. |
| `08_STRETCH_DOMAINS.md` | Aviation, logistics security, and where the PS boundary is. |

---

## G. The one-paragraph version

> The app feels wrong because a navigation app and an operations dashboard are
> opposite design problems and we have been building them as one. Split them:
> Navigator hides everything except your position and is judged on its first three
> seconds; Command reveals everything and is judged on information density. Share
> only the palette and the mark. Then design three moments obsessively — the
> launch animation, the QR pairing where a judge sees *their own phone* appear,
> and the blackout — because those three are what anyone will remember. And turn
> the tracking-versus-privacy tension into our best privacy moment by showing the
> judge exactly what we hold about their device and deleting it on request, live.
