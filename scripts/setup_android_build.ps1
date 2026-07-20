#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure Android build dependencies for the Flutter RPT client are present.

.DESCRIPTION
  Verifies/installs (when sdkmanager is available):
    - JDK 17 (JAVA_HOME)
    - Android SDK platform-tools, platforms 34–36, build-tools 34–36
    - NDK side-by-side (27/28), CMake 3.22.1
    - Android SDK licenses accepted
  Then runs flutter doctor, flutter pub get, and optionally a release APK build.

.PARAMETER SkipApkBuild
  Only install/verify toolchain; do not run flutter build apk.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\setup_android_build.ps1
#>
param(
    [switch]$SkipApkBuild
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ClientApp = Join-Path $Root "client_app"
$Flutter = "C:\src\flutter\bin\flutter.bat"
if (-not (Test-Path $Flutter)) {
    $Flutter = (Get-Command flutter -ErrorAction SilentlyContinue).Source
}
if (-not $Flutter) { throw "Flutter not found. Install Flutter and ensure flutter is on PATH." }

# JDK 17
$jdkCandidates = @(
    $env:JAVA_HOME,
    "C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot",
    "C:\Program Files\Microsoft\jdk-17*",
    "C:\Program Files\Eclipse Adoptium\jdk-17*"
) | Where-Object { $_ }
$jdk = $null
foreach ($c in $jdkCandidates) {
    $resolved = Get-Item $c -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($resolved -and (Test-Path (Join-Path $resolved.FullName "bin\java.exe"))) {
        $jdk = $resolved.FullName
        break
    }
}
if (-not $jdk) {
    throw "JDK 17 not found. Install Microsoft OpenJDK 17 or set JAVA_HOME."
}
$env:JAVA_HOME = $jdk
Write-Host "JAVA_HOME=$env:JAVA_HOME"

# Android SDK
$sdk = $env:ANDROID_HOME
if (-not $sdk -or -not (Test-Path $sdk)) {
    $sdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
}
if (-not (Test-Path $sdk)) {
    throw "Android SDK not found at $sdk. Install Android Studio or command-line tools first."
}
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk
Write-Host "ANDROID_HOME=$env:ANDROID_HOME"

# Persist session-friendly user env (non-destructive if already set)
[Environment]::SetEnvironmentVariable("ANDROID_HOME", $sdk, "User")
[Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $sdk, "User")
[Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk, "User")

# local.properties for Gradle
$lp = Join-Path $ClientApp "android\local.properties"
$sdkEsc = $sdk -replace "\\", "\\"
$flutterSdk = "C:\\src\\flutter"
if ($Flutter -match "flutter\.bat$") {
    $flutterSdk = (Resolve-Path (Join-Path (Split-Path $Flutter) "..")).Path
}
$flutterEsc = $flutterSdk -replace "\\", "\\"
@"
sdk.dir=$sdkEsc
flutter.sdk=$flutterEsc
flutter.buildMode=release
flutter.versionName=0.2.3
flutter.versionCode=1
"@ | Set-Content -Path $lp -Encoding ASCII
Write-Host "Wrote $lp"

# sdkmanager packages
$sm = Join-Path $sdk "cmdline-tools\latest\bin\sdkmanager.bat"
if (Test-Path $sm) {
    Write-Host "Accepting Android SDK licenses..."
    $yes = ("y`n" * 60)
    $yes | & $sm --licenses 2>&1 | Out-Null
    $packages = @(
        "platform-tools",
        "platforms;android-36",
        "platforms;android-35",
        "platforms;android-34",
        "build-tools;36.0.0",
        "build-tools;35.0.0",
        "build-tools;34.0.0",
        "ndk;28.2.13676358",
        "ndk;27.0.12077973",
        "cmake;3.22.1"
    )
    Write-Host "Installing/refreshing SDK packages..."
    & $sm --install $packages 2>&1 | Write-Host
} else {
    Write-Warning "sdkmanager not found at $sm — skipping package install (use Android Studio SDK Manager)."
}

Push-Location $ClientApp
try {
    Write-Host "flutter doctor -v"
    & $Flutter doctor -v
    Write-Host "flutter pub get"
    & $Flutter pub get
    if (-not $SkipApkBuild) {
        Write-Host "flutter build apk --release"
        & $Flutter build apk --release
        $apk = Join-Path $ClientApp "build\app\outputs\flutter-apk\app-release.apk"
        if (-not (Test-Path $apk)) { throw "APK missing after build: $apk" }
        $len = (Get-Item $apk).Length
        Write-Host "APK OK: $apk ($len bytes)"
        if ($len -lt 1MB) { throw "APK too small: $len" }
    }
} finally {
    Pop-Location
}

Write-Host "Android build dependencies ready."
