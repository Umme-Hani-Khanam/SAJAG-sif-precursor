"""Password and opaque-session authentication.

Only SHA-256 token digests are persisted. Passwords use memory-hard scrypt with a
per-password random salt; neither credentials nor bearer tokens are logged/stored.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import AuthSession, User
from services.roles import ROLES


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N, SCRYPT_R, SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = encoded.split("$", 5)
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=base64.urlsafe_b64decode(salt.encode()),
            n=int(n), r=int(r), p=int(p), dklen=32,
        )
        return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False


def create_user(
    db: Session, *, name: str, email: str, username: str, password: str,
    role: str, site_scope: list[str] | None = None, active: bool = True,
) -> User:
    normalized_role = role.strip().upper()
    if normalized_role not in ROLES:
        raise ValueError(f"Unknown application role: {normalized_role}")
    normalized_email = email.strip().lower()
    normalized_username = username.strip().lower()
    if db.query(User).filter(or_(User.email == normalized_email, User.username == normalized_username)).first():
        raise ValueError("A user with that email or username already exists.")
    user = User(
        user_id=f"USR-{uuid4().hex[:16].upper()}", name=name.strip(), email=normalized_email,
        username=normalized_username, password_hash=hash_password(password), role=normalized_role,
        site_scope=json.dumps(sorted({item.strip() for item in (site_scope or []) if item.strip()})),
        active=active,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, identifier: str, password: str) -> User:
    value = identifier.strip().lower()
    user = db.query(User).filter(or_(User.email == value, User.username == value)).first()
    # Always do password work for unknown users to reduce account-enumeration timing signal.
    if user is None:
        hashlib.scrypt(password.encode(), salt=b"SAJAG-invalid-user", n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")
    if not user.active:
        raise HTTPException(status_code=403, detail="This user account is inactive.")
    user.last_login = datetime.now(timezone.utc)
    return user


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    minutes = max(5, min(int(os.getenv("SESSION_TTL_MINUTES", "60")), 1440))
    session = AuthSession(
        session_id=f"SES-{uuid4().hex[:16].upper()}", user_id=user.user_id,
        token_hash=token_digest(token), expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
    )
    db.add(session)
    db.flush()
    return token, session


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_session(db: Session, token: str) -> tuple[AuthSession, User]:
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_digest(token)).first()
    now = datetime.now(timezone.utc)
    if session is None or session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Authentication session is invalid.")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now:
        raise HTTPException(status_code=401, detail="Authentication session has expired.")
    if not session.user.active:
        raise HTTPException(status_code=403, detail="This user account is inactive.")
    return session, session.user


def revoke_session(db: Session, token: str) -> None:
    session, _ = resolve_session(db, token)
    session.revoked_at = datetime.now(timezone.utc)
    db.flush()


def safe_user(user: User) -> dict:
    try:
        sites = json.loads(user.site_scope or "[]")
    except json.JSONDecodeError:
        sites = []
    return {
        "user_id": user.user_id, "name": user.name, "email": user.email,
        "username": user.username, "role": user.role, "site_scope": sites,
        "active": bool(user.active), "created_at": user.created_at, "last_login": user.last_login,
    }
