"""Brief smoke test for coast_console: GET / and GET /metrics."""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8787"


def main() -> int:
    with urllib.request.urlopen(BASE + "/", timeout=10) as r:
        body = r.read()
        text = body.decode("utf-8", "replace")
        print("/", "status", r.status, "bytes", len(body))
        print("  has trainBtn", 'id="trainBtn"' in text)
        print("  has lossChart", "lossChart" in text)
        print("  has COAST", "COAST" in text)

    with urllib.request.urlopen(BASE + "/metrics", timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
        print("/metrics", "status", r.status, "rows", len(data.get("ledger", [])))
        print("  story:", data.get("story"))
        for row in data.get("ledger", []):
            print(" -", row["display"], "|", row["source"])
        assert data.get("ledger"), "empty ledger"
        assert any("2.02" in row["display"] for row in data["ledger"])
        assert any("55%" in row["display"] for row in data["ledger"])
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
