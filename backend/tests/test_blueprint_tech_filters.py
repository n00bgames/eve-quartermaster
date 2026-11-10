import csv
import io
import json
import unittest
from app.api.quartermaster import blueprint_matches_export_filters, export_blueprints, list_blueprints
from app.models import Blueprint, EveCategory, EveDogmaAttribute, EveTypeDogmaAttribute, User
from tests import test_blueprint_library_research_shadow as fixtures

class BlueprintTechFilterTests(unittest.TestCase):
    setUp = fixtures.BlueprintLibraryResearchShadowTests.setUp
    tearDown = fixtures.BlueprintLibraryResearchShadowTests.tearDown
    add_active_project = fixtures.BlueprintLibraryResearchShadowTests.add_active_project

    def add_tech(self, tech):
        self.db.add(EveDogmaAttribute(attribute_id=422, name="techLevel"))
        self.db.add(EveTypeDogmaAttribute(type_id=self.product_type.type_id, attribute_id=422, value=tech))
        self.db.flush()

    def test_owned_blueprint_uses_manufacturing_product_tech_and_exports(self):
        self.add_tech(2)
        self.db.add(Blueprint(ownership_entity_id=self.owner.id, blueprint_type_id=self.blueprint_type.type_id,
                              material_efficiency=0, time_efficiency=0, is_copy=True))
        self.db.commit()
        rows=list_blueprints(current_user=self.user, db=self.db)
        self.assertEqual(rows[0]["product_tech_level"], 2)
        self.assertEqual(rows[0]["product_type_id"], self.product_type.type_id)
        for tech, expected in [("2",1),("3",0),("all",1)]:
            result=export_blueprints({"format":"json","scope":"filtered","filters":{"tech_level":tech}},current_user=self.user,db=self.db)
            self.assertEqual(len(json.loads(result["content"])["records"]),expected)
        result=export_blueprints({"format":"json","scope":"all","filters":{"tech_level":"3"}},current_user=self.user,db=self.db)
        self.assertEqual(result["row_count"],1)

    def test_research_shadow_inherits_product_technology(self):
        self.add_tech(3); self.add_active_project(); self.db.commit()
        rows=list_blueprints(current_user=self.user,db=self.db)
        self.assertTrue(rows[0]["research_shadow"])
        self.assertEqual(rows[0]["product_tech_level"],3)

    def test_unknown_product_technology_is_not_guessed(self):
        self.add_active_project(); self.db.commit()
        row=list_blueprints(current_user=self.user,db=self.db)[0]
        self.assertIsNone(row["product_tech_level"])
        self.assertFalse(blueprint_matches_export_filters(row,{"tech_level":"2"},{}))
        self.assertTrue(blueprint_matches_export_filters(row,{},{}))

    def test_product_filters_and_existing_filters_intersect(self):
        row={"product_tech_level":3,"product_category_id":32,"owner_name":"Demo", "is_copy":True,"inventory_subtype":"Defensive Subsystem"}
        filters={"tech_level":"3","product_category":"modules","kind":"bpc","owner":"Demo","subtype":"Defensive Subsystem"}
        self.assertTrue(blueprint_matches_export_filters(row,filters,{}))
        for changed in [{"product_category":"ships"},{"owner":"Other"},{"kind":"bpo"},{"tech_level":"2"}]:
            self.assertFalse(blueprint_matches_export_filters(row,{**filters,**changed},{}))
        self.assertTrue(blueprint_matches_export_filters({**row,"product_category_id":7},filters,{}))
        self.assertFalse(blueprint_matches_export_filters({**row,"product_category_id":8},filters,{}))

    def test_subsystem_csv_matches_filter_and_keeps_empty_header(self):
        self.add_tech(3)
        self.product_type.group.category = EveCategory(category_id=32, name="Subsystem")
        self.db.add(Blueprint(ownership_entity_id=self.owner.id, blueprint_type_id=self.blueprint_type.type_id,
                              material_efficiency=0, time_efficiency=0, is_copy=True))
        self.db.commit()
        def export(category):
            return export_blueprints({"format":"csv","scope":"filtered","filters":{"tech_level":"3","product_category":category}},current_user=self.user,db=self.db)
        matching=export("modules")
        rows=list(csv.DictReader(io.StringIO(matching["content"].lstrip("\ufeff"))))
        self.assertEqual(len(rows),1)
        self.assertEqual(float(rows[0]["product_tech_level"]),3)
        empty=export("ships")
        self.assertEqual(empty["row_count"],0)
        self.assertEqual(matching["content"].splitlines()[0],empty["content"].splitlines()[0])

    def test_technology_metadata_does_not_expose_private_blueprints(self):
        self.add_tech(2)
        self.db.add(Blueprint(ownership_entity_id=self.owner.id, blueprint_type_id=self.blueprint_type.type_id,
                              material_efficiency=0, time_efficiency=0, is_copy=True))
        viewer=User(email="other@example.test",display_name="Other",role="member")
        self.db.add(viewer); self.db.commit()
        self.assertEqual(list_blueprints(current_user=viewer,db=self.db),[])
        result=export_blueprints({"format":"json","scope":"filtered","filters":{"tech_level":"2"}},current_user=viewer,db=self.db)
        self.assertEqual(result["row_count"],0)
