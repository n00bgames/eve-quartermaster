from app.services.skill_dogma import _attribute_label, _bonus_rows, _plain_text


def test_plain_text_removes_sde_markup_and_decodes_entities() -> None:
    assert _plain_text("bonus to <a href=showinfo:3326>Cruise Missile</a>&nbsp;velocity") == "bonus to Cruise Missile velocity"


def test_bonus_rows_preserve_value_unit_and_english_text() -> None:
    rows = _bonus_rows([{
        "bonus": 5,
        "bonusText": {"en": "bonus to <a href=showinfo:3325>Torpedo</a> rate of fire"},
        "importance": 1,
        "unitID": 105,
    }])
    assert rows == [{"value": 5.0, "unit_id": 105, "text": "bonus to Torpedo rate of fire", "importance": 1}]


def test_dogma_attribute_names_receive_readable_fallback_labels() -> None:
    assert _attribute_label("maxFlightTimeBonus", None) == "missile flight time"
    assert _attribute_label("scanResolutionBonus", None) == "scan resolution"
