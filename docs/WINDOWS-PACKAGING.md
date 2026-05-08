# Windows Packaging Runbook

Goal: ship the True Color Press Console as a single double-clickable Windows .exe that staff run on the shop's Windows PC. Browser auto-opens to the UI on launch. No Python install, no command line.

## Architecture decision: PyInstaller `onedir`, not `onefile`

We ship a folder containing `TrueColorPress.exe` + supporting DLLs. Staff double-click the .exe inside the folder.

**Why not `--onefile`?** Onefile re-extracts the entire ~200 MB bundle to `%TEMP%\_MEI*` on every launch. First boot is 10-15s on a shop PC. Onedir launches in ~2s and keeps Ghostscript / frontend / ICC profile inspectable on disk. The "double-click an exe" UX is identical.

The whole folder zips cleanly (`TrueColorPress-vX.Y.Z.zip`). Updates = unzip on top.

## What gets bundled

| Component | Source | Bundled to |
|---|---|---|
| Backend Python code | `backend/` | exe via PyInstaller hook |
| Frontend static assets | `frontend/dist/` | `_internal/frontend_dist/` |
| ICC profile | `icc/` | `_internal/icc/` |
| Test pattern PDFs | `assets/test-patterns/` | `_internal/assets/test-patterns/` |
| Click-rate CSV | `truecolor-estimator/data/tables/config.v1.csv` | `_internal/data/config.v1.csv` (vendored — see Click-rate vendoring below) |
| Ghostscript Windows binary | downloaded separately, see below | `_internal/gs/` |
| Stocks JSON overlay | `~/.config/press-console/stocks.json` (live, not bundled) | created on first run |
| Scanner inbox | `~/Documents/PressConsole/scans/` (live, not bundled) | created on first run, configurable via `PRESS_SCANNER_INBOX` env var |
| Job history | `tmp/jobs/` (live) | created on first run, alongside the exe |

## One-time setup on the build machine

You need a Windows machine (or Windows VM, or `wine` on the Mac for limited builds — but native Windows is more reliable). PyInstaller cannot cross-compile.

1. Install **Python 3.12** from python.org (check "Add to PATH").
2. Install **Node.js 20+** for the frontend build.
3. Install **Ghostscript for Windows** from `https://ghostscript.com/releases/gsdnld.html` — pick the 64-bit installer. Default install path is `C:\Program Files\gs\gs10.xx.x\`. We'll copy this into the bundle, not require it system-wide.
4. Clone or copy the repo to the build machine.
5. From the repo root:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e .[dev]
   pip install pyinstaller>=6.10
   cd frontend
   npm install
   cd ..
   ```

## Build steps (one command)

From repo root, on Windows:
```powershell
.\build\build-windows.ps1
```

This script:
1. Builds the frontend (`npm run build` in `frontend/`).
2. Vendors the click-rate CSV from sibling repo into `build/vendored/`.
3. Copies Ghostscript from `C:\Program Files\gs\` into `build/gs-portable/`.
4. Runs `pyinstaller build/truecolorpress.spec`.
5. Zips `dist/TrueColorPress/` to `dist/TrueColorPress-v0.X.Y.zip`.

Output: `dist/TrueColorPress/TrueColorPress.exe` (the thing staff double-click).

## What happens at runtime

1. Staff double-click `TrueColorPress.exe`.
2. `build/launch.py` (the PyInstaller entry point) runs:
   - Prepends `_internal/gs/bin/` to `PATH` so `shutil.which("gs")` resolves to the bundled binary.
   - Aliases `gswin64c.exe` → `gs.exe` if needed (see Ghostscript binary name shim below).
   - Starts uvicorn in a daemon thread on `127.0.0.1:5273` (localhost-only by default).
   - Waits for the health endpoint to respond (max 10s).
   - Calls `webbrowser.open("http://localhost:5273")`.
   - Blocks on the uvicorn thread (so closing the console window kills the server).
3. Default browser opens, login page appears, staff types `qwerty123`.

## Ghostscript binary name shim

On Mac the binary is `gs`. On Windows the official binaries are `gswin64c.exe` (console) and `gswin64.exe` (windowed). The two `shutil.which("gs")` call sites — [backend/normalize.py:151](../backend/normalize.py#L151) and [backend/thumbs.py:25](../backend/thumbs.py#L25) — won't find them by default.

**Fix at packaging time, not at code level:** [build/runtime_hook.py](../build/runtime_hook.py) creates a copy named `gs.exe` next to `gswin64c.exe` inside the bundle, so both names resolve. This keeps `backend/` Mac-and-Windows-clean with no platform branches.

If the other chat introduces a shared `bin_paths.py` helper, drop the runtime hook's name-aliasing — the helper handles it.

## Click-rate vendoring

`backend/settings.py` defaults `estimator_config_csv` to `../truecolor-estimator/data/tables/config.v1.csv`. That sibling repo path doesn't exist on the shop PC.

**Build script vendors it in:** copies the CSV to `build/vendored/config.v1.csv`, and the spec ships it inside the bundle at `_internal/data/config.v1.csv`. The runtime hook sets the `PRESS_ESTIMATOR_CONFIG_CSV` env var to that path before settings.py loads, so `click_rates()` finds it.

**Annual refresh:** every November (per Meridian OneCap lease escalator), update the sibling estimator CSV, then rebuild + reship the Windows package.

## Bind host (single-machine default)

The bundled launcher binds to `127.0.0.1:5273` — only the machine running the exe can reach the UI. This matches CLAUDE.md rule 4 (single-user, single-machine).

**LAN override (rare):** if you ever want another computer on the shop network to reach the UI, drop a `.env` next to the exe containing `PRESS_BIND_HOST=0.0.0.0` and restart. The qwerty123 password gate still applies.

**Windows Firewall:** localhost binds don't trigger the firewall prompt. The prompt only appears if you flip to `0.0.0.0`. Allow on private networks if you ever do that, deny on public.

## Updating

1. Land changes on `main` of the press-console repo.
2. Pull on the build machine.
3. Re-run `.\build\build-windows.ps1`.
4. Stop the running exe on the shop PC (close the console window).
5. Replace the `TrueColorPress` folder on the shop PC with the new dist folder (or unzip on top).
6. Double-click `TrueColorPress.exe` to start.

Job history (`tmp/jobs/`) and the stocks overlay (`~/.config/press-console/stocks.json`) survive updates — they live outside the bundle.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Windows protected your PC" SmartScreen prompt | Click "More info" → "Run anyway". Resolved permanently by code-signing the exe (deferred — costs ~$300/yr for an EV cert, not worth it for one shop). |
| Browser doesn't auto-open | Manually visit `http://localhost:5273`. Check the console window for uvicorn errors. |
| `Ghostscript not found` errors | Confirm `_internal/gs/bin/gs.exe` exists in the bundle. If missing, the build machine didn't have Ghostscript installed when the build ran. |
| Port 5273 already in use | Another instance is already running. Close the existing console window. Or set `PRESS_BIND_PORT=5274` in a `.env` next to the exe. |
| Click rates wrong | Confirm `_internal/data/config.v1.csv` exists and matches the latest sibling-repo CSV. Re-vendor + rebuild. |

## Hardware gates still apply

Packaging doesn't change the print-safety story. `SAFE_PRINT_MODE=dry` ships as the default. After the tech clears C-6753 and the imaging chain is verified, set `PRESS_SAFE_PRINT_MODE=live` in a `.env` next to the exe and restart. Don't bake `live` into the build itself — it's a runtime decision per shop, not a release decision.

See [HARDWARE-GATES.md](HARDWARE-GATES.md) for the full pre-print checklist.
