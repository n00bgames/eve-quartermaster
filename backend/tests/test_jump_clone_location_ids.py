from sqlalchemy import BigInteger, create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, CharacterJumpClone, EveCharacter


def test_jump_clone_location_uses_bigint_and_round_trips_structure_id() -> None:
    assert isinstance(CharacterJumpClone.__table__.c.location_id.type, BigInteger)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[EveCharacter.__table__, CharacterJumpClone.__table__],
    )
    structure_id = 1_022_167_642_188

    with Session(engine) as db:
        character = EveCharacter(character_id=90_000_001, name="Structure Clone Pilot")
        db.add(character)
        db.flush()
        db.add(
            CharacterJumpClone(
                character_id=character.id,
                clone_kind="jump_clone",
                jump_clone_id=178_436_274,
                name="Structure clone",
                location_id=structure_id,
                location_type="structure",
            )
        )
        db.commit()

        saved = db.scalar(select(CharacterJumpClone))
        assert saved is not None
        assert saved.location_id == structure_id

    engine.dispose()
