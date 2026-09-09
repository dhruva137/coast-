#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckStatus:
    name: str
    status: str  # PASS / FAIL / SKIP
    detail: str


def run_command(name: str, cmd: list[str], cwd: Path | None = None) -> CheckStatus:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        missing = exc.filename or cmd[0]
        return CheckStatus(name, "SKIP", f"missing command: {missing}")
    except Exception as exc:  # pragma: no cover
        return CheckStatus(name, "SKIP", f"could not run: {exc}")

    if proc.returncode == 0:
        return CheckStatus(name, "PASS", "ok")
    output = (proc.stdout + "\n" + proc.stderr).strip()
    detail = output.splitlines()[-1] if output else f"exit {proc.returncode}"
    return CheckStatus(name, "FAIL", detail)


def check_android_strings(root: Path) -> CheckStatus:
    strings_xml = root / "android/app/src/main/res/values/strings.xml"
    if not strings_xml.exists():
        return CheckStatus("android-strings", "SKIP", "strings.xml not found")
    try:
        ET.parse(strings_xml)
        return CheckStatus("android-strings", "PASS", "xml parses")
    except ET.ParseError as exc:
        return CheckStatus("android-strings", "FAIL", f"xml parse error: {exc}")


def check_web_quick(root: Path) -> CheckStatus:
    if shutil.which("npm") is None:
        return CheckStatus("web-quick", "SKIP", "npm not installed")
    pkg = root / "web/package.json"
    if not pkg.exists():
        return CheckStatus("web-quick", "SKIP", "web/package.json missing")
    return run_command("web-quick", ["npm", "--version"], cwd=root)


def check_lab_quick(root: Path) -> CheckStatus:
    demo_py = root / "lab/demo.py"
    if not demo_py.exists():
        return CheckStatus("lab-quick", "SKIP", "lab/demo.py missing")
    return run_command("lab-quick", [sys.executable, "-m", "py_compile", str(demo_py)], cwd=root)


def check_manifold(root: Path) -> CheckStatus:
    test = root / "tests/test_manifold.py"
    if not test.exists():
        return CheckStatus("manifold", "SKIP", "tests/test_manifold.py missing")
    return run_command("manifold", [sys.executable, str(test)], cwd=root)


def check_privacy_report(root: Path, *, regenerate: bool) -> CheckStatus:
    script = root / "tools/privacy_report.py"
    if not script.exists():
        return CheckStatus("privacy-report", "SKIP", "tools/privacy_report.py missing")
    if regenerate:
        wrote = run_command(
            "privacy-report",
            [sys.executable, str(script)],
            cwd=root,
        )
        if wrote.status == "FAIL":
            return wrote
    return run_command(
        "privacy-report",
        [sys.executable, str(script), "--check"],
        cwd=root,
    )


def print_summary(results: list[CheckStatus]) -> None:
    print("\nStatus summary")
    print("-" * 72)
    print(f"{'Check':24} {'Status':8} Detail")
    print("-" * 72)
    for item in results:
        print(f"{item.name:24} {item.status:8} {item.detail}")
    print("-" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run claim verification and local sanity checks.")
    parser.add_argument("--strict", action="store_true", help="Fail on any FAIL status.")
    parser.add_argument(
        "--privacy-check-only",
        action="store_true",
        help="Only --check docs/PRIVACY_REPORT.md (do not regenerate).",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results: list[CheckStatus] = []

    claims = run_command(
        "verify-claims",
        [sys.executable, "tools/verify_claims.py", "--product"],
        cwd=root,
    )
    results.append(claims)
    results.append(check_android_strings(root))
    results.append(check_web_quick(root))
    results.append(check_lab_quick(root))
    results.append(check_manifold(root))
    results.append(
        check_privacy_report(root, regenerate=not args.privacy_check_only)
    )

    print_summary(results)

    claim_failed = any(r.name == "verify-claims" and r.status == "FAIL" for r in results)
    privacy_failed = any(r.name == "privacy-report" and r.status == "FAIL" for r in results)
    any_failed = any(r.status == "FAIL" for r in results)
    if args.strict:
        return 1 if any_failed else 0
    return 1 if (claim_failed or privacy_failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
