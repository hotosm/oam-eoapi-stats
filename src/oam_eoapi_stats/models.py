"""Response models and the in-memory snapshot they are served from.

Wording follows STATS.md: an *image* is a scene (one Maxar capture split into many tiles is one image),
an *entry* is a raw catalog item. Area is in km² and always split by resolution (GSD) class.
"""

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

AreaByClass = dict[str, float]


class SetAside(BaseModel):
    items: int = Field(description="Entries left out of area figures for implausible GSD or size")
    area_km2: float = Field(description="Area those entries would have added")


class GroupTotals(BaseModel):
    images: int
    entries: int
    area_km2: AreaByClass = Field(description="Total area by GSD class; overlaps count each time")
    earliest_capture: datetime | None
    latest_capture: datetime | None
    invalid_dates: int = Field(description="Entries whose capture date is outside 1990..tomorrow")
    duplicates: int = Field(description="Extra copies of exact duplicates, whose area is counted once")
    set_aside: SetAside


class Totals(BaseModel):
    generated_at: datetime
    hosted: GroupTotals
    federated: GroupTotals


class PlatformRow(BaseModel):
    platform: str
    images: int
    entries: int
    area_km2: AreaByClass


class YearRow(BaseModel):
    year: int
    images: int
    entries: int
    area_km2: AreaByClass


class LicenceRow(BaseModel):
    licence: str
    images: int
    entries: int
    area_km2: AreaByClass


class CollectionRow(BaseModel):
    collection: str
    images: int
    entries: int
    area_km2: AreaByClass
    earliest_capture: datetime | None
    latest_capture: datetime | None


class Breakdown[RowT: BaseModel](BaseModel):
    generated_at: datetime
    hosted: list[RowT]
    federated: list[RowT]


@dataclass(frozen=True)
class Snapshot:
    generated_at: datetime
    totals: Totals
    platforms: Breakdown[PlatformRow]
    by_year: Breakdown[YearRow]
    licences: Breakdown[LicenceRow]
    collections: Breakdown[CollectionRow]
