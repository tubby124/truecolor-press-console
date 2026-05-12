# Session Handoff — 2026-05-11 (late night → next day brochure debug)

You are resuming the C3070 press-console build. Mac side is done. Windows side (TC1) is operationally usable. Saddle/fold for **letter** is permanently hardware-blocked. The job for next session: **prove the booklet + fold path for 12×18 and 11×17 input** so brochures and customer booklets work without manual finish.

## What's running RIGHT NOW

- **Windows shop PC (TC1)** has TrueColorPress v0.3.5 (just pushed). Reachable from any LAN/Tailnet browser at `http://tc1:5273`. Login `qwerty123`.
- **6 print queues** configured on TC1: `C3070 Plain / Booklet / Stapled / Punched / Trifold / Halffold`. Each has PrintTicket defaults baked in via `docs/apply-konica-finishing.ps1`. `Config:KOOpSaddleUnit = SD-510` declared on all.
- **Mac dev box** also running v0.3.5 at `http://localhost:5273` — useful for code iteration, but can't engage finishers (Windows-spooler-only).

## What's confirmed working (the boys can use these tonight)

- ✅ Business cards / postcards / flyers / posters → plain print, top tray
- ✅ Stapled documents → 1 corner staple upper-left, stapler tray
- ✅ Hole-punched documents → 3 holes left edge, stapler tray
- ✅ Combo stapled+punched in one job → both engage

## What's broken on letter (hardware constraint)

- ❌ Saddle booklet on letter (`booklet_5.5x8.5_letter`)
- ❌ Half-fold card on letter
- ❌ Tri-fold brochure on letter

These all hit the **same hardware limit**: BM-660/SD-510 fold mechanism on this press won't fold sheets smaller than 11×17. Tested every reasonable combination (Layout=Booklet vs not, FoldStitch on/off, OutputBin overrides, SD-510 declared) — driver either demands 11×17 or prints flat. Probably a Konica firmware-enforced minimum sheet size for the saddle/fold unit.

UI now shows these tiles as **"Manual finish"** — operator prints flat + folds/stitches by hand at the Graphic Wizard.

## What's untested = your job for next session

### Priority 1: Booklet `booklet_8.5x11_12x18` (high-confidence win)

This is the **real production booklet path** Hasan has used historically. 12×18 is in Tray 4 already.

**To test:**
1. Source a PDF with **proper bleed** (the current `tmp/booklet-test-5pg.pdf` doesn't have bleed — preflight will warn `no-trimbox`). Add 0.125" bleed in InDesign/Illustrator, save as PDF.
2. From TC1: drop the bleed PDF in the app at `http://tc1:5273`, click the `8.5×11 Booklet (12×18)` tile, qty 1, submit. OR via API:
   ```bash
   ssh -i ~/.ssh/id_ed25519_tc1 TrueC@tc1
   # Then on TC1:
   "C:\Users\TrueC\AppData\Local\SumatraPDF\SumatraPDF.exe" -print-to "C3070 Booklet" -silent -exit-when-done <bleed-pdf>
   ```
3. **Expected:** 2 sheets of 12×18 from T4 → folded in half + saddle-stitched at spine → drops at saddle tray. Trim 3 edges at Graphic Wizard for clean 8.5×11 finished booklet.
4. **If flat:** SD-510 saddle hardware isn't engaging even on 12×18 → Konica tech consult required.

### Priority 2: Bi-fold brochure on 11×17

Hasan's bi-fold brochure tile (`bifold_1up_11x17`) wants 11×17 input.

**To test:**
1. **Load 11×17 paper in a tray** (T4 currently has 12×18 — either swap or load T5 with 11×17). Update tray state in app (`/api/trays` PUT).
2. Drop a 4-page letter-content PDF (or generate one), click the bi-fold tile.
3. **Expected:** 1 sheet of 11×17, duplex, folded once down the middle into an 8.5×11 4-page brochure.
4. **If flat:** same fold-hardware investigation needed.

### Priority 3: If both fold tests fail → Konica tech consult

The question for the tech (be precise):
- Is the **SD-510 saddle stitcher** physically installed on this C3070?
- Is the **FD-503 multi-folder unit** installed?
- If SD-510 is installed: what's the minimum sheet size it can fold?
- If FD-503 is installed: same question + can it tri-fold letter?
- Current behavior: `Config:KOOpSaddleUnit=SD-510` accepted, `Config:KOOpSaddleStitcher` rejects all values (only takes "Plugin"). What's the correct enum for "saddle stitcher fully installed and enabled"?

## How to drive TC1 from a fresh session

```bash
# SSH (auth is by key, no password)
ssh -i ~/.ssh/id_ed25519_tc1 TrueC@tc1

# App status (run on TC1 or via SSH)
curl http://localhost:5273/api/health
# expect: {"ok":true,"safe_print_mode":"live","version":"0.3.5"}

# Press status (raw PJL, doesn't need app login)
# Direct over TCP — see existing scripts for PowerShell equivalent

# To re-apply finishing defaults (idempotent):
pwsh -ExecutionPolicy Bypass -File C:\Users\TrueC\Desktop\TrueColorSetup\apply-konica-finishing.ps1

# STOP everything (kill switch):
curl -X POST http://localhost:5273/api/stop -b <cookie-jar>
# Or click the red STOP button in the app's topbar at http://tc1:5273
```

## Files that matter for this work

- `backend/win_spooler.py` — workflow → queue routing logic (Chat B added trifold/halffold here)
- `backend/impose.py` — imposition. Note `stapled_plain_letter` and `punched_plain_letter` collapse multi-page input to 1 sheet (real bug — Chat B may have addressed in v0.3.4)
- `frontend/src/workflows/tiles.ts` — tile catalog with status pills (added in v0.3.5)
- `docs/apply-konica-finishing.ps1` — PrintTicket finishing defaults + SD-510 declaration
- `docs/test-folds.ps1` — creates Trifold/Halffold queues + tests
- `docs/TESTING-LOG.md` — full chronological test log
- `~/Downloads/Obsidian Vault/Projects/true-color/2026-05-11-c3070-finisher-validation.md` — Hasan-facing summary

## What NOT to repeat

- Don't waste time on letter saddle/fold — hardware blocks it.
- Don't try changing `Config:KOOpSaddleStitcher` (rejects all values).
- Don't try Layout=Booklet when sending a pre-imposed PDF — driver double-imposes, demands 11×17.
- Don't trust Mac-side audit logs to attribute Windows-side jobs — they're separate uvicorn instances.
- Don't add per-job finisher options (left/right staple, 2/3/4 hole) without first deciding the architectural approach: more queues, or per-job PrintTicket overrides.

## Open question for Hasan

If brochures don't auto-fold even on 12×18 / 11×17 → is manual fold at the Graphic Wizard acceptable production-wise, or do we need to insist on the tech consult to get the BM-660/SD-510/FD-503 properly enabled?
