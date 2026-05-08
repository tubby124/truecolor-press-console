# Wiring `press_state_router` into `backend/main.py`

Two edits, both additive.

## 1. Import (with the other backend module imports near the top)

```python
from . import press_state_router
```

## 2. Register the router (anywhere after `app = FastAPI(...)` — placement
before the static-asset mount is fine, the router uses `/api/press/*` so it
won't collide with `/assets`)

```python
app.include_router(press_state_router.router)
```

That's it. The two endpoints come up at:

- `GET /api/press/state`
- `GET /api/press/state/refresh`

Both are protected by the same session cookie as every other `/api/*` route.

## Dependency

`pyproject.toml` now declares `pysnmp>=6.2`. Run:

```bash
pip install -e .
# or, if you use uv
uv pip install -e .
```

The router degrades gracefully if `pysnmp` is missing — you'll get
`{snmp_available: false, error: "pysnmp not installed; ..."}` instead of a
500. So integration won't break a stale environment.

## Smoke test

```bash
# After login (cookie in ~/.config/press-console/sessions.json)
curl -s --cookie-jar /tmp/c --cookie /tmp/c \
  -d 'password=qwerty123' http://127.0.0.1:5273/login
curl -s --cookie /tmp/c http://127.0.0.1:5273/api/press/state | jq .
```

Expected fields: `ts`, `host`, `reachable`, `snmp_available`, `trays{}`,
`alerts[]`, `lifetime_pagecount`, `device_status`, `error`, `cached`.

## Notes

- `composite_state` caches in-memory for 15s. `state/refresh` clears that
  cache before re-querying. The frontend polls `/state` every 30s and only
  hits `/refresh` on explicit user action.
- All SNMP queries are read-only (`getCmd` / `nextCmd`). No SET. The press is
  in stored-fault state from the C-6753 voltage event — nothing here can
  nudge the panel state machine.
- SNMP target is `printer_host:161` with community `public`. If the shop ever
  hardens the press (it shouldn't on a flat 172.16.x VLAN), expose
  `PRESS_SNMP_COMMUNITY` and pass it through.
