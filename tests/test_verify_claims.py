from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_claims import load_claim_registry, run_claim_check


class VerifyClaimsTests(unittest.TestCase):
    def test_parses_claims_json_top_level_array(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_path = root / "claims.json"
            claims_path.write_text(
                json.dumps([{"value": 17, "unit": "count"}, {"value": 120305, "unit": "Hz"}]),
                encoding="utf-8",
            )
            parsed = load_claim_registry(claims_path)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0].unit, "count")
            self.assertEqual(parsed[1].unit, "Hz")

    def test_parses_claims_json_with_object_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_path = root / "claims.json"
            claims_path.write_text(
                json.dumps({"claims": [{"value": 2.02, "unit": "x"}, {"value": 125.2, "unit": "m"}]}),
                encoding="utf-8",
            )
            parsed = load_claim_registry(claims_path)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0].unit, "x")
            self.assertAlmostEqual(parsed[1].value, 125.2, places=3)

    def test_catches_unsourced_injected_number(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_path = root / "win_tuning/CLAIMS.json"
            allowlist_path = root / "win_tuning/CLAIMS_ALLOWLIST.txt"
            scan_file = root / "final_demo_pitch/demo.md"
            claims_path.parent.mkdir(parents=True, exist_ok=True)
            scan_file.parent.mkdir(parents=True, exist_ok=True)
            claims_path.write_text(json.dumps({"claims": [{"value": 2.02, "unit": "x"}]}), encoding="utf-8")
            allowlist_path.write_text("", encoding="utf-8")
            scan_file.write_text("Published number: 99.99x\n", encoding="utf-8")

            result = run_claim_check(
                root=root,
                claims_path=claims_path,
                allowlist_path=allowlist_path,
                strict_phrases=False,
                scan_files=[scan_file],
            )
            self.assertEqual(result.checked, 1)
            self.assertEqual(len(result.unsourced), 1)
            self.assertEqual(result.unsourced[0].token, "99.99x")

    def test_respects_claims_ignore_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_path = root / "win_tuning/CLAIMS.json"
            allowlist_path = root / "win_tuning/CLAIMS_ALLOWLIST.txt"
            scan_file = root / "final_demo_pitch/demo.md"
            claims_path.parent.mkdir(parents=True, exist_ok=True)
            scan_file.parent.mkdir(parents=True, exist_ok=True)
            claims_path.write_text(json.dumps({"claims": [{"value": 2.02, "unit": "x"}]}), encoding="utf-8")
            allowlist_path.write_text("", encoding="utf-8")
            scan_file.write_text("Draft number: 99.99x # claims:ignore\n", encoding="utf-8")

            result = run_claim_check(
                root=root,
                claims_path=claims_path,
                allowlist_path=allowlist_path,
                strict_phrases=False,
                scan_files=[scan_file],
            )
            self.assertEqual(result.checked, 0)
            self.assertEqual(len(result.unsourced), 0)

    def test_product_mode_excludes_pitch_decks(self) -> None:
        from tools.verify_claims import discover_product_scan_files, discover_scan_files

        root = Path(__file__).resolve().parents[1]
        product = discover_product_scan_files(root)
        full = discover_scan_files(root, include_readme=False, include_docs=False, product=False)
        self.assertTrue(any("web" in str(p) and "src" in str(p) for p in product))
        self.assertFalse(any("final_demo_pitch" in p.parts for p in product))
        self.assertTrue(any("final_demo_pitch" in p.parts for p in full))


if __name__ == "__main__":
    unittest.main()
