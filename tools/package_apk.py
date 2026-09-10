"""Assemble a signed APK from Gradle's own build intermediates.

Why this exists
---------------
Gradle cannot run in some sandboxed environments: it always forks a single-use
daemon and talks to it over a loopback socket, and where outbound loopback
connections are blocked the build dies at startup with "Unable to establish
loopback connection" -- before compiling anything.

But Gradle's *outputs* survive. Once `:app:assembleStandardDebug` has run once
on a machine that could do it, `app/build/intermediates/` holds everything the
final packaging step needs: linked resources, dex, merged native libs, assets.
This script performs only that last step, using the Android SDK build-tools
directly, so a fresh APK can be produced from already-compiled classes.

It is a packaging tool, not a build system. It compiles nothing. If the Kotlin
has changed since the last successful Gradle run, the intermediates are stale
and this will faithfully package the *old* code -- so it prints the age of what
it found and refuses to run silently on something ancient.

    python tools/package_apk.py --flavor standard --build-type debug
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INTER = REPO / "android" / "app" / "build" / "intermediates"
OUT_DIR = REPO / "android" / "dist"

# Entries that must not be deflated: the runtime maps them directly.
STORE_SUFFIXES = (".so", ".onnx", ".arsc")


def find_build_tools() -> Path:
    """Locate build-tools, preferring the newest."""
    roots = []
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        v = os.environ.get(env)
        if v:
            roots.append(Path(v))
    roots += [
        Path("C:/idr-build/android-sdk"),
        Path.home() / "AppData/Local/Android/Sdk",
        Path.home() / "Android/Sdk",
    ]
    for r in roots:
        bt = r / "build-tools"
        if bt.is_dir():
            versions = sorted((d for d in bt.iterdir() if d.is_dir()), reverse=True)
            if versions:
                return versions[0]
    raise SystemExit("Could not find Android build-tools. Set ANDROID_HOME.")


def newest_mtime(p: Path) -> float:
    if p.is_file():
        return p.stat().st_mtime
    best = 0.0
    for f in p.rglob("*"):
        if f.is_file():
            best = max(best, f.stat().st_mtime)
    return best


def collect_dex(variant: str) -> list[Path]:
    """Dex from both the project and its dependencies, in a stable order.

    Ordering matters: the primary classes.dex must contain the app entry points,
    so project dex is emitted first.
    """
    dex_root = INTER / "dex" / variant
    project = sorted((dex_root / f"mergeProjectDex{variant[0].upper()}{variant[1:]}").rglob("*.dex"))
    ext = sorted((dex_root / f"mergeExtDex{variant[0].upper()}{variant[1:]}").rglob("*.dex"))
    if not project and not ext:
        # Fall back to any dex under the variant.
        return sorted(dex_root.rglob("*.dex"))
    return project + ext


def redex_project(bt: Path, variant: str, work: Path) -> list[Path]:
    """Re-dex the project's freshly compiled classes.

    Gradle's dex intermediates can lag its Kotlin output: the compiler runs,
    then the build dies before dexing. Packaging the stale dex silently ships
    old code -- which is how a rebuilt APK ends up missing the feature it was
    rebuilt for. So dex the current classes ourselves.

    Any dependency added since the last successful dex must also be dexed here,
    because the merged dependency dex will not contain it.
    """
    kotlin_cls = INTER.parent / "tmp" / "kotlin-classes" / variant
    cap = variant[0].upper() + variant[1:]
    javac_cls = INTER / "javac" / variant / f"compile{cap}JavaWithJavac" / "classes"
    r_jar = (
        INTER
        / "compile_and_runtime_not_namespaced_r_class_jar"
        / variant
        / f"process{cap}Resources"
        / "R.jar"
    )

    inputs: list[Path] = []
    for p in (kotlin_cls, javac_cls):
        if p.is_dir():
            inputs.extend(sorted(p.rglob("*.class")))
    if r_jar.is_file():
        inputs.append(r_jar)

    # Dependencies newer than the merged dependency dex.
    cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
    extra_jars: list[Path] = []
    for aar in cache.glob("com.journeyapps/zxing-android-embedded/*/*/*.aar"):
        dest = work / "zxing_aar"
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(aar) as z:
            if "classes.jar" in z.namelist():
                out = dest / "classes.jar"
                out.write_bytes(z.read("classes.jar"))
                extra_jars.append(out)
    extra_jars.extend(sorted(cache.glob("com.google.zxing/core/*/*/core-*.jar")))
    inputs.extend(extra_jars)

    if not inputs:
        raise SystemExit(f"No compiled classes found for {variant}.")

    android_jar = None
    for root in (Path("C:/idr-build/android-sdk"), Path(os.environ.get("ANDROID_HOME", ""))):
        for plat in sorted((root / "platforms").glob("android-*"), reverse=True):
            if (plat / "android.jar").is_file():
                android_jar = plat / "android.jar"
                break
        if android_jar:
            break
    if android_jar is None:
        raise SystemExit("Could not find android.jar.")

    out = work / "dex"
    out.mkdir(parents=True, exist_ok=True)
    listing = work / "d8_inputs.txt"
    listing.write_text("\n".join(str(p) for p in inputs), encoding="utf-8")

    print(f"  dexing {len(inputs)} inputs "
          f"({len(extra_jars)} newly-added dependency jars)...")
    subprocess.run(
        [
            str(bt / "d8.bat"),
            "--debug",
            "--min-api", "26",
            "--lib", str(android_jar),
            "--output", str(out),
            f"@{listing}",
        ],
        check=True,
    )
    dex = sorted(out.glob("*.dex"), key=lambda p: (len(p.name), p.name))
    print(f"  produced {len(dex)} project dex")
    return dex


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--flavor", default="standard")
    ap.add_argument("--build-type", default="debug", choices=["debug", "release"])
    ap.add_argument("--max-age-hours", type=float, default=48.0)
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--abi",
        default="arm64-v8a",
        help="comma-separated ABIs to include, or 'all'. The merged_native_libs "
        "intermediate can still hold x86/x86_64 from an older build even after "
        "abiFilters was narrowed, and an emulator has no usable IMU anyway, so "
        "arm64-v8a alone is the right artifact for a phone.",
    )
    args = ap.parse_args()
    abis = None if args.abi == "all" else {a.strip() for a in args.abi.split(",") if a.strip()}

    variant = args.flavor + args.build_type.capitalize()
    cap = variant[0].upper() + variant[1:]
    bt = find_build_tools()
    print(f"build-tools: {bt}")

    ap_file = (
        INTER
        / "linked_resources_binary_format"
        / variant
        / f"process{cap}Resources"
        / f"linked-resources-binary-format-{variant}.ap_"
    )
    if not ap_file.is_file():
        raise SystemExit(f"No linked resources for {variant}: {ap_file}\n"
                         "Run a Gradle build once on a machine that can, then re-run this.")

    work = REPO / "android" / "build-tmp" / variant
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    # Project dex is rebuilt from current classes; dependency dex is reused
    # (deps do not change unless the build file does, and anything newly added
    # is dexed alongside the project in redex_project).
    dex = redex_project(bt, variant, work)
    ext_dir = INTER / "dex" / variant / f"mergeExtDex{cap}"
    dex += sorted(ext_dir.rglob("*.dex"))
    if not dex:
        raise SystemExit(f"No dex found for {variant}.")

    native = INTER / "merged_native_libs" / variant / f"merge{cap}NativeLibs" / "out" / "lib"
    assets_src = REPO / "android" / "app" / "src" / "main" / "assets"

    age_h = (time.time() - max(newest_mtime(ap_file), max(newest_mtime(d) for d in dex))) / 3600.0
    print(f"intermediates age: {age_h:.1f} h  ({len(dex)} dex files)")
    if age_h > args.max_age_hours:
        raise SystemExit(
            f"Intermediates are {age_h:.1f} h old (limit {args.max_age_hours}). "
            "They may not match current source. Re-run Gradle, or pass a larger "
            "--max-age-hours if you know they are current."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"COAST-{args.flavor}-{args.build_type}"
    unsigned = OUT_DIR / f"{stem}-unsigned.apk"
    aligned = OUT_DIR / f"{stem}-aligned.apk"
    final = Path(args.out) if args.out else OUT_DIR / f"{stem}.apk"

    # 1) base = linked resources (manifest + resources.arsc + res/), copied
    #    entry by entry so each keeps its original compression.
    print("packaging...")
    with zipfile.ZipFile(ap_file) as src, zipfile.ZipFile(
        unsigned, "w", zipfile.ZIP_DEFLATED
    ) as z:
        for info in src.infolist():
            data = src.read(info.filename)
            ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            ni.compress_type = info.compress_type
            ni.external_attr = info.external_attr
            z.writestr(ni, data)

        # 2) dex, renumbered as Android expects
        for i, d in enumerate(dex):
            name = "classes.dex" if i == 0 else f"classes{i + 1}.dex"
            z.write(d, name, compress_type=zipfile.ZIP_DEFLATED)
        print(f"  + {len(dex)} dex")

        # 3) native libs, stored uncompressed so they can be mapped in place
        n_so = 0
        skipped: set[str] = set()
        if native.is_dir():
            for so in sorted(native.rglob("*.so")):
                rel = so.relative_to(native).as_posix()
                abi = rel.split("/")[0]
                if abis is not None and abi not in abis:
                    skipped.add(abi)
                    continue
                # extractNativeLibs=false in the manifest, so these must stay
                # uncompressed and page-aligned or the loader cannot map them.
                z.write(so, f"lib/{rel}", compress_type=zipfile.ZIP_STORED)
                n_so += 1
        print(f"  + {n_so} native libs"
              + (f"  (skipped ABIs: {', '.join(sorted(skipped))})" if skipped else ""))

        # 4) Java resources from dependency jars: META-INF/services entries,
        #    Kotlin builtins, okhttp's public-suffix list. Easy to forget and
        #    fatal to omit -- without
        #    META-INF/services/kotlinx.coroutines.internal.MainDispatcherFactory
        #    the coroutines main dispatcher cannot be resolved and the app dies
        #    on launch, with no missing class to point at.
        jres = (
            INTER
            / "merged_java_res"
            / variant
            / f"merge{cap}JavaResource"
            / "base.jar"
        )
        n_jr = 0
        if jres.is_file():
            with zipfile.ZipFile(jres) as jz:
                for info in jz.infolist():
                    if info.is_dir():
                        continue
                    z.writestr(
                        zipfile.ZipInfo(info.filename, date_time=info.date_time),
                        jz.read(info.filename),
                        compress_type=zipfile.ZIP_DEFLATED,
                    )
                    n_jr += 1
            print(f"  + {n_jr} java resources")
        else:
            print(f"  ! no merged java resources at {jres} -- app will likely "
                  f"crash on launch")

        # 5) assets straight from source
        n_as = 0
        if assets_src.is_dir():
            for f in sorted(assets_src.rglob("*")):
                if not f.is_file():
                    continue
                rel = f"assets/{f.relative_to(assets_src).as_posix()}"
                ct = (
                    zipfile.ZIP_STORED
                    if f.suffix.lower() in STORE_SUFFIXES
                    else zipfile.ZIP_DEFLATED
                )
                z.write(f, rel, compress_type=ct)
                n_as += 1
        print(f"  + {n_as} assets")

    # 5) align. -p page-aligns .so so they can be loaded without extraction.
    if aligned.exists():
        aligned.unlink()
    subprocess.run(
        [str(bt / "zipalign.exe"), "-p", "-f", "4", str(unsigned), str(aligned)],
        check=True,
    )
    print("  aligned")

    # 6) sign with the standard debug key -- installable for testing, and
    #    honestly not a Play-uploadable artifact.
    ks = Path.home() / ".android" / "debug.keystore"
    if not ks.is_file():
        raise SystemExit(f"No debug keystore at {ks}. Run any Gradle debug build once.")
    signer = bt / "apksigner.bat"
    subprocess.run(
        [
            str(signer), "sign",
            "--ks", str(ks),
            "--ks-pass", "pass:android",
            "--ks-key-alias", "androiddebugkey",
            "--key-pass", "pass:android",
            "--out", str(final),
            str(aligned),
        ],
        check=True,
    )
    r = subprocess.run([str(signer), "verify", str(final)], capture_output=True, text=True)
    ok = r.returncode == 0

    unsigned.unlink(missing_ok=True)
    aligned.unlink(missing_ok=True)
    idsig = final.with_suffix(".apk.idsig")
    idsig.unlink(missing_ok=True)

    size_mb = final.stat().st_size / 1e6
    print(f"\n{'OK' if ok else 'SIGNATURE VERIFY FAILED'}  {final}  ({size_mb:.1f} MB)")
    if not ok:
        print(r.stdout or r.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
