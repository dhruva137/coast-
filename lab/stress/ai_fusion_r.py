"""Learned diagonal measurement-covariance head (AI-IMU-DR style).

Brossard, Barrau, Bonnabel 2020, "AI-IMU Dead-Reckoning" (IEEE T-IV;
MIT-licensed code at github.com/mbrossar/ai-imu-dr) keep a physics EKF and
learn only the *noise* of the constraints. A network looks at IMU / filter
features and emits the covariance of pseudo-measurements (NHC, and here also
speed, ZUPT, and GNSS position). We follow that split:

* Speed *mean* is frozen / skipped (no exported residual ONNX in this tree).
* This module emits ``diag(R)`` as log-variances.
* Training (in the runner) minimises 60 s integrated position error, **not**
  Gaussian NLL — NLL produced variance inflation in
  ``lab/models/results/nll_diagnosis/``.

CPU / NumPy only. No CUDA.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

SEED = 26168

# log-variance clamps → std roughly:
#   GNSS  1–100 m,  speed 0.14–10 m/s,  NHC 0.14–10 m/s,  ZUPT 0.05–3 m/s
LOG_R_MIN = np.array([0.0, -4.0, -4.0, -6.0], dtype=np.float64)
LOG_R_MAX = np.array([9.21, 4.61, 4.61, 2.20], dtype=np.float64)

OUT_GNSS = 0
OUT_SPEED = 1
OUT_NHC = 2
OUT_ZUPT = 3
N_OUT = 4

FEATURE_NAMES: tuple[str, ...] = (
    "log1p_acc_h_m",
    "log1p_innovation_m",
    "log1p_predicted_sigma_m",
    "log1p_fix_age_s",
    "log1p_abs_gyro",
    "log1p_highband_energy",
    "log1p_speed_mps",
    "stopped",
)
N_IN = len(FEATURE_NAMES)

REPO_ROOT = Path(__file__).resolve().parents[2]
ONNX_CANDIDATES: tuple[Path, ...] = (
    REPO_ROOT / "lab" / "models" / "weights" / "avnet_tiny.onnx",
    REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "avnet_tiny.onnx",
)


def highband_energy(ax: np.ndarray, ay: np.ndarray, az: np.ndarray) -> np.ndarray:
    """Consecutive accel differences — stand-in high-frequency energy (10 Hz)."""
    a = np.column_stack(
        [
            np.asarray(ax, dtype=np.float64).ravel(),
            np.asarray(ay, dtype=np.float64).ravel(),
            np.asarray(az, dtype=np.float64).ravel(),
        ]
    )
    if a.shape[0] == 0:
        return np.zeros(0, dtype=np.float64)
    d = np.diff(a, axis=0, prepend=a[:1])
    return np.sqrt(np.sum(d * d, axis=1))


def fusion_features(
    acc_h_m: float,
    innovation_m: float,
    predicted_sigma_m: float,
    fix_age_s: float,
    abs_gyro: float,
    energy: float,
    speed_mps: float,
    stopped: float,
) -> np.ndarray:
    values = np.asarray(
        [
            acc_h_m,
            innovation_m,
            predicted_sigma_m,
            fix_age_s,
            abs_gyro,
            energy,
            speed_mps,
            stopped,
        ],
        dtype=np.float64,
    )
    values = np.where(np.isfinite(values), np.maximum(values, 0.0), 0.0)
    out = np.empty(N_IN, dtype=np.float64)
    out[:7] = np.log1p(values[:7])
    out[7] = 1.0 if values[7] >= 0.5 else 0.0
    return out


def probe_coast_onnx() -> dict[str, object]:
    """Attempt to load a COAST speed ONNX. Absence is a real limitation, not a skip-claim."""
    found = [str(p) for p in ONNX_CANDIDATES if p.is_file() and p.stat().st_size > 1024]
    if not found:
        return {
            "loaded": False,
            "reason": (
                "No avnet_tiny.onnx / residual-speed ONNX on disk. "
                "Speed *mean* is skipped; CAN speed is an ORACLE ablation and "
                "hold-last GNSS speed is the online persistence ablation."
            ),
            "paths_checked": [str(p) for p in ONNX_CANDIDATES],
        }
    try:
        import onnxruntime as ort  # type: ignore
    except ImportError:
        return {
            "loaded": False,
            "reason": (
                f"ONNX file present ({found[0]}) but onnxruntime is not installed; "
                "not loading a GPU/ORT session from this CPU fusion job."
            ),
            "paths_checked": found,
        }
    try:
        sess = ort.InferenceSession(found[0], providers=["CPUExecutionProvider"])
        inputs = [i.name for i in sess.get_inputs()]
        del sess
    except Exception as exc:  # noqa: BLE001
        return {
            "loaded": False,
            "reason": f"onnxruntime failed to open {found[0]}: {exc}",
            "paths_checked": found,
        }
    return {
        "loaded": True,
        "path": found[0],
        "input_names": inputs,
        "reason": "ONNX opened on CPUExecutionProvider; runner still freezes speed mean.",
    }


@dataclass
class LogVarRHead:
    """Tiny tanh MLP: features → 4 log-variances (GNSS, speed, NHC, ZUPT)."""

    W1: np.ndarray
    b1: np.ndarray
    W2: np.ndarray
    b2: np.ndarray
    feature_mean: np.ndarray
    feature_scale: np.ndarray
    n_hidden: int

    @classmethod
    def zeros(cls, n_hidden: int = 8, rng: np.random.Generator | None = None) -> "LogVarRHead":
        rng = np.random.default_rng(SEED) if rng is None else rng
        # Near-zero weights so the untrained net is almost the output bias
        # (classical-ish R). Training may grow the feature path.
        return cls(
            W1=rng.normal(0.0, 0.02, (n_hidden, N_IN)).astype(np.float64),
            b1=np.zeros(n_hidden, dtype=np.float64),
            W2=rng.normal(0.0, 0.02, (N_OUT, n_hidden)).astype(np.float64),
            b2=np.array(
                [
                    math.log(25.0),  # ~5 m GNSS σ
                    math.log(1.00),  # 1 m/s speed
                    math.log(0.25),  # 0.5 m/s NHC
                    math.log(0.04),  # 0.2 m/s ZUPT
                ],
                dtype=np.float64,
            ),
            feature_mean=np.zeros(N_IN, dtype=np.float64),
            feature_scale=np.ones(N_IN, dtype=np.float64),
            n_hidden=int(n_hidden),
        )

    def freeze_mlp(self) -> None:
        """Stage-2a: only the output bias (global diag R) is free."""
        self.W1[:] = 0.0
        self.b1[:] = 0.0
        self.W2[:] = 0.0

    def set_feature_norm(self, mean: np.ndarray, scale: np.ndarray) -> None:
        self.feature_mean = np.asarray(mean, dtype=np.float64).reshape(N_IN)
        sc = np.asarray(scale, dtype=np.float64).reshape(N_IN)
        sc = np.where(np.isfinite(sc) & (sc > 1e-8), sc, 1.0)
        self.feature_scale = sc

    def log_vars(self, feat: np.ndarray) -> np.ndarray:
        z = (np.asarray(feat, dtype=np.float64) - self.feature_mean) / self.feature_scale
        h = np.tanh(self.W1 @ z + self.b1)
        return np.clip(self.W2 @ h + self.b2, LOG_R_MIN, LOG_R_MAX)

    def variances(self, feat: np.ndarray) -> np.ndarray:
        return np.exp(self.log_vars(feat))

    def n_parameters(self) -> int:
        return int(self.W1.size + self.b1.size + self.W2.size + self.b2.size)

    def pack(self) -> np.ndarray:
        return np.concatenate([self.W1.ravel(), self.b1, self.W2.ravel(), self.b2])

    def unpack_into(self, vec: np.ndarray) -> None:
        p = np.asarray(vec, dtype=np.float64).ravel()
        n_h, n_in = self.n_hidden, N_IN
        i0 = n_h * n_in
        i1 = i0 + n_h
        i2 = i1 + N_OUT * n_h
        self.W1 = p[:i0].reshape(n_h, n_in).copy()
        self.b1 = p[i0:i1].copy()
        self.W2 = p[i1:i2].reshape(N_OUT, n_h).copy()
        self.b2 = np.clip(p[i2 : i2 + N_OUT], LOG_R_MIN, LOG_R_MAX).copy()

    def pack_bias(self) -> np.ndarray:
        return self.b2.copy()

    def unpack_bias(self, vec: np.ndarray) -> None:
        self.b2 = np.clip(np.asarray(vec, dtype=np.float64).ravel()[:N_OUT], LOG_R_MIN, LOG_R_MAX)

    def to_dict(self) -> dict[str, object]:
        return {
            "model_type": "numpy_tanh_mlp_logvar_R",
            "n_hidden": self.n_hidden,
            "n_parameters": self.n_parameters(),
            "feature_names": list(FEATURE_NAMES),
            "output_names": ["r_gnss_m2", "r_speed_m2s2", "r_nhc_m2s2", "r_zupt_m2s2"],
            "feature_mean": [float(v) for v in self.feature_mean],
            "feature_scale": [float(v) for v in self.feature_scale],
            "b2_log_var": [float(v) for v in self.b2],
            "sigma_bias": {
                "gnss_m": float(math.exp(0.5 * self.b2[OUT_GNSS])),
                "speed_mps": float(math.exp(0.5 * self.b2[OUT_SPEED])),
                "nhc_mps": float(math.exp(0.5 * self.b2[OUT_NHC])),
                "zupt_mps": float(math.exp(0.5 * self.b2[OUT_ZUPT])),
            },
        }

    def copy(self) -> "LogVarRHead":
        return LogVarRHead(
            W1=self.W1.copy(),
            b1=self.b1.copy(),
            W2=self.W2.copy(),
            b2=self.b2.copy(),
            feature_mean=self.feature_mean.copy(),
            feature_scale=self.feature_scale.copy(),
            n_hidden=self.n_hidden,
        )


def fit_feature_norm(samples: Sequence[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    if not samples:
        return np.zeros(N_IN), np.ones(N_IN)
    x = np.vstack([np.asarray(s, dtype=np.float64).reshape(N_IN) for s in samples])
    x = x[np.isfinite(x).all(axis=1)]
    if x.shape[0] < 4:
        return np.zeros(N_IN), np.ones(N_IN)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    return mean, scale


def nelder_mead_bias(
    head: LogVarRHead,
    loss_fn: Callable[[LogVarRHead], float],
    *,
    maxiter: int = 35,
) -> dict[str, object]:
    """Stage 2a: freeze MLP weights, fit global log-R bias vs 60 s position error."""
    try:
        from scipy.optimize import minimize
    except ImportError:
        return _coordinate_bias(head, loss_fn, steps=maxiter)

    head.freeze_mlp()
    x0 = head.pack_bias()
    history: list[float] = []

    def objective(vec: np.ndarray) -> float:
        head.unpack_bias(vec)
        val = float(loss_fn(head))
        history.append(val)
        return val if math.isfinite(val) else 1e6

    init = objective(x0)
    result = minimize(
        objective,
        x0,
        method="Nelder-Mead",
        options={"maxiter": int(maxiter), "xatol": 1e-2, "fatol": 1e-2, "disp": False},
    )
    best_vec = np.asarray(result.x, dtype=np.float64)
    head.unpack_bias(best_vec)
    best = float(loss_fn(head))
    if not math.isfinite(best) or best > init:
        head.unpack_bias(x0)
        best = init
        best_vec = x0
    return {
        "method": "Nelder-Mead",
        "n_evals": int(result.nfev),
        "init_loss": init,
        "final_loss": float(best),
        "bias": [float(v) for v in head.pack_bias()],
        "improved": bool(best < init - 1e-6),
        "history_tail": [float(v) for v in history[-8:]],
    }


def _coordinate_bias(
    head: LogVarRHead,
    loss_fn: Callable[[LogVarRHead], float],
    *,
    steps: int,
) -> dict[str, object]:
    head.freeze_mlp()
    b = head.pack_bias()
    init = float(loss_fn(head))
    best = init
    scales = np.array([0.6, 0.6, 0.6, 0.6])
    n_evals = 1
    for _ in range(max(steps, 1)):
        for i in range(N_OUT):
            for delta in (scales[i], -scales[i]):
                trial = b.copy()
                trial[i] = float(np.clip(trial[i] + delta, LOG_R_MIN[i], LOG_R_MAX[i]))
                head.unpack_bias(trial)
                val = float(loss_fn(head))
                n_evals += 1
                if math.isfinite(val) and val < best:
                    best = val
                    b = trial
            scales[i] *= 0.7
    head.unpack_bias(b)
    return {
        "method": "coordinate-descent-fallback",
        "n_evals": n_evals,
        "init_loss": init,
        "final_loss": float(best),
        "bias": [float(v) for v in b],
        "improved": bool(best < init - 1e-6),
    }


def spsa_fit(
    head: LogVarRHead,
    loss_fn: Callable[[LogVarRHead], float],
    *,
    iters: int = 18,
    a0: float = 0.08,
    c0: float = 0.06,
    rng: np.random.Generator | None = None,
) -> dict[str, object]:
    """Stage 2b: SPSA on the full packed MLP against the same 60 s position loss.

    Two rollouts per iteration, independent of parameter count — CPU-safe.
    """
    rng = np.random.default_rng(SEED + 7) if rng is None else rng
    theta = head.pack()
    init = float(loss_fn(head))
    best_theta = theta.copy()
    best = init
    history = [init]
    n_evals = 1
    for k in range(1, max(int(iters), 0) + 1):
        ak = a0 / (k + 8) ** 0.6
        ck = c0 / (k + 4) ** 0.25
        delta = rng.choice(np.array([-1.0, 1.0]), size=theta.size)
        plus = theta + ck * delta
        minus = theta - ck * delta
        head.unpack_into(plus)
        lp = float(loss_fn(head))
        head.unpack_into(minus)
        lm = float(loss_fn(head))
        n_evals += 2
        if not (math.isfinite(lp) and math.isfinite(lm)):
            head.unpack_into(best_theta)
            theta = best_theta.copy()
            continue
        grad = (lp - lm) / (2.0 * ck * delta)
        theta = theta - ak * grad
        # Keep output bias in clamp range via unpack.
        head.unpack_into(theta)
        theta = head.pack()
        cur = float(loss_fn(head))
        n_evals += 1
        history.append(cur)
        if math.isfinite(cur) and cur < best:
            best = cur
            best_theta = theta.copy()
    head.unpack_into(best_theta)
    return {
        "method": "SPSA",
        "n_iters": int(iters),
        "n_evals": n_evals,
        "init_loss": init,
        "final_loss": float(best),
        "improved": bool(best < init - 1e-6),
        "history_tail": [float(v) for v in history[-8:]],
    }
