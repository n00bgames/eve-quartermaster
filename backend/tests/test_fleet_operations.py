from __future__ import annotations

from datetime import date, datetime, time, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.doctrines import create_doctrine
from app.api.skill_plans import create_plan, merge_preview
from app.api.srp import create_operation, create_request, intake_context, transition_request
from app.models import (
    AppSetting, Base, CharacterFitting, CharacterFittingItem, Doctrine, DoctrinePriorityField,
    DoctrinePriorityOption, EveAlliance, EveCharacter, EveCorporation, EveDogmaAttribute,
    EveType, EveTypeDogmaAttribute, SkillPlan, SkillPlanEntry, SrpRequest, SrpRequestEvent, User,
)
from app.schemas.fleet_operations import DoctrineInput, SkillPlanInput, SkillPlanMergeInput, SrpOperationInput, SrpRequestInput, SrpTransitionInput
from app.services.doctrine_priority import validate_priority_values
from app.services.skill_plan_generator import generate_fitting_skill_plan, merge_requirement
from app.services.srp import normalize_loss_datetime, validate_srp_transition


def test_priority_fields_validate_allowed_values_and_generate_code() -> None:
    field = SimpleNamespace(
        id=1, key="strategic", name="Strategic Importance", field_type="select", is_required=True,
        display_order=0, is_active=True,
        options=[SimpleNamespace(value="critical", short_code="C", is_active=True)],
    )
    values, code = validate_priority_values([field], {"strategic": "critical"})
    assert values == {"strategic": "critical"}
    assert code == "C"
    with pytest.raises(HTTPException, match="Invalid value"):
        validate_priority_values([field], {"strategic": "casual"})


def test_skill_requirement_merge_deduplicates_at_highest_level() -> None:
    requirements = {}
    merge_requirement(requirements, 3300, 1, "Hull")
    merge_requirement(requirements, 3300, 4, "Module")
    merge_requirement(requirements, 3300, 2, "Drone")
    assert requirements[3300]["target_level"] == 4
    assert requirements[3300]["introduced_by"] == ["Hull", "Module", "Drone"]


def test_loss_datetime_preserves_entered_eve_time_as_utc() -> None:
    value = normalize_loss_datetime(date(2026, 8, 13), time(21, 45))
    assert value.isoformat() == "2026-08-13T21:45:00+00:00"
    assert value.tzinfo == timezone.utc


def test_srp_transitions_are_server_validated() -> None:
    validate_srp_transition("draft", "submitted", manager=False)
    with pytest.raises(HTTPException, match="Cannot move"):
        validate_srp_transition("submitted", "paid", manager=True)
    with pytest.raises(HTTPException, match="officer"):
        validate_srp_transition("submitted", "under_review", manager=False)


