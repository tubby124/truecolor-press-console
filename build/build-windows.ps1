# Build True Color Press Console for Windows.
#
# Run from the repo root with the venv activated:
#   .\build\build-windows.ps1
#
# Steps:
#   1. Build the React frontend (npm run build)
#   2. Vendor the click-rate CSV from the sibling estimator repo
#   3. Copy the system Ghostscript install into build/gs-portable/
#   4. Run PyInstaller against build/truecolorpress.spec
#   5. Zip the dist folder for shipping
#
# Outputs:
#   dist/TrueColorPress/TrueColorPress.exe  (the thing staff double-click)
#   dist/TrueColorPress-vX.Y.Z.zip          (single-file shipping artifact)

[CmdletBinding()]
param(
    # Sibling repo path (where estimator's config.v1.csv lives). Override if
    # the repos aren't in the same parent dir on the build machine.
    [string]$EstimatorRepo = "..\truecolor-estimator",

    # Where Ghostscript is installed on this machine.
    [string]$GhostscriptDir = "C:\Program Files\gs",

    # Skip the frontend build if you've already run `npm run build` recently.
    [switch]$SkipFrontend,

    # Skip the Ghostscript copy if build\gs-portable already has it.
    [switch]$SkipGhostscript,

    # Don't zip the dist folder. Saves time during local iteration.
    [switch]$NoZip
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

Write-Host "==> Repo root: $RepoRoot" -ForegroundColor Cyan

# ───────────────────────── 1. Frontend build ─────────────────────────

if (-not $SkipFrontend) {
    Write-Host "==> Building frontend (npm run build)" -ForegroundColor Cyan
    Push-Location "frontend"
    if (-not (Test-Path "node_modules")) {
        npm install
    }
    npm run build
    Pop-Location

    if (-not (Test-Path "frontend\dist\index.html")) {
        throw "Frontend build did not produce frontend\dist\index.html"
    }
} else {
    Write-Host "==> Skipping frontend build (--SkipFrontend)" -ForegroundColor Yellow
}

# ───────────────────────── 2. Vendor click-rate CSV ─────────────────────────

$VendorDir = Join-Path $RepoRoot "build\vendored"
New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

$EstimatorCsv = Join-Path $EstimatorRepo "data\tables\config.v1.csv"
$VendoredCsv = Join-Path $VendorDir "config.v1.csv"
if (Test-Path $EstimatorCsv) {
    Write-Host "==> Vendoring click-rate CSV from $EstimatorCsv (sibling estimator repo)" -ForegroundColor Cyan
    Copy-Item -Force $EstimatorCsv $VendoredCsv
} elseif (Test-Path $VendoredCsv) {
    Write-Host "==> Sibling estimator repo not found; using committed vendored CSV at $VendoredCsv" -ForegroundColor Yellow
} else {
    Write-Warning "Estimator CSV not found at $EstimatorCsv and no committed fallback — bundle will use hardcoded click rates."
}

# ───────────────────────── 3. Stage Ghostscript ─────────────────────────

$GsPortable = Join-Path $RepoRoot "build\gs-portable"

if (-not $SkipGhostscript) {
    if (-not (Test-Path $GhostscriptDir)) {
        throw "Ghostscript not found at $GhostscriptDir. Install it from https://ghostscript.com/releases/gsdnld.html or pass -GhostscriptDir <path>."
    }

    # Pick the newest gs10.* (or gs9.*) subdir.
    $GsInstall = Get-ChildItem -Path $GhostscriptDir -Directory -Filter "gs*" |
                 Sort-Object Name -Descending |
                 Select-Object -First 1
    if (-not $GsInstall) {
        throw "No gs* subdirectory found inside $GhostscriptDir"
    }

    Write-Host "==> Staging Ghostscript from $($GsInstall.FullName)" -ForegroundColor Cyan
    if (Test-Path $GsPortable) {
        Remove-Item -Recurse -Force $GsPortable
    }
    New-Item -ItemType Directory -Force -Path $GsPortable | Out-Null
    Copy-Item -Recurse -Force "$($GsInstall.FullName)\bin" (Join-Path $GsPortable "bin")
    Copy-Item -Recurse -Force "$($GsInstall.FullName)\lib" (Join-Path $GsPortable "lib")
    if (Test-Path "$($GsInstall.FullName)\Resource") {
        Copy-Item -Recurse -Force "$($GsInstall.FullName)\Resource" (Join-Path $GsPortable "Resource")
    }
} else {
    Write-Host "==> Skipping Ghostscript copy (--SkipGhostscript)" -ForegroundColor Yellow
    if (-not (Test-Path (Join-Path $GsPortable "bin"))) {
        throw "build\gs-portable\bin missing — cannot --SkipGhostscript on a clean build."
    }
}

# ───────────────────────── 4. PyInstaller ─────────────────────────

Write-Host "==> Running PyInstaller" -ForegroundColor Cyan

# Clear stale build artifacts so we don't pick up old datas/binaries.
if (Test-Path "build\__pycache__") { Remove-Item -Recurse -Force "build\__pycache__" }
if (Test-Path "build\TrueColorPress") { Remove-Item -Recurse -Force "build\TrueColorPress" }
if (Test-Path "dist\TrueColorPress") { Remove-Item -Recurse -Force "dist\TrueColorPress" }

pyinstaller --noconfirm --clean (Join-Path $RepoRoot "build\truecolorpress.spec")

if (-not (Test-Path "dist\TrueColorPress\TrueColorPress.exe")) {
    throw "PyInstaller did not produce dist\TrueColorPress\TrueColorPress.exe"
}

Write-Host "==> Build OK: dist\TrueColorPress\TrueColorPress.exe" -ForegroundColor Green

# ───────────────────────── 5. Zip ─────────────────────────

if (-not $NoZip) {
    $Version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
    if (-not $Version) { $Version = "dev" }
    $ZipPath = Join-Path $RepoRoot "dist\TrueColorPress-v$Version.zip"
    if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
    Write-Host "==> Zipping to $ZipPath" -ForegroundColor Cyan
    Compress-Archive -Path "dist\TrueColorPress" -DestinationPath $ZipPath
    Write-Host "==> Ready: $ZipPath" -ForegroundColor Green
}
