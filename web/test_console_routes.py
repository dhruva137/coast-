"""End-to-end route tests for the console, driven in-process.

The handler is exercised through its real HTTP path -- raw request bytes in,
raw response bytes out -- using fake file objects instead of a socket. That
tests the routing, status codes, headers and bodies for real, and it runs
anywhere, including on a machine that cannot open a listening port.

    python web/test_console_routes.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.coast_console import FLEET, Handler  # noqa: E402


class _Resp:
    def __init__(self, raw: bytes) -> None:
        head, _, body = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        self.status = int(lines[0].split()[1]) if lines and lines[0] else 0
        self.headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                self.headers[k.strip().lower()] = v.strip()
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def call(method: str, path: str, body: dict | None = None) -> _Resp:
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    raw = f"{method} {path} HTTP/1.0\r\nHost: test\r\n"
    if body is not None:
        raw += f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n"
    raw += "\r\n"
    data = raw.encode("latin-1") + payload

    class _H(Handler):
        def setup(self) -> None:
            self.rfile = io.BytesIO(data)
            self.wfile = io.BytesIO()

        def finish(self) -> None:
            pass

        def log_message(self, fmt, *args) -> None:
            pass

        def address_string(self) -> str:
            return "test"

    h = _H.__new__(_H)
    h.client_address = ("test", 0)
    h.request = None
    h.server = None
    h.setup()
    h.handle_one_request()
    return _Resp(h.wfile.getvalue())


def main() -> int:
    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name} {detail}")
            fails.append(name)

    print("console routes")

    r = call("GET", "/")
    check("GET /  serves the console", r.status == 200 and b"COAST" in r.body,
          f"status={r.status} bytes={len(r.body)}")
    check("GET /  is html", "text/html" in r.headers.get("content-type", ""))

    r = call("GET", "/pair?s=abc")
    check("GET /pair serves the phone page", r.status == 200 and b"Start sharing" in r.body,
          f"status={r.status}")

    r = call("GET", "/api/engine")
    j = r.json()
    check("GET /api/engine parses the C++ README",
          r.status == 200 and j.get("worst_hz", 0) > 0 and len(j.get("scenarios", [])) >= 3,
          f"worst={j.get('worst_hz')} n={len(j.get('scenarios', []))}")

    r = call("GET", "/api/claims")
    j = r.json()
    check("GET /api/claims returns the registry", r.status == 200 and len(j.get("claims", [])) >= 15,
          f"n={len(j.get('claims', []))}")

    r = call("GET", "/api/fleet")
    check("GET /api/fleet returns a snapshot", r.status == 200 and "devices" in r.json())

    # ---- pairing round trip -------------------------------------------
    r = call("POST", "/api/pair/new", {})
    j = r.json()
    token = j.get("token", "")
    check("POST /api/pair/new mints a token", r.status == 200 and len(token) > 10)
    check("      ... and renders a QR", bool(j.get("qr_svg", "").startswith("<svg")),
          f"qr bytes={len(j.get('qr_svg') or '')}")
    check("      ... payload carries both endpoints",
          "s=" in j.get("payload", "") and "lan=" in j.get("payload", ""))

    r = call("POST", "/ingest", {"token": "bogus", "lat": 52.4, "lon": -1.5})
    check("POST /ingest rejects an unknown token", r.status == 400 and not r.json()["ok"],
          f"status={r.status}")

    r = call("POST", "/ingest", {"token": token, "lat": 52.4000, "lon": -1.5000,
                                 "mode": "GNSS", "speed_mps": 12.0})
    j = r.json()
    device_id = j.get("device_id", "")
    check("POST /ingest accepts a paired phone", r.status == 200 and j.get("ok"), str(j))

    call("POST", "/ingest", {"token": token, "lat": 52.4009, "lon": -1.5009,
                             "mode": "IDR", "speed_mps": 11.0})

    snap = call("GET", "/api/fleet").json()
    dev = next((d for d in snap["devices"] if d["device_id"] == device_id), None)
    check("fleet shows the device", dev is not None)
    if dev:
        check("      ... with both points", dev["n_points"] == 2, str(dev["n_points"]))
        check("      ... and a GNSS->IDR transition", len(dev["events"]) == 1, str(dev["events"]))
        check("      ... and a computed distance", dev["distance_m"] > 50, str(dev["distance_m"]))

    r = call("GET", f"/api/privacy/{device_id}")
    j = r.json()
    check("GET /api/privacy shows what is held",
          r.status == 200 and j["held"]["positions_received"] == 2)
    check("      ... and lists what is not collected", len(j.get("not_collected", [])) >= 4)

    r = call("POST", f"/api/forget/{device_id}")
    check("POST /api/forget deletes the device", r.status == 200 and r.json()["ok"])
    snap = call("GET", "/api/fleet").json()
    check("      ... and it is really gone",
          all(d["device_id"] != device_id for d in snap["devices"]))

    r = call("GET", "/api/privacy/definitely-not-a-device")
    check("GET /api/privacy 404s for an unknown device", r.status == 404)

    r = call("GET", "/nope")
    check("GET /nope 404s", r.status == 404)

    FLEET.forget_all()
    print()
    if fails:
        print(f"{len(fails)} FAILED: {', '.join(fails)}")
        return 1
    print("all console routes OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
