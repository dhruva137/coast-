"""Build a compact offline road graph from OpenStreetMap.

The graph is the *independent* prior used by ``lab/nav/mapmatch.py``. It is
built from OSM alone. It never sees an IO-VNBD trajectory, a GNSS fix, or any
column of an ``S-*.csv`` / ``V-*.csv``. The only thing the drives determine is
*which rectangle of the planet* to download, and the rectangle is a fixed,
hand-written city-scale box (see ``REGIONS``) whose extract contains every road
inside it -- driven or not.

Sources, in priority order
--------------------------
1. ``data/maps/osm/*.osm`` / ``*.xml`` -- a local OSM XML extract dropped in by
   hand (works with zero network; ``--offline`` forces this path).
2. ``data/maps/overpass/<tile>.json`` -- cached Overpass tiles from a previous
   run (also zero network).
3. The Overpass API -- fetched tile by tile on a fixed 0.05 degree global grid
   and cached under (2). Requires network; only needed once.

``.osm.pbf`` is deliberately *not* parsed: that needs a protobuf/varint reader
we would have to hand-roll, or a heavy new dependency. Convert first with
``osmium cat in.osm.pbf -o out.osm`` (or ``osmconvert``) and drop the XML in
``data/maps/osm/``.

Output
------
``maps/graphs/<name>.graph.npz``  -- nodes, edges, per-edge and per-segment
headings, routing adjacency, and a uniform-grid spatial index, all as flat
NumPy arrays.
``maps/graphs/<name>.graph.meta.json`` -- small, human-readable provenance.

Run
---
    python maps/osm_extract.py --region iovnbd_midlands
    python maps/osm_extract.py --region iovnbd_midlands --offline
    python maps/osm_extract.py --list-regions
"""

from __future__ import annotations

import argparse
import json
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator

import numpy as np

# --- constants -------------------------------------------------------------

SEED = 26168
R_EARTH_M = 6_371_008.8
# Same flat-earth constants lab/eval/metrics.lla_to_enu uses, so ENU metres
# from this module and from the benchmark agree exactly.
M_PER_DEG_LAT = 111_132.92
M_PER_DEG_LON_EQ = 111_412.84

TILE_DEG = 0.05
"""Fixed global fetch/cache grid. Tile identity does not depend on any drive."""

GRID_DEG = 0.002
"""Spatial-index cell, ~222 m north-south. Small enough that a 60 m radius
query touches at most a 3x3 block of cells."""

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
USER_AGENT = "SIH26168-mapmatch/0.1 (offline navigation research)"
OVERPASS_PAUSE_S = 1.0
OVERPASS_TIMEOUT_S = 300

# Drivable classes only. Service roads, tracks, footways and cycleways are
# excluded: they roughly triple the graph while a car on a 60 s tunnel-style
# outage is on none of them.
HIGHWAY_CLASSES: tuple[str, ...] = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
)
_CLASS_INDEX = {name: i for i, name in enumerate(HIGHWAY_CLASSES)}

# Named regions. Hand-written city-scale rectangles, NOT route hulls.
# iovnbd_midlands covers Coventry / east Birmingham / Nuneaton / Rugby, the
# area the eight CAN-truth IO-VNBD drives happen to fall inside.
REGIONS: dict[str, dict[str, Any]] = {
    "iovnbd_midlands": {
        "bbox": (52.35, -1.62, 52.57, -1.22),  # (lat_min, lon_min, lat_max, lon_max)
        "note": "UK Midlands: Coventry, east Birmingham, Nuneaton, Rugby.",
    },
}


