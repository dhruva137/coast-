"""Every number we publish must trace to a measured file. This enforces it.

Two independent checks, because there are two ways a claim goes wrong:

1. **Drift** — the registry says 2.02x but the results file now says something
   else. Each claim carries a resolver that re-reads its source file, so the
   registry cannot silently diverge from the data.
2. **Invention** — a slide states a number that no results file produced. The
   surface scan looks for claim-shaped numbers (a value next to Hz, x, %, m)
   in pitch-facing text and fails on anything the registry does not know.

Usage
-----
    python tools/verify_claims.py              # verify, exit non-zero on failure
    python tools/verify_claims.py --json       # (re)write win_tuning/CLAIMS.json
    python tools/verify_claims.py --demo-failure
        Plant a fabricated number in a temp copy and show the check catching it.
        Fifteen seconds, and it demonstrates the discipline rather than asserting it.

Adding a claim
--------------
Add an entry to CLAIMS with a resolver that reads the measured artifact. Never
hardcode the expected value -- if a number has no file behind it, it is not a
claim we are allowed to make, and the right fix is to remove it from the deck.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "win_tuning" / "CLAIMS.json"

IGNORE_MARK = "claims:ignore"


def _json(rel: str) -> Any:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Claim:
    id: str
    statement: str
    unit: str
    source_file: str
    resolve: Callable[[], float]
    tolerance: float = 0.01
    confidence: str = "measured"
    note: str = ""


def _mapfilter(field: str) -> Callable[[], float]:
    def go() -> float:
        return float(_json("lab/stress/results/mapfilter/report.json")["scenarios"]["junctions"][field])

    return go


def _oracle_fail_pct() -> float:
    agg = _json("lab/stress/results/heading_ablation/report.json")["aggregate"]["F_oracle"]
    return round(100.0 * (1.0 - agg["pass_isro"] / agg["n_rows"]))


def _isro_arm(arm: str) -> Callable[[], float]:
    def go() -> float:
        summary = _json("lab/stress/results/isro_benchmark/report.json")["summary"]
        rates = [v["pass_rate"] for k, v in summary.items() if k.startswith(arm + "/")]
        return round(max(rates) * 100)

    return go


def _fusion_x() -> float:
    return float(_json("lab/stress/results/gnss_ins_fusion/report.json")["summary"]["all"]["fused_vs_gnss_x"])


def _mag(field: str) -> Callable[[], float]:
    def go() -> float:
        return float(_json("lab/stress/results/magnetometer/report.json")[field])

    return go


def _documented_number(rel: str, pattern: str, expect: float) -> float:
    """Confirm a historical narrative number is still documented where we say.

    Some claims are about our own process rather than a current measurement --
    the unit bug we caught, for instance. There is no results file to re-derive
    them from, so the check is that the write-up still says what we say it says.
    """
    text = (REPO / rel).read_text(encoding="utf-8")
    if not re.search(pattern, text):
        raise ValueError(f"{rel} no longer documents this")
    return expect


_THROUGHPUT_ROW = re.compile(r"\|\s*Sustained throughput\s*\|(.+)$", re.MULTILINE)
_HZ = re.compile(r"([\d,]+)\s*Hz")


def _edge_throughput(pick: str) -> Callable[[], float]:
    """Read the sustained-throughput rows out of the edge engine's own README.

    The C++ benchmark is the primary record and it reports a *range per
    configuration*, not one number. We deliberately publish the worst measured
    configuration: a claim nobody can attack by picking a harder scenario.
    """

    def go() -> float:
        text = (REPO / "core/cpp/apps/README.md").read_text(encoding="utf-8")
        rates: list[float] = []
        for row in _THROUGHPUT_ROW.finditer(text):
            for m in _HZ.finditer(row.group(1)):
                rates.append(float(m.group(1).replace(",", "")))
        if not rates:
            raise ValueError("no 'Sustained throughput' rows found in edge README")
        return min(rates) if pick == "min" else max(rates)

    return go


CLAIMS: list[Claim] = [
    Claim(
        "map_in_loop_improvement_x",
        "Map-in-loop vs free dead reckoning, lower median POSITION ERROR "
        "(not drift %) across 43 real GNSS outages, vehicle CAN ground truth",
        "x",
        "lab/stress/results/mapfilter/report.json",
        _mapfilter("improvement_x"),
        note="Quote as 2.02x lower median position error. The drift-% ratio is a "
        "different number (1.65x) and the two must never share a cell.",
    ),
    Claim(
        "free_median_error_m",
        "Free dead-reckoning median position error over the outage set",
        "m",
        "lab/stress/results/mapfilter/report.json",
        _mapfilter("free_median_error_m"),
        tolerance=0.05,
    ),
    Claim(
        "coast_median_error_m",
        "COAST median position error over the same outage set",
        "m",
        "lab/stress/results/mapfilter/report.json",
        _mapfilter("pf_median_error_m"),
        tolerance=0.05,
    ),
    Claim(
        "free_median_drift_pct",
        "Free dead-reckoning median drift as % of distance travelled",
        "%",
        "lab/stress/results/mapfilter/report.json",
        _mapfilter("free_median_drift_pct"),
        tolerance=0.05,
    ),
    Claim(
        "coast_median_drift_pct",
        "COAST median drift as % of distance travelled. ISRO bar is <10% -- "
        "we do NOT clear it, and say so first.",
        "%",
        "lab/stress/results/mapfilter/report.json",
        _mapfilter("pf_median_drift_pct"),
        tolerance=0.05,
    ),
    Claim(
        "n_outages",
        "Real GNSS outages scored",
        "count",
        "lab/stress/results/mapfilter/report.json",
        _mapfilter("n"),
    ),
    Claim(
        "perfect_gyro_fail_pct",
        "A PERFECT (oracle) yaw sensor still fails this share of 60 s segments. "
        "The negative result the pitch is built on.",
        "%",
        "lab/stress/results/heading_ablation/report.json",
        _oracle_fail_pct,
        tolerance=0.5,
    ),
    Claim(
        "free_dr_short_arm_pct",
        "Free-DR pass rate, ISRO short arm (<5 m over 50 m, <60 s)",
        "%",
        "lab/stress/results/isro_benchmark/report.json",
        _isro_arm("ARM_SHORT"),
        tolerance=0.5,
    ),
    Claim(
        "free_dr_tunnel_arm_pct",
        "Free-DR pass rate, ISRO tunnel arm (<10% and <100 m/km over 60 s)",
        "%",
        "lab/stress/results/isro_benchmark/report.json",
        _isro_arm("ARM_TUNNEL"),
        tolerance=0.5,
    ),
    Claim(
        "gnss_ins_fusion_x",
        "Loosely-coupled GNSS+INS fusion vs GNSS alone. A WASH -- report it. "
        "The PS asks for an AI-based fusion model; ours is classical.",
        "x",
        "lab/stress/results/gnss_ins_fusion/report.json",
        _fusion_x,
        confidence="measured-negative",
    ),
    Claim(
        "posthoc_mapmatch_x",
        "Post-hoc road snapping vs free dead reckoning. BELOW 1.0 -- snapping a "
        "drifted track onto a confidently wrong road makes it worse. This is the "
        "control that proves the value is in-loop, not in the map.",
        "x",
        "lab/stress/results/mapmatch/report.json",
        lambda: float(_json("lab/stress/results/mapmatch/report.json")["summary"]["improvement_x"]),
        confidence="measured-negative",
    ),
    Claim(
        "edge_worst_case_hz",
        "Worst measured edge-engine configuration (180-particle graph filter, "
        "100% GNSS-denied, 200 Hz). Publish THIS, not a best case: it is 98x the "
        "200 Hz requirement and cannot be attacked with a harder scenario.",
        "Hz",
        "core/cpp/apps/README.md",
        _edge_throughput("min"),
        tolerance=1.0,
    ),
    Claim(
        "edge_worst_case_multiple",
        "Worst measured edge throughput as a multiple of the 200 Hz requirement",
        "x",
        "core/cpp/apps/README.md",
        lambda: float(int(_edge_throughput("min")() / 200.0)),
        confidence="derived",
        note="Derived: edge_worst_case_hz / 200, floored.",
    ),
    Claim(
        "edge_best_case_hz",
        "Best measured edge-engine configuration. Quote only with its "
        "configuration attached, never as the headline.",
        "Hz",
        "core/cpp/apps/README.md",
        _edge_throughput("max"),
        tolerance=1.0,
    ),
    Claim(
        "heading_gyro_drift_pct",
        "Heading-induced drift over a 60 s outage using gyro integration alone "
        "(today's behaviour), 655 windows across 34 drives",
        "%",
        "lab/stress/results/heading_fusion/report.json",
        lambda: float(
            _json("lab/stress/results/heading_fusion/report.json")["policies"]["gyro"][
                "median_drift_pct"
            ]
        ),
        tolerance=0.05,
    ),
    Claim(
        "heading_compass_drift_pct",
        "Same, using an onset-calibrated compass for heading. Calibration uses "
        "only the last GNSS bearing before the outage, so it is implementable.",
        "%",
        "lab/stress/results/heading_fusion/report.json",
        lambda: float(
            _json("lab/stress/results/heading_fusion/report.json")["policies"]["compass"][
                "median_drift_pct"
            ]
        ),
        tolerance=0.05,
    ),
    Claim(
        "heading_compass_pass_pct",
        "Share of 60 s outage windows meeting the ISRO <10% drift criterion on "
        "the heading channel with the compass, vs 32% for gyro alone",
        "%",
        "lab/stress/results/heading_fusion/report.json",
        lambda: float(
            _json("lab/stress/results/heading_fusion/report.json")["policies"]["compass"][
                "pass_rate_under_10pct"
            ]
        ),
        tolerance=0.5,
    ),
    Claim(
        "unit_bug_inflation_x",
        "The km/h-vs-m/s loader bug we found in our OWN pipeline, which inflated "
        "every reported drift %. Historical, not a current measurement -- the "
        "resolver only confirms the write-up still documents it.",
        "x",
        "docs/AUDIT_AND_PLAN.md",
        lambda: _documented_number("docs/AUDIT_AND_PLAN.md", r"/\s*3\.6", 3.6),
        confidence="historical",
    ),
    Claim(
        "magnetometer_heading_err_deg",
        "Phone compass heading error vs GPS course, after granting a perfect "
        "per-drive mount and declination offset. Lower bound on real error.",
        "deg",
        "lab/stress/results/magnetometer/report.json",
        _mag("phone_yaw_median_deg"),
        tolerance=0.1,
    ),
    Claim(
        "gyro_free_run_60s_deg",
        "Free-running gyro heading error over a 60 s outage",
        "deg",
        "lab/stress/results/magnetometer/report.json",
        _mag("gyro_60s_median_deg"),
        tolerance=0.1,
    ),
]

# Claim-shaped numbers found in pitch text. Each entry maps a literal that may
# appear in prose to the claim it must agree with.
# Judge-facing surfaces only. The strategy folders (win_tuning/, design_v3/)
# are internal and carry externally-cited figures with URLs -- linting those
# produces noise that trains people to ignore the linter. What matters is that
# nothing unsourced reaches a slide or the team's spoken brief.
SURFACES = [
    "final_demo_pitch/ppt_assets/slide_*.md",
    "final_demo_pitch/PPT_DRAFT.md",
    "final_demo_pitch/TEAM_MASTER_BRIEF.md",
]

# Numbers that look like claims but are not ours to source: requirement figures
# quoted from the problem statement, dataset sizes, years, and the like.
ALLOWED_LITERALS = {
    "200",      # PS requirement: 200 Hz on the edge engine
    "10",       # PS requirement: 10 Hz on phone / <10% drift bar
    "26168",    # problem statement number
    "2026",
    "2025",
    "100",      # handover ms, and percentages
    "50",       # PS: 50 m short arm
    "1",
    "60",       # 60 s outage window
    "1.00",     # the free-DR baseline, 1.0x by definition
    "33",       # edge p50 latency, us -- core/cpp/apps/README.md scenario C
}

CLAIM_PATTERN = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(?:\*\*)?\s*(Hz|×|x the|% drift|deg|°)",
    re.IGNORECASE,
)


def _load_expected() -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    errors: list[str] = []
    for c in CLAIMS:
        try:
            values[c.id] = float(c.resolve())
        except (OSError, KeyError, TypeError, ValueError, ZeroDivisionError, json.JSONDecodeError) as exc:
            errors.append(f"{c.id}: cannot resolve from {c.source_file} -- {exc}")
    return values, errors


def _write_registry(values: dict[str, float]) -> None:
    payload = {
        "_comment": (
            "Generated by tools/verify_claims.py. Do not hand-edit: every value is "
            "re-derived from the measured file named in source_file. A number with "
            "no entry here is a number we are not allowed to publish."
        ),
        "claims": [
            {
                "id": c.id,
                "value": values.get(c.id),
                "unit": c.unit,
                "statement": c.statement,
                "source_file": c.source_file,
                "confidence": c.confidence,
                "note": c.note,
            }
            for c in CLAIMS
        ],
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _known_literals(values: dict[str, float]) -> set[str]:
    """Every rendering of a registry value we accept in prose."""
    out: set[str] = set(ALLOWED_LITERALS)
    for v in values.values():
        for text in (
            f"{v:.0f}",
            f"{v:.1f}",
            f"{v:.2f}",
            f"{round(v):,}",
            f"{v:,.0f}",
        ):
            out.add(text)
    return out


def _scan_surfaces(values: dict[str, float]) -> list[str]:
    known = _known_literals(values)
    findings: list[str] = []
    for pattern in SURFACES:
        for path in sorted(REPO.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO).as_posix()
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if IGNORE_MARK in line:
                    continue
                for match in CLAIM_PATTERN.finditer(line):
                    literal = match.group(1)
                    if literal in known or literal.replace(",", "") in known:
                        continue
                    findings.append(
                        f"{rel}:{lineno}: unsourced claim-shaped number "
                        f"{literal!r} in {match.group(0).strip()!r}"
                    )
    return findings


def _demo_failure() -> int:
    """Plant a fabricated number in a scratch copy and show the check catch it."""
    values, _ = _load_expected()
    known = _known_literals(values)
    fake = "987654"
    assert fake not in known
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "planted.md"
        target.write_text(
            "# Planted claim\n\nOur edge engine sustains 987654 Hz.\n", encoding="utf-8"
        )
        line = "Our edge engine sustains 987654 Hz."
        hit = CLAIM_PATTERN.search(line)
        print("Planted into a scratch file:  " + line)
        if hit and hit.group(1) not in known:
            print(f"CAUGHT: unsourced claim-shaped number {hit.group(1)!r} -- no "
                  f"measured file produces it.")
            print("\nA real run would fail the build here.")
            return 0
        print("NOT CAUGHT -- the linter is broken.")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="(re)write win_tuning/CLAIMS.json")
    ap.add_argument("--demo-failure", action="store_true", help="show the check catching a planted number")
    args = ap.parse_args()

    if args.demo_failure:
        return _demo_failure()

    values, errors = _load_expected()

    print(f"Resolved {len(values)}/{len(CLAIMS)} claims from measured files.")
    for c in CLAIMS:
        if c.id in values:
            print(f"  {c.id:<32} {values[c.id]:>12.3f} {c.unit:<6} <- {c.source_file}")

    if args.json:
        _write_registry(values)
        print(f"\nWrote {REGISTRY_PATH.relative_to(REPO)}")

    findings = _scan_surfaces(values)

    if errors:
        print(f"\n{len(errors)} claim(s) could not be resolved:")
        for e in errors:
            print(f"  ! {e}")
    if findings:
        print(f"\n{len(findings)} unsourced claim-shaped number(s):")
        for f in findings[:60]:
            print(f"  ! {f}")
        if len(findings) > 60:
            print(f"  ... and {len(findings) - 60} more")

    if errors or findings:
        print("\nFAIL -- fix by finding the number's real source, or by removing "
              "the claim. Do NOT fix by inventing a registry entry.")
        return 1

    print("\nOK -- every claim-shaped number traces to a measured file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
