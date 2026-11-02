"""Explicit battle boundaries, independent of the selected pilot's participation."""
from datetime import datetime, timedelta, timezone
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class BattleWindow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start_time: datetime
    end_time: datetime
    system_ids: list[Annotated[int, Field(gt=0, le=2147483647, strict=True)]] = Field(min_length=1, max_length=8)

    @model_validator(mode='after')
    def bounded(self):
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError('Battle times must include a timezone; the editor uses UTC.')
        self.start_time, self.end_time = utc(self.start_time), utc(self.end_time)
        if not timedelta(0) < self.end_time-self.start_time <= timedelta(hours=12):
            raise ValueError('Choose a positive battle window of at most 12 hours.')
        if self.end_time > datetime.now(timezone.utc)+timedelta(hours=1):
            raise ValueError('Battle end cannot be more than one hour in the future.')
        self.system_ids = sorted(set(self.system_ids))
        return self
