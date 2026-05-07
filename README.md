# True Color Press Console

Mac drag-and-drop interface for the shop's **Konica AccurioPress C3070**.

Bypasses the dead touchscreen panel (locked behind stored error C-6753) and drives the press over the network so operators can print business cards, brochures, booklets, and stapled documents without touching the broken UI.

**Sibling repo to** [`truecolor-estimator`](../truecolor-estimator) — same shop, different surface area. Estimator is the public SEO site. This is internal shop tooling.

## Status

- 2026-05-07 — discovery + plan locked. Scaffold up. **First test print blocked until tech clears C-6753 and verifies imaging chain post-brownout.**
- See [docs/HARDWARE-GATES.md](docs/HARDWARE-GATES.md) for the gate checklist.
- Full plan: `../C3070-PRESS-CONSOLE-PLAN.md`
- Vault summary: `~/Downloads/Obsidian Vault/Projects/true-color/2026-05-07-c3070-press-console-discovery.md`

## Architecture

- **Backend:** Python 3.12 + FastAPI. PJL over raw 9100 to the press. PDF normalization via Ghostscript + pikepdf.
- **Frontend:** Vite + React. Drag-drop, 6 workflow tiles, live preview, preflight panel.
- **Local-only.** Runs at `http://localhost:5273` on the shop Mac. No cloud, no auth, no external network.

## Workflows (v1 = no finishers)

| Tile | Status | Notes |
|---|---|---|
| Plain print | scaffold | Letter / legal / 12×18 / SRA3, duplex toggle, tray select |
| Business cards | scaffold | 10-up letter or 21-up SRA3 with crop marks + bleed (auto-cutter handles separation) |
| Bi-fold brochure | scaffold | Manual fold — UI prints fold guides as ghost lines |
| Tri-fold brochure | scaffold | Manual fold — UI prints fold guides as ghost lines |
| Multi-page document | scaffold | Duplex, no finishing |
| Saddle-stitch booklet | **gated v2** | Engages booklet maker — disabled until that finisher is independently verified |

Staple, hole punch, and finisher-output bins are all v2+ — disabled in v1 to engage zero finisher mechanisms.

## Run

```bash
# from this directory
uv venv && source .venv/bin/activate
uv pip install -e .
# CLI dry-run (does NOT send to printer)
python -m backend.cli probe --host 172.16.1.149
python -m backend.cli dry-run plain-print path/to/file.pdf

# Web UI (when frontend is built)
python -m backend.main           # backend on :5273
cd frontend && npm run dev        # frontend on :5174 with proxy to :5273
```

## Hardware gates

See [docs/HARDWARE-GATES.md](docs/HARDWARE-GATES.md). Do not enable real-print mode until all gates clear.

## Constants of record

- **Press IP:** `172.16.1.149` (LAN at shop)
- **Click rate (Year 3, 2026):** `$0.0573/sheet color`, `$0.0117/sheet B&W` — source: [truecolor-estimator/data/tables/config.v1.csv](../truecolor-estimator/data/tables/config.v1.csv) keys `konica_ink_cost_per_sheet`, `konica_bw_cost_per_sheet`. Update annually each November per Meridian OneCap lease (Order S00665431).
- **Lifetime page count (as of 2026-05-07):** 391,394
- **Memory:** 14 GB system, 970 MB free for jobs
- **Trays:** T1=Letter · T2=Custom (cardstock?) · T3=Letter · T4=12×18 · T5=12×18
- **Languages:** PCL, **PostScript**, TIFF, PPML, JPEG
