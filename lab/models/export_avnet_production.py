"""Train and export the production AVNet model after LFO gates pass.

This is deliberately separate from ``train_avnet.py`` and the leave-file-out
runner. It trains once on every clean, CAN-labelled drive and exports the raw-SI
Android contract: input ``imu`` [1, 6, 20], output ``outputs`` [1, 6].

Nothing is copied into Android assets unless ``--copy-android-assets`` is
explicitly passed. Existing outputs also require ``--overwrite``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from backbone import avnet_loss, build_model, default_config  # noqa: E402
from pipeline_integrity import inspect_onnx_contract, sha256_file  # noqa: E402
from speed_data import IMU_AXES, IMU_UNITS, clean_drives, load_corpus  # noqa: E402

DEFAULT_OUTPUT = _HERE / "weights" / "avnet_tiny.onnx"
ANDROID_ASSET = _ROOT / "android" / "app" / "src" / "main" / "assets" / "avnet_tiny.onnx"
SEED = 26168
INPUT_SHAPE = (1, 6, 20)
OUTPUT_SHAPE = (1, 6)


def _training_arrays() -> tuple[np.ndarray, np.ndarray, list[str]]:
    drives = clean_drives(load_corpus(can_only=True, verbose=True))
    if not drives:
        raise RuntimeError("no clean CAN-labelled IO-VNBD drives found")
    imu = np.concatenate([drive.imu for drive in drives], axis=0)
    speed = np.concatenate([drive.speed for drive in drives], axis=0)
    yaw = np.concatenate([drive.yaw_rate for drive in drives], axis=0)
    zeros = np.zeros_like(speed)
    targets = np.stack([speed, yaw, zeros, zeros], axis=1).astype(np.float32)
    # Authoritative windows are (N,T,C); Android/ONNX is channel-major (N,C,T).
    inputs = np.ascontiguousarray(np.transpose(imu, (0, 2, 1)), dtype=np.float32)
    return inputs, targets, [drive.name for drive in drives]


def train_production(
    *,
    epochs: int,
    batch_size: int,
    lr: float,
    device_name: str,
) -> tuple[torch.nn.Module, dict[str, Any]]:
    """Train on all clean windows with raw SI input and no standardisation."""
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(device_name)

    imu, targets, drive_names = _training_arrays()
    dataset = TensorDataset(torch.from_numpy(imu), torch.from_numpy(targets))
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )
    model = build_model().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    started = time.perf_counter()
    history: list[float] = []
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        seen = 0
        for xb, yb in loader:
            xb = xb.to(device, non_blocking=device.type == "cuda")
            yb = yb.to(device, non_blocking=device.type == "cuda")
            optimizer.zero_grad(set_to_none=True)
            loss = avnet_loss(model(xb), yb)["loss"]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
            total += float(loss.item()) * xb.shape[0]
            seen += xb.shape[0]
        scheduler.step()
        mean_loss = total / max(seen, 1)
        history.append(mean_loss)
        print(f"epoch {epoch:02d}/{epochs} loss={mean_loss:.5f}")

    metadata = {
        "purpose": "production_export",
        "training_scope": "all_clean_can_drives",
        "drives": drive_names,
        "n_windows": len(dataset),
        "epochs": epochs,
        "device": str(device),
        "input_shape": list(INPUT_SHAPE),
        "output_shape": list(OUTPUT_SHAPE),
        "input_units": list(IMU_UNITS),
        "input_axes": list(IMU_AXES),
        "normalisation": "none_raw_si_including_gravity",
        "train_seconds": time.perf_counter() - started,
        "final_loss": history[-1],
    }
    return model.cpu().eval(), metadata


def export_production(
    model: torch.nn.Module,
    output: Path,
    *,
    metadata: dict[str, Any],
    overwrite: bool,
    copy_android_assets: bool,
) -> dict[str, Any]:
    """Export and verify the fixed production contract, then optionally copy."""
    output = Path(output)
    if output.exists() and not overwrite:
        raise FileExistsError(f"{output} exists; pass --overwrite to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    dummy = torch.zeros(*INPUT_SHAPE, dtype=torch.float32)
    with torch.no_grad():
        if tuple(model(dummy).shape) != OUTPUT_SHAPE:
            raise RuntimeError("PyTorch model violates output [1,6] contract")
    torch.onnx.export(
        model,
        dummy,
        str(temporary),
        input_names=["imu"],
        output_names=["outputs"],
        opset_version=14,
        dynamo=False,
    )
    temporary.replace(output)
    contract = inspect_onnx_contract(output)
    if (
        contract["input_shape"] != list(INPUT_SHAPE)
        or contract["output_shape"] != list(OUTPUT_SHAPE)
    ):
        raise RuntimeError(f"exported ONNX contract mismatch: {contract}")

    metadata = {**metadata, **contract, "sha256": sha256_file(output)}
    metadata_path = output.with_suffix(".production.json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if copy_android_assets:
        ANDROID_ASSET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, ANDROID_ASSET)
        if sha256_file(output) != sha256_file(ANDROID_ASSET):
            raise RuntimeError("Android asset hash differs after copy")
        metadata["android_asset"] = str(ANDROID_ASSET)
    return metadata


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train all clean drives and export AVNet production ONNX")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1.5e-3)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--copy-android-assets", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    model, metadata = train_production(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device_name=args.device,
    )
    result = export_production(
        model,
        args.output,
        metadata=metadata,
        overwrite=args.overwrite,
        copy_android_assets=args.copy_android_assets,
    )
    print(f"exported {args.output} sha256={result['sha256']}")
    if args.copy_android_assets:
        print(f"copied {ANDROID_ASSET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
