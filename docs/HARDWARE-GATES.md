# Hardware Gates — Before First Real Print

The press hit `C-6753` (scanner DSIPB ASIC clock fault) from a voltage event. The print engine reports `ONLINE=TRUE` over the network, but `ONLINE=TRUE` is a soft signal — it does not guarantee the imaging chain (laser, polygon, fuser, HV unit, transfer) survived the brownout intact.

**Do not flip `SAFE_PRINT_MODE` from `dry` to `live` until every gate below is checked off by the technician.**

## Gate 1 — Power on spec'd circuit

- [ ] Printer is on a **dedicated 208V / 20A** circuit (Konica AccurioPress C3070 spec).
- [ ] No shared loads on the same breaker (no other heavy draw).
- [ ] Confirmed by tech / electrician.
- Date confirmed: ____  By: ____

## Gate 2 — C-6753 cleared

- [ ] Konica technician entered service mode and cleared stored `C-6753`.
- [ ] Touchscreen reachable to home screen (or technician confirms code is no longer latched).
- [ ] Re-probe via `python -m backend.cli probe` returns no Level A trouble flags.
- Date cleared: ____  By: ____  Service code/ticket: ____

## Gate 3 — Imaging chain verified post-event

Tech must visually + functionally verify each component was not silently damaged by the brownout:

- [ ] Laser scanner unit (LSU) — polygon spin, beam alignment OK
- [ ] Fuser — heat element resistance within spec, lamp + thermistor OK
- [ ] High-voltage power supply (HVPS) — transfer / charge / developer voltages within spec
- [ ] Transfer belt + secondary transfer roller — no scoring or burn marks
- [ ] Drum cartridges — no laser damage on photoreceptor surface
- Date verified: ____  By: ____

## Gate 4 — First test print (single page, supervised)

After gates 1-3 are clear:

1. Load tray 1 with letter plain paper.
2. Run `python -m backend.cli test-page --supervised`.
3. Watch the press during the entire print cycle.
4. Compare output to expected: solid black bar, four corner registration marks, color gradient, lifetime page count timestamp.
5. If anything is off (banding, colour shift, jam, smell, weird noise) — abort, power off, call tech.

- [ ] First test page printed successfully without abnormal behavior.
- Date: ____  Notes: ____

## Gate 5 — Per-finisher verification (one at a time)

Only after gate 4 passes. Each finisher gets its own gate before being exposed in the UI.

- [ ] **Stapler** — single 10-page corner-staple test → check stitch quality, no jam
- [ ] **Booklet maker** — single 8-page saddle-stitch test → check fold alignment, stitch position
- [ ] **Hole punch** — single 1-page punch test → check hole position, paper damage

Each finisher gets its workflow tile re-enabled in the UI only after its row above is checked.

---

**Operator instruction:** Until every box on this page is checked, the press console UI runs in `dry` mode. The "Print" button generates the print-ready PDF + PJL bundle into `tmp/jobs/` for review, but does NOT open a socket to `172.16.1.149:9100`. Switch `SAFE_PRINT_MODE=live` in `.env` only after this checklist is signed off.