class OsmSourceError(RuntimeError):
    """No usable OSM source (no network, no cache, no local extract)."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def cache_dir() -> Path:
    return repo_root() / "data" / "maps"


def graphs_dir() -> Path:
    return repo_root() / "maps" / "graphs"


def default_graph_path(region: str = "iovnbd_midlands") -> Path:
    return graphs_dir() / f"{region}.graph.npz"


# --- geometry --------------------------------------------------------------


def lla_to_enu(
    lat_deg: np.ndarray, lon_deg: np.ndarray, origin_lat: float, origin_lon: float
) -> np.ndarray:
    """Geographic degrees -> local east/north metres (metrics.lla_to_enu twin)."""
    lat = np.asarray(lat_deg, dtype=np.float64)
    lon = np.asarray(lon_deg, dtype=np.float64)
    c = math.cos(math.radians(float(origin_lat)))
    east = (lon - float(origin_lon)) * M_PER_DEG_LON_EQ * c
    north = (lat - float(origin_lat)) * M_PER_DEG_LAT
    return np.column_stack([east.ravel(), north.ravel()])


def _haversine_m(lat1, lon1, lat2, lon2):
    p1 = np.deg2rad(np.asarray(lat1, dtype=np.float64))
    p2 = np.deg2rad(np.asarray(lat2, dtype=np.float64))
    dp = p2 - p1
    dl = np.deg2rad(np.asarray(lon2, dtype=np.float64) - np.asarray(lon1, dtype=np.float64))
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return 2.0 * R_EARTH_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _bearing_deg(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing, degrees clockwise from north in [0, 360)."""
    p1 = np.deg2rad(np.asarray(lat1, dtype=np.float64))
    p2 = np.deg2rad(np.asarray(lat2, dtype=np.float64))
    dl = np.deg2rad(np.asarray(lon2, dtype=np.float64) - np.asarray(lon1, dtype=np.float64))
    y = np.sin(dl) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return np.rad2deg(np.arctan2(y, x)) % 360.0


# --- Overpass fetch --------------------------------------------------------


def tile_ids(bbox: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    """Fixed-grid tile ids (i_lat, i_lon) covering ``bbox``."""
    lat0, lon0, lat1, lon1 = bbox
    i0 = int(math.floor(lat0 / TILE_DEG))
    i1 = int(math.floor((lat1 - 1e-9) / TILE_DEG))
    j0 = int(math.floor(lon0 / TILE_DEG))
    j1 = int(math.floor((lon1 - 1e-9) / TILE_DEG))
    return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]


def tile_bbox(tile: tuple[int, int]) -> tuple[float, float, float, float]:
    i, j = tile
    return (i * TILE_DEG, j * TILE_DEG, (i + 1) * TILE_DEG, (j + 1) * TILE_DEG)


def tile_cache_path(tile: tuple[int, int]) -> Path:
    i, j = tile
    return cache_dir() / "overpass" / f"tile_{i:+06d}_{j:+06d}.json"


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    lat0, lon0, lat1, lon1 = bbox
    classes = "|".join(HIGHWAY_CLASSES)
    return (
        "[out:json][timeout:%d];\n"
        'way["highway"~"^(%s)$"](%.6f,%.6f,%.6f,%.6f);\n'
        "out body qt;\n>;\nout skel qt;\n"
    ) % (OVERPASS_TIMEOUT_S, classes, lat0, lon0, lat1, lon1)


def fetch_tile(
    tile: tuple[int, int], *, offline: bool = False, verbose: bool = True
) -> Path | None:
    """Return the cached Overpass JSON for ``tile``, downloading if allowed."""
    path = tile_cache_path(tile)
    if path.is_file() and path.stat().st_size > 64:
        return path
    if offline:
        return None
    try:
        import requests
    except ImportError as exc:
        raise OsmSourceError("requests is unavailable; re-run with --offline") from exc

    query = overpass_query(tile_bbox(tile))
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            t0 = time.time()
            resp = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=OVERPASS_TIMEOUT_S,
            )
            if resp.status_code != 200:
                last_err = RuntimeError(f"{endpoint} HTTP {resp.status_code}")
                continue
            payload = resp.json()
            if "elements" not in payload:
                last_err = RuntimeError(f"{endpoint} returned no elements")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            if verbose:
                print(
                    f"  tile {tile}: {len(payload['elements'])} elements, "
                    f"{path.stat().st_size / 1e6:.2f} MB, {time.time() - t0:.1f}s"
                )
            time.sleep(OVERPASS_PAUSE_S)
            return path
        except Exception as exc:  # noqa: BLE001 -- network is allowed to fail
            last_err = exc
    if verbose:
        print(f"  tile {tile}: FAILED ({last_err})")
    return None


