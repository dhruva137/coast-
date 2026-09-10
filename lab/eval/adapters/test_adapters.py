"""Load-only tests for dataset adapters (no large downloads)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from lab.eval.adapters import get_adapter  # noqa: E402

_COMMA = _REPO / "lab" / "eval" / "fixtures" / "comma2k19_tiny"


class TestComma2k19Fixture(unittest.TestCase):
    def test_discover_and_load_tiny(self) -> None:
        adapter = get_adapter("comma2k19")
        files = adapter.discover(_COMMA)
        self.assertGreaterEqual(len(files), 1, msg=str(_COMMA))
        session = adapter.load(files[0])
        self.assertEqual(session.t_s.size, session.ax.size)
        self.assertGreaterEqual(session.t_s.size, 50)
        self.assertTrue((session.t_s[1:] >= session.t_s[:-1]).all())
        self.assertTrue(session.meta.get("adapter") == "comma2k19")
        # Rough SF-ish coordinates from the synthetic fixture — not a claim.
        self.assertTrue(30.0 < float(session.lat[0]) < 50.0)
        self.assertTrue(-130.0 < float(session.lon[0]) < -100.0)


class TestGsdcRegistered(unittest.TestCase):
    def test_get_adapter(self) -> None:
        a = get_adapter("gsdc")
        self.assertEqual(a.name, "gsdc")


if __name__ == "__main__":
    unittest.main()
