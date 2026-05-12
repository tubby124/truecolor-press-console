# Codex handoff — finish the Windows-side setup for True Color Press Console

You are picking up a multi-session task on the shop's Windows PC. The previous session ran on Hasan's Mac and is documented in [TESTING-LOG.md](TESTING-LOG.md). Your job is to finish the Windows-side setup so the BM-660 booklet maker, stapler, and 3-hole punch on the Konica AccurioPress C3070 can be engaged automatically from the app at `localhost:5273`.

## Context you need before doing anything

- **Repo:** `https://github.com/tubby124/truecolor-press-console`
- **Branch / commit at handoff:** `main` @ `d6fe683` (v0.3.3 tag — STOP button + default qty 1 + louder error toasts + test-pattern fix). If the v0.3.3 Windows zip exists in [GitHub Releases](https://github.com/tubby124/truecolor-press-console/releases), that's the build to deploy. If only v0.3.2 is there, the v0.3.3 zip is still building (Chocolatey 504'd once and was re-triggered); check Actions tab.
- **Press:** KONICA AccurioPress C3070 at `172.16.1.149`. Touchscreen is dead from a brownout-era stored fault (C-6753). Engine + network are healthy. Hardware finishers (BM-660 saddle/fold, corner stapler, 3-hole punch) must be confirmed post-brownout-healthy by the Konica tech BEFORE you run a real finishing job. Hasan to confirm.
- **The four trays the shop has loaded:** T1, T2, T3 = 8.5×11 plain (`24lb-bond`). T4 = 12×18. T5 = larger stock. The app's tray registration is at `/api/trays`; update it via the `TrayStatusBar` in the topbar when reality changes.
- **What's already done:**
  - SumatraPDF is installed on this Windows PC.
  - Mac side has been validated end-to-end: PJL pipeline works, booklet imposition works (5-page test → 2 letter sheets fold to a 5.5×8.5 booklet, page order verified), STOP button works, error toasts are loud and persistent.
  - Stock catalog has a known mismatch for the color-blocks test pattern (asks for 100lb-gloss-text → TRAY4, but TRAY4 has 12×18). Don't run that test pattern on this shop until catalog is fixed or coated text is loaded in a letter tray. The booklet test on `24lb-bond` (TRAY1) is the one that works.

## What you must do, in order

### 1. Make sure v0.3.3 is installed on this Windows PC

- If TrueColorPress isn't installed at all: download `TrueColorPress-v0.3.3.zip` (or latest) from the GitHub Releases page, unzip somewhere reasonable (e.g. `C:\TrueColorPress\`), drop a `.env` next to `TrueColorPress.exe` containing:
  ```
  PRESS_SAFE_PRINT_MODE=live
  ```
  Double-click `TrueColorPress.exe`. Browser opens to `localhost:5273`. Log in: `qwerty123`. Verify version reads `0.3.3` in topbar.
- If v0.3.2 or earlier is already installed: open the app, the OTA banner should appear; click "Download & install". App restarts on v0.3.3. If banner doesn't appear within a few minutes, fetch the latest zip manually and unzip on top of the existing install dir.

### 2. Run the print-queue setup script

The PowerShell script lives at [setup-c3070-queues.ps1](setup-c3070-queues.ps1) in this repo. From an admin PowerShell prompt in the repo root (or wherever you've copied the script):

```powershell
pwsh -ExecutionPolicy Bypass -File docs\setup-c3070-queues.ps1
```

It will:
- Skip SumatraPDF (already installed)
- Add a raw-TCP port `C3070_9100` at `172.16.1.149:9100`
- Auto-detect the Konica driver and add four queues: `C3070 Plain`, `C3070 Booklet`, `C3070 Stapled`, `C3070 Punched`
- Print the per-queue Finishing-tab walkthrough at the end

If auto-detect can't find the Konica driver: install the C3070 Windows driver from Konica's support site first, then re-run.

### 3. Configure each queue's Finishing tab — manual, only Hasan can do this

You CANNOT script the Konica driver UI. Walk Hasan through it. For each of the four queues:

`Control Panel → Devices and Printers → right-click queue → Printer properties → Preferences… → Finishing tab` then set:

| Queue | What to set |
|---|---|
| **C3070 Plain** | Output Method: Print · Finisher: OFF · Output Tray: top |
| **C3070 Booklet** | Layout: Booklet · Binding: Saddle-stitch + Center-fold · Output: Booklet tray. (Cover-tab settings below for cover stock variant.) |
| **C3070 Stapled** | Staple: ON · Position: 1-corner upper-left · Output: finisher tray 1 |
| **C3070 Punched** | Punch: ON · 3-hole · Edge: left · Output: finisher tray 1 |

After setting each, click Apply then OK on both Preferences and Properties. Settings persist as the queue's defaults.

For the cover-stock variant of booklets: in `C3070 Booklet`'s Preferences → Cover tab → enable "Front cover" → source from the tray loaded with cover stock (e.g. `100lb-cover-uncoated` in TRAY5). Same for "Back cover" if needed.

### 4. Verify queues are visible to the app

In the app: open Settings → Printer Queues panel (or curl `GET /api/printer-queues` with the session cookie). Expect:
```
"supported": true,
"queues": { "booklet": "C3070 Booklet", "stapled": "C3070 Stapled", "punched": "C3070 Punched" }
```
If `supported: false` → you're not running on Windows OR the app process can't see the queues. Restart the app.

### 5. Run supervised first-prints — qty=1, ONE finisher at a time

Order matters. Do them in this order so when something misbehaves you know which finisher is the suspect. After each: append a dated entry to [TESTING-LOG.md](TESTING-LOG.md) under a new "## 2026-MM-DD (Windows shop PC, post v0.3.3 deploy)" header. Mark each row pass/fail with what you observed.

1. **Plain print** (sanity check, no finisher engagement). Drop any PDF, qty 1, sides 1, plain workflow. Expect output at the top tray, no finishing applied. Confirms the Windows app + Sumatra + raw-9100 path agrees with what the Mac was doing.
2. **Corner staple**. Drop a 3-page PDF, workflow `stapled_doc`, preset `stapled_plain_letter`, qty 1. Expect 3 sheets stapled in upper-left.
3. **3-hole punch**. Drop a 3-page PDF, workflow `punched`, preset `punched_plain_letter`, qty 1. Expect 3 sheets with 3 holes along the left edge.
4. **Saddle booklet (5.5×8.5 from letter)**. Use the same numbered 5-page test PDF that's at `tmp/booklet-test-5pg.pdf` on the Mac (or regenerate it via Pillow — see [TESTING-LOG.md](TESTING-LOG.md) for the script). Workflow `booklet_5.5x8.5_letter`, qty 1. Expect 2 letter sheets to come out **already folded and saddle-stitched** at the spine via the BM-660. Visually verify fold accuracy + staple position. Page order: cover=1, inside front=2, inside spread=3 4, last=5, rest blank.
5. **Hard stock cover booklet**. Load `100lb-cover-uncoated` (or whatever cover stock the shop has) into TRAY5, mark it in the app's TrayStatusBar. Configure `C3070 Booklet`'s Cover tab to pull front+back covers from TRAY5. Re-submit the same booklet job. Expect cover sheet to be cover stock, inner sheets text weight.
6. **(Optional, only if Hasan has a customer job for it) 8.5×11 booklet on 12×18 with bleed + trim.** Workflow `booklet_8.5x11_12x18`. Press folds, operator trims head/foot/face on the Graphic Wizard 4908. Verify final size = 8.5×11 and trim marks survived.

If a STOP is needed mid-test: the red STOP button in the topbar sends `JOB CANCEL` to the press + purges all four Windows queues via `Remove-PrintJob`. Use it freely; that's what it's for.

### 6. Update TESTING-LOG.md and push

After each supervised test, edit [TESTING-LOG.md](TESTING-LOG.md) to mark the row pass/fail with notes. After the session, commit + push:

```bash
git add docs/TESTING-LOG.md
git commit -m "test(v0.3.3): finisher supervised first-prints — <pass/fail summary>"
git push origin main
```

## What you must NOT do

- Don't change app code in this session. If you find a bug, log it in TESTING-LOG.md under "Known caveats" and tell Hasan; he'll prioritize a v0.3.4. The point of this session is operational validation, not feature work.
- Don't run quantity jobs (>1 piece) on a finisher before that finisher has passed a supervised single-piece test. Per CLAUDE.md hard rule #1.
- Don't reset `PRESS_SAFE_PRINT_MODE` to `dry` mid-session — Hasan has it on `live` intentionally.
- Don't trust any tray's contents you haven't physically verified today. The press's SNMP tray endpoint is currently returning empty (`trays: {}`); operators are the source of truth.

## If something goes wrong

- **App version doesn't read 0.3.3:** the OTA hadn't run. Check `~\.config\press-console\` for stale config, or just re-unzip the latest release manually.
- **Queue setup script fails on "no Konica driver":** install the C3070 driver first, then re-run with `-DriverName 'Exact Driver Name From Print Management'`.
- **Finisher physically jams or misbehaves:** STOP, do not retry. Call the Konica tech. The brownout-era voltage event may have damaged finisher components in ways that aren't visible without a service inspection.
- **Press goes silent / unreachable:** check the wired LAN at the shop — it was flaky earlier today (Mac had to switch to Wi-Fi). `ping 172.16.1.149`. If unreachable, fix the cable/switch before doing anything else.
- **Press complains via PageScope `http://172.16.1.149/` but the app's topbar shows nothing:** there's a known v0.3.3 gap — the app surfaces `code + display` but not the full firmware error tree. Log it; v0.3.4 will plug that. For now, PageScope is the fallback.

## End state when you're done

- All four queues exist on this Windows PC and pass their supervised single-piece test.
- TESTING-LOG.md has a dated Windows-session entry with pass/fail per finisher.
- The repo is on main with that commit pushed.
- Hasan can now do production runs of any of: plain print, stapled doc, 3-hole punched doc, saddle-stitched booklet (with or without hard cover), and 8.5×11-on-12×18 booklets with trim.

Ask Hasan to confirm the Konica tech has post-brownout-cleared each finisher before you fire its first supervised job. That's the only gate left.
