"""Stdlib HTTP server for the COAST pairing relay.

    python -m relay

Bind 0.0.0.0:8788 by default. TLS belongs in the reverse proxy / Cloudflare.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .mailbox import DEFAULT_TTL_S, MailboxStore, validate_token

HOST = "0.0.0.0"
PORT = 8788
MAX_BODY_BYTES = 262_144

STORE = MailboxStore()

PAIR_LANDING = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>COAST · pair this phone</title>
<style>
  :root{--bg:#07090D;--panel:#0C1016;--line:#1C232D;--text:#E8EDF2;--dim:#8B97A6;
        --faint:#5A6673;--accent:#00D4AA;--mono:ui-monospace,Menlo,Consolas,monospace}
  *{box-sizing:border-box}
  body{margin:0;min-height:100dvh;background:var(--bg);color:var(--text);
       font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       padding:28px 16px}
  .wrap{max-width:28rem;margin:0 auto}
  .brand{letter-spacing:.02em;margin-bottom:18px}
  .brand small{display:block;color:var(--dim);font-size:11px;letter-spacing:.08em;
               text-transform:uppercase;margin-top:4px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
        padding:16px;margin-bottom:12px}
  h1{font-size:22px;margin:0 0 8px}
  p{margin:0 0 12px;color:var(--dim)}
  .code{font-family:var(--mono);font-size:28px;letter-spacing:.06em;font-weight:700;
        color:var(--accent);word-break:break-all;line-height:1.25;padding:12px;
        background:#11161E;border:1px solid var(--line);border-radius:12px;
        text-align:center}
  a.btn{display:block;text-align:center;text-decoration:none;border-radius:12px;
        padding:14px 16px;font:600 16px system-ui;margin-bottom:10px}
  .go{background:var(--accent);color:#04120E}
  .ghost{background:transparent;color:var(--dim);border:1px solid var(--line)}
  .note{font-size:13px;color:var(--faint);margin:0}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand"><b>COAST</b><small>pair this phone</small></div>
  <div class="card">
    <h1>Open this in the COAST app</h1>
    <p>A generic camera cannot run dead reckoning. Install the app, then scan
      or type the code. Position only — no account, no device ID.</p>
    <div class="code" id="code">—</div>
  </div>
  <a class="btn go" id="openapp" href="#">Open in COAST app</a>
  <a class="btn ghost" href="/">What is COAST?</a>
  <div class="card">
    <p class="note">This page is a public relay. Your phone talks to the internet;
      the operator laptop pulls the track. Guest Wi-Fi does not need to reach
      the laptop.</p>
  </div>
</div>
<script>
"use strict";
const qs = location.search || "";
const token = new URLSearchParams(qs).get("s") || "";
const code = document.getElementById("code");
code.textContent = token || "(no pairing code in this link)";
const open = document.getElementById("openapp");
open.href = "coast://pair" + qs;
</script>
</body>
</html>
"""

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>COAST pairing relay</title>
<style>
  body{margin:0;background:#07090D;color:#E8EDF2;font:16px/1.5 system-ui,sans-serif;
       padding:48px 20px}
  main{max-width:36rem;margin:0 auto}
  a{color:#00D4AA}
  .dim{color:#8B97A6}
</style>
</head>
<body>
<main>
  <h1>COAST pairing relay</h1>
  <p>Store-and-forward for phone → operator console. The phone never needs a
    route to the laptop.</p>
  <p class="dim">Scan a console QR, or open <a href="/pair">/pair</a>.
    Health: <a href="/api/health">/api/health</a>.</p>
</main>
</body>
</html>
"""


def configure_store(
    *,
    persist_dir: str | None = None,
    jsonl_path: str | None = None,
    ttl_s: float = DEFAULT_TTL_S,
) -> MailboxStore:
    global STORE
    STORE = MailboxStore(ttl_s=ttl_s, persist_dir=persist_dir, jsonl_path=jsonl_path)
    return STORE


def reset_store(store: MailboxStore | None = None) -> MailboxStore:
    global STORE
    STORE = store if store is not None else MailboxStore()
    return STORE


def _parse_content_length(headers: Any, *, max_bytes: int = MAX_BODY_BYTES) -> tuple[int | None, str | None]:
    raw = headers.get("Content-Length") if headers is not None else None
    if raw is None or raw == "":
        return 0, None
    try:
        length = int(raw)
    except (TypeError, ValueError):
        return None, "invalid Content-Length"
    if length < 0:
        return None, "invalid Content-Length"
    if length > max_bytes:
        return None, f"body too large (max {max_bytes} bytes)"
    return length, None


class Handler(BaseHTTPRequestHandler):
    server_version = "COASTRelay/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")

    def _json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _html(self, code: int, html: str, head_only: bool) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self._security_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _reject(self, code: int, message: str) -> None:
        self._json(code, {"ok": False, "error": message})

    def _read_json_body(self, *, require_body: bool = True) -> dict[str, Any] | None:
        length, err = _parse_content_length(self.headers, max_bytes=MAX_BODY_BYTES)
        if err:
            self._reject(413 if "too large" in err else 400, err)
            return None
        assert length is not None
        if require_body and length <= 0:
            self._reject(400, "empty body")
            return None
        ct = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ct and ct not in ("application/json", "text/json") and length > 0:
            self._reject(415, "Content-Type must be application/json")
            return None
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {} if not require_body else None
        try:
            frame = json.loads(raw.decode("utf-8"))
            if not isinstance(frame, dict):
                raise ValueError("expected object")
        except Exception:
            self._reject(400, "invalid json")
            return None
        return frame

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle_get(head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        self._handle_get(head_only=False)

    def _handle_get(self, head_only: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query or "")

        if path == "/api/health":
            payload = STORE.stats()
            payload["t"] = int(time.time())
            self._json(200, payload)
            return

        if path == "/pair":
            self._html(200, PAIR_LANDING, head_only)
            return

        if path == "/":
            self._html(200, INDEX_HTML, head_only)
            return

        token = None
        consume = True
        after = 0
        if path == "/feed":
            token = (qs.get("s") or [None])[0]
            consume = (qs.get("peek") or ["0"])[0] not in ("1", "true", "yes")
            try:
                after = int((qs.get("after") or ["0"])[0])
            except (TypeError, ValueError):
                after = 0
        elif path.startswith("/mailbox/"):
            token = unquote(path[len("/mailbox/") :])
            consume = (qs.get("peek") or ["0"])[0] not in ("1", "true", "yes")
            try:
                after = int((qs.get("after") or ["0"])[0])
            except (TypeError, ValueError):
                after = 0

        if token is not None:
            if not token:
                self._reject(400, "missing token")
                return
            result = STORE.feed(token, consume=consume, after=max(0, after))
            self._json(200 if result.get("ok") else 400, result)
            return

        self.send_error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        length, len_err = _parse_content_length(self.headers, max_bytes=MAX_BODY_BYTES)
        if len_err:
            self._reject(413 if "too large" in len_err else 400, len_err)
            return
        _ = length

        if path == "/pair/open":
            frame = self._read_json_body(require_body=False)
            if frame is None:
                return
            token = frame.get("token")
            if token is not None and str(token).strip() == "":
                token = None
            if token is not None:
                tok, err = validate_token(token)
                if err:
                    self._reject(400, err)
                    return
                token = tok
            result = STORE.open(token)
            self._json(200 if result.get("ok") else 400, result)
            return

        if path == "/ingest":
            frame = self._read_json_body(require_body=True)
            if frame is None:
                return
            result = STORE.ingest(frame)
            self._json(200 if result.get("ok") else 400, result)
            return

        self.send_error(404, "not found")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    host = os.environ.get("COAST_RELAY_HOST", HOST)
    port = int(os.environ.get("COAST_RELAY_PORT", str(PORT)))
    persist = os.environ.get("COAST_RELAY_STORE")
    jsonl = os.environ.get("COAST_RELAY_JSONL")
    ttl = float(os.environ.get("COAST_RELAY_TTL_S", str(DEFAULT_TTL_S)))

    if "--host" in args:
        host = args[args.index("--host") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--store" in args:
        persist = args[args.index("--store") + 1]
    if "--jsonl" in args:
        jsonl = args[args.index("--jsonl") + 1]
    if "--ttl" in args:
        ttl = float(args[args.index("--ttl") + 1])

    configure_store(persist_dir=persist, jsonl_path=jsonl, ttl_s=ttl)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(
        f"COAST pairing relay on http://{host}:{port}/  "
        f"(health http://127.0.0.1:{port}/api/health)",
        flush=True,
    )
    print(
        "POST /pair/open  POST /ingest  GET /feed?s=TOKEN  GET /mailbox/{token}  GET /pair",
        flush=True,
    )
    if persist:
        print(f"snapshots: {Path(persist).resolve()}", flush=True)
    if jsonl:
        print(f"jsonl: {Path(jsonl).resolve()}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        httpd.server_close()
    return 0
