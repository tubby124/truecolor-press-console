"""Simple session auth.

Single-password admin gate. Default password is `qwerty123` (change via
PRESS_ADMIN_PASSWORD in .env). Designed to migrate cleanly to a proper
hashed-password store + per-user accounts when we deploy beyond the shop Mac.

Sessions are stored server-side in `~/.config/press-console/sessions.json` so
they survive a process restart. Cookie is HTTP-only, SameSite=Lax. We don't
set Secure flag yet because v1 is localhost only — flip when behind HTTPS.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, Request, Response, status

SESSION_COOKIE = "press_session"
SESSION_TTL = timedelta(days=30)
SESSIONS_FILE = Path.home() / ".config" / "press-console" / "sessions.json"
SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _hash(password: str) -> str:
    salt = os.environ.get("PRESS_PASSWORD_SALT", "true-color-press-console")
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def expected_hash() -> str:
    plain = os.environ.get("PRESS_ADMIN_PASSWORD", "qwerty123")
    return _hash(plain)


def _load_sessions() -> dict[str, dict]:
    if not SESSIONS_FILE.exists():
        return {}
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_sessions(sessions: dict[str, dict]) -> None:
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2))


def _purge_expired(sessions: dict[str, dict]) -> dict[str, dict]:
    now = datetime.utcnow()
    return {
        sid: s for sid, s in sessions.items()
        if datetime.fromisoformat(s["expires_at"]) > now
    }


def login(password: str, response: Response) -> bool:
    if _hash(password) != expected_hash():
        return False
    sessions = _purge_expired(_load_sessions())
    sid = secrets.token_urlsafe(32)
    sessions[sid] = {
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + SESSION_TTL).isoformat(),
        "user": "admin",
    }
    _save_sessions(sessions)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=sid,
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
    )
    return True


def logout(request: Request, response: Response) -> None:
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        sessions = _purge_expired(_load_sessions())
        sessions.pop(sid, None)
        _save_sessions(sessions)
    response.delete_cookie(SESSION_COOKIE)


def current_user(request: Request) -> str:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    sessions = _purge_expired(_load_sessions())
    session = sessions.get(sid)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
    return session["user"]