# --- source readers --------------------------------------------------------


def _read_overpass_json(path: Path) -> tuple[dict[int, tuple[float, float]], list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict] = []
    for el in payload.get("elements", ()):
        if el.get("type") == "node":
            nodes[int(el["id"])] = (float(el["lat"]), float(el["lon"]))
        elif el.get("type") == "way":
            tags = el.get("tags", {}) or {}
            hw = tags.get("highway")
            if hw not in _CLASS_INDEX:
                continue
            ways.append(
                {
                    "id": int(el["id"]),
                    "refs": [int(r) for r in el.get("nodes", ())],
                    "highway": hw,
                    "oneway": tags.get("oneway", ""),
                    "junction": tags.get("junction", ""),
                }
            )
    return nodes, ways


def _read_osm_xml(path: Path) -> tuple[dict[int, tuple[float, float]], list[dict]]:
    """Stream a plain OSM XML extract. Handles files far larger than RAM/2."""
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict] = []
    refs: list[int] = []
    tags: dict[str, str] = {}
    way_id = -1
    in_way = False
    for event, el in ET.iterparse(str(path), events=("start", "end")):
        if event == "start":
            if el.tag == "way":
                in_way, refs, tags, way_id = True, [], {}, int(el.get("id", "-1"))
            elif in_way and el.tag == "nd":
                refs.append(int(el.get("ref", "0")))
            elif in_way and el.tag == "tag":
                tags[el.get("k", "")] = el.get("v", "")
            continue
        if el.tag == "node":
            try:
                nodes[int(el.get("id", "0"))] = (
                    float(el.get("lat", "nan")),
                    float(el.get("lon", "nan")),
                )
            except (TypeError, ValueError):
                pass
            el.clear()
        elif el.tag == "way":
            hw = tags.get("highway")
            if hw in _CLASS_INDEX and len(refs) >= 2:
                ways.append(
                    {
                        "id": way_id,
                        "refs": list(refs),
                        "highway": hw,
                        "oneway": tags.get("oneway", ""),
                        "junction": tags.get("junction", ""),
                    }
                )
            in_way, refs, tags = False, [], {}
            el.clear()
    return nodes, ways


def iter_sources(
    bbox: tuple[float, float, float, float],
    *,
    offline: bool = False,
    verbose: bool = True,
) -> Iterator[tuple[str, Path]]:
    """Yield ``(kind, path)`` for every usable OSM source covering ``bbox``."""
    osm_dir = cache_dir() / "osm"
    local = sorted(list(osm_dir.glob("*.osm")) + list(osm_dir.glob("*.xml")))
    for p in local:
        yield ("osm_xml", p)
    pbf = sorted(osm_dir.glob("*.pbf"))
    if pbf and verbose:
        print(
            f"  note: {len(pbf)} .osm.pbf present but NOT parsed. Convert with "
            "'osmium cat x.osm.pbf -o x.osm' and re-run."
        )
    for tile in tile_ids(bbox):
        p = fetch_tile(tile, offline=offline, verbose=verbose)
        if p is not None:
            yield ("overpass_json", p)


# --- graph construction ----------------------------------------------------


def _oneway_flag(way: dict) -> int:
    """+1 forward-only, -1 reverse-only, 0 bidirectional."""
    v = str(way.get("oneway", "")).strip().lower()
    if v in ("yes", "true", "1"):
        return 1
    if v in ("-1", "reverse"):
        return -1
    if v in ("no", "false", "0"):
        return 0
    if str(way.get("junction", "")).strip().lower() in ("roundabout", "circular"):
        return 1
    if str(way.get("highway", "")) in ("motorway", "motorway_link"):
        return 1
    return 0


