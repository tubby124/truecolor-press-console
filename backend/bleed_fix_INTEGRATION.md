# `POST /api/bleed-fix` — pair with new `BleedNoContentError`

`backend/bleed_fix.py` now raises `BleedNoContentError` from `fix_bleed()` when
all four trim edges of page 1 are near-white (no design content past the cut
line — trim-extend would just hide white slivers).

The route in `backend/main.py` currently catches any non-`FileNotFoundError`
exception and returns 500. Add a `BleedNoContentError` branch that returns a
structured 422 the frontend can recognize.

## Edit `bleed_fix_endpoint` in `backend/main.py`

Find this block (roughly lines 263-291):

```python
@app.post("/api/bleed-fix")
def bleed_fix_endpoint(body: BleedFixBody, user: str = Depends(auth.current_user)):
    ...
    src_pdf = _resolve_inspected_pdf(body.inspect_filename)
    try:
        fixed_path, grew_in = bleed_fix.fix_bleed(src_pdf, target_bleed_in=body.target_bleed_in)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Couldn't extend the bleed: {e}")
```

Insert the new branch before the catch-all:

```python
@app.post("/api/bleed-fix")
def bleed_fix_endpoint(body: BleedFixBody, user: str = Depends(auth.current_user)):
    ...
    src_pdf = _resolve_inspected_pdf(body.inspect_filename)
    try:
        fixed_path, grew_in = bleed_fix.fix_bleed(src_pdf, target_bleed_in=body.target_bleed_in)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except bleed_fix.BleedNoContentError as e:
        # 422 = "the input is structurally fine but we can't proceed".
        # Frontend (InspectCard.tsx) catches this status + body shape and
        # renders a friendlier toast pointing the operator at re-exporting
        # from their design tool with bleed.
        raise HTTPException(
            status_code=422,
            detail={
                "error": "design-ends-at-cut-line",
                "message": str(e),
            },
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Couldn't extend the bleed: {e}")
```

That's it — `bleed_fix` is already imported at the top of `main.py`.

## Frontend handling

`frontend/src/components/InspectCard.tsx` already catches the 422 and uses the
`{error, message}` body shape. If the body shape changes here, mirror it in
the frontend.

## Why 422 and not 400

400 is "client sent malformed input" — the PDF is fine, the user did
nothing wrong, the auto-fix just doesn't apply to designs without bleed.
422 ("Unprocessable Entity") fits semantically: the server understood the
request but cannot fulfill it because of the content, not the format.

## Smoke test

Build a 1-page PDF with white margins (no full-bleed background), drop it
into the console, click "Fix it for me" on the bleed warning. Expected:
toast says "design ends right at the cut line — re-export with 1/8" bleed",
no extension is performed, and the original file is preserved on disk.

A regular full-bleed PDF should still extend successfully and toast
"Extended your background 0.125\"…" as before.
