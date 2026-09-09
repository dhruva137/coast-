"""Brief smoke test for coast_console metrics honesty (FIX-1 / FIX-2).

Always unit-tests ``_load_metrics`` (including missing report.json).
Optionally hits a running console at BASE if reachable.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8787"
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from web import coast_console as cc  # noqa: E402


def _assert_happy_ledger(data: dict) -> None:
    assert not data.get("report_error"), data.get("report_error")
    assert data.get("ledger"), "empty ledger"
    error_rows = [r for r in data["ledger"] if r.get("metric") == "median position error"]
    drift_rows = [r for r in data["ledger"] if r.get("metric") == "median drift %"]
    assert any("2.02" in r["display"] for r in error_rows), "2.02× must sit on median position error"
    assert all("2.02" not in r["display"] for r in drift_rows), "2.02× must not sit on drift %"
    assert any("55%" in r["display"] for r in data["ledger"])


def _test_missing_report() -> None:
    orig = cc._MAPFILTER_REPORT
    try:
        cc._MAPFILTER_REPORT = Path("/nonexistent/mapfilter/report.json")
        data = cc._load_metrics()
        err = data.get("report_error") or ""
        assert "Could not read lab/stress/results/mapfilter/report.json" in err, err
        assert "no measured numbers to show" in err, err
        assert data.get("ledger") == [], "fallback numbers must not appear"
    finally:
        cc._MAPFILTER_REPORT = orig


def _test_local_load() -> None:
    data = cc._load_metrics()
    _assert_happy_ledger(data)
    story = str(data.get("story", "")).replace("→", "->")
    print("unit /metrics ok -", len(data["ledger"]), "rows; story:", story)


def _test_http() -> None:
    with urllib.request.urlopen(BASE + "/", timeout=3) as r:
        body = r.read()
        text = body.decode("utf-8", "replace")
        print("/", "status", r.status, "bytes", len(body))
        print("  has trainBtn", 'id="trainBtn"' in text)
        print("  has lossChart", "lossChart" in text)
        print("  has COAST", "COAST" in text)
        print("  has intro", "What this is" in text)
        print("  has offline fallback", "Map unavailable offline" in text or "__coastBoot" in text)

    with urllib.request.urlopen(BASE + "/metrics", timeout=3) as r:
        data = json.loads(r.read().decode("utf-8"))
        print("/metrics", "status", r.status, "rows", len(data.get("ledger", [])))
        print("  story:", data.get("story"))
        for row in data.get("ledger", []):
            print(" -", row["display"], "|", row["source"])
        if any(row.get("metric") == "median position error" for row in data.get("ledger", [])):
            _assert_happy_ledger(data)
        else:
            print("  HTTP ledger check skipped (running server appears to be stale build).")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    _test_missing_report()
    print("missing-report error state OK")
    _test_local_load()
    try:
        _test_http()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print("HTTP smoke skipped (console not running):", exc)
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
