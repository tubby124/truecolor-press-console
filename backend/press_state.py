"""Live press-state queries for the AccurioPress C3070.

Read-only window into what the press is *actually* doing, separate from the
operator-maintained tray bookkeeping in `backend/trays.py`. Three sources:

  1. SNMP — Standard Printer MIB v2 (RFC 3805) for tray contents, alerts, and
     the marker life count. Konica also exposes vendor OIDs under enterprise
     1.3.6.1.4.1.18334 but the standard MIB is enough for v1.
  2. PJL — fallback for `@PJL INFO PAGECOUNT` over the existing 9100 socket
     when SNMP is firewalled or returns nothing for `prtMarkerLifeCount`.
  3. In-memory composite cache (15s TTL) so a UI polling at 30s can hit refresh
     without hammering the press.

Hard rules:
  - Never write. Every helper here uses GET/GET-NEXT walks or a read-only PJL
    INFO query. The press is in stored-fault state (C-6753) until the tech
    clears it; anything that could nudge the panel state machine is off-limits.
  - Graceful failure: a network blip returns ``{reachable: false, error: ...}``
    instead of raising. The UI must still render.
  - SAFE_PRINT_MODE is irrelevant here — state queries don't touch the print
    pipeline. Read regardless of dry/live.

If pysnmp is missing the module degrades to PJL-only state; the SNMP-derived
fields come back empty and the UI shows "SNMP unavailable" rather than crashing
the whole endpoint. This keeps `pyproject.toml` honest while letting the
operator at least see lifetime page count + the existing PJL probe data.
"""

from __future__ import annotations

import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from .settings import settings

logger = logging.getLogger("press-console.state")


# ───────────────────────── SNMP plumbing ─────────────────────────

# Standard Printer MIB v2 (RFC 3805) base OIDs we walk.
OID_PRT_INPUT_DESCRIPTION = "1.3.6.1.2.1.43.8.2.1.13"          # prtInputDescription
OID_PRT_INPUT_CURRENT_LEVEL = "1.3.6.1.2.1.43.8.2.1.10"        # prtInputCurrentLevel
OID_PRT_INPUT_MAX_CAPACITY = "1.3.6.1.2.1.43.8.2.1.9"          # prtInputMaxCapacity
OID_PRT_INPUT_MEDIA_NAME = "1.3.6.1.2.1.43.8.2.1.12"           # prtInputMediaName
OID_PRT_INPUT_DIM_FEED = "1.3.6.1.2.1.43.8.2.1.4"              # prtInputMediaDimFeedDirDeclared
OID_PRT_INPUT_DIM_XFEED = "1.3.6.1.2.1.43.8.2.1.5"             # prtInputMediaDimXFeedDirDeclared
OID_PRT_INPUT_DIM_UNIT = "1.3.6.1.2.1.43.8.2.1.3"              # prtInputDefaultMediaDimUnit (2=micrometres, 3=10000ths-of-inch)
OID_PRT_ALERT_TABLE = "1.3.6.1.2.1.43.18.1.1"                  # prtAlertEntry
OID_PRT_ALERT_SEVERITY = "1.3.6.1.2.1.43.18.1.1.2"             # prtAlertSeverityLevel
OID_PRT_ALERT_GROUP = "1.3.6.1.2.1.43.18.1.1.4"                # prtAlertGroup
OID_PRT_ALERT_CODE = "1.3.6.1.2.1.43.18.1.1.7"                 # prtAlertCode
OID_PRT_ALERT_DESCRIPTION = "1.3.6.1.2.1.43.18.1.1.8"          # prtAlertDescription
OID_PRT_ALERT_TIME = "1.3.6.1.2.1.43.18.1.1.9"                 # prtAlertTime (sysUpTime ticks)
OID_PRT_MARKER_LIFE_COUNT = "1.3.6.1.2.1.43.10.2.1.4.1.1"      # prtMarkerLifeCount.1.1
OID_HR_DEVICE_STATUS = "1.3.6.1.2.1.25.3.2.1.5.1"              # hrDeviceStatus
OID_HR_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"             # hrPrinterStatus
OID_HR_PRINTER_DETECTED_ERROR_STATE = "1.3.6.1.2.1.25.3.5.1.2.1"

# RFC 3805 mappings.
ALERT_SEVERITY_MAP = {
    1: "other",
    3: "critical",       # criticalBinaryChangeEvent
    4: "warning",        # warningBinaryChangeEvent
    5: "warning",        # warningUnaryChangeEvent
    6: "critical",       # criticalUnaryChangeEvent
}
ALERT_GROUP_MAP = {
    5: "general",
    6: "cover",
    7: "localization",
    8: "input",
    9: "output",
    10: "marker",
    11: "marker-supplies",
    12: "marker-colorant",
    13: "media-path",
    14: "channel",
    15: "interpreter",
    16: "console",
    17: "alert",
}
HR_PRINTER_STATUS_MAP = {1: "other", 2: "unknown", 3: "idle", 4: "printing", 5: "warmup"}

