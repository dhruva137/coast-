#!/usr/bin/env python3
"""Create or verify a SHA-256 evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MANIFEST = HERE / "results" / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_version() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                [
                    "git", "status", "--porcelain", "--",
                    "lab/proof", "lab/stress/load_iovnbd.py",
                    "docs/PROOF_PROTOCOL.md", "web/public/evidence",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"git_commit": commit, "proof_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": None, "proof_tree_dirty": None}


def artifact_paths(manifest_path: Path) -> list[Path]:
    paths = list(HERE.glob("*.py"))
    paths.extend(path for path in (HERE / "results").rglob("*") if path.is_file())
    protocol = ROOT / "docs" / "PROOF_PROTOCOL.md"
    if protocol.is_file():
        paths.append(protocol)
    for supporting_path in (
        ROOT / "lab" / "stress" / "load_iovnbd.py",
        ROOT / "lab" / "stress" / "results" / "alignment" / "ALIGNMENT_REPORT.md",
        ROOT / "web" / "public" / "evidence" / "proof_summary.json",
        ROOT / "web" / "public" / "evidence" / "proof_reliability.png",
    ):
        if supporting_path.is_file():
            paths.append(supporting_path)
    paths = [path for path in paths if path.resolve() != manifest_path.resolve()]

    # Bind every real source log referenced by the battery/challenge into the manifest.
    for result_name in ("reliability.json",):
        result_path = HERE / "results" / result_name
        if not result_path.is_file():
            continue
        report = json.loads(result_path.read_text(encoding="utf-8"))
        for log in report.get("logs", []):
            source = ROOT / Path(log["path"])
            if source.is_file():
                paths.append(source)
    twin_path = HERE / "results" / "counterfactual_twin.json"
    if twin_path.is_file():
        twin = json.loads(twin_path.read_text(encoding="utf-8"))
        source = ROOT / Path(twin["real_noise_source"]["path"])
        if source.is_file():
            paths.append(source)
    return sorted(set(paths), key=lambda path: path.relative_to(ROOT).as_posix())


def create(manifest_path: Path) -> dict[str, Any]:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for path in artifact_paths(manifest_path):
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema": "SIH26168-evidence-manifest-v2-corrected-axis",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "root": "repository root",
        "code_version": code_version(),
        "config": {
            "default_seed": 26168,
            "outage_durations_s": [20, 40, 60, 90],
            "held_out": "GNSS lat/lon/bearing/speed during each outage",
        },
        "files": files,
        "verification": "python lab/proof/evidence_manifest.py verify lab/proof/results/manifest.json",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify(manifest_path: Path) -> tuple[bool, list[str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    for expected in manifest["files"]:
        path = ROOT / Path(expected["path"])
        if not path.is_file():
            failures.append(f"MISSING {expected['path']}")
            continue
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != expected["bytes"]:
            failures.append(f"SIZE {expected['path']}: {size} != {expected['bytes']}")
        if digest != expected["sha256"]:
            failures.append(f"SHA256 {expected['path']}: {digest} != {expected['sha256']}")
    return not failures, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create")
    create_parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    if args.command == "create":
        manifest = create(manifest_path)
        print(f"CREATED {manifest_path} ({len(manifest['files'])} files)")
        return 0
    ok, failures = verify(manifest_path)
    if ok:
        print(f"VERIFIED {manifest_path}: all files match")
        return 0
    print("\n".join(["VERIFICATION FAILED", *failures]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
