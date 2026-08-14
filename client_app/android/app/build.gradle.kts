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

// Inject public node keys into APK assets only. Per-device Ed25519 client keys
// are generated on first run (never a shared client_ed25519.priv in every APK).
// Live catalog: IS node_elgamal.pub; DE de_node_elgamal.pub;
// exit_node_elgamal.pub mirrors DE for multi-hop residual-via-exit.
// US us_node_elgamal.pub is **retired** — not injected (stale dials normalize to DE).
// Wrong pub → hybrid decrypt fail → silent node drop → timeout.
// rootProject = client_app/android → ../.. = restore_privacy
tasks.register("copyRptSecretsToAssets") {
    doLast {
        val destDir = file("src/main/assets/secrets")
        destDir.mkdirs()
        // Remove any previously injected shared client priv / retired US pin
        file("src/main/assets/secrets/client_ed25519.priv").let { if (it.exists()) it.delete() }
        file("src/main/assets/secrets/us_node_elgamal.pub").let { if (it.exists()) it.delete() }
        val names = listOf(
            "node_elgamal.pub",
            "de_node_elgamal.pub",
            "sg_node_elgamal.pub",
            "exit_node_elgamal.pub",
        )
        for (name in names) {
            val candidates = listOf(
                rootProject.file("../../product/$name"),
                rootProject.file("../../secrets/$name"),
            )
            val dest = file("src/main/assets/secrets/$name")
            val src = candidates.firstOrNull { it.exists() }
            if (src != null) {
                src.copyTo(dest, overwrite = true)
                logger.lifecycle("copyRptSecretsToAssets: injected $name from ${src.absolutePath}")
            } else if (name == "node_elgamal.pub" || name == "de_node_elgamal.pub" || name == "sg_node_elgamal.pub") {
                logger.warn(
                    "copyRptSecretsToAssets: missing product/ and secrets/ $name — APK handshake will fail"
                )
            } else {
                // exit pin for multihop; warn if missing
                logger.warn(
                    "copyRptSecretsToAssets: missing $name — residual HELLO for that peer will fail closed"
                )
            }
        }
    }
}

tasks.named("preBuild").configure {
    dependsOn("copyRptSecretsToAssets")
}
