# R8 rules for the release build (isMinifyEnabled + isShrinkResources).
#
# The rule that matters most is the ONNX Runtime one. ORT is a thin Java layer
# over a native library: the C++ side looks Java classes and fields up by name
# through JNI, and R8 cannot see those references. Stripping or renaming them
# produces a build that compiles, installs, launches, and then fails at
# OrtEnvironment.getEnvironment() with a NoSuchMethod/UnsatisfiedLinkError --
# on the phone, at the venue, in front of judges. The app would not crash: it
# would fall back to the labelled FALLBACK integrator and quietly stop being an
# ML project. Keep the whole package.

-keep class ai.onnxruntime.** { *; }
-keepclassmembers class ai.onnxruntime.** { *; }
-dontwarn ai.onnxruntime.**

# Anything the JNI layer calls back into, everywhere.
-keepclasseswithmembernames class * {
    native <methods>;
}

# The estimator and the frozen log schema. `data` mirrors the CSV/JSON column
# names in lab/ and core/; keeping the names means a stack trace or a dump from
# a release build is still readable against the research code.
-keep class in.sih26168.idr.nav.** { *; }
-keep class in.sih26168.idr.data.** { *; }

# Kotlin metadata, so reflection-based tooling and coroutine debugging still
# resolve types in a minified build.
-keepattributes RuntimeVisibleAnnotations,RuntimeVisibleParameterAnnotations
-keepattributes InnerClasses,Signature,Exceptions,EnclosingMethod
-keep class kotlin.Metadata { *; }

# Readable crash reports. There is no crash reporter in this app -- these are
# for `adb logcat` when a judge hands the phone back.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# Coroutines' service loader and the atomicfu volatile fields.
-keepclassmembers class kotlinx.coroutines.** { volatile <fields>; }
-dontwarn kotlinx.coroutines.**

# org.json is provided by the platform; the test-only artifact must not be
# dragged in or warned about.
-dontwarn org.json.**

# MapLibre Native (the OpenStreetMap basemap). Like ONNX Runtime it is a Java
# layer over a native library, and the C++ side resolves Java classes, fields
# and JNI callbacks by name. Keep the package intact so a minified release still
# draws the map instead of throwing at getMapAsync/setStyle. R8 would otherwise
# strip or rename the reflected members with no compile-time complaint.
-keep class org.maplibre.android.** { *; }
-keep class org.maplibre.geojson.** { *; }
-keepclassmembers class org.maplibre.android.** { *; }
-dontwarn org.maplibre.**
