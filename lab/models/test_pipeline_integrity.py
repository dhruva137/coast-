from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "lab"
MODELS = LAB / "models"
for path in (LAB, MODELS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from datasets.io_vnbd import _batch_from_drives  # noqa: E402
from export_avnet_production import export_production  # noqa: E402
from backbone import build_model  # noqa: E402
from pipeline_integrity import (  # noqa: E402
    ANDROID_ASSET,
    MODEL,
    asset_integrity,
    validate_android_latency_evidence,
)
from speed_data import DriveWindows  # noqa: E402


def _drive() -> DriveWindows:
    imu = np.arange(3 * 20 * 6, dtype=np.float32).reshape(3, 20, 6)
    return DriveWindows(
        name="S-test",
        imu=imu,
        speed=np.array([1.0, 2.0, 3.0], dtype=np.float32),
        t_end=np.array([1.9, 2.1, 2.3], dtype=np.float32),
        label_source="can_10hz",
        n_rows=24,
        hz_est=10.0,
        speed_unit_decision="m/s",
        speed_unit_ratio=1.0,
        csv_path="S-test.csv",
        yaw_rate=np.array([0.1, 0.2, 0.3], dtype=np.float32),
    )


def test_legacy_batch_is_exact_authoritative_window_adapter() -> None:
    drive = _drive()
    batch = _batch_from_drives([drive])
    np.testing.assert_array_equal(batch.imu, drive.imu)
    np.testing.assert_array_equal(batch.speed, drive.speed)
    np.testing.assert_array_equal(batch.psi_dot, drive.yaw_rate)
    assert batch.imu.shape == (3, 20, 6)
    assert batch.y().shape == (3, 4)


def test_android_latency_schema_has_no_workstation_escape_hatch() -> None:
    schema = json.loads(
        (MODELS / "android_latency_evidence.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["measurement_scope"]["const"] == "physical_android_device"
    with pytest.raises(ValueError, match="physical_android_device"):
        validate_android_latency_evidence(
            {
                "schema_version": 1,
                "measurement_scope": "workstation_pytorch",
                "device_model": "not-a-phone",
                "android_version": "n/a",
                "app_variant": "n/a",
                "model_sha256": "0" * 64,
                "runtime": "pytorch",
                "sample_count": 1,
                "latency_ms": {"p50": 1.0, "p95": 1.0, "max": 1.0},
                "captured_at_utc": "2026-01-01T00:00:00Z",
            }
        )


def test_existing_onnx_assets_have_fixed_shapes_and_matching_hashes() -> None:
    if not MODEL.is_file() and not ANDROID_ASSET.is_file():
        pytest.skip("no ONNX model or Android asset in this checkout")
    try:
        report = asset_integrity()
    except ImportError:
        pytest.skip("onnxruntime/onnx is not installed")
    for item in (report["model"], report["android_asset"]):
        if not item["exists"]:
            continue
        assert item["contract"]["input_shape"] == [1, 6, 20]
        assert item["contract"]["output_shape"] == [1, 6]
    if report["model"]["exists"] and report["android_asset"]["exists"]:
        assert report["hash_match"] is True


def test_production_export_smoke_uses_fixed_raw_si_contract(tmp_path: Path) -> None:
    try:
        result = export_production(
            build_model().eval(),
            tmp_path / "avnet_tiny.onnx",
            metadata={"normalisation": "none_raw_si_including_gravity"},
            overwrite=False,
            copy_android_assets=False,
        )
    except ImportError:
        pytest.skip("ONNX export dependencies are not installed")
    assert result["input_shape"] == [1, 6, 20]
    assert result["output_shape"] == [1, 6]
    assert result["normalisation"] == "none_raw_si_including_gravity"
