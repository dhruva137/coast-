// Placeholder JNI surface for libnav_core.
//
// Do not put estimator maths here. The Kotlin app will call into
// nav::runEngine / InvariantEKF after the 15 Oct JNI+WASM go/no-go
// (SIH26168_PROJECT_BIBLE.md §5.3). If both bindings are not green
// by that date, fork the core into Kotlin and TypeScript instead.
//
// Planned exports (names only — implement when the NDK toolchain is wired):
//   Java_org_sih26168_nav_Engine_create
//   Java_org_sih26168_nav_Engine_step
//   Java_org_sih26168_nav_Engine_runLog
//   Java_org_sih26168_nav_Engine_destroy
//
// Pack ISensorFrame / IGnssFix / INavState from include/nav/types.h.
// Keep this file free of lean / EKF / graph logic.

#ifdef SIH26168_BUILD_JNI
// #include <jni.h>
// #include "nav/engine.h"
#endif

// Empty translation unit so a mistaken add_library() still links.
void nav_jni_placeholder() {}
