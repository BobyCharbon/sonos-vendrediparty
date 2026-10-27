// App Android « Party ! » : la webapp en Trusted Web Activity (Chrome plein écran, sans barre d'adresse).
// Compilée par GitHub Actions (.github/workflows/android-play.yml) : aucun outil Android n'est requis en local.
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
    }
}

rootProject.name = "Party"
include(":app")
