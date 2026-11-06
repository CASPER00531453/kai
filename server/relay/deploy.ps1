# Puts Kai's link relay on your own Cloudflare account (free plan) and tells Kai about it.
#   powershell -File server\relay\deploy.ps1
# The first time, Cloudflare's sign-in page opens in the browser: sign in there yourself.
# Prints the relay's address and its access key; Kai keeps them (sealed) and uses them
# when "Cloudflare" is picked in Kai window › Phone.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path node_modules)) { npm install --no-audit --no-fund | Out-Null }

$ErrorActionPreference = "Continue"
$who = npx wrangler whoami 2>&1 | Out-String
if ($who -match "not authenticated|You are not logged in") {
    Write-Output "Cloudflare'e giriş sayfası açılıyor; girişi tarayıcıda sen yap."
    npx wrangler login
}
$out = npx wrangler deploy 2>&1 | Out-String
$ErrorActionPreference = "Stop"
$match = [regex]::Match($out, "https://[a-z0-9.-]+\.workers\.dev")
if (-not $match.Success) { Write-Output $out; throw "The relay's address was not found in wrangler's output." }
$url = $match.Value -replace "^https://", "wss://"

# The access key gates the use of the relay (your quota), not the content: 32 random bytes.
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$access = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
$access | npx wrangler secret put ACCESS_KEY | Out-Null

$python = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
if (Test-Path $python) {
    & $python -c "import sys; sys.path.insert(0, r'$PSScriptRoot\..\..'); import relay_link; relay_link.save_relay('$url', '$access')"
    Write-Output "Kai'ye kaydedildi: $url"
} else {
    Write-Output "Kai window > Phone > Cloudflare: paste these two."
    Write-Output "Address:    $url"
    Write-Output "Access key: $access"
}
