"""Frequency-decoupled AVNet-tiny backbone [F7].

Low band (< 2 Hz) carries vehicle motion (SNR +29 dB). High band is
vibration / mount noise (adapter). Fusion regresses body-frame speed,
yaw-rate ψ̇, optional roll/pitch residual, and a TLIO-style log-variance.

Target: ~50k–200k params, < 5 MB, CPU inference that feels like < 10 ms.
Windows: 20 samples @ 10 Hz (2.0 s). Not 200 @ 200 Hz.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from datasets.log_schema import IMU_HZ_IO_VNBD, MOTION_BAND_HZ, WINDOW_SAMPLES
except ImportError:
    try:
        from lab.datasets.log_schema import IMU_HZ_IO_VNBD, MOTION_BAND_HZ, WINDOW_SAMPLES
    except ImportError:
        try:
            from log_schema import IMU_HZ_IO_VNBD, MOTION_BAND_HZ, WINDOW_SAMPLES  # type: ignore
        except ImportError:
            IMU_HZ_IO_VNBD = 10.0
            MOTION_BAND_HZ = 2.0
            WINDOW_SAMPLES = 20


def fir_lowpass_kernel(cutoff_hz: float, fs: float, taps: int = 9) -> np.ndarray:
    """Hamming-windowed sinc, DC gain 1. ``taps`` should be odd."""
    if taps % 2 == 0:
        taps += 1
    fc = float(cutoff_hz) / float(fs)
    n = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
    h = np.sinc(2.0 * fc * n) * np.hamming(taps)
    h = h / np.sum(h)
    return h.astype(np.float32)


class FrequencySplit(nn.Module):
    """Fixed FIR low/high split at the [F7] 2 Hz boundary. Not learned."""

    def __init__(self, channels: int = 6, cutoff_hz: float = MOTION_BAND_HZ, fs: float = IMU_HZ_IO_VNBD, taps: int = 9):
        super().__init__()
        k = fir_lowpass_kernel(cutoff_hz, fs, taps)
        weight = torch.from_numpy(k).view(1, 1, -1).repeat(channels, 1, 1)
        self.register_buffer("kernel", weight)
        self.channels = channels
        self.pad = taps // 2

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (B, C, T). Odd tap count + same padding keeps T.
        low = F.conv1d(x, self.kernel, padding="same", groups=self.channels)
        return low, x - low


class FrequencyDecoupledNet(nn.Module):
    """Tiny CNN-GRU stand-in for AVNet: speed, ψ̇, residuals, log-variance."""

    def __init__(
        self,
        in_ch: int = 6,
        window: int = WINDOW_SAMPLES,
        gru_hidden: int = 80,
        gru_layers: int = 2,
        conv_ch: int = 48,
        fuse: int = 96,
        dropout: float = 0.05,
    ):
        super().__init__()
        self.in_ch = in_ch
        self.window = window
        self.gru_hidden = gru_hidden
        self.split = FrequencySplit(channels=in_ch)

        self.low_proj = nn.Sequential(
            nn.Conv1d(in_ch, 32, kernel_size=3, padding=1, bias=True),
            nn.GELU(),
        )
        self.gru = nn.GRU(
            input_size=32,
            hidden_size=gru_hidden,
            num_layers=gru_layers,
            batch_first=True,
            dropout=dropout if gru_layers > 1 else 0.0,
        )

        self.high_adapter = nn.Sequential(
            nn.Conv1d(in_ch, conv_ch, kernel_size=5, padding=2),
            nn.GroupNorm(8, conv_ch),
            nn.GELU(),
            nn.Conv1d(conv_ch, conv_ch, kernel_size=3, padding=1),
            nn.GroupNorm(8, conv_ch),
            nn.GELU(),
            nn.Conv1d(conv_ch, conv_ch, kernel_size=3, padding=1),
            nn.GELU(),
        )
        fused = gru_hidden + conv_ch + in_ch + 1  # + low mean + kinematic speed cue
        self.head = nn.Sequential(
            nn.Linear(fused, fuse),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(fuse, 6),
        )
        # Mild prior: log-variance starts near ln(0.25^2) for speed, ln(0.05^2) for yaw.
        with torch.no_grad():
            self.head[-1].bias.zero_()
            self.head[-1].bias[4] = math.log(0.25**2)
            self.head[-1].bias[5] = math.log(0.05**2)

    def _as_bct(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 2:
            x = x.unsqueeze(0)
        if x.dim() != 3:
            raise ValueError(f"expected (B,C,T) or (B,T,C), got {tuple(x.shape)}")
        if x.size(1) != self.in_ch and x.size(-1) == self.in_ch:
            x = x.transpose(1, 2)
        if x.size(1) != self.in_ch:
            raise ValueError(f"channel dim must be {self.in_ch}, got {tuple(x.shape)}")
        return x.contiguous()

    def kinematic_speed_prior(self, low: torch.Tensor) -> torch.Tensor:
        """v ≈ sqrt(|a|² − g²) / |ω_yz|. Clamped; unreliable when |ω| is tiny."""
        a = low[:, :3].mean(dim=-1)
        w_yz = torch.linalg.vector_norm(low[:, 4:6].mean(dim=-1), dim=-1).clamp_min(1e-3)
        amag = torch.linalg.vector_norm(a, dim=-1)
        g = a.new_tensor(9.80665)
        cent = torch.sqrt((amag * amag - g * g).clamp_min(0.0))
        return (cent / w_yz).clamp(0.0, 40.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """``x`` is (B, 6, T) or (B, T, 6). Returns (B, 6).

        Outputs: speed, psi_dot, roll_res, pitch_res, logvar_speed, logvar_psi.
        """
        x = self._as_bct(x)
        low, high = self.split(x)
        seq = self.low_proj(low).transpose(1, 2)  # (B, T, 32)
        _, h_n = self.gru(seq)
        low_feat = h_n[-1]
        high_feat = self.high_adapter(high).mean(dim=-1)
        prior = self.kinematic_speed_prior(low).unsqueeze(1)
        return self.head(torch.cat([low_feat, high_feat, low.mean(dim=-1), prior], dim=-1))

    def split_heads(self, y: torch.Tensor) -> dict[str, torch.Tensor]:
        return {
            "speed": y[:, 0],
            "psi_dot": y[:, 1],
            "roll_res": y[:, 2],
            "pitch_res": y[:, 3],
            "logvar_speed": y[:, 4],
            "logvar_psi": y[:, 5],
        }

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def nll_gaussian(pred: torch.Tensor, logvar: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Diagonal Gaussian NLL (TLIO-style heteroscedastic head)."""
    s = logvar.clamp(-8.0, 4.0)
    return 0.5 * (((pred - target) ** 2) * torch.exp(-s) + s).mean()


