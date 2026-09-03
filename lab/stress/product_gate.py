#!/usr/bin/env python3
"""Semantically explicit readiness gates for the SIH26168 navigation SDK.

``prototype`` preserves the historical research checks, but can only emit
``RESEARCH_PROTOTYPE_PASS``. ``deployment`` is the default and requires
corrected-axis alignment, real road-speed ISRO performance, calibrated
covariance, and real two-wheeler field evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
HARDENED = RESULTS / "hardened_report.json"
BASIC = RESULTS / "report.json"
ALIGNMENT = RESULTS / "alignment" / "alignment_report.json"
RELIABILITY = Path(__file__).resolve().parents[1] / "proof" / "results" / "reliability.json"
TWO_WHEELER_MANIFEST = RESULTS / "two_wheeler_field_manifest.json"

RATIO_LO = 0.85
RATIO_HI = 1.15
ROAD_SPEED_SITES = {"mid_route", "high_speed"}


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _adv_pass(hardened: dict | None, basic: dict | None) -> tuple[bool, str]:
    if hardened and "adversarial_tw" in hardened:
        v = hardened["adversarial_tw"].get("verdict", "MISSING")
        return v == "PASS_CLAIM", f"adversarial_tw={v}"
    if basic and "adversarial_tw" in basic:
        v = basic["adversarial_tw"].get("verdict", "MISSING")
        return v == "PASS_CLAIM", f"adversarial_tw(basic)={v}"
    # Basic battery nested shape
    if basic:
        for key in ("adversarial", "adversarial_two_wheeler"):
            if key in basic:
                v = basic[key].get("verdict", "MISSING")
                return v == "PASS_CLAIM", f"{key}={v}"
    return False, "adversarial_tw=MISSING"


def _car_sanity(hardened: dict | None, basic: dict | None) -> tuple[bool, str]:
    if hardened and hardened.get("car_lean_sanity"):
        block = hardened["car_lean_sanity"]
        ok = bool(block.get("ok"))
        n = len(block.get("rows") or [])
        bad = [r for r in (block.get("rows") or []) if not r.get("ok")]
        detail = f"hardened sanity rows={n} bad={len(bad)}"
        return ok and n > 0, detail

    # Derive from hardened rows
    if hardened and hardened.get("rows"):
        by: dict[tuple, dict] = {}
        for r in hardened["rows"]:
            by.setdefault((r["csv"], r["site"], r["deny_s"]), {})[r["method"]] = r
        ratios = []
        for methods in by.values():
            car = methods.get("car_bias")
            lean = methods.get("idr_bias")
            if not car or not lean:
                continue
            ratio = lean["final_m"] / max(car["final_m"], 1e-6)
            ratios.append(ratio)
        if ratios:
            ok = all(RATIO_LO <= r <= RATIO_HI for r in ratios)
            return ok, f"derived ratios n={len(ratios)} min={min(ratios):.3f} max={max(ratios):.3f}"

    # Basic report: car_vs_lean_final_ratio on trials
    if basic and basic.get("files"):
        ratios = []
        for f in basic["files"]:
            for trial in f.get("trials") or []:
                r = trial.get("car_vs_lean_final_ratio")
                if r is not None:
                    ratios.append(float(r))
        if ratios:
            ok = all(RATIO_LO <= r <= RATIO_HI for r in ratios)
            return ok, f"basic ratios n={len(ratios)} min={min(ratios):.3f} max={max(ratios):.3f}"

    return False, "car_lean_sanity=MISSING"


def _map_aided_60s(hardened: dict | None) -> tuple[bool, str, list[dict]]:
    if not hardened or not hardened.get("rows"):
        return False, "hardened_report missing rows", []
    hits = []
    for r in hardened["rows"]:
        if float(r.get("deny_s", 0)) != 60.0:
            continue
        method = str(r.get("method", ""))
        if not method.endswith("_map"):
            continue
        if method.endswith("_mapblind") or method.endswith("_mapproj"):
            continue
        verd = str(r.get("verdict", ""))
        if verd.startswith("PASS"):
            hits.append(r)
    scenarios = {(r["csv"], r["site"]) for r in hits}
    ok = len(scenarios) >= 1
    return (
        ok,
        (
            f"map_aided_60s_PASS methods={len(hits)} "
            f"independent_scenarios={len(scenarios)}"
        ),
        hits,
    )


def _alignment_pass(alignment: dict | None) -> tuple[bool, str]:
    common = (alignment or {}).get("common_mapping") or {}
    count = int(common.get("files_above_threshold", 0))
    ok = (
        (alignment or {}).get("verdict") == "PASS_ALIGNMENT"
        and common.get("exists") is True
        and count >= 2
    )
    return ok, (
        f"verdict={(alignment or {}).get('verdict', 'MISSING')} "
        f"files_above_threshold={count}/2"
    )


def _road_speed_isro(basic: dict | None) -> tuple[bool, str]:
    trials: list[dict] = []
    for file_block in (basic or {}).get("files") or []:
        for trial in file_block.get("trials") or []:
            if trial.get("requested_deny_s") != 60:
                continue
            if trial.get("site") not in ROAD_SPEED_SITES:
                continue
            score = (trial.get("scores") or {}).get("idr_lean") or {}
            gate = (trial.get("gates") or {}).get("idr_lean") or {}
            drift = score.get("drift_pct")
            m_per_km = gate.get("m_per_km")
            if drift is None or m_per_km is None:
                continue
            trials.append(
                {
                    "drift_pct": float(drift),
                    "m_per_km": float(m_per_km),
                    "pass": float(drift) < 10.0 and float(m_per_km) < 100.0,
                }
            )
    passed = sum(row["pass"] for row in trials)
    rate = passed / len(trials) if trials else 0.0
    return len(trials) > 0 and rate >= 0.80, (
        f"idr_lean real 60s mid/high-speed trials={len(trials)} "
        f"meeting drift<10% AND <100m/km={passed} ({rate:.1%}; required >=80%)"
    )


def _covariance_pass(reliability: dict | None) -> tuple[bool, str]:
    method = ((reliability or {}).get("methods") or {}).get("idr_lean_bias") or {}
    coverage = method.get("coverage_95_endpoint")
    calibrated = (reliability or {}).get("calibrated_coverage_target")
    coverage_ok = coverage is not None and float(coverage) >= 0.90
    calibrated_ok = (
        isinstance(calibrated, dict)
        and calibrated.get("documented") is True
        and calibrated.get("target") is not None
        and bool(calibrated.get("rationale"))
    )
    coverage_text = "MISSING" if coverage is None else f"{float(coverage):.1%}"
    mode = "explicit calibrated target documented" if calibrated_ok else "none"
    return coverage_ok or calibrated_ok, (
        f"nominal-95% endpoint coverage={coverage_text} (required >=90%) "
        f"or calibrated_target={mode}"
    )


def _two_wheeler_logs(manifest: dict | None) -> tuple[bool, str]:
    logs = (manifest or {}).get("logs") or []
    qualifying = [
        log
        for log in logs
        if str(log.get("vehicle_type", "")).lower()
        in {"bicycle", "motorcycle", "scooter", "two-wheeler", "two_wheeler"}
        and log.get("real_field_log") is True
    ]
    return len(qualifying) >= 10, (
        f"qualifying real two-wheeler field logs={len(qualifying)} (required >=10)"
    )


def _print_checks(title: str, checks: list[tuple[str, bool, str]]) -> bool:
    print(f"# {title}")
    print()
    for name, ok, detail in checks:
        print(f"- [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return all(ok for _, ok, _ in checks)


def _run_prototype(hardened: dict | None, basic: dict | None) -> int:
    adv_ok, adv_detail = _adv_pass(hardened, basic)
    car_ok, car_detail = _car_sanity(hardened, basic)
    map_ok, map_detail, _ = _map_aided_60s(hardened)
    checks = [
        ("injected_adversarial_TW_PASS_CLAIM", adv_ok, adv_detail),
        ("real_car_lean_approx_car_sanity", car_ok, car_detail),
        ("map_aided_60s_PASS_COMPETITIVE+", map_ok, map_detail),
    ]
    ok = _print_checks("SIH26168 research prototype gate", checks)
    print()
    print("NOT DEPLOYMENT READINESS: injected lean and competitive map-aided evidence")
    print("do not establish ISRO compliance or real two-wheeler field readiness.")
    status = "RESEARCH_PROTOTYPE_PASS" if ok else "RESEARCH_PROTOTYPE_FAIL"
    print(f"STATUS: {status}")
    return 0 if ok else 1


def _run_deployment(basic: dict | None) -> int:
    alignment = _load(ALIGNMENT)
    reliability = _load(RELIABILITY)
    field_manifest = _load(TWO_WHEELER_MANIFEST)
    checks = [
        ("corrected_alignment_on_2+_files", *_alignment_pass(alignment)),
        ("real_60s_road_speed_ISRO_rate", *_road_speed_isro(basic)),
        ("covariance_calibration", *_covariance_pass(reliability)),
        ("real_two_wheeler_field_logs", *_two_wheeler_logs(field_manifest)),
    ]
    ok = _print_checks("SIH26168 deployment readiness gate", checks)
    print()
    status = "DEPLOYMENT_READY_PASS" if ok else "DEPLOYMENT_READY_FAIL"
    print(f"STATUS: {status}")
    if not ok:
        print("Deployment and two-wheeler readiness claims remain blocked.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        choices=("prototype", "deployment"),
        default="deployment",
        help="gate strength (default: deployment)",
    )
    args = parser.parse_args(argv)

    hardened = _load(HARDENED)
    basic = _load(BASIC)
    if args.level == "prototype":
        return _run_prototype(hardened, basic)
    return _run_deployment(basic)


if __name__ == "__main__":
    raise SystemExit(main())
