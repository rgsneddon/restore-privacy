plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.restoreprivacy.restore_privacy_client"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.restoreprivacy.restore_privacy_client"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.78.1")
}

// Inject admission material into APK assets at build time from gitignored repo secrets/.
// Never commits *.priv — only copies when present on the builder machine.
// rootProject = client_app/android → ../../secrets = restore_privacy/secrets
tasks.register("copyRptSecretsToAssets") {
    doLast {
        val repoSecrets = rootProject.file("../../secrets")
        val destDir = file("src/main/assets/secrets")
        destDir.mkdirs()
        listOf("client_ed25519.priv", "node_elgamal.pub", "client_ed25519.pub").forEach { name ->
            val src = rootProject.file("../../secrets/$name")
            val dest = file("src/main/assets/secrets/$name")
            if (src.exists()) {
                src.copyTo(dest, overwrite = true)
                logger.lifecycle("copyRptSecretsToAssets: injected $name")
            } else {
                logger.warn("copyRptSecretsToAssets: missing ${src.absolutePath}")
            }
        }
    }
}

tasks.named("preBuild").configure {
    dependsOn("copyRptSecretsToAssets")
}
