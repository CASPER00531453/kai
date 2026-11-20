# Casper.exe'yi bu bilgisayarda derle: dist\Casper.exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean Casper.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız" }
Write-Output "HAZIR: $PSScriptRoot\dist\Casper.exe"