def avnet_loss(pred: torch.Tensor, target: torch.Tensor) -> dict[str, torch.Tensor]:
    """``target`` is (B, 4): speed, psi_dot, roll_res, pitch_res.

    NLL lets the covariance head learn honesty; MSE keeps speed from
    collapsing to the dataset mean on weakly observable straight windows.
    """
    speed_nll = nll_gaussian(pred[:, 0], pred[:, 4], target[:, 0])
    yaw_nll = nll_gaussian(pred[:, 1], pred[:, 5], target[:, 1])
    speed_mse = F.mse_loss(pred[:, 0] / 10.0, target[:, 0] / 10.0)
    yaw_mse = F.mse_loss(pred[:, 1], target[:, 1])
    res_l = 0.25 * F.mse_loss(pred[:, 2:4], target[:, 2:4])
    total = speed_nll + yaw_nll + 4.0 * speed_mse + 8.0 * yaw_mse + res_l
    return {"loss": total, "nll_speed": speed_nll, "nll_yaw": yaw_nll, "mse_res": res_l}


def default_config() -> dict[str, Any]:
    return {
        "in_ch": 6,
        "window": WINDOW_SAMPLES,
        "gru_hidden": 80,
        "gru_layers": 2,
        "conv_ch": 48,
        "fuse": 96,
        "hz": IMU_HZ_IO_VNBD,
        "cutoff_hz": MOTION_BAND_HZ,
    }


def build_model(**overrides: Any) -> FrequencyDecoupledNet:
    cfg = default_config()
    cfg.update(overrides)
    return FrequencyDecoupledNet(
        in_ch=int(cfg["in_ch"]),
        window=int(cfg["window"]),
        gru_hidden=int(cfg["gru_hidden"]),
        gru_layers=int(cfg["gru_layers"]),
        conv_ch=int(cfg["conv_ch"]),
        fuse=int(cfg["fuse"]),
    )