# prtInputCurrentLevel / prtInputMaxCapacity sentinels per RFC 3805.
LEVEL_OTHER = -1
LEVEL_UNKNOWN = -2
LEVEL_REMAINING_AT_LEAST_ONE = -3


def _pysnmp_available() -> bool:
    try:
        import pysnmp.hlapi  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — any import error → degrade gracefully
        return False


def _snmp_walk(host: str, base_oid: str, timeout: float, community: str = "public") -> list[tuple[str, Any]]:
    """Walk ``base_oid`` and return ``[(oid_string, value), ...]``.

    Returns ``[]`` on any error (timeout, no SNMP, wrong community, etc.). The
    caller is expected to treat empty as "no data" rather than "no press" —
    that distinction is encoded in ``composite_state``'s ``reachable`` field
    via a separate TCP probe.
    """
    try:
        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            nextCmd,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("pysnmp import failed: %s", e)
        return []

    rows: list[tuple[str, Any]] = []
    try:
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),  # SNMPv2c
            UdpTransportTarget((host, 161), timeout=timeout, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,  # stop when we leave the subtree
        )
        for error_indication, error_status, _error_index, var_binds in iterator:
            if error_indication or error_status:
                logger.debug(
                    "SNMP walk error %s/%s on %s",
                    error_indication, error_status, base_oid,
                )
                break
            for oid, value in var_binds:
                rows.append((str(oid), value))
    except Exception as e:  # noqa: BLE001 — pysnmp throws a zoo of exceptions
        logger.debug("SNMP walk exception on %s: %s", base_oid, e)
        return []
    return rows


def _snmp_get(host: str, oid: str, timeout: float, community: str = "public") -> Any:
    """Single OID GET. Returns the value or None on any failure."""
    try:
        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            getCmd,
        )
    except Exception:  # noqa: BLE001
        return None
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, 161), timeout=timeout, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        error_indication, error_status, _error_index, var_binds = next(iterator)
        if error_indication or error_status:
            return None
        if not var_binds:
            return None
        _, value = var_binds[0]
        return value
    except Exception as e:  # noqa: BLE001
        logger.debug("SNMP get exception on %s: %s", oid, e)
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        # pysnmp OctetString prints with prettyPrint; bytes/str work too.
        s = str(value)
    except Exception:  # noqa: BLE001
        return ""
    return s.strip()


def _last_index(oid: str) -> str:
    """Return the trailing index of a tabular OID. ``...8.2.1.13.1.1`` → ``1.1``.

    The Standard Printer MIB indexes inputs with two integers
    (hrDeviceIndex, prtInputIndex). We use the last two components as the
    tray identity so a multi-engine press would still produce stable keys.
    """
    parts = oid.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return parts[-1] if parts else ""


def _convert_dim(raw: int | None, unit: int | None) -> float | None:
    """Convert prtInputMediaDim* to inches.

    Per RFC 3805:
      unit 2 → micrometres
      unit 3 → 10000ths of an inch
    """
    if raw is None or raw <= 0:
        return None
    if unit == 2:
        return round(raw / 25400.0, 3)  # µm → inches
    if unit == 3:
        return round(raw / 10000.0, 3)
    # Default to 10000ths-inch — Konica historically reports unit 3.
    return round(raw / 10000.0, 3)


# ───────────────────────── Public queries ─────────────────────────

