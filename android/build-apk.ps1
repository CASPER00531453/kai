# Builds the Kai Android app: android\ -> Kai-Android-<version>.apk next to the desktop setup.
# The Android tools refuse a path with non-ASCII letters ("Masaüstü"), so the
# project is mirrored to %LOCALAPPDATA%\KaiBuild\android and built there.

param([string]$Task = "assembleDebug")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$work = Join-Path $env:LOCALAPPDATA "KaiBuild\android"
New-Item -ItemType Directory -Force $work | Out-Null
# /MIR keeps the mirror exact; the build outputs and Gradle's caches stay out of it.
robocopy . $work /MIR /XD build .gradle .kotlin /XF local.properties /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
$sdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
Set-Content -Encoding ascii (Join-Path $work "local.properties") ("sdk.dir=" + ($sdk -replace '\\', '\\'))

# A release is signed with Kai's own key, kept outside the project (and outside git):
# %USERPROFILE%\.kai-android\kai-release.jks with its keystore.properties. Lose it and
# phones can no longer update the app in place.
if ($Task -like "*Release*") {
    $props = Join-Path $env:USERPROFILE ".kai-android\keystore.properties"
    if (-not (Test-Path $props)) { throw "No signing key: $props" }
    foreach ($line in Get-Content $props) {
        $name, $value = $line -split "=", 2
        if ($name) { Set-Item "env:$name" $value }
    }
}

Push-Location $work
# Gradle and Kotlin write notices to stderr; in Windows PowerShell that is not a failure, the exit code is.
$ErrorActionPreference = "Continue"
& .\gradlew.bat $Task --no-daemon -q 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -match "^e: |error:|FAILED|What went wrong" }
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
Pop-Location
if ($code -ne 0) { throw "Gradle failed ($code)" }

$kind = if ($Task -like "*Release*") { "release" } else { "debug" }
$apk = Get-ChildItem (Join-Path $work "app\build\outputs\apk\$kind") -Filter *.apk | Select-Object -First 1
$version = (Select-String -Path app\build.gradle.kts -Pattern 'versionName\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$out = Join-Path $PSScriptRoot "..\build\Kai-Android-$version.apk"
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
Copy-Item $apk.FullName $out -Force
Write-Output "APK: $((Resolve-Path $out).Path)"
