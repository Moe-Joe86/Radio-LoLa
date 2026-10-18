plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "de.moejoe.radiolola"
    compileSdk = 35

    defaultConfig {
        applicationId = "de.moejoe.radiolola"
        minSdk = 24
        targetSdk = 35
        // Jeder Bau auf GitHub zählt hoch, damit Android die neue APK als Aktualisierung annimmt.
        versionCode = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1
        versionName = "1.$versionCode"
    }

    // Fester Schlüssel im Repo: Jede neue APK lässt sich über die alte installieren. Er schützt nichts Geheimes.
    signingConfigs {
        create("fest") {
            storeFile = file("radio-lola.keystore")
            storePassword = "radiolola"
            keyAlias = "radiolola"
            keyPassword = "radiolola"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("fest")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    lint {
        checkReleaseBuilds = false
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
