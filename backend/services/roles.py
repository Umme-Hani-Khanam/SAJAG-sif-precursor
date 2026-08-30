import json
import os
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db


ROLES = (
    "WORKER",
    "SITE_SUPERVISOR",
    "HSE_OFFICER",
    "HSE_MANAGER",
    "AUDITOR",
    "ADMIN",
)

PERMISSIONS = {
    "WORKER": {"SUBMIT_REPORT", "VIEW_BASIC", "CAPA_EVIDENCE"},
    "SITE_SUPERVISOR": {"SUBMIT_REPORT", "VIEW_SITE", "CAPA_ASSIGN", "CAPA_UPDATE", "CAPA_EVIDENCE", "ALERT_VIEW"},
    "HSE_OFFICER": {"SUBMIT_REPORT", "VIEW_ALL", "REVIEW_ANALYSIS", "CAPA_CREATE", "CAPA_ASSIGN", "CAPA_UPDATE", "CAPA_EVIDENCE", "CAPA_VERIFY", "AUDIT_VIEW", "KNOWLEDGE_MANAGE", "ALERT_VIEW", "ALERT_DECIDE"},
    "HSE_MANAGER": {"SUBMIT_REPORT", "VIEW_ALL", "REVIEW_ANALYSIS", "CAPA_CREATE", "CAPA_ASSIGN", "CAPA_UPDATE", "CAPA_EVIDENCE", "CAPA_VERIFY", "AUDIT_VIEW", "KNOWLEDGE_MANAGE", "ALERT_VIEW", "ALERT_DECIDE", "ANALYTICS_ADVANCED"},
    "AUDITOR": {"VIEW_ALL", "AUDIT_VIEW", "ALERT_VIEW"},
    "ADMIN": {"*"},
}


@dataclass(frozen=True)
class Actor:
    name: str
    role: str
    user_id: str | None = None
    site_scope: tuple[str, ...] = field(default_factory=tuple)
    authenticated: bool = False
    demo: bool = False


def get_actor(
    authorization: str | None = Header(default=None),
    x_actor_name: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Actor:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Use an Authorization: Bearer token header.")
        from services.auth import resolve_session

        _, user = resolve_session(db, token)
        try:
            sites = tuple(json.loads(user.site_scope or "[]"))
        except json.JSONDecodeError:
            sites = ()
        return Actor(user.name, user.role, user.user_id, sites, True, False)

    if os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}:
        role = str(x_actor_role or "HSE_MANAGER").strip().upper()
        if role not in ROLES:
            raise HTTPException(status_code=400, detail=f"Unknown application role: {role}")
        name = str(x_actor_name or "Demo HSE Manager").strip() or "Demo User"
        demo_scope = tuple(item.strip() for item in os.getenv("DEMO_SITE_SCOPE", "*").split(",") if item.strip())
        return Actor(name, role, None, demo_scope, False, True)
    raise HTTPException(status_code=401, detail="Authentication is required.")


def has_permission(actor: Actor, permission: str) -> bool:
    permissions = PERMISSIONS.get(actor.role, set())
    return "*" in permissions or permission in permissions


def require(actor: Actor, permission: str) -> None:
    if not has_permission(actor, permission):
        raise HTTPException(
            status_code=403,
            detail=f"Role {actor.role} does not have permission {permission}.",
        )


def permission_matrix() -> dict[str, list[str]]:
    return {role: sorted(values) for role, values in PERMISSIONS.items()}


def can_access_site(actor: Actor, site: str | None) -> bool:
    if actor.role == "ADMIN" or "*" in actor.site_scope:
        return True
    normalized = str(site or "").strip().casefold()
    return bool(normalized) and normalized in {item.strip().casefold() for item in actor.site_scope}


def require_site(actor: Actor, site: str | None) -> None:
    if not can_access_site(actor, site):
        raise HTTPException(status_code=403, detail="The requested site is outside this account's authorized scope.")


def scoped_sites(actor: Actor) -> tuple[str, ...] | None:
    """Return None for unrestricted actors, otherwise the normalized allowed sites."""
    if actor.role == "ADMIN" or "*" in actor.site_scope:
        return None
    return actor.site_scope
