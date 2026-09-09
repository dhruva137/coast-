import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

/**
 * Release signing, read from `android/keystore.properties`, which is gitignored
 * and must never be committed. Expected keys:
 *
 *     storeFile=C:/path/to/idr-release.jks
 *     storePassword=...
 *     keyAlias=idr
 *     keyPassword=...
 *
 * When the file is absent -- which is the normal case for a teammate who has
 * just cloned, and for CI -- `assembleRelease` still succeeds, signed with the
 * debug key. That build installs and runs for testing but Play will reject it,
 * which is the correct failure mode: a broken build helps nobody, and a release
 * that silently ships unsigned would be worse.
 */
val keystoreProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val hasReleaseKeystore = keystoreProps.getProperty("storeFile")
    ?.let { file(it).exists() } == true

android {
    namespace = "in.sih26168.idr"
    compileSdk = 35

    defaultConfig {
        applicationId = "in.sih26168.idr"
        minSdk = 26
        targetSdk = 35
        // Bump versionCode on every upload; Play refuses a repeat.
        versionCode = 4
        versionName = "0.4.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        resourceConfigurations += listOf("en")

        // ONNX Runtime ships four ABIs, which made the debug APK 91 MB: 42 MB of
        // that was x86/x86_64, used only by emulators. An emulator has no usable
        // IMU, so this app cannot be meaningfully tested on one anyway. Shipping
        // the two real-device ABIs halves the install a judge has to sideload at
        // the venue. Override with -PallAbis=true if an x86 emulator is ever
        // genuinely needed.
        if (!project.hasProperty("allAbis")) {
            ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
        }
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                storeFile = file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    // standard = shippable F8 privacy build (uploads nothing).
    // tracker  = demo-only LAN uploader (src/tracker); never the Play artifact.
    flavorDimensions += "distribution"
    productFlavors {
        create("standard") {
            dimension = "distribution"
            isDefault = true
            buildConfigField("boolean", "LAN_TRACKER", "false")
        }
        create("tracker") {
            dimension = "distribution"
            applicationIdSuffix = ".tracker"
            versionNameSuffix = "-tracker"
            buildConfigField("boolean", "LAN_TRACKER", "true")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            signingConfig = if (hasReleaseKeystore) {
                signingConfigs.getByName("release")
            } else {
                // Only shout about it when a release artifact was actually asked
                // for; this block is evaluated on every Gradle invocation.
                val wantsRelease = gradle.startParameter.taskNames.any {
                    it.contains("Release", ignoreCase = true)
                }
                if (wantsRelease) {
                    logger.warn(
                        "IDR: android/keystore.properties not found -- signing this " +
                            "release build with the DEBUG key. Installable for " +
                            "testing, NOT uploadable to Play. See android/README.md.",
                    )
                }
                signingConfigs.getByName("debug")
            }
        }
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
    androidResources {
        // Keep avnet_tiny.onnx uncompressed so OrtSession maps it without a
        // full inflate on every cold start.
        noCompress += "onnx"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    // Platform splash screen, backported. Required from Android 12; also gives
    // us the exit-animation handoff into Compose so launch reads as one motion.
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-service:2.8.7")

    implementation("androidx.compose.ui:ui")
    // ui-text-google-fonts is deliberately NOT here. It fetches fonts over the
    // network through Play Services, which was the only reason this app ever
    // needed the INTERNET permission. See ui/theme/Type.kt.
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // On-device inference for lab/models/weights/avnet_tiny.onnx (AVNet-tiny,
    // 20×6 @ 10 Hz). Required by the problem statement: the trained model runs
    // on the phone, not on a laptop over the wire.
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")

    // OpenStreetMap basemap under the dead-reckoned track, drawn by MapLibre
    // Native. The problem statement names OpenStreetMap explicitly, and this
    // stack needs NO API key, NO billing account and NO Google Play services:
    // the public OSM tile server is open and MapLibre is a plain Android View.
    // Resolved from Maven Central (mavenCentral() in settings.gradle.kts).
    // Tiles MapLibre has fetched are cached, so the map survives losing the
    // radio -- which is the tunnel demo. See ui/MapLibreDriveMap.kt.
    implementation("org.maplibre.gl:android-sdk:11.5.2")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
