# 02 — Platform Architecture (all free, verified 9 Sep 2026)

**The goal:** a judge opens a public website, downloads the APK, scans a QR code
with it, and their phone appears live on the dashboard. Multiple phones at once.
No paid service anywhere.

**Everything below was verified against vendor documentation on 9 Sep 2026.**
Free tiers change constantly; several widely-repeated recommendations are now
wrong (see §A).

---

## A. Five things that would have broken this, found before we built it

1. **Hugging Face Spaces is no longer free for this.** Official docs: Gradio and
   Docker Spaces *"require a paid plan to create: PRO for personal accounts."*
   Only **Static** Spaces remain free. Most guides still say otherwise.
2. **Render Free spins down after 15 minutes idle and takes ~1 minute to wake.**
   If a judge is the first visitor, they wait a minute looking at nothing. Fatal
   on stage unless pre-warmed.
3. **Vercel Hobby caps every connection at 300 s.** An SSE/WebSocket feed will
   drop every five minutes. Reconnect logic becomes mandatory.
4. **Fly.io requires a credit card for all organisations.** Railway's free tier is
   now a $5 one-time 30-day trial. **Glitch shut down hosting on 8 Jul 2025.**
5. **Cloudflare Pages has a 25 MiB per-file limit** — it *cannot* host our 68 MB
   APK. Their own docs redirect you to R2.

---

## B. The recommended architecture

| Layer | Choice | Why |
|---|---|---|
| Public site + dashboard | **Cloudflare Pages** on `paper2anything.com` | Unlimited bandwidth, free automatic TLS, 500 builds/mo, no card |
| APK download | **GitHub Releases** | 2 GiB per file, no interstitial, no login, direct mobile link |
| Position ingest — **PRIMARY** | **Laptop running `tracker_server.py` on a Windows Mobile Hotspot at `http://192.168.137.1:8787`** | No internet dependency, no cold start, immune to AP isolation, deterministic IP |
| Position relay — secondary | **Render Free** running the same file | Only free tier that runs our existing code as-is |
| ML training | **Laptop only** | No free tier has the CPU or the duration — and it is the honest story |
| QR generate / scan | `qrcode` (JS, client-side) / **ML Kit bundled model** | Free, offline, no API key |
| Auth | QR session token + one Argon2-hashed demo passcode | See §F |

**Our existing `web/tracker_server.py` is 331 lines of stdlib `http.server`**
(`POST /ingest`, `GET /feed`, binds `0.0.0.0:8787`). That is very portable — it
runs unmodified on a laptop or on Render. It is *not* ASGI, so any serverless
target would need a rewrite. Do not rewrite it.

---

## C. The pairing design — the important part

**The QR encodes a plain HTTPS URL carrying the token and *both* endpoints:**

```
https://paper2anything.com/pair
  ?s=<32-char-session-token>
  &lan=http://192.168.137.1:8787
  &relay=https://<render-app>.onrender.com
```

**The app scans it, then races both endpoints with a ~1.5 s timeout, pins
whichever answers first, and re-races after three consecutive failures.**

That single mechanism is what makes the demo robust: judges join the laptop's
hotspot and get the LAN path; any phone that can't or won't join silently falls
back to the relay over its own mobile data. **Same QR, same code path, two
independent networks, nothing to change on stage.**

Why a URL rather than a JSON blob or an App Link: a URL degrades gracefully — a
generic camera app can open it and land on a "get the app" page. A JSON blob
cannot. An Android App Link would need a verified `assetlinks.json` and adds a
failure mode for no benefit, since our own app does the scanning.

**Token semantics — copy WhatsApp Web / Google device pairing:** the token is a
short-lived one-time *nonce*, not a credential. The phone's first `POST /ingest`
is what activates the session and binds it. Expire in ~10 minutes.

### Why the hotspot is primary — AP isolation

**AP isolation (client isolation) is the default on most guest wifi.** It lets
clients reach the gateway and the internet but **blocks all device-to-device
traffic**. It would silently kill phone→laptop with a connection *timeout*, not
an error message — and you cannot test for it until you are in the room.

**Windows Mobile Hotspot always places the host at `192.168.137.1`.** Fixed,
memorable, printable, and hotspots do not apply client isolation. This removes
the single largest demo risk and costs nothing.

**Do this:** laptop runs the hotspot, phones join it, QR carries that fixed
address. Print the hotspot name and password on a card.

---

## D. The APK download path

**GitHub Releases.** 2 GiB per file, up to 1000 assets, no documented bandwidth
limit, direct link with no interstitial or login. Cloudflare R2 is a fine
alternative (10 GB, egress free) but is unnecessary.

**Avoid Google Drive** — files over ~100 MB show a virus-scan interstitial and
direct links are unstable.

**Ship an arm64-only release APK** for the download link (see
`03_APP_DESIGN_SPEC.md` §J) — roughly half the size, covers essentially every
modern phone.

