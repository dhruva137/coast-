#!/usr/bin/env python3
"""Export the corrected proof summary and plot for the web Evidence Room."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
PUBLIC = ROOT / "web" / "public" / "evidence"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    reliability_path = RESULTS / "reliability.json"
    twin_path = RESULTS / "counterfactual_twin.json"
    commitment_path = RESULTS / "blind" / "blind_commitment.json"
    reveal_path = RESULTS / "blind" / "blind_reveal.json"
    reliability = json.loads(reliability_path.read_text(encoding="utf-8"))
    twin = json.loads(twin_path.read_text(encoding="utf-8"))
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    reveal = json.loads(reveal_path.read_text(encoding="utf-8"))
    primary = reliability["methods"]["idr_lean_bias"]

    PUBLIC.mkdir(parents=True, exist_ok=True)
    plot_source = RESULTS / "reliability.png"
    plot_target = PUBLIC / "proof_reliability.png"
    shutil.copy2(plot_source, plot_target)

    summary = {
        "schema": "SIH26168-web-proof-summary-v2",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "CORRECTED_PROTOCOL_COMPLETE_PERFORMANCE_NOT_DEPLOYMENT_READY",
        "honesty_note": (
            "Measured real-car errors and covariance undercoverage are retained. "
            "Injected lean is synthetic evidence, not a two-wheeler field result."
        ),
        "supersedes": {
            "status": "SUPERSEDES_STALE_FALLBACK",
            "reason": "Corrected vehicle yaw=-GYROSCOPE Pitch and segmented sessions",
            "prior_summary": {
                "placements": 120,
                "median_error_m": 212.2,
                "p95_error_m": 578.5,
                "coverage_95": 0.30,
                "failure_rate_over_50m": 0.90,
            },
        },
        "provenance": {
            "protocol": reliability["protocol"],
            "seed": reliability["seed"],
            "data_class": reliability["data_class"],
            "axis_mapping": reliability["axis_mapping"],
            "segmentation": reliability["segmentation"],
            "independent_source_files": reliability["independent_source_files"],
            "viable_sessions": reliability["viable_sessions"],
            "completed_placements": reliability["completed_trials"],
            "source_logs": reliability["logs"],
            "manifest_path": "lab/proof/results/manifest.json",
            "manifest_verification_command": (
                "python lab/proof/evidence_manifest.py verify "
                "lab/proof/results/manifest.json"
            ),
            "artifacts": {
                "reliability": {
                    "path": "lab/proof/results/reliability.json",
                    "sha256": sha256_file(reliability_path),
                },
                "counterfactual": {
                    "path": "lab/proof/results/counterfactual_twin.json",
                    "sha256": sha256_file(twin_path),
                },
                "blind_commitment": {
                    "path": "lab/proof/results/blind/blind_commitment.json",
                    "sha256": sha256_file(commitment_path),
                },
                "blind_reveal": {
                    "path": "lab/proof/results/blind/blind_reveal.json",
                    "sha256": sha256_file(reveal_path),
                },
            },
        },
        "primary_method": "idr_lean_bias",
        "overall": primary,
        "by_outage_seconds": primary["by_duration_s"],
        "blind_challenge": {
            "selection": commitment["selection"],
            "scores": reveal["scores"],
        },
        "counterfactual": {
            "status": twin["counterfactual_status"],
            "data_class": twin["twins"]["injected_lean"]["data_class"],
            "injected_lean": twin["twins"]["injected_lean"],
            "noiseless_consistency_check": twin["noiseless_consistency_check"],
            "investigation": twin["investigation"],
        },
        "plots": ["/evidence/proof_reliability.png"],
    }
    target = PUBLIC / "proof_summary.json"
    target.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"WROTE {target}")
    print(f"COPIED {plot_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
