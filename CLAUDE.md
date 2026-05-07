# CLAUDE.md — True Color Press Console

Repo-specific instructions. Read first when working in this repo.

## Mission
Make the shop's Konica AccurioPress C3070 usable without the dead touchscreen. Operators drop a file, pick a workflow tile, click print. No panel, no driver wrestling, no imposition by hand.

## Hard rules

1. **Never enable a finisher mechanism (staple / fold / punch) until that specific accessory has been verified healthy by the tech post-brownout AND tested with a single supervised print.** v1 ships with all finishers disabled (passive pass-through to top output bin).
2. **Never send a real print job to `172.16.1.149` until C-6753 is cleared by Konica technician.** Use dry-run mode (write the PJL bundle to `tmp/`, don't open socket to 9100). The `SAFE_PRINT_MODE=dry` env var is the gate.
3. **Click rate must be sourced from `truecolor-estimator/data/tables/config.v1.csv`.** Don't hardcode. The number escalates 3% annually per Meridian OneCap lease.
4. **Local-only.** No cloud auth, no external network calls. Runs on shop Mac at `localhost:5273`. If you find yourself adding OAuth, Stripe, Supabase — stop, you're in the wrong repo.
5. **Single-user assumption.** v1 runs on one Mac, one operator at a time. Don't add multi-tenant complexity.

## Diagnose before changing

- If a print job fails: query the printer status (`backend.printer.probe()`) before changing imposition logic. Most failures are paper/tray/finisher state, not bad PDFs.
- If preflight rejects a file: surface the exact reason to the operator, don't silently fix.
- Log every job to `backend/jobs/YYYY-MM-DD/` with the input file, normalized PDF, PJL header, and printer response. No invisible state.

## Tech stack

- Python 3.12 + FastAPI
- pikepdf, Pillow, psd-tools, Ghostscript (system), ImageMagick (system), qpdf (system)
- Vite + React + TypeScript on the frontend
- Pure socket to port 9100 with PJL — no CUPS, no LPR (more deterministic, fewer moving parts)

## File map

- `backend/printer.py` — PJL driver, status probe, PDL send
- `backend/preflight.py` — color mode, fonts, resolution, bleed checks
- `backend/normalize.py` — input → PDF/X-1a CMYK
- `backend/impose.py` — n-up, brochure, booklet imposition
- `backend/settings.py` — printer IP, click rates, paths
- `backend/main.py` — FastAPI app
- `backend/cli.py` — dry-run + diagnostic CLI
- `frontend/src/App.tsx` — drop zone + workflow tiles
- `frontend/src/workflows/*.ts` — per-workflow logic + UI hints
- `docs/HARDWARE-GATES.md` — manual checklist before enabling real-print mode
- `icc/` — Konica C3070 ICC profile (download from Konica; not committed)
- `tmp/` — working files (gitignored)

## Sibling repos

- `../truecolor-estimator` — public SEO site for True Color. Source of truth for click rates and product data.
- `../` (TRUE COLOR PRICING dir) — operational docs, plans, handoff files.

## When to escalate to Hasan

- Tech reports finisher / fuser / HV unit damage from the voltage event (changes scope).
- Click-rate CSV is missing or schema changed (estimator drift).
- Anything that requires touching the press's panel via the network admin (Konica's PageScope auth state).
