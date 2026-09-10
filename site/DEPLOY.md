# Deploying the COAST landing page

The landing lives at `site/`. It's fully static (`index.html`, `styles.css`,
`vercel.json`, `_headers`, `_redirects`) — no build step, no runtime — so any
static host works. The live console (`web/coast_console.py`) still needs a
Python process and stays on the demo laptop; the landing is what a stranger
opens on the internet.

---

## Option A — Vercel

Fastest, no local install needed.

1. Push the repo to GitHub.
2. On [vercel.com](https://vercel.com), *Add New → Project → Import your repo*.
3. **Root Directory:** set to `site` (the landing lives there — not the repo
   root).
4. **Framework Preset:** *Other*. No build command, no output directory.
5. *Deploy.* You get a `*.vercel.app` URL immediately.

### Custom domain — `coast.paper2anything.com`

1. In Vercel → *Project → Settings → Domains*, add `coast.paper2anything.com`.
   Vercel shows a CNAME target (usually `cname.vercel-dns.com`).
2. In Cloudflare → your `paper2anything.com` zone → *DNS* → *Add record*:
   - Type: `CNAME`
   - Name: `coast`
   - Target: the CNAME Vercel showed
   - Proxy status: **DNS only** (grey cloud) — Vercel handles TLS. Leaving the
     orange cloud on breaks the Vercel-issued certificate.
3. Wait a few minutes; Vercel provisions the cert, then serves the page.

---

## Option B — Cloudflare Pages

Same repo, one host.

1. In Cloudflare → *Pages → Create a project → Connect to Git → your repo*.
2. **Build settings:** framework preset *None*; build command empty;
   **build output directory** `site`.
3. Deploy. You get a `*.pages.dev` URL.

### Custom domain — `coast.paper2anything.com`

1. In the Pages project → *Custom domains → Set up a custom domain* →
   `coast.paper2anything.com`. Cloudflare adds the DNS record automatically
   because the zone is already in the account.
2. Certificate provisions in a minute or two. Done.

> Note: Cloudflare Pages caps individual files at **25 MiB**. The APK is
> ~47 MB, so the APK link on the landing points to a GitHub Release, not to a
> file on Pages. Vercel has the same practical constraint. Keep the APK on
> GitHub Releases regardless of which host you pick.

---

## Whichever host you pick

- The landing links to `/console/`. On Vercel/Pages that path 404s unless the
  console is proxied through the same host. Two common ways:
  - Change `href="/console/"` in `index.html` to the demo laptop's public
    address (a tunnelled URL — `cloudflared` or `ngrok` — is enough for a
    demo).
  - Or add a redirect on the host: for Vercel edit `vercel.json`'s
    `redirects` array, for Pages use the existing `_redirects` file.

- The APK button already points to
  `https://github.com/coast/coast/releases/latest/download/coast.apk` — change
  the org/repo slug on the release cut, keep the filename.