class TestFleetOperationsIntegration:
    def setup_method(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.host = User(email="host@fleet.test", display_name="Fleet Host", role="host")
        self.member = User(email="member@fleet.test", display_name="Fleet Member", role="member")
        self.db.add_all([self.host, self.member]); self.db.flush()
        self.character = EveCharacter(character_id=91_000_123, name="Doctrine Pilot", owner_user_id=self.member.id)
        self.db.add(self.character)
        self.ship = EveType(type_id=100, name="Test Cruiser", published=True)
        self.module = EveType(type_id=101, name="Test Module", published=True)
        self.skill_a = EveType(type_id=201, name="Cruiser Operation", published=True)
        self.skill_b = EveType(type_id=202, name="Spaceship Command", published=True)
        self.charge = EveType(type_id=102, name="Test Charge", published=True)
        self.skill_c = EveType(type_id=203, name="Charge Operation", published=True)
        self.db.add_all([self.ship, self.module, self.skill_a, self.skill_b, self.charge, self.skill_c]); self.db.flush()
        self.fit = CharacterFitting(character_id=self.character.id, name="Canonical Cruiser", ship_type_id=self.ship.type_id, is_shared=True, is_draft=True)
        self.db.add(self.fit); self.db.flush()
        self.db.add(CharacterFittingItem(fitting_id=self.fit.id, type_id=self.module.type_id, charge_type_id=self.charge.type_id, flag="HiSlot0", quantity=1))
        names = ["requiredSkill1", "requiredSkill1Level"]
        attrs = [EveDogmaAttribute(attribute_id=1, name=names[0]), EveDogmaAttribute(attribute_id=2, name=names[1])]
        self.db.add_all(attrs); self.db.flush()
        # Hull needs A I; module needs A III; A needs B II; charge needs C II.
        for type_id, skill_id, level in [(100,201,1),(101,201,3),(201,202,2),(102,203,2)]:
            self.db.add_all([EveTypeDogmaAttribute(type_id=type_id, attribute_id=1, value=skill_id), EveTypeDogmaAttribute(type_id=type_id, attribute_id=2, value=level)])
        field = DoctrinePriorityField(key="tier", name="Tier", field_type="select", is_required=True, display_order=0, created_by_user_id=self.host.id)
        field.options = [DoctrinePriorityOption(label="Primary", value="primary", short_code="P", display_order=0)]
        self.db.add(field); self.db.commit()

    def teardown_method(self) -> None:
        self.db.close(); self.engine.dispose()

    def test_doctrine_plan_generation_and_srp_submission_share_canonical_fit(self) -> None:
        doctrine_payload = DoctrineInput(name="Cruiser Line", purpose="Primary cruiser response", fitting_id=self.fit.id, priority_values={"tier":"primary"})
        doctrine_data = create_doctrine(doctrine_payload, self.host, self.db)
        assert doctrine_data["priority_code"] == "P"
        assert doctrine_data["fitting_id"] == self.fit.id

        preview = generate_fitting_skill_plan(self.db, self.fit.id)
        levels = {row["skill_type_id"]: row["target_level"] for row in preview["entries"]}
        assert levels == {201: 3, 202: 2, 203: 2}
        plan_payload = SkillPlanInput(
            name="Cruiser Minimums", character_id=self.character.id, fitting_id=self.fit.id,
            source_doctrine_id=doctrine_data["id"], source="doctrine",
            entries=[{"skill_type_id": row["skill_type_id"], "target_level": row["target_level"], "sort_order": row["sort_order"], "introduced_by": row["introduced_by"]} for row in preview["entries"]],
        )
        plan_data = create_plan(plan_payload, self.member, self.db)
        assert len(plan_data["entries"]) == 3

        srp_payload = SrpRequestInput(character_id=self.character.id, fitting_id=self.fit.id, doctrine_id=doctrine_data["id"], loss_date=date(2026,8,13), loss_time=time(21,45), status="submitted")
        srp_data = create_request(srp_payload, self.member, self.db)
        assert srp_data["status"] == "submitted"
        assert srp_data["fitting_id"] == doctrine_data["fitting_id"]
        assert srp_data["loss_occurred_at"].startswith("2026-08-13T21:45:00")

        reviewed = transition_request(srp_data["id"], SrpTransitionInput(status="under_review"), self.host, self.db)
        assert reviewed["status"] == "under_review"

    def test_doctrine_can_hold_multiple_fits_and_srp_accepts_non_primary_fit(self) -> None:
        alternate = CharacterFitting(
            character_id=self.character.id, name="Alternate Cruiser", ship_type_id=self.ship.type_id,
            is_shared=True, is_draft=True,
        )
        self.db.add(alternate); self.db.flush()
        self.db.add(CharacterFittingItem(fitting_id=alternate.id, type_id=self.module.type_id, flag="HiSlot0", quantity=2))
        self.db.commit()
        doctrine = create_doctrine(DoctrineInput(
            name="Cruiser Wing", purpose=None, fitting_ids=[self.fit.id, alternate.id],
            primary_fitting_id=self.fit.id, priority_values={"tier": "primary"},
        ), self.host, self.db)
        assert doctrine["fitting_id"] == self.fit.id
        assert [row["fitting_id"] for row in doctrine["fittings"]] == [self.fit.id, alternate.id]
        assert doctrine["fittings"][0]["is_primary"] is True

        request = create_request(SrpRequestInput(
            character_id=self.character.id, fitting_id=alternate.id, doctrine_id=doctrine["id"],
            loss_date=date(2026, 8, 13), loss_time=time(22, 10), status="draft",
        ), self.member, self.db)
        assert request["fitting_id"] == alternate.id
        assert request["doctrine_id"] == doctrine["id"]

    def test_doctrine_links_multiple_fitting_specific_plans_and_plans_merge(self) -> None:
        alternate = CharacterFitting(character_id=self.character.id, name="Alternate Cruiser", ship_type_id=self.ship.type_id, is_shared=True, is_draft=True)
        self.db.add(alternate); self.db.commit()
        plan_a = create_plan(SkillPlanInput(name="Core Hull", entries=[
            {"skill_type_id": self.skill_a.type_id, "target_level": 3, "sort_order": 0},
            {"skill_type_id": self.skill_b.type_id, "target_level": 2, "sort_order": 1},
        ]), self.member, self.db)
        plan_b = create_plan(SkillPlanInput(name="Alternate Weapons", entries=[
            {"skill_type_id": self.skill_a.type_id, "target_level": 5, "sort_order": 0},
            {"skill_type_id": self.skill_c.type_id, "target_level": 2, "sort_order": 1},
        ]), self.member, self.db)
        doctrine = create_doctrine(DoctrineInput(
            name="Multi-plan Wing", fitting_ids=[self.fit.id, alternate.id], primary_fitting_id=self.fit.id,
            priority_values={"tier": "primary"}, skill_plan_links=[
                {"skill_plan_id": plan_a["id"], "fitting_id": self.fit.id},
                {"skill_plan_id": plan_b["id"], "fitting_id": alternate.id},
            ],
        ), self.host, self.db)
        assert [(row["skill_plan_id"], row["fitting_id"]) for row in doctrine["skill_plan_links"]] == [
            (plan_a["id"], self.fit.id), (plan_b["id"], alternate.id),
        ]
        merged = merge_preview(SkillPlanMergeInput(plan_ids=[plan_a["id"], plan_b["id"]]), self.host, self.db)
        assert merged["source"] == "merged"
        assert {entry["skill_type_id"]: entry["target_level"] for entry in merged["entries"]} == {
            self.skill_a.type_id: 5, self.skill_b.type_id: 2, self.skill_c.type_id: 2,
        }

    def test_staff_created_srp_instance_generates_link_and_locks_submission_context(self) -> None:
        doctrine_data = create_doctrine(DoctrineInput(name="Defense Line", purpose="Home defense", fitting_id=self.fit.id,
                                                       priority_values={"tier":"primary"}), self.host, self.db)
        operation = create_operation(SrpOperationInput(name="Armor Timer", start_at=datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc),
                                                        doctrine_id=doctrine_data["id"]), self.host, self.db)
        assert operation["submission_url"].endswith(f"#srp/submit/{operation['share_token']}")
        assert intake_context(operation["share_token"], self.member, self.db)["name"] == "Armor Timer"
        submitted = create_request(SrpRequestInput(character_id=self.character.id, fitting_id=self.fit.id,
            operation_token=operation["share_token"], loss_date=date(2026, 8, 13), loss_time=time(21, 45), status="submitted"), self.member, self.db)
        assert submitted["operation_name"] == "Armor Timer"
        assert submitted["doctrine_name"] == "Defense Line"
        assert submitted["fitting_snapshot"]["name"] == "Canonical Cruiser"
        assert self.db.query(SrpRequestEvent).filter_by(request_id=submitted["id"], event_type="submitted").count() == 1
