// Placeholder Emscripten / WASM surface for libnav_core.
//
// Do not put estimator maths here. The web console will call into
// nav::runEngine after the 15 Oct JNI+WASM go/no-go
// (SIH26168_PROJECT_BIBLE.md §5.3). If both bindings are not green
// by that date, keep core/ts and fork rather than ship a half-built
// .wasm.
//
// Planned exports (names only — implement when emsdk is wired):
//   nav_engine_run
//   nav_engine_free
//   nav_lean_solve
// Pack ISensorFrame / INavState from include/nav/types.h.
// Keep this file free of lean / EKF / graph logic.

#ifdef SIH26168_BUILD_WASM
// #include <emscripten.h>
// #include "nav/engine.h"
#endif

// Empty translation unit so a mistaken add_library() still links.
void nav_wasm_placeholder() {}
