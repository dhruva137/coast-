"""Leaderboard / comparison table over experiment result directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import HonestyError, assert_closed_loop_present, forbid_rmse_only_win

_HERE = Path(__file__).resolve().parent
DEFAULT_RESULTS_ROOT = _HERE.parent / "results"

COMPARE_COLUMNS = (
    ("name", "name"),
    ("status", "status"),
    ("per_window_rmse_mps", "pw_rmse"),
    ("hold_baseline_rmse_mps", "hold_rmse"),
    ("rmse_vs_hold_mps", "vs_hold"),
    ("closed_loop_60s_distance_error_m", "cl_60s_m"),
    ("outage_drift_pct", "drift_%"),
    ("mount_swap_delta_rmse_mps", "mount_drmse"),
    ("params", "params"),
    ("onnx_size_bytes", "onnx_B"),
    ("on_device_latency_ms", "lat_ms"),
)


def load_run(path: Path) -> dict[str, Any]:
    metrics_path = path / "metrics.json" if path.is_dir() else path
    if metrics_path.is_dir():
        metrics_path = metrics_path / "metrics.json"
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert_closed_loop_present(data)
    forbid_rmse_only_win(data)
    data.setdefault("name", path.name if path.is_dir() else path.parent.name)
    return data


def collect_runs(results_root: Path) -> list[dict[str, Any]]:
    root = Path(results_root)
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        m = child / "metrics.json"
        if not m.is_file():
            continue
        try:
            rows.append(load_run(child))
        except (HonestyError, json.JSONDecodeError, OSError) as exc:
            rows.append(
                {
                    "name": child.name,
                    "status": "invalid",
                    "closed_loop_60s_distance_error_m": None,
                    "closed_loop_note": f"failed to load: {exc}",
                    "notes": [str(exc)],
                }
            )
    return rows


def _cell(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def format_table(rows: list[dict[str, Any]]) -> str:
    headers = [h for _, h in COMPARE_COLUMNS]
    body: list[list[str]] = []
    for r in rows:
        body.append([_cell(r.get(k)) for k, _ in COMPARE_COLUMNS])

    widths = [len(h) for h in headers]
    for row in body:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    lines = [
        fmt_row(headers),
        "| " + " | ".join("-" * w for w in widths) + " |",
    ]
    lines.extend(fmt_row(r) for r in body)
    lines.append("")
    lines.append(
        "Rule: per-window RMSE alone is not a win. "
        "`cl_60s_m` must be present (value or null with note in metrics.json)."
    )
    return "\n".join(lines)


def write_leaderboard(
    results_root: Path | None = None,
    *,
    out_path: Path | None = None,
) -> str:
    root = Path(results_root) if results_root else DEFAULT_RESULTS_ROOT
    table = format_table(collect_runs(root))
    dest = out_path or (root / "leaderboard.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "# Experiment leaderboard\n\n" + table + "\n",
        encoding="utf-8",
    )
    return table


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare lab experiment results")
    ap.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
        help="Directory containing results/<name>/metrics.json",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path for leaderboard.md (default: <results-root>/leaderboard.md)",
    )
    args = ap.parse_args(argv)
    table = write_leaderboard(args.results_root, out_path=args.out)
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
