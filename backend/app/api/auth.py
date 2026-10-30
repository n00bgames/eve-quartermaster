from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import delete as sa_delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_session_token, replace_account_password, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.services.permissions import BUILT_IN_ROLES, ROLE_RANK, SECTION_DEFINITIONS, disabled_sections, effective_permissions, role_exists, role_payload, role_rank, role_names, section_payload, set_disabled_sections, base_role_for, assigned_roles, assign_roles, assigned_base_roles, quartermaster_read_only
from app.services.user_accounts import retire_user_account
from app.services.esi_scope_policy import is_utility_user
from app.models import EsiSyncJob, EsiToken, EveCharacter, RecruitmentUserCapability, RoleDefinition, RoleSectionPermission, User, UserInvite, UserSectionPermission, UserRoleAssignment

router = APIRouter(prefix="/auth", tags=["auth"])
ROLES = BUILT_IN_ROLES
REMEMBER_ME_COOKIE = "eq_remember_session"


def set_remember_me_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    max_age = settings.remember_me_days * 24 * 60 * 60
    response.set_cookie(
        key=REMEMBER_ME_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.frontend_url.lower().startswith("https://"),
        samesite="lax",
        path=settings.api_prefix or "/",
    )


def clear_remember_me_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=REMEMBER_ME_COOKIE,
        path=settings.api_prefix or "/",
        httponly=True,
        secure=settings.frontend_url.lower().startswith("https://"),
        samesite="lax",
    )


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "password_reset_required": user.password_reset_required,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "roles": assigned_roles(user),
        "main_character_id": getattr(user, "main_character_id", None),
        "timezone": getattr(user, "timezone", None) or "UTC",
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_invite_usable(invite: UserInvite | None) -> bool:
    if invite is None or invite.accepted_at or invite.revoked_at:
        return False
    return invite.expires_at is None or invite.expires_at.replace(tzinfo=invite.expires_at.tzinfo or timezone.utc) > datetime.now(timezone.utc)


def serialize_invite(invite: UserInvite, include_status: bool = True) -> dict[str, Any]:
    payload = {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "roles": invite.roles_json or [invite.role],
        "created_by_display_name": invite.created_by_user.display_name if invite.created_by_user else None,
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "accepted_at": invite.accepted_at.isoformat() if invite.accepted_at else None,
        "revoked_at": invite.revoked_at.isoformat() if invite.revoked_at else None,
    }
    if include_status:
        payload["status"] = "accepted" if invite.accepted_at else "revoked" if invite.revoked_at else "expired" if not is_invite_usable(invite) else "pending"
    return payload


def admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(
            User.role.in_(("host", "admin")),
            User.password_hash.is_not(None),
            User.deleted_at.is_(None),
        )
    ) or 0


def host_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "host",
            User.password_hash.is_not(None),
            User.deleted_at.is_(None),
        )
    ) or 0


def require_host(user: User) -> None:
    if user.role != "host":
        raise HTTPException(status_code=403, detail="host role is required")


def protect_host_assignment(current_user: User, requested_role: str) -> None:
    if requested_role == "host" and current_user.role != "host":
        raise HTTPException(status_code=403, detail="Only a host can assign the host role")


