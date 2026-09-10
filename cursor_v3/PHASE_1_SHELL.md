# Phase 1 — Shell, identity, and the design system

**The complaint:** *"the landing page is not cool. This command center should
look like a login or something, not just like a demo. The UI is very terrible."*

**The diagnosis:** the console currently opens straight into a working tool with
no threshold. There is no moment that says *you have arrived somewhere*. Real
operations software has a front door — and a front door is also the natural place
to put the product's identity, its claim, and its proof.

**Target:** a judge glances at the screen from across the room and thinks
*"that's a product."* Before they read a single word.

Everything in `design_v3/00_DESIGN_THESIS.md` applies. The console is an
**operations console** — dense, structured, dark, information-first. Not a phone
app stretched wide, and not a marketing page.

---

## 1.1 — The design system (do this first; everything else depends on it)

Extract the current inline CSS into a real token system and serve it as a static
file, not a Python string. Create `web/static/` and serve it from the console
with correct MIME types and `Cache-Control: no-store`.

**Tokens** — define once, use everywhere. No literal colours in components.

```
--bg:#07090D  --panel:#0C1016  --panel2:#11161E  --line:#1C232D
--text:#E8EDF2  --dim:#8B97A6  --faint:#5A6673
--accent:#00D4AA        the one accent. COAST teal.
--gnss:#4A9EFF          reserved EXCLUSIVELY for GNSS. Never decorative.
--warn:#FFD166  --bad:#FF6B6B
```

**Type scale:** exactly four sizes — 32 / 20 / 14 / 12. One family (system
stack). **Tabular figures on every number that updates** — a metric that changes
width as digits change is the single most common tell of amateur software.

**Space:** 8px grid, no exceptions. Panel padding 24. Related items 8 apart,
unrelated groups 24.

**Motion:** 150–250 ms, ease-out. Values animate; layout never shifts. Nothing
bounces, nothing spins, nothing pulses without meaning.

**Deliverables:** `web/static/tokens.css`, `web/static/components.css`,
`web/static/app.js`. The console page becomes a thin HTML shell that links them.
This also makes every later phase easier to work on in parallel.

## 1.2 — The front door

A full-screen entry view at `/`, before the console proper.

**It is not a marketing page and not a form dump.** It is a *threshold*: identity,
one claim, one proof, one way in.

Layout — one screen, no scrolling:

```
                    ◆  COAST
              GNSS-DENIED NAVIGATION

     Navigation that keeps working when GPS doesn't.

     ┌────────────────────────────────────────────┐
     │  2.02×          55%            98×          │
     │  lower median   a perfect      the 200 Hz   │
     │  position error gyro still     edge         │
     │  vs naive DR    fails          requirement  │
     └────────────────────────────────────────────┘

              [ Enter Command Console ]
                    Operator sign-in

     SIH 2026 · PS 26168 · ISRO / Dept. of Space
```

Requirements:
- The mark animates in once, briefly (≤600 ms), then rests. Reuse the geometry
  from `android/.../res/drawable/ic_launcher_foreground.xml` so the app and the
  console share one identity — arrow plus fading breadcrumb trail.
- The three numbers come from `/api/claims`. **Never hardcode them.** If the
  registry cannot be read, show the panel empty with an error, not remembered
  values.
- Subtle live background: the COAST/free-DR trajectory pair drawn faintly and
  slowly, from real committed data. Not particles, not noise — *our actual
  result*, used as texture.
- Works with no network. No CDN, no web font.

## 1.3 — Operator sign-in

The user asked for a login. Build it as an **operator session**, not user accounts.

**Design decision, and hold it:** we do not create user accounts, and we do not
add Google Sign-In. Reasons — an unverified Google OAuth app shows a "Google
hasn't verified this app" warning *in front of judges*, testing-mode tokens
expire in 7 days, and verification takes weeks. More importantly, our F8 privacy
position is *"we hold no identity, so there is nothing to leak."* Accounts
weaken a criterion we currently score well on.