def _pack_edges(
    edge_nodes: np.ndarray, edge_ptr: np.ndarray, node_lat: np.ndarray, node_lon: np.ndarray
) -> dict[str, np.ndarray]:
    """Per-segment lengths/bearings plus per-edge length/bearing, CSR style."""
    n_edges = edge_ptr.size - 1
    seg_counts = np.diff(edge_ptr) - 1
    seg_ptr = np.zeros(n_edges + 1, dtype=np.int64)
    seg_ptr[1:] = np.cumsum(seg_counts)
    keep_a = np.ones(edge_nodes.size, dtype=bool)
    keep_a[edge_ptr[1:] - 1] = False
    keep_b = np.ones(edge_nodes.size, dtype=bool)
    keep_b[edge_ptr[:-1]] = False
    ia = edge_nodes[keep_a]
    ib = edge_nodes[keep_b]
    seg_len = _haversine_m(node_lat[ia], node_lon[ia], node_lat[ib], node_lon[ib])
    seg_bear = _bearing_deg(node_lat[ia], node_lon[ia], node_lat[ib], node_lon[ib])
    edge_len = np.zeros(n_edges, dtype=np.float64)
    np.add.at(edge_len, np.repeat(np.arange(n_edges), seg_counts), seg_len)
    u = edge_nodes[edge_ptr[:-1]]
    v = edge_nodes[edge_ptr[1:] - 1]
    edge_bear = _bearing_deg(node_lat[u], node_lon[u], node_lat[v], node_lon[v])
    return {
        "seg_ptr": seg_ptr,
        "seg_len_m": seg_len,
        "seg_bearing_deg": seg_bear,
        "edge_len_m": edge_len,
        "edge_bearing_deg": edge_bear,
        "edge_u": u.astype(np.int32),
        "edge_v": v.astype(np.int32),
    }


