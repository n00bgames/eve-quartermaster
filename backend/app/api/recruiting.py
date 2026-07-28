from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, RecruitmentApplication, RecruitmentAuditLog, RecruitmentInterview, RecruitmentLinkedCharacter, RecruitmentMessage, RecruitmentNote, RecruitmentSettings, RecruitmentStatusHistory, RecruitmentUserCapability, User
from app.services.esi_client import EsiClient, resolve_names
from app.services.permissions import role_exists
from app.services.recruiting import CAPABILITIES, RECRUITER, RECRUITMENT_ADMIN, applicant_application, audit, capabilities_for, is_recruiter, is_recruitment_admin, load_application, missing_requirements, normalize_draft_discord_username, public_settings_payload, require_recruiter, require_recruitment_admin, serialize_application, settings_row, setup_defaults, sync_recruitment_character, transition_status

router = APIRouter(prefix="/recruiting", tags=["recruiting"])


def clean_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        rows = value
    else:
        rows = str(value or "").splitlines()
    return list(dict.fromkeys(str(row).strip() for row in rows if str(row).strip()))


def settings_payload(row: RecruitmentSettings) -> dict[str, Any]:
    return {
        "id": row.id, "setup_complete": row.setup_complete,
        "corporation": {"id": row.corporation_eve_id, "name": row.corporation_name, "ticker": row.corporation_ticker, "logo_url": row.corporation_logo_url},
        "alliance": {"id": row.alliance_eve_id, "name": row.alliance_name, "ticker": row.alliance_ticker, "logo_url": row.alliance_logo_url},
        "ceo": {"id": row.ceo_character_eve_id, "name": row.ceo_character_name, "portrait_url": row.ceo_portrait_url, "manual_override": row.ceo_manual_override},
        "primary_timezone": row.primary_timezone, "activity_window_start": row.activity_window_start, "activity_window_end": row.activity_window_end,
        "public_headline": row.public_headline, "public_subheading": row.public_subheading,
        "public_summary": row.public_summary, "public_body": row.public_body,
        "offers": row.offers_json, "expectations": row.expectations_json, "priorities": row.priorities_json,
        "privacy_notice": row.privacy_notice, "required_scopes": row.required_scopes_json,
        "ceo_manual_override": row.ceo_manual_override, "statuses": row.statuses_json, "tags": row.tags_json,
        "form_options": row.form_options_json, "application_questions": row.application_questions_json,
        "interview_questions": row.interview_questions_json, "parameter_definitions": row.parameter_definitions_json,
        "declined_retention_days": row.declined_retention_days, "withdrawn_retention_days": row.withdrawn_retention_days,
        "abandoned_retention_days": row.abandoned_retention_days, "auto_refresh_hours": row.auto_refresh_hours,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def application_query() -> Any:
    return select(RecruitmentApplication).options(
        selectinload(RecruitmentApplication.applicant), selectinload(RecruitmentApplication.assigned_recruiter),
        selectinload(RecruitmentApplication.linked_characters).selectinload(RecruitmentLinkedCharacter.character),
        selectinload(RecruitmentApplication.interviews).selectinload(RecruitmentInterview.interviewer),
        selectinload(RecruitmentApplication.notes).selectinload(RecruitmentNote.author),
        selectinload(RecruitmentApplication.messages).selectinload(RecruitmentMessage.author),
        selectinload(RecruitmentApplication.history).selectinload(RecruitmentStatusHistory.acting_user),
    )


def hydrated_application(db: Session, application_id: int) -> RecruitmentApplication:
    application = db.scalar(application_query().where(RecruitmentApplication.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application was not found")
    return application


@router.get("/public")
def public_page(db: Session = Depends(get_db)) -> dict[str, Any]:
    return public_settings_payload(settings_row(db))


@router.post("/register")
def register_applicant(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = settings_row(db)
    if settings is None or not settings.setup_complete:
        raise HTTPException(status_code=409, detail="Recruiting has not completed Initial Setup")
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    display_name = str(payload.get("display_name") or email).strip()
    if not email or "@" not in email or len(password) < 8 or not display_name:
        raise HTTPException(status_code=400, detail="Display name, valid email, and an 8+ character password are required")
    existing = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing:
        raise HTTPException(status_code=400, detail="An account already exists for this email")
    user = User(email=email, display_name=display_name, role="applicant", password_hash=hash_password(password), timezone="UTC")
    db.add(user)
    db.flush()
    applicant_application(db, user, create=True)
    audit(db, user, "applicant_registered", "Applicant account created")
    db.commit()
    return {"access_token": create_access_token(str(user.id), {"role": user.role}), "token_type": "bearer", "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role, "timezone": user.timezone}}


@router.get("/context")
def context(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = settings_row(db)
    caps = sorted(capabilities_for(db, current_user))
    recruiter = is_recruiter(db, current_user)
    admin = is_recruitment_admin(db, current_user)
    result: dict[str, Any] = {"role": current_user.role, "capabilities": caps, "is_recruiter": recruiter, "is_recruitment_admin": admin, "setup_complete": bool(settings and settings.setup_complete), "public": public_settings_payload(settings)}
    if current_user.role == "applicant":
        application = db.scalar(application_query().where(RecruitmentApplication.applicant_user_id == current_user.id).order_by(RecruitmentApplication.id.desc()))
        result["application"] = serialize_application(application, settings) if application else None
        result["form_options"] = settings.form_options_json if settings else setup_defaults()["form_options"]
        result["application_questions"] = settings.application_questions_json if settings else setup_defaults()["application_questions"]
    return result


@router.get("/setup/defaults")
def defaults(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    return setup_defaults()


@router.get("/settings")
def get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    return settings_payload(settings_row(db, create=True))


@router.patch("/settings")
async def update_settings(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    row = settings_row(db, create=True)
    assert row is not None
    simple_fields = ["primary_timezone", "activity_window_start", "activity_window_end"]
    for field in simple_fields:
        if field in payload:
            setattr(row, field, payload[field] if payload[field] != "" else None)
    for field in ["public_headline", "public_subheading", "public_summary", "public_body", "privacy_notice"]:
        if field in payload:
            setattr(row, field, str(payload[field] or ""))

    requested_corporation_id = int(payload["corporation_eve_id"]) if payload.get("corporation_eve_id") else None
    restore_automatic_ceo = "ceo_manual_override" in payload and not bool(payload["ceo_manual_override"]) and row.ceo_manual_override
    corporation_changed = requested_corporation_id is not None and (requested_corporation_id != row.corporation_eve_id or not row.corporation_name)
    if corporation_changed or restore_automatic_ceo:
        corporation_id = requested_corporation_id or row.corporation_eve_id
        if corporation_id is None:
            raise HTTPException(status_code=400, detail="Choose a corporation before resolving its CEO")
        client = EsiClient()
        corporation = await client.get(f"/corporations/{corporation_id}/")
        ceo_id = int(corporation["ceo_id"])
        alliance_id = int(corporation["alliance_id"]) if corporation.get("alliance_id") else None
        ids = [ceo_id] + ([alliance_id] if alliance_id else [])
        names = await client.post("/universe/names/", ids)
        names_by_id = {int(item["id"]): item["name"] for item in names}
        row.corporation_eve_id = corporation_id
        row.corporation_name = corporation["name"]
        row.corporation_ticker = corporation.get("ticker")
        row.corporation_logo_url = f"https://images.evetech.net/corporations/{corporation_id}/logo?size=128"
        row.ceo_character_eve_id = ceo_id
        row.ceo_character_name = names_by_id.get(ceo_id)
        row.ceo_portrait_url = f"https://images.evetech.net/characters/{ceo_id}/portrait?size=128"
        row.ceo_manual_override = False
        if "alliance_eve_id" not in payload:
            row.alliance_eve_id = alliance_id
            row.alliance_name = names_by_id.get(alliance_id) if alliance_id else None
            row.alliance_ticker = None
            row.alliance_logo_url = f"https://images.evetech.net/alliances/{alliance_id}/logo?size=128" if alliance_id else None
        action = "corporation_selected" if corporation_changed else "ceo_override_disabled"
        summary = f"Selected {row.corporation_name}; CEO resolved from ESI" if corporation_changed else f"Restored ESI CEO for {row.corporation_name}"
        audit(db, current_user, action, summary, details={"corporation_eve_id": corporation_id, "ceo_character_eve_id": ceo_id})

    for field in ["alliance_eve_id", "alliance_name", "alliance_ticker", "alliance_logo_url"]:
        if field in payload:
            setattr(row, field, payload[field] if payload[field] != "" else None)

    if payload.get("ceo_manual_override"):
        override_id = int(payload["ceo_character_eve_id"]) if payload.get("ceo_character_eve_id") else None
        override_name = str(payload.get("ceo_character_name") or "").strip()
        if override_id is None or not override_name:
            raise HTTPException(status_code=400, detail="Resolve a CEO character before enabling the manual override")
        changed = not row.ceo_manual_override or row.ceo_character_eve_id != override_id
        row.ceo_character_eve_id = override_id
        row.ceo_character_name = override_name
        row.ceo_portrait_url = payload.get("ceo_portrait_url") or f"https://images.evetech.net/characters/{override_id}/portrait?size=128"
        row.ceo_manual_override = True
        if changed:
            audit(db, current_user, "ceo_override_enabled", "Recruitment CEO was manually overridden", details={"ceo_character_eve_id": override_id, "ceo_character_name": override_name})
    elif "ceo_manual_override" in payload:
        row.ceo_manual_override = False
    if "primary_timezone" in payload:
        try:
            ZoneInfo(str(row.primary_timezone))
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=400, detail="Choose a valid IANA timezone") from exc
    list_fields = {"offers": "offers_json", "expectations": "expectations_json", "priorities": "priorities_json", "statuses": "statuses_json", "tags": "tags_json", "required_scopes": "required_scopes_json"}
    for source, target in list_fields.items():
        if source in payload:
            setattr(row, target, clean_lines(payload[source]))
    json_fields = {"form_options": "form_options_json", "application_questions": "application_questions_json", "interview_questions": "interview_questions_json", "parameter_definitions": "parameter_definitions_json"}
    for source, target in json_fields.items():
        if source in payload:
            setattr(row, target, payload[source])
    for field in ["declined_retention_days", "withdrawn_retention_days", "abandoned_retention_days", "auto_refresh_hours"]:
        if field in payload:
            setattr(row, field, max(1, int(payload[field])))
    if payload.get("setup_complete"):
        required = [row.corporation_eve_id, row.corporation_name, row.ceo_character_eve_id, row.ceo_character_name, row.public_headline, row.public_summary, row.privacy_notice]
        if not all(required):
            raise HTTPException(status_code=400, detail="Corporation, verified CEO, public summary, and privacy notice are required to complete setup")
        row.setup_complete = True
    row.updated_by_user_id = current_user.id
    audit(db, current_user, "settings_updated", "Recruiting configuration updated")
    db.commit()
    db.refresh(row)
    return settings_payload(row)


@router.get("/resolve-organization")
async def resolve_organization(kind: str = Query(..., pattern="^(corporation|alliance|character)$"), name: str = Query(..., min_length=2, max_length=255), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    resolved = await resolve_names([name])
    collection = resolved.get({"corporation": "corporations", "alliance": "alliances", "character": "characters"}[kind]) or []
    exact = next((row for row in collection if str(row.get("name", "")).casefold() == name.strip().casefold()), None)
    if not exact:
        raise HTTPException(status_code=404, detail=f"No exact EVE {kind} match was found")
    eve_id = int(exact["id"])
    client = EsiClient()
    if kind == "corporation":
        details = await client.get(f"/corporations/{eve_id}/")
        ceo_id = int(details["ceo_id"])
        names = await client.post("/universe/names/", [ceo_id] + ([int(details["alliance_id"])] if details.get("alliance_id") else []))
        name_map = {int(row["id"]): row["name"] for row in names}
        alliance_id = int(details["alliance_id"]) if details.get("alliance_id") else None
        payload = {"id": eve_id, "name": details["name"], "ticker": details.get("ticker"), "logo_url": f"https://images.evetech.net/corporations/{eve_id}/logo?size=128", "ceo": {"id": ceo_id, "name": name_map.get(ceo_id), "portrait_url": f"https://images.evetech.net/characters/{ceo_id}/portrait?size=128"}, "alliance": {"id": alliance_id, "name": name_map.get(alliance_id) if alliance_id else None, "logo_url": f"https://images.evetech.net/alliances/{alliance_id}/logo?size=128" if alliance_id else None}}
    elif kind == "alliance":
        details = await client.get(f"/alliances/{eve_id}/")
        payload = {"id": eve_id, "name": details["name"], "ticker": details.get("ticker"), "logo_url": f"https://images.evetech.net/alliances/{eve_id}/logo?size=128"}
    else:
        details = await client.get(f"/characters/{eve_id}/")
        payload = {"id": eve_id, "name": details["name"], "portrait_url": f"https://images.evetech.net/characters/{eve_id}/portrait?size=128"}
    audit(db, current_user, "organization_resolved", f"Resolved {kind} {payload['name']}", details={"kind": kind, "eve_id": eve_id})
    db.commit()
    return payload


@router.get("/capabilities")
def list_capabilities(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    users = db.scalars(select(User).where(User.deleted_at.is_(None), User.role != "applicant").order_by(User.display_name)).all()
    rows = db.scalars(select(RecruitmentUserCapability)).all()
    assignments: dict[int, list[str]] = {}
    for row in rows:
        assignments.setdefault(row.user_id, []).append(row.capability)
    return {"capabilities": sorted(CAPABILITIES), "users": [{"id": user.id, "display_name": user.display_name, "email": user.email, "role": user.role, "capabilities": sorted(assignments.get(user.id, []))} for user in users]}


@router.put("/capabilities/{user_id}")
def update_capabilities(user_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.role == "applicant":
        raise HTTPException(status_code=404, detail="Eligible user was not found")
    requested = {str(item) for item in payload.get("capabilities", [])}
    if not requested <= CAPABILITIES:
        raise HTTPException(status_code=400, detail="Unknown recruiting capability")
    db.execute(delete(RecruitmentUserCapability).where(RecruitmentUserCapability.user_id == user_id))
    for capability in sorted(requested):
        db.add(RecruitmentUserCapability(user_id=user_id, capability=capability, assigned_by_user_id=current_user.id))
    audit(db, current_user, "capabilities_updated", f"Updated recruiting capabilities for {user.display_name}", details={"user_id": user_id, "capabilities": sorted(requested)})
    db.commit()
    return {"user_id": user_id, "capabilities": sorted(requested)}


@router.patch("/applications/me")
def save_my_application(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if current_user.role != "applicant":
        raise HTTPException(status_code=403, detail="Applicant role is required")
    application = applicant_application(db, current_user, create=True)
    assert application is not None
    if application.status not in {"Draft", "Additional Information Requested", "ESI Verification Required"}:
        raise HTTPException(status_code=409, detail="This application is read-only in its current status")
    if "discord_username" in payload:
        application.discord_username = normalize_draft_discord_username(payload.get("discord_username"))
    for field in ["discord_display_name", "discord_user_id", "preferred_name", "pronouns", "primary_interest"]:
        if field in payload:
            setattr(application, field, str(payload[field]).strip() or None)
    if "timezone" in payload:
        zone = str(payload.get("timezone") or "").strip()
        try:
            ZoneInfo(zone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=400, detail="Choose a valid IANA timezone") from exc
        application.timezone = zone
        current_user.timezone = zone
    settings = settings_row(db)
    if "answers" in payload:
        answers = dict(payload.get("answers") or {})
        answers["_question_schema"] = settings.application_questions_json if settings else setup_defaults()["application_questions"]
        application.answers_json = answers
        application.veteran_status = bool(answers.get("military_veteran"))
    if "acknowledgements" in payload:
        application.acknowledgements_json = dict(payload.get("acknowledgements") or {})
    if "activity_preferences" in payload:
        application.activity_preferences_json = dict(payload.get("activity_preferences") or {})
    application.last_applicant_activity_at = datetime.now(timezone.utc)
    audit(db, current_user, "application_saved", "Applicant saved draft answers", application.id)
    db.commit()
    return serialize_application(hydrated_application(db, application.id), settings_row(db))


@router.post("/applications/me/submit")
def submit_my_application(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    application = applicant_application(db, current_user)
    if application is None:
        raise HTTPException(status_code=404, detail="Start an application first")
    application = hydrated_application(db, application.id)
    missing = missing_requirements(application)
    if missing:
        raise HTTPException(status_code=400, detail={"message": "Complete all requirements before submitting", "missing": missing})
    transition_status(db, application, "Submitted", current_user, "Applicant submitted application")
    db.commit()
    return serialize_application(hydrated_application(db, application.id), settings_row(db))


@router.post("/applications/me/withdraw")
def withdraw_my_application(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    application = applicant_application(db, current_user)
    if application is None:
        raise HTTPException(status_code=404, detail="Application was not found")
    transition_status(db, application, "Applicant Withdrew", current_user, str(payload.get("reason") or "Applicant withdrew"))
    db.commit()
    return {"status": application.status}


@router.post("/applications/me/messages")
def applicant_message(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if current_user.role != "applicant":
        raise HTTPException(status_code=403, detail="Applicant role is required")
    application = applicant_application(db, current_user)
    body = str(payload.get("body") or "").strip()
    if application is None or not body:
        raise HTTPException(status_code=400, detail="Application and message text are required")
    message = RecruitmentMessage(application_id=application.id, author_user_id=current_user.id, body=body, from_applicant=True)
    db.add(message)
    audit(db, current_user, "applicant_message", "Applicant sent a recruiter message", application.id)
    db.commit()
    return {"id": message.id, "status": "sent"}


@router.patch("/applications/me/interviews/{interview_id}")
def applicant_interview_update(interview_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    application = applicant_application(db, current_user)
    interview = db.get(RecruitmentInterview, interview_id)
    if application is None or interview is None or interview.application_id != application.id:
        raise HTTPException(status_code=404, detail="Interview was not found")
    if "availability" in payload:
        interview.availability_json = clean_lines(payload["availability"])
    if payload.get("acknowledged"):
        interview.applicant_acknowledged_at = datetime.now(timezone.utc)
        audit(db, current_user, "interview_acknowledged", "Applicant acknowledged the interview schedule", application.id, {"interview_id": interview.id})
    db.commit()
    return serialize_application(hydrated_application(db, application.id), settings_row(db))

@router.post("/applications/me/characters/{linked_id}/main")
def set_main_character(linked_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    application = applicant_application(db, current_user)
    linked = db.get(RecruitmentLinkedCharacter, linked_id)
    if application is None or linked is None or linked.application_id != application.id:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    for row in db.scalars(select(RecruitmentLinkedCharacter).where(RecruitmentLinkedCharacter.application_id == application.id)).all():
        row.is_main = row.id == linked_id
    audit(db, current_user, "main_character_selected", f"Selected {linked.character.name} as main", application.id)
    db.commit()
    return {"id": linked.id, "is_main": True}


@router.delete("/applications/me/characters/{linked_id}")
def unlink_character(linked_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    application = applicant_application(db, current_user)
    linked = db.get(RecruitmentLinkedCharacter, linked_id)
    if application is None or linked is None or linked.application_id != application.id:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    if application.status not in {"Draft", "ESI Verification Required", "Additional Information Requested"}:
        raise HTTPException(status_code=409, detail="Characters cannot be unlinked in the current status")
    token = db.scalar(select(EsiToken).where(EsiToken.character_id == linked.character_id, EsiToken.user_id == current_user.id, EsiToken.revoked_at.is_(None)))
    if token:
        token.revoked_at = datetime.now(timezone.utc)
    name = linked.character.name
    db.delete(linked)
    audit(db, current_user, "character_unlinked", f"Applicant unlinked {name}", application.id)
    db.commit()
    return {"status": "unlinked"}


@router.post("/applications/me/characters/{linked_id}/sync")
async def refresh_character(linked_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    application = applicant_application(db, current_user)
    linked = db.scalar(select(RecruitmentLinkedCharacter).options(selectinload(RecruitmentLinkedCharacter.character)).where(RecruitmentLinkedCharacter.id == linked_id))
    if application is None or linked is None or linked.application_id != application.id:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    token = db.scalar(select(EsiToken).where(EsiToken.character_id == linked.character_id, EsiToken.user_id == current_user.id, EsiToken.revoked_at.is_(None)))
    if token is None:
        raise HTTPException(status_code=409, detail="This character needs EVE SSO authorization")
    await sync_recruitment_character(db, linked, token)
    audit(db, current_user, "character_refreshed", f"Applicant refreshed {linked.character.name}", application.id)
    db.commit()
    return serialize_application(hydrated_application(db, application.id), settings_row(db))


@router.get("/dashboard")
def dashboard(status: str | None = None, search: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    settings = settings_row(db)
    query = application_query().where(RecruitmentApplication.status != "Draft").order_by(RecruitmentApplication.submitted_at.desc().nullslast(), RecruitmentApplication.id.desc())
    if status:
        query = query.where(RecruitmentApplication.status == status)
    applications = db.scalars(query).unique().all()
    if search:
        term = search.casefold()
        applications = [row for row in applications if term in " ".join([row.discord_username or "", row.preferred_name or "", row.applicant.display_name if row.applicant else "", *(item.character.name for item in row.linked_characters)]).casefold()]
    counts = dict(db.execute(select(RecruitmentApplication.status, func.count()).group_by(RecruitmentApplication.status)).all())
    users = db.scalars(select(User).where(User.deleted_at.is_(None), User.role != "applicant").order_by(User.display_name)).all()
    recruiters = [{"id": user.id, "display_name": user.display_name} for user in users if is_recruiter(db, user)]
    return {
        "counts": counts, "statuses": settings.statuses_json if settings else [],
        "tags": settings.tags_json if settings else [],
        "parameter_definitions": settings.parameter_definitions_json if settings else [],
        "interview_questions": settings.interview_questions_json if settings else [],
        "recruiters": recruiters,
        "applications": [serialize_application(row, settings, recruiter=True, admin=is_recruitment_admin(db, current_user)) for row in applications],
    }


@router.get("/applications/{application_id}")
def recruiter_application(application_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    application = hydrated_application(db, application_id)
    audit(db, current_user, "application_viewed", f"Viewed application {application_id}", application_id, {"sensitive_record_access": True})
    db.commit()
    return serialize_application(application, settings_row(db), recruiter=True, admin=is_recruitment_admin(db, current_user))


@router.patch("/applications/{application_id}")
def review_application(application_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    application = hydrated_application(db, application_id)
    if "status" in payload:
        new_status = str(payload["status"])
        if new_status in {"Accepted", "Accepted with Onboarding Plan", "Declined", "Closed", "Draft"} and not is_recruitment_admin(db, current_user):
            raise HTTPException(status_code=403, detail="Recruitment administrator capability is required for final decisions or reopening")
        transition_status(db, application, new_status, current_user, str(payload.get("reason") or "") or None, bool(payload.get("applicant_visible", True)))
        if new_status in {"Accepted", "Accepted with Onboarding Plan"}:
            accepted_role = str(payload.get("accepted_role") or "member")
            if not role_exists(db, accepted_role) or accepted_role == "applicant":
                raise HTTPException(status_code=400, detail="Choose a valid member role")
            application.applicant.role = accepted_role
    if "assigned_recruiter_user_id" in payload:
        recruiter_id = int(payload["assigned_recruiter_user_id"]) if payload["assigned_recruiter_user_id"] else None
        if recruiter_id:
            assignee = db.get(User, recruiter_id)
            if assignee is None or not is_recruiter(db, assignee):
                raise HTTPException(status_code=400, detail="Assignee must have a recruiting capability")
        application.assigned_recruiter_user_id = recruiter_id
    if "tags" in payload:
        application.tags_json = clean_lines(payload["tags"])
    if "recruiter_ratings" in payload:
        application.recruiter_ratings_json = dict(payload["recruiter_ratings"] or {})
    if "internal_flags" in payload:
        application.internal_flags_json = clean_lines(payload["internal_flags"])
    audit(db, current_user, "application_review_updated", f"Updated review data for application {application_id}", application_id, {"fields": sorted(payload.keys())})
    db.commit()
    return serialize_application(hydrated_application(db, application_id), settings_row(db), recruiter=True, admin=is_recruitment_admin(db, current_user))


@router.post("/applications/{application_id}/notes")
def add_note(application_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    load_application(db, application_id)
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Note text is required")
    note = RecruitmentNote(application_id=application_id, author_user_id=current_user.id, body=body, applicant_visible=bool(payload.get("applicant_visible")))
    db.add(note)
    audit(db, current_user, "note_added", "Recruiter added an application note", application_id, {"applicant_visible": note.applicant_visible})
    db.commit()
    return {"id": note.id}


@router.patch("/applications/{application_id}/notes/{note_id}/redact")
def redact_note(application_id: int, note_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruitment_admin(db, current_user)
    note = db.get(RecruitmentNote, note_id)
    if note is None or note.application_id != application_id:
        raise HTTPException(status_code=404, detail="Note was not found")
    note.redacted_at = datetime.now(timezone.utc)
    audit(db, current_user, "note_redacted", "Recruitment administrator redacted a note", application_id, {"note_id": note_id})
    db.commit()
    return {"status": "redacted"}


@router.post("/applications/{application_id}/messages")
def recruiter_message(application_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    load_application(db, application_id)
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message text is required")
    message = RecruitmentMessage(application_id=application_id, author_user_id=current_user.id, body=body, from_applicant=False)
    db.add(message)
    audit(db, current_user, "recruiter_message", "Recruiter sent an applicant-visible message", application_id)
    db.commit()
    return {"id": message.id}


@router.post("/applications/{application_id}/interviews")
def create_interview(application_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    application = load_application(db, application_id)
    scheduled = datetime.fromisoformat(str(payload["scheduled_at"]).replace("Z", "+00:00")) if payload.get("scheduled_at") else None
    interview = RecruitmentInterview(application_id=application_id, interviewer_user_id=int(payload.get("interviewer_user_id") or current_user.id), scheduled_at=scheduled, applicant_timezone=application.timezone, availability_json=payload.get("availability") or [], attendance_status="scheduled" if scheduled else "requested", visible_follow_up=str(payload.get("visible_follow_up") or "") or None)
    db.add(interview)
    transition_status(db, application, "Interview Scheduled" if scheduled else "Interview Scheduling", current_user, "Interview workflow updated")
    audit(db, current_user, "interview_created", "Recruiter created an interview record", application_id)
    db.commit()
    return {"id": interview.id}


@router.patch("/applications/{application_id}/interviews/{interview_id}")
def update_interview(application_id: int, interview_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_recruiter(db, current_user)
    interview = db.get(RecruitmentInterview, interview_id)
    if interview is None or interview.application_id != application_id:
        raise HTTPException(status_code=404, detail="Interview was not found")
    for field in ["attendance_status", "internal_notes", "visible_follow_up", "recommendation"]:
        if field in payload:
            setattr(interview, field, payload[field])
    if "answers" in payload:
        interview.answers_json = dict(payload["answers"] or {})
    if "scheduled_at" in payload:
        interview.scheduled_at = datetime.fromisoformat(str(payload["scheduled_at"]).replace("Z", "+00:00")) if payload["scheduled_at"] else None
    if payload.get("completed"):
        interview.completed_at = datetime.now(timezone.utc)
        transition_status(db, load_application(db, application_id), "Interview Complete", current_user, "Interview completed")
    audit(db, current_user, "interview_updated", "Recruiter updated an interview", application_id, {"interview_id": interview_id, "fields": sorted(payload.keys())})
    db.commit()
    return {"id": interview.id, "status": interview.attendance_status}


@router.get("/audit")
def recruitment_audit(limit: int = Query(200, ge=1, le=1000), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_recruitment_admin(db, current_user)
    rows = db.scalars(select(RecruitmentAuditLog).options(selectinload(RecruitmentAuditLog.actor)).order_by(RecruitmentAuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": row.id, "application_id": row.application_id, "actor": row.actor.display_name if row.actor else "System", "action": row.action, "summary": row.summary, "details": row.details_json, "created_at": row.created_at.isoformat()} for row in rows]
