# Wiring `test_patterns_router` into `backend/main.py`

Two edits, both additive — same pattern as `press_state_INTEGRATION.md`.

## 1. Import (with the other backend module imports near the top)

```python
from . import test_patterns_router
```

## 2. Register the router (anywhere after `app = FastAPI(...)`, before the
static-asset mount at the bottom of the file)

```python
app.include_router(test_patterns_router.router)
```

That's it. After both edits, three new endpoints come up:

- `GET  /api/test-patterns`
- `GET  /api/test-patterns/{id}/file.pdf`
- `POST /api/test-patterns/{id}/print-test`

All session-cookie protected.

## Asset prerequisite

The router serves binary PDFs from `assets/test-patterns/`. They're checked
into the repo, but if anything weird happens to them, regenerate:

```bash
python scripts/generate_test_patterns.py
```

Outputs `color-blocks-letter.pdf`, `registration-target-12x18.pdf`,
`density-bar-letter.pdf`. Total under 6 KB — safe to commit.

## Smoke test

After login (cookie in `~/.config/press-console/sessions.json`):

```bash
curl -s --cookie /tmp/c http://127.0.0.1:5273/api/test-patterns | jq .
curl -s --cookie /tmp/c -X POST \
  http://127.0.0.1:5273/api/test-patterns/color-blocks-letter/print-test | jq .
```

Expected:

- `GET` returns 3 entries with `available: true` and `file_size_kb` populated.
- `POST` returns a `Job` JSON identical in shape to `/api/job` — same fields,
  `status: "spooled-dry"` when `SAFE_PRINT_MODE=dry`.

## Notes

- The `print-test` endpoint passes `expect_bleed_in=0.0` to `jobs.run_job` —
  these patterns include their own marks; surfacing a bleed warning would be
  a false positive for calibration prints.
- Recommended stocks use codes that already exist in `catalog._DEFAULT_STOCKS`
  (`100lb-gloss-text`, `14pt-cs-gloss`). If those get renamed in the catalog,
  update `PATTERNS[*].recommended_stock` in `test_patterns_router.py`.
- Patterns hit the same tray-vs-stock guard as `/api/job` once we lift the
  guard from `submit_job` into `jobs.run_job` (currently the guard sits in
  the route, so `print-test` skips it). For the tech visit this is fine —
  tech is standing at the press, not relying on tray-state metadata.
