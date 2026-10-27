plugins {
    id("com.android.application")
}

// Deux apps distinctes, comme sur iOS :
// beta = VendrediPartyBETA (site de test, develop) ; prod = VendrediParty (site principal, main).
data class Variant(val suffix: String, val host: String, val label: String)

val variants = mapOf(
    "beta" to Variant(".beta", "partytest.bobycharbon.ch", "Party BETA"),
    "prod" to Variant("", "party.bobycharbon.ch", "Party !"),
)

// Numéro de version : celui de l'exécution GitHub Actions (toujours croissant), 1 en local.
val buildNumber = (System.getenv("BUILD_NUMBER") ?: "1").toInt()

android {
    namespace = "ch.bobycharbon.party"
    compileSdk = 36

    defaultConfig {
        applicationId = "ch.bobycharbon.party"
        minSdk = 24
        targetSdk = 36
        versionCode = buildNumber
        versionName = "1.0.0"
    }

    flavorDimensions += "site"
    productFlavors {
        variants.forEach { (name, v) ->
            create(name) {
                dimension = "site"
                applicationIdSuffix = v.suffix
                val url = "https://${v.host}/"
                manifestPlaceholders += mapOf("hostName" to v.host, "defaultUrl" to url, "launcherName" to v.label)
                resValue("string", "app_name", v.label)
                // Digital Asset Links : le site déclare l'app (/.well-known/assetlinks.json), l'app déclare le site.
                resValue(
                    "string", "asset_statements",
                    """[{"relation":["delegate_permission/common.handle_all_urls"],"target":{"namespace":"web","site":"https://${v.host}"}}]""",
                )
            }
        }
    }

    // Clé d'envoi (upload key) fournie par les secrets GitHub ; Google re-signe l'app (Play App Signing).
    val keystorePath = System.getenv("ANDROID_KEYSTORE_PATH")
    signingConfigs {
        if (keystorePath != null) {
            create("upload") {
                storeFile = file(keystorePath)
                storeType = "pkcs12"
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (keystorePath != null) signingConfig = signingConfigs.getByName("upload")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("com.google.androidbrowserhelper:androidbrowserhelper:2.5.0")
}