def requested_account_roles(payload, current_user, db):
    roles = payload.get("roles", [payload.get("role") or "member"])
    if not isinstance(roles, list) or not roles or len(roles) > 32 or any(not isinstance(r, str) for r in roles):
        raise HTTPException(400, "Select one or more valid roles (at most 32)")
    roles = sorted(set(roles))
    for role in roles:
        if not role_exists(db, role):
            raise HTTPException(400, f"Unknown role: {role}")
        if base_role_for(db, role) == "host" and role_rank(current_user, db) < ROLE_RANK["host"]:
            raise HTTPException(403, "Only a host can assign the host role")
    return roles


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    bearer_token = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
    token = bearer_token or request.cookies.get(REMEMBER_ME_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in is required")
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid sign-in token") from exc
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    if payload.get("kind") is not None or payload.get("auth_version", 0) != user.auth_version or user.password_reset_required:
        raise HTTPException(401, "Your session has expired. Please sign in again or reset your password.")
    utility_path = request.url.path.rstrip("/").removeprefix(get_settings().api_prefix)
    quartermaster_utility = request.method == "POST" and (
        utility_path in {"/market/appraise", "/navigation/local-threat", "/navigation/local-threat/jobs", "/esi/ui/waypoint", "/client-links/preview", "/client-links/draft"}
        or re.fullmatch(r"/navigation/local-threat/jobs/[A-Za-z0-9_-]+/cancel", utility_path) is not None
        or re.fullmatch(r"/navigation/systems/\d+/objects/(?:sync|structures/\d+)", utility_path) is not None
    )
    quartermaster_utility = quartermaster_utility or (request.method == "PUT" and utility_path == "/auth/me/main-character")
    quartermaster_utility = quartermaster_utility or (request.method == "POST" and utility_path in {"/industry-reports", "/industry-reports/reports/delete"})
    quartermaster_utility = quartermaster_utility or (request.method == "PATCH" and utility_path == "/appearance/me") or (request.method == "PUT" and utility_path == "/appearance/me/banner")
    quartermaster_utility = quartermaster_utility or (request.method == "PATCH" and utility_path == "/auth/me")
    quartermaster_refresh = request.method == "POST" and request.url.path.rstrip("/") == f"{get_settings().api_prefix}/quartermaster-oversight/sync"
    if quartermaster_read_only(user, db) and request.method not in {"GET", "HEAD", "OPTIONS"} and not quartermaster_refresh and not quartermaster_utility:
        raise HTTPException(status_code=403, detail="Quartermaster is a view-only role")
    return user


def require_role(user: User, minimum_role: str, db: Session | None = None) -> None:
    if role_rank(user, db) < ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=403, detail=f"{minimum_role} role is required")


def can_view_all_characters(user: User, db: Session | None = None) -> bool:
    return role_rank(user, db) >= ROLE_RANK["director"]



def validate_timezone(value: str) -> str:
    timezone_name = value.strip()
    if not timezone_name or len(timezone_name) > 64:
        raise HTTPException(status_code=400, detail="A valid timezone is required")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Unknown timezone") from exc
    return timezone_name

def normalize_role_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", name).strip("_")