### What a judge actually taps

Download in Chrome → tap the file → *"your phone is not allowed to install
unknown apps from this source"* → Settings → **Allow from this source** → back →
**Install** → Play Protect may show a second scan prompt → **Install anyway**.

Two separate gates. **Budget three minutes per judge, and expect some to decline.**

**Therefore: have 2–3 phones pre-installed and ready.** The QR pairing demo should
work with *our* phones by default; a judge installing it themselves is a bonus,
not the critical path.

### One timing check that matters

Google's developer-verification requirement for sideloaded apps begins
**30 September 2026 — in Brazil, Indonesia, Singapore and Thailand only. India is
not in the first wave**; global follows in 2027. **The 11 Sep India demo is
unaffected.** For later, a limited-distribution account is free, needs no
government ID, and covers up to 20 devices.

---

## E. paper2anything.com — the setup

**Do the DNS step now.** Nameserver propagation can take hours, and it is the one
part that cannot be rushed on the day.

1. Add `paper2anything.com` as a site in Cloudflare; change the registrar's
   nameservers to the two Cloudflare provides.
2. Connect the GitHub repo to Cloudflare Pages. Build command `npm run build`,
   output directory `web/dist`.
3. Pages → Custom domains → add `paper2anything.com` and `www`. Because DNS is
   already at Cloudflare it writes the records itself (CNAME flattening handles
   the apex) and issues the certificate. HTTPS is free and automatic.

**Is it required for Friday? No.** It is a strong touch for the finals and a nice
one for Friday if DNS is already propagated. The demo must not depend on it —
everything works from the laptop hotspot regardless.

---

## F. Authentication — the opinionated recommendation

**Skip Google OAuth. Build a session token plus one shared passcode.**

Google Sign-In is free, but for a demo it is a liability:
- An unverified app shows a **"Google hasn't verified this app"** warning screen —
  in front of judges.
- Testing mode caps you at 100 test users and **expires their tokens after 7 days**.
- Verification needs domain verification plus review: weeks, not days.

**Build instead:** the QR-issued session token (which we need anyway) plus a
single Argon2-hashed passcode on the dashboard. It looks professional, has zero
external dependencies, and cannot fail on stage.

This also *protects the F8 privacy story* — no identity collected means nothing to
leak. See `06_PRIVACY_MODEL_FOR_TRACKING.md`. Put "Sign in with Google" on the
roadmap slide, not in the demo.

---

## G. Where training runs — and why that is the honest answer

**Training stays on the laptop.** No free tier can host it: Render gives 0.1 CPU;
Vercel, Workers and Cloud Run all cap execution duration.

This is not a compromise, it is the architecture the problem statement describes:
*"Complex training happens in the cloud/desktop apriori, while inference happens
on the smartphone."* Training on the laptop and inference on the phone is
**exactly** the specified workflow. Say it that way.

---

## H. Scope split — what is realistic

Friday is **two days away**. Be honest about scope.

### Achievable for Friday (11 Sep)
- Laptop hotspot + `tracker_server.py` at a fixed IP — mostly works today
- QR generation on the dashboard (client-side JS, an afternoon)
- QR scanning in the app (ML Kit bundled, an afternoon)
- 2–3 phones pre-installed and paired
- Multi-phone fleet view — the server already accepts multiple devices

### Finals scope (30 Sep)
- `paper2anything.com` live on Cloudflare Pages
- Render relay + endpoint racing
- Judge self-service APK download and install
- Accounts, session history, the full operator console

**The Friday demo must work with zero internet.** Anything hosted is a bonus
surface, never the critical path.

---

## I. Build order

1. **Start DNS propagation for `paper2anything.com` today** — it is slow and free.
2. Verify `tracker_server.py` runs on a Windows Mobile Hotspot at
   `192.168.137.1:8787` and a phone can reach it. **This is the demo's spine.**
3. QR generation on the dashboard encoding token + `lan` + `relay`.
4. ML Kit **bundled** scanner in the app (+2.4 MB). **Not the unbundled model** —
   it downloads via Play Services on first use and fails with no wifi.
5. Endpoint racing with a 1.5 s timeout and re-race on three failures.
6. Multi-device fleet view with per-device colour and path history.
7. *(Finals)* Cloudflare Pages deploy, Render relay, self-service download.

---

## J. Things to verify yourself before quoting them

Marked **NOT VERIFIED** by the research pass — do not put these on a slide:

- Whether Render Free requires a card (community reports say no; not confirmed
  officially)
- Render's exact free RAM/CPU on the official pricing page
- Cloudflare R2 card requirement
- GitHub Pages size and bandwidth soft limits
- Replit's current free-tier terms
- Oracle Always Free card requirement

Also note: **Oracle reclaims idle Always Free instances** if CPU, network *and*
memory all sit below 20% for 7 days — not suitable for something that must be up
on one specific day.
