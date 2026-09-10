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
import os
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.coast_console import FLEET, Handler  # noqa: E402
from web import auth  # noqa: E402


class _Resp:
    def __init__(self, raw: bytes) -> None:
        head, _, body = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        self.status = int(lines[0].split()[1]) if lines and lines[0] else 0
        self.headers = {}
        self.set_cookies: list[str] = []
        for line in lines[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                key = k.strip().lower()
                val = v.strip()
                if key == "set-cookie":
                    self.set_cookies.append(val)
                self.headers[key] = val
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def call(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    cookie: str | None = None,
    raw_body: bytes | None = None,
    content_type: str | None = "application/json",
) -> _Resp:
    if raw_body is not None:
        payload = raw_body
    elif body is not None:
        payload = json.dumps(body).encode("utf-8")
    else:
        payload = b""
    raw = f"{method} {path} HTTP/1.0\r\nHost: test\r\n"
    if payload or body is not None:
        if content_type:
            raw += f"Content-Type: {content_type}\r\n"
        raw += f"Content-Length: {len(payload)}\r\n"
    if cookie:
        raw += f"Cookie: {cookie}\r\n"
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


def _cookie_from_login(resp: _Resp) -> str | None:
    for sc in resp.set_cookies:
        if sc.startswith(f"{auth.COOKIE_NAME}="):
            return sc.split(";", 1)[0]
    return None


def main() -> int:
    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name} {detail}")
            fails.append(name)

    # Ensure open mode for the default cold-start path.
    env_backup = os.environ.get(auth.ENV_HASH)
    os.environ.pop(auth.ENV_HASH, None)
    file_patch = mock.patch.object(auth, "OPERATOR_FILE", Path("/nonexistent/operator.txt"))
    file_patch.start()
    auth.reset_state()
    auth.reload_config()

    print("console routes")

    r = call("GET", "/")
    check("GET /  serves the console (open mode)", r.status == 200 and b"COAST" in r.body,
          f"status={r.status} bytes={len(r.body)}")
    check("GET /  is html", "text/html" in r.headers.get("content-type", ""))
    check("GET /  Cache-Control no-store", "no-store" in r.headers.get("cache-control", ""))

    r = call("GET", "/pair?s=abc")
    check("GET /pair serves the phone page", r.status == 200 and b"Start sharing" in r.body,
          f"status={r.status}")

    r = call("GET", "/static/tokens.css")
    check("GET /static/tokens.css serves CSS",
          r.status == 200 and b"--accent" in r.body,
          f"status={r.status}")
    check("      ... text/css MIME", "text/css" in r.headers.get("content-type", ""),
          r.headers.get("content-type", ""))
    check("      ... Cache-Control: no-store",
          r.headers.get("cache-control") == "no-store",
          r.headers.get("cache-control", ""))

    r = call("GET", "/static/app.js")
    check("GET /static/app.js serves JS",
          r.status == 200 and len(r.body) > 0,
          f"status={r.status}")
    ctype = r.headers.get("content-type", "")
    check("      ... javascript MIME",
          "javascript" in ctype or "ecmascript" in ctype,
          ctype)
    check("      ... Cache-Control: no-store",
          r.headers.get("cache-control") == "no-store")

    r = call("GET", "/static/../coast_console.py")
    check("GET /static/.. is rejected", r.status in (400, 404), f"status={r.status}")

    r = call("GET", "/api/engine")
    j = r.json()
    check("GET /api/engine parses the C++ README",
          r.status == 200 and j.get("worst_hz", 0) > 0 and len(j.get("scenarios", [])) >= 3,
          f"worst={j.get('worst_hz')} n={len(j.get('scenarios', []))}")

    r = call("GET", "/api/claims")
    j = r.json()
    check("GET /api/claims returns the registry",
          r.status == 200 and len(j.get("claims", [])) >= 15,
          f"n={len(j.get('claims', []))}")
    headlines = j.get("headlines") or {}
    check("      ... front-door headlines present",
          all(
              k in headlines
              for k in (
                  "map_in_loop_improvement_x",
                  "perfect_gyro_fail_pct",
                  "edge_worst_case_hz",
                  "edge_worst_case_multiple",
              )
          ),
          str(sorted(headlines.keys())))
    check("      ... 2.02x-class improvement",
          abs(float(headlines["map_in_loop_improvement_x"]["value"]) - 2.02) < 0.02,
          str(headlines.get("map_in_loop_improvement_x")))
    check("      ... ~55% perfect gyro fail",
          float(headlines["perfect_gyro_fail_pct"]["value"]) == 55.0,
          str(headlines.get("perfect_gyro_fail_pct")))
    check("      ... 98x edge multiple",
          float(headlines["edge_worst_case_multiple"]["value"]) == 98.0,
          str(headlines.get("edge_worst_case_multiple")))
    check("GET /api/claims Cache-Control no-store",
          r.headers.get("cache-control") == "no-store")

    # Broken registry → HTTP 500, never invented numbers.
    with mock.patch("web.coast_console.CLAIMS_JSON", Path("/nonexistent/CLAIMS.json")):
        r = call("GET", "/api/claims")
    check("GET /api/claims 500 when registry missing",
          r.status == 500 and "CLAIMS.json" in r.json().get("error", ""),
          f"status={r.status} body={r.body[:200]!r}")
    check("      ... no hardcoded headlines on failure",
          "headlines" not in r.json() or not r.json().get("headlines"),
          str(r.json()))

    r = call("GET", "/api/session")
    j = r.json()
    check("GET /api/session open mode",
          r.status == 200 and j.get("open_mode") is True and j.get("authenticated") is True,
          str(j))

    r = call("POST", "/api/login", {"passcode": "unused"})
    check("POST /api/login in open mode succeeds",
          r.status == 200 and r.json().get("ok") is True and r.json().get("open_mode") is True,
          str(r.json()))

    r = call("GET", "/api/fleet")
    check("GET /api/fleet returns a snapshot", r.status == 200 and "devices" in r.json())

    # ---- UK demo track (same geography as training / APK) --------------
    r = call("POST", "/api/demo/uk/start", {})
    j = r.json()
    check("POST /api/demo/uk/start streams UK track",
          r.status == 200 and j.get("ok") is True and (j.get("n_points") or 0) > 10,
          str({k: j.get(k) for k in ("ok", "n_points", "error", "region")}))
    time.sleep(0.25)
    snap = call("GET", "/api/fleet").json()
    uk = next((d for d in snap["devices"] if d.get("device_id") == "demo-uk-s1"), None)
    check("UK demo device appears on fleet", uk is not None and (uk.get("n_points") or 0) >= 1,
          str(uk and {k: uk.get(k) for k in ("label", "n_points", "device_id")}))
    if uk and uk.get("points"):
        p0 = uk["points"][0]
        check("UK demo starts in Midlands lat band",
              52.35 <= float(p0["lat"]) <= 52.50 and -1.75 <= float(p0["lon"]) <= -1.40,
              str(p0))
    r = call("GET", "/api/demo/uk")
    check("GET /api/demo/uk status", r.status == 200 and "running" in r.json())
    call("POST", "/api/demo/uk/stop", {})
    snap = call("GET", "/api/fleet").json()
    check("UK demo stop removes device",
          all(d.get("device_id") != "demo-uk-s1" for d in snap["devices"]))

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

    # ---- locked mode: HTML gated; pair / claims / static stay public ----
    print("auth-gated routes")
    digest = auth.hash_passcode("correct-horse")
    os.environ[auth.ENV_HASH] = digest
    auth.reset_state()
    auth.reload_config()

    r = call("GET", "/")
    check("GET /  401 without session when locked",
          r.status == 401 and b"COAST" in r.body,
          f"status={r.status}")

    r = call("GET", "/pair?s=abc")
    check("GET /pair still public when locked", r.status == 200, f"status={r.status}")

    r = call("GET", "/api/claims")
    check("GET /api/claims still public when locked",
          r.status == 200 and len(r.json().get("headlines", {})) >= 4,
          f"status={r.status}")

    r = call("GET", "/static/tokens.css")
    check("GET /static/* still public when locked",
          r.status == 200 and r.headers.get("cache-control") == "no-store",
          f"status={r.status}")

    r = call("GET", "/api/session")
    check("GET /api/session unauthenticated when locked",
          r.status == 200 and r.json().get("open_mode") is False
          and r.json().get("authenticated") is False,
          str(r.json()))

    r = call("POST", "/api/login", {"passcode": "wrong"})
    check("POST /api/login rejects wrong passcode",
          r.status == 401 and r.json().get("ok") is False,
          str(r.json()))

    r = call("POST", "/api/login", {"passcode": "correct-horse"})
    cookie = _cookie_from_login(r)
    check("POST /api/login accepts right passcode",
          r.status == 200 and r.json().get("ok") is True and cookie is not None,
          f"status={r.status} cookie={cookie}")

    r = call("GET", "/", cookie=cookie)
    check("GET /  200 with session cookie",
          r.status == 200 and b"COAST" in r.body,
          f"status={r.status}")

    r = call("GET", "/api/session", cookie=cookie)
    check("GET /api/session authenticated",
          r.status == 200 and r.json().get("authenticated") is True,
          str(r.json()))

    r = call("POST", "/ingest", {"token": "bogus", "lat": 1.0, "lon": 2.0}, cookie=None)
    check("POST /ingest still ungated when locked",
          r.status == 400,  # bad token, but reachable
          f"status={r.status}")

    r = call("POST", "/api/logout", {}, cookie=cookie)
    check("POST /api/logout clears session",
          r.status == 200 and r.json().get("ok") is True,
          str(r.json()))

    r = call("GET", "/", cookie=cookie)
    check("GET /  401 after logout",
          r.status == 401,
          f"status={r.status}")

    # ---- engine: live arithmetic over the real UK strip ----------------
    r = call("GET", "/api/engine/meta")
    j = r.json()
    check("GET /api/engine/meta describes the real demo strip",
          r.status == 200 and j.get("n_samples", 0) > 100
          and "iovnbd_demo.csv" in j.get("source", ""),
          str(j)[:120])

    from web.engine_compute import EngineRun  # noqa: PLC0415

    run = EngineRun()
    steps = []
    while True:
        s = run.step()
        if s is None:
            break
        steps.append(s)
    check("engine computes every sample", len(steps) == run.n, f"{len(steps)}/{run.n}")

    idr = [s for s in steps if s["mode"] == "IDR"]
    gnss = [s for s in steps if s["mode"] == "GNSS"]
    check("engine has both GNSS and IDR phases", len(idr) > 50 and len(gnss) > 50,
          f"idr={len(idr)} gnss={len(gnss)}")
    # Free dead reckoning must visibly diverge during the outage -- if it does
    # not, either the outage is not being applied or the integration is inert,
    # and the whole view would be showing a flat lie.
    check("free-DR error grows through the outage",
          idr[-1]["position"]["err_m"] > idr[0]["position"]["err_m"] + 20,
          f"{idr[0]['position']['err_m']} -> {idr[-1]['position']['err_m']}")
    check("gravity is actually removed",
          all(abs(s["linear"]["mag"]) < 30 for s in steps),
          "linear accel magnitude should never approach raw |a| ~9.8+")
    check("throughput is measured, not asserted",
          steps[-1]["perf"]["us_per_sample"] > 0)

    FLEET.forget_all()
    file_patch.stop()
    if env_backup is None:
        os.environ.pop(auth.ENV_HASH, None)
    else:
        os.environ[auth.ENV_HASH] = env_backup
    auth.reset_state()
    auth.reload_config()

    print()
    if fails:
        print(f"{len(fails)} FAILED: {', '.join(fails)}")
        return 1
    print("all console routes OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
