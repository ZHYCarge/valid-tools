import secrets
import time
from typing import Dict, Optional

SESSION_TTL_SECONDS = 60 * 60 * 12
_SESSIONS: Dict[str, Dict[str, object]] = {}


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = {"expires_at": time.time() + SESSION_TTL_SECONDS, "user": username}
    return token


def get_session(token: Optional[str]) -> Optional[Dict[str, object]]:
    if not token:
        return None
    session = _SESSIONS.get(token)
    if not session:
        return None
    if session["expires_at"] < time.time():
        _SESSIONS.pop(token, None)
        return None
    return session


def delete_session(token: Optional[str]) -> None:
    if not token:
        return
    _SESSIONS.pop(token, None)
