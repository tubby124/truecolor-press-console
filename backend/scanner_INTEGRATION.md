# Scanner integration notes

Quick checklist to wire the new scanner module into the running app. Three
single-line edits — no logic changes required.

## 1. backend/main.py

### a) Import (top of file, near other `from . import` lines)

```python
from . import scanner_router
```

Add it next to the existing `from . import (auth, bleed_fix, ..., trays)`
block — alongside the others is fine; it doesn't matter alphabetically.

### b) Mount the router (after `app = FastAPI(...)`)

Add this one line anywhere after `app = FastAPI(...)` and before `def run()`.
Putting it just below the `# Static assets:` comment — but BEFORE the
`app.mount("/assets", ...)` line — keeps `/api/*` taking priority over
static, same pattern as the existing routes.

```python
app.include_router(scanner_router.router)
```

### c) (Optional) Hook into lifespan purge

Inside the existing `lifespan()` function, after the `jobs.purge_old_jobs()`
call, add:

```python
try:
    scanner.purge_old_dismissed()
except Exception as e:  # noqa: BLE001
    logger.warning("Scanner dismissed-purge failed at startup: %s", e)
```

…and add `scanner` to the import block. Skipping this is fine for v1 —
dismissed scans accumulate slowly and a manual `rm -rf ~/Documents/PressConsole/scans/_dismissed/`
clears them anytime.

## 2. frontend/src/App.tsx

### a) Import (with the other component imports)

```tsx
import { ScanInbox } from "./components/ScanInbox";
```

### b) Render — placement matches the spec: under `<SavedPresets />`,
before `<WorkflowTiles />`

Replace:

```tsx
<SavedPresets />
<WorkflowTiles />
```

with:

```tsx
<SavedPresets />
<ScanInbox />
<WorkflowTiles />
```

`<ScanInbox />` self-hides when `stage.kind !== "idle"` AND when the inbox
is empty, so there's no extra gating to add.

## What I did NOT touch

- `backend/main.py` — untouched (per spec)
- `frontend/src/App.tsx` — untouched (per spec)
- Existing inspect/preview/job pipeline — untouched; scan import re-uses it

## What I added

| File | Purpose |
| --- | --- |
| `backend/scanner.py` | Inbox dir, list, import, dismiss, purge, SMB setup MD |
| `backend/scanner_router.py` | `/api/scan/{inbox,import,dismiss,file/<name>,setup-instructions}` |
| `frontend/src/components/ScanInbox.tsx` | Polling tile, self-hiding |
| `frontend/src/api.ts` | `scanInbox`, `scanImport`, `scanDismiss`, `scanSetup` |
| `frontend/src/types.ts` | `ScanItem`, `ScanInboxResponse`, `ScanImportResult`, `ScanSetupResponse` |
| `docs/SCANNER-SETUP.md` | Operator-facing setup guide |

## One extra endpoint (worth flagging)

The router exposes `GET /api/scan/file/{filename}` so the frontend can pull
the imported scan back as a `Blob` and reconstruct a `File` for the
existing InspectCard / `/api/job` multipart flow. It's auth-gated, only
serves files directly under `settings.jobs_dir/_inspect/`, and rejects path
traversal. If you'd rather not add this surface, the alternative is to
have `/api/scan/import` also return the file bytes (base64) — but that's
ugly and wastes memory on large TIFFs.
