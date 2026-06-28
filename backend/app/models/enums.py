import enum


class OwnerKind(str, enum.Enum):
    CHARACTER = "character"
    CORPORATION = "corporation"
    ALLIANCE = "alliance"
    MANUAL_GROUP = "manual_group"


class LocationKind(str, enum.Enum):
    REGION = "region"
    CONSTELLATION = "constellation"
    SYSTEM = "system"
    STATION = "station"
    STRUCTURE = "structure"
    CONTAINER = "container"
    UNKNOWN = "unknown"


class AssetSource(str, enum.Enum):
    ESI = "esi"
    MANUAL = "manual"
    SDE = "sde"


class ActivityKind(str, enum.Enum):
    MANUFACTURING = "manufacturing"
    COPYING = "copying"
    INVENTION = "invention"
    REACTION = "reaction"
    RESEARCH_MATERIAL = "research_material"
    RESEARCH_TIME = "research_time"


class ProcurementKind(str, enum.Enum):
    BUY = "buy"
    MINE = "mine"
    REPROCESS = "reprocess"
    REACT = "react"
    MANUFACTURE = "manufacture"
    STOCKPILE = "stockpile"


class SyncStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
