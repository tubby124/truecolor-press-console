# Operator First Day — 30-Minute Walkthrough

**Audience:** anyone new to the True Color shop touching the C3070 press for the first time. No print-shop background needed.

**Time:** 5 minutes to read, 25 minutes hands-on.

**You will need:**
- The shop laptop / Mac at the press
- A test PDF (any business card or letter-size design — Hasan can hand you one)
- Two empty trays in the press loaded with paper that matches the test design

---

## 1. What the press is, and what's broken (3 sentences)

The Konica AccurioPress C3070 is the office-style print-on-demand press in the back room. **Its built-in touchscreen is dead** — there was a power surge a few months ago, and the screen now permanently shows a stored error code (C-6753). The press itself is fine; we drive it from the laptop instead, through this web app on `localhost:5273`.

So when something looks weird, **don't tap the press's panel** — come to the laptop.

---

## 2. Open the app

1. Open Chrome (or Safari).
2. Type `localhost:5273` in the address bar.
3. Password: `qwerty123`. Tap **Log in**.

You should see "True Color · Press Console" at the top, a big drop area in the middle, and a row of workflow tiles below.

> **Tip:** the first time you log in, a 3-step popover walks you through the basics. If you skipped it and want it again, clear the browser's site data for `localhost:5273` and refresh.

---

## 3. Print one job (the happy path)

1. **Drop your test PDF into the big drop area.** Or tap it and pick the file from your computer.
2. The system reads the PDF and shows a "Recommendation" card. It pre-fills:
   - **Layout** (e.g. "Business cards — 21 per sheet (standard)")
   - **Paper** (e.g. "Thick glossy business card paper")
   - **Quantity** (a sensible default, usually 100)
   - **Sides** (1-sided or 2-sided)
3. **Look at the imposed-sheet preview** on the right. There's a one-line plain-English caption under it telling you what you're going to get ("21 cards per sheet — cutter slices them apart afterward").
4. If everything looks right, tap the **green "Looks good — print N" button**.
5. If the right paper isn't loaded in any tray yet, the app pops up a modal: **"Put [paper] in [tray], then tap the green button below."** Load the paper into the tray it tells you, then tap **"Done — print now."**
6. The press starts printing. You'll get a success toast at the bottom right.

That's it for a normal job.

---

## 4. What to do when something looks off

**Don't ignore the warning panels.** They're trying to save you a reprint.

The 4 most common warnings:

### "This file doesn't say where the cut line is"
Code: `no-trimbox`. Means the PDF was exported without crop marks. **What to do:** if your design doesn't go to the edge (no full-bleed background or photo), this is fine — just print. If it does, re-export the PDF from the design tool with "Marks and Bleeds" turned on, and drop the new PDF.

### "Your design might cut white at the edges"
Code: `insufficient-bleed`. Means the design goes near the edge but not far enough past it. **What to do:** tap the **"Fix it for me"** button right next to the warning. The app extends the background out for you. Toast confirms how much it extended ("Extended your background 0.062"…"). If your design ends sharply at the cut line (no background to extend), re-export from the design tool with at least 1/8" bleed.

### "Some fonts in this file aren't included"
Code: `fonts-not-embedded`. **Hard blocker** — the press will print Courier (typewriter font) instead of what was designed. **What to do:** open the file in the design tool that made it, re-export as PDF with **"Embed all fonts"** turned on, and drop the new PDF.

### "A photo on this page is low-resolution"
Code: `low-dpi-image`. **What to do:** if it's important (premium print, glossy flyer), get a sharper version of the photo from the customer. If it's a draft, just print — it'll look soft but it'll print.

For any other warning, tap the **"What to do about it"** button under the warning. It expands with numbered fix steps.

---

## 5. The tray bar (top of the screen)

By default it's collapsed to a small grey pill: **"Trays · 3 of 5 loaded"**. **You almost never need to touch it.**

When you do need to touch it:
- The press ran out of a paper and you just refilled it → tap the pill, click the tray, mark it "full".
- You loaded a new paper into a tray that wasn't being used → tap the pill, click the empty tray, pick the paper from the dropdown, save.

Otherwise: leave it collapsed.

---

## 6. Batch printing (multiple files at once)

Drop **2 or more** files into the drop area at once.

The screen switches to "Batch · N files". You pick the layout + paper + quantity once, the system makes one job per file. Useful for: 30 different business-card customers, all 3.5×2", running on the same paper.

A confirmation toast fires when batch mode engages so you know it's not single-file inspect anymore.

---

## 7. When to call Hasan

- The press displays a **status code** other than C-6753 on its panel (anything blinking, anything new).
- The print physically jams or sounds wrong.
- The app shows an **error toast you don't understand** that doesn't go away after refresh.
- A customer's file fails preflight with errors you can't fix from the design tool.
- The tech is on-site working on the press.
- Anything you're not sure about.

**Hasan's number is on the laminated card on the wall.** Don't be shy — five minutes of "wait, ask first" beats a wasted ream of paper.

---

## 8. When you're done for the day

- Hit **Log out** (top right).
- The press goes to sleep on its own — no need to power it down unless Hasan says so.
- **Don't unplug the press from the wall.** It's on a UPS / surge protector and the protector handles brownouts; unplugging interrupts the warm-up cycle.

---

## Quick recovery card (print and pin near the laptop)

| Problem | What to do |
|---------|------------|
| App page is blank / won't load | Refresh the page once. Still blank? Quit Chrome and reopen. Still blank? Restart the laptop. |
| "Press not reachable" banner | Check the press is powered on; check the network cable from the press to the wall jack. |
| Tray light blinking on the press | Out of paper. Refill the tray, mark it "full" in the tray bar. |
| File won't drop | Save the design as PDF first (from Word, Photoshop, etc.) then drop the PDF. |
| "DRY mode" banner | We're still in safety mode — print jobs aren't going to the press for real, just being saved as preview files. Don't worry about it; Hasan flips this off when the tech clears the press. |

---

## What the dry-mode banner means

Right now there's a yellow banner at the top: **"SAFE PRINT MODE — DRY"**. It means jobs are being **simulated** instead of physically printed. We're in this mode because the Konica technician hasn't yet cleared the press's stored error code (C-6753). Until they do, the press stays untouched.

When you tap "print" in dry mode, you'll see "Spooled (DRY): N sheets" instead of "Sent to press." The job file is saved on disk so we can verify everything looks right, but no paper moves.

**Hasan flips this to "live" once the tech clears the press.** You don't need to do anything — the banner just disappears.
