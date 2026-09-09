"""EqNIO-style gravity-axis canonicalization for AVNet IMU windows.

EqNIO (ICLR 2025, arXiv 2408.06321) exploits roto-reflection symmetry about the
gravity axis so a network sees a consistent vertical regardless of phone mount.
We do the practical half of that idea: estimate gravity from the window's
specific-force mean and rotate accel + gyro so gravity lands on +z.

The residual freedom is a yaw about gravity (SO(2)). Aligning z alone is enough
to remove the dominant mount-tilt nuisance for a scalar speed head; we do not
claim full EqNIO subequivariance.

Input layout matches ``speed_data`` / bakeoff: ``(..., T, 6)`` with
``ax, ay, az, gx, gy, gz`` in SI (m/s² including gravity, rad/s).
"""

from __future__ import annotations

import numpy as np

G_REF = 9.80665


def _skew(v: np.ndarray) -> np.ndarray:
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=np.float64)


def rotation_aligning_gravity_to_z(g: np.ndarray) -> np.ndarray:
    """Rodrigues rotation ``R`` with ``R @ g_hat ≈ [0, 0, 1]``.

    Near-antipodal gravity uses a stable Householder-style 180° flip about an
    axis perpendicular to g so the map stays continuous enough for batch use.
    """
    g = np.asarray(g, dtype=np.float64).reshape(3)
    n = float(np.linalg.norm(g))
    if not np.isfinite(n) or n < 1e-6:
        return np.eye(3, dtype=np.float64)
    g_hat = g / n
    target = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    c = float(np.dot(g_hat, target))
    if c > 1.0 - 1e-8:
        return np.eye(3, dtype=np.float64)
    if c < -1.0 + 1e-8:
        # 180°: pick any unit vector orthogonal to g_hat.
        axis = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(g_hat[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        axis = axis - g_hat * float(np.dot(axis, g_hat))
        axis = axis / float(np.linalg.norm(axis))
        # R = 2 aaᵀ − I  (Householder reflection through plane ⊥ axis?);
        # for 180° about axis: R = 2 aaᵀ − I is reflection; use Rodrigues:
        # R = I cosπ + (a×) sinπ + a aᵀ (1−cosπ) = −I + 2 a aᵀ
        return (-np.eye(3) + 2.0 * np.outer(axis, axis)).astype(np.float64)
    v = np.cross(g_hat, target)
    s = float(np.linalg.norm(v))
    vx = _skew(v)
    r = np.eye(3) + vx + vx @ vx * ((1.0 - c) / (s * s))
    return r.astype(np.float64)


def canonicalize_window(imu_tc6: np.ndarray) -> np.ndarray:
    """Canonicalize one ``(T, 6)`` window. Gravity from mean specific force."""
    x = np.asarray(imu_tc6, dtype=np.float64)
    if x.ndim != 2 or x.shape[-1] != 6:
        raise ValueError(f"expected (T, 6), got {x.shape}")
    g = x[:, :3].mean(axis=0)
    r = rotation_aligning_gravity_to_z(g)
    out = x.copy()
    out[:, :3] = x[:, :3] @ r.T
    out[:, 3:6] = x[:, 3:6] @ r.T
    return out.astype(np.float32)


def canonicalize_imu(imu: np.ndarray) -> np.ndarray:
    """Canonicalize a batch ``(N, T, 6)`` or a single ``(T, 6)`` window.

    Each window gets its own gravity estimate (mount can slowly change; per-window
    is the causal phone contract). Vectorised over the batch.
    """
    x = np.asarray(imu, dtype=np.float64)
    single = x.ndim == 2
    if single:
        x = x[None, ...]
    if x.ndim != 3 or x.shape[-1] != 6:
        raise ValueError(f"expected (N, T, 6) or (T, 6), got {imu.shape}")

    n, t, _ = x.shape
    g = x[:, :, :3].mean(axis=1)  # (N, 3)
    gn = np.linalg.norm(g, axis=1, keepdims=True)
    safe = gn[:, 0] >= 1e-6
    g_hat = np.zeros_like(g)
    g_hat[safe] = g[safe] / gn[safe]

    target = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    # Build R per row. Small N·T batches dominate cost elsewhere; clarity > micro-opts.
    out = x.copy()
    eye = np.eye(3, dtype=np.float64)
    for i in range(n):
        if not safe[i]:
            r = eye
        else:
            r = rotation_aligning_gravity_to_z(g_hat[i] * gn[i, 0])
        out[i, :, :3] = x[i, :, :3] @ r.T
        out[i, :, 3:6] = x[i, :, 3:6] @ r.T
    if single:
        return out[0].astype(np.float32)
    return out.astype(np.float32)


def gravity_z_stats(imu: np.ndarray) -> dict[str, float]:
    """Diagnostics: after canonicalize, mean |g_xy| should collapse vs |g_z|."""
    x = np.asarray(imu, dtype=np.float64)
    if x.ndim == 2:
        x = x[None, ...]
    g = x[:, :, :3].mean(axis=1)
    gxy = np.linalg.norm(g[:, :2], axis=1)
    gz = np.abs(g[:, 2])
    return {
        "median_gxy": float(np.median(gxy)),
        "median_gz": float(np.median(gz)),
        "median_g_norm": float(np.median(np.linalg.norm(g, axis=1))),
    }


def apply_fixed_rotation(imu: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Apply one body-frame rotation to all windows (mount-swap probe)."""
    x = np.asarray(imu, dtype=np.float64)
    r = np.asarray(r, dtype=np.float64).reshape(3, 3)
    single = x.ndim == 2
    if single:
        x = x[None, ...]
    out = x.copy()
    out[..., :3] = x[..., :3] @ r.T
    out[..., 3:6] = x[..., 3:6] @ r.T
    if single:
        return out[0].astype(np.float32)
    return out.astype(np.float32)


def random_so3(rng: np.random.Generator) -> np.ndarray:
    """Uniform random rotation (Shoemake)."""
    u1, u2, u3 = rng.random(3)
    q1 = np.sqrt(1.0 - u1) * np.sin(2.0 * np.pi * u2)
    q2 = np.sqrt(1.0 - u1) * np.cos(2.0 * np.pi * u2)
    q3 = np.sqrt(u1) * np.sin(2.0 * np.pi * u3)
    q4 = np.sqrt(u1) * np.cos(2.0 * np.pi * u3)
    # Quaternion (q1,q2,q3,q4) → rotation matrix.
    xx, yy, zz = q1 * q1, q2 * q2, q3 * q3
    xy, xz, yz = q1 * q2, q1 * q3, q2 * q3
    wx, wy, wz = q4 * q1, q4 * q2, q4 * q3
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )
