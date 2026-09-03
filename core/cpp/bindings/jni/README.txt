JNI / WASM placeholders. Decision rule: if both builds are not green by 15 Oct 2026, fork the core into Kotlin + TypeScript (bible §5.3).

NDK: compile nav_core as a shared library, wrap engine.h in JNI.
Emscripten: em++ -s WASM=1 with the same sources, export runEngine.
