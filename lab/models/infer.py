"""Numpy / Torch inference for a 2.0 s @ 10 Hz IMU window.

Input layout: (T, 6) or (6, T) with columns ax, ay, az, gx, gy, gz (SI).
T defaults to 20 (IO-VNBD rate). AVNet's 200-sample @ 200 Hz window is wrong.

    python lab/models/infer.py
    python lab/models/infer.py --weights lab/models/weights/avnet_tiny.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

_LAB = Path(__file__).resolve().parents[1]
if str(_LAB) not in sys.path:
    sys.path.insert(0, str(_LAB))

DEFAULT_WEIGHTS = Path(__file__).resolve().parent / "weights" / "avnet_tiny.pt"
WINDOW = 20
IN_CH = 6

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


@dataclass
class InferResult:
    speed: float
    psi_dot: float
    speed_var: float
    yaw_var: float
    roll_res: float
    pitch_res: float
    backend: str


def _as_tc(imu: np.ndarray) -> np.ndarray:
    x = np.asarray(imu, dtype=np.float32)
    if x.ndim == 3:
        x = x.reshape(x.shape[-2], x.shape[-1]) if x.shape[0] == 1 else x[0]
    if x.ndim != 2:
        raise ValueError(f"imu must be (T,6) or (6,T), got {x.shape}")
    if x.shape[0] == IN_CH and x.shape[1] != IN_CH:
        x = x.T
    if x.shape[1] != IN_CH:
        raise ValueError(f"expected 6 IMU channels, got {x.shape}")
    if x.shape[0] < 4:
        raise ValueError("window too short")
    if x.shape[0] != WINDOW:
        # crop or pad to the trained length
        if x.shape[0] > WINDOW:
            x = x[-WINDOW:]
        else:
            pad = np.repeat(x[:1], WINDOW - x.shape[0], axis=0)
            x = np.concatenate([pad, x], axis=0)
    return np.ascontiguousarray(x, dtype=np.float32)


def _physics_fallback(imu: np.ndarray) -> InferResult:
    """Match core/ts FrequencyDecoupledOdo when weights / torch are missing."""
    w = _as_tc(imu)
    n = w.shape[0]
    low = w.mean(axis=0)
    d = np.diff(w, axis=0)
    high_rms = float(np.sqrt(np.mean(d[:, :3] ** 2))) if n > 1 else 0.0
    speed = max(0.0, float(low[0]) * 0.0)  # no integrator state in one-shot
    # One-shot: |a| consistency is a weak speed prior; prefer 0 + high variance.
    a_mean = float(np.mean(np.linalg.norm(w[:, :3], axis=1)))
    gz = float(low[5])
    gy = float(low[4])
    # crude coordinated-turn yaw-rate mix (φ unknown → mostly gz)
    psi = gy * 0.0 + gz
    speed_var = 0.4 + 3.2 * high_rms
    if a_mean < 10.4 and abs(gz) < 0.05:
        speed_var *= 0.9
    return InferResult(
        speed=speed,
        psi_dot=float(psi),
        speed_var=float(speed_var),
        yaw_var=float(0.02 + high_rms),
        roll_res=0.0,
        pitch_res=0.0,
        backend="numpy-physics",
    )


def load_model(weights: str | Path | None = None):
    if torch is None:
        return None
    path = Path(weights) if weights is not None else DEFAULT_WEIGHTS
    if not path.is_file():
        return None
    try:
        from models.backbone import FrequencyDecoupledNet, build_model
    except ImportError:
        from backbone import FrequencyDecoupledNet, build_model  # type: ignore

    try:
        blob = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        blob = torch.load(path, map_location="cpu")
    if isinstance(blob, dict) and "state_dict" in blob:
        cfg = blob.get("config") or {}
        model = build_model(**{k: cfg[k] for k in ("in_ch", "window", "gru_hidden", "gru_layers", "conv_ch", "fuse") if k in cfg})
        model.load_state_dict(blob["state_dict"])
    elif isinstance(blob, dict) and any(k.startswith("gru.") or k.startswith("head.") for k in blob):
        model = FrequencyDecoupledNet()
        model.load_state_dict(blob)
    else:
        model = build_model()
        model.load_state_dict(blob)
    model.eval()
    return model


def infer_window(
    imu: np.ndarray,
    *,
    model=None,
    weights: str | Path | None = None,
) -> InferResult:
    """Run FrequencyDecoupledNet on one window. Falls back to a physics prior."""
    x = _as_tc(imu)
    net = model
    if net is None and torch is not None:
        net = load_model(weights)
    if net is None or torch is None:
        return _physics_fallback(x)
    xt = torch.from_numpy(x.T).unsqueeze(0)  # (1, 6, T)
    ctx = torch.no_grad()
    with ctx:
        y = net(xt).squeeze(0).cpu().numpy()
    return InferResult(
        speed=float(max(0.0, y[0])),
        psi_dot=float(y[1]),
        speed_var=float(np.exp(np.clip(y[4], -8.0, 4.0))),
        yaw_var=float(np.exp(np.clip(y[5], -8.0, 4.0))),
        roll_res=float(y[2]),
        pitch_res=float(y[3]),
        backend="torch",
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Infer speed / yaw-rate from a 20-sample IMU window")
    p.add_argument("--weights", type=str, default=str(DEFAULT_WEIGHTS))
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)
    from datasets.synthetic_tw import generate_windows

    batch = generate_windows(n_windows=1, seed=args.seed)
    res = infer_window(batch.imu[0], weights=args.weights)
    print(json.dumps({**asdict(res), "truth_speed": float(batch.speed[0]), "truth_psi_dot": float(batch.psi_dot[0])}, indent=2))


if __name__ == "__main__":
    main()
