"""Fast integrity checks for the AVNet data and deployment boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "lab" / "models" / "weights" / "avnet_tiny.onnx"
ANDROID_ASSET = ROOT / "android" / "app" / "src" / "main" / "assets" / "avnet_tiny.onnx"


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixed_shape(shape: list[Any]) -> list[int | str | None]:
    return [int(value) if isinstance(value, int) else value for value in shape]


def inspect_onnx_contract(path: Path | str) -> dict[str, Any]:
    """Return names and fixed shapes without running inference."""
    path = Path(path)
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        model_input = session.get_inputs()[0]
        model_output = session.get_outputs()[0]
        return {
            "input_name": model_input.name,
            "input_shape": _fixed_shape(model_input.shape),
            "output_name": model_output.name,
            "output_shape": _fixed_shape(model_output.shape),
        }
    except ImportError:
        import onnx

        model = onnx.load(str(path), load_external_data=False)

        def dimensions(value_info: Any) -> list[int | str | None]:
            result: list[int | str | None] = []
            for dim in value_info.type.tensor_type.shape.dim:
                if dim.HasField("dim_value"):
                    result.append(int(dim.dim_value))
                elif dim.HasField("dim_param"):
                    result.append(dim.dim_param)
                else:
                    result.append(None)
            return result

        model_input = model.graph.input[0]
        model_output = model.graph.output[0]
        return {
            "input_name": model_input.name,
            "input_shape": dimensions(model_input),
            "output_name": model_output.name,
            "output_shape": dimensions(model_output),
        }


def asset_integrity(
    model_path: Path | str = MODEL,
    asset_path: Path | str = ANDROID_ASSET,
) -> dict[str, Any]:
    """Check ONNX shape and byte parity when either deployment file exists."""
    model_path, asset_path = Path(model_path), Path(asset_path)
    report: dict[str, Any] = {
        "model": {"path": str(model_path), "exists": model_path.is_file()},
        "android_asset": {"path": str(asset_path), "exists": asset_path.is_file()},
    }
    for key, path in (("model", model_path), ("android_asset", asset_path)):
        if path.is_file():
            report[key]["sha256"] = sha256_file(path)
            report[key]["contract"] = inspect_onnx_contract(path)
    if model_path.is_file() and asset_path.is_file():
        report["hash_match"] = (
            report["model"]["sha256"] == report["android_asset"]["sha256"]
        )
    else:
        report["hash_match"] = None
    return report


def validate_android_latency_evidence(evidence: dict[str, Any]) -> None:
    """Validate measured phone evidence; never accepts workstation timings."""
    required = {
        "schema_version",
        "device_model",
        "android_version",
        "app_variant",
        "model_sha256",
        "runtime",
        "sample_count",
        "latency_ms",
        "captured_at_utc",
    }
    missing = sorted(required - evidence.keys())
    if missing:
        raise ValueError(f"missing Android latency evidence fields: {missing}")
    if evidence.get("measurement_scope") != "physical_android_device":
        raise ValueError("measurement_scope must be physical_android_device")
    latency = evidence["latency_ms"]
    for key in ("p50", "p95", "max"):
        value = latency.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"latency_ms.{key} must be a non-negative number")
    if int(evidence["sample_count"]) < 1:
        raise ValueError("sample_count must be >= 1")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check AVNet ONNX shape and asset hash")
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--asset", type=Path, default=ANDROID_ASSET)
    args = parser.parse_args(argv)
    report = asset_integrity(args.model, args.asset)
    print(json.dumps(report, indent=2))
    contracts = [
        item["contract"]
        for item in (report["model"], report["android_asset"])
        if item["exists"]
    ]
    good_shapes = all(
        contract["input_shape"] == [1, 6, 20]
        and contract["output_shape"] == [1, 6]
        for contract in contracts
    )
    good_hash = report["hash_match"] is not False
    return 0 if good_shapes and good_hash else 1


if __name__ == "__main__":
    raise SystemExit(main())
