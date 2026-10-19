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
        // Every build on GitHub counts up, so Android accepts the new APK as an update.
        versionCode = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1
        versionName = "1.$versionCode"
    }

    // Fixed key in the repository: every new APK installs over the old one. It protects nothing secret.
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
