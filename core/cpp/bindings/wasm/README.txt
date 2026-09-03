Emscripten / WebAssembly bindings for the same C++17 navigation core.

Goal: one codebase compiled to nav_core.wasm that the React / MapLibre
research console loads. Replay a log entirely client-side — no backend.

Planned toolchain
  emsdk  (emcc / em++ matching C++17)
  CMake 3.16+ via emcmake
  Output  nav_core.wasm + JS glue (MODULARIZE=1)

Example:

  emcmake cmake -B build-wasm -DSIH26168_BUILD_WASM=ON
  cmake --build build-wasm

nav_wasm.cpp will export a C ABI (or Embind) around nav::runEngine:
  run_log(imu*, n_imu, gnss*, n_gnss, meta) → trajectory buffer
The web console already has a TypeScript core (core/ts). WASM replaces
it only if this build is green — same golden vectors, 1e-6.

Decision rule — SIH26168_PROJECT_BIBLE.md §5.3, decide by 15 Oct
  If this .wasm build AND the NDK .so build are not both green by
  15 October, abandon the single-core plan and keep the TypeScript
  core for web plus a Kotlin port for Android, locked together by
  the golden-vector suite.

This folder is a placeholder until that gate.
