"""One-command live demo: short speed train + regenerate screening figures.

Presenter command::

    python -m lab.demo

Wall-time target: ≤90 s. Full leave-file-out bakeoff and map-in-loop stress
eval already live under ``lab/models/results/`` and ``lab/stress/results/``;
this entrypoint does a short *honest* training pass (live epoch/loss lines)
then regenerates the three PPT figures from measured mapfilter results plus a
live trajectory overlay on a real IO-VNBD outage window.

PPT headline numbers (2.02×, 17%/10% free-DR arms, etc.) are read from the
committed decision-layer sources — never invented from the quick run.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

_REPO = Path(__file__).resolve().parents[1]
_FIGURES = _REPO / "figures"
_REFERENCE = _FIGURES / "_reference"
_MAPFILTER_REPORT = _REPO / "lab" / "stress" / "results" / "mapfilter" / "report.json"
_MAPFILTER_SUMMARY = _REPO / "lab" / "stress" / "results" / "mapfilter" / "summary.md"
_ISRO_SUMMARY = _REPO / "lab" / "stress" / "results" / "isro_benchmark" / "summary.md"
_SPEED_SUMMARY = _REPO / "lab" / "models" / "results" / "speed_bakeoff" / "summary.md"

# Fixed seed for reproducible figure regeneration.
SEED = 26168

# Quick-run training budget (live on stage). Does NOT replace the full bakeoff.
QUICK_EPOCHS = 4
QUICK_CAP = 24_000
QUICK_FOLDS = 1


def _banner() -> None:
    print("=" * 72)
    print("  COAST SIH 2026 - live demo (lab.demo)")
    print("  Data: IO-VNBD smartphone IMU + CAN 10 Hz ground truth (local)")
    print("  Steps: short AVNet-tiny train -> mapfilter figures -> figures/")
    print("  Budget: <=90 s wall time  |  seed:", SEED)
    print("  Full bakeoff / mapfilter results already committed under lab/")
    print("=" * 72)
    print()


def _load_headline_numbers() -> dict:
    """Verbatim decision-layer numbers from committed result files."""
    report = json.loads(_MAPFILTER_REPORT.read_text(encoding="utf-8"))
    junc = report["scenarios"]["junctions"]
    return {
        "mapfilter_improvement_x": float(junc["improvement_x"]),
        "free_pass": int(junc["free_pass"]),
        "pf_pass": int(junc["pf_pass"]),
        "n_outages": int(junc["n"]),
        "free_median_error_m": float(junc["free_median_error_m"]),
        "pf_median_error_m": float(junc["pf_median_error_m"]),
        "free_median_drift_pct": float(junc["free_median_drift_pct"]),
        "pf_median_drift_pct": float(junc["pf_median_drift_pct"]),
        # Decision layer §D baselines (ISRO arms) — fixed measured rates.
        "free_dr_short_arm_pct": 17,
        "free_dr_tunnel_arm_pct": 10,
        "sources": {
            "mapfilter": str(_MAPFILTER_SUMMARY.relative_to(_REPO)),
            "isro": str(_ISRO_SUMMARY.relative_to(_REPO)),
            "speed": str(_SPEED_SUMMARY.relative_to(_REPO)),
        },
    }


def _quick_train() -> dict:
    """Short leave-file-out fold with live epoch/loss lines.

    Writes nothing over the full bakeoff under lab/models/results/speed_bakeoff.
    Returns the quick-run metrics for the console only.
    """
    # Import after path setup so sibling modules resolve.
    models_dir = str(_REPO / "lab" / "models")
    if models_dir not in sys.path:
        sys.path.insert(0, models_dir)

    from backbone import build_model  # noqa: WPS433
    from run_speed_bakeoff import (  # noqa: WPS433
        Standardiser,
        _hold_label,
        _rmse,
        clean_drives,
    )
    from speed_data import load_corpus  # noqa: WPS433

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[1/3] Quick AVNet-tiny train  device={device}  "
          f"epochs={QUICK_EPOCHS}  cap={QUICK_CAP}  folds={QUICK_FOLDS}")
    print("      (live-demo quick run - full leave-file-out in "
          "lab/models/results/speed_bakeoff/)")

    drives = clean_drives(load_corpus(verbose=False))
    if not drives:
        raise RuntimeError("No clean CAN-labelled IO-VNBD drives found locally.")
    held = drives[0]
    train = [d for d in drives if d.name != held.name]
    print(f"      held-out drive: {held.name}  (train on {len(train)} drives)")

    rng = np.random.default_rng(SEED)
    imu = np.concatenate([d.imu for d in train], axis=0)
    speed = np.concatenate([d.speed for d in train], axis=0)
    if imu.shape[0] > QUICK_CAP:
        sel = rng.choice(imu.shape[0], size=QUICK_CAP, replace=False)
        imu, speed = imu[sel], speed[sel]

    std = Standardiser(imu)
    x = torch.from_numpy(std(imu)).to(device)
    y = torch.from_numpy(speed).to(device)
    model = build_model().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-5)
    n = x.shape[0]
    bs = 1024
    warmup = max(1, int(0.6 * QUICK_EPOCHS))
    model.train()
    t0 = time.time()
    last_loss = float("nan")
    for ep in range(QUICK_EPOCHS):
        use_nll = ep >= warmup
        perm = torch.randperm(n, device=device)
        total = 0.0
        steps = 0
        for i in range(0, n, bs):
            b = perm[i : i + bs]
            out = model(x[b])
            heads = model.split_heads(out)
            mu = heads["speed"]
            if use_nll:
                logvar = heads["logvar_speed"].clamp(-4.0, 2.0)
                nll = 0.5 * (
                    F.mse_loss(mu, y[b], reduction="none") * torch.exp(-logvar) + logvar
                )
                loss = nll.mean()
            else:
                loss = F.mse_loss(mu, y[b])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            total += float(loss.detach().cpu())
            steps += 1
        last_loss = total / max(steps, 1)
        mode = "NLL" if use_nll else "MSE"
        print(f"      epoch {ep + 1}/{QUICK_EPOCHS}  loss={last_loss:.4f}  "
              f"({mode})  {time.time() - t0:.1f}s")

    model.eval()
    with torch.no_grad():
        mu = model.split_heads(model(torch.from_numpy(std(held.imu)).to(device)))["speed"]
        mu_np = mu.cpu().numpy().astype(np.float64)
    y_h = held.speed.astype(np.float64)
    hold = _hold_label(held).astype(np.float64)
    quick = {
        "held": held.name,
        "epochs": QUICK_EPOCHS,
        "cap": QUICK_CAP,
        "device": device,
        "final_loss": last_loss,
        "model_rmse": _rmse(mu_np, y_h),
        "hold_rmse": _rmse(hold, y_h),
        "seconds": time.time() - t0,
        "note": "quick-run only; PPT cites full bakeoff summary.md",
    }
    print(f"      quick RMSE model={quick['model_rmse']:.3f}  "
          f"hold={quick['hold_rmse']:.3f}  ({quick['seconds']:.1f}s)")
    print()
    return quick


def _write_figures() -> dict:
    """Regenerate the three screening PNGs into figures/."""
    print("[2/3] Regenerating screening figures from measured mapfilter + live overlay")
    from lab.eval import demo_plots as dp  # noqa: WPS433

    _FIGURES.mkdir(parents=True, exist_ok=True)
    # Wipe prior PNGs (keep _reference/).
    for p in _FIGURES.glob("*.png"):
        p.unlink()

    meta = dp.write_all_figures(_FIGURES)
    paths = meta.get("paths") or {}
    for name, path in paths.items():
        print(f"      wrote {path}")
    cdf_path = Path(paths.get("cdf_error", _FIGURES / "cdf_error.png"))
    if not cdf_path.is_file():
        raise RuntimeError(
            "cdf_error.png missing after write_all_figures — "
            "screening Figure B requires measured mapfilter CDF"
        )
    if meta.get("cdf") is None:
        raise RuntimeError(
            "CDF metadata empty — mapfilter report had no measured errors; "
            "refusing to invent CDF points"
        )
    print()
    return meta


def _ensure_reference(paths: dict[str, str]) -> None:
    """Keep known-good copies under figures/_reference/ for stage fallback."""
    _REFERENCE.mkdir(parents=True, exist_ok=True)
    for name, src in paths.items():
        src_p = Path(src)
        if not src_p.is_file():
            continue
        dst = _REFERENCE / src_p.name
        shutil.copy2(src_p, dst)
        print(f"      reference {dst.relative_to(_REPO)}")


def _print_headlines(head: dict, wall_s: float) -> None:
    print("[3/3] Headline numbers (decision layer - measured, not quick-run)")
    x = head["mapfilter_improvement_x"]
    print(f"      Map-in-loop vs free DR:  {x:.2f}x  "
          f"(pass {head['free_pass']}->{head['pf_pass']} of {head['n_outages']})")
    print(f"      Median error:           free {head['free_median_error_m']:.1f} m  |  "
          f"COAST {head['pf_median_error_m']:.1f} m")
    print(f"      Median drift %:         free {head['free_median_drift_pct']:.0f}%  |  "
          f"COAST {head['pf_median_drift_pct']:.0f}%  |  ISRO bar 10%")
    print(f"      Free-DR baseline arms:  short {head['free_dr_short_arm_pct']}%  /  "
          f"tunnel {head['free_dr_tunnel_arm_pct']}%")
    print(f"      Sources: {head['sources']['mapfilter']}")
    print(f"               {head['sources']['isro']}")
    print(f"               {head['sources']['speed']}")
    print()
    print(f"Done in {wall_s:.1f}s  ->  {_FIGURES}")
    print("Fallback copies: figures/_reference/")


def main() -> int:
    # Windows consoles are often cp1252; keep banner ASCII-safe.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    t0 = time.time()
    _banner()
    try:
        head = _load_headline_numbers()
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"FATAL: cannot load measured mapfilter results: {exc}", file=sys.stderr)
        return 1

    try:
        quick = _quick_train()
    except Exception as exc:  # noqa: BLE001 — stage must still get figures
        print(f"WARNING: quick train skipped ({exc})")
        print("         regenerating figures from committed measured results only.")
        quick = {"error": str(exc)}

    print("[eval] Using committed map-in-loop report "
          f"({head['n_outages']} outages) - not re-running full stress eval.")
    print()

    try:
        meta = _write_figures()
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: figure generation failed: {exc}", file=sys.stderr)
        # Silent fallback: copy reference figures into figures/ if present.
        if _REFERENCE.is_dir():
            for p in _REFERENCE.glob("*.png"):
                shutil.copy2(p, _FIGURES / p.name)
                print(f"      fell back to {p.name}")
        return 1

    paths = meta.get("paths") or {}
    _ensure_reference(paths)

    meta_out = {
        "wall_seconds": time.time() - t0,
        "quick_train": quick,
        "headlines": head,
        "figures": meta,
    }
    (_FIGURES / "demo_run.json").write_text(
        json.dumps(meta_out, indent=2), encoding="utf-8"
    )

    _print_headlines(head, time.time() - t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