def query_tray_state(host: str, timeout: float = 2.0) -> dict[str, dict]:
    """Return ``{tray_id: {paper_size, paper_type, level_pct, capacity, ...}}``.

    ``tray_id`` is the prtInputEntry index (e.g. ``"1.1"``, ``"1.2"``). Mapping
    to user-friendly tray names (T1..T5) is the caller's job — it depends on
    operator labelling, not the MIB.
    """
    descriptions = dict(_snmp_walk(host, OID_PRT_INPUT_DESCRIPTION, timeout))
    levels = dict(_snmp_walk(host, OID_PRT_INPUT_CURRENT_LEVEL, timeout))
    capacities = dict(_snmp_walk(host, OID_PRT_INPUT_MAX_CAPACITY, timeout))
    media_names = dict(_snmp_walk(host, OID_PRT_INPUT_MEDIA_NAME, timeout))
    feed_dims = dict(_snmp_walk(host, OID_PRT_INPUT_DIM_FEED, timeout))
    xfeed_dims = dict(_snmp_walk(host, OID_PRT_INPUT_DIM_XFEED, timeout))
    units = dict(_snmp_walk(host, OID_PRT_INPUT_DIM_UNIT, timeout))

    if not descriptions:
        return {}

    out: dict[str, dict] = {}
    for oid, desc in descriptions.items():
        idx = _last_index(oid)
        # Find sibling entries by matching the same index suffix.
        suffix = "." + idx

        def find(table: dict[str, Any]) -> Any:
            for o, v in table.items():
                if o.endswith(suffix):
                    return v
            return None

        level_raw = _to_int(find(levels))
        capacity = _to_int(find(capacities))
        unit = _to_int(find(units))
        feed = _to_int(find(feed_dims))
        xfeed = _to_int(find(xfeed_dims))
        media = _to_str(find(media_names))

        # Translate sentinel level codes to a human percentage.
        if level_raw is None:
            level_pct: int | None = None
            level_label = "unknown"
        elif level_raw == LEVEL_UNKNOWN:
            level_pct = None
            level_label = "unknown"
        elif level_raw == LEVEL_OTHER:
            level_pct = None
            level_label = "other"
        elif level_raw == LEVEL_REMAINING_AT_LEAST_ONE:
            level_pct = None
            level_label = "low"
        elif capacity and capacity > 0:
            level_pct = max(0, min(100, int(round(level_raw / capacity * 100))))
            level_label = (
                "empty" if level_pct == 0
                else "low" if level_pct < 25
                else "ok" if level_pct < 75
                else "full"
            )
        else:
            level_pct = None
            level_label = "unknown"

        feed_in = _convert_dim(feed, unit)
        xfeed_in = _convert_dim(xfeed, unit)

        paper_size = None
        if feed_in and xfeed_in:
            paper_size = f"{xfeed_in}×{feed_in} in"

        out[idx] = {
            "description": _to_str(desc),
            "paper_type": media or None,
            "paper_size": paper_size,
            "feed_in": feed_in,
            "xfeed_in": xfeed_in,
            "level_raw": level_raw,
            "level_pct": level_pct,
            "level_label": level_label,
            "capacity": capacity,
        }
    return out


def query_alerts(host: str, timeout: float = 2.0) -> list[dict]:
    """Walk prtAlertTable and return one dict per active alert.

    Empty list = no alerts OR SNMP unreachable. Distinguish via
    ``composite_state`` reachability.
    """
    severities = dict(_snmp_walk(host, OID_PRT_ALERT_SEVERITY, timeout))
    groups = dict(_snmp_walk(host, OID_PRT_ALERT_GROUP, timeout))
    codes = dict(_snmp_walk(host, OID_PRT_ALERT_CODE, timeout))
    descriptions = dict(_snmp_walk(host, OID_PRT_ALERT_DESCRIPTION, timeout))
    times = dict(_snmp_walk(host, OID_PRT_ALERT_TIME, timeout))

    if not severities:
        return []

    alerts: list[dict] = []
    for oid, sev in severities.items():
        idx = oid.rsplit(".", 1)[-1]
        suffix = "." + idx

        def find(table: dict[str, Any]) -> Any:
            for o, v in table.items():
                if o.endswith(suffix):
                    return v
            return None

        sev_int = _to_int(sev)
        group_int = _to_int(find(groups))
        code_int = _to_int(find(codes))
        desc = _to_str(find(descriptions))
        time_ticks = _to_int(find(times))

        alerts.append({
            "id": idx,
            "severity": ALERT_SEVERITY_MAP.get(sev_int or 0, "unknown"),
            "severity_code": sev_int,
            "group": ALERT_GROUP_MAP.get(group_int or 0, "unknown"),
            "group_code": group_int,
            "code": code_int,
            "description": desc,
            "uptime_ticks": time_ticks,
        })
    # Sort critical first, then warning, then everything else.
    sev_order = {"critical": 0, "warning": 1, "other": 2, "unknown": 3}
    alerts.sort(key=lambda a: sev_order.get(a["severity"], 9))
    return alerts


