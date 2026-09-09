#!/usr/bin/env python3
"""Generate docs/PRIVACY_REPORT.md by scanning Android manifests and network call sites.

F8 privacy proof artifact. Exact INTERNET wording (never claim absence):

  Declared for public OSM/Carto basemap tiles only; with basemap off,
  network traffic is zero.

Usage (from repo root):
  python tools/privacy_report.py           # write docs/PRIVACY_REPORT.md
  python tools/privacy_report.py --check   # fail if report would change
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OUT_PATH = REPO / "docs" / "PRIVACY_REPORT.md"

# Exact claim language for INTERNET (F8 / verify_claims).
INTERNET_JUSTIFICATION = (
    "Declared for public OSM/Carto basemap tiles only; with basemap off, "
    "network traffic is zero."
)

PERMISSION_JUSTIFICATIONS: dict[str, str] = {
    "android.permission.INTERNET": INTERNET_JUSTIFICATION,
    "android.permission.ACCESS_NETWORK_STATE": (
        "Lets MapLibre detect connectivity before requesting public basemap tiles; "
        "no position or session data is sent."
    ),
    "android.permission.FOREGROUND_SERVICE": (
        "Required so live dead reckoning and CSV logging survive the screen turning off."
    ),
    "android.permission.FOREGROUND_SERVICE_LOCATION": (
        "API 34+ type permission for the location foregroundServiceType on RecordService."
    ),
    "android.permission.FOREGROUND_SERVICE_DATA_SYNC": (
        "API 34+ type permission for the dataSync foregroundServiceType used while writing session CSV."
    ),
    "android.permission.POST_NOTIFICATIONS": (
        "API 33+: shows the ongoing notification that tracking or recording is running."
    ),
    "android.permission.WAKE_LOCK": (
        "Keeps the CPU awake so IMU integration continues with the screen off."
    ),
    "android.permission.ACCESS_COARSE_LOCATION": (
        "Optional at runtime; arms and navigates without it when the user declines."
    ),
    "android.permission.ACCESS_FINE_LOCATION": (
        "Optional at runtime for GNSS fusion when the user grants it; not required to arm."
    ),
    "android.permission.HIGH_SAMPLING_RATE_SENSORS": (
        "API 31+: allows SENSOR_DELAY_FASTEST sampling above 200 Hz for the estimator."
    ),
    "android.permission.ACCESS_WIFI_STATE": (
        "May appear via MapLibre/network stack merges; not used to exfiltrate user data."
    ),
}

# (regex, purpose template). Groups may capture a host-ish hint.
NETWORK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bLanUploader\b"),
        "Demo-only LAN POST of HUD estimate to presenter laptop (/ingest); tracker flavor only.",
    ),
    (
        re.compile(r"\bHttpURLConnection\b"),
        "Outbound HTTP via HttpURLConnection (LAN uploader or similar).",
    ),
    (
        re.compile(r"\bOkHttp\b"),
        "OkHttp client usage.",
    ),
    (
        re.compile(r"\bURLConnection\b"),
        "java.net.URLConnection open for outbound traffic.",
    ),
    (
        re.compile(r"\.openConnection\s*\("),
        "URL.openConnection() call site for outbound HTTP.",
    ),
    (
        re.compile(r"\baxios\b"),
        "axios HTTP client call site.",
    ),
    (
        re.compile(r"\bfetch\s*\("),
        "Browser/Node fetch() to a local or remote endpoint.",
    ),
    (
        re.compile(r"basemaps\.cartocdn\.com"),
        "Public Carto dark basemap raster tiles (MapLibre style); no API key, no user data.",
    ),
    (
        re.compile(r"tile\.openstreetmap\.org"),
        "Public OpenStreetMap raster tiles for map basemap / console map.",
    ),
    (
        re.compile(r"https://unpkg\.com/maplibre"),
        "Console CDN load of MapLibre GL (presenter laptop UI only).",
    ),
    (
        re.compile(r"cdn\.jsdelivr\.net/npm/chart\.js"),
        "Console CDN load of Chart.js for real training loss (presenter laptop UI only).",
    ),
]

SKIP_DIR_NAMES = {
    "node_modules",
    ".git",
    "build",
    ".gradle",
    "__pycache__",
    "dist",
    ".vite",
    "ppt_assets",
    "win_tuning",
    "final_demo_pitch",
    "design_v3",
}

SCAN_SUFFIXES = {".kt", ".java", ".ts", ".tsx", ".js", ".jsx", ".py", ".xml", ".html"}


@dataclass(frozen=True)
class PermissionHit:
    permission: str
    rel_path: str
    line_no: int
    justification: str


@dataclass(frozen=True)
class NetworkHit:
    rel_path: str
    line_no: int
    snippet: str
    purpose: str


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def find_manifests() -> list[Path]:
    """Source manifests only (all flavours under src/), not Gradle merge outputs."""
    src_root = REPO / "android" / "app" / "src"
    if not src_root.is_dir():
        return []
    return sorted(p for p in src_root.rglob("AndroidManifest.xml") if not _should_skip(p))


def scan_permissions(manifests: list[Path]) -> list[PermissionHit]:
    perm_re = re.compile(
        r"""<uses-permission\b[^>]*android:name\s*=\s*["'](android\.permission\.[A-Z0-9_]+)["']"""
    )
    hits: list[PermissionHit] = []
    for path in manifests:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, start=1):
            m = perm_re.search(line)
            if not m:
                continue
            name = m.group(1)
            just = PERMISSION_JUSTIFICATIONS.get(
                name,
                "Declared in manifest; add a one-sentence justification in tools/privacy_report.py if new.",
            )
            hits.append(
                PermissionHit(
                    permission=name,
                    rel_path=_rel(path),
                    line_no=i,
                    justification=just,
                )
            )
    return hits


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    # Skip generated / binary-ish trees under android build outputs.
    if "android" in path.parts and any(p in {"build", ".cxx", "intermediates"} for p in path.parts):
        return True
    return False