**Build instead:**
- A single operator passcode, **Argon2id-hashed** (or PBKDF2-HMAC-SHA256 with
  ≥600k iterations if argon2 is unavailable — stdlib `hashlib.pbkdf2_hmac`).
  Never store or compare a plaintext passcode.
- Hash read from `web/operator.txt` (gitignored) or the `COAST_OPERATOR_HASH`
  env var. If neither is set, the console runs in **open mode** with a visible
  banner saying so — do not invent a default password.
- On success, an HttpOnly, SameSite=Strict session cookie, random 32 bytes,
  with an idle timeout.
- Constant-time comparison (`hmac.compare_digest`). Rate-limit attempts.
- A visible **Sign out** in the header, and the operator name in the status rail.

**Add `web/auth.py`** with tests in `web/test_auth.py`: wrong passcode rejected,
right one accepted, cookie required on protected routes, timing-safe compare,
rate limiter trips.

**Do not gate `/pair` or `/ingest`** — phones must pair without an operator
session, and those already have their own token.

## 1.4 — The shell

Once signed in:

- **Header:** mark, operator, live status pills (server / devices / training /
  offline-capable), sign-out. Pills must not wrap into a tall stack on narrow
  screens — collapse to icons under 900px.
- **Left icon rail** instead of the current top tabs: Fleet · Engine · Training ·
  Evidence · Sessions. Icons with labels, 56px wide, current item marked with the
  accent. Frees vertical space and reads as an operations tool rather than a
  website.
- **Command palette** on `Ctrl/Cmd-K`: jump to a view, start training, mint a
  pairing code, sign out. Cheap to build, and it reads as serious software the
  instant a judge sees it.
- **Keyboard shortcuts:** `1`–`5` for views, `?` for a shortcut sheet.
- **Connection state is always visible.** If the backend goes away, the header
  says so within 2 s and the views show their last-known state clearly marked
  stale — never silently frozen.

## 1.5 — Responsive and projector-safe

A projector may be 4:3, and a judge may open this in a half-width window.

- Breakpoints at 1180px and 640px. Under 1180 the side rails stack under the
  main panel instead of crushing it. Under 640 the header compacts.
- **Presentation mode** (`P`): hides the rail and chrome, scales type up ~25%,
  leaves only the current view. For projecting to a room.
- Verify at 1920×1080, 1440×900, 1280×1024 (4:3) and 1024×768. Nothing clipped,
  no horizontal page scroll, no overlapping text.

## 1.6 — Empty, loading, error, stale

Design all four for every view. A judge *will* see empty states, because nothing
is paired when they walk up.

- **Empty is the call to action.** The empty fleet view is the pairing QR at
  full size with "Scan this to put your phone on the map."
- **Loading reserves final layout.** Skeletons at the exact size of the content
  they replace. Nothing may shift when data lands — this is what the earlier
  "figures popping up randomly" complaint actually was.
- **Errors name the thing.** *"Could not read
  `lab/stress/results/mapfilter/report.json`."* Never a generic failure, never a
  remembered number.

---

## Acceptance

- [ ] `web/static/{tokens,components,app}.{css,js}` exist; no literal colours in components
- [ ] Front door renders in one screen, no scroll, numbers from `/api/claims`
- [ ] Registry unreadable → front door shows an error, not remembered numbers
- [ ] Passcode hashed with Argon2id/PBKDF2, constant-time compare, rate-limited
- [ ] No hash configured → open mode with a visible banner, no default password
- [ ] `/pair` and `/ingest` reachable without an operator session
- [ ] `web/test_auth.py` passes
- [ ] Icon rail, command palette, keyboard shortcuts, presentation mode
- [ ] Verified at 1920×1080, 1440×900, 1280×1024, 1024×768
- [ ] Every view has designed empty / loading / error / stale states
- [ ] Whole console cold-starts with no network
- [ ] `python web/test_console_routes.py` still green
