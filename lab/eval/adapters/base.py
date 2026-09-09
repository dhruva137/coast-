"""Column-mapping adapter pattern → COAST session schema.

Any external smartphone IMU (+ GPS) dump becomes a uniform ``SessionArrays``
so ``lab/stress/run_dataset_stress.py`` can score free-DR (and map-in-loop when
an independent OSM graph covers the track).

Schema (SI units)
-----------------
* ``t_s`` — seconds since start (monotonic)
* ``ax,ay,az`` — body accel m/s²
* ``gx,gy,gz`` — body gyro rad/s (vehicle-frame mapping is adapter-specific)
* ``lat,lon`` — WGS-84 degrees (GPS truth when present)
* ``speed`` — m/s (GPS or derived)
* ``bearing_deg`` — degrees clockwise from north (NaN if unknown)
"""

from __future__ import annotations

import csv
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def norm_header(name: str) -> str:
    """Lowercase + strip units/punctuation for fuzzy column match."""
    s = name.strip().lstrip("\ufeff").lower()
    s = re.sub(r"[^\x00-\x7f]", " ", s)
    for ch in "[](){}^/":
        s = s.replace(ch, " ")
    s = s.replace("_", " ").replace("-", " ").replace(",", " ")
    return " ".join(s.split())


def map_columns(
    header: Sequence[str],
    aliases: Mapping[str, Sequence[str]],
) -> dict[str, int]:
    """Map canonical keys → column index via alias list (first match wins)."""
    norms = [norm_header(h) for h in header]
    found: dict[str, int] = {}
    for key, alts in aliases.items():
        alias_set = {norm_header(a) for a in alts}
        alias_compact = {a.replace(" ", "") for a in alias_set}
        for i, n in enumerate(norms):
            if key in found:
                break
            compact = n.replace(" ", "")
            if n in alias_set or compact in alias_compact:
                found[key] = i
                break
            for a in alias_set:
                if len(a) > 3 and a in n:
                    found[key] = i
                    break
    return found


def read_csv_table(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"{path} is empty")
    header = [c.strip().lstrip("\ufeff") for c in rows[0]]
    body = [r for r in rows[1:] if r and any(c.strip() for c in r)]
    return header, body


def float_col(body: list[list[str]], idx: int | None, n: int) -> np.ndarray:
    out = np.full(n, np.nan, dtype=np.float64)
    if idx is None:
        return out
    for i, row in enumerate(body):
        if i >= n:
            break
        if idx < len(row) and row[idx] != "":
            try:
                out[i] = float(row[idx])
            except ValueError:
                out[i] = np.nan
    return out


@dataclass
class SessionArrays:
    """Uniform session after column mapping."""

    name: str
    t_s: np.ndarray
    ax: np.ndarray
    ay: np.ndarray
    az: np.ndarray
    gx: np.ndarray
    gy: np.ndarray
    gz: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    speed: np.ndarray
    bearing_deg: np.ndarray
    source_path: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = int(self.t_s.size)
        for name in (
            "ax",
            "ay",
            "az",
            "gx",
            "gy",
            "gz",
            "lat",
            "lon",
            "speed",
            "bearing_deg",
        ):
            arr = np.asarray(getattr(self, name), dtype=np.float64).ravel()
            if arr.size != n:
                raise ValueError(f"{name} length {arr.size} != t_s length {n}")
            setattr(self, name, arr)
        self.t_s = np.asarray(self.t_s, dtype=np.float64).ravel()

    @property
    def n(self) -> int:
        return int(self.t_s.size)

    @property
    def hz(self) -> float:
        if self.n < 2:
            return float("nan")
        dt = float(self.t_s[-1] - self.t_s[0]) / (self.n - 1)
        return 1.0 / dt if dt > 0 else float("nan")


class ColumnAdapter(ABC):
    """Base: discover files in a directory and emit ``SessionArrays``."""

    name: str = "base"

    @abstractmethod
    def discover(self, dataset_dir: Path) -> list[Path]:
        """Return input files / session dirs this adapter can load."""

    @abstractmethod
    def load(self, path: Path) -> SessionArrays:
        """Map one file (or session dir) → session schema."""

    def load_all(self, dataset_dir: Path) -> list[SessionArrays]:
        paths = self.discover(Path(dataset_dir))
        if not paths:
            raise FileNotFoundError(
                f"adapter={self.name!r} found no loadable files under {dataset_dir}"
            )
        return [self.load(p) for p in paths]


def require_keys(found: Mapping[str, int], keys: Iterable[str], *, where: str) -> None:
    missing = [k for k in keys if k not in found]
    if missing:
        raise ValueError(f"{where}: missing columns for {missing} (mapped={dict(found)})")