def iter_scan_files() -> list[Path]:
    roots = [
        REPO / "android" / "app" / "src",
        REPO / "web",
        REPO / "lab",
    ]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if _should_skip(path):
                continue
            out.append(path)
    return sorted(out)


def scan_network_sites(files: list[Path]) -> list[NetworkHit]:
    hits: list[NetworkHit] = []
    seen: set[tuple[str, int, str]] = set()
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        rel = _rel(path)
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("#"):
                # Still scan comments that document tile URLs — they are call-site evidence
                # when they contain live tile host strings inside Kotlin/TS string literals.
                pass
            for pattern, purpose in NETWORK_PATTERNS:
                if not pattern.search(line):
                    continue
                key = (rel, i, purpose)
                if key in seen:
                    continue
                seen.add(key)
                snippet = stripped[:120]
                hits.append(
                    NetworkHit(
                        rel_path=rel,
                        line_no=i,
                        snippet=snippet,
                        purpose=purpose,
                    )
                )
    return hits


def check_flavor_uploader_split() -> tuple[bool, list[str]]:
    """Confirm standard has no uploader; LanUploader only under tracker sources."""
    notes: list[str] = []
    ok = True

    lan_files = list((REPO / "android").rglob("LanUploader.kt")) if (REPO / "android").is_dir() else []
    lan_files = [p for p in lan_files if not _should_skip(p)]

    if not lan_files:
        notes.append("FAIL: LanUploader.kt not found under android/ (expected under src/tracker).")
        ok = False
    else:
        for p in lan_files:
            rel = _rel(p)
            if "/tracker/" not in rel.replace("\\", "/"):
                notes.append(f"FAIL: LanUploader outside tracker sources: {rel}")
                ok = False
            else:
                notes.append(f"OK: LanUploader only under tracker → `{rel}`")

    standard_hooks = REPO / "android/app/src/standard/java/in/sih26168/idr/demo/TrackerHooks.kt"
    tracker_hooks = REPO / "android/app/src/tracker/java/in/sih26168/idr/demo/TrackerHooks.kt"
    if standard_hooks.is_file():
        text = standard_hooks.read_text(encoding="utf-8")
        if "LanUploader" in text:
            notes.append("FAIL: standard TrackerHooks references LanUploader.")
            ok = False
        elif "Intentionally empty" in text or "no-op" in text.lower() or "empty" in text.lower():
            notes.append(
                f"OK: standard TrackerHooks is a no-op (`{_rel(standard_hooks)}`) — no uploader."
            )
        else:
            notes.append(
                f"OK: standard TrackerHooks has no LanUploader (`{_rel(standard_hooks)}`)."
            )
    else:
        notes.append("WARN: standard TrackerHooks.kt missing — cannot confirm no-op flavor bridge.")

    if tracker_hooks.is_file():
        text = tracker_hooks.read_text(encoding="utf-8")
        if "LanUploader" in text:
            notes.append(f"OK: tracker TrackerHooks wires LanUploader (`{_rel(tracker_hooks)}`).")
        else:
            notes.append("WARN: tracker TrackerHooks does not mention LanUploader.")

    # Ensure no LanUploader import under standard tree.
    standard_src = REPO / "android/app/src/standard"
    if standard_src.is_dir():
        for p in standard_src.rglob("*"):
            if p.suffix.lower() not in {".kt", ".java"}:
                continue
            body = p.read_text(encoding="utf-8", errors="ignore")
            if "LanUploader" in body or "HttpURLConnection" in body:
                notes.append(f"FAIL: network uploader symbol in standard sources: {_rel(p)}")
                ok = False

    return ok, notes


