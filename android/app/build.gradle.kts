plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "in.sih26168.idr"
    compileSdk = 35

    defaultConfig {
        applicationId = "in.sih26168.idr"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "0.3.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

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

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
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
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-service:2.8.7")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-text-google-fonts")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // On-device inference for lab/models/weights/avnet_tiny.onnx (AVNet-tiny,
    // 20×6 @ 10 Hz). Required by the problem statement: the trained model runs
    // on the phone, not on a laptop over the wire.
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")

    // Optional MapLibre Native — unpaid, no API key. Swap ui.TrailMap for a
    // MapView when you bundle offline MBTiles. Keep the Canvas placeholder
    // until then so the skeleton builds with zero extras.
    // implementation("org.maplibre.gl:android-sdk:11.5.2")
}
