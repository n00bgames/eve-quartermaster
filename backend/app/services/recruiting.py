from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import RecruitmentApplication, RecruitmentAuditLog, RecruitmentSettings, RecruitmentStatusHistory, RecruitmentUserCapability, User
from app.services.permissions import base_role_for

RECRUITER = "recruiter"
RECRUITMENT_ADMIN = "recruitment_admin"
CAPABILITIES = {RECRUITER, RECRUITMENT_ADMIN}
TERMINAL_STATUSES = {"Accepted", "Accepted with Onboarding Plan", "Declined", "Applicant Withdrew", "Closed"}
DEFAULT_STATUSES = [
    "Draft", "Submitted", "ESI Verification Required", "Under Initial Review", "Additional Information Requested",
    "Interview Required", "Interview Scheduling", "Interview Scheduled", "Interview Complete", "Final Review",
    "Accepted", "Accepted with Onboarding Plan", "Hold", "Declined", "Applicant Withdrew", "Closed",
]
DEFAULT_TAGS = [
    "New player", "Returning player", "Experienced player", "Military veteran", "Strong timezone overlap",
    "Partial timezone overlap", "Off-timezone coverage", "PvP-focused", "Industry-focused", "PvE-focused",
    "Mixed PvX", "Scout", "Tackle", "Logistics", "Electronic warfare", "Miner", "Booster", "Hauler",
    "Manufacturer", "Researcher", "Market specialist", "Fleet commander", "Capital pilot", "Black Ops",
    "Doctrine ready", "Needs doctrine training", "Needs onboarding plan", "Defense interest", "War-interested",
    "Referred applicant", "Previous member",
]
DEFAULT_PARAMETERS = [
    "PvP interest", "Industry interest", "PvE interest", "Lowsec comfort", "War appetite", "Doctrine commitment",
    "Pocket-defense commitment", "Fleet participation interest", "Support-role willingness", "Loss tolerance",
    "Group orientation", "Self-direction", "Teachability", "Communication maturity", "Conflict-management maturity",
    "Reliability", "Activity overlap", "Leadership potential", "New-player support needs", "Veteran-community interest",
    "Overall expectation alignment",
]
DEFAULT_INTERVIEW_QUESTIONS = [
    "What parts of EVE keep you logging in, and what tends to burn you out?",
    "What role do you normally enjoy during group activities?",
    "Tell us about a ship loss or mistake you learned from.",
    "A fleet is forming, but you cannot fly the priority doctrine. What would you do?",
    "You are doing your own activity when a defensive ping goes out. How would you decide whether to respond?",
    "How do you prefer to receive correction when something goes wrong?",
    "When learning something new, do you research first, ask for help first, learn by doing, or use a mixture?",
    "What do you expect from a corporation, and what do you expect to contribute?",
    "How interested are you in lowsec PvP and optional war-eligible opportunities?",
    "Describe your typical play schedule and how often it changes.",
    "Suppose another member makes a mistake that costs the fleet ships or ISK. How would you handle it?",
    "What would make you decide this corporation was not right for you?",
    "Do you have any concerns about doctrine training, voice communications, or helping defend shared space?",
    "What questions do you have for us?",
]
DEFAULT_FORM_OPTIONS = {
    "age_ranges": ["18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-59", "60+", "Prefer not to specify beyond confirming I am 18+"],
    "microphone": ["Yes", "No", "Sometimes"],
    "voice_comfort": ["Comfortable speaking", "Prefer listening unless needed", "Comfortable after getting to know the group", "Text communication preferred", "Other"],
    "activity_frequency": ["A few times per month", "About once per week", "Several times per week", "Most days", "Daily or nearly daily", "Highly variable"],
    "scheduled_availability": ["Usually", "Sometimes", "Rarely", "Unknown"],
    "defensive_availability": ["Usually", "Sometimes", "Rarely", "Only when already online", "Unknown"],
    "eve_experience": ["Brand new", "Less than 3 months", "3-6 months", "6-12 months", "1-3 years", "3-5 years", "More than 5 years", "Returning after a long break"],
    "primary_interests": ["PvP", "Industry", "PvE", "Mixed PvX", "Undecided / still learning"],
    "experience_ratings": ["No experience", "Interested in learning", "Beginner", "Comfortable", "Experienced", "Able to teach", "Able to lead"],
    "lowsec_experience": ["None", "Limited", "Comfortable", "Experienced", "I live primarily in lowsec"],
    "loss_comfort": ["Very uncomfortable", "Learning to accept losses", "Comfortable with normal losses", "Experienced PvP loss tolerance"],
    "defense_willingness": ["Yes", "Usually, when online", "Sometimes", "Interested but need training", "No"],
    "war_interest": ["Yes", "Maybe", "No", "I need more information"],
    "assessment_levels": ["Not assessed", "Very low", "Low", "Moderate", "High", "Very high"],
}
DEFAULT_APPLICATION_QUESTIONS = [
    {"key": "previous_experience", "section": "Player Background", "label": "Previous EVE experience", "type": "textarea"},
    {"key": "corporation_experience", "section": "Player Background", "label": "Previous corporation or alliance experience", "type": "textarea"},
    {"key": "leaving_reason", "section": "Player Background", "label": "Why are you leaving or considering leaving your current corporation?", "type": "textarea"},
    {"key": "heard_about_us", "section": "Player Background", "label": "How did you hear about us?", "type": "text"},
    {"key": "looking_for", "section": "Player Background", "label": "What are you looking for in a corporation?", "type": "textarea", "required": True},
    {"key": "contribution", "section": "Player Background", "label": "What do you expect to contribute?", "type": "textarea", "required": True},
    {"key": "retention_risks", "section": "Player Background", "label": "What tends to make you stop playing or take a break?", "type": "textarea"},
    {"key": "fleet_roles", "section": "Fleet and Doctrine", "label": "Preferred fleet roles, current capabilities, and roles you are willing to train", "type": "textarea"},
    {"key": "training_limits", "section": "Fleet and Doctrine", "label": "Practical limitations that affect your training plans", "type": "textarea"},
    {"key": "defensive_role", "section": "Lowsec and Defense", "label": "Preferred defensive role and support interests", "type": "textarea"},
    {"key": "war_roles", "section": "War-Eligible Gameplay", "label": "Optional war-focused interests, characters, and preferred roles", "type": "textarea"},
    {"key": "anything_else", "section": "Final Notes", "label": "Anything else recruiters should know?", "type": "textarea"},
]


