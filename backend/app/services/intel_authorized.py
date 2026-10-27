"""Permission-scoped private enrichment. Never persisted in public intel records."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import CharacterFitting, CharacterSkill, CharacterSkillQueueEntry, EsiSyncJob, EsiToken, EveCharacter, EveType, RecruitmentApplication, RecruitmentLinkedCharacter, User
from app.models.enums import SyncStatus
from app.services.permissions import can_view_section
from app.services.recruiting import is_recruiter


def authorized_context(db: Session, user: User, subject):
    if subject.kind != "character": return None
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == subject.eve_id))
    if character is None or character.owner_user_id is None or character.sync_opt_out: return None
    token = db.scalar(select(EsiToken).where(EsiToken.character_id == character.id, EsiToken.user_id == character.owner_user_id, EsiToken.revoked_at.is_(None)).order_by(EsiToken.id.desc()))
    if token is None: return None
    link = db.scalar(select(RecruitmentLinkedCharacter).join(RecruitmentApplication, RecruitmentApplication.id == RecruitmentLinkedCharacter.application_id).where(
        RecruitmentLinkedCharacter.character_id == character.id, RecruitmentApplication.applicant_user_id == token.user_id,
        RecruitmentLinkedCharacter.verification_status.in_(["verified","stale"]), RecruitmentApplication.status.not_in(["Withdrawn","Declined"])))
    applicant_access = bool(link and is_recruiter(db,user) and can_view_section(user,"recruiting",db))
    from app.api.characters import can_view_character_detail
    regular_access = can_view_section(user,"characters",db) and can_view_character_detail(user,character,db)
    if not (regular_access or applicant_access): return None
    return character, token, link if applicant_access else None, regular_access


def private_enrichment(db: Session, user: User, subject) -> dict:
    context = authorized_context(db,user,subject)
    if context is None: return {"state":"not_authorized", "notice":"Private ESI data is unavailable to this viewer. This is not a risk signal."}
    character, token, link, regular = context
    scopes = set(token.scopes.split())
    if link and not regular: scopes &= set(link.granted_scopes_json or [])
    result = {"state":"authorized", "scopes":sorted(scopes), "source":"Authorized EQM cache", "datasets":{}}
    if "esi-skills.read_skills.v1" in scopes and (link or (regular and can_view_section(user,"skills",db))):
        if character.skills_synced_at or (link and link.last_successful_sync_at):
            rows = db.execute(select(CharacterSkill,EveType.name).outerjoin(EveType,EveType.type_id==CharacterSkill.skill_type_id).where(CharacterSkill.character_id==character.id).order_by(CharacterSkill.skillpoints_in_skill.desc()).limit(50)).all()
            result["datasets"]["skills"] = {"state":"available","total_sp":character.total_skill_points,"synced_at":str(character.skills_synced_at or link.last_successful_sync_at),
                "top_skills":[{"id":row.skill_type_id,"name":name or f"Type {row.skill_type_id}","trained_level":row.trained_skill_level,"active_level":row.active_skill_level} for row,name in rows]}
        else: result["datasets"]["skills"]={"state":"not_collected"}
    else: result["datasets"]["skills"]={"state":"not_authorized"}
    if regular and can_view_section(user,"skills",db) and "esi-skills.read_skillqueue.v1" in scopes:
        queue=db.execute(select(CharacterSkillQueueEntry,EveType.name).outerjoin(EveType,EveType.type_id==CharacterSkillQueueEntry.skill_type_id).where(CharacterSkillQueueEntry.character_id==character.id).order_by(CharacterSkillQueueEntry.queue_position).limit(50)).all()
        result["datasets"]["queue"]={"state":"available" if character.skill_queue_synced_at else "not_collected","synced_at":str(character.skill_queue_synced_at) if character.skill_queue_synced_at else None,
            "entries":[{"name":name or f"Type {row.skill_type_id}","level":row.finished_level,"finish":row.finish_date.isoformat() if row.finish_date else None} for row,name in queue] if character.skill_queue_synced_at else []}
    if regular and can_view_section(user,"fittings",db) and "esi-fittings.read_fittings.v1" in scopes:
        rows=db.scalars(select(CharacterFitting).options(selectinload(CharacterFitting.ship_type)).where(CharacterFitting.character_id==character.id).order_by(CharacterFitting.name).limit(100)).all()
        last_sync=db.scalar(select(EsiSyncJob).where(EsiSyncJob.token_id==token.id,EsiSyncJob.sync_type=="character_fittings",EsiSyncJob.status==SyncStatus.SUCCESS).order_by(EsiSyncJob.finished_at.desc()).limit(1))
        result["datasets"]["fittings"]={"state":"available" if rows or last_sync else "not_collected","rows":[{"id":row.id,"name":row.name,"ship":row.ship_type.name if row.ship_type else str(row.ship_type_id),"synced_at":str(row.last_synced_at) if row.last_synced_at else None} for row in rows],"notice":"Saved templates do not prove the fitting was flown."}
    if link:
        # Curated fields only. No application answers, messages, flags, wallet,
        # assets or unrelated linked characters are copied into this response.
        result["applicant"]={"application_id":link.application_id,"verification_status":link.verification_status,"token_health":link.token_health,"last_successful_sync_at":str(link.last_successful_sync_at) if link.last_successful_sync_at else None,
                             "granted_scopes":link.granted_scopes_json}
    from app.api.esi import can_force_sync_character_token
    refresh = []
    if regular and can_force_sync_character_token(token,character,user,db):
        if can_view_section(user,"skills",db) and {"esi-skills.read_skills.v1","esi-skills.read_skillqueue.v1"} <= scopes: refresh.append("skills")
        if can_view_section(user,"fittings",db) and "esi-fittings.read_fittings.v1" in scopes: refresh.append("fittings")
    if link and "esi-skills.read_skills.v1" in scopes: refresh.append("applicant")
    result["refresh_datasets"]=refresh
    return result


async def refresh_authorized(db: Session,user: User,subject,dataset: str) -> dict:
    context=authorized_context(db,user,subject)
    available=private_enrichment(db,user,subject)
    if context is None or dataset not in available.get("refresh_datasets",[]): raise HTTPException(403,"This private ESI dataset is not authorized for refresh")
    character,token,link,_regular=context
    if dataset=="applicant":
        from app.services.recruiting import sync_recruitment_character
        await sync_recruitment_character(db,link,token)
        db.commit()
    else:
        from app.api.esi import sync_character_fittings_for_token, sync_character_skills_for_token
        helper=sync_character_skills_for_token if dataset=="skills" else sync_character_fittings_for_token
        await helper(token.id,user,db,allow_opt_out_override=False)
    return private_enrichment(db,user,subject)
