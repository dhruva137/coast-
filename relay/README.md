# COAST public pairing relay

Venue guest Wi-Fi almost always runs **AP isolation**: phones can reach the
internet, but not the operator laptop. The phone must never need a route to
the laptop.

This directory is a **store-and-forward mailbox**:

1. The console registers a short-lived nonce (`POST /pair/open`).
2. The QR URL is hosted on the **relay**, with the laptop LAN address as a
   query fallback (`lan=`). The COAST app races both.
3. The phone `POST`s `/ingest` here (token, lat, lon, mode, speed_mps, acc_m;
   or a `points` batch). No IMEI / advertising ID.
4. The laptop console **pulls** `GET /feed?s=TOKEN` on a timer and merges
   into Fleet. The laptop does not need a public IP.

Cloudflare **Pages** (`site/`) can serve a static landing. Pages has **no
persistent process**, so it cannot be the relay. Render's free tier spins
down after ~15 minutes idle — if you use Render, add a keep-alive ping to
`GET /api/health` every 10 minutes, or prefer the Worker below.

This repo does **not** claim the relay is deployed.

## HTTP contract

| Method | Path | Role |
| --- | --- | --- |
| `GET` | `/api/health` | Phone probe + keep-alive |
| `GET` | `/pair` | Human landing after a generic-camera QR scan |
| `POST` | `/pair/open` | `{token?}` — register mailbox, TTL 2 hours |
| `POST` | `/ingest` | Same body as the console LAN ingest |
| `GET` | `/feed?s=TOKEN` | Console pull; default **consume** (delete after read) |
| `GET` | `/feed?s=TOKEN&peek=1` | Read without deleting |
| `GET` | `/feed?s=TOKEN&after=N` | Cursor: points with `seq > N` |
| `GET` | `/mailbox/{token}` | Alias of `/feed` |

Unknown or expired tokens are rejected. Device-identifier keys (`imei`,
`android_id`, `gaid`, …) are rejected, not stored.

## Run on any VPS (Python, stdlib only)

From the repo root:

```
python -m relay
```

Defaults to `0.0.0.0:8788`. Put Caddy / nginx / Cloudflare in front for TLS
and point `COAST_RELAY_BASE` on the laptop at that origin.

```
python -m relay --port 8788 --store ./relay-data --jsonl ./relay.jsonl
```

| Env / flag | Meaning |
| --- | --- |
| `COAST_RELAY_HOST` / `--host` | Bind address |
| `COAST_RELAY_PORT` / `--port` | Bind port (default 8788) |
| `COAST_RELAY_STORE` / `--store` | Directory of per-token JSON snapshots |
| `COAST_RELAY_JSONL` / `--jsonl` | Append-only ingest audit log |
| `COAST_RELAY_TTL_S` / `--ttl` | Mailbox TTL seconds (default 7200) |

On the **laptop console**:

```
set COAST_RELAY_BASE=https://coast.paper2anything.com
python -m web.coast_console
```

PowerShell: `$env:COAST_RELAY_BASE = "https://coast.paper2anything.com"`.

If unset, the console still encodes `https://coast.paper2anything.com` in the
QR so a venue phone can post without LAN. Set `COAST_RELAY_BASE=off` to force
LAN-only (QR host = laptop).

**Do not** put Cloudflare Pages alone on that hostname. The phone probes
`GET /pair` and treats HTTP 200 as “relay is up”, then `POST /ingest` which
Pages cannot serve. Either:

- bind the **Worker** (below) to the hostname, or
- run Python behind TLS on that hostname, or
- set `COAST_RELAY_BASE=off`.

## Cloudflare Worker + KV (same contract)

`relay/worker.js` is a drop-in Worker. KV holds mailboxes (TTL on the key).

```
cd relay
npx wrangler kv namespace create MAILBOX
```

Paste the id into `relay/wrangler.toml`, then `npx wrangler deploy`. Route the
custom domain (`coast.paper2anything.com`) to this Worker in the dashboard.

If Pages also uses that domain, Worker routes must win for `/ingest`,
`/pair/open`, `/feed`, `/mailbox*`, `/api/health`, and `/pair`.

## Keep-alive (Render / idle hosts)

Free PaaS will sleep. Hit `/api/health` from a cron every 10 minutes, or
don't use a sleeping host for a live demo.

## Tests

From the repo root (PowerShell: separate commands, no `&&`):

```
python tests/test_relay.py
python web/test_console_routes.py
```
