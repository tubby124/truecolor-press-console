# Auto-Fold Setup — One-Page Checklist

Goal: brochures come out of the C3070 **already folded**, not flat. One-time setup on the shop Windows PC. ~45 minutes.

After this is done, the console's Tri-fold / Bi-fold / Half-fold tiles will route through Windows queues that have the FD-503 fold unit configured. Click tile → press folds → done.

---

## What you need before starting

- [ ] Shop Windows PC, admin login.
- [ ] C3070 Windows print driver installed (download from Konica's support site if not — look for "AccurioPress C3070 PCL/PS Driver"). The script auto-detects it.
- [ ] Konica tech has verified the FD-503 fold unit is healthy post-brownout. **If the tech only cleared C-6753 + ran flat prints, the fold unit is not yet verified.** Call before continuing.
- [ ] The press is reachable from the Windows PC at `172.16.1.149` (ping it from `cmd` to confirm).

---

## Step 1 — Run the queue-install script

1. Copy [setup-c3070-queues.ps1](setup-c3070-queues.ps1) to the Windows PC desktop.
2. Right-click → **Run with PowerShell** (or in admin PowerShell: `pwsh -ExecutionPolicy Bypass -File setup-c3070-queues.ps1`).
3. Script installs SumatraPDF, adds a TCP port to the press, and creates 6 print queues.

Expected output: `[OK]` lines for SumatraPDF, port, driver, and 6 queues.

---

## Step 2 — Configure each queue's Finishing tab (10 min each — manual, but one-time)

Control Panel → **Devices and Printers** → right-click each queue → **Printer properties** → **Preferences** → **Finishing** (or **Layout**) tab → set:

| Queue            | What to set                                                                |
|------------------|----------------------------------------------------------------------------|
| C3070 Plain      | Finisher: OFF · Output tray: top                                           |
| C3070 Booklet    | Layout: Booklet · Binding: Saddle-stitch + Center-fold · Output: Booklet tray |
| C3070 Stapled    | Staple: ON, 1-corner (upper-left) · Output: Finisher tray 1                |
| C3070 Punched    | Punch: ON, 3-hole, left edge · Output: Finisher tray 1                     |
| **C3070 Trifold**  | **Fold: ON · Mode: Letter Tri-fold** (Z-fold or C-fold — pick one and stick with it) · Output: Folder catch tray |
| **C3070 Halffold** | **Fold: ON · Mode: Half-fold · Staple: OFF** · Output: Folder catch tray   |

Click **Apply** + **OK** twice for each. Settings persist as queue defaults.

---

## Step 3 — Test one fold, quantity 1, supervised

Open TrueColorPress on the Windows PC (or point Mac console at Windows queue — see [CODEX-WINDOWS-HANDOFF.md](CODEX-WINDOWS-HANDOFF.md)).

1. Log in (qwerty123).
2. Settings → Printer Queues → confirm `trifold` row maps to `C3070 Trifold` and `halffold` row maps to `C3070 Halffold`.
3. Click **Tri-fold Brochure** tile.
4. Upload any 2-sided letter-size PDF (or use any business-card artwork stretched to letter — the imposition lays out the fold panels for you).
5. Quantity: **1**.
6. Click Print. Watch the folder catch tray.

**Expected**: sheet exits the press, enters the FD-503, comes out folded in thirds (or Z/C-folded depending on your driver setting).

**If it comes out flat**: queue's Finishing tab didn't take. Re-open Preferences, confirm Fold is checked, Apply twice. The Konica driver loses settings if you skip the second Apply.

**If the press faults**: hit STOP in the topbar. The fold unit may need the tech back. Do NOT retry without surfacing the fault code first.

---

## Step 4 — Repeat once for half-fold

Same as Step 3 but click **Half-fold Card** tile. Expected: sheet exits folded in half (one crease, no staple).

---

## Done. Now what?

- Brochure jobs from the Mac console will route through the Windows PC's queues if you wire the console's `printer-queues.json` to point at it. See [CODEX-WINDOWS-HANDOFF.md](CODEX-WINDOWS-HANDOFF.md) for the Mac→Windows queue-name wiring (it's just JSON, no code).
- Add a new dated block to [TESTING-LOG.md](TESTING-LOG.md) after each fold type is verified so the next operator knows what's actually tested.

## Stop conditions

Don't continue past Step 2 if:
- The Konica driver doesn't expose a Fold checkbox under Finishing → either the wrong driver is installed (download PCL+PS combo, not "host-based" / GDI) or the FD-503 fold unit isn't registered with the driver. In Devices and Printers → Printer properties → Configure tab → "Get Status from Device" → confirm "Fold unit FD-503" appears in the installed-options list.
- The first supervised tri-fold print jams or comes out crooked → call the tech. Fold rollers can drift after a brownout even if the engine looks fine.
