"""Dataset column adapters for field / public-log stress scoring.

Manager drops real downloads under ``data/field/``; do not run this pipeline
inside a Kaggle notebook (see README.md).
"""

from __future__ import annotations

from .base import ColumnAdapter, SessionArrays
from .comma2k19 import Comma2k19Adapter
from .gsdc import GsdcAdapter
from .iovnbd import IoVnbdAdapter
from .synthetic import SyntheticAdapter, fixture_dir

ADAPTERS: dict[str, type[ColumnAdapter]] = {
    SyntheticAdapter.name: SyntheticAdapter,
    IoVnbdAdapter.name: IoVnbdAdapter,
    Comma2k19Adapter.name: Comma2k19Adapter,
    GsdcAdapter.name: GsdcAdapter,
}


def get_adapter(name: str) -> ColumnAdapter:
    key = name.strip().lower()
    if key not in ADAPTERS:
        known = ", ".join(sorted(ADAPTERS))
        raise KeyError(f"unknown adapter {name!r}; known: {known}")
    return ADAPTERS[key]()


__all__ = [
    "ADAPTERS",
    "ColumnAdapter",
    "Comma2k19Adapter",
    "GsdcAdapter",
    "IoVnbdAdapter",
    "SessionArrays",
    "SyntheticAdapter",
    "fixture_dir",
    "get_adapter",
]
