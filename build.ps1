# Build Kai and its installer: island UI -> dist\Kai\ (one folder) -> Kai-Setup-<version>.exe
# The version comes from version.py, the one place it is written down.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
}
$version = (& .\.venv\Scripts\python -c "from version import VERSION; print(VERSION)").Trim()
Write-Output "Kai $version"

Push-Location _coucou_ui
npm run build
Pop-Location

# A Kai running out of dist\ locks the exe and the build cannot replace it.
Get-Process Kai -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "$PSScriptRoot\dist\*" } | Stop-Process -Force
# As a module: pyinstaller.exe remembers the folder the venv was made in and
# stops working when the project moves.
.\.venv\Scripts\python -m PyInstaller --noconfirm Kai.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed; the installer was not built" }
Copy-Item kai_hook.py dist\Kai\kai_hook.py -Force

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found: winget install JRSoftware.InnoSetup" }
& $iscc /Q "/DMyAppVersion=$version" installer\Kai.iss

Write-Output "SETUP: $PSScriptRoot\build\Kai-Setup-$version.exe"
