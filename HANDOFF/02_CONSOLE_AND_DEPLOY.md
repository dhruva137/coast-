# Console cleanup and Cloudflare deployment

Read `00_CONTEXT.md` first.

---

## 1. The deployment constraint you must design around

**Cloudflare Pages is static hosting. The console is a Python server.** You
cannot deploy `coast_console.py` to Pages. Pretending otherwise wastes a day.

Split it in two:

| Surface | Where | What it contains |
|---|---|---|
| **Public site** | Cloudflare Pages (`site/`) | Landing page, the pitch, the evidence/claims table, the model card, screenshots, APK download link |
| **Live console** | The demo laptop | Fleet map, live training, engine arithmetic — anything needing a running process |

The public site must be **fully static**: bake `CLAIMS.json` and the results
tables into JSON at build time and fetch them locally. No Python at runtime.

**This is the right architecture anyway** — a hosted console would depend on
venue internet, and free tiers that sleep after 15 minutes idle would be
catastrophic if a judge is the first visitor.

### APK download

**Cloudflare Pages caps files at 25 MiB. The APK is ~47 MB — it will not
upload.** Options, in order:

1. **GitHub Releases** — 2 GiB per file, direct link, no interstitial, no
   login. Link it from the site. This is the recommended path.
2. **Cloudflare R2** — 10 GB free, egress free, works with a Pages site.
3. Do **not** use Google Drive — files over ~100 MB get a virus-scan
   interstitial and direct links are unstable.

Also render a **QR code on the landing page pointing at the APK URL**, so a
judge can install without typing anything.

### Steps

1. Point `coast.paper2anything.com` at Cloudflare (nameservers), add it as a
   Pages custom domain. DNS propagation takes hours — **do this first**.
2. Build `site/` to static output; `wrangler.toml` already exists.
3. Upload the APK to GitHub Releases; put the URL + QR on the site.
4. Verify the whole site loads with the network throttled and with JS errors
   visible — no CDN, no web fonts, no remote tiles.

---

## 2. Evidence view — currently messy

Target: it should read like a **compliance report**, not a debug dump. A judge
should be able to scan it in fifteen seconds and conclude "these people measure
things."

**Structure it in three bands:**

1. **Headline row** — three or four stat cards, large numbers, one line of
   meaning each. `2.02×` · `55%` · `98×` · `100 ms`.
2. **The claims table** — one row per claim from `CLAIMS.json`:
   claim · value · confidence · source file. Sortable. Group by confidence so
   `measured` and `measured-negative` sit together rather than interleaved.
3. **The honesty band** — a short, deliberately prominent section listing what
   we do *not* claim: the 10% bar we do not meet, the 1.07× fusion wash, the
   0.98× post-hoc control, the rejected residual model, the hidden confidence
   radius. **This is a feature, not a disclaimer.** Style it as confidently as
   the wins.

**Visual rules** (a token system already exists in `web/static/tokens.css`):
- Near-black background, one accent (`--accent` teal), `--gnss` blue reserved
  strictly for GNSS. No other colours.
- **Tabular figures on every number** (`font-variant-numeric: tabular-nums`) —
  numbers that change width as digits change is the most common tell of amateur
  software.
- Four type sizes only. 8 px spacing grid. Generous whitespace between groups —
  density comes from small, well-aligned type, not from cramming.
- Every row links to its source file path. The point is that it is checkable.

**Empty/error states:** if `CLAIMS.json` cannot be read, say exactly that and
name the file. Never fall back to remembered numbers — that pattern was already
removed once and must not return.

---

## 3. Console polish generally

- **Scrollbars**: already styled dark in `tokens.css`. If any new scrollable
  surface appears light, it inherits the OS theme — check `color-scheme: dark`
  applies.
- **Responsive**: verify at 1920×1080, 1440×900, 1280×1024 (4:3 projector) and
  1024×768. Nothing clipped, no horizontal page scroll.
- **Presentation mode**: a key that hides chrome and scales type up ~25% for
  projecting to a room.
- **Loading states must reserve final layout** so nothing shifts when data
  lands.

---

## Acceptance

- [ ] `site/` builds to static output and deploys to Cloudflare Pages
- [ ] Custom domain resolves with automatic HTTPS
- [ ] Site loads fully with no network beyond its own origin
- [ ] APK downloadable from GitHub Releases, linked and QR-coded on the site
- [ ] Evidence view: headline cards, grouped claims table, prominent honesty band
- [ ] Tabular figures everywhere a number updates
- [ ] Claims unreadable → explicit error naming the file, never remembered values
- [ ] `python web/test_console_routes.py` green
- [ ] `python tools/verify_claims.py` exits 0
