"""Stub tests for press_state.py.

We can't unit-test against a real SNMP target in CI, so these tests mock out
the two underlying pysnmp helpers (`_snmp_walk`, `_snmp_get`) and the TCP
reachability probe. They cover:

  - tray-level percentage math + sentinel handling (RFC 3805 −1/−2/−3)
  - alert sort order + severity mapping
  - PJL pagecount fallback when SNMP returns 0/None
  - composite_state cache semantics + graceful degradation paths

Run with: ``python -m pytest tests/test_press_state.py``
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from backend import press_state


# ───────────────────────── Tray math ─────────────────────────

def test_tray_state_normal_percentages():
    """Walks return aligned by suffix; level becomes a clean percentage."""

    def fake_walk(host, base_oid, timeout, community="public"):
        if base_oid == press_state.OID_PRT_INPUT_DESCRIPTION:
            return [
                ("1.3.6.1.2.1.43.8.2.1.13.1.1", "Tray 1"),
                ("1.3.6.1.2.1.43.8.2.1.13.1.2", "Tray 2"),
            ]
        if base_oid == press_state.OID_PRT_INPUT_CURRENT_LEVEL:
            return [
                ("1.3.6.1.2.1.43.8.2.1.10.1.1", 250),  # half of 500
                ("1.3.6.1.2.1.43.8.2.1.10.1.2", 0),    # empty
            ]
        if base_oid == press_state.OID_PRT_INPUT_MAX_CAPACITY:
            return [
                ("1.3.6.1.2.1.43.8.2.1.9.1.1", 500),
                ("1.3.6.1.2.1.43.8.2.1.9.1.2", 500),
            ]
        if base_oid == press_state.OID_PRT_INPUT_MEDIA_NAME:
            return [
                ("1.3.6.1.2.1.43.8.2.1.12.1.1", "Plain"),
                ("1.3.6.1.2.1.43.8.2.1.12.1.2", "Cardstock"),
            ]
        if base_oid == press_state.OID_PRT_INPUT_DIM_FEED:
            return [
                ("1.3.6.1.2.1.43.8.2.1.4.1.1", 110000),  # 11.0 in
                ("1.3.6.1.2.1.43.8.2.1.4.1.2", 110000),
            ]
        if base_oid == press_state.OID_PRT_INPUT_DIM_XFEED:
            return [
                ("1.3.6.1.2.1.43.8.2.1.5.1.1", 85000),   # 8.5 in
                ("1.3.6.1.2.1.43.8.2.1.5.1.2", 85000),
            ]
        if base_oid == press_state.OID_PRT_INPUT_DIM_UNIT:
            return [
                ("1.3.6.1.2.1.43.8.2.1.3.1.1", 3),       # 10000ths-of-inch
                ("1.3.6.1.2.1.43.8.2.1.3.1.2", 3),
            ]
        return []

    with patch.object(press_state, "_snmp_walk", side_effect=fake_walk):
        result = press_state.query_tray_state("172.16.1.149")

    assert "1.1" in result and "1.2" in result
    assert result["1.1"]["level_pct"] == 50
    assert result["1.1"]["level_label"] == "ok"
    assert result["1.1"]["paper_size"] == "8.5×11.0 in"
    assert result["1.2"]["level_pct"] == 0
    assert result["1.2"]["level_label"] == "empty"


def test_tray_state_unknown_sentinel():
    """RFC 3805 sentinel −2 must surface as 'unknown' rather than a fake 0%."""

    def fake_walk(host, base_oid, timeout, community="public"):
        if base_oid == press_state.OID_PRT_INPUT_DESCRIPTION:
            return [("1.3.6.1.2.1.43.8.2.1.13.1.1", "Tray 1")]
        if base_oid == press_state.OID_PRT_INPUT_CURRENT_LEVEL:
            return [("1.3.6.1.2.1.43.8.2.1.10.1.1", press_state.LEVEL_UNKNOWN)]
        return []

    with patch.object(press_state, "_snmp_walk", side_effect=fake_walk):
        result = press_state.query_tray_state("host")
    assert result["1.1"]["level_pct"] is None
    assert result["1.1"]["level_label"] == "unknown"


def test_tray_state_low_sentinel():
    """Sentinel −3 ('at least one sheet remaining') maps to 'low'."""

    def fake_walk(host, base_oid, timeout, community="public"):
        if base_oid == press_state.OID_PRT_INPUT_DESCRIPTION:
            return [("1.3.6.1.2.1.43.8.2.1.13.1.1", "Tray 1")]
        if base_oid == press_state.OID_PRT_INPUT_CURRENT_LEVEL:
            return [("1.3.6.1.2.1.43.8.2.1.10.1.1", press_state.LEVEL_REMAINING_AT_LEAST_ONE)]
        return []

    with patch.object(press_state, "_snmp_walk", side_effect=fake_walk):
        result = press_state.query_tray_state("host")
    assert result["1.1"]["level_label"] == "low"


# ───────────────────────── Alerts ─────────────────────────

def test_alerts_sort_critical_first():
    def fake_walk(host, base_oid, timeout, community="public"):
        if base_oid == press_state.OID_PRT_ALERT_SEVERITY:
            return [
                ("1.3.6.1.2.1.43.18.1.1.2.1", 4),  # warning
                ("1.3.6.1.2.1.43.18.1.1.2.2", 3),  # critical
                ("1.3.6.1.2.1.43.18.1.1.2.3", 1),  # other
            ]
        if base_oid == press_state.OID_PRT_ALERT_GROUP:
            return [
                ("1.3.6.1.2.1.43.18.1.1.4.1", 8),
                ("1.3.6.1.2.1.43.18.1.1.4.2", 6),
                ("1.3.6.1.2.1.43.18.1.1.4.3", 5),
            ]
        if base_oid == press_state.OID_PRT_ALERT_CODE:
            return [
                ("1.3.6.1.2.1.43.18.1.1.7.1", 1001),
                ("1.3.6.1.2.1.43.18.1.1.7.2", 1002),
                ("1.3.6.1.2.1.43.18.1.1.7.3", 1003),
            ]
        if base_oid == press_state.OID_PRT_ALERT_DESCRIPTION:
            return [
                ("1.3.6.1.2.1.43.18.1.1.8.1", "Tray 2 empty"),
                ("1.3.6.1.2.1.43.18.1.1.8.2", "Cover open"),
                ("1.3.6.1.2.1.43.18.1.1.8.3", "Info"),
            ]
        if base_oid == press_state.OID_PRT_ALERT_TIME:
            return [
                ("1.3.6.1.2.1.43.18.1.1.9.1", 12345),
                ("1.3.6.1.2.1.43.18.1.1.9.2", 12346),
                ("1.3.6.1.2.1.43.18.1.1.9.3", 12347),
            ]
        return []

    with patch.object(press_state, "_snmp_walk", side_effect=fake_walk):
        alerts = press_state.query_alerts("host")
    assert [a["severity"] for a in alerts] == ["critical", "warning", "other"]
    assert alerts[0]["group"] == "cover"
    assert alerts[1]["group"] == "input"


# ───────────────────────── Lifetime pagecount ─────────────────────────

def test_lifetime_pagecount_uses_snmp_when_available():
    with patch.object(press_state, "_snmp_get", return_value=391394):
        assert press_state.query_lifetime_pagecount("host") == 391394


def test_lifetime_pagecount_falls_back_to_pjl():
    """When SNMP returns None, we read the existing 9100 socket via PJL."""

    class FakeSocket:
        def __init__(self):
            self._sent = b""
            self._reads = [b'@PJL INFO PAGECOUNT\r\nPAGECOUNT=391394\r\n', b""]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def sendall(self, data):
            self._sent = data

        def settimeout(self, _t):
            pass

        def recv(self, _n):
            return self._reads.pop(0) if self._reads else b""

    with patch.object(press_state, "_snmp_get", return_value=None), \
         patch("backend.press_state.socket.create_connection", return_value=FakeSocket()):
        assert press_state.query_lifetime_pagecount("host") == 391394


# ───────────────────────── Composite + cache ─────────────────────────

def test_composite_state_unreachable():
    press_state.invalidate_cache()
    with patch.object(press_state, "_tcp_reachable", return_value=False), \
         patch.object(press_state, "_pysnmp_available", return_value=False):
        result = press_state.composite_state("172.16.1.149")
    assert result["reachable"] is False
    assert result["error"]
    assert result["trays"] == {}


def test_composite_state_cache_hit():
    press_state.invalidate_cache()
    with patch.object(press_state, "_tcp_reachable", return_value=True), \
         patch.object(press_state, "_pysnmp_available", return_value=False), \
         patch.object(press_state, "query_lifetime_pagecount", return_value=391394):
        first = press_state.composite_state("h")
        second = press_state.composite_state("h")
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["lifetime_pagecount"] == 391394


def test_composite_state_force_bypasses_cache():
    press_state.invalidate_cache()
    with patch.object(press_state, "_tcp_reachable", return_value=True), \
         patch.object(press_state, "_pysnmp_available", return_value=False), \
         patch.object(press_state, "query_lifetime_pagecount", return_value=1):
        press_state.composite_state("h")
        result = press_state.composite_state("h", force=True)
    assert result["cached"] is False


def test_composite_state_pysnmp_missing_still_returns_pagecount():
    press_state.invalidate_cache()
    with patch.object(press_state, "_tcp_reachable", return_value=True), \
         patch.object(press_state, "_pysnmp_available", return_value=False), \
         patch.object(press_state, "query_lifetime_pagecount", return_value=391394):
        result = press_state.composite_state("h")
    assert result["reachable"] is True
    assert result["snmp_available"] is False
    assert result["lifetime_pagecount"] == 391394
    assert result["trays"] == {}


# Auto-clear cache between tests so order doesn't matter.
@pytest.fixture(autouse=True)
def _clear_press_state_cache():
    press_state.invalidate_cache()
    yield
    press_state.invalidate_cache()
    # Belt-and-braces: ensure no stale monotonic time leaks into TTL checks.
    _ = time.monotonic()