def build_graph(
    nodes: dict[int, tuple[float, float]],
    ways: list[dict],
    *,
    bbox: tuple[float, float, float, float] | None = None,
    name: str = "osm",
    provenance: dict[str, Any] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Split ways at junctions and pack the result into flat arrays."""
    if not ways:
        raise OsmSourceError("no drivable OSM ways available to build a graph")

    # 1. Junction nodes: way endpoints, or a node shared by >= 2 ways.
    use_count: dict[int, int] = {}
    kept: list[dict] = []
    for w in ways:
        refs = [r for r in w["refs"] if r in nodes]
        if len(refs) < 2:
            continue
        w = dict(w)
        w["refs"] = refs
        kept.append(w)
        for r in refs:
            use_count[r] = use_count.get(r, 0) + 1
    if not kept:
        raise OsmSourceError("every OSM way lost its geometry (missing node coords)")

    junction: set[int] = set()
    for w in kept:
        refs = w["refs"]
        junction.add(refs[0])
        junction.add(refs[-1])
        for r in refs[1:-1]:
            if use_count.get(r, 0) >= 2:
                junction.add(r)

    # 2. Compact node table: only nodes referenced by a kept way.
    used = sorted({r for w in kept for r in w["refs"]})
    node_index = {osm_id: i for i, osm_id in enumerate(used)}
    node_lat = np.array([nodes[r][0] for r in used], dtype=np.float64)
    node_lon = np.array([nodes[r][1] for r in used], dtype=np.float64)
    node_osm = np.array(used, dtype=np.int64)

    # 3. Split each way into junction-to-junction edges, keeping geometry.
    edge_nodes: list[int] = []
    edge_ptr: list[int] = [0]
    edge_class: list[int] = []
    edge_oneway: list[int] = []
    edge_way: list[int] = []
    seen: set[tuple[int, ...]] = set()
    for w in kept:
        refs = w["refs"]
        one = _oneway_flag(w)
        if one < 0:
            refs = refs[::-1]
            one = 1
        cls = _CLASS_INDEX[w["highway"]]
        start = 0
        for k in range(1, len(refs)):
            if refs[k] not in junction and k != len(refs) - 1:
                continue
            chunk = refs[start : k + 1]
            start = k
            if len(chunk) < 2:
                continue
            key = tuple(node_index[r] for r in chunk)
            if key in seen or (one == 0 and key[::-1] in seen):
                continue
            seen.add(key)
            edge_nodes.extend(key)
            edge_ptr.append(len(edge_nodes))
            edge_class.append(cls)
            edge_oneway.append(one)
            edge_way.append(int(w["id"]))

    if len(edge_ptr) < 2:
        raise OsmSourceError("way splitting produced no edges")

    edge_nodes_a = np.asarray(edge_nodes, dtype=np.int32)
    edge_ptr_a = np.asarray(edge_ptr, dtype=np.int64)
    edge_class_a = np.asarray(edge_class, dtype=np.int8)
    edge_oneway_a = np.asarray(edge_oneway, dtype=np.int8)
    edge_way_a = np.asarray(edge_way, dtype=np.int64)
    packed = _pack_edges(edge_nodes_a, edge_ptr_a, node_lat, node_lon)

    # 4. Drop degenerate (sub-metre) edges, then repack.
    good = packed["edge_len_m"] > 0.5
    if not np.all(good):
        keep_idx = np.flatnonzero(good)
        counts = np.diff(edge_ptr_a)[keep_idx]
        take = np.concatenate(
            [np.arange(edge_ptr_a[e], edge_ptr_a[e + 1]) for e in keep_idx]
        )
        edge_nodes_a = edge_nodes_a[take]
        edge_ptr_a = np.zeros(keep_idx.size + 1, dtype=np.int64)
        edge_ptr_a[1:] = np.cumsum(counts)
        edge_class_a = edge_class_a[keep_idx]
        edge_oneway_a = edge_oneway_a[keep_idx]
        edge_way_a = edge_way_a[keep_idx]
        packed = _pack_edges(edge_nodes_a, edge_ptr_a, node_lat, node_lon)
    n_edges = edge_ptr_a.size - 1
    u = packed["edge_u"]
    v = packed["edge_v"]

    # 5. Routing adjacency (CSR: node index -> outgoing edge ids).
    #    Reverse traversals of two-way edges are stored as ``edge_id + n_edges``.
    two_way = np.flatnonzero(edge_oneway_a == 0)
    src = np.concatenate([u, v[two_way]])
    eid = np.concatenate([np.arange(n_edges), two_way + n_edges]).astype(np.int64)
    order = np.argsort(src, kind="stable")
    adj_edge = eid[order].astype(np.int64)
    n_nodes = node_lat.size
    adj_ptr = np.zeros(n_nodes + 1, dtype=np.int64)
    adj_ptr[1:] = np.cumsum(np.bincount(src[order].astype(np.int64), minlength=n_nodes))

    # 6. Uniform-grid spatial index over edge bounding boxes.
    if bbox is None:
        bbox = (
            float(node_lat.min()),
            float(node_lon.min()),
            float(node_lat.max()),
            float(node_lon.max()),
        )
    grid_lat0 = float(np.floor(node_lat.min() / GRID_DEG) * GRID_DEG)
    grid_lon0 = float(np.floor(node_lon.min() / GRID_DEG) * GRID_DEG)
    n_lat = int(np.ceil((node_lat.max() - grid_lat0) / GRID_DEG)) + 1
    n_lon = int(np.ceil((node_lon.max() - grid_lon0) / GRID_DEG)) + 1

    owner = np.repeat(np.arange(n_edges), np.diff(edge_ptr_a))
    vlat = node_lat[edge_nodes_a]
    vlon = node_lon[edge_nodes_a]
    lat_min = np.full(n_edges, np.inf)
    lat_max = np.full(n_edges, -np.inf)
    lon_min = np.full(n_edges, np.inf)
    lon_max = np.full(n_edges, -np.inf)
    np.minimum.at(lat_min, owner, vlat)
    np.maximum.at(lat_max, owner, vlat)
    np.minimum.at(lon_min, owner, vlon)
    np.maximum.at(lon_max, owner, vlon)
    i0 = np.floor((lat_min - grid_lat0) / GRID_DEG).astype(np.int64)
    i1 = np.floor((lat_max - grid_lat0) / GRID_DEG).astype(np.int64)
    j0 = np.floor((lon_min - grid_lon0) / GRID_DEG).astype(np.int64)
    j1 = np.floor((lon_max - grid_lon0) / GRID_DEG).astype(np.int64)
    cells: list[np.ndarray] = []
    owners: list[np.ndarray] = []
    for e in range(n_edges):
        ii = np.arange(i0[e], i1[e] + 1)
        jj = np.arange(j0[e], j1[e] + 1)
        c = (ii[:, None] * n_lon + jj[None, :]).ravel()
        cells.append(c)
        owners.append(np.full(c.size, e, dtype=np.int32))
    cells_a = np.concatenate(cells) if cells else np.zeros(0, dtype=np.int64)
    owners_a = np.concatenate(owners) if owners else np.zeros(0, dtype=np.int32)
    order = np.argsort(cells_a, kind="stable")
    grid_edge = owners_a[order]
    n_cells = n_lat * n_lon
    grid_ptr = np.zeros(n_cells + 1, dtype=np.int64)
    grid_ptr[1:] = np.cumsum(np.bincount(cells_a[order], minlength=n_cells))

    meta = {
        "name": name,
        "source": "openstreetmap",
        "built_from_drive_data": False,
        "guarantee": (
            "Built from OpenStreetMap only. No IO-VNBD trajectory, GNSS fix or "
            "CSV column was read while building this graph."
        ),
        "bbox_lat_min": float(bbox[0]),
        "bbox_lon_min": float(bbox[1]),
        "bbox_lat_max": float(bbox[2]),
        "bbox_lon_max": float(bbox[3]),
        "highway_classes": list(HIGHWAY_CLASSES),
        "n_nodes": int(n_nodes),
        "n_edges": int(n_edges),
        "n_segments": int(packed["seg_len_m"].size),
        "total_edge_length_km": float(packed["edge_len_m"].sum() / 1000.0),
        "median_edge_len_m": float(np.median(packed["edge_len_m"])),
        "oneway_frac": float(np.mean(edge_oneway_a != 0)),
        "grid_deg": GRID_DEG,
        "grid_n_lat": int(n_lat),
        "grid_n_lon": int(n_lon),
        "tile_deg": TILE_DEG,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "attribution": "(c) OpenStreetMap contributors, ODbL 1.0",
    }
    if provenance:
        meta["provenance"] = provenance
    if verbose:
        print(
            f"  graph: {n_nodes} nodes, {n_edges} edges, "
            f"{meta['total_edge_length_km']:.1f} km of road, "
            f"median edge {meta['median_edge_len_m']:.0f} m"
        )

    return {
        "meta": meta,
        "node_lat": node_lat,
        "node_lon": node_lon,
        "node_osm_id": node_osm,
        "edge_ptr": edge_ptr_a,
        "edge_nodes": edge_nodes_a,
        "edge_u": u,
        "edge_v": v,
        "edge_len_m": packed["edge_len_m"],
        "edge_bearing_deg": packed["edge_bearing_deg"],
        "edge_class": edge_class_a,
        "edge_oneway": edge_oneway_a,
        "edge_way_id": edge_way_a,
        "seg_ptr": packed["seg_ptr"],
        "seg_len_m": packed["seg_len_m"],
        "seg_bearing_deg": packed["seg_bearing_deg"],
        "adj_ptr": adj_ptr,
        "adj_edge": adj_edge,
        "grid_ptr": grid_ptr,
        "grid_edge": grid_edge,
        "grid_lat0": np.float64(grid_lat0),
        "grid_lon0": np.float64(grid_lon0),
        "grid_deg": np.float64(GRID_DEG),
        "grid_n_lat": np.int64(n_lat),
        "grid_n_lon": np.int64(n_lon),
    }


def save_graph(graph: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in graph.items() if k not in ("meta", "path")}
    payload["meta_json"] = np.array(json.dumps(graph["meta"]))
    np.savez_compressed(path, **payload)
    meta_path = path.with_name(path.name.replace(".npz", "") + ".meta.json")
    meta_path.write_text(json.dumps(graph["meta"], indent=2), encoding="utf-8")
    return path


def load_graph(path: Path | str) -> dict[str, Any]:
    """Load a ``.graph.npz`` written by :func:`save_graph`."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Build it with: python maps/osm_extract.py --region <name>"
        )
    with np.load(path, allow_pickle=False) as z:
        graph = {k: z[k] for k in z.files if k != "meta_json"}
        graph["meta"] = json.loads(str(z["meta_json"]))
    graph["path"] = str(path)
    return graph


