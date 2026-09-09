"""Unit checks for EqNIO-style gravity-axis canonicalization."""

from __future__ import annotations

import numpy as np

from gravity_canonical import (
    apply_fixed_rotation,
    canonicalize_imu,
    gravity_z_stats,
    random_so3,
    rotation_aligning_gravity_to_z,
)


def test_aligns_tilted_gravity_to_z():
    rng = np.random.default_rng(0)
    g = np.array([3.0, -2.0, 8.0], dtype=np.float64)
    g = g / np.linalg.norm(g) * 9.81
    t = 20
    imu = np.zeros((t, 6), dtype=np.float32)
    imu[:, :3] = g + rng.normal(0.0, 0.05, size=(t, 3))
    imu[:, 3:6] = rng.normal(0.0, 0.01, size=(t, 3))
    out = canonicalize_imu(imu)
    g2 = out[:, :3].mean(axis=0)
    assert abs(g2[0]) < 0.15 and abs(g2[1]) < 0.15, g2
    assert g2[2] > 9.0, g2


def test_batch_invariant_to_prior_rotation():
    """Canonicalize(R @ x) ≈ Canonicalize(x) up to yaw about z (g on +z)."""
    rng = np.random.default_rng(1)
    base = np.zeros((8, 20, 6), dtype=np.float32)
    base[..., 2] = 9.81
    base[..., 0] += rng.normal(0.0, 0.3, size=base[..., 0].shape)
    r = random_so3(rng)
    rotated = apply_fixed_rotation(base, r)
    c0 = canonicalize_imu(base)
    c1 = canonicalize_imu(rotated)
    g0 = gravity_z_stats(c0)
    g1 = gravity_z_stats(c1)
    assert g0["median_gxy"] < 0.2
    assert g1["median_gxy"] < 0.2
    # |g| preserved
    assert abs(g0["median_g_norm"] - g1["median_g_norm"]) < 0.05


def test_rotation_identity_when_already_z():
    r = rotation_aligning_gravity_to_z(np.array([0.0, 0.0, 9.81]))
    assert np.allclose(r, np.eye(3), atol=1e-6)


if __name__ == "__main__":
    test_aligns_tilted_gravity_to_z()
    test_batch_invariant_to_prior_rotation()
    test_rotation_identity_when_already_z()
    print("gravity_canonical ok")
