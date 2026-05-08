# catalog.py — Integration Notes

Notes from the catalog-expansion pass (4 → 14 stocks). Read this before wiring the new fields into UI surfaces, recompose flows, or main.py.

## Schema changes

**No new fields were added to the `Stock` dataclass.** Every new stock fits inside the existing schema:

```
code, name, finish, weight, cost_per_unit, parent_sheet, tags,
default_tray="AUTO", default_paper_size="P12X18", friendly_name=""
```

The override-JSON loader (`shop_stocks()` + `_load_overrides()`) is therefore **fully backwards compatible** with any `~/.config/press-console/stocks.json` written against the previous 4-stock catalog. Old override files keep working unchanged. New override entries can use any of the same fields.

## What I did NOT change

- `backend/main.py` — untouched. The `/api/stocks` endpoint already returns every field the new stocks use (verified at [backend/main.py L171-L187](backend/main.py)).
- `backend/settings.py` — untouched.
- `backend/jobs.py` — untouched. Already reads `stock.default_tray` and `stock.code` correctly (L76, L124, L135).
- `backend/printer.py` — untouched. Still receives `MEDIASOURCE` from `stock.default_tray`.
- `backend/trays.py` — untouched. Note: trays.py uses `T1..T5` keys for operator state tracking; `Stock.default_tray` uses `TRAY1..TRAY5` for PJL `MEDIASOURCE`. These are separate concerns — no normalization needed.

## What I DID change beyond catalog.py

- `backend/impose.py` — additive only. Added two oriented sheet entries to `SHEETS` for completeness so any future stock that prints on 13×19 can pick a landscape orientation and SRA3 has a landscape variant:
  - `19x13` → SheetSpec("P13X19", 19.0, 13.0)
  - `sra3-l` → SheetSpec("SRA3", 17.7, 12.6)
  
  No existing presets reference these; they're available for future use. No risk to existing flows.

## Tags introduced (UI implication)

Three new "control" tags appear in the catalog. The cost panel / stock picker UI should treat them specially when rendering:

| Tag | Meaning | Suggested UI behavior |
|-----|---------|------------------------|
| `_cost_unverified` | `cost_per_unit` is an industry-grounded estimate, not from Hasan's actual invoice | Show a small "~" prefix on the cost figure, OR a warning chip in the cost-breakdown drawer. Margin-tight quotes should warn the operator before send. |
| `_inactive` | Hasan doesn't stock this right now (set via override) | Gray out in the picker, sort to the bottom of the list, do NOT auto-select. |
| `_press_setup_required` | Stock requires Konica tech setup before C3070 will fuse it correctly (only `synthetic-yupo-8mil` today) | Block selection in `live` mode unless an admin has explicitly enabled it; show a tech-call-required modal. |

These tags are not enforced anywhere in the backend yet. Surfacing them is a frontend / cost-panel task. Filing as a non-blocking follow-up is fine — defaults still print correctly without any of this.

## Tray distribution sanity-check

| Tray  | Stocks targeting this tray (by default)                        |
|-------|----------------------------------------------------------------|
| TRAY1 | 24lb-bond, 60lb-offset-text                                    |
| TRAY2 | 14pt-cs-gloss, 14pt-cs-silk                                    |
| TRAY3 | 80lb-gloss-text, 80lb-silk-text, 60lb-bw-text                  |
| TRAY4 | 100lb-gloss-text, 100lb-uncoated-text, 16pt-cs-gloss, 16pt-cs-silk |
| TRAY5 | 100lb-cover-uncoated, synthetic-yupo-8mil, vellum-translucent  |

Convention: T1 = letter docs, T2 = volume BC, T3 = mid flyers, T4 = heavy / premium, T5 = uncoated + specialty. No tray has more than 4 stocks defaulting to it; the operator can still load whatever they want — `default_tray` is just the picker's first-suggestion.

## Migration / deploy steps

1. No migration needed — the catalog is read each time the API hits `/api/stocks`, so changes appear on the next operator UI refresh.
2. No restart needed if the catalog is overridden via `~/.config/press-console/stocks.json` — that file is re-read every call. (FastAPI app reload is only needed if `_DEFAULT_STOCKS` itself is edited.)
3. Existing `SHOP_STOCKS = shop_stocks()` module-level eager-evaluated tuple at L146 still works — but consumers should prefer `catalog.shop_stocks()` (the function) for live override visibility. The module-level alias only matters at import time and is kept for backwards compat with anything that already imports it. Worth keeping an eye on — if a test or older route relies on the eager tuple being authoritative, it'll go stale relative to override edits.

## Things to ask Hasan before going live

1. **Real Spicers/Pacesetter/Unisource invoice prices** for each stock — close Gate 6 in HARDWARE-GATES.md.
2. **Confirm finish naming** — is "silk" the right word in shop slang, or does Hasan say "matte" / "dull" / "satin"? Stocks with `finish="silk"` should match what's on the operator's vocabulary.
3. **Synthetic stock decision** — does Hasan actually run Yupo / Polylith on the C3070, or is signage / outdoor work always sent to wide-format? If it never runs through the C3070, drop the synthetic stock and remove the `_press_setup_required` complexity.
4. **Translucent vellum** — is this a real stock he carries? It's a niche specialty. If unused, kill it.
5. **60lb bright white text** — is the cheap-flyer slot actually 60lb or 70lb at his shop? The cost split is meaningful (~30% per sheet).
6. **Tray rotation** — Hasan should walk through each tray currently in the press and tell us what's actually loaded; that determines whether the `default_tray` assignments above match reality.

## Ship checklist

- [x] `_DEFAULT_STOCKS` expanded to 14 entries
- [x] No `Stock` dataclass field changes (backwards compat preserved)
- [x] `impose.py` SHEETS additive only (`19x13`, `sra3-l`)
- [x] `STOCKS-OVERRIDE-TEMPLATE.json` written with examples
- [x] HARDWARE-GATES.md Gate 6 added
- [x] `main.py` untouched
- [x] `settings.py` untouched