def setup_defaults() -> dict[str, Any]:
    return {
        "statuses": DEFAULT_STATUSES, "tags": DEFAULT_TAGS, "form_options": DEFAULT_FORM_OPTIONS,
        "application_questions": DEFAULT_APPLICATION_QUESTIONS,
        "interview_questions": [{"id": index + 1, "text": text, "active": True} for index, text in enumerate(DEFAULT_INTERVIEW_QUESTIONS)],
        "parameter_definitions": [{"key": item.lower().replace(" ", "_").replace("-", "_"), "label": item, "active": True} for item in DEFAULT_PARAMETERS],
        "required_scopes": ["publicData", "esi-skills.read_skills.v1"],
    }


def settings_row(db: Session, create: bool = False) -> RecruitmentSettings | None:
    row = db.get(RecruitmentSettings, 1)
    if row is None and create:
        defaults = setup_defaults()
        row = RecruitmentSettings(id=1, statuses_json=defaults["statuses"], tags_json=defaults["tags"], form_options_json=defaults["form_options"], application_questions_json=defaults["application_questions"], interview_questions_json=defaults["interview_questions"], parameter_definitions_json=defaults["parameter_definitions"], required_scopes_json=defaults["required_scopes"])
        db.add(row)
        db.flush()
    return row


def capabilities_for(db: Session, user: User) -> set[str]:
    return set(db.scalars(select(RecruitmentUserCapability.capability).where(RecruitmentUserCapability.user_id == user.id)).all())


