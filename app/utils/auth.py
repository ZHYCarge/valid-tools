import base64
import secrets
from typing import Optional, Tuple


def parse_basic_auth(header_value: Optional[str]) -> Optional[Tuple[str, str]]:
    if not header_value:
        return None
    if not header_value.startswith("Basic "):
        return None
    token = header_value.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


def check_basic_auth(header_value: Optional[str], username: str, password: str) -> bool:
    parsed = parse_basic_auth(header_value)
    if not parsed:
        return False
    candidate_user, candidate_pass = parsed
    return secrets.compare_digest(candidate_user, username) and secrets.compare_digest(
        candidate_pass, password
    )
