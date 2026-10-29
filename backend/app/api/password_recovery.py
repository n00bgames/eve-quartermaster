"""Recovery tokens never appear in database plaintext, URLs sent to the API, or logs."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import logging
import secrets
import smtplib
import ssl
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from app.api.auth import clear_remember_me_cookie, get_current_user, require_role
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import AuditEvent, PasswordReset, RecoveryRateLimit, User
from app.services.permissions import assigned_base_roles, role_rank, ROLE_RANK

router = APIRouter(prefix="/auth", tags=["password recovery"])
GENERIC = {"message": "If this account can receive recovery email, a reset link will arrive shortly. Otherwise, contact your EQM administrator."}
INVALID = "This reset link is invalid or expired. Request a new link."

class RecoveryRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

class ResetRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=8, max_length=1024)

class AdminRecoveryRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    require_reset: bool = False

def limit(db, value, maximum):
    """Shared fixed windows; no raw email/IP stored and no process-local bypass."""
    now = datetime.now(timezone.utc)
    window = int(now.timestamp()) // 900
    key = hmac.new(get_settings().auth_secret_key.encode(), f"{window}:{value}".encode(), hashlib.sha256).hexdigest()
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    db.execute(insert(RecoveryRateLimit).values(bucket=key, attempts=0, expires_at=now+timedelta(minutes=30)).on_conflict_do_nothing(index_elements=["bucket"]))
    result = db.execute(update(RecoveryRateLimit).where(RecoveryRateLimit.bucket == key, RecoveryRateLimit.attempts < maximum).values(attempts=RecoveryRateLimit.attempts+1))
    db.execute(delete(RecoveryRateLimit).execution_options(synchronize_session="fetch").where(RecoveryRateLimit.expires_at < now))
    db.execute(delete(PasswordReset).execution_options(synchronize_session="fetch").where(PasswordReset.expires_at < now-timedelta(days=1)))
    db.commit()
    return result.rowcount == 1

def issue(db, user):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc)+timedelta(minutes=get_settings().password_reset_minutes)
    # A new link supersedes earlier links. Requests alone never lock an account.
    db.execute(delete(PasswordReset).execution_options(synchronize_session="fetch").where(PasswordReset.user_id == user.id))
    db.add(PasswordReset(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
        auth_version=user.auth_version, email=user.email, expires_at=expires))
    base = urlsplit(get_settings().frontend_url)
    if base.scheme not in {"http","https"} or not base.netloc or base.username or base.password:
        raise HTTPException(503, "Recovery URL is not configured correctly")
    link = urlunsplit((base.scheme, base.netloc, base.path.rstrip('/')+'/', '', 'reset-password/'+token))
    return link, expires

def deliver(email, link):
    settings = get_settings()
    try:
        message = EmailMessage()
        message["Subject"] = "Reset your EVE Quartermaster password"
        message["From"] = settings.smtp_from
        message["To"] = email
        message.set_content(f"A password reset was requested for your EQM account.\n\n{link}\n\nThis single-use link expires in {settings.password_reset_minutes} minutes. If you did not request it, ignore this email. Your password has not changed.")
        context = ssl.create_default_context()
        client = smtplib.SMTP_SSL(settings.smtp_host,settings.smtp_port,timeout=10,context=context) if settings.smtp_ssl else smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=10)
        with client:
            if not settings.smtp_ssl:
                client.starttls(context=context)
            if settings.smtp_username:
                client.login(settings.smtp_username,settings.smtp_password)
            client.send_message(message)
    except Exception:
        # SMTP exception bodies can contain account details; never log them.
        logging.getLogger(__name__).warning("Password recovery email delivery failed; check SMTP configuration.")

@router.post("/password-recovery", status_code=202)
def request_recovery(payload: RecoveryRequest, request: Request, response: Response, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    email = payload.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    if not limit(db, "request-ip:"+ip, 10):
        return GENERIC
    if not limit(db, "email:"+email, 2):
        return GENERIC
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None), User.password_hash.is_not(None)))
    if user and settings.smtp_host and settings.smtp_from:
        try:
            link, _ = issue(db, user)
            db.commit()
        except HTTPException:
            db.rollback()
            logging.getLogger(__name__).warning("Password recovery URL configuration is invalid.")
        else:
            tasks.add_task(deliver, email, link)
    return GENERIC

@router.post("/password-reset")
def reset_password(payload: ResetRequest, response: Response, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    hashed = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hashed, PasswordReset.consumed_at.is_(None), PasswordReset.expires_at > now))
    if not reset:
        raise HTTPException(400, INVALID)
    password_hash = hash_password(payload.password)
    claimed = db.execute(update(PasswordReset).execution_options(synchronize_session="fetch").where(PasswordReset.token_hash == hashed, PasswordReset.consumed_at.is_(None), PasswordReset.expires_at > now).values(consumed_at=now))
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, INVALID)
    changed = db.execute(update(User).where(User.id == reset.user_id, User.deleted_at.is_(None), User.auth_version == reset.auth_version, User.email == reset.email).values(password_hash=password_hash, auth_version=User.auth_version+1, password_reset_required=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, INVALID)
    db.add(AuditEvent(event_kind="password_reset",title="Password reset completed; previous sessions invalidated",recipient_user_id=reset.user_id))
    db.commit()
    clear_remember_me_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Password updated. Sign in with your new password."}

@router.post("/users/{user_id}/recovery-link")
def admin_recovery(user_id: int, payload: AdminRecoveryRequest, response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(current_user, "admin", db)
    if not limit(db, f"admin:{current_user.id}", 10):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(400, "Your current password is required")
    user = db.get(User,user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(404, "Account not found")
    if "host" in assigned_base_roles(user,db) and role_rank(current_user,db) < ROLE_RANK["host"]:
        raise HTTPException(403, "Only a host can manage another host account")
    if user.id == current_user.id and payload.require_reset:
        raise HTTPException(400, "Use your profile to change your own password")
    if payload.require_reset:
        user.auth_version += 1
        user.password_reset_required = True
        db.flush()
    link, expires = issue(db,user)
    db.add(AuditEvent(event_kind="password_recovery_issued",title="Administrator created a password recovery link",actor_user_id=current_user.id,recipient_user_id=user.id,
        body="Existing sessions revoked; password reset required." if payload.require_reset else "Existing login remains available until password reset."))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"url":link,"expires_at":expires.isoformat(),"password_reset_required":payload.require_reset}
