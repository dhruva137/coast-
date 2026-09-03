pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Optional MapLibre Native (no API key). Uncomment together with the
        // app/build.gradle.kts MapLibre dependency to replace TrailMap Canvas.
        // maven(url = "https://dl.cloudsmith.io/public/maplibre/maplibre-native/maven/")
    }
}

rootProject.name = "IDR"
include(":app")