@router.get("/roles")
def list_roles(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_role(current_user, "admin", db)
    return role_payload(db)


@router.post("/roles")
def create_role(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin", db)
    raw_name = str(payload.get("name") or payload.get("display_name") or "")
    name = normalize_role_name(raw_name)
    display_name = str(payload.get("display_name") or raw_name).strip()
    base_role = str(payload.get("base_role") or "member")
    if not name or not display_name:
        raise HTTPException(status_code=400, detail="Role name is required")
    if name in BUILT_IN_ROLES or db.get(RoleDefinition, name):
        raise HTTPException(status_code=400, detail="Role already exists")
    if base_role not in BUILT_IN_ROLES or base_role in {"host", "admin"}:
        raise HTTPException(status_code=400, detail="Choose a non-admin base role")
    role = RoleDefinition(name=name, display_name=display_name, base_role=base_role, sort_order=100)
    db.add(role)
    db.commit()
    db.refresh(role)
    return {
        "name": role.name,
        "display_name": role.display_name,
        "base_role": role.base_role,
        "is_system": role.is_system,
        "sort_order": role.sort_order,
        "rank": ROLE_RANK.get(role.base_role, ROLE_RANK["member"]),
    }

@router.get("/sections/enabled")
def section_enabled_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin", db)
    return {"sections": section_payload(), "disabled_sections": sorted(disabled_sections(db))}


@router.patch("/sections/enabled")
def update_section_enabled_settings(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin", db)
    requested = payload.get("disabled_sections") or []
    if not isinstance(requested, list):
        raise HTTPException(status_code=400, detail="disabled_sections must be a list")
    set_disabled_sections(db, {str(section) for section in requested})
    db.commit()
    return {"sections": section_payload(), "disabled_sections": sorted(disabled_sections(db))}

@router.get("/permissions/effective")
def my_effective_permissions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.api.industry_reports import can_ships
    return {"ship_reports_available":can_ships(db,current_user),"sections": section_payload(), "permissions": effective_permissions(current_user, db), "read_only_quartermaster": quartermaster_read_only(current_user, db), "utility_only": is_utility_user(db, current_user)}


@router.get("/permissions")
def permission_matrix(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    role_rows = db.scalars(select(RoleSectionPermission)).all()
    user_rows = db.scalars(select(UserSectionPermission)).all()
    return {
        "sections": section_payload(),
        "roles": role_names(db),
        "role_permissions": [
            {"id": row.id, "role": row.role, "section": row.section, "can_view": row.can_view}
            for row in role_rows
        ],
        "user_permissions": [
            {"id": row.id, "user_id": row.user_id, "section": row.section, "can_view": row.can_view}
            for row in user_rows
        ],
    }


@router.patch("/permissions/roles/{role}")
def update_role_permission(role: str, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    section = str(payload.get("section") or "").strip()
    if not role_exists(db, role) or section not in SECTION_DEFINITIONS:
        raise HTTPException(status_code=400, detail="Unknown role or section")
    existing = db.scalar(select(RoleSectionPermission).where(RoleSectionPermission.role == role, RoleSectionPermission.section == section))
    if payload.get("can_view") is None:
        if existing:
            db.delete(existing)
            db.commit()
        return {"role": role, "section": section, "can_view": None}
    if existing is None:
        existing = RoleSectionPermission(role=role, section=section, can_view=bool(payload["can_view"]))
        db.add(existing)
    else:
        existing.can_view = bool(payload["can_view"])
    db.commit()
    db.refresh(existing)
    return {"id": existing.id, "role": existing.role, "section": existing.section, "can_view": existing.can_view}


@router.patch("/permissions/users/{user_id}")
def update_user_permission(user_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    section = str(payload.get("section") or "").strip()
    if section not in SECTION_DEFINITIONS:
        raise HTTPException(status_code=400, detail="Unknown section")
    if db.scalar(select(User.id).where(User.id == user_id, User.deleted_at.is_(None))) is None:
        raise HTTPException(status_code=404, detail="User was not found")
    existing = db.scalar(select(UserSectionPermission).where(UserSectionPermission.user_id == user_id, UserSectionPermission.section == section))
    if payload.get("can_view") is None:
        if existing:
            db.delete(existing)
            db.commit()
        return {"user_id": user_id, "section": section, "can_view": None}
    if existing is None:
        existing = UserSectionPermission(user_id=user_id, section=section, can_view=bool(payload["can_view"]))
        db.add(existing)
    else:
        existing.can_view = bool(payload["can_view"])
    db.commit()
    db.refresh(existing)
    return {"id": existing.id, "user_id": existing.user_id, "section": existing.section, "can_view": existing.can_view}

@router.get("/bootstrap")
def bootstrap_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"needs_admin": admin_count(db) == 0, "roles": role_names(db)}


@router.post("/bootstrap")
def bootstrap_admin(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    if admin_count(db):
        raise HTTPException(status_code=400, detail="Initial host already exists")
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    display_name = str(payload.get("display_name") or email).strip()
    if not email or not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Email and an 8+ character password are required")
    user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or user.deleted_at is not None:
        user = User(email=email, display_name=display_name, role="host")
        db.add(user)
    user.display_name = display_name
    user.role = "host"
    user.password_hash = hash_password(password)
    db.commit()
    db.refresh(user)
    token = create_session_token(user, {"role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}


@router.post("/login")
def login(payload: dict[str, Any], response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.password_reset_required:
        raise HTTPException(403, "A password reset is required. Use your recovery link or Forgot password.")
    remember_me = payload.get("remember_me") is True
    settings = get_settings()
    token = create_session_token(
        user,
        {"role": user.role, "remember_me": remember_me},
        expires_minutes=settings.remember_me_days * 24 * 60 if remember_me else None,
    )
    if remember_me:
        set_remember_me_cookie(response, token)
    else:
        clear_remember_me_cookie(response)
    return {
        "access_token": None if remember_me else token,
        "token_type": "cookie" if remember_me else "bearer",
        "remembered": remember_me,
        "user": serialize_user(user),
    }


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    clear_remember_me_cookie(response)
    return {"status": "signed_out"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return serialize_user(current_user)



@router.patch("/me")
def update_me(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if "main_character_id" in payload:
        from app.services.report_identity import owned_characters
        selected = payload["main_character_id"]
        if selected is not None and (type(selected) is not int or selected not in {c.character_id for c in owned_characters(db, current_user)}):
            raise HTTPException(422, "Choose one of your currently linked characters")
        current_user.main_character_id = selected
    if payload.get("display_name"):
        display_name = str(payload["display_name"]).strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="Display name is required")
        current_user.display_name = display_name

    if payload.get("email"):
        email = str(payload["email"]).strip().lower()
        current_password = str(payload.get("current_password") or "")
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="A valid email is required")
        if not current_user.password_hash or not verify_password(current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is required to change email")
        existing = db.scalar(select(User).where(User.email == email, User.id != current_user.id))
        if existing:
            raise HTTPException(status_code=400, detail="Email is already in use")
        current_user.email = email

    if "timezone" in payload:
        current_user.timezone = validate_timezone(str(payload.get("timezone") or ""))

    if payload.get("password"):
        current_password = str(payload.get("current_password") or "")
        new_password = str(payload["password"])
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        if not current_user.password_hash or not verify_password(current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is required to change password")
        replace_account_password(db, current_user, new_password)

    db.commit()
    db.refresh(current_user)
    return serialize_user(current_user)

@router.get("/users")
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_role(current_user, "admin")
    users = db.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.display_name)).all()
    return [serialize_user(user) for user in users]


@router.post("/users")
def create_user(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    display_name = str(payload.get("display_name") or email).strip()
    roles = requested_account_roles(payload, current_user, db)
    role = roles[0]
    if not email or not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Email and an 8+ character password are required")
    if db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None))):
        raise HTTPException(status_code=400, detail="Email is already in use")
    user = User(email=email, display_name=display_name, role=role, password_hash=hash_password(password))
    db.add(user)
    assign_roles(db, user, roles)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User was not found")
    if "host" in assigned_base_roles(user, db) and role_rank(current_user, db) < ROLE_RANK["host"]:
        raise HTTPException(403, "Only a host can manage another host account")
    if payload.get("display_name"):
        user.display_name = str(payload["display_name"]).strip()
    if "role" in payload or "roles" in payload:
        roles = requested_account_roles(payload, current_user, db)
        old_bases = assigned_base_roles(user, db)
        new_bases = {base_role_for(db, role) for role in roles}
        if "host" in old_bases and role_rank(current_user, db) < ROLE_RANK["host"]:
            raise HTTPException(403, "Only a host can manage another host account")
        if "host" in old_bases and "host" not in new_bases and host_count(db) <= 1:
            raise HTTPException(400, "At least one host account is required")
        if old_bases & {"host", "admin"} and not new_bases & {"host", "admin"} and admin_count(db) <= 1:
            raise HTTPException(400, "At least one host or admin account is required")
        assign_roles(db, user, roles)
    if payload.get("password"):
        password = str(payload["password"])
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        replace_account_password(db, user, password)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own signed-in account")
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User was not found")
    if user.role == "host" and current_user.role != "host":
        raise HTTPException(status_code=403, detail="Only a host can delete another host account")
    if user.role == "host" and host_count(db) <= 1:
        raise HTTPException(status_code=400, detail="At least one host account is required")
    if user.role in {"host", "admin"} and admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="At least one host or admin account is required")

    token_ids = db.scalars(select(EsiToken.id).where(EsiToken.user_id == user_id)).all()
    if token_ids:
        db.execute(update(EsiSyncJob).where(EsiSyncJob.token_id.in_(token_ids)).values(token_id=None))
    db.execute(sa_delete(EsiToken).where(EsiToken.user_id == user_id))
    db.execute(sa_delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id))
    db.execute(sa_delete(UserSectionPermission).where(UserSectionPermission.user_id == user_id))
    db.execute(sa_delete(RecruitmentUserCapability).where(RecruitmentUserCapability.user_id == user_id))
    db.execute(update(EveCharacter).where(EveCharacter.owner_user_id == user_id).values(owner_user_id=None))
    retire_user_account(user)
    db.commit()
    return {"status": "deleted", "user_id": user_id}


@router.get("/invites")
def list_invites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_role(current_user, "admin")
    invites = db.scalars(select(UserInvite).order_by(UserInvite.created_at.desc(), UserInvite.id.desc())).all()
    return [serialize_invite(invite) for invite in invites]


@router.post("/invites")
def create_invite(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    email = str(payload.get("email", "")).strip().lower()
    roles = requested_account_roles(payload, current_user, db)
    role = min(roles, key=lambda r: (-role_rank(r, db), r))
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if db.scalar(select(User).where(User.email == email, User.password_hash.is_not(None))):
        raise HTTPException(status_code=400, detail="A user already exists for that email")

    token = secrets.token_urlsafe(32)
    invite = UserInvite(email=email, role=role, roles_json=roles, token_hash=hash_invite_token(token), created_by_user_id=current_user.id)
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # Only the raw token can create the account. The database stores a hash so
    # an exported database cannot be used as an invite link list.
    invite_url = f"{get_settings().frontend_url.rstrip('/')}/?invite={token}"
    payload = serialize_invite(invite)
    payload["invite_url"] = invite_url
    return payload


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    invite = db.get(UserInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite was not found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Accepted invites cannot be revoked")
    invite.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invite)
    return serialize_invite(invite)


@router.get("/invites/{token}")
def inspect_invite(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    invite = db.scalar(select(UserInvite).where(UserInvite.token_hash == hash_invite_token(token)))
    if not is_invite_usable(invite):
        raise HTTPException(status_code=404, detail="Invite is invalid or expired")
    return {"email": invite.email, "role": invite.role, "roles": invite.roles_json or [invite.role], "expires_at": invite.expires_at.isoformat() if invite.expires_at else None}


def claim_invite(db, invite):
    at = datetime.now(timezone.utc)
    claimed = db.execute(update(UserInvite).where(UserInvite.id == invite.id,
        UserInvite.accepted_at.is_(None), UserInvite.revoked_at.is_(None),
        (UserInvite.expires_at.is_(None)) | (UserInvite.expires_at > at)).values(accepted_at=at).execution_options(synchronize_session="fetch"))
    if claimed.rowcount != 1:
        raise HTTPException(409, "Invite is no longer available")


@router.post("/invites/{token}/accept")
def accept_invite(token: str, payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    invite = db.scalar(select(UserInvite).where(UserInvite.token_hash == hash_invite_token(token)))
    if not is_invite_usable(invite):
        raise HTTPException(status_code=404, detail="Invite is invalid or expired")

    claim_invite(db, invite)
    display_name = str(payload.get("display_name") or invite.email).strip()
    password = str(payload.get("password", ""))
    if not display_name or not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Display name and an 8+ character password are required")

    user = db.scalar(select(User).where(User.email == invite.email))
    if user and user.password_hash:
        raise HTTPException(status_code=400, detail="An account already exists for this invite email")
    if user is None or user.deleted_at is not None:
        user = User(email=invite.email, display_name=display_name, role=invite.role)
        db.add(user)
        db.flush()
    user.display_name = display_name
    invite_roles = invite.roles_json or [invite.role]
    if any(not role_exists(db, r) for r in invite_roles):
        raise HTTPException(400, "An invited role no longer exists; request a new invite")
    assign_roles(db, user, invite_roles)
    user.password_hash = hash_password(password)
    invite.accepted_at = datetime.now(timezone.utc)
    invite.accepted_by_user_id = user.id
    db.commit()
    db.refresh(user)
    token = create_session_token(user, {"role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}










@router.get("/me/characters")
def own_profile_characters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.report_identity import owned_characters
    return {"main_character_id": current_user.main_character_id,
            "characters": [{"character_id": c.character_id, "name": c.name} for c in owned_characters(db, current_user)]}


@router.put("/me/main-character")
def set_profile_main(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if set(payload) != {"main_character_id"}:
        raise HTTPException(422, "Provide main_character_id only")
    return update_me(payload, current_user, db)
