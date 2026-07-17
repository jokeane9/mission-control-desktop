# Build the distributable Windows app: PyInstaller dir build + Inno Setup
# installer (if iscc is on PATH) + a plain zip fallback.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#
# Code signing is applied afterwards in CI (see .github/workflows/release.yml);
# see DISTRIBUTION.md for the SmartScreen story.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Version = if ($env:APP_VERSION) { $env:APP_VERSION } else { "1.0.0" }
$Version = $Version -replace '^v', ''                    # v1.0.0 -> 1.0.0

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }

pyinstaller --noconfirm packaging/orrery.spec
if (-not (Test-Path "dist/Orrery")) { throw "build failed" }

# WebView2 Evergreen bootstrapper (tiny stub; installer runs it if the runtime
# is missing — Win11 and current Win10 ship WebView2, older Win10 may not)
$bootstrap = "packaging/windows/MicrosoftEdgeWebview2Setup.exe"
if (-not (Test-Path $bootstrap)) {
    Invoke-WebRequest "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $bootstrap
}

# zip fallback (portable)
Compress-Archive -Path "dist/Orrery" -DestinationPath "dist/Orrery-$Version-win64.zip" -Force

# Inno Setup installer
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if ($iscc) {
    & $iscc /DAppVersion=$Version packaging/windows/installer.iss
    Write-Host "installer: dist/Orrery-$Version-setup.exe"
} else {
    Write-Host "iscc not found - skipped installer, zip only"
}