def is_recruiter(db: Session, user: User) -> bool:
    return bool(capabilities_for(db, user) & CAPABILITIES) or base_role_for(db, user.role) in {"host", "admin"}


def is_recruitment_admin(db: Session, user: User) -> bool:
    return RECRUITMENT_ADMIN in capabilities_for(db, user) or base_role_for(db, user.role) in {"host", "admin"}


def require_recruiter(db: Session, user: User) -> None:
    if not is_recruiter(db, user):
        raise HTTPException(status_code=403, detail="Recruiter capability is required")


def require_recruitment_admin(db: Session, user: User) -> None:
    if not is_recruitment_admin(db, user):
        raise HTTPException(status_code=403, detail="Recruitment administrator capability is required")


def audit(db: Session, actor: User | None, action: str, summary: str, application_id: int | None = None, details: dict[str, Any] | None = None) -> None:
    db.add(RecruitmentAuditLog(application_id=application_id, actor_user_id=actor.id if actor else None, action=action, summary=summary[:500], details_json=details or {}))


def load_application(db: Session, application_id: int) -> RecruitmentApplication:
    application = db.scalar(select(RecruitmentApplication).options(selectinload(RecruitmentApplication.linked_characters), selectinload(RecruitmentApplication.interviews), selectinload(RecruitmentApplication.notes), selectinload(RecruitmentApplication.messages), selectinload(RecruitmentApplication.history)).where(RecruitmentApplication.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application was not found")
    return application


def applicant_application(db: Session, user: User, create: bool = False) -> RecruitmentApplication | None:
    application = db.scalar(select(RecruitmentApplication).where(RecruitmentApplication.applicant_user_id == user.id).order_by(RecruitmentApplication.id.desc()))
    if application is None and create:
        application = RecruitmentApplication(applicant_user_id=user.id, status="Draft", last_applicant_activity_at=datetime.now(timezone.utc))
        db.add(application)
        db.flush()
        db.add(RecruitmentStatusHistory(application_id=application.id, previous_status=None, new_status="Draft", acting_user_id=user.id, reason="Application started"))
        audit(db, user, "application_created", "Applicant started an application", application.id)
    return application


def transition_status(db: Session, application: RecruitmentApplication, new_status: str, actor: User, reason: str | None = None, applicant_visible: bool = True) -> None:
    settings = settings_row(db)
    allowed = settings.statuses_json if settings and settings.statuses_json else DEFAULT_STATUSES
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail="Unknown recruitment status")
    previous = application.status
    application.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "Submitted" and application.submitted_at is None:
        application.submitted_at = now
    if new_status == "Applicant Withdrew":
        application.withdrawn_at = now
    if new_status in TERMINAL_STATUSES:
        application.closed_at = now
    db.add(RecruitmentStatusHistory(application_id=application.id, previous_status=previous, new_status=new_status, acting_user_id=actor.id, reason=reason, applicant_visible=applicant_visible, notifications_json=["in_app"]))
    audit(db, actor, "status_changed", f"Application moved from {previous} to {new_status}", application.id, {"previous_status": previous, "new_status": new_status, "reason": reason, "applicant_visible": applicant_visible})


def missing_requirements(application: RecruitmentApplication) -> list[str]:
    missing: list[str] = []
    if not application.discord_username:
        missing.append("Discord username")
    if not application.timezone:
        missing.append("Timezone and availability")
    if not application.primary_interest:
        missing.append("Primary activity interest")
    required_acknowledgements = ["adult", "english", "discord", "voice", "esi", "doctrine", "defense"]
    if not all(bool((application.acknowledgements_json or {}).get(key)) for key in required_acknowledgements):
        missing.append("Required acknowledgements")
    if not application.linked_characters:
        missing.append("At least one EVE character")
    elif not any(row.is_main for row in application.linked_characters):
        missing.append("Main EVE character")
    elif not all(row.verification_status == "verified" for row in application.linked_characters):
        missing.append("Verified EVE character data")
    questions = settings_row_from_application_questions(application)
    if questions:
        required_answers = [row["key"] for row in questions if row.get("required")]
        if not all(str((application.answers_json or {}).get(key) or "").strip() for key in required_answers):
            missing.append("Required application answers")
    return missing


def normalize_draft_discord_username(value: Any) -> str | None:
    discord = str(value or "").strip()
    if len(discord) > 120 or any(char.isspace() for char in discord):
        raise HTTPException(status_code=400, detail="Enter a valid current Discord username without spaces")
    return discord or None


def settings_row_from_application_questions(application: RecruitmentApplication) -> list[dict[str, Any]]:
    # Required fields are represented in the application schema snapshot only when present.
    schema = (application.answers_json or {}).get("_question_schema")
    return schema if isinstance(schema, list) else DEFAULT_APPLICATION_QUESTIONS


def progress(application: RecruitmentApplication) -> int:
    return max(0, min(100, 100 - len(missing_requirements(application)) * 20))


def timezone_payload(name: str | None, at: datetime | None = None) -> dict[str, Any] | None:
    if not name:
        return None
    try:
        now = (at or datetime.now(timezone.utc)).astimezone(ZoneInfo(name))
    except ZoneInfoNotFoundError:
        return {"name": name, "valid": False}
    offset = now.utcoffset()
    seconds = int(offset.total_seconds()) if offset else 0
    sign = "+" if seconds >= 0 else "-"
    hours, remainder = divmod(abs(seconds), 3600)
    minutes = remainder // 60
    return {"name": name, "valid": True, "current_time": now.isoformat(), "utc_offset": f"UTC{sign}{hours:02d}:{minutes:02d}"}


def overlap_hours(applicant_timezone: str | None, start_value: str | None, end_value: str | None, settings: RecruitmentSettings | None) -> float | None:
    if not applicant_timezone or not start_value or not end_value or settings is None:
        return None
    try:
        applicant_zone, corp_zone = ZoneInfo(applicant_timezone), ZoneInfo(settings.primary_timezone)
        today = datetime.now(timezone.utc).date()

        def utc_window(zone: ZoneInfo, start_text: str, end_text: str) -> tuple[datetime, datetime]:
            start = datetime.combine(today, time.fromisoformat(start_text), zone).astimezone(timezone.utc)
            end = datetime.combine(today, time.fromisoformat(end_text), zone).astimezone(timezone.utc)
            if end <= start:
                end += timedelta(days=1)
            return start, end

        app_start, app_end = utc_window(applicant_zone, start_value, end_value)
        corp_start, corp_end = utc_window(corp_zone, settings.activity_window_start, settings.activity_window_end)
        overlaps = []
        for shift in (-1, 0, 1):
            shifted_start = app_start + timedelta(days=shift)
            shifted_end = app_end + timedelta(days=shift)
            overlap = (min(shifted_end, corp_end) - max(shifted_start, corp_start)).total_seconds() / 3600
            overlaps.append(max(0.0, overlap))
        return round(max(overlaps), 1)
    except (ValueError, ZoneInfoNotFoundError):
        return None

def public_settings_payload(settings: RecruitmentSettings | None) -> dict[str, Any]:
    if settings is None or not settings.setup_complete:
        return {"setup_complete": False}
    return {
        "setup_complete": True,
        "corporation": {"id": settings.corporation_eve_id, "name": settings.corporation_name, "ticker": settings.corporation_ticker, "logo_url": settings.corporation_logo_url},
        "alliance": {"id": settings.alliance_eve_id, "name": settings.alliance_name, "ticker": settings.alliance_ticker, "logo_url": settings.alliance_logo_url},
        "ceo": {"id": settings.ceo_character_eve_id, "name": settings.ceo_character_name, "portrait_url": settings.ceo_portrait_url, "manual_override": settings.ceo_manual_override},
        "primary_timezone": timezone_payload(settings.primary_timezone), "activity_window_start": settings.activity_window_start, "activity_window_end": settings.activity_window_end,
        "public_headline": settings.public_headline, "public_subheading": settings.public_subheading,
        "public_summary": settings.public_summary, "public_body": settings.public_body,
        "offers": settings.offers_json, "expectations": settings.expectations_json, "priorities": settings.priorities_json,
        "privacy_notice": settings.privacy_notice, "required_scopes": settings.required_scopes_json,
    }


def serialize_character(row: Any, recruiter: bool) -> dict[str, Any]:
    character = row.character
    payload = {"id": row.id, "character_id": character.character_id, "name": character.name, "portrait_url": character.portrait_url, "security_status": character.security_status, "total_skill_points": character.total_skill_points, "is_main": row.is_main, "verification_status": row.verification_status, "token_health": row.token_health, "last_successful_sync_at": row.last_successful_sync_at.isoformat() if row.last_successful_sync_at else None, "granted_scopes": row.granted_scopes_json, "snapshot": row.snapshot_json}
    if recruiter:
        payload["employment_history"] = row.employment_history_json
        payload["last_sync_error"] = row.last_sync_error
    return payload


def serialize_application(application: RecruitmentApplication, settings: RecruitmentSettings | None, recruiter: bool = False, admin: bool = False) -> dict[str, Any]:
    application.progress_percent = progress(application)
    answers = dict(application.answers_json or {})
    answers.pop("_question_schema", None)
    payload: dict[str, Any] = {
        "id": application.id, "status": application.status, "discord_username": application.discord_username,
        "discord_display_name": application.discord_display_name, "discord_user_id": application.discord_user_id,
        "discord_verified_at": application.discord_verified_at.isoformat() if application.discord_verified_at else None,
        "preferred_name": application.preferred_name, "pronouns": application.pronouns, "timezone": application.timezone,
        "timezone_info": timezone_payload(application.timezone), "primary_interest": application.primary_interest,
        "answers": answers, "acknowledgements": application.acknowledgements_json, "activity_preferences": application.activity_preferences_json,
        "progress_percent": application.progress_percent, "missing_requirements": missing_requirements(application),
        "characters": [serialize_character(row, recruiter) for row in application.linked_characters],
        "messages": [{"id": row.id, "body": row.body, "from_applicant": row.from_applicant, "author": row.author.display_name if row.author else "Former account", "created_at": row.created_at.isoformat()} for row in application.messages],
        "timeline": [{"id": row.id, "previous_status": row.previous_status, "new_status": row.new_status, "reason": row.reason, "created_at": row.created_at.isoformat()} for row in application.history if recruiter or row.applicant_visible],
        "interviews": [{"id": row.id, "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None, "applicant_timezone": row.applicant_timezone, "availability": row.availability_json, "attendance_status": row.attendance_status, "visible_follow_up": row.visible_follow_up, "recommendation": row.recommendation if recruiter else None, "applicant_acknowledged_at": row.applicant_acknowledged_at.isoformat() if row.applicant_acknowledged_at else None, "completed_at": row.completed_at.isoformat() if row.completed_at else None, **({"answers": row.answers_json, "internal_notes": row.internal_notes, "interviewer": row.interviewer.display_name if row.interviewer else None} if recruiter else {})} for row in application.interviews],
        "created_at": application.created_at.isoformat(), "updated_at": application.updated_at.isoformat(), "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
    }
    availability = application.activity_preferences_json or {}
    payload["overlap_hours"] = overlap_hours(application.timezone, availability.get("active_start"), availability.get("active_end"), settings)
    if recruiter:
        payload.update({
            "applicant_user_id": application.applicant_user_id, "applicant_name": application.applicant.display_name if application.applicant else None,
            "applicant_email": application.applicant.email if application.applicant else None,
            "assigned_recruiter_user_id": application.assigned_recruiter_user_id,
            "assigned_recruiter": application.assigned_recruiter.display_name if application.assigned_recruiter else None,
            "veteran_status": application.veteran_status, "tags": application.tags_json, "recruiter_ratings": application.recruiter_ratings_json,
            "internal_flags": application.internal_flags_json,
            "notes": [{"id": row.id, "body": None if row.redacted_at else row.body, "redacted": bool(row.redacted_at), "applicant_visible": row.applicant_visible, "author": row.author.display_name if row.author else "Former account", "created_at": row.created_at.isoformat()} for row in application.notes],
        })
    payload["recruitment_admin"] = admin if recruiter else False
    return payload

async def sync_recruitment_character(db: Session, linked: Any, token: Any) -> None:
    from app.api.esi import refresh_access_token
    from app.services.esi_client import EsiClient

    now = datetime.now(timezone.utc)
    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        character = linked.character
        public = await client.get(f"/characters/{character.character_id}/")
        skills = await client.get(f"/characters/{character.character_id}/skills/")
        employment = await client.get(f"/characters/{character.character_id}/corporationhistory/")
        corporation_ids = sorted({int(row["corporation_id"]) for row in employment if row.get("corporation_id")})
        names = await client.post("/universe/names/", corporation_ids) if corporation_ids else []
        name_map = {int(row["id"]): row["name"] for row in names}
        employment_rows: list[dict[str, Any]] = []
        for index, row in enumerate(employment):
            start = datetime.fromisoformat(str(row["start_date"]).replace("Z", "+00:00"))
            end = now if index == 0 else datetime.fromisoformat(str(employment[index - 1]["start_date"]).replace("Z", "+00:00"))
            employment_rows.append({"corporation_id": int(row["corporation_id"]), "corporation_name": name_map.get(int(row["corporation_id"]), f"Corporation {row['corporation_id']}"), "start_date": start.isoformat(), "end_date": end.isoformat(), "duration_days": max(0, (end - start).days), "is_deleted": bool(row.get("is_deleted"))})
        birthday = public.get("birthday")
        birthday_dt = datetime.fromisoformat(str(birthday).replace("Z", "+00:00")) if birthday else None
        corporation_id = int(public["corporation_id"]) if public.get("corporation_id") else None
        corporation_name = name_map.get(corporation_id) if corporation_id else None
        alliance_id = int(public["alliance_id"]) if public.get("alliance_id") else None
        alliance_name = None
        if alliance_id:
            alliance_name = (await client.get(f"/alliances/{alliance_id}/")).get("name")
        character.name = public.get("name") or character.name
        character.security_status = public.get("security_status")
        character.total_skill_points = int(skills.get("total_sp") or 0)
        character.portrait_url = f"https://images.evetech.net/characters/{character.character_id}/portrait?size=128"
        character.last_synced_at = now
        scopes = sorted(scope for scope in str(token.scopes or "").split() if scope)
        durations = [row["duration_days"] for row in employment_rows]
        recent = {str(days): sum(1 for row in employment_rows if (now - datetime.fromisoformat(row["start_date"])).days <= days) for days in (30, 90, 365)}
        linked.snapshot_json = {"birthday": birthday, "character_age_days": (now - birthday_dt).days if birthday_dt else None, "corporation_id": corporation_id, "corporation_name": corporation_name, "alliance_id": alliance_id, "alliance_name": alliance_name, "security_status": character.security_status, "total_skill_points": character.total_skill_points, "corporation_changes": max(0, len(employment_rows) - 1), "average_tenure_days": round(sum(durations) / len(durations), 1) if durations else None, "shortest_tenure_days": min(durations) if durations else None, "longest_tenure_days": max(durations) if durations else None, "changes_within_days": recent, "data_source": "live ESI"}
        linked.employment_history_json = employment_rows
        linked.granted_scopes_json = scopes
        linked.token_health = "healthy"
        linked.verification_status = "verified"
        linked.last_successful_sync_at = now
        linked.last_sync_error = None
    except Exception as exc:
        linked.token_health = "error"
        linked.verification_status = "stale" if linked.last_successful_sync_at else "failed"
        linked.last_sync_error = str(getattr(exc, "detail", exc))[:2000]