def render_report(
    permissions: list[PermissionHit],
    network: list[NetworkHit],
    flavor_ok: bool,
    flavor_notes: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# COAST privacy report (F8)")
    lines.append("")
    lines.append(
        "Generated by `tools/privacy_report.py` from the current tree. "
        "Regenerate with `python tools/privacy_report.py` "
        "(also wired into `tools/verify_all.py`)."
    )
    lines.append("")
    lines.append("## INTERNET permission (exact wording)")
    lines.append("")
    lines.append(f"> {INTERNET_JUSTIFICATION}")
    lines.append("")
    lines.append(
        "Do **not** claim the app has \"no INTERNET permission\". "
        "Navigation and logging still run with the radio off; the only "
        "app-initiated outbound traffic with basemap on is public OSM/Carto tile fetches."
    )
    lines.append("")
    lines.append("## Android permissions (all manifests / flavours)")
    lines.append("")
    if not permissions:
        lines.append("_No `<uses-permission>` entries found._")
    else:
        lines.append("| Permission | Location | Justification |")
        lines.append("|---|---|---|")
        for hit in permissions:
            loc = f"`{hit.rel_path}:{hit.line_no}`"
            lines.append(f"| `{hit.permission}` | {loc} | {hit.justification} |")
    lines.append("")
    lines.append("### Manifest inventory")
    lines.append("")
    for m in find_manifests():
        lines.append(f"- `{_rel(m)}`")
    lines.append("")
    lines.append("## Flavour split: uploader")
    lines.append("")
    lines.append(
        f"**standard has no uploader:** {'yes' if flavor_ok else 'NO — see failures below'}."
    )
    lines.append("")
    for note in flavor_notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("## Outbound network call sites (scanned)")
    lines.append("")
    lines.append(
        "Heuristic scan for OkHttp / HttpURLConnection / fetch / axios / URLConnection / "
        "LanUploader / known tile & CDN hosts under `android/app/src`, `web`, `lab`."
    )
    lines.append("")
    if not network:
        lines.append("_No matching call sites found._")
    else:
        lines.append("| File:line | Purpose | Snippet |")
        lines.append("|---|---|---|")
        for hit in network:
            snip = hit.snippet.replace("|", "\\|")
            lines.append(
                f"| `{hit.rel_path}:{hit.line_no}` | {hit.purpose} | `{snip}` |"
            )
    lines.append("")
    lines.append("## Airplane-mode / offline demo checklist")
    lines.append("")
    lines.append(
        "Manual product insurance (also mirrored in `docs/OFFLINE_DEMO.md`):"
    )
    lines.append("")
    lines.append("1. Build **standard** APK; confirm Settings privacy copy does not say \"no INTERNET permission\".")
    lines.append("2. Enable airplane mode; turn **basemap off** (SHOW GRID) — expect zero tile traffic.")
    lines.append("3. Arm and navigate; confirm estimator runs without a fix.")
    lines.append("4. Optional: enable airplane mode with bundled MBTiles if present — basemap may still render locally.")
    lines.append("5. On the laptop: `python -m web.coast_console` with Wi‑Fi off — page must still explain itself (map CDN may fall back).")
    lines.append("6. Press Train offline — failure must show a real error, never a fake loss curve.")
    lines.append("7. Tracker flavor only: LAN uploader is opt-in; standard must never POST HUD frames.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_flavor_uploader_ok={flavor_ok}_")
    lines.append("")
    return "\n".join(lines)


def build() -> tuple[str, bool]:
    permissions = scan_permissions(find_manifests())
    network = scan_network_sites(iter_scan_files())
    flavor_ok, flavor_notes = check_flavor_uploader_split()
    # Structural requirement: INTERNET must be present and justified with exact wording.
    internet_hits = [p for p in permissions if p.permission.endswith(".INTERNET")]
    if not internet_hits:
        flavor_ok = False
        flavor_notes.append(
            "FAIL: android.permission.INTERNET not found in any manifest "
            "(report must not claim absence — declare for OSM/Carto tiles)."
        )
    else:
        for h in internet_hits:
            if h.justification != INTERNET_JUSTIFICATION:
                flavor_ok = False
                flavor_notes.append(
                    f"FAIL: INTERNET justification mismatch at {h.rel_path}:{h.line_no}"
                )
    text = render_report(permissions, network, flavor_ok, flavor_notes)
    return text, flavor_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or check docs/PRIVACY_REPORT.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if PRIVACY_REPORT.md is missing or differs from a fresh scan.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write docs/PRIVACY_REPORT.md (default when not --check).",
    )
    args = parser.parse_args(argv)

    text, flavor_ok = build()
    out = OUT_PATH

    if args.check:
        if not out.is_file():
            print(f"FAIL: missing {out.relative_to(REPO)} — run without --check to generate", file=sys.stderr)
            return 1
        existing = out.read_text(encoding="utf-8").replace("\r\n", "\n")
        if existing != text.replace("\r\n", "\n"):
            print(
                f"FAIL: {out.relative_to(REPO)} is stale — run python tools/privacy_report.py",
                file=sys.stderr,
            )
            return 1
        if not flavor_ok:
            print("FAIL: flavour / INTERNET structural checks failed (see report)", file=sys.stderr)
            return 1
        print(f"OK: {out.relative_to(REPO)} matches scan; flavour split OK")
        return 0

    # Default: write
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {out.relative_to(REPO)}")
    if not flavor_ok:
        print("WARN: flavour / INTERNET structural checks reported issues (see report)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
