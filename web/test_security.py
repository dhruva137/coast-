"""Tests for web.security helpers — path traversal, validation, rate limits.

    python web/test_security.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.security import (  # noqa: E402
    MAX_BODY_BYTES,
    RateLimiter,
    assert_path_in_roots,
    parse_content_length,
    safe_join,
    validate_ingest_payload,
    validate_lat_lon,
    validate_mode,
    validate_speed_mps,
    validate_token,
)


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        raise AssertionError(name)


def test_lat_lon() -> None:
    print("lat/lon validation")
    check("valid coords", validate_lat_lon(12.5, 77.1) == (12.5, 77.1))
    check("rejects lat > 90", isinstance(validate_lat_lon(91, 0), str))
    check("rejects lon < -180", isinstance(validate_lat_lon(0, -181), str))
    check("rejects non-numeric", isinstance(validate_lat_lon("x", 1), str))
    check("rejects nan", isinstance(validate_lat_lon(float("nan"), 1), str))
    check("rejects inf", isinstance(validate_lat_lon(0, float("inf")), str))


def test_mode_speed_token() -> None:
    print("mode / speed / token")
    m, err = validate_mode("idr")
    check("mode allowlist casefold", m == "IDR" and err is None)
    m, err = validate_mode("FLY")
    check("mode rejects unknown", m is None and err is not None)
    v, err = validate_speed_mps(12.0)
    check("speed ok", v == 12.0 and err is None)
    v, err = validate_speed_mps(-1)
    check("speed rejects negative", v is None)
    v, err = validate_speed_mps(10_000)
    check("speed rejects huge", v is None)
    v, err = validate_speed_mps(float("nan"))
    check("speed rejects nan", v is None and not math.isfinite(0 if v else float("nan")))
    t, err = validate_token("abc")
    check("token rejects short", t is None)
    t, err = validate_token("a" * 16)
    check("token accepts charset", t == "a" * 16 and err is None)
    t, err = validate_token("../etc/passwd")
    check("token rejects path junk", t is None)


def test_ingest_payload() -> None:
    print("ingest payload")
    ok = validate_ingest_payload(
        {"token": "tok_" + "x" * 12, "lat": 52.4, "lon": -1.5, "mode": "GNSS", "speed_mps": 5}
    )
    check("clean payload accepted", isinstance(ok, dict) and ok["mode"] == "GNSS")
    bad = validate_ingest_payload({"token": "short", "lat": 52.4, "lon": -1.5})
    check("bad token rejected", isinstance(bad, str))
    bad = validate_ingest_payload(
        {"token": "tok_" + "x" * 12, "lat": 999, "lon": 0, "mode": "GNSS"}
    )
    check("bad lat rejected", isinstance(bad, str))
    bad = validate_ingest_payload(
        {"token": "tok_" + "x" * 12, "lat": 1, "lon": 1, "mode": "TELEPORT"}
    )
    check("bad mode rejected (no coerce)", isinstance(bad, str))


def test_body_size() -> None:
    print("body size")
    length, err = parse_content_length({"Content-Length": str(MAX_BODY_BYTES)})
    check("at cap ok", length == MAX_BODY_BYTES and err is None)
    length, err = parse_content_length({"Content-Length": str(MAX_BODY_BYTES + 1)})
    check("over cap rejected", length is None and err is not None and "too large" in err)
    length, err = parse_content_length({"Content-Length": "nope"})
    check("invalid length rejected", length is None)


def test_path_traversal() -> None:
    print("path traversal / safe_join")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ok.png").write_bytes(b"png")
        (root / "nested").mkdir()
        (root / "nested" / "a.png").write_bytes(b"png")

        check("basename join", safe_join(root, "ok.png") == (root / "ok.png").resolve())
        check("rejects ..", safe_join(root, "..") is None)
        check("rejects ../etc/passwd style", safe_join(root, "..", "etc") is None)
        check("rejects slash in name", safe_join(root, "../ok.png") is None)
        check("rejects nested slash string", safe_join(root, "nested/a.png") is None)
        check("allows nested via parts", safe_join(root, "nested", "a.png") is not None)
        check("rejects empty", safe_join(root, "") is None)
        check("rejects dot", safe_join(root, ".") is None)

        # Absolute path as a single segment (Unix or Windows).
        abs_attempt = str((root / "ok.png").resolve())
        check("rejects absolute segment", safe_join(root, abs_attempt) is None)

        outside = Path(tmp).resolve().parent / "outside.png"
        check(
            "assert_path_in_roots true for file under root",
            assert_path_in_roots(root / "ok.png", [root]),
        )
        # Create a sibling outside root if possible
        try:
            outside.write_bytes(b"x")
            check(
                "assert_path_in_roots false outside",
                not assert_path_in_roots(outside, [root]),
            )
        finally:
            if outside.exists():
                outside.unlink()


def test_rate_limiter() -> None:
    print("rate limiter")
    lim = RateLimiter(rate=2, per_s=60.0, burst=2)
    check("first allow", lim.allow("ip1"))
    check("second allow", lim.allow("ip1"))
    check("third denied", not lim.allow("ip1"))
    check("other key independent", lim.allow("ip2"))
    lim.reset()
    check("reset clears", lim.allow("ip1"))


def main() -> int:
    try:
        test_lat_lon()
        test_mode_speed_token()
        test_ingest_payload()
        test_body_size()
        test_path_traversal()
        test_rate_limiter()
    except AssertionError:
        print("\nFAILED")
        return 1
    print("\nall security tests OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
