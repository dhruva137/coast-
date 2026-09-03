"""CPU trainer for AVNet-tiny (FrequencyDecoupledNet).

IO-VNBD is 10 Hz. Windows are 2.0 s → 20 samples, not 200 @ 200 Hz.

Trains 8–15 epochs on synthetic coordinated-turn + car windows. Default
device is CPU. Target wall time < 3 minutes.

From repo root::

    python lab/models/train_avnet.py
    python lab/models/train_avnet.py --epochs 12 --seed 7

Writes
    lab/models/weights/avnet_tiny.pt
    lab/models/weights/metrics.json
    lab/models/weights/avnet_tiny.onnx   (best-effort)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, random_split

_LAB = Path(__file__).resolve().parents[1]
if str(_LAB) not in sys.path:
    sys.path.insert(0, str(_LAB))

from datasets.synthetic_tw import WindowBatch, generate_windows  # noqa: E402
from models.backbone import avnet_loss, build_model, default_config  # noqa: E402

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
CKPT_NAME = "avnet_tiny.pt"
METRICS_NAME = "metrics.json"
ONNX_NAME = "avnet_tiny.onnx"


class _WinDS(Dataset):
    def __init__(self, imu: np.ndarray, y: np.ndarray):
        self.imu = torch.from_numpy(np.ascontiguousarray(imu)).float()
        self.y = torch.from_numpy(np.ascontiguousarray(y)).float()

    def __len__(self) -> int:
        return int(self.imu.shape[0])

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.imu[i], self.y[i]


def _rmse(pred: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - target) ** 2)))


@torch.no_grad()
def evaluate(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    ps, ts = [], []
    for imu, y in loader:
        imu = imu.to(device)
        out = model(imu).cpu().numpy()
        ps.append(out)
        ts.append(y.numpy())
    p = np.concatenate(ps, axis=0)
    t = np.concatenate(ts, axis=0)
    return {
        "rmse_speed_mps": _rmse(p[:, 0], t[:, 0]),
        "rmse_yaw_rate_rps": _rmse(p[:, 1], t[:, 1]),
        "rmse_yaw_rate_dps": _rmse(p[:, 1], t[:, 1]) * (180.0 / np.pi),
        "rmse_roll_res_rad": _rmse(p[:, 2], t[:, 2]),
        "rmse_pitch_res_rad": _rmse(p[:, 3], t[:, 3]),
    }


@torch.no_grad()
def time_inference_ms(model: torch.nn.Module, device: torch.device, window: int = 20, repeats: int = 40) -> float:
    x = torch.randn(1, 6, window, device=device)
    for _ in range(8):
        model(x)
    t0 = time.perf_counter()
    for _ in range(repeats):
        model(x)
    return (time.perf_counter() - t0) / repeats * 1000.0


def export_onnx(model: torch.nn.Module, path: Path, window: int = 20) -> str | None:
    dummy = torch.randn(1, 6, window)
    model_cpu = model.to("cpu").eval()
    kwargs = dict(
        input_names=["imu"],
        output_names=["outputs"],
        opset_version=14,
    )
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                torch.onnx.export(model_cpu, dummy, str(path), dynamo=False, **kwargs)
            except TypeError:
                torch.onnx.export(model_cpu, dummy, str(path), **kwargs)
        return str(path)
    except Exception as exc:  # onnx / onnxscript optional
        print(f"ONNX export skipped: {exc}")
        return None


def train(
    *,
    epochs: int = 12,
    batch_size: int = 64,
    n_windows: int = 4096,
    seed: int = 7,
    lr: float = 1.5e-3,
) -> dict:
    if not 8 <= int(epochs) <= 15:
        raise ValueError("epochs must be in [8, 15] for the CPU time budget")
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = torch.device("cpu")

    batch: WindowBatch = generate_windows(n_windows=n_windows, seed=seed)
    imu = np.transpose(batch.imu, (0, 2, 1))  # (N, 6, T)
    y = batch.y()
    ds = _WinDS(imu, y)
    n_val = max(256, int(0.18 * len(ds)))
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(
        ds, [n_train, n_val], generator=torch.Generator().manual_seed(seed)
    )
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = build_model().to(device)
    n_params = model.count_parameters()
    if not 50_000 <= n_params <= 200_000:
        raise RuntimeError(f"param count {n_params} outside the 50k–200k tiny-net budget")
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    t0 = time.perf_counter()
    history: list[dict[str, float]] = []
    for ep in range(1, epochs + 1):
        model.train()
        running = 0.0
        n_seen = 0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(xb)
            parts = avnet_loss(pred, yb)
            parts["loss"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step()
            bs = xb.size(0)
            running += float(parts["loss"].item()) * bs
            n_seen += bs
        sched.step()
        val = evaluate(model, val_loader, device)
        row = {"epoch": ep, "train_loss": running / max(n_seen, 1), **val}
        history.append(row)
        print(
            f"epoch {ep:02d}/{epochs}  loss={row['train_loss']:.4f}  "
            f"RMSE v={val['rmse_speed_mps']:.3f} m/s  "
            f"yaw={val['rmse_yaw_rate_dps']:.2f} deg/s"
        )

    train_s = time.perf_counter() - t0
    val = evaluate(model, val_loader, device)
    infer_ms = time_inference_ms(model, device, window=int(default_config()["window"]))

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = default_config()
    metrics = {
        **val,
        "n_params": int(n_params),
        "epochs": int(epochs),
        "device": "cpu",
        "window_samples": int(cfg["window"]),
        "hz": float(cfg["hz"]),
        "window_s": 2.0,
        "cutoff_hz": float(cfg["cutoff_hz"]),
        "train_seconds": float(train_s),
        "infer_ms_cpu": float(infer_ms),
        "n_train": int(n_train),
        "n_val": int(n_val),
        "seed": int(seed),
        "source": "synthetic",
        "history": history,
    }
    ckpt_path = WEIGHTS_DIR / CKPT_NAME
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": cfg,
            "n_params": int(n_params),
            "metrics": {k: v for k, v in metrics.items() if k != "history"},
        },
        ckpt_path,
    )
    metrics_path = WEIGHTS_DIR / METRICS_NAME
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    onnx_path = export_onnx(model, WEIGHTS_DIR / ONNX_NAME, window=int(cfg["window"]))
    metrics["ckpt"] = str(ckpt_path)
    metrics["onnx"] = onnx_path
    print(
        f"saved {ckpt_path}  params={n_params}  "
        f"{train_s:.1f}s  infer={infer_ms:.2f} ms"
    )
    if onnx_path:
        print(f"saved {onnx_path}")
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train AVNet-tiny on CPU synthetic windows")
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--n-windows", type=int, default=4096)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--lr", type=float, default=1.5e-3)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    train(
        epochs=args.epochs,
        batch_size=args.batch_size,
        n_windows=args.n_windows,
        seed=args.seed,
        lr=args.lr,
    )


if __name__ == "__main__":
    main()
