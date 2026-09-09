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
        // MapLibre Native (org.maplibre.gl:android-sdk) is published to Maven
        // Central, so no extra repository is needed. No API key, no billing.
        mavenCentral()
    }
}

rootProject.name = "IDR"
include(":app")
