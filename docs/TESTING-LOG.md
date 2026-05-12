# C3070 Finishing Testing Log

---

## 2026-05-11 (Windows TC1 — late-night supervised tests)

### Setup applied via SSH (no GUI clicks)
- TrueColorPress v0.3.3 → v0.3.5 deployed to `C:\TrueColorPress\`
- 6 print queues: Plain, Booklet, Stapled, Punched, Trifold, Halffold (all on `172.16.1.149_1:9100`)
- PrintTicket defaults set via `docs/apply-konica-finishing.ps1` (PrintTicket XML mutation)
- `Config:KOOpSaddleUnit = SD-510` declared on all queues (changes some driver behavior — see results)

### Confirmed working ✅
- **Plain print** — every tile that doesn't need a finisher (BC, postcards, flyers, posters)
- **Corner stapler** — multi-sheet jobs come out with 1 upper-left corner staple at stapler main tray. Confirmed with 3+5 sheet jobs.
- **3-hole punch** — multi-sheet jobs come out with 3 holes left edge at stapler main tray.
- **Stapler + punch combo** — both engage on the same multi-sheet job.

### Hardware-blocked ❌
- **Saddle booklet on letter** (BM-660/SD-510 won't fold sheets below 11×17 on this press). Tested multiple combos: Layout+Fold+Stitch, Fold-only, with/without SD-510 declared. Press either demands 11×17 (refuses to print letter) or prints flat (fold mechanism doesn't engage).
- **Half-fold on letter** — same hardware constraint. Flat output.
- **Tri-fold on letter** — cancelled before test, same hardware constraint expected.

### Untested (likely working with right paper) ⏳
- **Booklet 8.5×11 from 12×18** — preset `booklet_8.5x11_12x18`. Hardware supports 12×18 saddle. Need test PDF with proper bleed.
- **Booklet 8.5×11 from 11×17** — preset `booklet_8.5x11_11x17`. No 11×17 currently loaded; need to load.
- **Bi-fold brochure on 11×17** — same as above, needs 11×17 input.

### Key technical findings
1. **SumatraPDF does honor queue PrintTicket defaults** (confirmed by working stapler test). Earlier loose-output result was a Mac job sneaking in. **Production path uses SumatraPDF → C3070 queue with finishing baked in.**
2. **`Config:KOOpSaddleUnit = SD-510`** changes driver behavior for saddle (no longer demands 11×17 for letter input in some configs). But press hardware still refuses to fold letter, so the actual fold/stitch doesn't engage.
3. **PJL INFO CONFIG reports output bins:** `Stapler MAIN TRAY`, `Stapler SUB TRAY`, `Stapler FOLD TRAY`, `Relay Unit 3 TRAY`. The "FOLD TRAY" is the LS-506 + SD-510 saddle output — present but minimum-size-gated.
4. **`Config:KOOp*` properties** mostly take "Plugin" as default; SD-510 was the one real model code accepted for SaddleUnit. Others rejected all attempts — likely auto-discover at print time.

### v0.3.5 changes (this session)
- Tile catalog gained `tip`, `finisher`, `status`, `statusNote` fields per tile.
- WorkflowTiles renders status pills (✓ Confirmed / ⚠ Manual finish / ✗ Blocked / ? Untested) + finisher action summary + `?` info button per tile.
- Operators now see at a glance which workflows the press will auto-finish vs which need manual finish, with hardware notes when relevant.

### Next-session priorities
1. **Test booklet_8.5×11_12x18 with proper bleed PDF** — most-likely-working production booklet path.
2. **Load 11×17 in a tray + test bifold + booklet_8.5×11_11x17**.
3. **Konica tech consult** if 12×18 booklet still doesn't fold — confirm SD-510 actually installed + whether FD-503 fold unit is on the press.
4. **UI: per-job finisher option selection** (staple left vs right vs 2-staple, punch 2/3/4 hole) — needs either more Windows queues OR per-job PrintTicket overrides.

---


Tracks what's been verified end-to-end against the physical press vs. what's
still pending Windows-side setup. Add a new dated block every test session.

---

## 2026-05-11 (Mac dev box, post v0.3.3 deploy)

### Environment
- Host: Hasan's Mac, app at `localhost:5273`, `PRESS_SAFE_PRINT_MODE=live`
- Press: KONICA AccurioPress C3070 @ 172.16.1.149 (online, touchscreen dead — driven via PJL + future Windows queues)
- Trays (per `/api/trays`): T1=24lb-bond (plain letter), T2=100lb-gloss-text, T3-T5=unknown
- Network: shop wired LAN dropped earlier, Mac on Wi-Fi (same subnet — printer reachable)

### ✅ What worked

#### Test pattern: color-blocks-letter
- Endpoint: `POST /api/test-patterns/color-blocks-letter/print-test`
- Preset: `poster_1up_letter` (fix in v0.3.3 — was missing in v0.3.2)
- Result: `status=sent-live`, press received the job. Press then reported `CODE=41502 DISPLAY="tray Letter"` until paper loaded.
- Action: confirms the PJL → port 9100 pipeline. Bundle is built correctly. Tray state surfacing works.

#### Saddle-stitch booklet imposition (5 pages, 5.5×8.5 finished, letter sheets)
- File: 5-page numbered test PDF at `tmp/booklet-test-5pg.pdf`
- Preset: `booklet_5.5x8.5_letter`
- Stock: `24lb-bond` (plain letter, T1)
- Quantity: 1 copy / 2 letter sheets / duplex
- Result: `status=sent-live`, 2 sheets imaged at the press.
- Info finding: "Booklet plan: 5 source pages → 2 sheet(s) per copy × 1 copies = 2 sheets. Fold only — no trim."
- Warn finding: "Finisher engagement skipped (Windows spooler only available on Windows). Press imaged correctly — fold/staple/punch by hand."
- **Imposition output**: 2 letter sheets, each printed both sides, page order arranged so that when the stack is folded in half down the spine and the outer sheet wraps the inner one:
  - cover = source page 1
  - inside front = page 2
  - inside pages = 3, 4, 5
  - back-side blanks fill the rounded-up 8th slot
- **Operator action**: fold the 2 sheets together in half, manually saddle-stitch with a long-arm stapler at the spine. Verify the page numbers come out in the right sequence.

#### STOP button (new in v0.3.3)
- Endpoint: `POST /api/stop`
- Sent PJL `JOB CANCEL` to press successfully (`printer.sent=true, host=172.16.1.149`)
- No pending app-side jobs to drop, no Windows spool layer on Mac
- UI: red STOP button in topbar, confirm modal, per-layer outcome surfaced as toasts

### ⛔ What's NOT yet tested (blocked on Windows setup)

These require the shop's Windows PC to have the 4 print queues configured per
[setup-c3070-queues.ps1](setup-c3070-queues.ps1) + the Konica driver's
Finishing tab populated per queue (UI step, not scriptable).

| Feature | Blocked on | Test plan once Windows is up |
|---|---|---|
| **Auto-fold + saddle-stitch** (BM-660 finisher) | `C3070 Booklet` Windows queue + driver: Layout=Booklet, Binding=Saddle-stitch+Center-fold | Submit same 5-page test PDF as `booklet_5.5x8.5_letter` from Windows app instance, qty=1. Expect 2 letter sheets to come out *already folded + stapled at the spine* via the BM-660. Visually verify fold accuracy + staple position. |
| **Hard stock cover** (cover stock pulled from a different tray) | `C3070 Booklet` queue → driver: Cover tab → Front cover from Tray N (cover stock), Back cover from Tray N | Load 100lb-cover-uncoated in T5, mark loaded in app, configure queue's Cover tab to pull front+back covers from T5. Resubmit booklet, qty=1. Cover sheet should be the cover stock, inner sheets the text stock. |
| **Corner staple** (single-staple stapler) | `C3070 Stapled` queue + driver: Staple=ON, 1-corner upper-left | Submit any multi-page PDF as `stapled_plain_letter`, qty=1. Expect output to come out stapled in the upper-left corner. |
| **3-hole punch** | `C3070 Punched` queue + driver: Punch=ON, 3-hole, left edge | Submit multi-page PDF as `punched_plain_letter`, qty=1. Expect output with 3 holes along the left edge. |
| **8.5×11 booklet on 12×18** (with trim) | Same as auto-fold above + Graphic Wizard 4908 manual trim pass | Submit a PDF with proper bleed as `booklet_8.5x11_12x18`. Press folds, operator trims head/foot/face on the Graphic Wizard. Verify trim marks survive and final size lands at 8.5×11. |

### Pre-flight checklist before each Windows-side test
1. Re-seat shop Ethernet — wired LAN was dropping earlier.
2. Verify finisher hardware health post-brownout per CLAUDE.md hard rule #1. Konica tech needs to OK the BM-660 + stapler + punch unit BEFORE running them in quantity.
3. Load the right paper in the right tray + mark in `/api/trays`.
4. First print of any finisher: **quantity 1, supervised**.
5. STOP button is always available in topbar if the finisher misbehaves.

### Known caveats
- Saddle imposition rounds source page count up to a multiple of 4. A 5-page source produces 8 booklet pages — last 3 are blank. Operator should be told if this isn't desired (consider adding a UI hint when source mod 4 != 0).
- The default tile stock for `booklet_5.5x8.5_letter` is `80lb-gloss-text` which has `parent_sheet=12x18` in the catalog — mismatched against the letter-parent booklet preset. Either the tile default should change to a letter-parent stock (`60lb-offset-text` or `24lb-bond`) or the catalog should add an 80lb gloss text option with `parent_sheet=letter`. Operator currently has to pick the stock manually for this preset.
- Tile defaults at v0.3.3 are all qty=1 (operator scales up). Confirm modal still fires at qty > 100.