def query_lifetime_pagecount(host: str, timeout: float = 2.0) -> int | None:
    """Total pages printed since the press was new.

    Tries SNMP prtMarkerLifeCount first (fast, single GET). Falls back to PJL
    INFO PAGECOUNT over the existing 9100 socket for engines whose marker
    table doesn't expose a life count.
    """
    snmp_val = _to_int(_snmp_get(host, OID_PRT_MARKER_LIFE_COUNT, timeout))
    if snmp_val is not None and snmp_val > 0:
        return snmp_val

    # PJL fallback. Read-only — same UEL pattern as printer.probe_status.
    try:
        UEL = b"\x1B%-12345X"
        query = UEL + b"@PJL INFO PAGECOUNT\r\n" + UEL
        with socket.create_connection((host, settings.printer_raw_port), timeout=timeout) as s:
            s.sendall(query)
            s.settimeout(timeout)
            chunks: list[bytes] = []
            while True:
                try:
                    data = s.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
                if len(b"".join(chunks)) > 256:
                    break
        text = b"".join(chunks).decode("ascii", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.isdigit():
                return int(stripped)
            if "=" in stripped:
                _, val = stripped.split("=", 1)
                val = val.strip().strip('"')
                if val.isdigit():
                    return int(val)
    except (OSError, socket.error) as e:
        logger.debug("PJL pagecount fallback failed: %s", e)
    return None


def query_device_status(host: str, timeout: float = 2.0) -> dict[str, Any]:
    """Pull hrPrinterStatus + detected error state for the topbar pill."""
    status_raw = _to_int(_snmp_get(host, OID_HR_PRINTER_STATUS, timeout))
    err_raw = _snmp_get(host, OID_HR_PRINTER_DETECTED_ERROR_STATE, timeout)
    return {
        "printer_status": HR_PRINTER_STATUS_MAP.get(status_raw or 0, "unknown") if status_raw else None,
        "printer_status_code": status_raw,
        "detected_error_bits": _to_str(err_raw) if err_raw is not None else None,
    }


# ───────────────────────── Composite + cache ─────────────────────────

_CACHE_TTL_SECONDS = 15.0
_cache: dict[str, Any] = {"ts": 0.0, "host": None, "value": None}


def _tcp_reachable(host: str, port: int, timeout: float = 1.5) -> bool:
    """Cheap reachability check independent of SNMP availability."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.error):
        return False


def composite_state(host: str | None = None, *, force: bool = False) -> dict:
    """Single dict the UI consumes. 15s in-memory cache.

    Runs the SNMP walks + lifetime-pagecount + device-status in parallel.
    Falls back to the empty-but-reachable shape when SNMP is unavailable but
    the press still answers on 9100.
    """
    h = host or settings.printer_host
    now = time.monotonic()
    if (
        not force
        and _cache["host"] == h
        and _cache["value"] is not None
        and now - _cache["ts"] < _CACHE_TTL_SECONDS
    ):
        cached = dict(_cache["value"])
        cached["cached"] = True
        return cached

    pjl_reachable = _tcp_reachable(h, settings.printer_raw_port)
    snmp_supported = _pysnmp_available()

    if not pjl_reachable and not snmp_supported:
        result = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": h,
            "reachable": False,
            "snmp_available": False,
            "trays": {},
            "alerts": [],
            "lifetime_pagecount": None,
            "device_status": None,
            "error": "press unreachable on TCP/9100 and pysnmp not installed",
            "cached": False,
        }
        _cache.update({"ts": now, "host": h, "value": result})
        return result

    trays_data: dict[str, dict] = {}
    alerts_data: list[dict] = []
    pagecount: int | None = None
    device: dict[str, Any] = {}
    snmp_used = False
    error: str | None = None

    if snmp_supported:
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fut_trays = pool.submit(query_tray_state, h, 2.0)
                fut_alerts = pool.submit(query_alerts, h, 2.0)
                fut_pages = pool.submit(query_lifetime_pagecount, h, 2.0)
                fut_dev = pool.submit(query_device_status, h, 2.0)
                trays_data = fut_trays.result()
                alerts_data = fut_alerts.result()
                pagecount = fut_pages.result()
                device = fut_dev.result()
            snmp_used = bool(trays_data or alerts_data or device.get("printer_status"))
        except Exception as e:  # noqa: BLE001
            error = f"snmp query failed: {e}"
    else:
        # No pysnmp: at least try PJL pagecount.
        pagecount = query_lifetime_pagecount(h, 2.0)
        error = "pysnmp not installed; tray + alert state unavailable"

    result = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "host": h,
        "reachable": pjl_reachable or snmp_used,
        "snmp_available": snmp_supported,
        "snmp_used": snmp_used,
        "trays": trays_data,
        "alerts": alerts_data,
        "lifetime_pagecount": pagecount,
        "device_status": device or None,
        "error": error,
        "cached": False,
    }
    _cache.update({"ts": now, "host": h, "value": result})
    return result


def invalidate_cache() -> None:
    """Public hook for the /refresh endpoint."""
    _cache.update({"ts": 0.0, "host": None, "value": None})
