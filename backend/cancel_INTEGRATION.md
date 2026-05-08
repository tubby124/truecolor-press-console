# `POST /api/job/{id}/cancel-spool` — endpoint addition for `backend/main.py`

One additive route. Per repo rule, integration sits in this file rather than
modifying `main.py` directly.

## What it does

Catches the 5-second window after a print job has been submitted but the
operator realizes they need to abort (wrong file, wrong quantity, wrong paper).

In `SAFE_PRINT_MODE=dry` this is purely a local cleanup — the PJL bundle
sits in `tmp/jobs/<id>/` until purged. Cancel deletes the job dir on disk
and returns 200, removing the job from history.

In `SAFE_PRINT_MODE=live` cancellation is best-effort: the job has already
been pushed over the socket to the press, so this endpoint only deletes the
local record. The operator still has to clear the press's queue at the panel
or via PageScope (we cannot reach into the C3070 to recall a queued job
remotely — Konica's print spooler doesn't expose a recall API).

## Add this near the other `@app.post("/api/job/...")` routes

```python
@app.post("/api/job/{job_id}/cancel-spool")
def cancel_spool(job_id: str, user: str = Depends(auth.current_user)):
    """Cancel a just-submitted job. Returns 200 on success, 409 if the job
    has moved past a cancellable state.

    Cancellable statuses: ``pending``, ``spooled-dry``. Once a job is
    ``sent-live`` we leave the dir in place (the operator needs to know the
    PJL bundle was pushed, even if cancellation succeeded at the press).
    Anything else returns 409 — frontend hides the cancel button on its own
    after 5 seconds OR when the status string changes, so the 409 is the
    last-line guard.
    """
    job_path = settings.jobs_dir / job_id
    job_file = job_path / "job.json"
    if not job_file.exists():
        raise HTTPException(404, "job not found")
    try:
        data = json.loads(job_file.read_text())
    except (json.JSONDecodeError, OSError):
        raise HTTPException(409, "job state unreadable; cannot cancel safely")

    status = (data.get("status") or "").lower()
    cancellable = {"pending", "spooled-dry"}
    if status not in cancellable:
        raise HTTPException(409, f"job is '{status}'; not cancellable from here")

    try:
        shutil.rmtree(job_path)
    except OSError as e:
        raise HTTPException(500, f"could not remove job dir: {e}")
    return {"job_id": job_id, "cancelled": True, "previous_status": status}
```

`shutil` is already imported at the top of `main.py`. `json` and `HTTPException`
likewise. No new imports needed.

## Smoke test

```bash
# After login (cookie in /tmp/c)
JOB=$(curl -s --cookie /tmp/c -X POST -F file=@some.pdf -F workflow=business_card \
  -F preset_key=bc_3p5x2_letter -F stock_code=14pt-cs-gloss -F quantity=1 \
  http://127.0.0.1:5273/api/job | jq -r .job_id)

curl -s --cookie /tmp/c -X POST \
  http://127.0.0.1:5273/api/job/$JOB/cancel-spool | jq .
# {"job_id": "...", "cancelled": true, "previous_status": "spooled-dry"}

# Calling cancel again on the same id returns 404 because the dir is gone:
curl -s -w "%{http_code}\n" --cookie /tmp/c -X POST \
  http://127.0.0.1:5273/api/job/$JOB/cancel-spool
# 404
```

## Frontend pairing

`frontend/src/components/ConfirmPrintButton.tsx` shows the Cancel button while
`stage.kind === "submitting"`. The button is auto-hidden 5 seconds after the
"Spooling…" toast OR as soon as the job status moves past `spooling` — the
state machine doesn't actually have a "spooling" status, but the frontend
treats `submitting` as the user-facing equivalent.

## Why not put cancel logic in `jobs.py`?

The job dataclass doesn't carry process state — once `run_job()` returns, the
job is in its terminal state (`spooled-dry` or `sent-live`). Cancellation is
external bookkeeping (delete the on-disk record), so it lives in the route
layer, not the orchestration layer.
