# True Color Press Console — Windows print-queue setup
#
# What this does, in order:
#   1. Installs SumatraPDF (silent, via winget) if it isn't already there.
#   2. Adds a raw-TCP printer port at 172.16.1.149:9100 named "C3070_9100".
#   3. Adds six Windows printer queues that all share that port, each with
#      a distinct name the app expects:
#         C3070 Plain        — no finishing (plain pass-through)
#         C3070 Booklet      — saddle-stitch + center-fold (BM-660)
#         C3070 Stapled      — corner staple
#         C3070 Punched      — 3-hole punch
#         C3070 Trifold      — letter tri-fold (FD-503)
#         C3070 Halffold     — half-fold only, no stitch (FD-503)
#   4. Tells you the ONE manual step left: open each queue's "Printing
#      preferences" → Finishing tab and set the finisher option per queue.
#
# Why this exists:
#   Konica's finisher controls (staple, fold, punch) aren't standard PJL
#   keywords — only the Windows driver knows how to engage them. The press
#   console picks the right queue per workflow and the driver attached to
#   that queue handles the finishing. See backend/win_spooler.py for the
#   wiring.
#
# How to run:
#   Right-click → Run with PowerShell  (or `pwsh -ExecutionPolicy Bypass -File setup-c3070-queues.ps1`)
#   Needs admin (Add-Printer touches the spooler).

#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$PrinterIP = "172.16.1.149",
    [int]$PrinterPort = 9100,
    [string]$DriverName = ""   # leave blank to auto-detect a Konica driver
)

$ErrorActionPreference = "Stop"

function Write-Step($n, $msg) {
    Write-Host ""
    Write-Host "─── Step $n ─── $msg" -ForegroundColor Cyan
}

function Write-OK($msg)   { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Skip($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor DarkGray }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [ERR]  $msg" -ForegroundColor Red }

# ─── Step 1: SumatraPDF ─────────────────────────────────────────────────────
Write-Step 1 "Install SumatraPDF (used by the app to spool PDFs)"
$sumatraPath = "C:\Program Files\SumatraPDF\SumatraPDF.exe"
if (Test-Path $sumatraPath) {
    Write-OK "SumatraPDF already installed at $sumatraPath"
} else {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "  Running: winget install SumatraPDF.SumatraPDF --silent --accept-source-agreements --accept-package-agreements"
        try {
            winget install SumatraPDF.SumatraPDF --silent --accept-source-agreements --accept-package-agreements | Out-Null
            if (Test-Path $sumatraPath) {
                Write-OK "SumatraPDF installed."
            } else {
                Write-Warn "winget finished but SumatraPDF.exe not at expected path. Install manually from https://www.sumatrapdfreader.org/"
            }
        } catch {
            Write-Warn "winget install failed: $_. Install manually from https://www.sumatrapdfreader.org/"
        }
    } else {
        Write-Warn "winget not available. Download SumatraPDF from https://www.sumatrapdfreader.org/ and install (default path)."
    }
}

# ─── Step 2: TCP port ───────────────────────────────────────────────────────
Write-Step 2 "Add raw-TCP printer port for the C3070"
$portName = "C3070_9100"
$existingPort = Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue
if ($existingPort) {
    Write-Skip "Port '$portName' already exists ($($existingPort.PrinterHostAddress):$($existingPort.PortNumber))"
} else {
    Add-PrinterPort -Name $portName -PrinterHostAddress $PrinterIP -PortNumber $PrinterPort
    Write-OK "Added port $portName → ${PrinterIP}:${PrinterPort}"
}

# ─── Step 3: Detect Konica driver ───────────────────────────────────────────
Write-Step 3 "Find the C3070 print driver"
if ([string]::IsNullOrWhiteSpace($DriverName)) {
    $candidates = Get-PrinterDriver | Where-Object {
        $_.Name -match "KONICA" -or $_.Name -match "AccurioPress" -or $_.Name -match "C3070"
    }
    if ($candidates.Count -eq 0) {
        Write-Err "No KONICA / AccurioPress / C3070 driver found on this machine."
        Write-Err "Install the C3070 Windows driver first (download from Konica's support site),"
        Write-Err "then re-run this script. Use -DriverName 'EXACT NAME' to override auto-detect."
        exit 1
    }
    $DriverName = $candidates[0].Name
    Write-OK "Auto-detected driver: $DriverName"
    if ($candidates.Count -gt 1) {
        Write-Host "  (Other matching drivers also installed, using the first:)"
        $candidates | Select-Object -Skip 1 | ForEach-Object { Write-Host "    - $($_.Name)" }
        Write-Host "  Override with: setup-c3070-queues.ps1 -DriverName 'Exact Driver Name'"
    }
} else {
    Write-OK "Using driver: $DriverName"
}