def build_region(
    region: str,
    *,
    offline: bool = False,
    out_path: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    if region not in REGIONS:
        raise KeyError(f"unknown region {region!r}; known: {sorted(REGIONS)}")
    bbox = tuple(REGIONS[region]["bbox"])
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict] = []
    used_sources: list[str] = []
    seen_way_ids: set[int] = set()
    for kind, path in iter_sources(bbox, offline=offline, verbose=verbose):
        try:
            n, w = _read_osm_xml(path) if kind == "osm_xml" else _read_overpass_json(path)
        except (OSError, ValueError, ET.ParseError) as exc:
            if verbose:
                print(f"  skip {path.name}: {exc}")
            continue
        nodes.update(n)
        for way in w:
            if way["id"] in seen_way_ids:
                continue
            seen_way_ids.add(way["id"])
            ways.append(way)
        used_sources.append(f"{kind}:{path.name}")
    if not ways:
        raise OsmSourceError(
            "No OSM data available. Either allow network access (Overpass) or drop "
            f"an .osm XML extract into {cache_dir() / 'osm'} and re-run with --offline."
        )
    provenance = {
        "region": region,
        "region_note": REGIONS[region]["note"],
        "bbox": list(bbox),
        "n_sources": len(used_sources),
        "sources": used_sources[:64],
        "sources_truncated": len(used_sources) > 64,
        "offline": bool(offline),
        "overpass_endpoints": [] if offline else list(OVERPASS_ENDPOINTS),
    }
    graph = build_graph(
        nodes, ways, bbox=bbox, name=region, provenance=provenance, verbose=verbose
    )
    out = Path(out_path) if out_path else default_graph_path(region)
    save_graph(graph, out)
    if verbose:
        print(f"  wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")
    graph["path"] = str(out)
    return graph


def main() -> int:
    ap = argparse.ArgumentParser(description="Build an offline OSM road graph.")
    ap.add_argument("--region", default="iovnbd_midlands")
    ap.add_argument("--offline", action="store_true", help="cache / local XML only")
    ap.add_argument("--out", default=None)
    ap.add_argument("--list-regions", action="store_true")
    args = ap.parse_args()
    if args.list_regions:
        for name, spec in REGIONS.items():
            print(f"{name}: bbox={spec['bbox']}  {spec['note']}")
        return 0
    try:
        build_region(
            args.region,
            offline=args.offline,
            out_path=Path(args.out) if args.out else None,
        )
    except OsmSourceError as exc:
        print(f"NO OSM SOURCE: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
