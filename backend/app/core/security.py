from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
import jwt
from passlib.context import CryptContext
from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# Higher rank includes all lower permissions.
_RANK = {Role.VIEWER: 1, Role.ANALYST: 2, Role.ADMIN: 3}


def has_role(user_role: str, required: Role) -> bool:
    return _RANK[Role(user_role)] >= _RANK[required]


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, hashed: str) -> bool:
    return _pwd.verify(p, hashed)


def _token(sub: str, kind: str, delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "type": kind, "iat": now, "exp": now + delta, **(extra or {})}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: int, role: str) -> str:
    return _token(str(user_id), "access", timedelta(minutes=get_settings().access_token_minutes), {"role": role})


def create_refresh_token(user_id: int) -> str:
    return _token(str(user_id), "refresh", timedelta(days=get_settings().refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    s = get_settings()
    data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])  # raises jwt.PyJWTError
    if data.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return data