# ─── Step 4: Add six queues ─────────────────────────────────────────────────
Write-Step 4 "Add the six named queues (each will share the C3070_9100 port)"
$queues = @("C3070 Plain", "C3070 Booklet", "C3070 Stapled", "C3070 Punched", "C3070 Trifold", "C3070 Halffold")
foreach ($q in $queues) {
    $existing = Get-Printer -Name $q -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Skip "$q already exists (port: $($existing.PortName), driver: $($existing.DriverName))"
        continue
    }
    try {
        Add-Printer -Name $q -DriverName $DriverName -PortName $portName
        Write-OK "Added queue: $q"
    } catch {
        Write-Err "Failed to add $q : $_"
    }
}

# ─── Step 5: Manual finishing-tab walkthrough ───────────────────────────────
Write-Step 5 "Configure finishing per queue (one-time manual step)"
Write-Host ""
Write-Host "  The Konica driver UI is the only way to bake finishing settings into each" -ForegroundColor White
Write-Host "  queue's default Printing Preferences. PowerShell can't reach those fields." -ForegroundColor White
Write-Host ""
Write-Host "  For EACH of the six queues:" -ForegroundColor White
Write-Host "    Control Panel → Devices and Printers → right-click the queue → Printer properties" -ForegroundColor White
Write-Host "    → click 'Preferences…' → switch to the 'Finishing' (or 'Layout') tab → set:" -ForegroundColor White
Write-Host ""
Write-Host "      C3070 Plain    → Output Method: Print  ·  Finisher: OFF  ·  Output Tray: top" -ForegroundColor Green
Write-Host "      C3070 Booklet  → Layout: Booklet  ·  Binding: Saddle-stitch + Center-fold  ·  Output: Booklet tray" -ForegroundColor Green
Write-Host "      C3070 Stapled  → Staple: ON, 1-corner (upper-left)  ·  Output Tray: finisher tray 1" -ForegroundColor Green
Write-Host "      C3070 Punched  → Punch: ON, 3-hole, left edge  ·  Output Tray: finisher tray 1" -ForegroundColor Green
Write-Host "      C3070 Trifold  → Fold: ON, Mode = Letter Tri-fold (Z or C — pick whichever your shop uses)  ·  Output Tray: folder catch" -ForegroundColor Green
Write-Host "                       Sheet size: Letter only. Tri-fold won't engage on 11×17 or 12×18 — driver will reject silently." -ForegroundColor DarkGray
Write-Host "      C3070 Halffold → Fold: ON, Mode = Half-fold  ·  Staple: OFF  ·  Output Tray: folder catch" -ForegroundColor Green
Write-Host "                       Use this for any 1-fold brochure where you DON'T want a staple (bifold + greeting cards)." -ForegroundColor DarkGray
Write-Host ""
Write-Host "    After setting, click Apply, then OK on both dialogs (Preferences + Properties)." -ForegroundColor White
Write-Host "    The settings persist as the queue's defaults so every job hitting that queue" -ForegroundColor White
Write-Host "    picks up the finishing automatically." -ForegroundColor White
Write-Host ""

# ─── Step 6: Verify ─────────────────────────────────────────────────────────
Write-Step 6 "Verify"
$installed = Get-Printer | Where-Object { $_.Name -like "C3070 *" } | Select-Object Name, PortName, DriverName
$installed | Format-Table -AutoSize
Write-Host ""
Write-OK "Setup complete. Open TrueColorPress, log in (qwerty123), and the queues will appear in Settings → Printer Queues."
Write-Host ""
Write-Host "Test a 1-piece print of each finishing type before running quantity. STOP button in the" -ForegroundColor Yellow
Write-Host "topbar will purge all four queues + send JOB CANCEL to the press if anything misbehaves." -ForegroundColor Yellow
