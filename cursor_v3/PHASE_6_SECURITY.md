# Phase 6 — Security and privacy hardening

The console now has a login, accepts uploads from phones, spawns subprocesses,
and serves files. Every one of those is an attack surface we did not have before.

**The framing that wins here:** our strongest privacy asset is *"we hold no
identity, so there is nothing to leak."* Every decision in this phase should
protect that sentence rather than erode it.

---

## 6.1 — Threat model, written down

`docs/THREAT_MODEL.md`. Short and real, not boilerplate. Cover:

- **Who can reach the console?** Anyone on the venue LAN or the laptop hotspot.
  Assume an unfriendly device on the same network.
- **What can they do?** Hit `/ingest` and `/pair`, which are deliberately
  unauthenticated. Bound the blast radius of that.
- **What is worth stealing?** Live positions of paired phones. Nothing else — no
  accounts, no credentials, no identifiers. Say so, and make it true.
- **What we are not defending against:** physical access to the laptop, a
  compromised phone, a state-level adversary. Naming your non-goals is a
  competence signal.

## 6.2 — Input hardening

Everything that crosses a boundary:

- **Body size caps** on every POST (already 64 KB on `/ingest` — audit the rest).
- **Strict validation**: lat/lon in range, speed finite and bounded, mode in an
  allowlist, token matching an expected charset and length. Reject, do not coerce.
- **Rate limiting** per source IP on `/ingest`, `/pair/new`, and the login. A
  simple token bucket in memory is enough; log rejections.
- **Bounded memory**: cap devices per server and points per device (currently
  4000). An unbounded ingest endpoint is a trivial denial of service.
- **No path traversal** on `/figures/<name>` and the APK route — resolve, then
  verify the result is inside the intended directory. Test with `../../` and an
  absolute path.
- **JSON only**; reject unexpected content types.

## 6.3 — Subprocess safety

`/train/start` spawns Python. Therefore:

- **Never** interpolate request data into a command. Fixed argv, no `shell=True`.
- One training run at a time; the existing lock must be verified under concurrent
  requests.
- Timeout and kill runaway runs.
- Require an **operator session** for `/train/start` — a visitor on the LAN
  should not be able to spin the laptop's GPU during the demo.

## 6.4 — Network posture

- **Default bind to `127.0.0.1`.** Require an explicit `--lan` (or
  `COAST_LAN_BASE`) to bind `0.0.0.0`, and print a clear warning when it does.
  Binding wide by default is how a dev server becomes an incident.
- Fix `web/vite.config.ts` — it currently binds `host: "::"`, exposing a dev
  server with a Python-spawning endpoint to the whole network.
- Security headers on every response: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, a restrictive `Content-Security-Policy`
  (`default-src 'self'`), `X-Frame-Options: DENY`.
- CORS is currently `*`. Narrow it, or document precisely why it must stay open
  for the pairing flow — and if it stays, keep it off authenticated routes.

## 6.5 — Secrets and data at rest

- No secrets in the repo. `web/operator.txt` gitignored; hash only, never a
  plaintext passcode.
- Session cookies: HttpOnly, SameSite=Strict, random 32 bytes, idle timeout.
- Position data lives **in memory only** by default. If a session log is written
  to disk it must be opt-in, clearly indicated, and deletable from the UI.
- **Delete must actually delete.** The privacy panel's delete button removes the
  device, its points, its events and its session — verify with a test that the
  data is gone from every structure, not just hidden from the view.

## 6.6 — Android

- Keep `usesCleartextTraffic="false"` except where LAN pairing genuinely needs an
  exception — and if it does, scope it with a **network security config** to the
  LAN ranges only, never globally.
- No logging of positions or tokens.
- The pairing token is a short-lived nonce; do not persist it beyond the session.
- Re-verify: no analytics, no third-party SDK, no hardcoded IPs, no secrets. This
  was clean at last audit — keep it clean.

## 6.7 — The privacy artifact

Extend `tools/privacy_report.py` → `docs/PRIVACY_REPORT.md`, generated from
source, regenerated in CI so it cannot drift:

- Every permission in every manifest with file:line and a one-line justification.
- **Every outbound network call site**, found by scanning, with purpose.
- Confirmation the `standard` flavour has no uploader.
- The precise `INTERNET` statement: declared for public OSM/Carto basemap tiles
  only; with the basemap off, network traffic is zero.

**Never claim "no INTERNET permission."** That claim was false once and was
fixed; add a linter rule so it cannot come back.

---

## Acceptance

- [ ] `docs/THREAT_MODEL.md` written, including non-goals
- [ ] Validation, rate limits and size caps on every endpoint, with tests
- [ ] Path traversal blocked on `/figures` and the APK route — tested
- [ ] `/train/start` requires an operator session; no shell interpolation
- [ ] Server binds localhost by default; `--lan` required and warns
- [ ] `vite.config.ts` no longer binds `::`
- [ ] Security headers present on all responses
- [ ] Delete verified to remove data from every structure
- [ ] `docs/PRIVACY_REPORT.md` generated from source
- [ ] Zero occurrences of "no INTERNET permission"; linter rule added
